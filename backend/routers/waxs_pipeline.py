"""
Integration-merge router (formerly the WAXS processing pipeline).

Batch import of already-integrated cakes / detector images, rolling-ball
background subtraction, and q-axis-aligned merging of multiple datasets.
Polarization-aware re-integration and PONI calibration live in the 2D
integration module; this router reuses the shared pyFAI helpers
(``_integrate_2d`` / ``_parse_poni``) and focuses on background + merge.

A merged result round-trips the imported ``processing_info.json`` so the
exported ZIP keeps the same standardized metadata the 2D integration
module emits.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from utils import (
    _file_path,
    _load_array,
    _save_array,
    _save_upload,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ParsePoniResponse(BaseModel):
    """Parameters parsed from a pyFAI PONI calibration file."""
    wavelength: float = Field(..., description="Wavelength in nm")
    dist: float = Field(..., description="Detector distance in meters")
    poni1: float = Field(..., description="PONI parameter 1")
    poni2: float = Field(..., description="PONI parameter 2")
    detector: str = Field(..., description="Detector type name")
    pixel1: float = Field(..., description="Pixel size 1 in meters")
    pixel2: float = Field(..., description="Pixel size 2 in meters")
    splineFile: Optional[str] = Field(None, description="Spline file path")
    maxShape: Optional[List[int]] = Field(None, description="Maximum detector shape [rows, cols]")


class ExportPoniRequest(BaseModel):
    """Calibration to serialise into a reusable .poni file.

    If ``poniFileId`` is set the calibration is round-tripped (parsed then
    re-emitted); otherwise the explicit parameters below are used.
    """
    poniFileId: Optional[str] = None
    wavelengthNm: Optional[float] = Field(None, description="Wavelength in nm")
    dist: Optional[float] = Field(None, description="Detector distance in meters")
    poni1: Optional[float] = None
    poni2: Optional[float] = None
    detector: Optional[str] = "Detector"
    pixel1: Optional[float] = Field(None, description="Pixel size 1 in meters")
    pixel2: Optional[float] = Field(None, description="Pixel size 2 in meters")
    rot1: float = 0.0
    rot2: float = 0.0
    rot3: float = 0.0
    splineFile: Optional[str] = None


class BackgroundRequest(BaseModel):
    fileId: str
    ballRadius: int = Field(20, ge=1, le=100)
    method: str = Field("scipy", description="scipy or skimage")
    rollingBallType: str = Field("classic", description="classic (minimum filter) or smooth (morphological opening)")
    fillValue: float = Field(0.0, description="clip floor for background-subtracted signal (values below this are replaced)")
    smoothingSigma: float = Field(0.0, ge=0, description="extra Gaussian smooth on the result (0 = off)")
    maskZeros: bool = Field(False, description="treat zero-valued pixels as mask: fill them before rolling-ball so they don't bias the background estimate")


class BackgroundResponse(BaseModel):
    signalFileId: str
    backgroundFileId: str


class MergeRequest(BaseModel):
    fileIds: List[str]
    fileInfos: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Per-file processing_info (xAxisRange/yAxisRangeDeg/"
                    "integrationPoints/xAxisUnit/polarizationFactor) used for "
                    "q-axis alignment. Length should match fileIds.",
    )
    chiOffsets: List[float] = Field(default_factory=list, description="Degrees offset per dataset")
    mergeMethod: str = Field("mean", description="mean / median / weighted / sequential")
    maskLowerBound: Optional[float] = Field(
        None,
        description="Mask lower bound: pixels below it (or non-finite) never "
                    "contribute to the merge; pixels with no valid contributor "
                    "are filled with maskLowerBound - 1. None disables masking.",
    )


class MergeResponse(BaseModel):
    mergedFileId: str
    qArrayFileId: Optional[str] = None
    chiArrayFileId: Optional[str] = None
    info: Dict[str, Any] = {}


class MergeExportRequest(BaseModel):
    mergedFileId: str
    qArrayFileId: Optional[str] = None
    chiArrayFileId: Optional[str] = None
    info: Dict[str, Any] = {}
    baseName: str = "merge"


class StepExportItem(BaseModel):
    """One recorded pipeline step to serialise into the steps-export ZIP.

    ``imageFileIds`` holds 1 id for a merge step or a background-on-merge step,
    and N ids for a per-image background step. q/chi/info are only meaningful
    for merge steps (and are written alongside the image then).
    """
    kind: str = Field("merge", description="merge | background")
    imageFileIds: List[str]
    qArrayFileId: Optional[str] = None
    chiArrayFileId: Optional[str] = None
    info: Dict[str, Any] = {}
    label: str = Field("step", description="sub-folder name inside the ZIP")


class StepsExportRequest(BaseModel):
    """Export one or many recorded steps into a single ZIP. Each step lands in
    its own sub-folder so single-step and all-steps exports share one path."""
    steps: List[StepExportItem]
    baseName: str = "polymcrystrefine_steps"


# ---------------------------------------------------------------------------
# Helpers -- shared with the 2D integration module
# ---------------------------------------------------------------------------

def _read_image(file_id: str) -> np.ndarray:
    """Read a detector image / cake from file-id (supports .npy, .edf, .tif, .h5, .hdf5)."""
    p = _file_path(file_id)
    ext = os.path.splitext(p)[1].lower()
    if ext == ".npy":
        return np.load(p, allow_pickle=True).astype(np.float64)
    if ext in (".h5", ".hdf5"):
        import h5py
        with h5py.File(p, "r") as h5:
            # Walk to first suitable 2-D dataset
            datasets: list[str] = []
            def _visitor(name, obj):
                if isinstance(obj, h5py.Dataset) and obj.ndim >= 2:
                    datasets.append(name)
            h5.visititems(_visitor)
            if not datasets:
                raise ValueError("No 2-D+ dataset found in HDF5 file")
            data = h5[datasets[0]][...]
            # Modern Eiger-style HDF5 files are often 4-D (1,1,y,x).
            # Squeeze singleton dims first, then take the first frame
            # if the result is still >2-D (e.g. a multi-frame stack).
            data = np.squeeze(data)
            if data.ndim > 2:
                data = data[0]
            return data.astype(np.float64)
    try:
        import fabio
        img = fabio.open(p)
        return img.data.astype(np.float64)
    except Exception:
        from PIL import Image
        return np.array(Image.open(p)).astype(np.float64)


def _parse_poni(file_id: str) -> dict:
    """Parse a pyFAI PONI file and return its calibration parameters."""
    from pyFAI import load as pyfai_load

    poni_path = _file_path(file_id)
    ai = pyfai_load(poni_path)

    detector = ai.detector
    detector_name = detector.name if detector is not None else "Unknown"
    pixel1 = detector.get_pixel1() if detector is not None else 0.0
    pixel2 = detector.get_pixel2() if detector is not None else 0.0

    spline_file = None
    if detector is not None and hasattr(detector, "splineFile") and detector.splineFile:
        spline_file = str(detector.splineFile)

    max_shape = None
    if detector is not None and hasattr(detector, "max_shape") and detector.max_shape is not None:
        max_shape = list(detector.max_shape)

    return {
        "wavelength": float(ai.wavelength) * 1e9,
        "dist": float(ai.dist),
        "poni1": float(ai.poni1),
        "poni2": float(ai.poni2),
        "detector": detector_name,
        "pixel1": float(pixel1),
        "pixel2": float(pixel2),
        "splineFile": spline_file,
        "maxShape": max_shape,
    }


def _integrate_2d(
    image: np.ndarray,
    poni_path: str,
    n_radial: int,
    n_azimuthal: int,
    method: str,
    unit: str = "q_nm^-1",
    mask: Optional[np.ndarray] = None,
    polarization_factor: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Azimuthal integration with pyFAI using integrate2d_ng.

    Returns (intensity_2d, q_array, chi_array).
    intensity_2d has shape (n_azimuthal, n_radial).

    ``polarization_factor`` is forwarded to pyFAI (typical synchrotron
    value ~0.99); ``None`` skips the polarization correction.
    """
    import warnings
    from pyFAI import load as pyfai_load

    ai = pyfai_load(poni_path)

    integration_method = (method, 'histogram', 'cython')

    mask_uint8 = None
    if mask is not None:
        mask_uint8 = mask.astype(np.uint8)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        I_cake, q_array, chi_array = ai.integrate2d_ng(
            image,
            npt_rad=n_radial,
            npt_azim=n_azimuthal,
            method=integration_method,
            unit=unit,
            correctSolidAngle=True,
            mask=mask_uint8,
            polarization_factor=polarization_factor,
        )

    return I_cake.astype(np.float64), q_array, chi_array


