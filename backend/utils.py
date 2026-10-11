"""
Shared utility functions for the PolymCrystRefine backend.

Centralises file I/O helpers, path-traversal protection, and
processing-info parsing so that every router imports from one place.
"""

from __future__ import annotations

import io
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from fastapi import HTTPException

from config import OUTPUT_DIR, UPLOAD_DIR


# ---------------------------------------------------------------------------
# Path traversal protection  (M2)
# ---------------------------------------------------------------------------

def _file_path(file_id: str) -> str:
    """Resolve a file-id to an absolute path inside UPLOAD_DIR or OUTPUT_DIR.

    Raises 403 if a path-traversal attempt is detected, 404 if not found.
    """
    real_upload = os.path.realpath(UPLOAD_DIR)
    real_output = os.path.realpath(OUTPUT_DIR)
    for base in (UPLOAD_DIR, OUTPUT_DIR):
        real = os.path.realpath(os.path.join(base, file_id))
        # Containment needs a path-separator boundary: a sibling directory
        # such as ``<base>-evil`` would pass a bare startswith check.
        contained = any(
            real == b or real.startswith(b + os.sep)
            for b in (real_upload, real_output)
        )
        if not contained:
            raise HTTPException(403, detail="Path traversal detected")
        if os.path.isfile(real):
            return real
    raise HTTPException(404, detail=f"File not found: {file_id}")


# ---------------------------------------------------------------------------
# File save helpers
# ---------------------------------------------------------------------------

def _save_upload(data: bytes, suffix: str = "") -> str:
    """Save raw bytes into UPLOAD_DIR and return the generated file-id."""
    fid = uuid.uuid4().hex[:12] + suffix
    # Defence-in-depth: fid is server-generated, but suffix is a caller
    # argument — refuse non-plain names and require the resolved location
    # to stay inside the storage directory before writing.
    if not fid or os.path.basename(fid) != fid:
        raise HTTPException(400, detail="Invalid file name")
    real = os.path.realpath(os.path.join(UPLOAD_DIR, fid))
    real_base = os.path.realpath(UPLOAD_DIR)
    if real != real_base and not real.startswith(real_base + os.sep):
        raise HTTPException(400, detail="Invalid file name")
    os.makedirs(os.path.dirname(real) or ".", exist_ok=True)
    Path(real).write_bytes(data)
    return fid


def _save_output(data: bytes, suffix: str = "") -> str:
    """Save raw bytes into OUTPUT_DIR and return the generated file-id."""
    fid = uuid.uuid4().hex[:12] + suffix
    # Defence-in-depth: fid is server-generated, but suffix is a caller
    # argument — refuse non-plain names and require the resolved location
    # to stay inside the storage directory before writing.
    if not fid or os.path.basename(fid) != fid:
        raise HTTPException(400, detail="Invalid file name")
    real = os.path.realpath(os.path.join(OUTPUT_DIR, fid))
    real_base = os.path.realpath(OUTPUT_DIR)
    if real != real_base and not real.startswith(real_base + os.sep):
        raise HTTPException(400, detail="Invalid file name")
    os.makedirs(os.path.dirname(real) or ".", exist_ok=True)
    Path(real).write_bytes(data)
    return fid


def _save_array(arr: np.ndarray) -> str:
    """Serialise a numpy array to .npy bytes, save in OUTPUT_DIR, return file-id."""
    buf = io.BytesIO()
    np.save(buf, arr)
    return _save_output(buf.getvalue(), suffix=".npy")


# ---------------------------------------------------------------------------
# Array loader
# ---------------------------------------------------------------------------

def _load_array(file_id: str) -> np.ndarray:
    """Load a numpy array from a .npy file-id."""
    p = _file_path(file_id)
    return np.load(p, allow_pickle=True)


# ---------------------------------------------------------------------------
# Processing-info parser  (C8 helper)
# ---------------------------------------------------------------------------

_PROCESSING_INFO_Q_RE = re.compile(
    r"X-axis.*?range:\s*([-\d.eE+]+)\s*to\s*([-\d.eE+]+)", re.IGNORECASE
)
_PROCESSING_INFO_CHI_RE = re.compile(
    r"Y-axis.*?range.*?:\s*([-\d.eE+]+)\s*to\s*([-\d.eE+]+)", re.IGNORECASE
)
_PROCESSING_INFO_PTS_RE = re.compile(
    r"Integration points.*?:.*?(\d+)\s*x\s*(\d+)", re.IGNORECASE
)


