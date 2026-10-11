"""
LMP Force Field Extractor router.

Integrated from ``reference/function4/lmptrans.py``.  Parses a PDB/MOL
structure file together with a LAMMPS data file, validates their
correspondence, lets the user select important atoms, and extracts force
field parameters (mass, pair/bond/angle/dihedral/improper coeffs) with
atom-ID remapping into a CSV.
"""

from __future__ import annotations

import io
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from utils import _save_upload

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AtomInfo(BaseModel):
    """One atom from the structure file (PDB/MOL)."""
    index: int = Field(..., description="1-based atom index in structure")
    element: str = Field(..., description="Element symbol")
    x: float
    y: float
    z: float
    residue: str = ""
    is_hydrogen: bool = False


class ParseStructureResponse(BaseModel):
    atoms: List[AtomInfo]
    file_id: str
    total_atoms: int
    formula: str = ""


class LmpAtomInfo(BaseModel):
    """One atom from the LAMMPS data file."""
    atom_id: str
    atom_type: int
    element: str = ""


class LmpSection(BaseModel):
    name: str
    lines: List[str]


class ParseLmpResponse(BaseModel):
    atoms: List[LmpAtomInfo]
    sections: Dict[str, List[str]]
    file_id: str
    total_atoms: int
    atom_style: str = "atomic"


class TypeElementInfo(BaseModel):
    """One LAMMPS atom TYPE with its mass and the element inferred from it."""
    type_id: int
    mass: float
    element: str


class ElementDiffRow(BaseModel):
    """Per-element count comparison between structure and LAMMPS data."""
    element: str
    struct: int
    lmp: int
    match: bool


class ValidationReport(BaseModel):
    ok: bool
    message: str
    structure_atom_count: int
    lmp_atom_count: int
    element_comparison: Dict[str, Dict[str, Union[int, str]]]  # {element: {struct: n, lmp: n|"? (types only)"}}
    type_elements: List[TypeElementInfo] = []
    struct_formula: str = ""
    lmp_formula: str = ""
    element_diff: List[ElementDiffRow] = []
    warnings: List[str] = []


class ExtractRequest(BaseModel):
    """Explicit old_atom_id -> new_atom_id mapping (both as strings) + file IDs.

    Mirrors the reference ``lmptrans.py`` workflow: the user supplies an exact
    ID remapping column-by-column, NOT a selection + auto-renumber. Atoms whose
    ``new`` value is blank are simply not emitted.

    Periodicity is carried as an **integer** period count (a bond/interaction can
    cross >=2 periodic images). ``period_map`` maps an old_atom_id to the user's
    chosen period count; it overrides the file-detected period for that atom
    when present, otherwise the period parsed from the LAMMPS data file's ``#``
    markers is used. Output writes ``#N`` (e.g. ``3#1``, ``3#2``); period 0
    means non-periodic (no marker).
    """
    structure_file_id: str
    lmp_file_id: str
    id_map: Dict[str, str] = Field(
        ...,
        description="Mapping old_atom_id -> new_atom_id (both as strings). Blank new = skipped.",
    )
    period_map: Dict[str, int] = Field(
        default_factory=dict,
        description="Optional override: old_atom_id -> period count (integer >=1).",
    )


class ExtractResponse(BaseModel):
    csv_text: str
    record_count: int
    summary: str


# ---------------------------------------------------------------------------
# Structure parsing (XYZ / MOL V2000 / SDF / PDB native; CIF via pymatgen)
# ---------------------------------------------------------------------------
#
# Native parsers — no openbabel. pymatgen's ``Molecule.from_str`` requires the
# openbabel Python bindings for mol/sdf/pdb/xyz (rarely installed; its absence
# made EVERY structure upload 500), and its ``Structure`` class does not accept
# mol/pdb at all. So we parse the common molecular formats ourselves and only
# fall back to pymatgen ``Structure`` for CIF (supported natively, no openbabel).

