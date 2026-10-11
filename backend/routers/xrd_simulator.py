"""
XRD simulation router — single-phase fiber diffraction.

Two simulation modes (mirroring reference/function2/Gaussianresult.py):

  * ``cake``     — "原始探测器": a 2-D Gaussian broadening on a q-χ grid
    (the cake representation).  Chi uses periodic boundary conditions.
  * ``detector`` — "2D 探测器": a real 2-D detector image in pixel space.
    Each (q, χ) peak is projected onto the detector via PONI geometry
    (wavelength, sample-detector distance, beam centre, pixel size, image
    dims) and broadened with a local-patch 2-D Gaussian.

Two compute kernels per mode, selected per request (``kernel`` field):

  * ``fast`` (default) — cake: separable 1-D Gaussians combined with one
    matrix product per peak block (the reference implementation's method,
    batched); detector: numba row-parallel kernel.  40-400x faster than
    legacy, numerically equivalent (max rel. diff ~1e-15).  Falls back to
    the legacy numpy paths when numba is not installed.
  * ``legacy`` — the original per-peak full-grid / patch numpy loops,
    kept bit-for-bit as the compatibility option.

Detector-mode responses carry a ≤1000×1000 decimated preview (the frontend
display cap) plus ``fileId``/``fullShape``; the full-resolution float32
image is fetched via ``GET /task/{fileId}/f32`` (export path).

Input is a fiber peak list ``peak_result.txt`` — either 7-column
``h k l q psi intensity belongto`` (psi == χ, the fiber azimuth) or the
6-column ``h k l q chi intensity`` legacy form.  The CIF → peak pipeline
(``/generate-peaks``) already emits the same psi-based fiber peaks.

Detector geometry is resolved from an uploaded PONI file (pyFAI, via the
shared ``waxs_pipeline._parse_poni``) with optional per-field overrides,
so the flow is "upload PONI → auto-fill → edit".
"""

from __future__ import annotations

import base64
import math
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from utils import (
    _file_path,
    _parse_processing_info,
    _q_range_to_angstrom,
    _save_array,
    _save_upload,
)
from routers.waxs_pipeline import _parse_poni

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PeakRow(BaseModel):
    h: int
    k: int
    l: int
    q: float
    chi: float
    intensity: float


class UploadPeaksResponse(BaseModel):
    peaks: List[PeakRow]
    fileId: str


class UploadCifResponse(BaseModel):
    fileId: str
    formula: str
    spaceGroup: str
    latticeParams: Dict[str, float]


class GeneratePeaksRequest(BaseModel):
    cifContent: str = Field(..., description="Raw CIF text content")
    wavelength: float = Field(1.5406, description="X-ray wavelength in Angstroms")
    xrayMode: str = Field("synchrotron", description="synchrotron or laboratory")
    maxQ: Optional[float] = Field(None, gt=0, description="Keep only peaks with q <= maxQ (1/Angstrom); None = no limit")
    maxH: Optional[int] = Field(None, ge=0, description="Keep only peaks with |h| <= maxH; None = no limit")
    maxK: Optional[int] = Field(None, ge=0, description="Keep only peaks with |k| <= maxK; None = no limit")
    maxL: Optional[int] = Field(None, ge=0, description="Keep only peaks with |l| <= maxL; None = no limit")
    minIntensity: Optional[float] = Field(None, ge=0, description="Keep only peaks with corrected intensity > minIntensity; default 1e-4")


class GeneratePeaksResponse(BaseModel):
    peaks: List[PeakRow]
    fileId: str


class GridParams(BaseModel):
    qMin: float = Field(0.0)
    qMax: float = Field(25.0)
    chiMin: float = Field(-180.0)
    chiMax: float = Field(180.0)
    nQ: int = Field(500, ge=10)
    nChi: int = Field(360, ge=10)


class DetectorParams(BaseModel):
    """2-D detector geometry.  All fields optional so a request can carry a
    partial override on top of the PONI-derived defaults.

    Units: wavelength Å, sample-detector distance mm, pixel size μm,
    centres / image dims in pixels.
    """
    wavelength_A: Optional[float] = Field(None, description="Wavelength (Å)")
    sd_mm: Optional[float] = Field(None, description="Sample-detector distance (mm)")
    centerx_px: Optional[float] = Field(None, description="Beam centre X (px)")
    centery_px: Optional[float] = Field(None, description="Beam centre Y (px)")
    pixelSize_um: Optional[float] = Field(None, description="Pixel size (μm)")
    imgW: Optional[int] = Field(None, description="Image width (px)")
    imgH: Optional[int] = Field(None, description="Image height (px)")