# ---------------------------------------------------------------------------
# Rolling-ball background (ported from reference)
# ---------------------------------------------------------------------------

def _rolling_ball_background(
    img2d: np.ndarray,
    radius: int,
    method: str = "scipy",
    rolling_ball_type: str = "classic",
    fill_value: float = 0.0,
    smoothing_sigma: float = 0.0,
    mask_zeros: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Rolling-ball background subtraction.

    *method* selects the implementation backend:

      * ``"skimage"`` — ``skimage.filters.rank.minimum`` on a uint16-normalised
        image (faster; classic type only).
      * ``"scipy"``    — ``scipy.ndimage`` filters.

    *rolling_ball_type* selects the estimator:

      * ``"classic"`` — minimum filter (the canonical rolling ball).
      * ``"smooth"``  — morphological opening (grey erosion + dilation),
        giving a smoother background; uses scipy morphology regardless of
        *method*.

    *smoothing_sigma* > 0 applies an extra Gaussian smooth to the final
    background-subtracted signal. *fill_value* is the floor for the
    signal after subtraction: values below it are clipped (default 0).

    *mask_zeros* replaces zero-valued pixels with a high percentile before
    the rolling-ball so they do not pull the minimum filter down; the mask
    is re-applied to the signal after subtraction.

    Returns ``(signal, background)``, both same shape as *img2d*.
    """
    from scipy.ndimage import (
        gaussian_filter,
        grey_dilation,
        grey_erosion,
        minimum_filter,
    )

    data = img2d.astype(np.float32)
    radius_int = max(int(radius), 1)

    # ---- zero-mask: replace zeros/near-zeros with a high percentile so they
    #      don't pull down the minimum-filter / erosion estimate ----
    zero_mask = None
    if mask_zeros:
        eps = 1e-12
        zero_mask = data <= eps
        if zero_mask.any() and not zero_mask.all():
            fill_val = float(np.percentile(data[~zero_mask], 95))
            data = np.where(zero_mask, fill_val, data)
        elif zero_mask.all():
            # All data is zero — nothing to subtract.
            return np.zeros_like(data, dtype=np.float64), np.zeros_like(data, dtype=np.float64)

    # Circular structuring element shared by the scipy-based branches.
    y, x = np.ogrid[-radius_int:radius_int + 1, -radius_int:radius_int + 1]
    kernel = (x * x + y * y <= radius_int * radius_int).astype(np.float32)

    if rolling_ball_type == "smooth":
        # Morphological opening: grey erosion followed by grey dilation.
        try:
            eroded = grey_erosion(data, footprint=kernel, mode="nearest")
            background = grey_dilation(eroded, footprint=kernel, mode="nearest")
        except Exception:
            background = minimum_filter(data, footprint=kernel, mode="nearest")
        if radius_int > 2:
            background = gaussian_filter(background, sigma=max(1, radius_int / 4.0))
    elif method == "skimage":
        # Fast uint16 rank-minimum on a normalised copy (classic only).
        from skimage.filters import rank as sk_rank
        from skimage.morphology import disk as sk_disk

        data_min = np.nanmin(data)
        data_max = np.nanmax(data)
        if data_max > data_min:
            data_norm = ((data - data_min) / (data_max - data_min) * 65535).astype(np.uint16)
        else:
            data_norm = np.zeros_like(data, dtype=np.uint16)

        selem = sk_disk(radius_int)
        try:
            bg_norm = sk_rank.minimum(data_norm, footprint=selem)
            if radius_int > 2:
                bg_norm = gaussian_filter(
                    bg_norm.astype(np.float32),
                    sigma=max(1, radius_int / 4.0),
                ).astype(np.uint16)
            background = (bg_norm.astype(np.float32) / 65535.0) * (data_max - data_min) + data_min
        except Exception:
            background = minimum_filter(data, footprint=kernel, mode="nearest")
            if radius_int > 2:
                background = gaussian_filter(background, sigma=max(1, radius_int / 4.0))
    else:
        # scipy classic: minimum filter.
        try:
            background = minimum_filter(data, footprint=kernel, mode="nearest")
            if radius_int > 2:
                background = gaussian_filter(background, sigma=max(1, radius_int / 4.0))
        except Exception:
            from scipy.ndimage import median_filter
            background = median_filter(data, size=max(3, radius_int))

    background = np.minimum(background, data)
    signal = np.clip(data - background, fill_value, None)

    if smoothing_sigma and float(smoothing_sigma) > 0:
        signal = gaussian_filter(signal, sigma=float(smoothing_sigma))

    # Re-apply zero mask so that originally-masked pixels stay zero in the
    # output signal (and the background is also zeroed there for consistency).
    if zero_mask is not None:
        signal[zero_mask] = 0.0
        background[zero_mask] = 0.0

    return signal.astype(np.float64), background.astype(np.float64)


def _combine_arrays(
    shifted: List[np.ndarray],
    method: str = "mean",
    mask_lower_bound: Optional[float] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Per-pixel combination of aligned 2-D arrays.

    When *mask_lower_bound* is given, each input masks its own pixels below
    the bound (and non-finite pixels) before combining — masked pixels never
    contribute, mirroring reference/function1/pages/combine.py. Pixels with
    no valid contributor in any input are filled with ``mask_lower_bound - 1``.

    "sequential" keeps the first valid value per pixel (input order) instead
    of averaging. Without a threshold, sequential treats only non-finite
    pixels as invalid.

    Returns ``(merged, meta)`` where *meta* carries ``masked``,
    ``fillValue`` and ``uncoveredFraction`` for the processing_info.
    """
    if not shifted:
        raise ValueError("No arrays to merge")

    masked_mode = mask_lower_bound is not None
    fill_value = (mask_lower_bound - 1.0) if masked_mode else 0.0

    if method == "sequential":
        out = np.full(shifted[0].shape, fill_value, dtype=np.float64)
        has_value = np.zeros(shifted[0].shape, dtype=bool)
        for arr in shifted:
            ok = (np.isfinite(arr) & (arr >= mask_lower_bound)) if masked_mode else np.isfinite(arr)
            take = ok & ~has_value
            out[take] = arr[take]
            has_value |= take
        meta = {
            "masked": masked_mode,
            "fillValue": fill_value if masked_mode else None,
            "uncoveredFraction": float((~has_value).mean()) if masked_mode else None,
        }
        return out, meta

    stack = np.stack(shifted, axis=0)
    if not masked_mode:
        if method == "median":
            return np.median(stack, axis=0), {"masked": False, "fillValue": None, "uncoveredFraction": None}
        if method == "weighted":
            weights = np.array([1.0 / (a.var() + 1e-12) for a in shifted])
            weights /= weights.sum()
            return np.tensordot(weights, stack, axes=([0], [0])), {
                "masked": False, "fillValue": None, "uncoveredFraction": None,
            }
        return np.mean(stack, axis=0), {"masked": False, "fillValue": None, "uncoveredFraction": None}

    mask_stack = np.stack([~(np.isfinite(a) & (a >= mask_lower_bound)) for a in shifted], axis=0)
    combined = np.ma.array(stack, mask=mask_stack)
    if method == "median":
        result = np.ma.median(combined, axis=0)
    elif method == "weighted":
        weights = np.array([1.0 / (a.var() + 1e-12) for a in shifted])
        weights /= weights.sum()
        result = np.ma.average(combined, axis=0, weights=weights)
    else:
        result = np.ma.mean(combined, axis=0)
    uncovered = float((np.ma.count(combined, axis=0) == 0).mean())
    merged = np.ma.filled(np.ma.asarray(result, dtype=np.float64), fill_value)
    return merged, {"masked": True, "fillValue": float(fill_value), "uncoveredFraction": uncovered}


def _chi_shift_and_merge(
    arrays: List[np.ndarray],
    chi_offsets_deg: List[float],
    method: str = "mean",
    mask_lower_bound: Optional[float] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Shift each 2-D array along the azimuthal (chi) axis and merge.

    *chi_offsets_deg* are in degrees; they are converted to pixel rows
    assuming the first axis spans 0-360 degrees.
    """
    if not arrays:
        raise ValueError("No arrays to merge")
    n_az = arrays[0].shape[0]
    deg_per_pixel = 360.0 / n_az

    shifted: List[np.ndarray] = []
    for idx, arr in enumerate(arrays):
        offset_deg = chi_offsets_deg[idx] if idx < len(chi_offsets_deg) else 0.0
        shift_px = int(round(offset_deg / deg_per_pixel))
        shifted.append(np.roll(arr, shift_px, axis=0))

    return _combine_arrays(shifted, method, mask_lower_bound)


def _save_array_bytes(arr: np.ndarray) -> bytes:
    """Serialise an array to .npy bytes (in memory)."""
    buf = io.BytesIO()
    np.save(buf, np.asarray(arr))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# q-axis-aligned merge
# ---------------------------------------------------------------------------

def _align_and_merge(
    arrays: List[np.ndarray],
    file_infos: List[Dict[str, Any]],
    chi_offsets_deg: List[float],
    method: str = "mean",
    mask_lower_bound: Optional[float] = None,
) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], Dict[str, Any]]:
    """Align cakes onto a common radial axis derived from per-file
    ``processing_info``, then merge.

    Each info needs an ``xAxisRange`` pair; the union span of all ranges
    becomes the common q axis, and every cake is resampled onto it via
    ``np.interp``. When no usable per-file info is provided, falls back to
    a plain chi-shift merge.

    Returns ``(merged, q_axis, chi_axis, info)``.
    """
    if not arrays:
        raise ValueError("No arrays to merge")

    infos = [fi for fi in (file_infos or []) if isinstance(fi, dict)]
    ranged = [
        fi for fi in infos
        if isinstance(fi.get("xAxisRange"), (list, tuple)) and len(fi["xAxisRange"]) == 2
    ]

    # Need one usable info per array to align meaningfully; otherwise chi-shift.
    if not ranged or len(ranged) != len(arrays):
        merged, combine_meta = _chi_shift_and_merge(arrays, chi_offsets_deg, method, mask_lower_bound)
        n_az, n_rad = merged.shape
        chi_axis = np.linspace(-180.0, 180.0, n_az)
        q_axis = np.linspace(0.0, n_rad - 1, n_rad)
        info: Dict[str, Any] = {
            "module": "PolymCrystRefine integration merge",
            "mergeMethod": method,
            "mergedFileCount": len(arrays),
            "aligned": False,
            **combine_meta,
            "xAxisRange": [float(q_axis.min()), float(q_axis.max())],
            "yAxisRangeDeg": [float(chi_axis.min()), float(chi_axis.max())],
            "integrationPoints": {"radial": int(n_rad), "azimuthal": int(n_az)},
        }
        return merged, q_axis, chi_axis, info

    # Common radial axis = union span of all xAxisRanges.
    q_mins = [float(fi["xAxisRange"][0]) for fi in ranged]
    q_maxs = [float(fi["xAxisRange"][1]) for fi in ranged]
    q_lo, q_hi = min(q_mins), max(q_maxs)

    declared_rad = [
        int(fi.get("integrationPoints", {}).get("radial"))
        for fi in ranged
        if isinstance(fi.get("integrationPoints", {}).get("radial"), (int, float))
    ]
    declared_rad = [r for r in declared_rad if r > 0]
    n_rad = max(declared_rad) if declared_rad else max(a.shape[1] for a in arrays)
    common_q = np.linspace(q_lo, q_hi, n_rad)

    aligned: List[np.ndarray] = []
    for arr, fi in zip(arrays, ranged):
        src_lo, src_hi = float(fi["xAxisRange"][0]), float(fi["xAxisRange"][1])
        n_az, n_src = arr.shape
        src_q = np.linspace(src_lo, src_hi, n_src)
        # np.interp requires increasing xp; flip if descending.
        if src_q[0] > src_q[-1]:
            src_q = src_q[::-1]
            arr = arr[:, ::-1]
        out = np.empty((n_az, n_rad), dtype=np.float64)
        for r in range(n_az):
            out[r] = np.interp(common_q, src_q, arr[r])
        aligned.append(out)

    # Optional chi-axis shift before stacking. Use the real chi span from the
    # shared processing_info (fall back to a 360 deg assumption when absent).
    if chi_offsets_deg:
        n_az = aligned[0].shape[0]
        yr = ranged[0].get("yAxisRangeDeg")
        chi_span = (
            abs(float(yr[1]) - float(yr[0]))
            if isinstance(yr, (list, tuple)) and len(yr) == 2 else 360.0
        )
        deg_per_pixel = (chi_span or 360.0) / n_az
        aligned = [
            np.roll(a, int(round((chi_offsets_deg[i] if i < len(chi_offsets_deg) else 0.0) / deg_per_pixel)), axis=0)
            for i, a in enumerate(aligned)
        ]

    merged, combine_meta = _combine_arrays(aligned, method, mask_lower_bound)

    yr = ranged[0].get("yAxisRangeDeg")
    if isinstance(yr, (list, tuple)) and len(yr) == 2:
        chi_axis = np.linspace(float(yr[0]), float(yr[1]), merged.shape[0])
    else:
        chi_axis = np.linspace(-180.0, 180.0, merged.shape[0])

    unit = ranged[0].get("xAxisUnit") or ranged[0].get("unit") or "q_nm^-1"
    pols = [fi.get("polarizationFactor") for fi in ranged if fi.get("polarizationFactor") is not None]

    info = {
        "module": "PolymCrystRefine integration merge",
        "mergeMethod": method,
        "mergedFileCount": len(arrays),
        "aligned": True,
        **combine_meta,
        "xAxisUnit": unit,
        "xAxisRange": [q_lo, q_hi],
        "yAxisRangeDeg": [float(chi_axis.min()), float(chi_axis.max())],
        "integrationPoints": {"radial": int(n_rad), "azimuthal": int(merged.shape[0])},
    }
    if pols and all(p == pols[0] for p in pols):
        info["polarizationFactor"] = pols[0]
    return merged, common_q, chi_axis, info


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/parse-poni", response_model=ParsePoniResponse)
def parse_poni(fileId: str = Body(..., embed=True)):
    """Parse a pyFAI PONI calibration file and return its parameters."""
    try:
        return ParsePoniResponse(**_parse_poni(fileId))
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/export-poni")
def export_poni(req: ExportPoniRequest):
    """Export a reusable pyFAI .poni calibration file.

    Round-trips an uploaded PONI (``poniFileId``) or serialises explicit
    parameters, so every pyFAI-based step can reuse the same calibration.
    """
    try:
        if req.poniFileId:
            params = _parse_poni(req.poniFileId)
            wavelength_nm = params["wavelength"]
            dist = params["dist"]
            poni1 = params["poni1"]
            poni2 = params["poni2"]
            detector = params["detector"]
            pixel1 = params["pixel1"]
            pixel2 = params["pixel2"]
            spline_file = params.get("splineFile")
            rot1 = rot2 = rot3 = 0.0
        else:
            missing = [k for k, v in {
                "wavelengthNm": req.wavelengthNm, "dist": req.dist,
                "poni1": req.poni1, "poni2": req.poni2,
                "pixel1": req.pixel1, "pixel2": req.pixel2,
            }.items() if v is None]
            if missing:
                raise HTTPException(400, detail=f"Missing calibration parameters: {', '.join(missing)}")
            wavelength_nm = req.wavelengthNm
            dist = req.dist
            poni1 = req.poni1
            poni2 = req.poni2
            detector = req.detector or "Detector"
            pixel1 = req.pixel1
            pixel2 = req.pixel2
            spline_file = req.splineFile
            rot1, rot2, rot3 = req.rot1, req.rot2, req.rot3

        spline_line = f"SplineFile: {spline_file}\n" if spline_file else ""
        poni_text = (
            "# PONI calibration exported by PolymCrystRefine\n"
            f"Distance: {dist}\n"
            f"Poni1: {poni1}\n"
            f"Poni2: {poni2}\n"
            f"Rot1: {rot1}\n"
            f"Rot2: {rot2}\n"
            f"Rot3: {rot3}\n"
            f"Wavelength: {(wavelength_nm or 0) * 1e-9}\n"
            f"{spline_line}"
            f"Detector: {detector}\n"
            f"PixelSize1: {pixel1}\n"
            f"PixelSize2: {pixel2}\n"
        )
        data = poni_text.encode("utf-8")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="calibration.poni"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/upload")
def upload_files(files: List[UploadFile] = File(...)):
    """Accept multiple detector images / cakes for batch import."""
    saved: list[dict] = []
    for f in files:
        data = f.file.read()
        ext = os.path.splitext(f.filename or "")[1]
        fid = _save_upload(data, suffix=ext)
        saved.append({"fileId": fid, "originalName": f.filename, "size": len(data)})
    return {"files": saved}


@router.post("/background", response_model=BackgroundResponse)
def background(req: BackgroundRequest):
    """Rolling-ball background subtraction (classic/smooth, scipy/skimage)."""
    try:
        arr = _load_array(req.fileId)
        signal, bg = _rolling_ball_background(
            arr, req.ballRadius, req.method,
            req.rollingBallType, req.fillValue, req.smoothingSigma,
            mask_zeros=req.maskZeros,
        )
        return BackgroundResponse(
            signalFileId=_save_array(signal),
            backgroundFileId=_save_array(bg),
        )
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/merge", response_model=MergeResponse)
def merge(req: MergeRequest):
    """q-axis-aligned merge of multiple cakes, driven by per-file processing_info."""
    try:
        arrays = [_load_array(fid) for fid in req.fileIds]
        merged, q_axis, chi_axis, info = _align_and_merge(
            arrays, req.fileInfos, req.chiOffsets, req.mergeMethod,
            mask_lower_bound=req.maskLowerBound,
        )
        fid_out = _save_array(merged)
        q_fid = _save_array(q_axis) if q_axis is not None else None
        chi_fid = _save_array(chi_axis) if chi_axis is not None else None
        return MergeResponse(
            mergedFileId=fid_out,
            qArrayFileId=q_fid,
            chiArrayFileId=chi_fid,
            info=info,
        )
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/merge/export")
def merge_export(req: MergeExportRequest):
    """Bundle the merged cake + axes + processing_info.json.

    The imported per-file info is round-tripped (and completed with the
    merged array's actual ranges/points) so the exported ZIP keeps the same
    standardized metadata the 2D integration module emits.
    """
    try:
        merged = _load_array(req.mergedFileId)
        q_arr = _load_array(req.qArrayFileId) if req.qArrayFileId else np.arange(merged.shape[1], dtype=np.float64)
        chi_arr = _load_array(req.chiArrayFileId) if req.chiArrayFileId else np.arange(merged.shape[0], dtype=np.float64)

        info = dict(req.info or {})
        info.setdefault("module", "PolymCrystRefine integration merge")
        info.setdefault("xAxisRange", [float(np.nanmin(q_arr)), float(np.nanmax(q_arr))])
        info.setdefault("yAxisRangeDeg", [float(np.nanmin(chi_arr)), float(np.nanmax(chi_arr))])
        info.setdefault("integrationPoints", {"radial": int(merged.shape[1]), "azimuthal": int(merged.shape[0])})
        info_text = json.dumps(info, indent=2, ensure_ascii=False)

        base = req.baseName or "merge"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{base}_merged.npy", _save_array_bytes(merged))
            zf.writestr("q_array.npy", _save_array_bytes(np.asarray(q_arr)))
            zf.writestr("chi_array.npy", _save_array_bytes(np.asarray(chi_arr)))
            zf.writestr("processing_info.json", info_text)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{base}_merge.zip"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/steps/export")
def steps_export(req: StepsExportRequest):
    """Bundle one or many recorded pipeline steps into a single ZIP.

    Each step is written under its own sub-folder ``{label}/``:

    * merge step (or any step carrying q/chi/info) → ``image.npy`` +
      ``q_array.npy`` + ``chi_array.npy`` + ``processing_info.json``;
    * background step → ``image.npy`` (single) or ``image_01.npy … image_NN.npy``
      (per-image).

    Single-step export simply passes one item; all-steps export passes the
    whole log. Either way the on-disk layout is identical.
    """
    try:
        if not req.steps:
            raise HTTPException(400, detail="No steps to export")

        base = req.baseName or "polymcrystrefine_steps"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for step in req.steps:
                folder = step.label or "step"
                if not step.imageFileIds:
                    continue

                # Merge-style step: one image plus axes + metadata.
                has_axes = step.kind == "merge" or bool(step.qArrayFileId or step.chiArrayFileId)
                if has_axes:
                    img = _load_array(step.imageFileIds[0])
                    zf.writestr(f"{folder}/image.npy", _save_array_bytes(img))
                    q_arr = (
                        _load_array(step.qArrayFileId)
                        if step.qArrayFileId
                        else np.arange(img.shape[1], dtype=np.float64)
                    )
                    chi_arr = (
                        _load_array(step.chiArrayFileId)
                        if step.chiArrayFileId
                        else np.arange(img.shape[0], dtype=np.float64)
                    )
                    zf.writestr(f"{folder}/q_array.npy", _save_array_bytes(np.asarray(q_arr)))
                    zf.writestr(f"{folder}/chi_array.npy", _save_array_bytes(np.asarray(chi_arr)))
                    info = dict(step.info or {})
                    info.setdefault("module", "PolymCrystRefine integration merge")
                    info.setdefault("xAxisRange", [float(np.nanmin(q_arr)), float(np.nanmax(q_arr))])
                    info.setdefault("yAxisRangeDeg", [float(np.nanmin(chi_arr)), float(np.nanmax(chi_arr))])
                    info.setdefault(
                        "integrationPoints",
                        {"radial": int(img.shape[1]), "azimuthal": int(img.shape[0])},
                    )
                    zf.writestr(f"{folder}/processing_info.json", json.dumps(info, indent=2, ensure_ascii=False))
                elif len(step.imageFileIds) == 1:
                    # Background step with a single image (e.g. background-on-merge).
                    img = _load_array(step.imageFileIds[0])
                    zf.writestr(f"{folder}/image.npy", _save_array_bytes(img))
                else:
                    # Per-image background step: keep every subtracted cake.
                    for i, fid in enumerate(step.imageFileIds, start=1):
                        img = _load_array(fid)
                        zf.writestr(f"{folder}/image_{i:02d}.npy", _save_array_bytes(img))
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{base}.zip"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))
