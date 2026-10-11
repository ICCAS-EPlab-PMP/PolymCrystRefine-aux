"""
qz band slice router — a standalone PolymCrystRefine module.

Post-processes the output of the GIWAXS fiber-integration merge module:
given the merged 2-D map (rows = out-of-plane / qz direction, cols =
in-plane) plus its two axes, the OOP range is sliced into parallel bands
("stripes") centred at every integer multiple of a chosen spacing ``qz``
(centres ``c = n * qz``, all integers n incl. 0 and negatives) with a
half-width ``interval`` — each band covers ``[c - interval, c + interval]``.

Every band yields ONE in-plane curve: the rows whose ``oop`` value falls
inside the band (endpoints included) are averaged per column with a finite
mean (``nanmean``), so peak positions can be compared between equal-qz
lamellar / layer-line orders. Export writes a CSV with one column per band.
"""

from __future__ import annotations

import io
import json
import math
import warnings
import zipfile
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from utils import _load_array, _save_array

router = APIRouter()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_BANDS = 512

DEFAULT_UNIT_IP = "qip_A^-1"
DEFAULT_UNIT_OOP = "qoop_A^-1"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AttachRequest(BaseModel):
    mergedFileId: str
    ipAxisFileId: str
    oopAxisFileId: str
    unitIp: Optional[str] = None      # None -> "qip_A^-1"
    unitOop: Optional[str] = None     # None -> "qoop_A^-1"
    sourceName: Optional[str] = None


class MapInfoResponse(BaseModel):
    sourceName: str
    mergedFileId: str
    ipAxisFileId: str
    oopAxisFileId: str
    unitIp: str
    unitOop: str
    ipRange: List[float]             # [min(ip[0],ip[-1]), max(...)]
    oopRange: List[float]
    nIp: int
    nOop: int
    ipAxis: List[float]              # downsampled preview axes (max side 224)
    oopAxis: List[float]
    preview: List[List[Optional[float]]]   # rows = oop, cols = ip; NaN -> null
    minIntensity: Optional[float] = None
    maxIntensity: Optional[float] = None


class RunRequest(BaseModel):
    mergedFileId: str
    ipAxisFileId: str
    oopAxisFileId: str
    qz: float = Field(..., gt=0)
    interval: float = Field(..., gt=0)
    maskLowerBound: Optional[float] = None   # pixels below are excluded everywhere


class BandItem(BaseModel):
    center: float
    qzLo: float
    qzHi: float
    nRows: int
    validFraction: float
    intensity: List[Optional[float]]   # NaN -> null


class RunResponse(BaseModel):
    qz: float
    interval: float
    maskLowerBound: Optional[float] = None   # echoed for the UI dirty check
    qx: List[float]                    # full in-plane axis (NOT downsampled)
    bands: List[BandItem]              # ascending by center


class ExportRequest(BaseModel):
    mergedFileId: str
    ipAxisFileId: str
    oopAxisFileId: str
    qz: float = Field(..., gt=0)
    interval: float = Field(..., gt=0)
    maskLowerBound: Optional[float] = None
    baseName: str = "qz_slice"
    unitIp: Optional[str] = None
    unitOop: Optional[str] = None
    sourceName: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _finite_stats(arr: np.ndarray):
    flat = arr.ravel()
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return None, None
    return float(flat.min()), float(flat.max())


