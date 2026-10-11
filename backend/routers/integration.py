"""
2D intensity integration router — a standalone PolymCrystRefine module.

Two input modes (modeled on reference/function1/pages/2dint.py):

  * ``detector`` — a raw detector image + a PONI calibration file are
    integrated with pyFAI ``integrate2d_ng``.
  * ``cake``     — a pre-integrated 2D cake (.npy, azimuth x q) is processed
    directly; only masking is applied.

Both modes support percentile / manual threshold masking and an optional
custom mask, and can export a ZIP containing the masked cake (.npy), the
q/chi axes and a processing_info.txt — plus a PONI export so the calibration
can be reused by any other pyFAI-based step.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import zipfile
from typing import List, Literal, Optional

import numpy as np
from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from utils import (
    _file_path,
    _identify_q_unit,
    _load_array,
    _parse_processing_info,
    _q_range_to_angstrom,
    _save_array,
    _save_upload,
)
from routers.waxs_pipeline import (
    ParsePoniResponse,
    _integrate_2d,
    _parse_poni,
    _read_image,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AutoThresholdRequest(BaseModel):
    fileId: str
    lowPct: float = Field(0.1, ge=0, le=100)
    highPct: float = Field(100.0, ge=0, le=100, description="Upper percentile; 100 = keep all values")


class RunRequest(BaseModel):
    mode: Literal["detector", "cake"] = "detector"
    imageFileId: str
    poniFileId: Optional[str] = Field(None, description="Required for detector mode")

    # cake-mode axis ranges
    qMin: Optional[float] = None
    qMax: Optional[float] = None
    chiMin: Optional[float] = None
    chiMax: Optional[float] = None

    # masking
    maskMode: Literal["auto", "manual", "none"] = "auto"
    lowPct: float = Field(0.1, ge=0, le=100)
    highPct: float = Field(100.0, ge=0, le=100, description="Upper percentile for auto-threshold; 100 = keep all values")
    minThreshold: Optional[float] = None
    maxThreshold: Optional[float] = None
    customMaskFileId: Optional[str] = None
    fillValue: float = 0.0

    # integration (detector mode)
    nptRadial: int = Field(1000, ge=10)
    nptAzimuthal: int = Field(360, ge=10)
    method: str = Field("csr", description="pyFAI integration method part (csr/bbox/splitpixel/numpy)")
    unit: str = Field("q_nm^-1", description="q/2th/r unit for integration")
    polarizationFactor: Optional[float] = Field(0.99, ge=-0.5, le=1, description="pyFAI polarization factor (None/0 = skip)")


class RunResponse(BaseModel):
    resultFileId: str
    qArrayFileId: Optional[str] = None
    chiArrayFileId: Optional[str] = None
    maskRatio: float = 0.0
    unit: str = "q_nm^-1"
    qAxis: List[float] = []      # downsampled q axis (preview)
    chiAxis: List[float] = []    # downsampled chi axis (preview)
    preview: List[List[float]] = []  # downsampled cake, rows=chi x cols=q
    minIntensity: Optional[float] = None
    maxIntensity: Optional[float] = None


class ExportRequest(BaseModel):
    resultFileId: str
    qArrayFileId: Optional[str] = None
    chiArrayFileId: Optional[str] = None
    unit: str = "q_nm^-1"
    mode: Literal["detector", "cake"] = "detector"
    nptRadial: Optional[int] = None
    nptAzimuthal: Optional[int] = None
    maskRatio: Optional[float] = None
    polarizationFactor: Optional[float] = None
    baseName: str = "integration"


class ExportBatchItem(BaseModel):
    """One batch result to place under ``{name}/`` inside the batch ZIP."""
    resultFileId: str
    qArrayFileId: Optional[str] = None
    chiArrayFileId: Optional[str] = None
    name: Optional[str] = Field(None, description="Sub-folder / base name (defaults to image_NN)")
    maskRatio: Optional[float] = None
    polarizationFactor: Optional[float] = None


class ExportBatchRequest(BaseModel):
    """Export several integration results (a full batch run) as one ZIP."""
    items: List[ExportBatchItem]
    unit: str = "q_nm^-1"
    mode: Literal["detector", "cake"] = "detector"
    nptRadial: Optional[int] = None
    nptAzimuthal: Optional[int] = None


class ExportPoniRequest(BaseModel):
    """Explicit PONI parameters to serialise into a .poni file."""
    wavelengthNm: float = Field(0.124, description="Wavelength in nm")
    dist: float = Field(..., description="Sample-detector distance in meters")
    poni1: float
    poni2: float
    detector: str = "Detector"
    pixel1: float = Field(172e-6, description="Pixel size 1 in meters")
    pixel2: float = Field(172e-6, description="Pixel size 2 in meters")
    rot1: float = 0.0
    rot2: float = 0.0
    rot3: float = 0.0
    splineFile: Optional[str] = None


class ParseInfoResponse(BaseModel):
    """Axis ranges parsed from a standalone processing_info sidecar.

    Used by *cake* mode to auto-fill the q/chi axis-range fields from a
    ``processing_info.json`` (or legacy ``.txt``) exported alongside a cake.
    q is always returned in Å^-1 (nm^-1 inputs are divided by 10); chi in
    degrees. ``unit`` is the detected *source* q unit ("Å^-1" / "nm^-1"), or
    None when the sidecar does not state it.
    """
    qRange: Optional[List[float]] = None
    chiRange: Optional[List[float]] = None
    unit: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_mask(file_id: Optional[str]) -> Optional[np.ndarray]:
    """Load an optional custom mask file; nonzero values are treated as masked."""
    if not file_id:
        return None
    arr = _read_image(file_id)
    return (np.asarray(arr) != 0).astype(bool)


def _thresholds_from_percentile(data: np.ndarray, low_pct: float, high_pct: float):
    flat = data.ravel()
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return None, None
    return float(np.percentile(flat, low_pct)), float(np.percentile(flat, high_pct))


def _build_mask(
    data: np.ndarray,
    lo: Optional[float],
    hi: Optional[float],
    custom_mask: Optional[np.ndarray] = None,
    dilate: bool = True,
) -> np.ndarray:
    """Boolean mask (True = masked) from thresholds + optional custom mask."""
    bad = ~np.isfinite(data)
    if lo is not None:
        bad |= data < lo
    if hi is not None:
        bad |= data > hi
    if custom_mask is not None and np.asarray(custom_mask).shape == data.shape:
        bad |= np.asarray(custom_mask).astype(bool)
    if dilate:
        from scipy.ndimage import binary_dilation
        bad = binary_dilation(bad, iterations=1)
    return bad


def _strided_downsample(cake: np.ndarray, q: np.ndarray, chi: np.ndarray, max_side: int = 200):
    """Downsample cake + axes by strided slicing, keeping exact axis alignment."""
    n_az, n_rad = cake.shape
    step_r = max(1, math.ceil(n_rad / max_side))
    step_a = max(1, math.ceil(n_az / max_side))
    return (
        cake[::step_a, ::step_r],
        q[::step_r].copy(),
        chi[::step_a].copy(),
    )


def _finite_stats(arr: np.ndarray):
    flat = arr.ravel()
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return None, None
    return float(flat.min()), float(flat.max())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload")
def upload_files(files: List[UploadFile] = File(...)):
    """Accept detector images, PONI files and/or custom masks."""
    saved: list[dict] = []
    for f in files:
        data = f.file.read()
        ext = os.path.splitext(f.filename or "")[1]
        fid = _save_upload(data, suffix=ext)
        name = (f.filename or "").lower()
        if name.endswith(".poni"):
            kind = "poni"
        elif ext.lower() in (".npy",):
            kind = "image"
        else:
            kind = "image"
        saved.append({"fileId": fid, "originalName": f.filename, "size": len(data), "kind": kind})
    return {"files": saved}


@router.post("/parse-poni", response_model=ParsePoniResponse)
def parse_poni(fileId: str = Body(..., embed=True)):
    """Parse a pyFAI PONI calibration file and return its parameters."""
    try:
        return ParsePoniResponse(**_parse_poni(fileId))
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/parse-info", response_model=ParseInfoResponse)
def parse_info(file: UploadFile = File(...)):
    """Parse a standalone processing_info sidecar (JSON or legacy text) and
    return the q (Å^-1) / chi (°) axis ranges, so *cake* mode can auto-fill the
    axis-range fields from the file exported alongside a cake (mirrors what
    reference/function3 does automatically for ``processing_info.txt``)."""
    try:
        text = file.file.read().decode("utf-8", errors="replace")
        parsed = _parse_processing_info(text)
        unit = parsed.get("x_axis_unit")
        identified = _identify_q_unit(unit)
        unit_label = {"nanometer": "nm^-1", "angstrom": "Å^-1"}.get(identified)
        q_range: Optional[List[float]] = None
        chi_range: Optional[List[float]] = None
        if "q_min" in parsed and "q_max" in parsed:
            q_range = list(_q_range_to_angstrom((parsed["q_min"], parsed["q_max"]), unit))
        if "chi_min" in parsed and "chi_max" in parsed:
            chi_range = [parsed["chi_min"], parsed["chi_max"]]
        return ParseInfoResponse(qRange=q_range, chiRange=chi_range, unit=unit_label)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/auto-threshold")
def auto_threshold(req: AutoThresholdRequest):
    """Compute low/high percentile thresholds of an image (for the UI)."""
    try:
        img = _read_image(req.fileId)
        lo, hi = _thresholds_from_percentile(img, req.lowPct, req.highPct)
        return {"min": lo, "max": hi, "lowPct": req.lowPct, "highPct": req.highPct}
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.get("/image/{file_id}")
def get_image(file_id: str, maxSide: int = 500):
    """Return a downsampled 2D preview of an image + stats (for display only)."""
    try:
        img = _read_image(file_id).astype(np.float64)
        if img.ndim != 2:
            raise HTTPException(400, detail="Only 2D images are supported")
        step_r = max(1, math.ceil(img.shape[1] / maxSide))
        step_a = max(1, math.ceil(img.shape[0] / maxSide))
        preview = img[::step_a, ::step_r]
        lo, hi = _finite_stats(img)
        return {
            "shape": [int(img.shape[0]), int(img.shape[1])],
            "preview": preview.tolist(),
            "min": lo,
            "max": hi,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/run", response_model=RunResponse)
def run_integration(req: RunRequest):
    """Run 2D integration (detector+PONI) or apply masking to a cake (cake mode)."""
    try:
        custom_mask = _read_mask(req.customMaskFileId)

        # Resolve thresholds ---------------------------------------------------
        if req.maskMode == "manual":
            lo, hi = req.minThreshold, req.maxThreshold
        else:
            lo = hi = None  # auto computed per-image below; none = no masking

        if req.mode == "detector":
            if not req.poniFileId:
                raise HTTPException(400, detail="Detector mode requires a PONI file.")

            img = _read_image(req.imageFileId)

            if req.maskMode == "auto":
                lo, hi = _thresholds_from_percentile(img, req.lowPct, req.highPct)
            det_mask = _build_mask(img, lo, hi, custom_mask, dilate=True)

            cake, q_arr, chi_arr = _integrate_2d(
                img, _file_path(req.poniFileId),
                req.nptRadial, req.nptAzimuthal,
                req.method, unit=req.unit, mask=det_mask,
                polarization_factor=req.polarizationFactor,
            )
            cake = cake.astype(np.float64)

            # Build cake-space mask so masked / saturated bins are filled with
            # the user-requested fillValue even when pyFAI leaves them as large
            # finite sentinels (e.g. the array maximum) rather than NaN.
            # Always recompute thresholds from the integrated cake — the
            # detector-level thresholds are in pixel-intensity space, not
            # cake integrated-intensity space.
            if req.maskMode in ("manual", "auto"):
                cake_lo, cake_hi = _thresholds_from_percentile(cake, req.lowPct, req.highPct)
            else:
                cake_lo = cake_hi = None

            cake = cake.copy()
            if req.maskMode != "none":
                cmask = _build_mask(cake, cake_lo, cake_hi, None, dilate=False)
            else:
                cmask = ~np.isfinite(cake)
            cake[cmask] = req.fillValue
            mask_ratio = float(cmask.mean()) if cmask.size else 0.0

        else:  # cake mode
            cake = _read_image(req.imageFileId).astype(np.float64)
            if cake.ndim != 2:
                raise HTTPException(400, detail="Cake input must be a 2D array (.npy).")
            n_az, n_rad = cake.shape

            q_arr = np.linspace(
                req.qMin if req.qMin is not None else 0.0,
                req.qMax if req.qMax is not None else n_rad - 1,
                n_rad,
            )
            chi_arr = np.linspace(
                req.chiMin if req.chiMin is not None else -180.0,
                req.chiMax if req.chiMax is not None else 180.0,
                n_az,
            )

            if req.maskMode == "auto":
                lo, hi = _thresholds_from_percentile(cake, req.lowPct, req.highPct)

            cake = cake.copy()
            # Non-finite bins (NaN/inf from empty pyFAI bins or upstream
            # sentinels) are ALWAYS treated as masked — even when maskMode is
            # "none" — so they never survive into the exported cake or the
            # downstream ROI extraction, where they would otherwise appear as
            # extremum values and pollute the intensity sum.
            if req.maskMode != "none":
                cmask = _build_mask(cake, lo, hi, custom_mask, dilate=False)
            else:
                cmask = ~np.isfinite(cake)
            cake[cmask] = req.fillValue
            mask_ratio = float(cmask.mean()) if cmask.size else 0.0

        # Persist outputs ------------------------------------------------------
        result_fid = _save_array(cake)
        q_fid = _save_array(q_arr)
        chi_fid = _save_array(chi_arr)

        preview_cake, q_ds, chi_ds = _strided_downsample(cake, q_arr, chi_arr)
        vmin, vmax = _finite_stats(cake)

        return RunResponse(
            resultFileId=result_fid,
            qArrayFileId=q_fid,
            chiArrayFileId=chi_fid,
            maskRatio=mask_ratio,
            unit=req.unit,
            qAxis=q_ds.tolist(),
            chiAxis=chi_ds.tolist(),
            preview=preview_cake.tolist(),
            minIntensity=vmin,
            maxIntensity=vmax,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


def _export_entry_bytes(
    cake: np.ndarray,
    q_arr: np.ndarray,
    chi_arr: np.ndarray,
    unit: str,
    mode: str,
    npt_radial: Optional[int],
    npt_azimuthal: Optional[int],
    mask_ratio: Optional[float],
    polarization_factor: Optional[float],
    base: str,
) -> dict:
    """Build the per-result ZIP entries (masked cake + axes + processing_info).

    ``base`` prefixes the cake file, matching the single-export layout, so a
    batch entry ``{name}/`` unpacks to exactly the same structure as one
    standalone export.
    """
    base = base or "integration"
    info = {
        "module": "PolymCrystRefine 2D intensity integration",
        "mode": mode,
        "xAxisUnit": unit,
        "xAxisRange": [float(np.nanmin(q_arr)), float(np.nanmax(q_arr))],
        "yAxisRangeDeg": [float(np.nanmin(chi_arr)), float(np.nanmax(chi_arr))],
        "integrationPoints": {
            "radial": npt_radial or cake.shape[1],
            "azimuthal": npt_azimuthal or cake.shape[0],
        },
    }
    if mask_ratio is not None:
        info["maskFraction"] = mask_ratio
    if polarization_factor is not None:
        info["polarizationFactor"] = polarization_factor
    return {
        f"{base}_masked.npy": _save_array_bytes(cake),
        "q_array.npy": _save_array_bytes(np.asarray(q_arr)),
        "chi_array.npy": _save_array_bytes(np.asarray(chi_arr)),
        "processing_info.json": json.dumps(info, indent=2, ensure_ascii=False),
    }


def _sanitize_zip_entry(name: Optional[str], index: int, used: set) -> str:
    """Turn an image name into a unique, filesystem-safe sub-folder name."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()).strip("._")
    if not cleaned:
        cleaned = f"image_{index:02d}"
    folder, i = cleaned, 2
    while folder.lower() in used:
        folder = f"{cleaned}_{i}"
        i += 1
    used.add(folder.lower())
    return folder


