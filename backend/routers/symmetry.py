"""
Space-group detection router — find the symmetry, KEEP the cell.

Materials Studio / PLATON always report a found space group in its ITA
standard setting, which rewrites the user's cell (axes swapped, c-glide
turned n-glide, the chain axis of a polymer fibre structure moved off c).
This module does the opposite:

  1. parse the uploaded CIF into the FULL cell (P1 expansion — symmetric
     CIFs are expanded by pymatgen, so any CIF works);
  2. run ``spglib.get_symmetry_dataset`` on that cell.  The returned
     rotations/translations are expressed in the INPUT cell basis, so the
     cell parameters never change — the standard-setting cell is returned
     separately as reference information only and is never applied;
  3. measure how exact the detected symmetry is: for every atom, the
     distance to its nearest symmetry image ("symmetrisation shift"),
     which tells the user how far atoms would have to move to sit on the
     found operations;
  4. optionally export a symmetrised CIF — same cell, a
     ``_symmetry_equiv_pos_as_xyz`` loop in the user's own basis, and only
     the asymmetric-unit atoms (Wyckoff letters included);
  5. optionally export the SAME symmetrisation as an all-atom P 1 CIF —
     the idealisation is actually applied to the coordinates (special-position
     atoms land exactly on their symmetry elements) and the full cell is
     expanded, so calculation programs that only read P 1 can consume it.

A tolerance sweep endpoint is provided because coordinates from a
refinement are only approximately symmetric; whether a space group is
"real" or pseudo-symmetry is a judgement the user should make by seeing
how the answer changes with ``symprec``.
"""

from __future__ import annotations

import math
import os
from datetime import date
from fractions import Fraction
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from utils import _file_path, _save_output, _save_upload

router = APIRouter()


# ---------------------------------------------------------------------------
# spglib access (attribute-style in 2.x, dict-style in some builds)
# ---------------------------------------------------------------------------

def _get(ds: Any, name: str):
    """Read a field from a SpglibDataset regardless of its layout."""
    try:
        return getattr(ds, name)
    except AttributeError:
        try:
            return ds[name]
        except Exception:
            return None


def _cell_tuple(structure):
    """(lattice rows, frac coords, atomic numbers) for spglib."""
    lattice = np.array(structure.lattice.matrix, dtype=float)
    frac = np.array(structure.frac_coords, dtype=float)
    numbers = [int(site.specie.Z) for site in structure]
    return lattice, frac, numbers


def _run_spglib(structure, symprec: float):
    """Run the symmetry search; raise HTTP errors on failure."""
    import spglib

    lattice, frac, numbers = _cell_tuple(structure)
    try:
        ds = spglib.get_symmetry_dataset((lattice, frac, numbers), symprec=symprec)
    except Exception as exc:
        raise HTTPException(422, detail=f"spglib 运行失败: {exc}")
    if ds is None:
        raise HTTPException(422, detail=f"对称性搜索失败 (symprec={symprec})，请尝试调整容差")
    return ds, lattice, frac, numbers


# ---------------------------------------------------------------------------
# Structure loading
# ---------------------------------------------------------------------------

def _load_structure(file_id: str):
    """Load a CIF into a pymatgen Structure (symmetric CIFs expand to P1)."""
    from pymatgen.core import Structure

    path = _file_path(file_id)
    try:
        return Structure.from_file(path)
    except Exception as exc:
        raise HTTPException(400, detail=f"无法解析 CIF 文件: {exc}")


# ---------------------------------------------------------------------------
# Symmetry analysis helpers
# ---------------------------------------------------------------------------

def _op_to_xyz(rotation, translation) -> str:
    """Format one operation as 'x,y,z' style, e.g. '-x+1/2,y+1/2,-z+1/2'."""
    names = ("x", "y", "z")
    parts = []
    for r in range(3):
        comp = []
        for c in range(3):
            v = float(rotation[r][c])
            if abs(v) < 1e-9:
                continue
            sign = "+" if v > 0 else "-"
            if abs(abs(v) - 1.0) < 1e-9:
                comp.append(f"{sign}{names[c]}")
            else:
                comp.append(f"{sign}{abs(v):g}*{names[c]}")
        tf = Fraction(float(translation[r])).limit_denominator(24)
        if tf != 0:
            sign = "+" if tf > 0 else "-"
            num, den = abs(tf).numerator, abs(tf).denominator
            comp.append(f"{sign}{num}" if den == 1 else f"{sign}{num}/{den}")
        parts.append("".join(comp).lstrip("+") or "0")
    return ",".join(parts)