def _parse_map(items, units=None):
    """Split uploaded arrays into (merged, ip, oop) by name, then by shape.

    ``items`` is a list of ``(lowercase_name, ndarray)`` pairs, ``units`` an
    optional dict carrying ``xAxisUnit`` / ``yAxisUnit`` from a
    ``processing_info.json``. Returns ``(merged, ip, oop, unit_ip, unit_oop)``
    with all three arrays as float64 and the axes validated against the map.
    """
    units = units or {}
    merged = ip = oop = None

    # Pass 1: name-based identification ("oop" is tested BEFORE "ip" so an
    # oop_* name can never fall through into the ip slot).
    for name, arr in items:
        if name.endswith("_giwaxs.npy"):
            merged = arr
        elif "oop" in name:
            oop = arr
        elif "ip" in name:
            ip = arr

    # Pass 2: shape-based fallback for unnamed uploads.
    if merged is None:
        for name, arr in items:
            if arr.ndim == 2:
                merged = arr
                break

    # Square grid + two same-length unnamed 1-D axes is ambiguous.
    if merged is not None and merged.ndim == 2 and merged.shape[0] == merged.shape[1] \
            and ip is None and oop is None:
        unnamed = [a for (n, a) in items
                   if a.ndim == 1 and "ip" not in n and "oop" not in n
                   and len(a) == merged.shape[0]]
        if len(unnamed) >= 2:
            raise HTTPException(
                400,
                detail="Square grid with two same-length 1-D arrays and no "
                       " recognisable names: name the axis files with 'ip' / 'oop' "
                       "(e.g. ip_array.npy / oop_array.npy).")

    if ip is None and merged is not None:
        for name, arr in items:
            if arr.ndim == 1 and len(arr) == merged.shape[1]:
                ip = arr
                break
    if oop is None and merged is not None:
        for name, arr in items:
            if arr.ndim == 1 and len(arr) == merged.shape[0]:
                oop = arr
                break

    if merged is None:
        raise HTTPException(400, detail="No merged map found among the uploads "
                                        "(expected a *_giwaxs.npy or any 2-D .npy).")

    merged = np.asarray(merged, dtype=np.float64)
    if merged.ndim != 2:
        raise HTTPException(400, detail=f"Merged map must be 2-D, got ndim={merged.ndim}.")
    if ip is None or len(np.ravel(ip)) != merged.shape[1]:
        raise HTTPException(
            400, detail=f"In-plane axis missing or length "
                        f"{0 if ip is None else len(np.ravel(ip))} != map columns "
                        f"{merged.shape[1]} (name it e.g. ip_array.npy).")
    if oop is None or len(np.ravel(oop)) != merged.shape[0]:
        raise HTTPException(
            400, detail=f"Out-of-plane axis missing or length "
                        f"{0 if oop is None else len(np.ravel(oop))} != map rows "
                        f"{merged.shape[0]} (name it e.g. oop_array.npy).")

    ip = np.ravel(np.asarray(ip, dtype=np.float64))
    oop = np.ravel(np.asarray(oop, dtype=np.float64))
    unit_ip = units.get("xAxisUnit") or DEFAULT_UNIT_IP
    unit_oop = units.get("yAxisUnit") or DEFAULT_UNIT_OOP
    if not isinstance(unit_ip, str):
        unit_ip = DEFAULT_UNIT_IP
    if not isinstance(unit_oop, str):
        unit_oop = DEFAULT_UNIT_OOP
    return merged, ip, oop, unit_ip, unit_oop


def _map_info(merged, ip, oop, fids, unit_ip, unit_oop, source_name) -> MapInfoResponse:
    """Build the shared map-info response (preview + stats + file-ids)."""
    preview, ip_ds, oop_ds = _strided_downsample(merged, ip, oop)
    vmin, vmax = _finite_stats(merged)
    return MapInfoResponse(
        sourceName=source_name,
        mergedFileId=fids[0],
        ipAxisFileId=fids[1],
        oopAxisFileId=fids[2],
        unitIp=unit_ip,
        unitOop=unit_oop,
        ipRange=[float(min(ip[0], ip[-1])), float(max(ip[0], ip[-1]))],
        oopRange=[float(min(oop[0], oop[-1])), float(max(oop[0], oop[-1]))],
        nIp=int(merged.shape[1]),
        nOop=int(merged.shape[0]),
        ipAxis=ip_ds.tolist(),
        oopAxis=oop_ds.tolist(),
        preview=_nan_to_none(preview.tolist()),
        minIntensity=vmin,
        maxIntensity=vmax,
    )