class SimulateRequest(BaseModel):
    peaks: List[PeakRow]
    sigmaQ: float = Field(0.03, description="Gaussian sigma in q (A^-1)")
    sigmaChi: float = Field(3.0, description="Gaussian sigma in chi (degrees)")
    mode: str = Field("cake", description="cake or detector")
    kernel: str = Field("fast", description="Compute kernel: fast or legacy")
    grid: GridParams = Field(default_factory=GridParams)
    # Detector mode geometry: PONI file-id (auto-fill) and/or explicit overrides.
    poniFileId: Optional[str] = Field(None, description="PONI file-id for detector mode")
    detector: Optional[DetectorParams] = Field(None, description="Detector geometry overrides")
    expandSymmetry: bool = Field(True, description="4-fold fiber symmetry expansion (on by default for single-phase fiber diffraction)")


class SimulateResponse(BaseModel):
    imageBase64: Optional[str] = None
    fileId: Optional[str] = None
    shape: List[int]
    # Full-resolution shape when imageBase64 carries a decimated detector
    # preview (equal to `shape` otherwise); fetch the full image via
    # GET /task/{fileId}/f32.
    fullShape: Optional[List[int]] = None


class DualSimulateRequest(BaseModel):
    peaksA: List[PeakRow]
    peaksB: List[PeakRow]
    ratio: float = Field(0.5, ge=0.0, le=1.0, description="Fraction of phase A")
    sigmaQ: float = 0.03
    sigmaChi: float = 3.0
    mode: str = "cake"
    kernel: str = Field("fast", description="Compute kernel: fast or legacy")
    grid: GridParams = Field(default_factory=GridParams)
    poniFileId: Optional[str] = None
    detector: Optional[DetectorParams] = None
    expandSymmetry: bool = Field(False, description="4-fold fiber symmetry expansion")


class PoniGeometryResponse(BaseModel):
    """Detector geometry derived from a PONI file (simulator units)."""
    wavelength_A: float
    sd_mm: float
    centerx_px: float
    centery_px: float
    pixelSize_um: float
    imgW: int
    imgH: int
    detector: Optional[str] = None


class ProcessingInfoGridResponse(BaseModel):
    """Cake grid (q-χ) recovered from a 2-D-integration ``processing_info``
    file.  Any field the source file omits is left ``None`` so the caller can
    keep the current value.  q is always returned in Å^-1 (nm^-1 sources are
    converted).
    """
    qMin: Optional[float] = None
    qMax: Optional[float] = None
    chiMin: Optional[float] = None
    chiMax: Optional[float] = None
    nQ: Optional[int] = None
    nChi: Optional[int] = None
    xUnit: Optional[str] = None


# ---------------------------------------------------------------------------
# Peak-list parsing  (peak_result.txt)
# ---------------------------------------------------------------------------

def _parse_peak_lines(text: str) -> List[PeakRow]:
    """Parse a fiber peak list into PeakRow.

    Accepts both:

      * 7-column ``h k l q psi intensity belongto`` (psi == χ)
      * 6-column ``h k l q chi intensity``

    Lines starting with ``#`` and header lines whose first token is not an
    integer (e.g. ``h1``, ``h``) are skipped.
    """
    peaks: List[PeakRow] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 6:
            continue
        # Skip header rows: hkl columns must parse as ints.
        try:
            h, k, l = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        try:
            q = float(parts[3])
            chi = float(parts[4])           # psi for the 7-column form
            intensity = float(parts[5])     # parts[6] (belongto) ignored
        except ValueError:
            continue
        peaks.append(PeakRow(h=h, k=k, l=l, q=q, chi=chi, intensity=intensity))
    return peaks


# ---------------------------------------------------------------------------
# 4-fold fiber symmetry expansion
# ---------------------------------------------------------------------------

def _expand_peaks_symmetry(peaks: List[PeakRow]) -> List[PeakRow]:
    """Replicate peaks from the first quadrant to all four quadrants.

    Assumes input peaks have chi normalised to [0, 90].  Generates four
    copies at chi, 180-chi, -180+chi, -chi for each peak — the fiber
    four-fold symmetry.
    """
    expanded: List[PeakRow] = []
    for pk in peaks:
        chi_norm = abs(pk.chi) % 90.0
        for chi_val in [chi_norm, 180.0 - chi_norm, -180.0 + chi_norm, -chi_norm]:
            expanded.append(PeakRow(
                h=pk.h, k=pk.k, l=pk.l,
                q=pk.q, chi=chi_val, intensity=pk.intensity,
            ))
    return expanded


# ---------------------------------------------------------------------------
# Simulation core
# ---------------------------------------------------------------------------

