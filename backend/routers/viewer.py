"""
Data viewer router.

Handles upload / display of NPY, EDF, TIFF and HDF5 images, custom colour-map
generation (smooth_WAXS_foxtrot, smooth_WAXS_fit2D), and PNG export.
"""

from __future__ import annotations

import io
import os
import uuid
from typing import Any, Dict, List, Literal, Optional

import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import UPLOAD_DIR
from utils import _file_path, _save_upload

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory file registry
# ---------------------------------------------------------------------------
_registry: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Format detection & loading
# ---------------------------------------------------------------------------

def _detect_format(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    mapping = {
        ".npy": "npy",
        ".edf": "edf",
        ".tif": "tiff",
        ".tiff": "tiff",
        ".h5": "hdf5",
        ".hdf5": "hdf5",
        ".hdf": "hdf5",
    }
    return mapping.get(ext, "unknown")


def _load_2d(path: str, fmt: str, channel: int = 0) -> np.ndarray:
    """
    Load a 2-D slice from a file.

    For HDF5 files, selects the *channel*-th dataset / slice from a
    multi-dimensional array.
    """
    if fmt == "npy":
        arr = np.load(path, allow_pickle=True)
        if arr.ndim > 2:
            arr = arr[channel] if channel < arr.shape[0] else arr[0]
        return arr.astype(np.float64)

    if fmt == "edf":
        import fabio
        img = fabio.open(path)
        return img.data.astype(np.float64)

    if fmt == "tiff":
        try:
            import fabio
            img = fabio.open(path)
            return img.data.astype(np.float64)
        except Exception:
            from PIL import Image
            return np.array(Image.open(path)).astype(np.float64)

    if fmt == "hdf5":
        import h5py
        with h5py.File(path, "r") as h5:
            # Walk to first suitable dataset
            datasets: list[str] = []

            def _visitor(name, obj):
                if isinstance(obj, h5py.Dataset) and obj.ndim >= 2:
                    datasets.append(name)

            h5.visititems(_visitor)
            if not datasets:
                raise ValueError("No 2-D+ dataset found in HDF5 file")
            ds_name = datasets[min(channel, len(datasets) - 1)]
            data = h5[ds_name][...]
            # Modern Eiger-style HDF5 files are often 4-D (1,1,y,x).
            # Squeeze singleton dims first, then take the requested frame.
            data = np.squeeze(data)
            if data.ndim > 2:
                data = data[channel] if channel < data.shape[0] else data[0]
            return data.astype(np.float64)

    raise ValueError(f"Unsupported format: {fmt}")


# ---------------------------------------------------------------------------
# Custom colormaps
# ---------------------------------------------------------------------------

def _smooth_waxs_foxtrot() -> "matplotlib.colors.LinearSegmentedColormap":
    """
    Custom colormap inspired by the Foxtrot WAXS viewer: dark-blue -> cyan ->
    green -> yellow -> red -> white.
    """
    import matplotlib.colors as mcolors

    colours = [
        (0.0, 0.0, 0.2),   # dark blue
        (0.0, 0.3, 0.6),   # blue
        (0.0, 0.7, 0.7),   # cyan
        (0.0, 0.8, 0.0),   # green
        (0.9, 0.9, 0.0),   # yellow
        (0.9, 0.3, 0.0),   # orange
        (0.9, 0.0, 0.0),   # red
        (0.6, 0.0, 0.0),   # dark red
        (1.0, 1.0, 1.0),   # white
    ]
    return mcolors.LinearSegmentedColormap.from_list("smooth_WAXS_foxtrot", colours, N=256)


def _smooth_waxs_fit2d() -> "matplotlib.colors.LinearSegmentedColormap":
    """
    Custom colormap inspired by fit2D: black -> purple -> blue -> cyan ->
    green -> yellow -> white.
    """
    import matplotlib.colors as mcolors

    colours = [
        (0.0, 0.0, 0.0),   # black
        (0.3, 0.0, 0.5),   # purple
        (0.0, 0.0, 0.8),   # blue
        (0.0, 0.5, 0.8),   # cyan-blue
        (0.0, 0.8, 0.5),   # cyan-green
        (0.0, 0.8, 0.0),   # green
        (0.8, 0.8, 0.0),   # yellow
        (1.0, 1.0, 0.5),   # light yellow
        (1.0, 1.0, 1.0),   # white
    ]
    return mcolors.LinearSegmentedColormap.from_list("smooth_WAXS_fit2D", colours, N=256)


def _electric() -> "matplotlib.colors.LinearSegmentedColormap":
    """
    The plotly 'Electric' colorscale (no matplotlib equivalent) — built from
    plotly's own stops so display and export stay identical.
    """
    import matplotlib.colors as mcolors

    colours = [
        (0.0, 0.0, 0.0),
        (30 / 255, 0.0, 100 / 255),
        (120 / 255, 0.0, 100 / 255),
        (160 / 255, 90 / 255, 0.0),
        (230 / 255, 200 / 255, 0.0),
        (1.0, 250 / 255, 220 / 255),
    ]
    return mcolors.LinearSegmentedColormap.from_list("electric", colours, N=256)


_CUSTOM_CMAPS = {
    "smooth_WAXS_foxtrot": _smooth_waxs_foxtrot,
    "smooth_WAXS_fit2D": _smooth_waxs_fit2d,
    "electric": _electric,
}


# Plotly sends capitalized colorscale names ("Viridis", "Gray", ...); the
# matplotlib registry keys are lowercase. Map the frontend's option values to
# their matplotlib equivalents so the exported PNG matches what is on screen.
_CMAP_ALIASES = {
    "grey": "gray",
    "greys": "gray",
    "grayscale": "gray",
    "greyscale": "gray",
}


def _get_cmap(name: str):
    """Return a matplotlib colormap by name, including custom ones.

    Name lookup is case-insensitive with a few alias rewrites; unknown names
    fall back to viridis (matching the previous behaviour). Uses the
    ``matplotlib.colormaps`` registry — ``matplotlib.cm.get_cmap`` was removed
    in matplotlib 3.9, which silently broke every export with an AttributeError.
    """
    import matplotlib

    key = (name or "").strip().lower()
    if name in _CUSTOM_CMAPS:
        return _CUSTOM_CMAPS[name]()
    if key in _CUSTOM_CMAPS:
        return _CUSTOM_CMAPS[key]()
    key = _CMAP_ALIASES.get(key, key)
    try:
        return matplotlib.colormaps[key]
    except (KeyError, ValueError, AttributeError, TypeError):
        return matplotlib.colormaps["viridis"]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class FileMeta(BaseModel):
    fileId: str
    originalName: str
    format: str
    shape: List[int]
    dtype: str
    ndim: int
    size: int


class UploadResponse(BaseModel):
    files: List[FileMeta]


class ImageResponse(BaseModel):
    fileId: str
    shape: List[int]
    displayShape: List[int]
    # Cells may be null where the source array held NaN/inf (pyFAI empty bins /
    # sentinels); Plotly renders nulls as gaps. bare NaN tokens are not valid
    # JSON and would break the client's JSON.parse.
    data: List[List[Optional[float]]]
    min: float
    max: float


class AxisParamsMixin(BaseModel):
    """Physical-axis system shared by single and batch export.

    Mirrors services/axes.js on the frontend so the exported PNG shows the
    same coordinates as the viewer: the underlying grid is q (Å⁻¹, cols) ×
    χ (°, rows); ``xAxis`` re-labels q as 2θ or d-spacing and ``yAxis``
    re-labels χ as azimuth. The optional χ crop window crops full-resolution
    rows before rendering (the on-screen crop only clamps the axis range).
    """
    xAxis: Literal["q", "2theta", "d"] = Field("q")
    yAxis: Literal["chi", "azimuth"] = Field("chi")
    wavelengthAngstrom: float = Field(1.5418, gt=0, description="λ for the 2θ axis (Å, default Cu Kα)")
    axisQMin: Optional[float] = None
    axisQMax: Optional[float] = None
    axisChiMin: Optional[float] = None
    axisChiMax: Optional[float] = None
    cropChiMin: Optional[float] = None
    cropChiMax: Optional[float] = None


class ExportRequest(AxisParamsMixin):
    fileId: str
    colormap: str = Field("viridis")
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    logScale: bool = Field(False)
    dpi: int = Field(150, ge=50, le=600)
    showAxes: bool = Field(True)
    showColorbar: bool = Field(True, description="Draw the intensity colorbar beside the image")
    channel: int = Field(0, ge=0)


class BatchExportItem(BaseModel):
    fileId: str
    name: Optional[str] = Field(None, description="Base name for the PNG inside the ZIP")


class BatchExportRequest(AxisParamsMixin):
    """Render several uploaded images as PNGs with shared settings, zipped."""
    files: List[BatchExportItem]
    colormap: str = Field("viridis")
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    logScale: bool = Field(False)
    dpi: int = Field(150, ge=50, le=600)
    showAxes: bool = Field(True)
    showColorbar: bool = Field(True)
    channel: int = Field(0, ge=0)


class FileInfo(BaseModel):
    fileId: str
    originalName: str
    format: str
    shape: List[int]
    dtype: str


# ---------------------------------------------------------------------------
# Endpoints  (C9: sync def for CPU-bound work)
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse)
def upload_files(files: List[UploadFile] = File(...)):
    """Upload viewer files (NPY/EDF/TIFF/H5)."""
    try:
        metas: list[FileMeta] = []
        for f in files:
            raw = f.file.read()
            ext = os.path.splitext(f.filename or "")[1]
            fmt = _detect_format(f.filename or "")
            if fmt == "unknown":
                # Skip non-image files (e.g. .txt, .csv)
                continue
            fid = _save_upload(raw, suffix=ext)
            path = os.path.join(UPLOAD_DIR, fid)

            try:
                arr = _load_2d(path, fmt)
            except Exception:
                # If loading fails, skip this file
                continue
            meta = FileMeta(
                fileId=fid,
                originalName=f.filename or "unknown",
                format=fmt,
                shape=list(arr.shape),
                dtype=str(arr.dtype),
                ndim=arr.ndim,
                size=int(arr.size),
            )
            _registry[fid] = meta.model_dump()
            metas.append(meta)
        return UploadResponse(files=metas)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.get("/image/{fileId}", response_model=ImageResponse)
