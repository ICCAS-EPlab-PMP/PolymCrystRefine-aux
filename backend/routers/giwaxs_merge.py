"""
GIWAXS fiber-integration merge router — a standalone PolymCrystRefine module.

Merges several raw detector images into ONE fiber-corrected GIWAXS map,
modeled on X-FAIS's fiber integration (pyFAI ``FiberIntegrator``):

  * every image is integrated separately on the SAME (in-plane, out-of-plane)
    grid, but with its own ``rot1/rot2/rot3`` override (degrees, empty =
    inherit the PONI value) — the sample/detector orientation that changed
    between exposures is corrected per image BEFORE any merging happens
    (unlike the 2D integration merge, which stitches already-integrated
    cakes);
  * the resulting maps are combined pixel-wise with the same merge methods
    as the 2D integration processing module (mean / median / weighted /
    sequential + optional lower-bound mask);
  * export produces a ZIP with the merged map (.npy), the in-plane /
    out-of-plane axes and a ``processing_info.json`` — plus an optional
    publication-style PNG rendered by matplotlib;
  * ``/render-png`` re-renders any stored 2-D result as a labelled PNG for
    viewing and downloading (the "image export" companion of the 2D
    integration module).
"""

from __future__ import annotations

import io
import json
import math
import os
import warnings
import zipfile
from typing import List, Literal, Optional

import numpy as np
from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from utils import _file_path, _save_array, _save_upload
from routers.waxs_pipeline import _read_image

router = APIRouter()


# ---------------------------------------------------------------------------
# Constants (unit lists ported from X-FAIS; all registered in pyFAI.units)
# ---------------------------------------------------------------------------

FIBER_UNITS_IP: List[str] = [
    "qip_nm^-1", "qip_A^-1",
    "qxgi_nm^-1", "qygi_nm^-1", "qzgi_nm^-1", "qtot_nm^-1",
    "qxgi_A^-1", "qygi_A^-1", "qzgi_A^-1", "qtot_A^-1",
    "scattering_angle_horz_rad", "exit_angle_horz_rad", "exit_angle_horz_deg",
    "chigi_rad", "chigi_deg",
]

FIBER_UNITS_OOP: List[str] = [
    "qoop_nm^-1", "qoop_A^-1",
    "qxgi_nm^-1", "qygi_nm^-1", "qzgi_nm^-1", "qtot_nm^-1",
    "qxgi_A^-1", "qygi_A^-1", "qzgi_A^-1", "qtot_A^-1",
    "scattering_angle_vert_rad", "exit_angle_vert_rad", "exit_angle_vert_deg",
    "chigi_rad", "chigi_deg",
]

MERGE_METHODS = ("mean", "median", "weighted", "sequential")

FIBER_METHODS = ("splitpixel", "csr", "lut", "bbox", "numpy")