def _gaussian_cake(
    peaks: List[PeakRow],
    sigma_q: float,
    sigma_chi: float,
    grid: GridParams,
    weight: float = 1.0,
) -> np.ndarray:
    """
    Generate a 2-D cake image (chi x q) by placing a 2-D Gaussian at every
    peak position.  Chi is treated with periodic boundary conditions.

    No sqrt(2π·σ) normalisation divisor (matches reference Gaussianresult.py).

    Returns array of shape (nChi, nQ).
    """
    q_arr = np.linspace(grid.qMin, grid.qMax, grid.nQ)
    chi_arr = np.linspace(grid.chiMin, grid.chiMax, grid.nChi)
    q_grid, chi_grid = np.meshgrid(q_arr, chi_arr)

    img = np.zeros_like(q_grid)

    for pk in peaks:
        dq = q_grid - pk.q
        # periodic chi distance (period 360°)
        dchi_raw = chi_grid - pk.chi
        dchi = np.minimum(np.abs(dchi_raw), 360.0 - np.abs(dchi_raw))

        gauss = pk.intensity * weight * np.exp(
            -0.5 * (dq ** 2 / sigma_q ** 2 + dchi ** 2 / sigma_chi ** 2)
        )
        img += gauss

    return img


# ---------------------------------------------------------------------------
# Fast kernels (default) — numerically equivalent, 40-400x faster
# ---------------------------------------------------------------------------

# Detector previews are decimated to at most this many pixels per axis
# (matches the frontend heatmap display cap); full resolution stays
# available via fileId.
_PREVIEW_MAX = 1000

# Peaks are processed in blocks of this size in the cake gemm kernel so the
# two (block x axis) kernel matrices stay small even for huge peak lists.
_CAKE_BLOCK = 2048