def _symmetry_shift(lattice, frac, rotations, translations, equivalent_atoms):
    """Per-atom distance (Å) to the nearest image of its representative.

    Zero for an exactly symmetric structure; ~0.05 Å means atoms would
    move that far if the structure were idealised onto the found group.
    """
    reps = frac[np.asarray(equivalent_atoms)]                 # (N,3)
    # images[n, k] = rotation_k applied to the representative of atom n
    images = np.einsum("kij,nj->nki", rotations, reps) + translations[None, :, :]
    delta = frac[:, None, :] - images
    delta -= np.round(delta)                                   # minimum image
    dist = np.linalg.norm(delta @ lattice, axis=-1)            # (N, n_ops)
    dev = dist.min(axis=1)
    return float(dev.max()), float(dev.mean())


def _cell_dict(lattice_matrix) -> Dict[str, float]:
    m = np.asarray(lattice_matrix, dtype=float)
    a, b, c = (float(np.linalg.norm(v)) for v in m)
    alpha = math.degrees(math.acos(np.dot(m[1], m[2]) / (b * c)))
    beta = math.degrees(math.acos(np.dot(m[0], m[2]) / (a * c)))
    gamma = math.degrees(math.acos(np.dot(m[0], m[1]) / (a * b)))
    return {"a": round(a, 6), "b": round(b, 6), "c": round(c, 6),
            "alpha": round(alpha, 6), "beta": round(beta, 6), "gamma": round(gamma, 6)}


def _representatives(equivalent_atoms) -> List[int]:
    """Indices of one atom per orbit, in order of first appearance."""
    eq = np.asarray(equivalent_atoms)
    seen, reps = set(), []
    for i, e in enumerate(eq):
        if int(e) not in seen:
            seen.add(int(e))
            reps.append(int(i))
    return reps


def _idealized_full_cell(structure, ds, lattice, frac, symprec):
    """Snap every orbit onto the found operations, expanded to the FULL cell.

    For each orbit representative p the exact images {R·p + t} are computed;
    images that coincide (within ``symprec``, the same tolerance spglib used
    to assign site symmetry) are site-symmetry partners — e.g. the two mirror
    images of an atom straddling a mirror — and their centroid is the exact
    special-position coordinate. The set of cluster centroids is therefore
    exactly invariant under the found group:

      * general-position atoms keep their coordinates (they define the orbit);
      * special-position atoms are averaged onto the symmetry element itself.

    Returns (atoms, shift) where atoms = [{'label','element','frac'}, ...]
    for the whole symmetrised cell and shift = (max, mean) distance (Å) the
    idealisation moved the original atoms.
    """
    rotations = np.asarray(_get(ds, "rotations"))
    translations = np.asarray(_get(ds, "translations"))
    eq = np.asarray(_get(ds, "equivalent_atoms"))
    species = [str(site.specie.symbol) for site in structure]

    pairs: List[tuple] = []          # (element, idealised fractional coord)
    for idx in _representatives(eq):
        images = np.einsum("kij,j->ki", rotations, frac[idx]) + translations
        means, counts = [], []
        for q in images % 1.0:
            for k, m in enumerate(means):
                d = q - m
                d -= np.round(d)                       # minimum image
                if np.linalg.norm(d @ lattice) < symprec:
                    means[k] = means[k] + d / (counts[k] + 1)   # unwrapped running mean
                    counts[k] += 1
                    break
            else:
                means.append(q.copy())
                counts.append(1)
        for m in means:
            pairs.append((species[idx], m % 1.0))

    atoms, counters = [], {}
    for el, c in pairs:
        counters[el] = counters.get(el, 0) + 1
        atoms.append({
            "label": f"{el}{counters[el]}",
            "element": el,
            "frac": [round(float(v) % 1.0, 8) for v in c],
        })
    return atoms, _idealization_shift(lattice, frac, species, pairs)