def _load_map(merged_fid: str, ip_fid: str, oop_fid: str):
    """Load + validate a stored merged map and its two axes (by file-id)."""
    merged = np.asarray(_load_array(merged_fid), dtype=np.float64)
    ip = np.ravel(np.asarray(_load_array(ip_fid), dtype=np.float64))
    oop = np.ravel(np.asarray(_load_array(oop_fid), dtype=np.float64))
    if merged.ndim != 2:
        raise HTTPException(400, detail=f"Merged map must be 2-D, got ndim={merged.ndim}.")
    if len(ip) != merged.shape[1]:
        raise HTTPException(400, detail=f"In-plane axis length {len(ip)} != map columns "
                                        f"{merged.shape[1]}.")
    if len(oop) != merged.shape[0]:
        raise HTTPException(400, detail=f"Out-of-plane axis length {len(oop)} != map rows "
                                        f"{merged.shape[0]}.")
    return merged, ip, oop


def _compute_bands(merged, ip, oop, qz: float, interval: float,
                   mask_lower_bound: Optional[float] = None) -> List[BandItem]:
    """Slice the OOP axis into qz-spaced bands; average each band's rows.

    Band centres are ``c = n * qz`` for every integer n (incl. 0 and
    negatives); each band covers ``[c - interval, c + interval]`` and keeps
    the rows whose oop value falls inside (endpoints included). The curve is
    the per-column finite mean (``nanmean``) over those rows — an all-NaN
    column stays NaN. ``mask_lower_bound`` additionally excludes pixels
    BELOW the bound from both the sum and the average (they count as no
    data). Bands are returned in ascending centre order.
    """
    oop = np.asarray(oop, dtype=np.float64)
    merged = np.asarray(merged, dtype=np.float64)
    oop_min, oop_max = float(oop.min()), float(oop.max())

    # Float-error-robust enumeration of the candidate band indices.
    n_min = math.ceil((oop_min - interval) / qz - 1e-9)
    n_max = math.floor((oop_max + interval) / qz + 1e-9)
    n_bands = n_max - n_min + 1
    if n_bands > MAX_BANDS:
        raise HTTPException(400, detail=f"qz spacing too small: would produce "
                                        f"{n_bands} bands (max {MAX_BANDS})")

    # Sort rows by oop so each band selects one contiguous row block even
    # when the stored axis is descending.
    order = np.argsort(oop)
    oop_s = oop[order]
    merged_s = merged[order, :]
    # Tolerance for endpoint inclusion (axis noise only; far smaller than
    # any realistic oop step).
    tol = 1e-9 * max(1.0, abs(oop_min), abs(oop_max), oop_max - oop_min)

    bands: List[BandItem] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # all-NaN columns are expected
        for n in range(n_min, n_max + 1):
            center = n * qz
            lo, hi = center - interval, center + interval
            if hi < oop_min - tol or lo > oop_max + tol:
                continue  # no overlap with the data range
            rows = np.where((oop_s >= lo - tol) & (oop_s <= hi + tol))[0]
            if rows.size < 1:
                continue
            block = merged_s[rows, :]
            valid = np.isfinite(block)
            if mask_lower_bound is not None:
                valid &= block >= mask_lower_bound
            curve = np.nanmean(np.where(valid, block, np.nan), axis=0)
            bands.append(BandItem(
                center=float(center),
                qzLo=float(lo),
                qzHi=float(hi),
                nRows=int(rows.size),
                validFraction=float(valid.mean()),
                intensity=_nan_to_none(curve.tolist()),
            ))
    return bands


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=MapInfoResponse)
def upload_files(files: List[UploadFile] = File(...)):
    """Upload a giwaxs_merge export ZIP and/or bare .npy map + axis files."""
    try:
        items: list = []
        units: dict = {}
        source_name = ""
        for f in files:
            data = f.file.read()
            if not source_name:
                source_name = f.filename or "upload"
            name = (f.filename or "").lower()
            if name.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for member in zf.namelist():
                        if member.endswith("/"):
                            continue  # directory entry
                        mname = member.lower()
                        if mname.endswith(".npy"):
                            arr = np.load(io.BytesIO(zf.read(member)), allow_pickle=False)
                            items.append((mname, arr))
                        elif mname.endswith("processing_info.json"):
                            try:
                                payload = json.loads(zf.read(member).decode("utf-8"))
                                if isinstance(payload, dict):
                                    units.update(payload)
                            except (ValueError, UnicodeDecodeError):
                                pass  # unreadable info file: keep defaults
                        # other members are ignored
            elif name.endswith(".npy"):
                arr = np.load(io.BytesIO(data), allow_pickle=False)
                items.append((name, arr))
            else:
                raise HTTPException(400, detail=f"Unsupported file type: {f.filename} "
                                                f"(expected .npy or .zip).")

        merged, ip, oop, unit_ip, unit_oop = _parse_map(items, units)
        merged_fid = _save_array(merged)
        ip_fid = _save_array(ip)
        oop_fid = _save_array(oop)
        return _map_info(merged, ip, oop, (merged_fid, ip_fid, oop_fid),
                         unit_ip, unit_oop, source_name)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/attach", response_model=MapInfoResponse)