_ELEM_FROM_ATOMIC_NUM = {
    1: "H", 2: "He", 3: "Li", 4: "Be", 5: "B", 6: "C", 7: "N", 8: "O",
    9: "F", 10: "Ne", 11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P",
    16: "S", 17: "Cl", 18: "Ar", 19: "K", 20: "Ca", 21: "Sc", 22: "Ti",
    23: "V", 24: "Cr", 25: "Mn", 26: "Fe", 27: "Co", 28: "Ni", 29: "Cu",
    30: "Zn", 31: "Ga", 32: "Ge", 33: "As", 34: "Se", 35: "Br", 36: "Kr",
    37: "Rb", 38: "Sr", 39: "Y", 40: "Zr", 41: "Nb", 42: "Mo", 43: "Tc",
    44: "Ru", 45: "Rh", 46: "Pd", 47: "Ag", 48: "Cd", 49: "In", 50: "Sn",
    51: "Sb", 52: "Te", 53: "I", 54: "Xe", 55: "Cs", 56: "Ba", 57: "La",
    58: "Ce", 59: "Pr", 60: "Nd", 61: "Pm", 62: "Sm", 63: "Eu", 64: "Gd",
    65: "Tb", 66: "Dy", 67: "Ho", 68: "Er", 69: "Tm", 70: "Yb", 71: "Lu",
    72: "Hf", 73: "Ta", 74: "W", 75: "Re", 76: "Os", 77: "Ir", 78: "Pt",
    79: "Au", 80: "Hg", 81: "Tl", 82: "Pb", 83: "Bi", 84: "Po", 85: "At",
    86: "Rn", 87: "Fr", 88: "Ra", 89: "Ac", 90: "Th", 91: "Pa", 92: "U",
}


_ELEMENT_SYMBOLS = set(_ELEM_FROM_ATOMIC_NUM.values())


# Standard atomic masses (g/mol) for elements common in molecular / polymer
# force fields. LAMMPS only stores a numeric mass per atom TYPE (not a symbol),
# so we infer each type's element by matching its mass to the nearest entry.
_ATOMIC_MASS_TO_ELEM = {
    "H": 1.008, "B": 10.811, "C": 12.011, "N": 14.007, "O": 15.999,
    "F": 18.998, "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.086,
    "P": 30.974, "S": 32.060, "Cl": 35.450, "K": 39.098, "Ca": 40.078,
    "Ti": 47.867, "Cr": 51.996, "Mn": 54.938, "Fe": 55.845, "Co": 58.933,
    "Ni": 58.693, "Cu": 63.546, "Zn": 65.380, "Br": 79.904, "Ag": 107.868,
    "Sn": 118.710, "I": 126.904, "Ba": 137.327, "Au": 196.967,
}


def _mass_to_element(mass) -> str:
    """Nearest element symbol for a numeric atomic mass, or ``'?'`` if the
    closest match is more than 5% away (i.e. no recognised element matches)."""
    try:
        m = float(mass)
    except (TypeError, ValueError):
        return "?"
    best_elem, best_diff = "?", None
    for elem, ref in _ATOMIC_MASS_TO_ELEM.items():
        diff = abs(m - ref)
        if best_diff is None or diff < best_diff:
            best_elem, best_diff = elem, diff
    if best_diff is None or best_diff > 0.05 * m:
        return "?"
    return best_elem


def _infer_type_elements(
    sections: Dict[str, List[str]],
) -> Dict[int, Tuple[float, str]]:
    """Map each LAMMPS atom type -> ``(mass, inferred_element)`` from Masses."""
    result: Dict[int, Tuple[float, str]] = {}
    for line in sections.get("Masses", []):
        parts = line.split()
        try:
            t_id = int(parts[0])
            mass = float(parts[1])
        except (ValueError, IndexError):
            continue
        result[t_id] = (mass, _mass_to_element(mass))
    return result


def _normalize_element(token: str) -> str:
    """Normalise a raw element token ('CL', 'c1', 'C12') to 'C' / 'Cl'."""
    token = (token or "").strip()
    m = re.match(r"[A-Za-z]{1,3}", token)
    if not m:
        return token.capitalize() if token else ""
    e = m.group(0)
    return e[0].upper() + e[1:].lower()


def _make_atom(idx: int, elem: str, x: float, y: float, z: float) -> AtomInfo:
    return AtomInfo(
        index=idx,
        element=elem,
        x=float(x), y=float(y), z=float(z),
        is_hydrogen=(elem == "H"),
    )