def _idealization_shift(lattice, frac, species, ideal_pairs):
    """(max, mean) distance (Å) from each original atom to the nearest
    same-element atom of the idealised cell — how far the symmetrisation
    actually moved the atoms."""
    by_el: Dict[str, List[np.ndarray]] = {}
    for el, c in ideal_pairs:
        by_el.setdefault(el, []).append(np.asarray(c))
    by_el = {el: np.array(v) for el, v in by_el.items()}
    devs = []
    for i, p in enumerate(frac):
        d = by_el[species[i]] - p
        d -= np.round(d)
        devs.append(float(np.linalg.norm((d @ lattice), axis=1).min()))
    return float(max(devs)), float(sum(devs) / len(devs))


def _analyse_payload(structure, ds, lattice, frac, symprec: float) -> Dict[str, Any]:
    """Assemble the shared analysis response (cell untouched)."""
    rotations = np.asarray(_get(ds, "rotations"))
    translations = np.asarray(_get(ds, "translations"))
    eq = np.asarray(_get(ds, "equivalent_atoms"))
    wyckoffs = _get(ds, "wyckoffs") or ["?"] * len(structure)

    max_dev, mean_dev = _symmetry_shift(lattice, frac, rotations, translations, eq)
    reps = _representatives(eq)
    species = [str(site.specie.symbol) for site in structure]

    # Volume ratio primitive/input. spglib's primitive_lattice rows are
    # Cartesian vectors, so det gives the absolute primitive volume; divide
    # by the input cell volume (verified: 1.0 for a primitive input cell,
    # 0.5 for a 2x supercell — i.e. < 1 means the input cell is a supercell
    # of the true primitive cell).
    prim = np.asarray(_get(ds, "primitive_lattice"), dtype=float)
    try:
        vol_ratio = float(abs(np.linalg.det(prim)) / abs(np.linalg.det(lattice)))
    except Exception:
        vol_ratio = 1.0
    is_primitive = abs(vol_ratio - 1.0) < 1e-6

    # Standard-setting cell — REFERENCE ONLY, never applied.
    std_cell = _cell_dict(_get(ds, "std_lattice"))
    try:
        det = float(np.linalg.det(np.asarray(_get(ds, "transformation_matrix"))))
    except Exception:
        det = 1.0

    asu_atoms = []
    counters: Dict[str, int] = {}
    for idx in reps:
        el = species[idx]
        counters[el] = counters.get(el, 0) + 1
        x, y, z = frac[idx] % 1.0
        asu_atoms.append({
            "label": f"{el}{counters[el]}",
            "element": el,
            "wyckoff": wyckoffs[idx],
            "frac": [round(float(x), 8), round(float(y), 8), round(float(z), 8)],
        })

    return {
        "fileId": None,
        "symprec": symprec,
        "inputCell": _cell_dict(lattice),
        "nAtoms": len(structure),
        "spaceGroup": {
            "number": int(_get(ds, "number")),
            "hmStandard": str(_get(ds, "international")),  # standard-setting name
            "hall": str(_get(ds, "hall")),
            "choice": str(_get(ds, "choice") or ""),
            "pointgroup": str(_get(ds, "pointgroup")),
            "nOperations": int(len(rotations)),
        },
        # Authoritative: operations in the INPUT cell basis.
        "operations": [
            {"id": k + 1, "xyz": _op_to_xyz(R, t),
             "rotation": [[int(round(float(v))) for v in row] for row in R],
             "translation": [round(float(v), 8) for v in t]}
            for k, (R, t) in enumerate(zip(rotations, translations))
        ],
        "nAsymmetricAtoms": len(reps),
        "asymmetricAtoms": asu_atoms,
        "verification": {
            "maxShiftA": round(max_dev, 6),
            "meanShiftA": round(mean_dev, 6),
        },
        "primitive": {
            "isInputPrimitive": is_primitive,
            "volumeRatio": round(vol_ratio, 6),   # primitive/input volume; < 1 → input is a supercell
        },
        "standardSettingReference": {
            "cell": std_cell,
            "transformationDeterminant": round(det, 6),
        },
    }


# ---------------------------------------------------------------------------
# Symmetrised CIF export (Materials-Studio style, cell unchanged)
# ---------------------------------------------------------------------------