def attach(req: AttachRequest):
    """Re-open an already-stored merged map + axes by file-id."""
    try:
        merged, ip, oop = _load_map(req.mergedFileId, req.ipAxisFileId, req.oopAxisFileId)
        unit_ip = req.unitIp or DEFAULT_UNIT_IP
        unit_oop = req.unitOop or DEFAULT_UNIT_OOP
        source = req.sourceName or "attached map"
        return _map_info(merged, ip, oop,
                         (req.mergedFileId, req.ipAxisFileId, req.oopAxisFileId),
                         unit_ip, unit_oop, source)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/run", response_model=RunResponse)
def run_slice(req: RunRequest):
    """Compute the qz-spaced band-averaged curves (one per band, ascending)."""
    try:
        merged, ip, oop = _load_map(req.mergedFileId, req.ipAxisFileId, req.oopAxisFileId)
        bands = _compute_bands(merged, ip, oop, req.qz, req.interval,
                               mask_lower_bound=req.maskLowerBound)
        return RunResponse(qz=req.qz, interval=req.interval,
                           maskLowerBound=req.maskLowerBound,
                           qx=ip.tolist(), bands=bands)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


def _export_lines(req: ExportRequest, sep: str, nan_text: str):
    """Shared CSV/TXT serialiser: recompute the bands, emit comment header +
    one column per band. Returns (text, header_first_column)."""
    merged, ip, oop = _load_map(req.mergedFileId, req.ipAxisFileId, req.oopAxisFileId)
    bands = _compute_bands(merged, ip, oop, req.qz, req.interval,
                           mask_lower_bound=req.maskLowerBound)
    unit_ip = req.unitIp or DEFAULT_UNIT_IP
    unit_oop = req.unitOop or DEFAULT_UNIT_OOP
    base = req.baseName or "qz_slice"

    def _fmt(v) -> str:
        return nan_text if v is None or not math.isfinite(v) else f"{v:.6g}"

    lines = [
        "# PolymCrystRefine qz band slice export",
        f"# source: {req.sourceName or base}",
        f"# qz spacing: {req.qz:.6g}",
        f"# interval (half width): {req.interval:.6g}",
        (f"# mask lower bound: {req.maskLowerBound:.6g}"
         if req.maskLowerBound is not None else "# mask lower bound: none"),
        f"# oop unit: {unit_oop} / ip unit: {unit_ip}",
        f"# bands: {len(bands)}",
        sep.join(["qip"] + [f"I[{b.qzLo:.6g},{b.qzHi:.6g}]" for b in bands]),
    ]
    columns = [b.intensity for b in bands]
    for row in zip(ip.tolist(), *columns):
        lines.append(sep.join(_fmt(v) for v in row))

    return "\n".join(lines) + "\n", base


@router.post("/export-csv")
def export_csv(req: ExportRequest):
    """Recompute the bands server-side and emit a labelled CSV download."""
    try:
        text, base = _export_lines(req, sep=",", nan_text="")
        return StreamingResponse(
            io.BytesIO(text.encode("utf-8")),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{base}_qz_slice.csv"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/export-txt")
def export_txt(req: ExportRequest):
    """Whitespace-column TXT variant (qip first column), for the lab's 1-D
    curve pipelines that read `#`-commented whitespace tables."""
    try:
        text, base = _export_lines(req, sep=" ", nan_text="nan")
        return StreamingResponse(
            io.BytesIO(text.encode("utf-8")),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{base}_qz_slice.txt"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))