def _peaks_to_arrays(peaks: List[PeakRow]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """PeakRow list -> (q, chi, intensity) float64 arrays."""
    n = len(peaks)
    qs = np.fromiter((pk.q for pk in peaks), dtype=np.float64, count=n)
    chis = np.fromiter((pk.chi for pk in peaks), dtype=np.float64, count=n)
    ws = np.fromiter((pk.intensity for pk in peaks), dtype=np.float64, count=n)
    return qs, chis, ws


def _gaussian_cake_fast(
    qs: np.ndarray,
    chis: np.ndarray,
    ws: np.ndarray,
    sigma_q: float,
    sigma_chi: float,
    grid: GridParams,
) -> np.ndarray:
    """
    Fast cake kernel: the 2-D Gaussian is separable, so per peak only two
    1-D kernels are needed; the outer products for a block of peaks are then
    a single matrix product ``img += (E_chi * w).T @ E_q``.

    Same maths (and the reference implementation's method) as
    ``_gaussian_cake``; chi stays periodic.  ``ws`` carries any phase weight.
    """
    q_arr = np.linspace(grid.qMin, grid.qMax, grid.nQ)
    chi_arr = np.linspace(grid.chiMin, grid.chiMax, grid.nChi)
    inv_q = -0.5 / (sigma_q * sigma_q)
    inv_c = -0.5 / (sigma_chi * sigma_chi)

    img = np.zeros((grid.nChi, grid.nQ))
    for s in range(0, qs.shape[0], _CAKE_BLOCK):
        e = min(qs.shape[0], s + _CAKE_BLOCK)
        eq = np.exp(((q_arr[None, :] - qs[s:e, None]) ** 2) * inv_q)   # (b, nQ)
        dchi = (chi_arr[None, :] - chis[s:e, None] + 180.0) % 360.0 - 180.0
        ec = np.exp((dchi ** 2) * inv_c)                               # (b, nChi)
        img += (ec * ws[s:e, None]).T @ eq
    return img


def _simulate_detector_fast_arrays(
    qs: np.ndarray,
    chis: np.ndarray,
    ws: np.ndarray,
    sigma_q: float,
    sigma_chi: float,
    geom: DetectorParams,
) -> Optional[np.ndarray]:
    """
    Fast detector kernel on packed peak arrays (weights folded into ``ws``).

    Returns None when numba is unavailable, so callers can fall back to the
    legacy numpy path.
    """
    try:
        from routers import _xrd_fast_kernels as fk
    except ImportError:
        return None

    img = np.zeros((int(geom.imgH), int(geom.imgW)), dtype=np.float64)
    fk.detector_row_parallel(
        img, qs, chis, ws,
        float(geom.centerx_px), float(geom.centery_px),
        geom.pixelSize_um * 1e-3,
        float(geom.sd_mm), float(geom.wavelength_A),
        float(sigma_q), float(sigma_chi),
    )
    return img


def _simulate_detector_fast(
    peaks: List[PeakRow],
    sigma_q: float,
    sigma_chi: float,
    geom: DetectorParams,
) -> np.ndarray:
    img = _simulate_detector_fast_arrays(*_peaks_to_arrays(peaks), sigma_q, sigma_chi, geom)
    if img is None:                       # numba missing -> legacy fallback
        return _simulate_detector(peaks, sigma_q, sigma_chi, geom)
    return img


def _validate_kernel(kernel: str) -> None:
    if kernel not in ("fast", "legacy"):
        raise HTTPException(400, detail=f"Unknown kernel: {kernel} (use 'fast' or 'legacy')")


def _respond_image(img: np.ndarray, mode: str) -> SimulateResponse:
    """Save the full image, return a transport-sized preview as base64.

    Detector images are decimated to <= _PREVIEW_MAX per axis (the display
    never shows more); cake grids are small enough to ship as-is.
    """
    fid = _save_array(img)
    preview = img
    if mode == "detector":
        step_r = max(1, math.ceil(img.shape[0] / _PREVIEW_MAX))
        step_c = max(1, math.ceil(img.shape[1] / _PREVIEW_MAX))
        preview = np.ascontiguousarray(img[::step_r, ::step_c])
    b64 = base64.b64encode(preview.astype(np.float32).tobytes()).decode("ascii")
    return SimulateResponse(
        imageBase64=b64, fileId=fid,
        shape=list(preview.shape), fullShape=list(img.shape),
    )


def _resolve_detector_geometry(
    poni_file_id: Optional[str],
    det: Optional[DetectorParams],
) -> DetectorParams:
    """Resolve a fully-populated DetectorParams from PONI + overrides.

    PONI (when given) supplies the defaults; any non-None field on ``det``
    overrides it; remaining gaps fall back to sane defaults.  Raises 400 on
    physically invalid geometry.
    """
    defaults = DetectorParams(
        wavelength_A=1.5406, sd_mm=100.0,
        centerx_px=1024.0, centery_px=1024.0,
        pixelSize_um=75.0, imgW=2048, imgH=2048,
    )
    src: Dict[str, Any] = {}

    if poni_file_id:
        poni = _parse_poni(poni_file_id)
        pixel1 = poni.get("pixel1") or 7.5e-5
        pixel2 = poni.get("pixel2") or pixel1
        max_shape = poni.get("maxShape") or [None, None]
        src = dict(
            wavelength_A=poni["wavelength"] * 10.0,     # nm -> Å
            sd_mm=poni["dist"] * 1000.0,                # m -> mm
            centerx_px=poni["poni2"] / pixel2,          # poni2 (m) / pixel2 (m)
            centery_px=poni["poni1"] / pixel1,
            pixelSize_um=pixel2 * 1e6,                  # m -> μm
            imgW=int(max_shape[1]) if max_shape[1] is not None else None,
            imgH=int(max_shape[0]) if max_shape[0] is not None else None,
        )

    if det is not None:
        for f in ("wavelength_A", "sd_mm", "centerx_px", "centery_px",
                  "pixelSize_um", "imgW", "imgH"):
            v = getattr(det, f)
            if v is not None:
                src[f] = v

    resolved = DetectorParams(**{
        f: src.get(f, getattr(defaults, f))
        for f in ("wavelength_A", "sd_mm", "centerx_px", "centery_px",
                  "pixelSize_um", "imgW", "imgH")
    })

    if resolved.wavelength_A <= 0 or resolved.sd_mm <= 0 or resolved.pixelSize_um <= 0:
        raise HTTPException(400, detail="Detector geometry: wavelength, sample distance and pixel size must be > 0")
    if resolved.imgW < 8 or resolved.imgH < 8:
        raise HTTPException(400, detail="Detector geometry: image dimensions too small")
    return resolved


def _simulate_detector(
    peaks: List[PeakRow],
    sigma_q: float,
    sigma_chi: float,
    geom: DetectorParams,
) -> np.ndarray:
    """Pure-numpy 2-D detector simulation.

    For every pixel the (q, χ) coordinates are computed from the detector
    geometry; every peak then contributes a local-patch 2-D Gaussian in
    (Δq, Δχ) with periodic χ wrap.  Each peak only touches a ±6σ patch, so
    the cost scales with (peaks × patch area) rather than (peaks × image).

    Geometry (matches reference Gaussianresult.py ``gaussian_detector_v2``):
      twoθ = atan(r_mm / sd);  q = 4π sin(twoθ/2) / λ;  χ = atan2(dy, dx).
    Returns an image of shape (imgH, imgW).
    """
    img_h = int(geom.imgH)
    img_w = int(geom.imgW)
    lam = geom.wavelength_A
    sd = geom.sd_mm
    ps = geom.pixelSize_um * 1e-3          # mm per pixel
    cx, cy = geom.centerx_px, geom.centery_px

    sigma_q = float(sigma_q)
    sigma_chi_deg = float(sigma_chi)
    sigma_chi_rad = np.radians(sigma_chi_deg)

    img = np.zeros((img_h, img_w), dtype=np.float64)

    # Per-pixel q and chi grids (vectorised, computed once).
    xs = np.arange(img_w)                  # column index (x)
    ys = np.arange(img_h)                  # row index (y)
    XX, YY = np.meshgrid(xs, ys)           # shape (img_h, img_w)
    dx_mm = (XX - cx) * ps
    dy_mm = (YY - cy) * ps
    r_mm = np.sqrt(dx_mm ** 2 + dy_mm ** 2)
    two_theta = np.arctan(r_mm / sd)
    q_px = 4.0 * np.pi * np.sin(two_theta / 2.0) / lam
    chi_px = np.degrees(np.arctan2(dy_mm, dx_mm))     # [-180, 180]

    for pk in peaks:
        q0 = pk.q
        chi0 = pk.chi                            # degrees
        intensity = pk.intensity

        # Peak → detector footprint.
        stt_arg = q0 * lam / (4.0 * np.pi)
        if stt_arg >= 1.0 or stt_arg <= 0.0:
            continue                            # outside Ewald reach
        two_theta_peak = 2.0 * np.arcsin(stt_arg)
        r_mm_peak = sd * np.tan(two_theta_peak)
        r_px = r_mm_peak / ps
        chi0_rad = np.radians(chi0)
        cx_peak = cx + r_px * np.cos(chi0_rad)
        cy_peak = cy + r_px * np.sin(chi0_rad)

        # Pixel-space σ: convert the q- and χ-Gaussian widths to pixels at
        # the peak radius so the patch size is physically meaningful.
        cos_half = np.cos(two_theta_peak / 2.0)
        cos_tt = np.cos(two_theta_peak)
        dq_dr_mm = (2.0 * np.pi / lam) * cos_half * (cos_tt ** 2) / sd
        dq_dpx = abs(dq_dr_mm) * ps
        if dq_dpx < 1e-12:
            dq_dpx = 1e-12
        sigma_q_px = sigma_q / dq_dpx
        sigma_chi_px = sigma_chi_rad * max(r_px, 1.0)

        half = 6.0 * max(sigma_q_px, sigma_chi_px, 1.0)
        x0 = max(int(np.floor(cx_peak - half)), 0)
        x1 = min(int(np.ceil(cx_peak + half)) + 1, img_w)
        y0 = max(int(np.floor(cy_peak - half)), 0)
        y1 = min(int(np.ceil(cy_peak + half)) + 1, img_h)
        if x0 >= x1 or y0 >= y1:
            continue

        patch_q = q_px[y0:y1, x0:x1]
        patch_chi = chi_px[y0:y1, x0:x1]
        dq = patch_q - q0
        dchi = patch_chi - chi0
        dchi = (dchi + 180.0) % 360.0 - 180.0          # periodic wrap
        gauss = intensity * np.exp(
            -0.5 * (dq ** 2 / sigma_q ** 2 + dchi ** 2 / sigma_chi_deg ** 2)
        )
        img[y0:y1, x0:x1] += gauss

    return img


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload-peaks", response_model=UploadPeaksResponse)
def upload_peaks(file: UploadFile = File(...)):
    """Upload a peak-list text file.

    Accepts the fiber ``peak_result.txt`` form (``h k l q psi intensity
    belongto``) or the 6-column ``h k l q chi intensity`` form.
    """
    try:
        raw = file.file.read()
        ext = os.path.splitext(file.filename or "")[1] or ".txt"
        fid = _save_upload(raw, suffix=ext)
        text = raw.decode("utf-8", errors="replace")
        peaks = _parse_peak_lines(text)
        return UploadPeaksResponse(peaks=peaks, fileId=fid)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/upload")
def upload_file(file: UploadFile = File(...)):
    """Upload a generic file (e.g. a PONI calibration) and return a file-id."""
    try:
        data = file.file.read()
        ext = os.path.splitext(file.filename or "")[1]
        fid = _save_upload(data, suffix=ext)
        return {"fileId": fid, "originalName": file.filename, "size": len(data)}
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/upload-cif", response_model=UploadCifResponse)
def upload_cif(file: UploadFile = File(...)):
    """Upload a CIF file and parse structure info with pymatgen."""
    try:
        raw = file.file.read()
        ext = ".cif"
        fid = _save_upload(raw, suffix=ext)
        path = _file_path(fid)

        from pymatgen.core import Structure

        struct = Structure.from_file(path)
        lp = struct.lattice
        return UploadCifResponse(
            fileId=fid,
            formula=struct.composition.reduced_formula,
            spaceGroup=struct.get_space_group_info()[0] if hasattr(struct, "get_space_group_info") else "unknown",
            latticeParams={
                "a": lp.a, "b": lp.b, "c": lp.c,
                "alpha": lp.alpha, "beta": lp.beta, "gamma": lp.gamma,
            },
        )
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/generate-peaks", response_model=GeneratePeaksResponse)
def generate_peaks(req: GeneratePeaksRequest):
    """
    Generate theoretical fiber diffraction peaks from CIF content using
    pymatgen's XRDCalculator with L1/P1 corrections (psi == fiber χ).

    Optional output filters (maxQ / maxH / maxK / maxL / minIntensity) keep the
    peak list small enough for the simulator; maxQ is also pushed down to
    pymatgen as a two_theta_range cap so far-out reflections are never
    computed at all.

    Ported from reference/function2/genfakepeaksresult.py.
    """
    try:
        from pymatgen.analysis.diffraction.xrd import XRDCalculator
        from pymatgen.core import Structure

        struct = Structure.from_str(req.cifContent, fmt="cif")
        c_lattice = struct.lattice.c

        calculator = XRDCalculator(wavelength=req.wavelength)
        # q = 4*pi*sin(theta)/lambda  ->  two_theta_max = 2*asin(maxQ*lambda/(4*pi))
        pattern_kwargs: Dict[str, Any] = {}
        if req.maxQ is not None and req.maxQ > 0:
            sin_theta = min(1.0, req.maxQ * req.wavelength / (4.0 * np.pi))
            pattern_kwargs["two_theta_range"] = (
                0.0, float(np.degrees(2.0 * np.arcsin(sin_theta)))
            )
        pattern = calculator.get_pattern(struct, scaled=False, **pattern_kwargs)

        is_synchrotron = req.xrayMode.lower() == "synchrotron"

        peaks: list[PeakRow] = []

        for i in range(len(pattern.x)):
            two_theta_deg = pattern.x[i]
            theta_rad = np.radians(two_theta_deg / 2.0)
            d = pattern.d_hkls[i]
            base_intensity = pattern.y[i]
            hkl_list = pattern.hkls[i]

            for hkl_item in hkl_list:
                h, k, l = hkl_item['hkl']

                y1 = l / c_lattice
                q = 2.0 * np.pi / d
                d1 = (1.0 / req.wavelength) * np.sin(2.0 * theta_rad)

                term_d_chk = 4.0 * d ** 2 - req.wavelength ** 2
                if abs(d1) < 1e-12:
                    ratio = 9999.0
                else:
                    ratio = y1 / d1

                if (ratio > 1.0) or (ratio < -1.0) or (term_d_chk < 0):
                    psi_deg = 90.0
                else:
                    psi_deg = abs(np.degrees(np.arcsin(ratio)))
                psi_rad = np.radians(psi_deg)

                q_term = (q / (2.0 * np.pi)) * req.wavelength
                check_val = q_term ** 2 - (y1 * req.wavelength) ** 2 - (q_term ** 4) / 4.0
                if check_val > 1e-9:
                    denom = np.sin(2.0 * theta_rad) * np.cos(psi_rad)
                    L_1 = 0.0 if abs(denom) < 1e-9 else 1.0 / denom
                else:
                    L_1 = 0.0

                if is_synchrotron:
                    P_1 = (np.sin(psi_rad) ** 2) + (np.cos(psi_rad) ** 2) * (np.cos(2.0 * theta_rad) ** 2)
                else:
                    P_1 = (1.0 + np.cos(2.0 * theta_rad) ** 2) / 2.0

                final_intensity = base_intensity * L_1 * P_1
                if req.maxQ is not None and q > req.maxQ:
                    continue
                if req.maxH is not None and abs(int(h)) > req.maxH:
                    continue
                if req.maxK is not None and abs(int(k)) > req.maxK:
                    continue
                if req.maxL is not None and abs(int(l)) > req.maxL:
                    continue
                if final_intensity > (0.0001 if req.minIntensity is None else req.minIntensity):
                    peaks.append(PeakRow(
                        h=int(h), k=int(k), l=int(l),
                        q=float(q), chi=float(psi_deg),
                        intensity=float(final_intensity),
                    ))

        fid = _save_array(np.array(
            [[p.h, p.k, p.l, p.q, p.chi, p.intensity] for p in peaks]
        ) if peaks else np.empty((0, 6)))
        return GeneratePeaksResponse(peaks=peaks, fileId=fid)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/parse-poni", response_model=PoniGeometryResponse)
def parse_poni(fileId: str = Body(..., embed=True)):
    """Parse a PONI file and return detector geometry in simulator units.

    Used by the single-phase detector mode to auto-fill the geometry
    (wavelength Å, distance mm, beam centre px, pixel size μm, image dims).
    """
    try:
        geom = _resolve_detector_geometry(fileId, None)
        poni = _parse_poni(fileId)
        return PoniGeometryResponse(
            wavelength_A=geom.wavelength_A,
            sd_mm=geom.sd_mm,
            centerx_px=geom.centerx_px,
            centery_px=geom.centery_px,
            pixelSize_um=geom.pixelSize_um,
            imgW=int(geom.imgW),
            imgH=int(geom.imgH),
            detector=poni.get("detector"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/parse-processing-info", response_model=ProcessingInfoGridResponse)
def parse_processing_info(fileId: str = Body(..., embed=True)):
    """Recover the cake grid from a 2-D-integration ``processing_info`` file
    (JSON or legacy text) and return it in simulator units (q in Å^-1).

    Lets the single-phase cake image reuse the *same* q-χ grid as a real
    integration run, so the simulated cake lines up pixel-for-pixel with the
    measured one.  Accepts a previously-uploaded file-id (``/upload``).
    """
    try:
        path = _file_path(fileId)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except FileNotFoundError:
        raise HTTPException(404, detail="processing_info file not found")
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))

    info = _parse_processing_info(text)
    unit = info.get("x_axis_unit")
    q_min, q_max = info.get("q_min"), info.get("q_max")
    if q_min is not None and q_max is not None:
        q_min, q_max = _q_range_to_angstrom((q_min, q_max), unit)

    return ProcessingInfoGridResponse(
        qMin=q_min,
        qMax=q_max,
        chiMin=info.get("chi_min"),
        chiMax=info.get("chi_max"),
        nQ=info.get("npt_rad"),
        nChi=info.get("npt_azim"),
        xUnit=unit,
    )


@router.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest):
    """Run single-phase fiber diffraction simulation (cake or detector)."""
    try:
        _validate_kernel(req.kernel)
        peaks = req.peaks
        if req.expandSymmetry:
            peaks = _expand_peaks_symmetry(peaks)

        if req.mode == "cake":
            if req.kernel == "legacy":
                img = _gaussian_cake(peaks, req.sigmaQ, req.sigmaChi, req.grid)
            else:
                img = _gaussian_cake_fast(
                    *_peaks_to_arrays(peaks), req.sigmaQ, req.sigmaChi, req.grid,
                )
        elif req.mode == "detector":
            geom = _resolve_detector_geometry(req.poniFileId, req.detector)
            if req.kernel == "legacy":
                img = _simulate_detector(peaks, req.sigmaQ, req.sigmaChi, geom)
            else:
                img = _simulate_detector_fast(peaks, req.sigmaQ, req.sigmaChi, geom)
        else:
            raise HTTPException(400, detail=f"Unknown mode: {req.mode}")

        return _respond_image(img, req.mode)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/simulate-dual", response_model=SimulateResponse)