def _write_symmetrized_cif(payload: Dict[str, Any], name: str) -> str:
    """CIF with the ORIGINAL cell, a symop loop in the input basis, ASU atoms."""
    sg = payload["spaceGroup"]
    cell = payload["inputCell"]
    lines = [
        f"data_{name}",
        f"_audit_creation_date              {date.today().isoformat()}",
        "_audit_creation_method            'PolymCrystRefine Space Group Detection'",
        # NOTE: the H-M name is the standard-setting symbol; the setting that
        # actually matches the operations below is the user's own basis and is
        # pinned by the Hall symbol + the symop loop.
        f"_symmetry_space_group_name_H-M    '{sg['hmStandard']}'",
        f"_symmetry_space_group_name_Hall   '{sg['hall']}'",
        f"_symmetry_Int_Tables_number       {sg['number']}",
        "loop_",
        "_symmetry_equiv_pos_site_id",
        "_symmetry_equiv_pos_as_xyz",
    ]
    for op in payload["operations"]:
        lines.append(f"  {op['id']}  '{op['xyz']}'")
    lines += [
        f"_cell_length_a                    {cell['a']:.6f}",
        f"_cell_length_b                    {cell['b']:.6f}",
        f"_cell_length_c                    {cell['c']:.6f}",
        f"_cell_angle_alpha                 {cell['alpha']:.6f}",
        f"_cell_angle_beta                  {cell['beta']:.6f}",
        f"_cell_angle_gamma                 {cell['gamma']:.6f}",
        "loop_",
        "_atom_site_label",
        "_atom_site_type_symbol",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
        "_atom_site_occupancy",
    ]
    for at in payload["asymmetricAtoms"]:
        x, y, z = at["frac"]
        lines.append(
            f"{at['label']:<6} {at['element']:<2} {x:11.8f} {y:11.8f} {z:11.8f}  1.00"
        )
    return "\n".join(lines) + "\n"