@router.post("/export")
def export_zip(req: ExportRequest):
    """Bundle the masked cake, q/chi axes and processing_info.json into a ZIP."""
    try:
        cake = _load_array(req.resultFileId)
        q_arr = _load_array(req.qArrayFileId) if req.qArrayFileId else np.arange(cake.shape[1], dtype=np.float64)
        chi_arr = _load_array(req.chiArrayFileId) if req.chiArrayFileId else np.arange(cake.shape[0], dtype=np.float64)

        base = req.baseName or "integration"
        entries = _export_entry_bytes(
            cake, q_arr, chi_arr,
            unit=req.unit, mode=req.mode,
            npt_radial=req.nptRadial, npt_azimuthal=req.nptAzimuthal,
            mask_ratio=req.maskRatio, polarization_factor=req.polarizationFactor,
            base=base,
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries.items():
                zf.writestr(name, data)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{base}_2d_integration.zip"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/export-batch")
def export_batch_zip(req: ExportBatchRequest):
    """Bundle every result of a batch integration run into a single flat ZIP.

    A batch run shares one PONI (cake mode: one axis-range set), so all cakes
    share identical q/chi axes — the axes and ``processing_info.json`` are
    written ONCE at the ZIP root and every cake lands next to them as
    ``{name}_masked.npy``, exactly like a single export. Per-image mask
    fractions are recorded under ``files`` in the shared processing_info.
    """
    try:
        if not req.items:
            raise HTTPException(400, detail="No results to export")

        loaded = []
        used: set = set()
        for idx, item in enumerate(req.items, start=1):
            cake = _load_array(item.resultFileId)
            base = _sanitize_zip_entry(item.name, idx, used)
            loaded.append((base, cake, item))

        first_cake = loaded[0][1]
        for base, cake, _ in loaded[1:]:
            if cake.shape != first_cake.shape:
                raise HTTPException(
                    400,
                    detail=(f"Cake shapes differ ({base}: {cake.shape} vs "
                            f"{loaded[0][0]}: {first_cake.shape}) — a flat export needs identical axes."),
                )

        q_arr = _load_array(req.items[0].qArrayFileId) if req.items[0].qArrayFileId else np.arange(first_cake.shape[1], dtype=np.float64)
        chi_arr = _load_array(req.items[0].chiArrayFileId) if req.items[0].chiArrayFileId else np.arange(first_cake.shape[0], dtype=np.float64)
        for base, cake, item in loaded[1:]:
            if item.qArrayFileId and not np.allclose(_load_array(item.qArrayFileId), q_arr):
                raise HTTPException(400, detail=f"q axis of '{base}' differs from the first result — a flat export needs one shared axis.")
            if item.chiArrayFileId and not np.allclose(_load_array(item.chiArrayFileId), chi_arr):
                raise HTTPException(400, detail=f"chi axis of '{base}' differs from the first result — a flat export needs one shared axis.")

        files_meta = []
        entries = {
            "q_array.npy": _save_array_bytes(np.asarray(q_arr)),
            "chi_array.npy": _save_array_bytes(np.asarray(chi_arr)),
        }
        for base, cake, item in loaded:
            entries[f"{base}_masked.npy"] = _save_array_bytes(cake)
            meta = {"name": base}
            if item.maskRatio is not None:
                meta["maskFraction"] = item.maskRatio
            files_meta.append(meta)

        info = {
            "module": "PolymCrystRefine 2D intensity integration",
            "mode": req.mode,
            "xAxisUnit": req.unit,
            "xAxisRange": [float(np.nanmin(q_arr)), float(np.nanmax(q_arr))],
            "yAxisRangeDeg": [float(np.nanmin(chi_arr)), float(np.nanmax(chi_arr))],
            "integrationPoints": {
                "radial": req.nptRadial or first_cake.shape[1],
                "azimuthal": req.nptAzimuthal or first_cake.shape[0],
            },
            "count": len(loaded),
            "files": files_meta,
        }
        if req.items[0].polarizationFactor is not None:
            info["polarizationFactor"] = req.items[0].polarizationFactor
        entries["processing_info.json"] = json.dumps(info, indent=2, ensure_ascii=False)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries.items():
                zf.writestr(name, data)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="2d_integration_batch.zip"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/export-poni")