def simulate_dual(req: DualSimulateRequest):
    """Run dual-phase simulation (weighted sum of two fiber phases)."""
    try:
        _validate_kernel(req.kernel)
        peaks_a = req.peaksA
        peaks_b = req.peaksB
        if req.expandSymmetry:
            peaks_a = _expand_peaks_symmetry(peaks_a)
            peaks_b = _expand_peaks_symmetry(peaks_b)

        if req.mode not in ("cake", "detector"):
            raise HTTPException(400, detail=f"Unknown mode: {req.mode}")

        img: Optional[np.ndarray] = None

        if req.kernel == "fast" and req.mode == "cake":
            # Weighted phases share one gemm pass (ratio folded into weights).
            qs_a, chis_a, ws_a = _peaks_to_arrays(peaks_a)
            qs_b, chis_b, ws_b = _peaks_to_arrays(peaks_b)
            img = _gaussian_cake_fast(
                np.concatenate([qs_a, qs_b]),
                np.concatenate([chis_a, chis_b]),
                np.concatenate([ws_a * req.ratio, ws_b * (1.0 - req.ratio)]),
                req.sigmaQ, req.sigmaChi, req.grid,
            )
        elif req.kernel == "fast" and req.mode == "detector":
            qs_a, chis_a, ws_a = _peaks_to_arrays(peaks_a)
            qs_b, chis_b, ws_b = _peaks_to_arrays(peaks_b)
            geom = _resolve_detector_geometry(req.poniFileId, req.detector)
            img = _simulate_detector_fast_arrays(
                np.concatenate([qs_a, qs_b]),
                np.concatenate([chis_a, chis_b]),
                np.concatenate([ws_a * req.ratio, ws_b * (1.0 - req.ratio)]),
                req.sigmaQ, req.sigmaChi, geom,
            )

        if img is None:
            # Legacy kernel, or fast detector with numba missing: the
            # original two-pass weighted simulation.
            if req.mode == "cake":
                img_a = _gaussian_cake(peaks_a, req.sigmaQ, req.sigmaChi, req.grid, weight=req.ratio)
                img_b = _gaussian_cake(peaks_b, req.sigmaQ, req.sigmaChi, req.grid, weight=1.0 - req.ratio)
                img = img_a + img_b
            else:
                geom = _resolve_detector_geometry(req.poniFileId, req.detector)
                img_a = _simulate_detector(peaks_a, req.sigmaQ, req.sigmaChi, geom)
                img_b = _simulate_detector(peaks_b, req.sigmaQ, req.sigmaChi, geom)
                img = req.ratio * img_a + (1.0 - req.ratio) * img_b

        return _respond_image(img, req.mode)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.get("/task/{taskId}/download")