def get_image(
    fileId: str,
    chiMin: Optional[float] = Query(None),
    chiMax: Optional[float] = Query(None),
    vmin: Optional[float] = Query(None),
    vmax: Optional[float] = Query(None),
    channel: int = Query(0, ge=0),
    max_dim: int = Query(512, ge=64),
):
    """Get image data for display with optional chi-range crop and value clipping."""
    try:
        meta = _registry.get(fileId)
        fmt = meta["format"] if meta else _detect_format(fileId)
        path = _file_path(fileId)
        arr = _load_2d(path, fmt, channel=channel)

        # Chi-range crop (first axis)
        if chiMin is not None or chiMax is not None:
            nrows = arr.shape[0]
            r0 = int(chiMin) if chiMin is not None else 0
            r1 = int(chiMax) if chiMax is not None else nrows
            r0 = max(0, min(r0, nrows - 1))
            r1 = max(r0 + 1, min(r1, nrows))
            arr = arr[r0:r1]

        # Downsample for display
        from scipy.ndimage import zoom

        h, w = arr.shape
        if h > max_dim or w > max_dim:
            factor = min(max_dim / h, max_dim / w)
            display = zoom(arr, factor)
        else:
            display = arr

        # Value clipping
        if vmin is not None:
            display = np.clip(display, vmin, None)
        if vmax is not None:
            display = np.clip(display, None, vmax)

        # Cake arrays commonly carry NaN/inf sentinels where pyFAI left empty
        # bins or upstream tools wrote a fill value. JSON cannot transport bare
        # NaN tokens (clients' JSON.parse rejects them), so emit null for those
        # cells — Plotly renders nulls as gaps — and report finite-only stats.
        finite = display[np.isfinite(display)]
        if finite.size:
            dmin = float(finite.min())
            dmax = float(finite.max())
        else:
            dmin = dmax = 0.0

        if not np.isfinite(display).all():
            obj = display.astype(object)
            obj[~np.isfinite(display)] = None
            payload = obj.tolist()
        else:
            payload = display.tolist()

        return ImageResponse(
            fileId=fileId,
            shape=list(arr.shape),
            displayShape=list(display.shape),
            data=payload,
            min=dmin,
            max=dmax,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


def _q_to_x(q: np.ndarray, mode: str, wavelength_angstrom: float) -> np.ndarray:
    """q (Å⁻¹) → display x. Mirrors qToX() in frontend services/axes.js."""
    if mode == "d":
        return (2.0 * np.pi) / np.maximum(q, 1e-6)
    if mode == "2theta":
        s = np.clip(q * wavelength_angstrom / (4.0 * np.pi), -1.0, 1.0)
        return np.degrees(2.0 * np.arcsin(s))
    return q


def _chi_to_y(chi: np.ndarray, mode: str) -> np.ndarray:
    """χ (°) → display y. Mirrors chiToY() in frontend services/axes.js."""
    return chi + 180.0 if mode == "azimuth" else chi


_X_LABELS = {"q": "q (Å$^{-1}$)", "2theta": "2θ (°)", "d": "d (Å)"}
_Y_LABELS = {"chi": "χ (°)", "azimuth": "azimuth (°)"}


def _crop_rows(
    arr: np.ndarray,
    chi_min: Optional[float],
    chi_max: Optional[float],
    crop_min: Optional[float],
    crop_max: Optional[float],
) -> np.ndarray:
    """Crop rows to the χ window [crop_min, crop_max] using the linear
    row↔χ mapping defined by [chi_min, chi_max]."""
    if crop_min is None and crop_max is None:
        return arr
    if chi_min is None or chi_max is None or arr.shape[0] < 2 or chi_max == chi_min:
        return arr
    rows = arr.shape[0]
    span = chi_max - chi_min
    lo, hi = (crop_min, crop_max) if span > 0 else (crop_max, crop_min)
    if lo is None:
        r0 = 0
    else:
        r0 = int(np.ceil((lo - chi_min) / span * (rows - 1)))
    if hi is None:
        r1 = rows
    else:
        r1 = int(np.floor((hi - chi_min) / span * (rows - 1))) + 1
    r0 = max(0, min(r0, rows - 1))
    r1 = max(r0 + 1, min(r1, rows))
    return arr[r0:r1]


def _render_png_bytes(
    arr: np.ndarray,
    *,
    colormap: str,
    vmin: Optional[float],
    vmax: Optional[float],
    logScale: bool,
    dpi: int,
    showAxes: bool,
    showColorbar: bool,
    title: Optional[str] = None,
    xAxis: str = "q",
    yAxis: str = "chi",
    wavelengthAngstrom: float = 1.5418,
    axisQMin: Optional[float] = None,
    axisQMax: Optional[float] = None,
    axisChiMin: Optional[float] = None,
    axisChiMax: Optional[float] = None,
    cropChiMin: Optional[float] = None,
    cropChiMax: Optional[float] = None,
) -> bytes:
    """Render a 2-D array to PNG bytes (shared by single and batch export).

    Without axis extents the image is drawn with pixel-index axes (legacy
    behaviour). With axis extents the physical coordinate system is applied —
    including the q→2θ/d and χ→azimuth display modes — and the optional χ
    crop window removes full-resolution rows before rendering, so the export
    matches the on-screen view.
    """
    import math

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    has_axes = (
        axisQMin is not None and axisQMax is not None
        and axisChiMin is not None and axisChiMax is not None
    )

    if has_axes:
        arr = _crop_rows(arr, axisChiMin, axisChiMax, cropChiMin, cropChiMax)
        rows, cols = arr.shape
        q_grid = np.linspace(axisQMin, axisQMax, cols) if cols > 1 else np.array([axisQMin])
        # After cropping, the visible χ band is the cropped window itself.
        chi_lo = axisChiMin if cropChiMin is None else cropChiMin
        chi_hi = axisChiMax if cropChiMax is None else cropChiMax
        if chi_hi < chi_lo:
            chi_lo, chi_hi = chi_hi, chi_lo
        chi_grid = np.linspace(chi_lo, chi_hi, rows) if rows > 1 else np.array([chi_lo])
        x_grid = _q_to_x(q_grid, xAxis, wavelengthAngstrom)
        y_grid = _chi_to_y(chi_grid, yAxis)
    else:
        x_grid = y_grid = None

    if logScale:
        # Mirror the frontend display path exactly: log10(v) for v > 0, NaN
        # (blank) otherwise, and the contrast window mapped into the log
        # domain. Applying vmin/vmax in linear units to log-transformed data
        # clamps the whole image to a single color.
        arr = np.asarray(arr, dtype=np.float64).copy()
        arr[arr <= 0] = np.nan
        with np.errstate(invalid="ignore"):
            arr = np.log10(arr)
        vmin = math.log10(vmin) if (vmin is not None and vmin > 0) else None
        vmax = math.log10(vmax) if (vmax is not None and vmax > 0) else None

    cmap = _get_cmap(colormap)

    fig, ax = plt.subplots(figsize=(8, 6))
    if has_axes:
        if xAxis in ("d", "2theta"):
            # Non-linear x transform needs a real coordinate grid; pcolormesh
            # accepts monotonic (descending ok) 1-D x/y with shading='nearest'.
            im = ax.pcolormesh(x_grid, y_grid, np.asarray(arr, dtype=np.float64),
                               cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest")
        else:
            im = ax.imshow(
                arr,
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                aspect="auto",
                origin="lower",
                extent=[float(x_grid[0]), float(x_grid[-1]), float(y_grid[0]), float(y_grid[-1])],
            )
        ax.set_xlabel(_X_LABELS.get(xAxis, "q (Å$^{-1}$)"))
        ax.set_ylabel(_Y_LABELS.get(yAxis, "χ (°)"))
    else:
        im = ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto", origin="lower")
        ax.set_xlabel("q (pixels)")
        ax.set_ylabel("chi (pixels)")

    if showColorbar:
        fig.colorbar(im, ax=ax, label="Intensity")

    if not showAxes:
        ax.axis("off")
    if title:
        ax.set_title(title)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _safe_png_name(name: Optional[str], fileId: str, used: set) -> str:
    """Derive a unique, filesystem-safe PNG entry name inside the ZIP."""
    base = (name or "").strip() or fileId
    base = os.path.splitext(base)[0]
    base = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in base) or "image"
    candidate, n = base, 1
    while candidate in used:
        n += 1
        candidate = f"{base}_{n}"
    used.add(candidate)
    return f"{candidate}.png"


@router.post("/export")
def export_image(req: ExportRequest):
    """Export an image as PNG with custom colormap and optional log scale."""
    try:
        meta = _registry.get(req.fileId)
        fmt = meta["format"] if meta else _detect_format(req.fileId)
        path = _file_path(req.fileId)
        arr = _load_2d(path, fmt, channel=req.channel)

        png = _render_png_bytes(
            arr,
            colormap=req.colormap,
            vmin=req.vmin,
            vmax=req.vmax,
            logScale=req.logScale,
            dpi=req.dpi,
            showAxes=req.showAxes,
            showColorbar=req.showColorbar,
            xAxis=req.xAxis,
            yAxis=req.yAxis,
            wavelengthAngstrom=req.wavelengthAngstrom,
            axisQMin=req.axisQMin,
            axisQMax=req.axisQMax,
            axisChiMin=req.axisChiMin,
            axisChiMax=req.axisChiMax,
            cropChiMin=req.cropChiMin,
            cropChiMax=req.cropChiMax,
        )
        return StreamingResponse(
            io.BytesIO(png),
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{os.path.splitext(req.fileId or "image")[0]}.png"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/export-batch")
def export_images_zip(req: BatchExportRequest):
    """Render several uploaded images with shared settings and return a ZIP of PNGs."""
    try:
        import zipfile

        buf = io.BytesIO()
        used: set = set()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in req.files:
                meta = _registry.get(item.fileId)
                fmt = meta["format"] if meta else _detect_format(item.fileId)
                path = _file_path(item.fileId)
                arr = _load_2d(path, fmt, channel=req.channel)
                png = _render_png_bytes(
                    arr,
                    colormap=req.colormap,
                    vmin=req.vmin,
                    vmax=req.vmax,
                    logScale=req.logScale,
                    dpi=req.dpi,
                    showAxes=req.showAxes,
                    showColorbar=req.showColorbar,
                    title=(meta or {}).get("originalName"),
                    xAxis=req.xAxis,
                    yAxis=req.yAxis,
                    wavelengthAngstrom=req.wavelengthAngstrom,
                    axisQMin=req.axisQMin,
                    axisQMax=req.axisQMax,
                    axisChiMin=req.axisChiMin,
                    axisChiMax=req.axisChiMax,
                    cropChiMin=req.cropChiMin,
                    cropChiMax=req.cropChiMax,
                )
                zf.writestr(_safe_png_name(item.name, item.fileId, used), png)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="viewer_export.zip"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.get("/file-list", response_model=List[FileInfo])
def file_list():
    """List all uploaded viewer files with metadata."""
    items: list[FileInfo] = []
    for fid, meta in _registry.items():
        items.append(FileInfo(
            fileId=fid,
            originalName=meta.get("originalName", "unknown"),
            format=meta.get("format", "unknown"),
            shape=meta.get("shape", []),
            dtype=meta.get("dtype", ""),
        ))
    return items


def _drop_thumb_cache(fileId: str) -> None:
    for key in [k for k in _thumb_cache if k.split("|", 1)[0] == fileId]:
        _thumb_cache.pop(key, None)


def _delete_file_by_id(fileId: str) -> bool:
    """Remove one uploaded file from disk, the registry and the thumb cache.

    Returns True when the file existed (on disk or in the registry). Missing
    disk files still drop their registry entry so the gallery stays in sync.
    """
    existed = False
    try:
        path = _file_path(fileId)
        if os.path.isfile(path):
            os.remove(path)
            existed = True
    except HTTPException:
        raise
    except OSError:
        pass  # already gone — still clean up the registry entry
    if fileId in _registry:
        existed = True
        _registry.pop(fileId, None)
    _drop_thumb_cache(fileId)
    return existed


@router.delete("/file/{fileId}")
def delete_file(fileId: str):
    """Delete one uploaded image (disk file + registry entry)."""
    try:
        deleted = _delete_file_by_id(fileId)
        if not deleted:
            raise HTTPException(404, f"Unknown fileId: {fileId}")
        return {"deleted": fileId}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.delete("/files")
def delete_all_files():
    """Delete every viewer-uploaded file (disk + registry + thumb cache)."""
    try:
        ids = list(_registry.keys())
        for fid in ids:
            _delete_file_by_id(fid)
        return {"deleted": len(ids)}
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


# ---------------------------------------------------------------------------
# Thumbnails (left-side gallery preview)
# ---------------------------------------------------------------------------

# Uploads are immutable, so a fileId (+render params) always maps to the same
# preview. Cache rendered bytes to avoid re-loading the full array per gallery
# render; each ~128 px PNG is a few KB, so a couple hundred entries are cheap.
_thumb_cache: Dict[str, bytes] = {}
_THUMB_CACHE_MAX = 256


@router.get("/thumbnail/{fileId}")
def get_thumbnail(
    fileId: str,
    channel: int = Query(0, ge=0),
    size: int = Query(128, ge=32, le=512),
    colormap: str = Query("viridis"),
):
    """Render a small square PNG preview of an uploaded image for the gallery."""
    key = f"{fileId}|{channel}|{size}|{colormap}"
    cached = _thumb_cache.get(key)
    if cached is not None:
        return StreamingResponse(io.BytesIO(cached), media_type="image/png")

    try:
        meta = _registry.get(fileId)
        fmt = meta["format"] if meta else _detect_format(fileId)
        path = _file_path(fileId)
        arr = _load_2d(path, fmt, channel=channel)

        # Nearest-neighbour downsample: fast and, unlike spline orders, it does
        # not smear NaN sentinels (pyFAI empty bins) into neighbouring pixels.
        from scipy.ndimage import zoom

        h, w = arr.shape
        factor = min(size / h, size / w)
        small = zoom(arr, factor, order=0) if factor < 1 else arr

        finite = small[np.isfinite(small)]
        vmin = float(finite.min()) if finite.size else 0.0
        vmax = float(finite.max()) if finite.size else 1.0

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=(size / 100.0, size / 100.0), dpi=100)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.imshow(
            small,
            cmap=_get_cmap(colormap),
            aspect="auto",
            origin="lower",
            vmin=vmin,
            vmax=vmax,
        )
        ax.axis("off")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        png = buf.getvalue()

        if len(_thumb_cache) >= _THUMB_CACHE_MAX:
            _thumb_cache.pop(next(iter(_thumb_cache)))
        _thumb_cache[key] = png
        return StreamingResponse(io.BytesIO(png), media_type="image/png")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))