def export_poni(req: ExportPoniRequest):
    """Serialise explicit calibration parameters into a downloadable .poni file.

    Lets any pyFAI-based step reuse the calibration used here.
    """
    try:
        wavelength_m = req.wavelengthNm * 1e-9
        spline_line = f"SplineFile: {req.splineFile}\n" if req.splineFile else ""
        poni_text = (
            f"# Saving the calibrations results to a PONI file (PolymCrystRefine)\n"
            f"Distance: {req.dist}\n"
            f"Poni1: {req.poni1}\n"
            f"Poni2: {req.poni2}\n"
            f"Rot1: {req.rot1}\n"
            f"Rot2: {req.rot2}\n"
            f"Rot3: {req.rot3}\n"
            f"Wavelength: {wavelength_m}\n"
            f"{spline_line}"
            f"Detector: {req.detector}\n"
            f"PixelSize1: {req.pixel1}\n"
            f"PixelSize2: {req.pixel2}\n"
        )
        data = poni_text.encode("utf-8")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="calibration.poni"'},
        )
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


def _save_array_bytes(arr: np.ndarray) -> bytes:
    """Serialise an array to .npy bytes (in memory)."""
    buf = io.BytesIO()
    np.save(buf, np.asarray(arr))
    return buf.getvalue()