def _parse_xyz(text: str) -> List[AtomInfo]:
    """Parse an XYZ file robustly.

    Handles: UTF-8 BOM, a missing comment line, atomic-number elements
    (``6`` → C), Fortran ``D``/``d`` exponent notation, and extended-XYZ
    keyword lines — by scanning for lines that look like ``elem x y z`` rather
    than trusting a rigid count/comment/atoms layout (which previously rejected
    perfectly valid XYZ files).
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.replace("\r", "").splitlines()

    # First non-blank line is usually the atom count.
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    n_expected: Optional[int] = None
    start = i
    if i < len(lines):
        try:
            n_expected = int(lines[i].split()[0])
            start = i + 1  # skip the count line; any comment line is skipped by the regex below
        except (ValueError, IndexError):
            n_expected = None
            start = i

    # An atom line: an element symbol (1-3 letters) OR an atomic number, then
    # three numbers (scientific / Fortran-D notation allowed).
    atom_re = re.compile(
        r"^\s*([A-Za-z]{1,3}|\d{1,3})\s+"
        r"([-+]?\d*\.?\d+(?:[eEdD][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[eEdD][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[eEdD][-+]?\d+)?)"
    )

    def _f(s: str) -> float:
        return float(s.replace("D", "E").replace("d", "e"))

    def _elem(tok: str) -> str:
        if tok.isdigit():
            return _ELEM_FROM_ATOMIC_NUM.get(int(tok), tok)
        return _normalize_element(tok)

    atoms: List[AtomInfo] = []
    for ln in lines[start:]:
        m = atom_re.match(ln)
        if not m:
            continue
        try:
            atoms.append(_make_atom(
                len(atoms) + 1, _elem(m.group(1)),
                _f(m.group(2)), _f(m.group(3)), _f(m.group(4)),
            ))
        except ValueError:
            continue
        if n_expected is not None and len(atoms) >= n_expected:
            break
    return atoms


def _parse_mol_v2000(text: str) -> List[AtomInfo]:
    """Parse the first molecule of an MDL MOL / SDF V2000 file."""
    lines = text.splitlines()
    if len(lines) < 4:
        return []
    # Counts line is the 4th record (after name / program / comment).
    try:
        n_atoms = int(lines[3].split()[0])
    except (ValueError, IndexError):
        return []
    if n_atoms <= 0:
        return []

    def atom_from_line(line: str):
        # Most tools space-separate the atom block: x y z elem ...
        parts = line.split()
        if len(parts) >= 4:
            try:
                x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                elem = _normalize_element(parts[3])
                if elem in _ELEMENT_SYMBOLS:
                    return x, y, z, elem
            except ValueError:
                pass
        # Fixed-width fallback: x[0:10] y[10:20] z[20:30] elem[30:34].
        try:
            x = float(line[0:10]); y = float(line[10:20]); z = float(line[20:30])
            elem = _normalize_element(line[30:34].strip())
            if elem in _ELEMENT_SYMBOLS:
                return x, y, z, elem
        except (ValueError, IndexError):
            pass
        return None

    atoms: List[AtomInfo] = []
    i = 4
    while i < len(lines) and len(atoms) < n_atoms:
        rec = atom_from_line(lines[i])
        if rec is None:
            break  # left the atom block (bonds / blank / SDF '$$$$')
        x, y, z, elem = rec
        atoms.append(_make_atom(len(atoms) + 1, elem, x, y, z))
        i += 1
    return atoms


def _looks_like_pdb(text: str) -> bool:
    head = text.splitlines()[:200]
    return any(ln[:6].strip().upper() in ("ATOM", "HETATM") for ln in head)


def _looks_like_xyz(text: str) -> bool:
    """Return True if the file content looks like an XYZ file.

    Scans for lines that match the typical ``element x y z`` pattern.
    At least 3 such lines are required so that PDB / MOL / CIF content
    is not accidentally classified as XYZ.
    """
    atom_re = re.compile(
        r"^\s*([A-Za-z]{1,3}|\d{1,3})\s+"
        r"([-+]?\d*\.?\d+(?:[eEdD][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[eEdD][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[eEdD][-+]?\d+)?)"
    )
    atom_like = 0
    for ln in text.splitlines():
        if atom_re.match(ln):
            atom_like += 1
            if atom_like >= 3:
                return True
    return False


def _parse_pdb(text: str) -> List[AtomInfo]:
    """Parse ATOM / HETATM records from a PDB file."""
    atoms: List[AtomInfo] = []
    for line in text.splitlines():
        if line[:6].strip().upper() not in ("ATOM", "HETATM"):
            continue
        # Coordinates: fixed columns 31-54, fallback to whitespace split.
        try:
            x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
        except (ValueError, IndexError):
            parts = line.split()
            try:
                x = float(parts[6]); y = float(parts[7]); z = float(parts[8])
            except (ValueError, IndexError):
                continue
        # Element: authoritative column 77-78 first; else the atom-name field,
        # whose element symbol is right-justified in cols 13-14 (col 13 blank ⇒
        # single-letter element in col 14) — so alpha-carbon "CA" → C, not Ca.
        elem = ""
        if len(line) >= 78:
            cand = _normalize_element(line[76:78])
            if cand in _ELEMENT_SYMBOLS:
                elem = cand
        if not elem and len(line) >= 14:
            c13, c14 = line[12], line[13]
            if c13.strip() == "" and c14.isalpha():
                elem = _normalize_element(c14)
            elif c13.isalpha():
                elem = _normalize_element(line[12:14])
        if not elem:
            name = line[12:16].strip() if len(line) >= 16 else ""
            m = re.match(r"[A-Za-z]{1,2}", name)
            elem = _normalize_element(m.group(0)) if m else ""
        atoms.append(_make_atom(len(atoms) + 1, elem, x, y, z))
    return atoms


def _parse_cif(text: str) -> List[AtomInfo]:
    """Parse a CIF via pymatgen Structure (native, no openbabel needed)."""
    from pymatgen.core import Structure
    struct = Structure.from_str(text, fmt="cif")
    atoms: List[AtomInfo] = []
    for i, site in enumerate(struct.sites):
        elem = str(site.specie)
        atoms.append(AtomInfo(
            index=i + 1, element=elem,
            x=float(site.x), y=float(site.y), z=float(site.z),
            is_hydrogen=(elem == "H"),
        ))
    return atoms


def _gro_atom_from_line(line: str):
    """Parse one fixed-width GROMACS .gro atom record -> (xA, yA, zA, element).

    GROMACS writes coordinates with %8.3f (8-wide, nm), starting at column 20 -
    NOT the 5-wide columns of the theoretical spec - so we read
    [20:28]/[28:36]/[36:44] first and fall back to whitespace splitting for
    files that pack fields differently. Coordinates are converted nm->A to
    match PDB/MOL/XYZ. The element comes from the leading letters of the atom
    name (C1->C, CL1->Cl), since .gro has no dedicated element column.
    """
    atomname = line[10:15].strip() if len(line) >= 15 else ""
    x = y = z = None
    if len(line) >= 44:
        try:
            x = float(line[20:28]); y = float(line[28:36]); z = float(line[36:44])
        except ValueError:
            x = y = z = None
    if x is None:
        parts = line.split()
        # resnr resname atomname atomnr x y z [vx vy vz]
        if len(parts) >= 7:
            try:
                atomname = atomname or parts[2]
                x = float(parts[4]); y = float(parts[5]); z = float(parts[6])
            except ValueError:
                return None
        else:
            return None
    m = re.match(r"[A-Za-z]+", atomname)
    elem = _normalize_element(m.group(0)) if m else ""
    if elem and elem not in _ELEMENT_SYMBOLS:
        elem = _normalize_element(elem[0])  # unknown 2-letter -> first letter
    return (x * 10.0, y * 10.0, z * 10.0, elem)  # nm -> Angstrom


def _parse_gro(text: str) -> List[AtomInfo]:
    """Parse a GROMACS .gro coordinate file (native, no openbabel needed).

    Layout: title / atom-count / N atom records / box line. Atom index is the
    1-based enumeration (the file's atom-number field overflows past 99,999
    atoms, so it is not trustworthy).
    """
    lines = text.replace("\r", "").splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():  # skip blanks -> title
        i += 1
    i += 1
    while i < len(lines) and not lines[i].strip():  # -> count line
        i += 1
    if i >= len(lines):
        return []
    try:
        n_atoms = int(lines[i].split()[0])
    except (ValueError, IndexError):
        return []
    i += 1

    atoms: List[AtomInfo] = []
    while i < len(lines) and len(atoms) < n_atoms:
        ln = lines[i]
        i += 1
        if not ln.strip():
            continue
        rec = _gro_atom_from_line(ln)
        if rec is None:
            break  # reached the box line / end of atom block
        x, y, z, elem = rec
        atoms.append(_make_atom(len(atoms) + 1, elem, x, y, z))
    return atoms


def _looks_like_gro(text: str) -> bool:
    """Heuristic: 2nd non-blank line is a positive integer (atom count) and the
    following line carries decimal coordinates in the coordinate region."""
    nonblank = [ln for ln in text.replace("\r", "").splitlines() if ln.strip()]
    if len(nonblank) < 3:
        return False
    try:
        n = int(nonblank[1].split()[0])
    except (ValueError, IndexError):
        return False
    if n <= 0:
        return False
    atom_line = nonblank[2]
    return len(atom_line) >= 35 and "." in atom_line[20:]


def _parse_structure_file(content: bytes, filename: str) -> List[AtomInfo]:
    """Parse an XYZ / MOL / SDF / PDB / GRO / CIF structure file into an atom list.

    The format is detected from the extension AND the content. The upload is
    stored with a ``.struct`` suffix, so when ``/validate`` re-parses from that
    path the original extension is lost — content sniffing covers that case.
    Native parsers avoid the openbabel dependency that pymatgen's Molecule
    reader requires (and which previously 500'd every structure upload).
    """
    text = content.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    ext = (filename or "").lower().rsplit(".", 1)[-1] if "." in (filename or "") else ""
    stripped = text.lstrip()

    # Ordered attempts — return the first that yields atoms.
    attempts: List = []
    if ext == "cif" or stripped.startswith(("data_", "loop_")):
        attempts.append(_parse_cif)
    if ext == "gro" or _looks_like_gro(text):
        attempts.append(_parse_gro)
    if ext in ("mol", "sdf") or "V2000" in text or "V3000" in text:
        attempts.append(_parse_mol_v2000)
    if ext == "pdb" or _looks_like_pdb(text):
        attempts.append(_parse_pdb)
    if ext in ("xyz", "") or _looks_like_xyz(text):
        attempts.append(_parse_xyz)
    # Last-resort sweep across every native parser.
    attempts += [p for p in (_parse_cif, _parse_gro, _parse_mol_v2000, _parse_pdb, _parse_xyz)
                 if p not in attempts]

    for fn in attempts:
        try:
            atoms = fn(text)
            if atoms:
                return atoms
        except Exception:
            continue
    raise ValueError(
        "Could not parse structure file. Supported formats: "
        "XYZ, MOL/SDF (V2000), PDB, GRO, CIF."
    )


# ---------------------------------------------------------------------------
# LAMMPS data file parsing (ported from reference/function4/lmptrans.py)
# ---------------------------------------------------------------------------

LMP_SECTION_NAMES = [
    "Masses", "Pair Coeffs", "Bond Coeffs", "Angle Coeffs",
    "Dihedral Coeffs", "Improper Coeffs",
    "Atoms", "Bonds", "Angles", "Dihedrals", "Impropers",
]


def _parse_lammps_data(text: str) -> Dict[str, List[str]]:
    """Parse a LAMMPS data file into named sections."""
    lines = [line.strip() for line in text.splitlines()]
    sections: Dict[str, List[str]] = {}
    current_section = None

    for line in lines:
        if line.startswith("#"):
            continue
        header_candidate = line.split("#")[0].strip()
        if header_candidate in LMP_SECTION_NAMES:
            current_section = header_candidate
            sections[current_section] = []
            continue
        if current_section and line:
            sections[current_section].append(line)

    return sections


def _detect_atom_style(atom_lines: List[str]) -> str:
    """Detect 'atomic' vs 'full' atom style from first atom line."""
    if not atom_lines:
        return "atomic"
    parts = atom_lines[0].split()
    # "full" style: id molecule-id type charge x y z ...
    # "atomic" style: id type x y z ...
    if len(parts) >= 3 and parts[2].isdigit() and "." not in parts[2]:
        return "full"
    return "atomic"


def _parse_lmp_atoms(sections: Dict[str, List[str]]) -> List[LmpAtomInfo]:
    """Extract atom list from LAMMPS data."""
    if "Atoms" not in sections:
        return []
    lines = sections["Atoms"]
    atom_style = _detect_atom_style(lines)
    type_col = 2 if atom_style == "full" else 1

    atoms = []
    for line in lines:
        parts = line.split()
        if len(parts) < type_col + 1:
            continue
        try:
            atom_id = parts[0]
            atom_type = int(parts[type_col])
            atoms.append(LmpAtomInfo(
                atom_id=atom_id,
                atom_type=atom_type,
            ))
        except (ValueError, IndexError):
            continue
    return atoms


def _parse_lmp_coeffs(sections: Dict[str, List[str]]) -> Dict[str, Dict[int, str]]:
    """Pre-parse force field coefficients from LAMMPS sections."""
    coeff_db: Dict[str, Dict[int, str]] = {
        "Masses": {},
        "Pair Coeffs": {},
        "Bond Coeffs": {},
        "Angle Coeffs": {},
        "Dihedral Coeffs": {},
        "Improper Coeffs": {},
    }
    for sec_name, db in coeff_db.items():
        if sec_name not in sections:
            continue
        for line in sections[sec_name]:
            parts = line.split()
            try:
                t_id = int(parts[0])
                params = " ".join(parts[1:])
                db[t_id] = params
            except ValueError:
                continue
    return coeff_db


# ---------------------------------------------------------------------------
# Extraction engine (adapted from LammpsMappedExtractor)
# ---------------------------------------------------------------------------

_PERIOD_TOKEN_RE = re.compile(r"^(\d+)(?:#(\d+))?(#*)$")


def _split_atom_token(tok: str) -> Tuple[str, int]:
    """Split a topology atom token into ``(atom_id, period_count)``.

    Handles every periodic notation found in LAMMPS data files: ``3`` ->
    (3, 0); ``3#`` -> (3, 1); ``3##`` -> (3, 2); ``3#2`` -> (3, 2). The
    integer form ``#N`` previously broke the old ``replace('#', '')`` parser,
    which read ``3#2`` as atom id ``32``; this fixes that.
    """
    m = _PERIOD_TOKEN_RE.match(tok or "")
    if not m:
        lead = re.match(r"\d+", tok or "")
        aid = lead.group(0) if lead else (tok or "")
        return aid, (1 if "#" in (tok or "") else 0)
    atom_id = m.group(1)
    period = int(m.group(2)) if m.group(2) else len(m.group(3))
    return atom_id, period


def _run_extraction(
    sections: Dict[str, List[str]],
    id_map: Dict[str, str],
    period_map: Optional[Dict[str, int]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Extract force field records for the explicit old_id -> new_id mapping.

    Mirrors reference ``lmptrans.py``: the caller supplies the exact remapping
    (NO sorting / auto-renumber). ``id_map`` keys/values are strings. Atoms not
    in ``id_map`` are dropped. Topology records whose members are all mapped are
    emitted.

    Periodicity is an integer count (a bond can cross >=2 periodic images).
    Each topology atom token is parsed with ``_split_atom_token`` to get its
    file-detected period; ``period_map`` (old_atom_id -> int) overrides that
    when present. Output writes ``#N`` for period >=1, no marker for 0. Records
    whose members are ALL periodic (period > 0) are skipped as periodic-image
    duplicates; records with some periodic members are kept and counted.

    Returns ``(records, stats)`` where ``stats`` reports how many periodic
    topology records were kept vs skipped, so the user can see periodicity.
    """

    coeff_db = _parse_lmp_coeffs(sections)
    selected_old_ids = set(id_map.keys())
    period_map = period_map or {}

    stats = {"periodic_kept": 0, "periodic_skipped": 0}

    # Detect atom style
    atom_lines = sections.get("Atoms", [])
    atom_style = _detect_atom_style(atom_lines)
    type_col = 2 if atom_style == "full" else 1

    records: List[Dict[str, Any]] = []

    def _period_suffix(clean_id: str, file_period: int) -> str:
        # period_map (user override) wins when present, else the file-detected
        # period. Output N copies of "#" for period >=1; nothing for 0.
        period = period_map.get(clean_id, file_period)
        try:
            period = int(period)
        except (TypeError, ValueError):
            period = file_period
        return "#" * period if period >= 1 else ""

    # ---- Process Atoms ----
    if "Atoms" in sections:
        for line in sections["Atoms"]:
            parts = line.split()
            if len(parts) < type_col + 1:
                continue
            try:
                old_id_str = parts[0]
                if old_id_str in selected_old_ids:
                    new_id = id_map[old_id_str]
                    new_id_with_period = f"{new_id}{_period_suffix(old_id_str, 0)}"
                    atom_type = int(parts[type_col])
                    mass_val = coeff_db["Masses"].get(atom_type, "N/A")
                    pair_val = coeff_db["Pair Coeffs"].get(atom_type, "N/A")
                    records.append({
                        "Category": "Atom",
                        "New_ID": new_id,
                        "Old_ID": old_id_str,
                        "Type_ID": atom_type,
                        "Related_New_Atoms": new_id_with_period,
                        "Parameter_1 (Mass)": mass_val,
                        "Parameter_2 (Coeffs)": pair_val,
                    })
            except (ValueError, IndexError):
                continue

    # ---- Process Topology ----
    topo_configs = [
        ("Bonds", "Bond", "Bond Coeffs", 4, [2, 3]),
        ("Angles", "Angle", "Angle Coeffs", 5, [2, 3, 4]),
        ("Dihedrals", "Dihedral", "Dihedral Coeffs", 6, [2, 3, 4, 5]),
        ("Impropers", "Improper", "Improper Coeffs", 6, [2, 3, 4, 5]),
    ]

    for sec_name, cat_name, coeff_key, min_cols, atom_indices in topo_configs:
        if sec_name not in sections:
            continue
        new_topo_counter = 1
        for line in sections[sec_name]:
            parts = line.split()
            if len(parts) < min_cols:
                continue
            try:
                parsed = [_split_atom_token(parts[idx]) for idx in atom_indices]
                clean_ids = [aid for aid, _ in parsed]
                periods = [p for _, p in parsed]

                # Skip pure periodic-image records (every member periodic).
                if all(p > 0 for p in periods):
                    stats["periodic_skipped"] += 1
                    continue

                # Emit if every member atom is mapped.
                if all(cid in selected_old_ids for cid in clean_ids):
                    type_id = int(parts[1])
                    involved_new = [
                        f"{id_map[cid]}{_period_suffix(cid, fp)}"
                        for cid, fp in zip(clean_ids, periods)
                    ]
                    coeff_val = coeff_db[coeff_key].get(type_id, "N/A")

                    records.append({
                        "Category": cat_name,
                        "New_ID": new_topo_counter,
                        "Old_ID": parts[0],
                        "Type_ID": type_id,
                        "Related_New_Atoms": ", ".join(involved_new),
                        "Parameter_1 (Mass)": "",
                        "Parameter_2 (Coeffs)": coeff_val,
                    })
                    new_topo_counter += 1
                    if any(p > 0 for p in periods):
                        stats["periodic_kept"] += 1
            except (ValueError, IndexError):
                continue

    return records, stats


def _records_to_csv(records: List[Dict[str, Any]]) -> str:
    """Convert extraction records to CSV string."""
    if not records:
        return ""
    df = pd.DataFrame(records)
    cols = [
        "Category", "New_ID", "Related_New_Atoms",
        "Type_ID", "Parameter_2 (Coeffs)", "Parameter_1 (Mass)", "Old_ID",
    ]
    cols = [c for c in cols if c in df.columns]
    df = df[cols]
    return df.to_csv(index=False)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/parse-structure", response_model=ParseStructureResponse)
async def parse_structure(file: UploadFile = File(...)):
    """Upload a PDB / MOL / SDF / XYZ structure file and return its atom list."""
    try:
        content = file.file.read()
        fid = _save_upload(content, suffix=".struct")
        atoms = _parse_structure_file(content, file.filename or "structure.pdb")
        formula = ""
        try:
            from collections import Counter
            elem_counts = Counter(a.element for a in atoms)
            formula = "".join(
                f"{e}{c if c > 1 else ''}" for e, c in sorted(elem_counts.items())
            )
        except Exception:
            pass
        return ParseStructureResponse(
            atoms=atoms,
            file_id=fid,
            total_atoms=len(atoms),
            formula=formula,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=f"Failed to parse structure: {exc}")


@router.post("/parse-lmp", response_model=ParseLmpResponse)
async def parse_lmp(file: UploadFile = File(...)):
    """Upload a LAMMPS data file and return its atom list + parsed sections."""
    try:
        content = file.file.read()
        fid = _save_upload(content, suffix=".lmp")
        text = content.decode("utf-8", errors="replace")
        sections = _parse_lammps_data(text)
        atoms = _parse_lmp_atoms(sections)
        atom_style = _detect_atom_style(sections.get("Atoms", []))
        return ParseLmpResponse(
            atoms=atoms,
            sections=sections,
            file_id=fid,
            total_atoms=len(atoms),
            atom_style=atom_style,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=f"Failed to parse LAMMPS data: {exc}")


@router.post("/validate", response_model=ValidationReport)
async def validate_correspondence(
    struct_file_id: str = Body(..., embed=True),
    lmp_file_id: str = Body(..., embed=True),
):
    """Validate that the structure and LAMMPS data correspond."""
    try:
        # Re-parse both files
        import os
        from utils import _file_path

        struct_path = _file_path(struct_file_id)
        lmp_path = _file_path(lmp_file_id)

        with open(struct_path, "rb") as f:
            struct_content = f.read()
        with open(lmp_path, "r", encoding="utf-8", errors="replace") as f:
            lmp_text = f.read()

        struct_filename = os.path.basename(struct_path)
        struct_atoms = _parse_structure_file(struct_content, struct_filename)
        lmp_sections = _parse_lammps_data(lmp_text)
        lmp_atoms = _parse_lmp_atoms(lmp_sections)

        # Compare atom counts
        n_struct = len(struct_atoms)
        n_lmp = len(lmp_atoms)
        warnings: List[str] = []

        # Element comparison
        from collections import Counter
        struct_elem_counts = Counter(a.element for a in struct_atoms)

        # Infer each LAMMPS atom TYPE's element from its mass, then build the
        # LAMMPS element composition by applying that type->element map to the
        # Atoms section. This is what makes a structure<->LAMMPS mismatch
        # *visible*: the user can read off "type 1 = H, type 3 = C ..." and see
        # exactly which elements are over/under-represented, instead of only
        # getting an opaque atom-count number.
        type_elems = _infer_type_elements(lmp_sections)
        type_elements_info = [
            TypeElementInfo(type_id=t, mass=m, element=e)
            for t, (m, e) in sorted(type_elems.items())
        ]
        lmp_elem_counts: Counter = Counter()
        unknown_types: set = set()
        for la in lmp_atoms:
            elem = type_elems.get(la.atom_type, (0.0, "?"))[1]
            if elem == "?":
                unknown_types.add(la.atom_type)
            lmp_elem_counts[elem] += 1

        def _formula(counts: Counter) -> str:
            items = sorted(
                ((e, c) for e, c in counts.items() if e),
                key=lambda kv: (kv[0] == "?", kv[0]),
            )
            return "".join(f"{e}{c if c > 1 else ''}" for e, c in items)

        struct_formula = _formula(struct_elem_counts)
        lmp_formula = _formula(lmp_elem_counts)

        all_elems = sorted(set(struct_elem_counts) | set(lmp_elem_counts))
        element_diff = [
            ElementDiffRow(
                element=e,
                struct=struct_elem_counts.get(e, 0),
                lmp=lmp_elem_counts.get(e, 0),
                match=struct_elem_counts.get(e, 0) == lmp_elem_counts.get(e, 0),
            )
            for e in all_elems
        ]
        elem_mismatch = [d for d in element_diff if not d.match]
        elem_comparison: Dict[str, Dict[str, Union[int, str]]] = {
            d.element: {"struct": d.struct, "lmp": d.lmp} for d in element_diff
        }

        ok = True
        msg = ""
        warnings: List[str] = []

        if n_struct == 0:
            ok = False
            msg = "Structure file contains no atoms."
        elif n_lmp == 0:
            ok = False
            msg = "LAMMPS data file contains no atoms."
        else:
            count_ok = n_struct == n_lmp
            elem_ok = not elem_mismatch
            if count_ok and elem_ok:
                msg = (f"Match: {n_struct} atoms and identical element "
                       f"composition (structure {struct_formula} == LAMMPS "
                       f"{lmp_formula}).")
            elif count_ok and not elem_ok:
                ok = False
                msg = (f"Atom counts match ({n_struct}) but element composition "
                       f"differs (structure {struct_formula} vs LAMMPS "
                       f"{lmp_formula}). See the comparison table below.")
            else:
                ok = False
                msg = (f"Mismatch: structure has {n_struct} atoms "
                       f"({struct_formula}), LAMMPS has {n_lmp} "
                       f"({lmp_formula}). See the comparison table below.")
            if unknown_types:
                warnings.append(
                    f"LAMMPS types with unrecognised mass (cannot infer "
                    f"element): {sorted(unknown_types)}. Check the Masses "
                    f"section."
                )

        return ValidationReport(
            ok=ok,
            message=msg,
            structure_atom_count=n_struct,
            lmp_atom_count=n_lmp,
            element_comparison=elem_comparison,
            type_elements=type_elements_info,
            struct_formula=struct_formula,
            lmp_formula=lmp_formula,
            element_diff=element_diff,
            warnings=warnings,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=f"Validation failed: {exc}")


@router.post("/extract", response_class=PlainTextResponse)
async def extract_csv(req: ExtractRequest = Body(...)):
    """Run the LMP force field extraction for an explicit old->new id map and return CSV."""
    try:
        from utils import _file_path

        lmp_path = _file_path(req.lmp_file_id)

        with open(lmp_path, "r", encoding="utf-8", errors="replace") as f:
            lmp_text = f.read()

        sections = _parse_lammps_data(lmp_text)

        records, stats = _run_extraction(
            sections, req.id_map, req.period_map,
        )

        csv_text = _records_to_csv(records)

        # Build summary (incl. periodic # stats so the user can spot periodicity)
        from collections import Counter
        cat_counts = Counter(r["Category"] for r in records)
        summary_parts = [f"{cat}: {cnt}" for cat, cnt in sorted(cat_counts.items())]
        summary = f"Extracted {len(records)} records -- " + ", ".join(summary_parts)
        summary += (
            f" | periodic(#): kept {stats['periodic_kept']}, "
            f"skipped {stats['periodic_skipped']}"
        )

        return PlainTextResponse(
            content=csv_text,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=extracted_params.csv",
                "X-Extraction-Summary": summary,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        raise HTTPException(
            500,
            detail=f"Extraction failed: {exc}\n\nTraceback:\n{tb}",
        )