# Human-readable axis labels for the PNG renderer.
_UNIT_LABELS = {
    "qip_nm^-1": "q\u2225 (nm$^{-1}$)", "qip_A^-1": "q\u2225 (\u00c5$^{-1}$)",
    "qoop_nm^-1": "q\u22a5 (nm$^{-1}$)", "qoop_A^-1": "q\u22a5 (\u00c5$^{-1}$)",
    "qxgi_nm^-1": "qx (nm$^{-1}$)", "qygi_nm^-1": "qy (nm$^{-1}$)",
    "qzgi_nm^-1": "qz (nm$^{-1}$)", "qtot_nm^-1": "|q| (nm$^{-1}$)",
    "qxgi_A^-1": "qx (\u00c5$^{-1}$)", "qygi_A^-1": "qy (\u00c5$^{-1}$)",
    "qzgi_A^-1": "qz (\u00c5$^{-1}$)", "qtot_A^-1": "|q| (\u00c5$^{-1}$)",
    "scattering_angle_horz_rad": "2\u03b8 horz (rad)",
    "scattering_angle_vert_rad": "2\u03b8 vert (rad)",
    "exit_angle_horz_rad": "exit angle (rad)", "exit_angle_horz_deg": "exit angle (\u00b0)",
    "exit_angle_vert_rad": "exit angle (rad)", "exit_angle_vert_deg": "exit angle (\u00b0)",
    "chigi_rad": "\u03c7 (rad)", "chigi_deg": "\u03c7 (\u00b0)",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PoniInfoResponse(BaseModel):
    """PONI calibration parameters, rotations exposed in degrees."""
    wavelength: float          # nm
    dist: float                # m
    poni1: float
    poni2: float
    rot1Deg: float
    rot2Deg: float
    rot3Deg: float
    detector: str
    pixel1: float              # m
    pixel2: float              # m
    beamCenterX: float         # px = poni2 / pixel2
    beamCenterY: float         # px = poni1 / pixel1
    maxShape: Optional[List[int]] = None


class ImageRotItem(BaseModel):
    """One raw image + its per-image detector rotation overrides.

    ``None`` (JSON null / omitted) inherits the value from the PONI file —
    the X-FAIS per-key override semantics (NOT all-or-nothing).
    """
    imageFileId: str
    name: Optional[str] = None
    rot1Deg: Optional[float] = None
    rot2Deg: Optional[float] = None
    rot3Deg: Optional[float] = None


class RunRequest(BaseModel):
    """Full merge run: per-image fiber integration + pixel-wise merge."""
    images: List[ImageRotItem] = Field(..., min_length=1)
    poniFileId: str
    maskFileId: Optional[str] = None

    # --- X-FAIS fiber-integration settings (shared by all images) ---
    sampleOrientation: int = Field(1, ge=1, le=8)
    incidentAngleDeg: float = 0.0
    tiltAngleDeg: float = 0.0
    polarizationFactor: Optional[float] = Field(None, ge=-1.0, le=1.0,
                                                description="None = no polarization correction")
    correctSolidAngle: bool = True
    unitIp: str = "qip_A^-1"
    unitOop: str = "qoop_A^-1"
    autoRange: bool = True
    ipRange: Optional[List[float]] = None    # [min, max]; auto from 1st image when None
    oopRange: Optional[List[float]] = None
    nptIp: int = Field(448, ge=32, le=4096)
    nptOop: int = Field(448, ge=32, le=4096)
    method: Optional[str] = Field(None, description="pyFAI method: splitpixel/csr/lut/bbox/numpy; None = default")

    # --- merge settings (same semantics as /api/waxs/merge) ---
    mergeMethod: Literal["mean", "median", "weighted", "sequential"] = "mean"
    maskLowerBound: Optional[float] = None


class ImageResultItem(BaseModel):
    name: str
    ok: bool
    error: Optional[str] = None
    rotApplied: List[float]           # degrees actually used (override or PONI)
    coverage: Optional[float] = None  # fraction of finite bins
    intensityFileId: Optional[str] = None
    preview: Optional[List[List[Optional[float]]]] = None


class RunResponse(BaseModel):
    mergedFileId: str
    ipAxisFileId: str
    oopAxisFileId: str
    unitIp: str
    unitOop: str
    ipRange: List[float]
    oopRange: List[float]
    nptIp: int
    nptOop: int
    ipAxis: List[float]              # downsampled preview axes
    oopAxis: List[float]
    preview: List[List[Optional[float]]]   # rows = out-of-plane, cols = in-plane
    minIntensity: Optional[float] = None
    maxIntensity: Optional[float] = None
    images: List[ImageResultItem]
    info: dict                       # processing_info payload (reused by /export)


class PngSettings(BaseModel):
    """Publication-style PNG render options (X-FAIS mpl renderer subset)."""
    cmap: str = "viridis"
    useLog: bool = False
    logFloor: float = 0.1
    climMode: Literal["auto", "manual"] = "auto"
    clim: Optional[List[float]] = None
    flipX: bool = False
    flipY: bool = False
    title: str = ""
    xLabel: Optional[str] = None     # None = derive from unit
    yLabel: Optional[str] = None
    showColorbar: bool = True
    dpi: int = Field(150, ge=50, le=600)
    noDataColor: str = "#ffffff"


class RenderPngRequest(PngSettings):
    resultFileId: str
    ipAxisFileId: Optional[str] = None
    oopAxisFileId: Optional[str] = None
    unitIp: str = "qip_A^-1"
    unitOop: str = "qoop_A^-1"
    baseName: str = "giwaxs_merge"


class ExportRequest(BaseModel):
    mergedFileId: str
    ipAxisFileId: Optional[str] = None
    oopAxisFileId: Optional[str] = None
    info: dict = {}
    baseName: str = "giwaxs_merge"
    includePng: bool = False
    png: Optional[PngSettings] = None
    unitIp: str = "qip_A^-1"
    unitOop: str = "qoop_A^-1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_unit(value: str, allowed: List[str], what: str) -> str:
    if value not in allowed:
        raise HTTPException(400, detail=f"Unsupported {what} unit '{value}'.")
    return value


def _nan_to_none(obj):
    """Recursively convert non-finite floats to None so the JSON is strict."""
    if isinstance(obj, list):
        return [_nan_to_none(v) for v in obj]
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    return obj


def _strided_downsample(intensity: np.ndarray, ip: np.ndarray, oop: np.ndarray, max_side: int = 224):
    """Downsample (rows=oop, cols=ip) map + axes by strided slicing."""
    n_oop, n_ip = intensity.shape
    step_r = max(1, math.ceil(n_ip / max_side))
    step_a = max(1, math.ceil(n_oop / max_side))
    return intensity[::step_a, ::step_r], ip[::step_r].copy(), oop[::step_a].copy()


def _read_mask(file_id: Optional[str], shape) -> Optional[np.ndarray]:
    """Optional custom mask; nonzero values are masked (1 = masked for pyFAI)."""
    if not file_id:
        return None
    arr = np.asarray(_read_image(file_id))
    if arr.shape != tuple(shape):
        raise HTTPException(400, detail=f"Mask shape {arr.shape} != image shape {shape}.")
    return (arr != 0).astype(np.uint8)


def _load_base_poni(file_id: str):
    from pyFAI import load as pyfai_load
    try:
        return pyfai_load(_file_path(file_id))
    except Exception as exc:
        raise HTTPException(400, detail=f"Cannot load PONI file: {exc}")


def _build_fiber_integrator(base_ai, rot1_deg, rot2_deg, rot3_deg):
    """FiberIntegrator built on the PONI geometry with per-key rot overrides."""
    from pyFAI.integrator.fiber import FiberIntegrator
    rot1 = math.radians(rot1_deg) if rot1_deg is not None else float(base_ai.rot1)
    rot2 = math.radians(rot2_deg) if rot2_deg is not None else float(base_ai.rot2)
    rot3 = math.radians(rot3_deg) if rot3_deg is not None else float(base_ai.rot3)
    fi = FiberIntegrator(
        dist=base_ai.dist, poni1=base_ai.poni1, poni2=base_ai.poni2,
        rot1=rot1, rot2=rot2, rot3=rot3,
        wavelength=base_ai.wavelength, detector=base_ai.detector,
    )
    return fi, (math.degrees(rot1), math.degrees(rot2), math.degrees(rot3))


def _integrate_fiber(fi, image, req: RunRequest, ip_range, oop_range, mask=None):
    """One fiber integration on the shared (ip, oop) grid.

    Returns (intensity[n_oop, n_ip] with empty bins as NaN, ip_axis, oop_axis).
    """
    kw = dict(
        data=np.asarray(image, dtype=np.float64).copy(),
        npt_ip=req.nptIp, npt_oop=req.nptOop,
        unit_ip=req.unitIp, unit_oop=req.unitOop,
        ip_range=ip_range, oop_range=oop_range,
        sample_orientation=req.sampleOrientation,
        incident_angle=math.radians(req.incidentAngleDeg),
        tilt_angle=math.radians(req.tiltAngleDeg),
        angle_unit="rad",
        correctSolidAngle=req.correctSolidAngle,
    )
    if mask is not None:
        kw["mask"] = mask.astype(np.uint8)
    if req.polarizationFactor is not None:
        kw["polarization_factor"] = req.polarizationFactor
    if req.method:
        kw["method"] = req.method
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = fi.integrate2d_grazing_incidence(**kw)
    intensity = np.asarray(res.intensity, dtype=np.float64)
    ip = np.asarray(res.inplane if hasattr(res, "inplane") else res.radial, dtype=np.float64)
    oop = np.asarray(res.outofplane if hasattr(res, "outofplane") else res.azimuthal, dtype=np.float64)
    count = getattr(res, "count", None)
    if count is not None:
        intensity = intensity.copy()
        intensity[np.asarray(count) == 0] = np.nan
    return intensity, ip, oop


def _merge_maps(stack: List[np.ndarray], method: str, mask_lower_bound: Optional[float]):
    """Pixel-wise merge of same-shaped maps (NaN = no data, never contributes).

    Mirrors /api/waxs/merge semantics: mean / median / weighted (inverse
    per-image variance) / sequential (first valid wins); ``mask_lower_bound``
    excludes values below the bound. Uncovered pixels stay NaN.
    """
    arr = np.stack(stack)
    valid = np.isfinite(arr)
    if mask_lower_bound is not None:
        valid &= arr >= mask_lower_bound
    counts = valid.sum(axis=0)
    masked_arr = np.where(valid, arr, np.nan)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # all-NaN slices are expected
        if method == "sequential":
            out = np.full(arr.shape[1:], np.nan)
            for k in range(arr.shape[0]):
                take = valid[k] & np.isnan(out)
                out[take] = arr[k][take]
        elif method == "median":
            out = np.nanmedian(masked_arr, axis=0)
        elif method == "weighted":
            weights = np.array([
                1.0 / (np.var(a[np.isfinite(a)]) + 1e-12)
                if np.isfinite(a).any() else 0.0
                for a in arr
            ])
            if weights.sum() > 0:
                weights = weights / weights.sum()
            warr = weights[:, None, None] * valid
            num = np.nansum(warr * masked_arr, axis=0)
            den = warr.sum(axis=0)
            out = np.full(arr.shape[1:], np.nan)
            nz = den > 0
            out[nz] = num[nz] / den[nz]
        else:  # mean
            out = np.nanmean(masked_arr, axis=0)

    stats = {
        "uncoveredFraction": float((counts == 0).mean()),
        "meanContributors": float(counts[counts > 0].mean()) if (counts > 0).any() else 0.0,
    }
    if mask_lower_bound is not None:
        finite = np.isfinite(arr)
        stats["maskedFraction"] = float((finite & ~valid).sum() / max(finite.sum(), 1))
    return out, stats


def _finite_stats(arr: np.ndarray):
    flat = arr.ravel()
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return None, None
    return float(flat.min()), float(flat.max())


def _unit_label(unit: str) -> str:
    return _UNIT_LABELS.get(unit, unit)


def _render_png_bytes(intensity, ip, oop, req: PngSettings, unit_ip: str, unit_oop: str) -> bytes:
    """Render a 2-D GIWAXS map as a labelled matplotlib PNG (X-FAIS style)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import colormaps as mpl_colormaps

    data = np.asarray(intensity, dtype=np.float64)
    try:
        cmap = mpl_colormaps[req.cmap].copy()
    except Exception:
        cmap = plt.get_cmap("viridis").copy()
    try:
        cmap.set_bad(req.noDataColor or "#ffffff")
    except Exception:
        pass

    vmin, vmax = _finite_stats(data)
    if req.useLog:
        floor = req.logFloor if (req.logFloor is not None and req.logFloor > 0) else \
            (vmin if (vmin is not None and vmin > 0) else 1e-3)
        data = np.log10(np.clip(data, floor, None))
        vmin, vmax = _finite_stats(data)
    if req.climMode == "manual" and req.clim and len(req.clim) == 2:
        vmin, vmax = float(req.clim[0]), float(req.clim[1])
    elif vmin is not None and vmax is not None:
        # X-FAIS auto suggestion: 0.5 / 99.5 percentiles
        flat = data.ravel()
        flat = flat[np.isfinite(flat)]
        if flat.size:
            vmin, vmax = float(np.percentile(flat, 0.5)), float(np.percentile(flat, 99.5))

    ip0, ip1 = (float(ip[0]), float(ip[-1])) if ip is not None and len(ip) else (-1.0, 1.0)
    oop0, oop1 = (float(oop[0]), float(oop[-1])) if oop is not None and len(oop) else (-1.0, 1.0)

    fig, ax = plt.subplots(figsize=(7.2, 6.0), dpi=req.dpi)
    masked = np.ma.masked_invalid(data)
    im = ax.imshow(
        masked, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax,
        extent=(min(ip0, ip1), max(ip0, ip1), min(oop0, oop1), max(oop0, oop1)),
        origin="lower", interpolation="nearest",
    )
    ax.set_xlabel(req.xLabel or _unit_label(unit_ip))
    ax.set_ylabel(req.yLabel or _unit_label(unit_oop))
    if req.title:
        ax.set_title(req.title)
    if req.showColorbar:
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("log$_{10}$(I)" if req.useLog else "Intensity")
    if req.flipX:
        ax.invert_xaxis()
    if req.flipY:
        ax.invert_yaxis()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _save_array_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, np.asarray(arr))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload")
def upload_files(files: List[UploadFile] = File(...)):
    """Accept raw detector images, a PONI calibration and/or a custom mask."""
    saved: list = []
    for f in files:
        data = f.file.read()
        ext = os.path.splitext(f.filename or "")[1]
        fid = _save_upload(data, suffix=ext)
        name = (f.filename or "").lower()
        kind = "poni" if name.endswith(".poni") else "image"
        saved.append({"fileId": fid, "originalName": f.filename, "size": len(data), "kind": kind})
    return {"files": saved}


@router.post("/parse-poni", response_model=PoniInfoResponse)
def parse_poni(fileId: str = Body(..., embed=True)):
    """Parse a PONI file and return calibration + rotations (degrees)."""
    ai = _load_base_poni(fileId)
    detector = ai.detector
    pixel1 = detector.get_pixel1() if detector is not None else 0.0
    pixel2 = detector.get_pixel2() if detector is not None else 0.0
    max_shape = None
    if detector is not None and getattr(detector, "max_shape", None) is not None:
        max_shape = list(detector.max_shape)
    return PoniInfoResponse(
        wavelength=float(ai.wavelength) * 1e9,
        dist=float(ai.dist),
        poni1=float(ai.poni1),
        poni2=float(ai.poni2),
        rot1Deg=float(np.degrees(ai.rot1)),
        rot2Deg=float(np.degrees(ai.rot2)),
        rot3Deg=float(np.degrees(ai.rot3)),
        detector=(detector.name if detector is not None else "Unknown"),
        pixel1=float(pixel1),
        pixel2=float(pixel2),
        beamCenterX=(float(ai.poni2 / pixel2) if pixel2 else 0.0),
        beamCenterY=(float(ai.poni1 / pixel1) if pixel1 else 0.0),
        maxShape=max_shape,
    )


@router.post("/run", response_model=RunResponse)
def run_merge(req: RunRequest):
    """Integrate every image on a shared fiber grid (per-image rot overrides),
    then merge the maps pixel-wise."""
    try:
        _validate_unit(req.unitIp, FIBER_UNITS_IP, "in-plane")
        _validate_unit(req.unitOop, FIBER_UNITS_OOP, "out-of-plane")
        if req.method and req.method not in FIBER_METHODS:
            raise HTTPException(400, detail=f"Unsupported method '{req.method}'.")
        if not req.images:
            raise HTTPException(400, detail="At least one image is required.")
        if not req.poniFileId:
            raise HTTPException(400, detail="A PONI calibration file is required.")

        base_ai = _load_base_poni(req.poniFileId)

        # Shared grid: explicit ranges win; otherwise auto-derived from the
        # FIRST integrable image so every map lands on identical axes.
        ip_range = req.ipRange if (not req.autoRange and req.ipRange and len(req.ipRange) == 2) else None
        oop_range = req.oopRange if (not req.autoRange and req.oopRange and len(req.oopRange) == 2) else None

        images_out: List[ImageResultItem] = []
        intensities: List[np.ndarray] = []
        ip_axis = oop_axis = None

        for idx, item in enumerate(req.images):
            name = item.name or f"image_{idx + 1:02d}"
            try:
                image = np.asarray(_read_image(item.imageFileId))
                mask = _read_mask(req.maskFileId, image.shape)
                fi, rot_applied = _build_fiber_integrator(
                    base_ai, item.rot1Deg, item.rot2Deg, item.rot3Deg)
                intensity, ip_ax, oop_ax = _integrate_fiber(
                    fi, image, req, ip_range, oop_range, mask)
                if ip_range is None:
                    # first successful integration fixes the shared grid
                    ip_range = [float(ip_ax[0]), float(ip_ax[-1])]
                    oop_range = [float(oop_ax[0]), float(oop_ax[-1])]
                    # re-integrate this image on the now-fixed explicit grid
                    fi, rot_applied = _build_fiber_integrator(
                        base_ai, item.rot1Deg, item.rot2Deg, item.rot3Deg)
                    intensity, ip_ax, oop_ax = _integrate_fiber(
                        fi, image, req, ip_range, oop_range, mask)
                ip_axis, oop_axis = ip_ax, oop_ax
                fid = _save_array(intensity)
                preview, _, _ = _strided_downsample(intensity, ip_ax, oop_ax)
                images_out.append(ImageResultItem(
                    name=name, ok=True, rotApplied=[round(r, 6) for r in rot_applied],
                    coverage=float(np.isfinite(intensity).mean()),
                    intensityFileId=fid, preview=_nan_to_none(preview.tolist()),
                ))
                intensities.append(intensity)
            except HTTPException:
                raise
            except Exception as exc:
                images_out.append(ImageResultItem(
                    name=name, ok=False, error=str(exc),
                    rotApplied=[item.rot1Deg or 0.0, item.rot2Deg or 0.0, item.rot3Deg or 0.0],
                ))

        if not intensities:
            raise HTTPException(500, detail="All image integrations failed; see per-image errors.")

        merged, merge_stats = _merge_maps(intensities, req.mergeMethod, req.maskLowerBound)

        merged_fid = _save_array(merged)
        ip_fid = _save_array(np.asarray(ip_axis))
        oop_fid = _save_array(np.asarray(oop_axis))

        preview, ip_ds, oop_ds = _strided_downsample(merged, ip_axis, oop_axis)
        vmin, vmax = _finite_stats(merged)

        import pyFAI
        info = {
            "module": "PolymCrystRefine GIWAXS fiber-integration merge",
            "mode": "fiber_giwaxs_merge",
            "mergeMethod": req.mergeMethod,
            "mergedImageCount": len(intensities),
            "xAxisUnit": req.unitIp,
            "yAxisUnit": req.unitOop,
            "xAxisRange": [float(ip_axis[0]), float(ip_axis[-1])],
            "yAxisRange": [float(oop_axis[0]), float(oop_axis[-1])],
            "integrationPoints": {"inPlane": req.nptIp, "outOfPlane": req.nptOop},
            "sampleOrientation": req.sampleOrientation,
            "incidentAngleDeg": req.incidentAngleDeg,
            "tiltAngleDeg": req.tiltAngleDeg,
            "correctSolidAngle": req.correctSolidAngle,
            "pyfaiVersion": str(pyFAI.version),
            "images": [
                {
                    "name": it.name,
                    "ok": it.ok,
                    **({"rot1Deg": it.rotApplied[0], "rot2Deg": it.rotApplied[1],
                        "rot3Deg": it.rotApplied[2], "coverage": it.coverage}
                       if it.ok else {"error": it.error}),
                }
                for it in images_out
            ],
        }
        if req.polarizationFactor is not None:
            info["polarizationFactor"] = req.polarizationFactor
        if req.method:
            info["integrationMethod"] = req.method
        if req.maskLowerBound is not None:
            info["maskLowerBound"] = req.maskLowerBound
        info.update(merge_stats)

        return RunResponse(
            mergedFileId=merged_fid,
            ipAxisFileId=ip_fid,
            oopAxisFileId=oop_fid,
            unitIp=req.unitIp,
            unitOop=req.unitOop,
            ipRange=[float(ip_axis[0]), float(ip_axis[-1])],
            oopRange=[float(oop_axis[0]), float(oop_axis[-1])],
            nptIp=req.nptIp,
            nptOop=req.nptOop,
            ipAxis=ip_ds.tolist(),
            oopAxis=oop_ds.tolist(),
            preview=_nan_to_none(preview.tolist()),
            minIntensity=vmin,
            maxIntensity=vmax,
            images=images_out,
            info=info,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/render-png")
def render_png(req: RenderPngRequest):
    """Render a stored 2-D result as a labelled PNG (view / download)."""
    try:
        data = _load_npy(req.resultFileId)
        ip = _load_axis(req.ipAxisFileId) if req.ipAxisFileId else None
        oop = _load_axis(req.oopAxisFileId) if req.oopAxisFileId else None
        png = _render_png_bytes(data, ip, oop, req, req.unitIp, req.unitOop)
        return StreamingResponse(
            io.BytesIO(png),
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{req.baseName or "giwaxs"}.png"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


def _load_npy(file_id: str) -> np.ndarray:
    """Load a stored .npy result (any 2-D array from this module)."""
    from utils import _load_array
    arr = np.asarray(_load_array(file_id))
    if arr.ndim != 2:
        raise HTTPException(400, detail="Result must be a 2-D array (.npy).")
    return arr


def _load_axis(file_id: str) -> np.ndarray:
    """Load a stored .npy axis (1-D in-plane / out-of-plane coordinates)."""
    from utils import _load_array
    arr = np.asarray(_load_array(file_id)).ravel()
    return arr


@router.post("/export")
def export_zip(req: ExportRequest):
    """Bundle the merged map (.npy), axes and processing_info.json (+optional PNG)."""
    try:
        merged = _load_npy(req.mergedFileId)
        ip = _load_axis(req.ipAxisFileId) if req.ipAxisFileId else \
            np.linspace(-1.0, 1.0, merged.shape[1])
        oop = _load_axis(req.oopAxisFileId) if req.oopAxisFileId else \
            np.linspace(-1.0, 1.0, merged.shape[0])

        base = req.baseName or "giwaxs_merge"
        info = dict(req.info or {})
        info.setdefault("module", "PolymCrystRefine GIWAXS fiber-integration merge")
        info.setdefault("xAxisUnit", req.unitIp)
        info.setdefault("yAxisUnit", req.unitOop)
        info.setdefault("xAxisRange", [float(ip[0]), float(ip[-1])])
        info.setdefault("yAxisRange", [float(oop[0]), float(oop[-1])])
        info.setdefault("integrationPoints",
                        {"inPlane": int(merged.shape[1]), "outOfPlane": int(merged.shape[0])})

        entries = {
            f"{base}_giwaxs.npy": _save_array_bytes(merged),
            "ip_array.npy": _save_array_bytes(np.asarray(ip)),
            "oop_array.npy": _save_array_bytes(np.asarray(oop)),
            "processing_info.json": json.dumps(info, indent=2, ensure_ascii=False),
        }
        if req.includePng:
            settings = req.png or PngSettings()
            entries[f"{base}_giwaxs.png"] = _render_png_bytes(
                merged, np.asarray(ip), np.asarray(oop), settings, req.unitIp, req.unitOop)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries.items():
                zf.writestr(name, data)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{base}_giwaxs_merge.zip"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))
