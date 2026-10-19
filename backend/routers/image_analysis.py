"""
Image analysis router.

Provides 2-D image upload / display, ROI intensity integration,
ROI CSV export, Miller-index matching, and DBSCAN-based background
estimation (POST /background-estimate).

Background modes (per-ROI subtraction during intensity integration):
  - none      : no background subtraction
  - fixed     : subtract a user-provided constant value per pixel
  - neighbor  : subtract the mean of the pixel columns adjacent to the ROI on a
                selectable side (left / right / both) over a unified band width
  - annular   : mean of surrounding expanded ring
  - radial    : mean along q at same chi range, shifted +/-offset
  - median2d  : median-filtered local background

DBSCAN background estimation (global, run before integration):
bright pixels are clustered; the non-cluster remainder is the background.
The estimated level is applied via mode=fixed by the UI.
"""

from __future__ import annotations

import io
import json
import math
import os
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from config import OUTPUT_DIR, UPLOAD_DIR
from utils import (
    _file_path,
    _identify_q_unit,
    _parse_processing_info,
    _q_range_to_angstrom,
    _save_output,
    _save_upload,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_file_meta: Dict[str, Dict[str, Any]] = {}  # fileId -> metadata


def _load_image(file_id: str) -> np.ndarray:
    """Load a 2-D image from its file-id (npy / h5 / hdf5 / edf / tiff)."""
    p = _file_path(file_id)
    ext = os.path.splitext(p)[1].lower()
    if ext == ".npy":
        return np.load(p, allow_pickle=True).astype(np.float64)
    if ext in (".h5", ".hdf5"):
        import h5py
        with h5py.File(p, "r") as h5:
            datasets: list[str] = []
            def _visitor(name, obj):
                if isinstance(obj, h5py.Dataset) and obj.ndim >= 2:
                    datasets.append(name)
            h5.visititems(_visitor)
            if not datasets:
                raise ValueError("No 2-D+ dataset found in HDF5 file")
            data = h5[datasets[0]][...]
            # Modern Eiger-style HDF5 files are often 4-D (1,1,y,x).
            # Squeeze singleton dims first, then take the first frame.
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


def _downsample(arr: np.ndarray, max_dim: int = 512) -> np.ndarray:
    """Downsample a 2-D array so neither dimension exceeds *max_dim*."""
    from scipy.ndimage import zoom

    h, w = arr.shape
    if h <= max_dim and w <= max_dim:
        return arr
    factor = min(max_dim / h, max_dim / w)
    return zoom(arr, factor)


def _finite_min_max(arr: np.ndarray):
    """Min/max over finite values only (NaN/inf ignored).

    Cakes straight from pyFAI (or other integrators) carry NaN in empty/edge
    bins; ``arr.min()/max()`` would otherwise return NaN and the frontend's
    contrast window collapses, making the heatmap render blank.
    """
    flat = arr.ravel()
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return None, None
    return float(flat.min()), float(flat.max())


def _safe_mean(a: np.ndarray) -> float:
    """Mean over finite values; 0.0 when the slice has no finite data."""
    a = np.asarray(a).ravel()
    a = a[np.isfinite(a)]
    return float(a.mean()) if a.size else 0.0


def _safe_median(a: np.ndarray) -> float:
    """Median over finite values; 0.0 when the slice has no finite data."""
    a = np.asarray(a).ravel()
    a = a[np.isfinite(a)]
    return float(np.median(a)) if a.size else 0.0


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class UploadImageResponse(BaseModel):
    fileId: str
    shape: List[int]
    dtype: str
    preview: List[List[float]]
    qRange: List[float]
    chiRange: List[float]
    processingInfo: Optional[str] = None


class ParseInfoResponse(BaseModel):
    """Axis ranges parsed from a standalone processing_info sidecar.

    q is always returned in Å^-1 (nm^-1 inputs are converted); chi in degrees.
    Fields are None when the sidecar does not declare them. ``unit`` is the
    detected *source* q unit ("Å^-1" / "nm^-1"), or None if unstated.
    """
    qRange: Optional[List[float]] = None
    chiRange: Optional[List[float]] = None
    unit: Optional[str] = None


class MillerPoint(BaseModel):
    h: int
    k: int
    l: int
    q: float
    psi: float  # chi-equivalent angle


class MillerDataset(BaseModel):
    name: str
    points: List[MillerPoint]
    fileId: str


class UploadMillerResponse(BaseModel):
    datasets: List[MillerDataset]


class BackgroundConfig(BaseModel):
    """Background subtraction configuration."""
    mode: str = Field("none", description="none | fixed | neighbor | annular | radial | median2d")
    fixedValue: float = Field(0.0, description="Per-pixel constant to subtract (mode=fixed)")
    # mode=neighbor: which side of the ROI bounding box supplies the background.
    # "left" / "right" sample a single side (the reference PyQt tool's 单侧选取);
    # "both" averages the two sides (legacy behaviour).
    side: str = Field("both", description="Neighbour side to sample: left | right | both (mode=neighbor)")
    # Unified neighbour band width in pixel columns (mode=neighbor). Applies to
    # whichever side(s) `side` selects. Default 10 per the original requirement.
    width: Optional[int] = Field(10, ge=0, description="Neighbour band width in pixel columns (mode=neighbor)")
    # Deprecated legacy per-side widths; only used when `width` is None.
    leftPixels: int = Field(5, description="Legacy: left neighbour columns (used only when width is None)")
    rightPixels: int = Field(5, description="Legacy: right neighbour columns (used only when width is None)")


class ROI(BaseModel):
    """Cake-image ROI in physical coordinates (q / azimuth)."""
    qMin: float = 0.0
    qMax: float = 0.0
    azimuthMin: float = 0.0
    azimuthMax: float = 0.0
    # Pixel-coordinate ROI fields (detector images)
    xMin: Optional[float] = None
    xMax: Optional[float] = None
    yMin: Optional[float] = None
    yMax: Optional[float] = None
    multiplier: float = 1.0
    # Optional *refine match box* (mirrors reference/function3). The integration
    # ROI above can be drawn large to capture a whole diffraction arc for good
    # intensity statistics, which also sweeps up many spurious Miller points.
    # When these four are set, Miller matching uses this smaller box instead of
    # the integration box so the user can pin the single true peak. Only read by
    # match_miller; intensity integration ignores them.
    matchQMin: Optional[float] = None
    matchQMax: Optional[float] = None
    matchAzMin: Optional[float] = None
    matchAzMax: Optional[float] = None
    # Per-peak background subtraction override. When set, this ROI integrates
    # with its own background config instead of the request-wide one — peaks
    # sitting at the q-range edge (neighbour band clipped) or on a sloping
    # background can use a different mode / side than their neighbours.
    background: Optional[BackgroundConfig] = None


class IntensityRequest(BaseModel):
    fileId: str
    regions: List[ROI]
    backgroundMode: int = Field(0, ge=0, le=3, description="Legacy: 0=none, 1=annular, 2=radial, 3=2D-median")
    background: Optional[BackgroundConfig] = Field(None, description="New background config (takes precedence)")
    coordinateType: str = Field("physical", description="'physical' for cake coords, 'pixel' for detector coords, 'pyfai' for q/chi windows resolved through a PONI calibration")
    # PONI calibration file id (required when coordinateType == 'pyfai'). The
    # per-pixel q (Å⁻¹) and χ (°) geometry arrays are built from it and each
    # ROI's q/χ window selects the contributing detector pixels — the same
    # bin assignment pyFAI's radial (linear) and azimuthal integrators use.
    poniFileId: Optional[str] = Field(None, description="Uploaded PONI file id (coordinateType='pyfai')")
    # Axis ranges of the cake image the ROIs were drawn on. Required to map the
    # ROI's physical (q/χ) coords onto the correct pixel rows/cols — without
    # these the mask fell back to hard-coded (0,25)/(0,360) and integrated the
    # wrong pixels whenever the real range differed (e.g. χ ∈ [-180,180]).
    qRange: Optional[List[float]] = None
    chiRange: Optional[List[float]] = None
    # Saturation mask: pixels below/above these thresholds (or non-finite) are
    # excluded from the ROI integration. Without this, sentinel / saturated
    # pixels that upstream tools store as the array maximum flow straight into
    # the sum and dominate the extracted intensity.
    minIntensity: Optional[float] = Field(0.0, description="Exclude ROI pixels below this value (default 0 keeps zeros, excludes negative fill)")
    maxIntensity: Optional[float] = Field(None, description="Exclude ROI pixels above this value (saturate mask)")


class ROIIntensity(BaseModel):
    region: ROI
    meanIntensity: float
    totalIntensity: float
    pixelCount: int


class IntensityResponse(BaseModel):
    results: List[ROIIntensity]


class PoniInfoResponse(BaseModel):
    """Geometry parsed from a pyFAI PONI calibration file.

    Wavelength is reported in Å and distances in mm for display; pixel sizes
    in μm. ``shape`` is the detector's expected pixel-grid shape (rows, cols).
    """
    fileId: str
    wavelength: float
    dist: float
    poni1: float
    poni2: float
    rot1: float
    rot2: float
    rot3: float
    detector: str
    pixel1: float
    pixel2: float
    shape: Optional[List[int]] = None
    # Beam-centre pixel (col, row) = (poni2/pixel2, poni1/pixel1).
    centerX: float
    centerY: float


class DetectorRoiWindowRequest(BaseModel):
    """Convert a pixel box on a calibrated detector image into the q/χ window
    it covers (min/max of the pyFAI geometry arrays inside the box)."""
    poniFileId: str
    xMin: float
    xMax: float
    yMin: float
    yMax: float
    shape: Optional[List[int]] = Field(None, description="Detector image shape (rows, cols) when it differs from the PONI's own shape")


class DetectorRoiWindowResponse(BaseModel):
    qMin: float
    qMax: float
    azimuthMin: float
    azimuthMax: float


class DetectorClickRequest(BaseModel):
    """Locate a point on the raw detector image (no peak-picking semantics —
    the raw clicked pixel, or optionally the brightest pixel in a small
    window when snap=True)."""
    fileId: str
    poniFileId: str
    x: float = Field(..., description="Click position, ORIGINAL detector pixel x")
    y: float = Field(..., description="Click position, ORIGINAL detector pixel y")
    window: int = Field(30, ge=3, description="Square snap-search window in pixels (snap=True only)")
    snap: bool = Field(True, description="Snap to the brightest valid pixel inside the window")
    minIntensity: Optional[float] = None
    maxIntensity: Optional[float] = None


class DetectorClickResponse(BaseModel):
    x: int
    y: int
    intensity: float
    q: float
    psiDeg: float


class DetectorIntegrateRequest(BaseModel):
    """Radial (q-I) + azimuthal (ψ-I) integration around an anchor point.

    Ranges are ± half-widths around the anchor's (q₀, ψ₀), mirroring the
    R1.7all PeakExtraction workflow:
      q-I : q ∈ q₀ ± radialHalf, χ ∈ ψ₀ ± azimuthHalf   (npt q bins)
      ψ-I : q ∈ q₀ ± radialHalfR, χ ∈ ψ₀ ± azimuthHalfR (nptR χ bins,
            nptRadR radial bins per χ bin)
    """
    fileId: str
    poniFileId: str
    x: float
    y: float
    azimuthHalf: float = Field(5.0, gt=0)
    radialHalf: float = Field(0.35, gt=0)
    npt: int = Field(500, ge=16)
    radialHalfR: float = Field(0.05, gt=0)
    azimuthHalfR: float = Field(30.0, gt=0)
    nptR: int = Field(150, ge=8)
    nptRadR: int = Field(50, ge=4)
    excludeEmptyBins: bool = True
    minIntensity: Optional[float] = None
    maxIntensity: Optional[float] = None


class DetectorIntegrateResponse(BaseModel):
    qValues: List[Optional[float]]
    iQ: List[Optional[float]]
    psiValues: List[Optional[float]]
    iPsi: List[Optional[float]]
    currentQ: float
    currentPsi: float
    # Outline of the extraction wedge (q₀±radialHalf × ψ₀±azimuthHalfR) in
    # ORIGINAL pixel [x, y] pairs, for overlay on the displayed heatmap.
    wedgePolygon: List[List[float]] = []
    wedgeQMin: float = 0.0
    wedgeQMax: float = 0.0
    wedgeAzMin: float = 0.0
    wedgeAzMax: float = 0.0


class DetectorCalcPixelRequest(BaseModel):
    """Refine the anchor: map a (q, ψ) picked on the integration curves back
    to a detector pixel."""
    fileId: str
    poniFileId: str
    selectedQ: Optional[float] = None
    selectedPsi: Optional[float] = None
    currentQ: float
    currentPsi: float


class DetectorCalcPixelResponse(BaseModel):
    x: int
    y: int
    intensity: float
    q: float
    psiDeg: float


class DetectorWedgeRequest(BaseModel):
    """Outline of an ARBITRARY q/χ region (the range the user selected on the
    integration curves) in ORIGINAL pixel coordinates, for overlay on the
    heatmap and as the bbox seed when recording it as a ROI."""
    poniFileId: str
    shape: List[int]
    qMin: float
    qMax: float
    azimuthMin: float
    azimuthMax: float


class DetectorWedgeResponse(BaseModel):
    polygon: List[List[float]] = []


class BackgroundEstimateRequest(BaseModel):
    """DBSCAN-based background estimation request.

    Workflow: bright pixels (above ``thresholdPercentile``) are clustered with
    DBSCAN in normalized image coordinates; the clusters are the diffraction
    peaks, everything else is background. Recorded ROI regions (``regions``)
    are always treated as peaks so user-confirmed peak boxes are excluded from
    the background even when DBSCAN misses them. The background level is the
    ``backgroundPercentile`` percentile of the non-peak pixel intensities.
    """
    fileId: str
    qRange: Optional[List[float]] = None
    chiRange: Optional[List[float]] = None
    # Percentile of finite pixel intensities above which a pixel is a peak
    # candidate (DBSCAN only sees bright pixels — clustering the whole image
    # is unnecessary and slow).
    thresholdPercentile: float = Field(90.0, ge=0.0, le=100.0)
    # DBSCAN neighbourhood radius in normalized [0,1] image coordinates
    # (1.0 = full image extent), so eps is independent of image resolution.
    eps: float = Field(0.02, gt=0.0, le=1.0)
    minSamples: int = Field(10, ge=1)
    # Clusters smaller than this many pixels are demoted to background noise.
    minClusterPixels: int = Field(30, ge=1)
    # Grow the peak mask by N pixels (8-connected) to cover peak tails that
    # sit just under the brightness threshold.
    dilationPixels: int = Field(2, ge=0, le=20)
    # Percentile of non-peak pixels reported as the background level
    # (50 = median; a higher value gives a more conservative estimate).
    backgroundPercentile: float = Field(50.0, ge=0.0, le=100.0)
    # User-confirmed peak regions (recorded ROIs) excluded from background.
    regions: Optional[List[ROI]] = None
    # Validity window, same semantics as /intensity.
    minIntensity: Optional[float] = None
    maxIntensity: Optional[float] = None


class ClusterStat(BaseModel):
    """Summary of one DBSCAN peak cluster."""
    q: float
    chi: float
    pixels: int
    meanIntensity: float


class BackgroundEstimateResponse(BaseModel):
    backgroundValue: float
    threshold: float
    nClusters: int
    peakPixelCount: int
    backgroundPixelCount: int
    # Peak mask downsampled to the /image display grid (1 = peak pixel), so
    # the frontend can overlay it exactly on the displayed heatmap.
    previewMask: List[List[float]]
    clusters: List[ClusterStat] = []


class ExportRoiRequest(BaseModel):
    regions: List[ROI]


class MatchMillerRequest(BaseModel):
    regions: List[ROI]
    millerDatasets: List[MillerDataset]
    qTolerance: float = Field(0.1, description="q matching tolerance (A^-1)")
    chiTolerance: float = Field(5.0, description="chi/psi matching tolerance (degrees)")
    # Miller→cake azimuth transform. Must mirror the overlay math in the UI so a
    # point drawn at χ=30° actually matches an ROI whose centre χ≈30°. Without
    # these the backend compared raw psi against raw ROI χ, but the UI displays
    # ψ after this offset/convention/normalization — so visually-aligned points
    # never matched.
    azimuthOffset: float = Field(0.0, description="Reference azimuth ψ₀ added to ψ before matching (degrees)")
    convention: str = Field("CCW", description="'CCW' (χ=ψ₀+ψ) or 'CW' (χ=ψ₀−ψ)")
    normalizeToSigned: bool = Field(True, description="Wrap χ into [−180,180) to match the cake χ axis convention")
    # Export margins: the exported q/ψ window is the min/max of the matched
    # Miller points inside the search box (refine box when present, else the
    # integration ROI) grown by these amounts, so the window fully covers the
    # peak but does not sweep in neighbours. The no-match fallback grows the
    # raw search box by the same margins (it used to apply none at all).
    exportQMargin: float = Field(0.02, ge=0.0, description="dq added/subtracted around min/max q for export (A^-1)")
    exportPsiMargin: float = Field(2.0, ge=0.0, description="dpsi added/subtracted around min/max psi for export (degrees)")


class MatchResult(BaseModel):
    region: ROI
    status: str  # "Found" or "Not Found"
    matchedPoints: List[MillerPoint] = []
    # Whether matching used a user-drawn refine box (vs. the integration ROI).
    refined: bool = False
    # Export ranges derived from the matched Miller points — q ± 0.02 Å⁻¹ and
    # ψ ± 3° around the matched points (NOT the integration-box ranges). When no
    # point matches, the search box is inverse-mapped to Miller ψ so the export
    # columns still carry Miller-space numbers. Mirrors reference/function3's
    # calculate_match_for_area "New_Q/PSI" output.
    exportQMin: Optional[float] = None
    exportQMax: Optional[float] = None
    exportPsiMin: Optional[float] = None
    exportPsiMax: Optional[float] = None


class MatchMillerResponse(BaseModel):
    results: List[MatchResult]


# ---------------------------------------------------------------------------
# Coordinate conversion helpers
# ---------------------------------------------------------------------------

def _resolve_ranges(
    file_id: str,
    q_range: Optional[List[float]],
    chi_range: Optional[List[float]],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Resolve the cake axis ranges for an image.

    Precedence: explicit request fields → ranges stored on the uploaded file
    → hard-coded defaults (0,25)/(0,360). The stored/uploaded ranges are what
    make ROIs drawn in the UI line up with the right pixels; callers that pass
    nothing used to silently get the defaults and integrate the wrong region.
    """
    meta = _file_meta.get(file_id, {})
    if q_range and len(q_range) == 2:
        q = (float(q_range[0]), float(q_range[1]))
    elif isinstance(meta.get("qRange"), (list, tuple)) and len(meta["qRange"]) == 2:
        q = (float(meta["qRange"][0]), float(meta["qRange"][1]))
    else:
        q = (0.0, 25.0)
    if chi_range and len(chi_range) == 2:
        chi = (float(chi_range[0]), float(chi_range[1]))
    elif isinstance(meta.get("chiRange"), (list, tuple)) and len(meta["chiRange"]) == 2:
        chi = (float(meta["chiRange"][0]), float(meta["chiRange"][1]))
    else:
        chi = (0.0, 360.0)
    return q, chi


def _miller_psi_to_chi(
    psi: float,
    azimuth_offset: float,
    convention: str,
    normalize_to_signed: bool,
) -> float:
    """Mirror of the UI Miller-overlay azimuth transform.

    χ = ψ₀ ± ψ (CCW/CW), then optionally wrapped into [−180,180) so it shares
    the cake χ-axis convention. Must stay byte-for-byte consistent with
    millerOverlayPoints in ImageAnalysisPage.vue.
    """
    chi = (azimuth_offset + psi) if convention != "CW" else (azimuth_offset - psi)
    if normalize_to_signed:
        chi = ((chi % 360.0) + 360.0) % 360.0
        if chi >= 180.0:
            chi -= 360.0
    return chi


def _chi_to_psi(
    chi: float,
    azimuth_offset: float,
    convention: str,
    normalize_to_signed: bool,
) -> float:
    """Inverse of ``_miller_psi_to_chi``: map a cake χ back to Miller ψ.

    CCW (χ = ψ₀ + ψ)  →  ψ = χ − ψ₀
    CW  (χ = ψ₀ − ψ)  →  ψ = ψ₀ − χ
    then optionally wrapped into [−180,180). Used to fill the export ψ columns
    when no Miller point matched, so the CSV still reports Miller-space angles
    instead of raw cake χ (mirrors reference/function3 ``to_psi``).
    """
    psi = (chi - azimuth_offset) if convention != "CW" else (azimuth_offset - chi)
    if normalize_to_signed:
        psi = ((psi % 360.0) + 360.0) % 360.0
        if psi >= 180.0:
            psi -= 360.0
    return psi


def _angular_in_range(chi: float, lo: float, hi: float, tol: float) -> bool:
    """True if angle ``chi`` lies within the ``[lo, hi]`` window, mirroring
    reference/function3 ``calculate_match_for_area``.

    The window direction is preserved (NOT reordered via min/max) so a box that
    crosses the ±180° seam — ``lo > hi``, e.g. ``[175, -175]`` — matches the two
    end caps ``chi >= lo`` OR ``chi <= hi``, exactly like the reference's::

        if az_min <= az_max: in_az = (az_min <= paz <= az_max)
        else:                in_az = (paz >= az_min) or (paz <= az_max)

    ``tol`` adds symmetric edge slack (default 0 ⇒ strict, matching reference).
    """
    tol = abs(tol)
    if lo <= hi:
        return lo - tol <= chi <= hi + tol
    # Wrap-around box (lo > hi): match both caps across the ±180° seam.
    return chi >= lo - tol or chi <= hi + tol


def _pixel_to_physical(
    row: int,
    col: int,
    shape: tuple[int, int],
    q_range: tuple[float, float] = (0.0, 25.0),
    chi_range: tuple[float, float] = (0.0, 360.0),
) -> tuple[float, float]:
    """Convert pixel (row, col) to physical (chi, q) coordinates."""
    nrows, ncols = shape
    q = q_range[0] + col / max(ncols - 1, 1) * (q_range[1] - q_range[0])
    chi = chi_range[0] + row / max(nrows - 1, 1) * (chi_range[1] - chi_range[0])
    return chi, q


def _physical_to_pixel(
    chi: float,
    q: float,
    shape: tuple[int, int],
    q_range: tuple[float, float] = (0.0, 25.0),
    chi_range: tuple[float, float] = (0.0, 360.0),
) -> tuple[int, int]:
    """Convert physical (chi, q) to pixel (row, col)."""
    nrows, ncols = shape
    row = int(round((chi - chi_range[0]) / max(chi_range[1] - chi_range[0], 1e-9) * (nrows - 1)))
    col = int(round((q - q_range[0]) / max(q_range[1] - q_range[0], 1e-9) * (ncols - 1)))
    row = np.clip(row, 0, nrows - 1)
    col = np.clip(col, 0, ncols - 1)
    return row, col


def _roi_mask(
    shape: tuple[int, int],
    roi: ROI,
    q_range: tuple[float, float] = (0.0, 25.0),
    chi_range: tuple[float, float] = (0.0, 360.0),
) -> np.ndarray:
    """Boolean mask for an ROI in pixel space (physical coordinates)."""
    nrows, ncols = shape
    q_arr = np.linspace(q_range[0], q_range[1], ncols)
    chi_arr = np.linspace(chi_range[0], chi_range[1], nrows)
    q_grid, chi_grid = np.meshgrid(q_arr, chi_arr)
    # Azimuth window preserves direction so a box crossing the ±180° seam
    # (azimuthMin > azimuthMax) selects the two end caps, matching
    # reference/function3 ``calculate_all_intensities``.
    if roi.azimuthMin <= roi.azimuthMax:
        az_in = (chi_grid >= roi.azimuthMin) & (chi_grid <= roi.azimuthMax)
    else:
        az_in = (chi_grid >= roi.azimuthMin) | (chi_grid <= roi.azimuthMax)
    mask = (q_grid >= roi.qMin) & (q_grid <= roi.qMax) & az_in
    return mask


def _roi_mask_pixel(
    shape: tuple[int, int],
    roi: ROI,
) -> np.ndarray:
    """Boolean mask for an ROI in pixel space (pixel coordinates)."""
    nrows, ncols = shape
    mask = np.zeros(shape, dtype=bool)
    # Use pixel coords if present, otherwise fall back to physical coords mapped to pixel
    if roi.xMin is not None and roi.xMax is not None and roi.yMin is not None and roi.yMax is not None:
        x1 = int(np.clip(min(roi.xMin, roi.xMax), 0, ncols - 1))
        x2 = int(np.clip(max(roi.xMin, roi.xMax), 0, ncols - 1))
        y1 = int(np.clip(min(roi.yMin, roi.yMax), 0, nrows - 1))
        y2 = int(np.clip(max(roi.yMin, roi.yMax), 0, nrows - 1))
        mask[y1:y2 + 1, x1:x2 + 1] = True
    else:
        # Fallback: use physical coords
        mask = _roi_mask(shape, roi)
    return mask


# ---------------------------------------------------------------------------
# pyFAI detector geometry
# ---------------------------------------------------------------------------

def _pyfai_load(poni_file_id: str):
    """Load the pyFAI AzimuthalIntegrator for an uploaded PONI file id."""
    try:
        from pyFAI import load as pyfai_load
    except ImportError:
        raise HTTPException(500, "pyfai 坐标模式需要 pyFAI：pip install pyfai")
    return pyfai_load(_file_path(poni_file_id))


# Geometry arrays are expensive (full detector grid) but identical for every
# ROI on the same calibration, so they are cached per PONI file id. The cache
# key includes the target shape because a differently-sized image re-uses the
# same PONI only by re-generating arrays at that shape.
_pyfai_array_cache: Dict[tuple, tuple] = {}


def _pyfai_arrays(poni_file_id: str, shape: tuple[int, int]):
    """Return (q in Å⁻¹, χ in degrees) pixel maps for the PONI geometry.

    These are the same per-pixel coordinates pyFAI's radial (linear) and
    azimuthal integrators bin by, so an ROI window over them selects exactly
    the pixels those integrations would sweep through.
    """
    key = (poni_file_id, shape)
    cached = _pyfai_array_cache.get(key)
    if cached is not None:
        return cached
    ai = _pyfai_load(poni_file_id)
    q_arr = np.asarray(ai.array_from_unit(shape=shape, unit="q_A^-1"), dtype=np.float64)
    chi_arr = np.asarray(ai.array_from_unit(shape=shape, unit="chi_deg"), dtype=np.float64)
    if len(_pyfai_array_cache) > 4:
        _pyfai_array_cache.clear()
    _pyfai_array_cache[key] = (q_arr, chi_arr)
    return q_arr, chi_arr


def _pyfai_window_mask(
    q_arr: np.ndarray,
    chi_arr: np.ndarray,
    q_lo: float,
    q_hi: float,
    az_lo: float,
    az_hi: float,
) -> np.ndarray:
    """Boolean mask of pixels whose (q, χ) fall in the ROI window.

    The χ window preserves direction so a box crossing the ±180° seam
    (az_lo > az_hi) selects the two end caps, matching _roi_mask.
    """
    q_in = (q_arr >= q_lo) & (q_arr <= q_hi)
    if az_lo <= az_hi:
        az_in = (chi_arr >= az_lo) & (chi_arr <= az_hi)
    else:
        az_in = (chi_arr >= az_lo) | (chi_arr <= az_hi)
    return q_in & az_in & np.isfinite(q_arr) & np.isfinite(chi_arr)


def _pyfai_wedge_polygon(
    q_arr: np.ndarray,
    chi_arr: np.ndarray,
    q_lo: float,
    q_hi: float,
    az_lo: float,
    az_hi: float,
) -> list[list[float]]:
    """Outline of a q/χ window's pixel footprint as [x, y] pairs (cosmetic
    overlay); empty when scikit-image is unavailable."""
    mask = _pyfai_window_mask(q_arr, chi_arr, q_lo, q_hi, az_lo, az_hi)
    try:
        from skimage.measure import find_contours
        contours = find_contours(mask.astype(float), 0.5)
        if contours:
            contour = max(contours, key=len)
            step = max(1, len(contour) // 160)
            return [[float(pt[1]), float(pt[0])] for pt in contour[::step]]
    except ImportError:
        pass
    return []


# ---------------------------------------------------------------------------
# Detector peak picking & pyFAI radial/azimuthal integration
#
# Ported from the R1.7all PeakExtraction raw-image workflow (backend/api/
# peak_raw.py): click an anchor point on the raw detector image, then run a
# narrow-sector radial (q-I) integration and an azimuthal (ψ-I) integration
# around it with user-tunable ± half-widths. Windows crossing the ±180° seam
# are split into two pyFAI segments and stitched back together.
# ---------------------------------------------------------------------------

def _normalize_angle_180(a: float) -> float:
    a = (a % 360.0 + 360.0) % 360.0
    return a - 360.0 if a >= 180.0 else a


def _split_azimuth_window(center_deg: float, half_width_deg: float) -> list[dict[str, float]]:
    """Split an azimuth window centred on center_deg into ±180-safe segments."""
    center = _normalize_angle_180(center_deg)
    start = center - half_width_deg
    end = center + half_width_deg
    if start >= -180.0 and end <= 180.0:
        return [{"start": start, "end": end, "width": end - start}]
    if start < -180.0:
        return [
            {"start": start + 360.0, "end": 180.0, "width": 180.0 - (start + 360.0)},
            {"start": -180.0, "end": end, "width": end + 180.0},
        ]
    return [
        {"start": start, "end": 180.0, "width": 180.0 - start},
        {"start": -180.0, "end": end - 360.0, "width": end - 180.0},
    ]


def _mask_empty_bins(intensity, count) -> np.ndarray:
    """NaN-out bins no pixel contributed to (pyFAI fills them with ai.empty=0,
    indistinguishable from a true zero and responsible for huge jumps in the
    curve across masked areas). True zeros (count>0) stay 0."""
    out = np.array(intensity, dtype=float).copy()
    if count is None:
        return out
    count_arr = np.asarray(count)
    if count_arr.shape == out.shape:
        out[count_arr == 0] = np.nan
    return out


def _weighted_merge_curves(curves: list[tuple[np.ndarray, float]]) -> list[float]:
    """Width-weighted mean of segment curves (nan-aware)."""
    if not curves:
        return []
    weighted_sum = np.zeros_like(curves[0][0], dtype=float)
    weight_sum = np.zeros_like(curves[0][0], dtype=float)
    for curve, width in curves:
        valid = np.isfinite(curve)
        weighted_sum[valid] += curve[valid] * width
        weight_sum[valid] += width
    merged = np.divide(
        weighted_sum, weight_sum,
        out=np.full_like(weight_sum, np.nan, dtype=float),
        where=weight_sum > 0,
    )
    return merged.tolist()


def _allocate_bins(total_bins: int, segments: list[dict[str, float]]) -> list[int]:
    """Split a total bin budget across seam segments proportionally."""
    if len(segments) == 1:
        return [max(2, total_bins)]
    total_width = sum(seg["width"] for seg in segments)
    raw = [(seg["width"] / total_width) * total_bins for seg in segments]
    bins = [max(2, int(math.floor(value))) for value in raw]
    while sum(bins) < total_bins:
        idx = max(range(len(raw)), key=lambda i: raw[i] - bins[i])
        bins[idx] += 1
    while sum(bins) > total_bins:
        idx = max(range(len(bins)), key=lambda i: bins[i])
        if bins[idx] <= 2:
            break
        bins[idx] -= 1
    return bins


def _collapse_psi_intensity(intensity: np.ndarray) -> np.ndarray:
    return np.nanmean(intensity, axis=0) if intensity.ndim == 2 else intensity.astype(float)


def _stitch_psi_segments(segments: list[tuple[np.ndarray, np.ndarray]], center_deg: float) -> tuple[list[float], list[float]]:
    """Concatenate seam segments into one axis continuous around the centre."""
    if not segments:
        return [], []
    stitched: list[tuple[float, float]] = []
    for axis, intensity in segments:
        for az, value in zip(axis.tolist(), intensity.tolist()):
            local_az = center_deg + _normalize_angle_180(az - center_deg)
            stitched.append((local_az, value))
    stitched.sort(key=lambda item: item[0])
    return [item[0] for item in stitched], [item[1] for item in stitched]


def _clean_series(values) -> list[Optional[float]]:
    cleaned: list[Optional[float]] = []
    for value in values:
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            cleaned.append(None)
        else:
            cleaned.append(float(value))
    return cleaned


def _estimate_background(
    arr: np.ndarray,
    mask: np.ndarray,
    bg_config: Optional[BackgroundConfig],
    legacy_bg_mode: int,
    roi: ROI,
    q_range: tuple[float, float] = (0.0, 25.0),
    chi_range: tuple[float, float] = (0.0, 360.0),
) -> float:
    """
    Estimate a scalar background value for a masked ROI.

    Returns 0.0 if no background subtraction.
    """
    if bg_config is not None:
        mode = bg_config.mode
    else:
        # Map legacy integer to mode string
        mode_map = {0: "none", 1: "annular", 2: "radial", 3: "median2d"}
        mode = mode_map.get(legacy_bg_mode, "none")

    # ---- Mode: none ----
    if mode == "none":
        return 0.0

    # ---- Mode: fixed ----
    if mode == "fixed":
        return float(bg_config.fixedValue if bg_config else 0.0)

    # ---- Mode: neighbor (x-axis neighbour pixel columns) ----
    if mode == "neighbor":
        # Single-side selection (reference PyQt 单侧选取): "left" / "right" sample
        # one side only; "both" averages the two sides (legacy behaviour).
        side = (bg_config.side if bg_config and bg_config.side else "both").lower()
        if side not in ("left", "right", "both"):
            side = "both"
        # Unified band width (default 10). Legacy per-side counts are only used
        # when the caller omits `width` entirely.
        if bg_config is not None and bg_config.width is not None:
            left_px = right_px = int(bg_config.width)
        else:
            left_px = bg_config.leftPixels if bg_config else 5
            right_px = bg_config.rightPixels if bg_config else 5
        nrows, ncols = arr.shape

        # Find the column range of the ROI
        cols_with_roi = np.any(mask, axis=0)
        if not np.any(cols_with_roi):
            return 0.0
        roi_cols = np.where(cols_with_roi)[0]
        first_col = roi_cols[0]
        last_col = roi_cols[-1]

        # Find row range of ROI
        rows_with_roi = np.any(mask, axis=1)
        row_min = 0
        row_max = nrows - 1
        if np.any(rows_with_roi):
            row_indices = np.where(rows_with_roi)[0]
            row_min = max(0, row_indices[0])
            row_max = min(nrows - 1, row_indices[-1])

        bg_vals = []
        # Left band: the `left_px` columns immediately left of the ROI bbox.
        if side in ("left", "both"):
            left_start = max(0, first_col - left_px)
            left_end = first_col
            if left_start < left_end:
                bg_vals.append(_safe_mean(arr[row_min:row_max + 1, left_start:left_end]))

        # Right band: the `right_px` columns immediately right of the ROI bbox.
        if side in ("right", "both"):
            right_start = last_col + 1
            right_end = min(ncols, last_col + 1 + right_px)
            if right_start < right_end:
                bg_vals.append(_safe_mean(arr[row_min:row_max + 1, right_start:right_end]))

        finite = [v for v in bg_vals if np.isfinite(v)]
        return float(np.mean(finite)) if finite else 0.0

    # ---- Mode: annular ----
    if mode == "annular":
        # Legacy behaviour: expanded ROI minus original ROI
        nrows, ncols = arr.shape
        q_arr = np.linspace(q_range[0], q_range[1], ncols)
        chi_arr = np.linspace(chi_range[0], chi_range[1], nrows)
        q_grid, chi_grid = np.meshgrid(q_arr, chi_arr)

        q_span = roi.qMax - roi.qMin
        az_span = roi.azimuthMax - roi.azimuthMin
        exp_q_min = roi.qMin - 0.2 * max(q_span, 0.01)
        exp_q_max = roi.qMax + 0.2 * max(q_span, 0.01)
        exp_az_min = roi.azimuthMin - 0.2 * max(az_span, 1.0)
        exp_az_max = roi.azimuthMax + 0.2 * max(az_span, 1.0)

        exp_mask = (
            (q_grid >= exp_q_min) & (q_grid <= exp_q_max)
            & (chi_grid >= exp_az_min) & (chi_grid <= exp_az_max)
        )
        annular_mask = exp_mask & ~mask
        if annular_mask.sum() > 0:
            return _safe_mean(arr[annular_mask])
        return 0.0

    # ---- Mode: radial ----
    if mode == "radial":
        offset = 0.5 * (roi.qMax - roi.qMin)
        bg_vals = []
        for shift in [-offset, offset]:
            shifted_roi = ROI(
                qMin=roi.qMin + shift, qMax=roi.qMax + shift,
                azimuthMin=roi.azimuthMin, azimuthMax=roi.azimuthMax,
            )
            sm = _roi_mask(arr.shape, shifted_roi, q_range, chi_range)
            if sm.sum() > 0:
                bg_vals.append(_safe_mean(arr[sm]))
        if bg_vals:
            return float(np.mean([v for v in bg_vals if np.isfinite(v)])) if any(np.isfinite(v) for v in bg_vals) else 0.0
        return 0.0

    # ---- Mode: median2d ----
    if mode == "median2d":
        from scipy.ndimage import median_filter
        finite = np.where(np.isfinite(arr), arr, 0.0)
        bg_arr = median_filter(finite, size=15)
        return _safe_median(bg_arr[mask])

    return 0.0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadImageResponse)
def upload_image(files: List[UploadFile] = File(...)):
    """Upload a 2-D image (TIFF/NPY/EDF) plus an optional processing_info
    sidecar (.json/.txt) from the same multipart batch."""
    try:
        image_file = None
        info_file = None
        for f in files:
            name = (f.filename or "").lower()
            if info_file is None and (name.endswith(".json") or name.endswith(".txt")):
                info_file = f
            elif image_file is None:
                image_file = f
        if image_file is None:
            image_file = files[0]

        raw = image_file.file.read()
        ext = os.path.splitext(image_file.filename or "")[1]
        fid = _save_upload(raw, suffix=ext)

        arr = _load_image(fid)

        info_text: Optional[str] = None
        if info_file is not None:
            info_text = info_file.file.read().decode("utf-8", errors="replace")

        q_range = [0.0, 25.0]
        chi_range = [0.0, 360.0]
        unit: Optional[str] = None
        if info_text:
            parsed = _parse_processing_info(info_text)
            unit = parsed.get("x_axis_unit")
            if "q_min" in parsed and "q_max" in parsed:
                # Present q in Å^-1 regardless of the source unit (nm^-1 -> /10).
                q_range = list(_q_range_to_angstrom((parsed["q_min"], parsed["q_max"]), unit))
            if "chi_min" in parsed and "chi_max" in parsed:
                chi_range = [parsed["chi_min"], parsed["chi_max"]]

        # Persist ranges so later /intensity calls can map ROIs onto the right
        # pixels even when the caller omits qRange/chiRange.
        _file_meta[fid] = {"shape": arr.shape, "dtype": str(arr.dtype), "qRange": q_range, "chiRange": chi_range}

        preview = _downsample(arr).tolist()

        return UploadImageResponse(
            fileId=fid,
            shape=list(arr.shape),
            dtype=str(arr.dtype),
            preview=preview,
            qRange=q_range,
            chiRange=chi_range,
            processingInfo=info_text,
        )
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/parse-info", response_model=ParseInfoResponse)
def parse_info(file: UploadFile = File(...)):
    """Parse a standalone processing_info sidecar (JSON or legacy text) and
    return the q (Å^-1) / chi (°) axis ranges, so the UI can rescale an
    already-loaded image's axes without re-uploading it."""
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


def _is_numeric_token(tok: str) -> bool:
    """True when a whitespace token parses as a number (int or float)."""
    try:
        float(tok)
        return True
    except (TypeError, ValueError):
        return False


def _detect_miller_columns(header_parts: List[str]) -> Dict[str, int]:
    """Map a Miller-file header row to column indices.

    Mirrors the parser in reference/function3/2dinter_area_obtaine.py: the q
    column is recognised by a name containing ``q(``/``q``, the psi/azimuth
    column by ``psi(``/``azimuth``/``chi``, and h/k/l by their single letters.
    Returns a dict that may carry keys h, k, l, q, psi.
    """
    cols: Dict[str, int] = {}
    for i, raw in enumerate(header_parts):
        name = raw.lower().strip()
        if "q(" in name or name == "q":
            cols["q"] = i
        elif "psi(" in name or "azimuth" in name or "chi" in name:
            cols["psi"] = i
        elif name == "h":
            cols["h"] = i
        elif name == "k":
            cols["k"] = i
        elif name == "l":
            cols["l"] = i
    return cols


def _parse_miller_text(text: str) -> List[MillerPoint]:
    """Parse a whitespace-separated Miller file (FullMiller / outputMiller).

    Format (per reference/function3/2dinter_area_obtaine.py)::

        h k l q(A-1) psi(degree)            # header (optional)
        1 0 0 1.2345 0.0
        1 1 0 1.5678 45.0

    FullMiller adds trailing columns (psi-root, 2theta) which are ignored.
    Column order is auto-detected from the header when one is present;
    otherwise the canonical positional order h, k, l, q, psi is assumed.
    Header / comment lines (whose first token is not numeric) are skipped.
    """
    h_idx, k_idx, l_idx, q_idx, psi_idx = 0, 1, 2, 3, 4
    header_seen = False
    points: List[MillerPoint] = []

    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        # Header / comment line: first token not a number.
        if not _is_numeric_token(parts[0]):
            if not header_seen:
                cols = _detect_miller_columns(parts)
                if cols:
                    h_idx = cols.get("h", h_idx)
                    k_idx = cols.get("k", k_idx)
                    l_idx = cols.get("l", l_idx)
                    q_idx = cols.get("q", q_idx)
                    psi_idx = cols.get("psi", psi_idx)
                header_seen = True
            continue

        max_idx = max(h_idx, k_idx, l_idx, q_idx, psi_idx)
        if len(parts) <= max_idx:
            continue
        try:
            h = int(float(parts[h_idx]))
            k = int(float(parts[k_idx]))
            l = int(float(parts[l_idx]))
            q = float(parts[q_idx])
            psi = float(parts[psi_idx])
        except (ValueError, IndexError):
            continue
        # NaN compares unequal to itself; drop non-positive q.
        if q != q or psi != psi or q <= 0:
            continue
        points.append(MillerPoint(h=h, k=k, l=l, q=q, psi=psi))
    return points


def _parse_miller_json(obj: Any) -> List[MillerPoint]:
    """Parse a JSON Miller payload.

    Accepted shapes::

        [ {"h":1,"k":0,"l":0,"q":1.2,"psi":0}, ... ]   # array of objects
        {"points": [ ... ]}                             # wrapped
        [ [1,0,0,1.2,0], ... ]                          # positional arrays
    """
    if isinstance(obj, dict):
        seq = obj.get("points", obj.get("data", obj.get("miller", [])))
    elif isinstance(obj, list):
        seq = obj
    else:
        return []
    points: List[MillerPoint] = []
    for item in seq:
        try:
            if isinstance(item, (list, tuple)):
                h = int(float(item[0])); k = int(float(item[1])); l = int(float(item[2]))
                q = float(item[3]); psi = float(item[4])
            elif isinstance(item, dict):
                h = int(float(item.get("h", item.get("H", 0))))
                k = int(float(item.get("k", item.get("K", 0))))
                l = int(float(item.get("l", item.get("L", 0))))
                q = float(item.get("q", item.get("Q", 0)))
                psi = float(item.get("psi", item.get("Psi",
                         item.get("azimuth", item.get("chi", 0)))))
            else:
                continue
        except (ValueError, IndexError, TypeError):
            continue
        if q != q or psi != psi or q <= 0:
            continue
        points.append(MillerPoint(h=h, k=k, l=l, q=q, psi=psi))
    return points


@router.post("/upload-miller", response_model=UploadMillerResponse)
def upload_miller(files: List[UploadFile] = File(...)):
    """
    Upload one or more Miller-index files.

    Two formats are accepted:
      - JSON (.json): ``[{"h":1,"k":0,"l":0,"q":1.23,"psi":0}, ...]`` or
        ``{"points": [...]}``.
      - Text (.txt): whitespace-separated ``h k l q psi`` with an optional
        header row (e.g. ``h k l q(A-1) psi(degree)``); trailing FullMiller
        columns (psi-root, 2theta) are ignored. Format follows
        reference/function3/2dinter_area_obtaine.py.
    """
    try:
        datasets: list[MillerDataset] = []
        for f in files:
            raw = f.file.read()
            ext = os.path.splitext(f.filename or "")[1] or ".txt"
            fid = _save_upload(raw, suffix=ext)

            text = raw.decode("utf-8", errors="replace")
            stripped = text.lstrip()
            if stripped[:1] in ("{", "["):
                try:
                    points = _parse_miller_json(json.loads(text))
                except (json.JSONDecodeError, ValueError):
                    points = []
            else:
                points = _parse_miller_text(text)

            name = os.path.splitext(f.filename or "unknown")[0]
            datasets.append(MillerDataset(name=name, points=points, fileId=fid))

        return UploadMillerResponse(datasets=datasets)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/poni-upload", response_model=PoniInfoResponse)
def upload_poni(file: UploadFile = File(...)):
    """Upload and parse a pyFAI PONI calibration file.

    The geometry is returned for display (wavelength in Å, distance in mm,
    beam-centre pixel) and the stored file id backs the detector tab's
    physical-coordinate ROI mode: pixel boxes are translated into q/χ windows
    and intensity is integrated over the calibrated pixels.
    """
    try:
        raw = file.file.read()
        ext = os.path.splitext(file.filename or "")[1] or ".poni"
        fid = _save_upload(raw, suffix=ext)
        ai = _pyfai_load(fid)

        detector = ai.detector
        pixel1 = float(detector.get_pixel1()) if detector is not None else 0.0
        pixel2 = float(detector.get_pixel2()) if detector is not None else 0.0
        max_shape = None
        if detector is not None and getattr(detector, "max_shape", None) is not None:
            max_shape = list(detector.max_shape)

        _file_meta[fid] = {"kind": "poni", "shape": max_shape}

        return PoniInfoResponse(
            fileId=fid,
            wavelength=float(ai.wavelength) * 1e10,   # m -> Å
            dist=float(ai.dist) * 1e3,                 # m -> mm
            poni1=float(ai.poni1),
            poni2=float(ai.poni2),
            rot1=float(getattr(ai, "rot1", 0.0) or 0.0),
            rot2=float(getattr(ai, "rot2", 0.0) or 0.0),
            rot3=float(getattr(ai, "rot3", 0.0) or 0.0),
            detector=(detector.name if detector is not None else "Unknown"),
            pixel1=pixel1 * 1e6,                       # m -> μm
            pixel2=pixel2 * 1e6,
            shape=max_shape,
            centerX=(float(ai.poni2) / pixel2) if pixel2 > 0 else 0.0,
            centerY=(float(ai.poni1) / pixel1) if pixel1 > 0 else 0.0,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=f"PONI 解析失败: {exc}")


@router.post("/detector-roi-window", response_model=DetectorRoiWindowResponse)
def detector_roi_window(req: DetectorRoiWindowRequest):
    """Translate a pixel box into the q (Å⁻¹) / χ (°) window it covers.

    The window is the min/max of the pyFAI geometry arrays over the box, so a
    drag on the raw detector image yields the physical-space ROI the pyFAI
    radial/azimuthal integrations would integrate over.
    """
    try:
        shape = tuple(req.shape) if req.shape else None
        if shape is None:
            meta = _file_meta.get(req.poniFileId, {})
            shape = meta.get("shape")
        if not shape or len(shape) < 2:
            raise HTTPException(400, "无法确定探测器尺寸：请提供 shape 或先解析 PONI")
        nrows, ncols = int(shape[0]), int(shape[1])
        x1 = int(np.clip(min(req.xMin, req.xMax), 0, ncols - 1))
        x2 = int(np.clip(max(req.xMin, req.xMax), 0, ncols - 1))
        y1 = int(np.clip(min(req.yMin, req.yMax), 0, nrows - 1))
        y2 = int(np.clip(max(req.yMin, req.yMax), 0, nrows - 1))

        q_arr, chi_arr = _pyfai_arrays(req.poniFileId, (nrows, ncols))
        q_box = q_arr[y1:y2 + 1, x1:x2 + 1]
        chi_box = chi_arr[y1:y2 + 1, x1:x2 + 1]
        q_fin = q_box[np.isfinite(q_box)]
        chi_fin = chi_box[np.isfinite(chi_box)]
        if q_fin.size == 0 or chi_fin.size == 0:
            raise HTTPException(400, "选定区域内没有有效标定像素")

        return DetectorRoiWindowResponse(
            qMin=float(q_fin.min()),
            qMax=float(q_fin.max()),
            azimuthMin=float(chi_fin.min()),
            azimuthMax=float(chi_fin.max()),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


def _pyfai_pixel_from_qchi(
    poni_file_id: str,
    shape: tuple[int, int],
    q_t: float,
    chi_t: float,
) -> tuple[int, int]:
    """Map a (q, χ) target back to the nearest detector pixel.

    An analytic rot1=rot2=rot3=0 inversion gives the initial guess (the same
    formula the R1.7all reference uses), then a local search against the true
    geometry arrays snaps it onto the exact pixel — robust even when the PONI
    carries small rotations.
    """
    ai = _pyfai_load(poni_file_id)
    wl = float(ai.wavelength)
    dist = float(ai.dist)
    pixel1 = float(ai.detector.get_pixel1())
    pixel2 = float(ai.detector.get_pixel2())
    q_si = float(q_t) * 1e10  # Å⁻¹ → m⁻¹
    sin_th = (q_si * wl) / (4.0 * math.pi)
    if abs(sin_th) >= 1.0:
        raise ValueError("q 值超出几何可达范围")
    theta = math.asin(sin_th)
    r = dist * math.tan(2.0 * theta)
    chi_r = math.radians(float(chi_t))
    gx = float(ai.poni2) / pixel2 + (r * math.cos(chi_r)) / pixel2
    gy = float(ai.poni1) / pixel1 + (r * math.sin(chi_r)) / pixel1

    nrows, ncols = shape
    q_arr, chi_arr = _pyfai_arrays(poni_file_id, shape)
    # Self-calibrated per-pixel scales: nearest in pixel units, not raw (q, χ).
    dq_per_px = (2.0 * math.pi * pixel2 / (wl * dist)) / 1e10 if (wl and dist) else 0.01
    r_px = max(r / pixel2 if pixel2 else 1.0, 1.0)
    dchi_per_px = max(math.degrees(1.0 / r_px), 1e-3)

    win = 80
    x1 = int(max(0, min(ncols - 1, round(gx) - win)))
    x2 = int(max(0, min(ncols, round(gx) + win + 1)))
    y1 = int(max(0, min(nrows - 1, round(gy) - win)))
    y2 = int(max(0, min(nrows, round(gy) + win + 1)))
    qs = q_arr[y1:y2, x1:x2]
    chis = chi_arr[y1:y2, x1:x2]
    dchi = np.degrees(np.arctan2(
        np.sin(np.radians(chis - chi_t)),
        np.cos(np.radians(chis - chi_t)),
    ))
    metric = ((qs - q_t) / dq_per_px) ** 2 + (dchi / dchi_per_px) ** 2
    metric = np.where(np.isfinite(metric), metric, np.inf)
    ly, lx = np.unravel_index(int(np.argmin(metric)), metric.shape)
    return int(x1 + lx), int(y1 + ly)


@router.post("/detector-click", response_model=DetectorClickResponse)
def detector_click(req: DetectorClickRequest):
    """Resolve a click to a pixel + its (q, χ). With snap=True the brightest
    valid pixel inside the window wins; otherwise the exact clicked pixel."""
    try:
        arr = _load_image(req.fileId)
        nrows, ncols = arr.shape
        q_arr, chi_arr = _pyfai_arrays(req.poniFileId, arr.shape)
        cx = int(np.clip(round(req.x), 0, ncols - 1))
        cy = int(np.clip(round(req.y), 0, nrows - 1))
        if req.snap:
            half = max(1, int(req.window) // 2)
            x1, x2 = max(0, cx - half), min(ncols, cx + half + 1)
            y1, y2 = max(0, cy - half), min(nrows, cy + half + 1)
            win = arr[y1:y2, x1:x2]
            valid = np.isfinite(win)
            if req.minIntensity is not None:
                valid &= win >= req.minIntensity
            if req.maxIntensity is not None:
                valid &= win <= req.maxIntensity
            if not valid.any():
                raise HTTPException(400, "选定窗口内没有有效像素")
            ly, lx = np.unravel_index(int(np.argmax(np.where(valid, win, -np.inf))), win.shape)
            gx, gy = int(x1 + lx), int(y1 + ly)
        else:
            gx, gy = cx, cy
        return DetectorClickResponse(
            x=gx, y=gy,
            intensity=float(arr[gy, gx]),
            q=float(q_arr[gy, gx]),
            psiDeg=float(chi_arr[gy, gx]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/detector-integrate", response_model=DetectorIntegrateResponse)
def detector_integrate(req: DetectorIntegrateRequest):
    """Radial (q-I) + azimuthal (ψ-I) pyFAI integration around an anchor.

    Mirrors the R1.7all PeakExtraction /integrate endpoint: ± half-width
    windows around the anchor's (q₀, ψ₀), seam-crossing azimuth windows split
    into segments, empty bins optionally NaN-masked, and the extraction wedge
    returned as a pixel-space polygon for overlay.
    """
    try:
        arr = _load_image(req.fileId)
        nrows, ncols = arr.shape
        q_arr, chi_arr = _pyfai_arrays(req.poniFileId, arr.shape)
        cx = int(np.clip(round(req.x), 0, ncols - 1))
        cy = int(np.clip(round(req.y), 0, nrows - 1))
        q0 = float(q_arr[cy, cx])
        psi0 = float(chi_arr[cy, cx])
        if not (np.isfinite(q0) and np.isfinite(psi0)):
            raise HTTPException(400, "选点落在标定有效范围之外")

        ai = _pyfai_load(req.poniFileId)
        mask = (~np.isfinite(arr)).astype(np.int8)
        if req.minIntensity is not None:
            mask |= (arr < req.minIntensity).astype(np.int8)
        if req.maxIntensity is not None:
            mask |= (arr > req.maxIntensity).astype(np.int8)

        # ---- q-I: radial profile inside a narrow azimuth sector ------------
        q_min = max(0.001, q0 - req.radialHalf)
        q_max = q0 + req.radialHalf
        q_axis: Optional[np.ndarray] = None
        q_results: list[tuple[np.ndarray, float]] = []
        for seg in _split_azimuth_window(psi0, req.azimuthHalf):
            try:
                res_q = ai.integrate1d_ng(
                    arr, int(req.npt),
                    unit="q_A^-1",
                    method="splitpixel",
                    correctSolidAngle=False,
                    azimuth_range=(seg["start"], seg["end"]),
                    radial_range=(q_min, q_max),
                    mask=mask,
                )
            except Exception:
                continue
            if q_axis is None:
                q_axis = np.array(res_q.radial, dtype=float)
            seg_i = _mask_empty_bins(res_q.intensity, getattr(res_q, "count", None)) \
                if req.excludeEmptyBins else np.array(res_q.intensity, dtype=float)
            q_results.append((seg_i, seg["width"]))
        if q_axis is None:
            raise HTTPException(400, "q-I 积分失败：请检查半宽参数")

        # ---- ψ-I: azimuthal profile inside a narrow radial ring ------------
        q_min_r = max(0.001, q0 - req.radialHalfR)
        q_max_r = q0 + req.radialHalfR
        psi_segments_in = _split_azimuth_window(psi0, req.azimuthHalfR)
        psi_bins = _allocate_bins(int(req.nptR), psi_segments_in)
        psi_results: list[tuple[np.ndarray, np.ndarray]] = []
        for seg, npt_bins in zip(psi_segments_in, psi_bins):
            try:
                res_psi = ai.integrate_radial(
                    arr,
                    npt_rad=int(req.nptRadR),
                    npt=int(npt_bins),
                    radial_range=(q_min_r, q_max_r),
                    azimuth_range=(seg["start"], seg["end"]),
                    unit="chi_deg",
                    radial_unit="q_A^-1",
                    method="splitpixel",
                    correctSolidAngle=False,
                    mask=mask,
                )
            except Exception:
                continue
            seg_axis = np.array(res_psi.radial, dtype=float)
            seg_i = _mask_empty_bins(res_psi.intensity, getattr(res_psi, "count", None)) \
                if req.excludeEmptyBins else np.array(res_psi.intensity, dtype=float)
            psi_results.append((seg_axis, _collapse_psi_intensity(seg_i)))
        if not psi_results:
            raise HTTPException(400, "ψ-I 积分失败：请检查半宽参数")
        psi_axis, i_psi = _stitch_psi_segments(psi_results, psi0)

        # ---- extraction wedge (union of both windows) as a pixel polygon ---
        wq_lo, wq_hi = q_min, q0 + req.radialHalf
        az_segs = _split_azimuth_window(psi0, req.azimuthHalfR)
        wedge_az_lo = min(seg["start"] for seg in az_segs)
        wedge_az_hi = max(seg["end"] for seg in az_segs)
        wedge_polygon = _pyfai_wedge_polygon(q_arr, chi_arr, wq_lo, wq_hi, wedge_az_lo, wedge_az_hi)

        return DetectorIntegrateResponse(
            qValues=_clean_series(q_axis.tolist()),
            iQ=_clean_series(_weighted_merge_curves(q_results)),
            psiValues=_clean_series(psi_axis),
            iPsi=_clean_series(i_psi),
            currentQ=q0,
            currentPsi=psi0,
            wedgePolygon=wedge_polygon,
            wedgeQMin=wq_lo, wedgeQMax=wq_hi,
            wedgeAzMin=wedge_az_lo, wedgeAzMax=wedge_az_hi,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/detector-calc-pixel", response_model=DetectorCalcPixelResponse)
def detector_calc_pixel(req: DetectorCalcPixelRequest):
    """Refine the anchor from (q, ψ) values picked on the integration curves."""
    try:
        q_t = float(req.selectedQ) if req.selectedQ is not None else float(req.currentQ)
        psi_t = _normalize_angle_180(
            float(req.selectedPsi) if req.selectedPsi is not None else float(req.currentPsi)
        )
        arr = _load_image(req.fileId)
        nrows, ncols = arr.shape
        nx, ny = _pyfai_pixel_from_qchi(req.poniFileId, arr.shape, q_t, psi_t)
        if not (0 <= ny < nrows and 0 <= nx < ncols):
            raise HTTPException(400, f"反算像素 ({nx}, {ny}) 超出图像范围")
        q_arr, chi_arr = _pyfai_arrays(req.poniFileId, arr.shape)
        return DetectorCalcPixelResponse(
            x=int(nx), y=int(ny),
            intensity=float(arr[ny, nx]),
            q=float(q_arr[ny, nx]),
            psiDeg=float(chi_arr[ny, nx]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, detail=str(exc))


@router.post("/detector-wedge", response_model=DetectorWedgeResponse)
def detector_wedge(req: DetectorWedgeRequest):
    """Outline of a user-selected q/χ region in pixel coordinates."""
    try:
        shape = (int(req.shape[0]), int(req.shape[1]))
        q_arr, chi_arr = _pyfai_arrays(req.poniFileId, shape)
        poly = _pyfai_wedge_polygon(
            q_arr, chi_arr,
            min(req.qMin, req.qMax), max(req.qMin, req.qMax),
            req.azimuthMin, req.azimuthMax,
        )
        return DetectorWedgeResponse(polygon=poly)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.get("/image/{fileId}")
def get_image(fileId: str, max_dim: int = Query(512, ge=64)):
    """Get image data for display, downsampled if large."""
    try:
        arr = _load_image(fileId)
        ds = _downsample(arr, max_dim)
        lo, hi = _finite_min_max(arr)
        return {
            "fileId": fileId,
            "shape": list(arr.shape),
            "displayShape": list(ds.shape),
            "data": ds.tolist(),
            "min": lo if lo is not None else 0.0,
            "max": hi if hi is not None else 0.0,
        }
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/intensity", response_model=IntensityResponse)
def calculate_intensity(req: IntensityRequest):
    """
    Calculate integrated intensity for each ROI.

    Supported coordinate types:
      - 'physical' (default): q/azimuth ranges on cake images
      - 'pixel': pixel x/y ranges on detector images
      - 'pyfai': q/azimuth windows resolved against a PONI calibration
        (requires poniFileId). The ROI window selects the detector pixels
        whose pyFAI q (Å⁻¹) / χ (°) coordinates fall inside it — exactly the
        pixels the pyFAI radial (linear) and azimuthal integrators sweep for
        that window — and the raw pixel intensities are summed. Regions may
        carry qMin/qMax/azimuthMin/azimuthMax directly or a pixel box whose
        q/χ extent is resolved server-side.

    Background modes (via background.mode or legacy backgroundMode):
      none      – no subtraction
      fixed     – subtract a constant per-pixel value
      neighbor  – subtract the mean of adjacent pixel columns on a selectable
                  side (left / right / both) over a unified band width
      annular   – mean of surrounding expanded ring (legacy 1)
      radial    – mean along q at same chi, shifted (legacy 2)
      median2d  – median-filtered local background (legacy 3)

    Each region may carry its own `background` config (per-peak subtraction);
    when present it overrides the request-wide `background` for that ROI only.
    """
    try:
        arr = _load_image(req.fileId)

        # Validity (mask) map: non-finite pixels and pixels outside the
        # optional [minIntensity, maxIntensity] window are excluded from every
        # ROI below. This is the mask that was missing vs reference/function3:
        # sentinel / saturated pixels (commonly stored as the array maximum by
        # upstream integrators) otherwise enter the sum and dominate it.
        valid = np.isfinite(arr)
        if req.minIntensity is not None:
            valid &= arr >= req.minIntensity
        if req.maxIntensity is not None:
            valid &= arr <= req.maxIntensity

        results: list[ROIIntensity] = []

        use_pixel_coords = (req.coordinateType == "pixel")
        use_pyfai_coords = (req.coordinateType == "pyfai")
        pyfai_arrays = None
        if use_pyfai_coords:
            if not req.poniFileId:
                raise HTTPException(400, "coordinateType='pyfai' 需要 poniFileId")
            pyfai_arrays = _pyfai_arrays(req.poniFileId, arr.shape)
        # Resolve the cake axis ranges (request → stored meta → defaults). These
        # map physical ROI coords onto pixels; using the hard-coded defaults
        # here integrated the wrong pixels whenever χ spanned e.g. [−180,180].
        q_range, chi_range = _resolve_ranges(req.fileId, req.qRange, req.chiRange)

        for roi in req.regions:
            # Build mask
            if use_pyfai_coords:
                q_arr, chi_arr = pyfai_arrays
                # ROI's q/χ fields default to 0.0 (not None), so presence is
                # detected by a non-degenerate q window; a bare pixel box
                # (all four zero) gets its window resolved from the geometry.
                has_q_window = (roi.qMax is not None and roi.qMin is not None
                                and roi.qMax > roi.qMin)
                if has_q_window:
                    q_lo, q_hi = min(roi.qMin, roi.qMax), max(roi.qMin, roi.qMax)
                    az_lo, az_hi = roi.azimuthMin, roi.azimuthMax
                elif (roi.xMin is not None and roi.xMax is not None
                      and roi.yMin is not None and roi.yMax is not None):
                    # Pixel box: resolve its q/χ extent from the geometry arrays.
                    nrows, ncols = arr.shape
                    x1 = int(np.clip(min(roi.xMin, roi.xMax), 0, ncols - 1))
                    x2 = int(np.clip(max(roi.xMin, roi.xMax), 0, ncols - 1))
                    y1 = int(np.clip(min(roi.yMin, roi.yMax), 0, nrows - 1))
                    y2 = int(np.clip(max(roi.yMin, roi.yMax), 0, nrows - 1))
                    q_box = q_arr[y1:y2 + 1, x1:x2 + 1]
                    chi_box = chi_arr[y1:y2 + 1, x1:x2 + 1]
                    q_lo = float(np.nanmin(q_box))
                    q_hi = float(np.nanmax(q_box))
                    az_lo = float(np.nanmin(chi_box))
                    az_hi = float(np.nanmax(chi_box))
                    # Echo the resolved window on the region so the caller sees
                    # which physical ROI the pixel box mapped to.
                    roi.qMin, roi.qMax = q_lo, q_hi
                    roi.azimuthMin, roi.azimuthMax = az_lo, az_hi
                else:
                    raise HTTPException(400, "pyfai ROI 需要 q/χ 窗口或像素框")
                mask = _pyfai_window_mask(q_arr, chi_arr, q_lo, q_hi, az_lo, az_hi)
            elif use_pixel_coords:
                mask = _roi_mask_pixel(arr.shape, roi)
            else:
                mask = _roi_mask(arr.shape, roi, q_range, chi_range)

            # Restrict to valid (finite, in-range) pixels — bad pixels are
            # excluded from the sum rather than counted as zero.
            roi_valid = mask & valid
            pixel_count = int(roi_valid.sum())
            if pixel_count == 0:
                results.append(ROIIntensity(
                    region=roi, meanIntensity=0.0, totalIntensity=0.0, pixelCount=0
                ))
                continue

            roi_values = arr[roi_valid]

            # Background estimation (nan-aware reductions handle any remaining
            # bad pixels in the background region). A per-ROI `background`
            # override takes precedence over the request-wide config so each
            # peak can use its own mode / side / width.
            roi_bg = roi.background if roi.background is not None else req.background
            bg = _estimate_background(arr, mask, roi_bg, req.backgroundMode, roi, q_range, chi_range)

            # Net intensity mirrors reference/function3 ``calculate_all_intensities``:
            #   net = (raw_sum − pixel_count × bg) × multiplier
            # No per-pixel negative clipping — the reference sums every pixel
            # in the box (only non-finite/saturated pixels are excluded above by
            # the validity mask), so a pixel below the background contributes its
            # true (possibly negative) value rather than being floored to 0.
            corrected = roi_values - bg
            total = float(corrected.sum()) * roi.multiplier
            mean = float(corrected.mean()) * roi.multiplier if pixel_count > 0 else 0.0

            results.append(ROIIntensity(
                region=roi,
                meanIntensity=mean,
                totalIntensity=total,
                pixelCount=pixel_count,
            ))

        return IntensityResponse(results=results)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/background-estimate", response_model=BackgroundEstimateResponse)
def estimate_background(req: BackgroundEstimateRequest):
    """Estimate a scalar background level via DBSCAN peak clustering.

    1. Pixels brighter than the ``thresholdPercentile`` percentile become peak
       candidates (a cheap pre-filter: peaks are the bright minority).
    2. DBSCAN clusters the candidates in normalized (q, χ) image coordinates
       — clusters are diffraction peaks, noise points fall back to background.
       ``eps``/``minSamples`` let the user tune how tightly pixels must group
       before they count as one peak cluster.
    3. The peak mask is dilated by ``dilationPixels`` to swallow peak tails,
       merged with the user's recorded ROI regions, and every remaining valid
       pixel is background — its ``backgroundPercentile`` percentile is the
       estimated background intensity.
    4. A downsampled copy of the peak mask comes back as ``previewMask`` so the
       user can visually verify the clusters against the image before applying
       the estimate as the fixed background for intensity extraction.
    """
    try:
        from sklearn.cluster import DBSCAN
    except ImportError:
        raise HTTPException(
            500,
            "DBSCAN 背景预估需要 scikit-learn：pip install scikit-learn",
        )

    try:
        arr = _load_image(req.fileId)
        nrows, ncols = arr.shape

        valid = np.isfinite(arr)
        if req.minIntensity is not None:
            valid &= arr >= req.minIntensity
        if req.maxIntensity is not None:
            valid &= arr <= req.maxIntensity
        if not valid.any():
            raise HTTPException(400, "No finite pixels in the validity window")

        valid_vals = arr[valid]

        # --- 1. Bright-pixel threshold with a size guard -------------------
        pct = float(req.thresholdPercentile)
        # Cap the candidate count: DBSCAN on hundreds of thousands of points
        # is slow; if the user's percentile is too permissive, raise it until
        # the candidate set is tractable (never above 99.98%).
        for _ in range(12):
            thr = float(np.percentile(valid_vals, pct))
            n_bright = int(np.count_nonzero(valid & (arr >= thr)))
            if n_bright <= 200_000:
                break
            pct = min(pct + 2.0, 99.98)
        bright = valid & (arr >= thr)

        # --- 2. DBSCAN clustering in normalized image coordinates -----------
        peak_mask = np.zeros(arr.shape, dtype=bool)
        n_clusters = 0
        clusters: list[ClusterStat] = []
        if bright.any():
            rows_i, cols_i = np.nonzero(bright)
            pts = np.column_stack([
                cols_i / max(ncols - 1, 1),
                rows_i / max(nrows - 1, 1),
            ])
            labels = DBSCAN(eps=float(req.eps), min_samples=int(req.minSamples)).fit_predict(pts)

            for lab in np.unique(labels):
                if lab < 0:
                    continue  # noise → background
                sel = labels == lab
                if int(sel.sum()) < int(req.minClusterPixels):
                    continue  # spurious speckle → background
                r_sel, c_sel = rows_i[sel], cols_i[sel]
                peak_mask[r_sel, c_sel] = True
                clusters.append(ClusterStat(
                    q=float(np.mean(c_sel) / max(ncols - 1, 1)),
                    chi=float(np.mean(r_sel) / max(nrows - 1, 1)),
                    pixels=int(sel.sum()),
                    meanIntensity=float(np.mean(arr[r_sel, c_sel])),
                ))
            n_clusters = len(clusters)

            # Sort by pixel count (largest cluster first) for the UI listing.
            clusters.sort(key=lambda c: -c.pixels)

        # --- 3. Dilate peak mask + merge user ROIs ---------------------------
        if req.dilationPixels > 0 and peak_mask.any():
            from scipy.ndimage import binary_dilation
            peak_mask = binary_dilation(
                peak_mask,
                structure=np.ones((3, 3), dtype=bool),
                iterations=int(req.dilationPixels),
            )
        q_range, chi_range = _resolve_ranges(req.fileId, req.qRange, req.chiRange)
        for roi in req.regions or []:
            peak_mask |= _roi_mask(arr.shape, roi, q_range, chi_range)

        # Report centroids in physical coordinates now that ranges are known.
        for c in clusters:
            c.q = q_range[0] + c.q * (q_range[1] - q_range[0])
            c.chi = chi_range[0] + c.chi * (chi_range[1] - chi_range[0])

        # --- 4. Background statistics ----------------------------------------
        bg_mask = valid & ~peak_mask
        if not bg_mask.any():
            # Everything was classified as peak — fall back to sub-threshold
            # pixels rather than failing outright.
            bg_mask = valid & (arr < thr)
            if not bg_mask.any():
                raise HTTPException(400, "No background pixels left after clustering")
        background_value = float(np.percentile(arr[bg_mask], float(req.backgroundPercentile)))

        # --- 5. Preview mask on the display grid -----------------------------
        # Same max_dim as GET /image/{fileId} so the overlay grid aligns
        # exactly with the displayed heatmap. Nearest-neighbour zoom keeps the
        # binary mask crisp (spline zoom would blur 0/1 cells into gray).
        from scipy.ndimage import zoom as _zoom
        h, w = peak_mask.shape
        if h > 512 or w > 512:
            factor = min(512 / h, 512 / w)
            preview = _zoom(
                peak_mask.astype(np.float64),
                factor,
                order=0,
            )
        else:
            preview = peak_mask.astype(np.float64)
        preview = np.clip(preview, 0.0, 1.0)

        return BackgroundEstimateResponse(
            backgroundValue=background_value,
            threshold=thr,
            nClusters=n_clusters,
            peakPixelCount=int(peak_mask.sum()),
            backgroundPixelCount=int(bg_mask.sum()),
            previewMask=preview.tolist(),
            clusters=clusters[:200],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/export-roi")
def export_roi(req: ExportRoiRequest):
    """Export recorded ROIs as CSV content."""
    try:
        lines = ["index,qMin,qMax,azimuthMin,azimuthMax,multiplier"]
        for i, roi in enumerate(req.regions):
            lines.append(
                f"{i},{roi.qMin:.4f},{roi.qMax:.4f},"
                f"{roi.azimuthMin:.4f},{roi.azimuthMax:.4f},{roi.multiplier:.4f}"
            )
        csv_content = "\n".join(lines)
        fid = _save_output(csv_content.encode("utf-8"), suffix=".csv")
        return {"csvContent": csv_content, "fileId": fid}
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/match-miller", response_model=MatchMillerResponse)
def match_miller(req: MatchMillerRequest):
    """
    Match each ROI to Miller-index points.

    A point matches when it falls **inside the search rectangle** — its q within
    the search q-window and its χ (ψ transformed by azimuthOffset/convention/
    normalizeToSigned, mirroring the UI overlay) within the search χ-window.
    qTolerance/chiTolerance default to 0 (strict box bounds, matching the
    reference); they only add symmetric edge slack when the user widens them.
    When several points sit inside the window, the FIRST one in file order is
    reported (reference ``found_points[0]``); export ranges use min/max over all.

    Search window selection (mirrors reference/function3 ``calculate_match_for_area``):
      - If the ROI carries a user-drawn *refine box* (matchQ/Az all set), use it.
        This lets the integration ROI stay large (good intensity statistics) while
        matching pins only the single true Miller point — discarding the spurious
        points a wide diffraction-arc box would otherwise sweep in.
      - Otherwise fall back to the integration ROI box.

    Export ranges (exportQ*/exportPsi*) are derived from the matched Miller
    points — q ± 0.02 Å⁻¹ and ψ ± 3° — NOT the integration-box ranges, so the
    exported peak identity tracks the Miller point rather than the box the user
    happened to draw. When nothing matches, the search window is inverse-mapped
    to Miller ψ so the columns still carry Miller-space angles.
    """
    # Half-widths of the export margin around the matched Miller points /
    # search box. User-tunable on the request (defaults dq=0.02 Å⁻¹, dψ=2°).
    export_q_margin = float(req.exportQMargin)
    export_psi_margin = float(req.exportPsiMargin)

    try:
        results: list[MatchResult] = []
        for roi in req.regions:
            # --- Pick the search window: refine box if present, else integration ROI
            has_refine = (
                roi.matchQMin is not None and roi.matchQMax is not None
                and roi.matchAzMin is not None and roi.matchAzMax is not None
            )
            if has_refine:
                # q is monotonic — safe to reorder to [lo, hi]. χ direction is
                # preserved (NOT reordered) so _angular_in_range can detect a
                # ±180° seam-crossing refine box (matchAzMin > matchAzMax),
                # matching the reference's wrap handling.
                s_q_lo, s_q_hi = min(roi.matchQMin, roi.matchQMax), max(roi.matchQMin, roi.matchQMax)
                s_az_lo, s_az_hi = roi.matchAzMin, roi.matchAzMax
            else:
                s_q_lo, s_q_hi = min(roi.qMin, roi.qMax), max(roi.qMin, roi.qMax)
                s_az_lo, s_az_hi = roi.azimuthMin, roi.azimuthMax

            # Collect every Miller point inside the search rectangle. Iteration
            # order is preserved (dataset order, then point order within) so the
            # reported hkl is the FIRST matching point in file order — matching
            # reference/function3 ``found_points[0]`` (no nearest-to-centre sort).
            inside: list[MillerPoint] = []
            for ds in req.millerDatasets:
                for pt in ds.points:
                    if not (s_q_lo - req.qTolerance <= pt.q <= s_q_hi + req.qTolerance):
                        continue
                    pt_chi = _miller_psi_to_chi(
                        pt.psi, req.azimuthOffset, req.convention, req.normalizeToSigned
                    )
                    if not _angular_in_range(pt_chi, s_az_lo, s_az_hi, req.chiTolerance):
                        continue
                    inside.append(pt)

            matched = inside
            status = "Found" if matched else "Not Found"

            # --- Export ranges (min/max of the matched points ± user margins).
            # 精致化 spec: take the min/max q and χ(ψ) of the Miller points
            # inside the search box (refine box when present), then grow by
            # dq/dψ so the window fully covers the peak without sweeping in
            # neighbouring peaks.
            if matched:
                qs = [pt.q for pt in matched]
                psis = [pt.psi for pt in matched]  # raw Miller ψ — export in Miller space
                export_q_min = min(qs) - export_q_margin
                export_q_max = max(qs) + export_q_margin
                export_psi_min = min(psis) - export_psi_margin
                export_psi_max = max(psis) + export_psi_margin
            else:
                # No point found: carry the search window q forward (± the
                # same margin — the fallback used to apply none, which broke
                # the "已精致化" exports), and inverse-map its χ bounds back to
                # Miller ψ so the column units stay ψ.
                export_q_min = s_q_lo - export_q_margin
                export_q_max = s_q_hi + export_q_margin
                p1 = _chi_to_psi(s_az_lo, req.azimuthOffset, req.convention, req.normalizeToSigned)
                p2 = _chi_to_psi(s_az_hi, req.azimuthOffset, req.convention, req.normalizeToSigned)
                export_psi_min = min(p1, p2) - export_psi_margin
                export_psi_max = max(p1, p2) + export_psi_margin

            results.append(MatchResult(
                region=roi,
                status=status,
                matchedPoints=matched,
                refined=has_refine,
                exportQMin=export_q_min,
                exportQMax=export_q_max,
                exportPsiMin=export_psi_min,
                exportPsiMax=export_psi_max,
            ))

        return MatchMillerResponse(results=results)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))