def _write_symmetrized_p1_cif(name: str, cell: Dict[str, float], sg: Dict[str, Any],
                              atoms: List[Dict[str, Any]], shift) -> str:
    """All-atom P 1 CIF: the symmetrisation APPLIED, the cell still original.

    The provenance group is kept as comments so calculation programs see a
    plain P 1 file while the user still knows where it came from.
    """
    lines = [
        f"data_{name}",
        f"_audit_creation_date              {date.today().isoformat()}",
        "_audit_creation_method            'PolymCrystRefine symmetrised P1 expansion'",
        f"# Idealised onto space group #{sg['number']} {sg['hmStandard']} (Hall {sg['hall']}).",
        f"# Symmetrisation moved atoms by at most {shift[0]:.6f} A (mean {shift[1]:.6f} A);",
        "# cell parameters are exactly those of the input refinement.",
        "_symmetry_space_group_name_H-M    'P 1'",
        "_symmetry_Int_Tables_number       1",
        "loop_",
        "_symmetry_equiv_pos_site_id",
        "_symmetry_equiv_pos_as_xyz",
        "  1  'x,y,z'",
        f"_cell_length_a                    {cell['a']:.6f}",
        f"_cell_length_b                    {cell['b']:.6f}",
        f"_cell_length_c                    {cell['c']:.6f}",
        f"_cell_angle_alpha                 {cell['alpha']:.6f}",
        f"_cell_angle_beta                  {cell['beta']:.6f}",
        f"_cell_angle_gamma                 {cell['gamma']:.6f}",
        "loop_",
        "_atom_site_label",
        "_atom_site_type_symbol",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
        "_atom_site_occupancy",
    ]
    for at in atoms:
        x, y, z = at["frac"]
        lines.append(
            f"{at['label']:<6} {at['element']:<2} {x:11.8f} {y:11.8f} {z:11.8f}  1.00"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    fileId: str
    # Distance tolerance (Å): refined coordinates are only approximately
    # symmetric — sweep first when unsure.
    symprec: float = Field(1e-3, gt=0.0, le=1.0)


class ScanRequest(BaseModel):
    fileId: str
    values: List[float] = Field(
        default_factory=lambda: [1e-5, 1e-4, 1e-3, 5e-3, 1e-2, 5e-2, 1e-1]
    )


class SymmetrizeRequest(AnalyzeRequest):
    filename: Optional[str] = None
    # "asu": symmetric CIF (symop loop + asymmetric-unit atoms).
    # "p1": the same symmetrisation applied to the coordinates, exported as
    #       an all-atom P 1 cell for calculation programs.
    mode: str = Field("asu", pattern="^(asu|p1)$")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload")
def upload_cif(file: UploadFile = File(...)):
    """Upload a CIF (P1 or symmetric) and return the parsed cell + sites."""
    try:
        raw = file.file.read()
        fid = _save_upload(raw, suffix=".cif")
        structure = _load_structure(fid)
        counts: Dict[str, int] = {}
        for site in structure:
            el = str(site.specie.symbol)
            counts[el] = counts.get(el, 0) + 1
        lattice = structure.lattice
        return {
            "fileId": fid,
            "originalName": file.filename,
            "cell": {
                "a": lattice.a, "b": lattice.b, "c": lattice.c,
                "alpha": lattice.alpha, "beta": lattice.beta, "gamma": lattice.gamma,
            },
            "nAtoms": len(structure),
            "counts": dict(counts),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    """Detect the space group. Cell parameters are returned untouched."""
    try:
        structure = _load_structure(req.fileId)
        ds, lattice, frac, _numbers = _run_spglib(structure, req.symprec)
        payload = _analyse_payload(structure, ds, lattice, frac, req.symprec)
        payload["fileId"] = req.fileId
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=str(exc))


@router.post("/scan")
def scan(req: ScanRequest):
    """Tolerance sweep — see how the detected group changes with symprec."""
    import spglib

    structure = _load_structure(req.fileId)
    lattice, frac, numbers = _cell_tuple(structure)
    rows = []
    for v in req.values:
        if v <= 0 or v > 1.0:
            continue
        try:
            ds = spglib.get_symmetry_dataset((lattice, frac, numbers), symprec=v)
        except Exception:
            ds = None
        if ds is None:
            rows.append({"symprec": v, "number": None, "hm": None, "nOperations": 0})
            continue
        eq = np.asarray(_get(ds, "equivalent_atoms"))
        rows.append({
            "symprec": v,
            "number": int(_get(ds, "number")),
            "hm": str(_get(ds, "international")),
            "nOperations": int(len(np.asarray(_get(ds, "rotations")))),
            "nAsymmetricAtoms": len(_representatives(eq)),
        })
    return {"fileId": req.fileId, "inputCell": _cell_dict(lattice), "scan": rows}


@router.post("/symmetrize")
def symmetrize(req: SymmetrizeRequest):
    """Export a symmetrised CIF (mode='asu': symop loop + ASU atoms;
    mode='p1': idealisation applied, all atoms, space group P 1)."""
    try:
        structure = _load_structure(req.fileId)
        ds, lattice, frac, _numbers = _run_spglib(structure, req.symprec)
        payload = _analyse_payload(structure, ds, lattice, frac, req.symprec)
        name = (req.filename or "symmetrized").strip()
        name = (name.rsplit(".", 1)[0] if "." in name else name).replace(" ", "_") or "symmetrized"
        if req.mode == "p1":
            if not name.lower().endswith("_p1"):
                name += "_P1"
            atoms, shift = _idealized_full_cell(structure, ds, lattice, frac, req.symprec)
            text = _write_symmetrized_p1_cif(name, payload["inputCell"],
                                             payload["spaceGroup"], atoms, shift)
            n_atoms, idealization = len(atoms), {
                "maxShiftA": round(shift[0], 6), "meanShiftA": round(shift[1], 6),
            }
        else:
            text = _write_symmetrized_cif(payload, name)
            n_atoms, idealization = payload["nAtoms"], None
        fid = _save_output(text.encode("utf-8"), suffix=".cif")
        return {
            "fileId": fid,
            "filename": f"{name}.cif",
            "mode": req.mode,
            "cif": text,
            "cell": payload["inputCell"],
            "spaceGroup": {k: payload["spaceGroup"][k] for k in ("number", "hmStandard", "hall")},
            "nOperations": payload["spaceGroup"]["nOperations"],
            "nAsymmetricAtoms": payload["nAsymmetricAtoms"],
            "nAtoms": n_atoms,
            "idealization": idealization,
            "verification": payload["verification"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=str(exc))


@router.get("/task/{taskId}/download")
def task_download(taskId: str):
    """Download a generated CIF."""
    from fastapi.responses import FileResponse

    path = _file_path(taskId)
    return FileResponse(path, filename=os.path.basename(path), media_type="chemical/x-cif")