def task_download(taskId: str):
    """Download a simulation result file."""
    from fastapi.responses import FileResponse

    path = _file_path(taskId)
    return FileResponse(path, filename=os.path.basename(path), media_type="application/octet-stream")


@router.get("/task/{taskId}/f32")
def task_f32(taskId: str):
    """Full-resolution simulation image as raw little-endian float32 bytes.

    Used by the export path to recover the exact image behind a decimated
    detector preview (shape = the response's ``fullShape``).
    """
    from fastapi.responses import Response

    try:
        path = _file_path(taskId)
        arr = np.load(path)
        return Response(
            content=arr.astype(np.float32).tobytes(),
            media_type="application/octet-stream",
        )
    except FileNotFoundError:
        raise HTTPException(404, detail="result file not found")
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


def _warm_numba() -> None:
    """Import and JIT-compile the fast detector kernel (best effort)."""
    try:
        from routers import _xrd_fast_kernels as fk

        fk.warmup()
    except Exception:
        pass


threading.Thread(target=_warm_numba, daemon=True, name="xrd-numba-warmup").start()


class LoadExperimentRequest(BaseModel):
    fileId: str
    mode: str = "cake"


@router.post("/load-experiment")
def load_experiment(req: LoadExperimentRequest):
    """Load an experimental data file (.npy or .tif) and return as base64 float32.

    For cake mode, accepts .npy (2-D array). For detector mode, accepts
    .tif/.tiff/.edf/.npy. Returns the same format as the simulate endpoint
    so the frontend can reuse its heatmap rendering.
    """
    try:
        path = _file_path(req.fileId)
        ext = os.path.splitext(path)[1].lower()

        if ext == ".npy":
            arr = np.load(path)
        elif ext in (".tif", ".tiff"):
            try:
                import fabio
                arr = fabio.open(path).data.astype(np.float64)
            except ImportError:
                from PIL import Image
                arr = np.array(Image.open(path), dtype=np.float64)
        elif ext == ".edf":
            try:
                import fabio
                arr = fabio.open(path).data.astype(np.float64)
            except ImportError:
                raise HTTPException(400, detail="fabio required for .edf files")
        else:
            raise HTTPException(400, detail=f"Unsupported format: {ext}")

        if arr.ndim != 2:
            raise HTTPException(400, detail=f"Expected 2-D array, got shape {arr.shape}")

        arr = arr.astype(np.float64)
        b64 = base64.b64encode(arr.astype(np.float32).tobytes()).decode("ascii")

        # For cake mode, return axis info if available from processing_info
        x_axis = None
        y_axis = None
        if req.mode == "cake":
            # Try to find a processing_info sibling
            info_dir = os.path.dirname(path)
            for fname in os.listdir(info_dir) if os.path.isdir(info_dir) else []:
                if "processing_info" in fname.lower():
                    try:
                        with open(os.path.join(info_dir, fname), "r", encoding="utf-8", errors="replace") as fh:
                            info = _parse_processing_info(fh.read())
                        q_min, q_max = info.get("q_min"), info.get("q_max")
                        chi_min, chi_max = info.get("chi_min"), info.get("chi_max")
                        if q_min is not None and q_max is not None:
                            x_axis = np.linspace(q_min, q_max, arr.shape[1]).tolist()
                        if chi_min is not None and chi_max is not None:
                            y_axis = np.linspace(chi_min, chi_max, arr.shape[0]).tolist()
                        break
                    except Exception:
                        pass

        return {
            "imageBase64": b64,
            "shape": list(arr.shape),
            "xAxis": x_axis,
            "yAxis": y_axis,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))