def _parse_processing_info(info_text: str) -> Dict[str, Any]:
    """Parse a processing_info file (JSON or legacy text) into a dict.

    JSON format (current standard export)::

        {"xAxisRange": [0.5, 25.0], "yAxisRangeDeg": [-180.0, 180.0],
         "integrationPoints": {"radial": 1000, "azimuthal": 360}}

    Legacy text format (still accepted)::

        X-axis (q_A^-1) range: 0.5 to 25.0
        Y-axis (chi) range (degrees): -180.0 to 180.0
        Integration points: 1000 x 360

    Returns a dict with keys q_min, q_max, chi_min, chi_max, npt_rad,
    npt_azim (all optional).
    """
    info: Dict[str, Any] = {}
    stripped = info_text.strip()

    # JSON first (current standard export format).
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            data = None
        if isinstance(data, dict):
            xr = data.get("xAxisRange")
            if isinstance(xr, (list, tuple)) and len(xr) == 2:
                info["q_min"], info["q_max"] = float(xr[0]), float(xr[1])
            yr = data.get("yAxisRangeDeg")
            if isinstance(yr, (list, tuple)) and len(yr) == 2:
                info["chi_min"], info["chi_max"] = float(yr[0]), float(yr[1])
            pts = data.get("integrationPoints")
            if isinstance(pts, dict):
                if pts.get("radial") is not None:
                    info["npt_rad"] = int(pts["radial"])
                if pts.get("azimuthal") is not None:
                    info["npt_azim"] = int(pts["azimuthal"])
            # Capture the x-axis unit so callers can convert nm^-1 -> Å^-1.
            unit = data.get("xAxisUnit") or data.get("unit")
            if isinstance(unit, str):
                info["x_axis_unit"] = unit
            return info

    # Legacy text format (regex).
    q_match = _PROCESSING_INFO_Q_RE.search(info_text)
    if q_match:
        info["q_min"] = float(q_match.group(1))
        info["q_max"] = float(q_match.group(2))

    chi_match = _PROCESSING_INFO_CHI_RE.search(info_text)
    if chi_match:
        info["chi_min"] = float(chi_match.group(1))
        info["chi_max"] = float(chi_match.group(2))

    pt_match = _PROCESSING_INFO_PTS_RE.search(info_text)
    if pt_match:
        info["npt_rad"] = int(pt_match.group(1))
        info["npt_azim"] = int(pt_match.group(2))

    return info


def _identify_q_unit(unit: Optional[str]) -> Optional[str]:
    """Classify a q-axis unit string as ``'nanometer'`` or ``'angstrom'``.

    Handles the spellings used by pyFAI / the 2D-integration export *and* the
    plain forms the user supplies in sidecar files:

      nm⁻¹ family:  q_nm^-1, nm^-1, nm-1, 1/nm, nanometer, nanometre
      Å⁻¹ family:  q_A^-1, A^-1, A-1, 1/A, Å^-1, angstrom

    Returns ``None`` when the unit is absent or unrecognised.
    """
    if not isinstance(unit, str) or not unit.strip():
        return None
    # Normalise: lowercase, drop spaces and underscores (so q_A^-1 -> qa^-1).
    u = unit.lower().replace(" ", "").replace("_", "")
    if "nm" in u or "nanomet" in u:
        return "nanometer"
    if "å" in u or "angstrom" in u:
        return "angstrom"
    if any(p in u for p in ("a^-1", "a-1", "1/a", "/a")):
        return "angstrom"
    return None


def _q_range_to_angstrom(q_range: Tuple[float, float], unit: Optional[str]) -> Tuple[float, float]:
    """Return a q range expressed in Å^-1.

    The 2D integration module exports q in nm^-1 by default
    (``xAxisUnit: q_nm^-1``); divide by 10 to present Å^-1 to the UI. Ranges
    already in Å^-1 (or with an unrecognised / absent unit) are returned
    unchanged.
    """
    lo, hi = float(q_range[0]), float(q_range[1])
    if _identify_q_unit(unit) == "nanometer":
        return lo / 10.0, hi / 10.0
    return lo, hi
