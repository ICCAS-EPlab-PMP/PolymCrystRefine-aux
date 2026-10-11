"""
CIF hydrogenation router — add hydrogens to refined (H-free) polymer CIFs.

Refined structures from the Fortran optimiser usually contain heavy atoms
only.  CP2K needs explicit hydrogens, so this module:

  1. perceives chemical bonds under periodic boundary conditions
     (covalent-radius cutoffs via ``Structure.get_all_neighbors``);
  2. infers bond orders from bond lengths (C=O double bonds decide how
     many H an ester carbon gets) and fills each atom's valence with H
     placed at idealised sp3/sp2 geometry;
  3. lets the user delete / add / re-order bonds (mis-perceived contacts
     happen at grain boundaries and disorder) and re-runs the H placement;
  4. exports a Materials-Studio-style CIF (P1, labelled sites, Uiso,
     ``_geom_bond`` loop with ``1_555``-style symmetry codes) matching
     ``reference/cif/opttest.cif``.

Bonds are identified by a canonical key ``"i:j:dx:dy:dz"`` (i<j; offset
negated when swapped), stable across re-runs for heavy-heavy bonds.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from utils import _file_path, _save_output, _save_upload

router = APIRouter()


# ---------------------------------------------------------------------------
# Chemistry tables
# ---------------------------------------------------------------------------

# Cordero covalent radii (Å) for the elements common in polymers.
COVALENT_RADII: Dict[str, float] = {
    "H": 0.31, "B": 0.84, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57,
    "Si": 1.11, "P": 1.07, "S": 1.05, "Cl": 1.02, "Br": 1.20, "I": 1.39,
    "Se": 1.20, "Na": 1.66, "K": 2.03, "Mg": 1.41, "Zn": 1.22,
}
_DEFAULT_RADIUS = 0.80

# Standard valences used for the H count (order sum -> remaining H).
DEFAULT_VALENCE: Dict[str, int] = {
    "H": 1, "B": 3, "C": 4, "N": 3, "O": 2, "F": 1,
    "Si": 4, "P": 3, "S": 2, "Cl": 1, "Br": 1, "I": 1,
}

# Distance thresholds (Å) below which a pair is a multiple bond.
_DOUBLE_BOND_MAX = {
    ("C", "C"): 1.38, ("C", "N"): 1.32, ("C", "O"): 1.30,
    ("N", "N"): 1.28, ("N", "O"): 1.30, ("C", "S"): 1.72,
    ("S", "O"): 1.55,
}
_TRIPLE_BOND_MAX = {
    ("C", "C"): 1.22, ("C", "N"): 1.17,
}

# CPK colours for the 3D view (frontend mirror).
CPK_COLORS: Dict[str, str] = {
    "H": "#F3F4F6", "B": "#FFB5B5", "C": "#4B5563", "N": "#3050F8",
    "O": "#FF0D0D", "F": "#90E050", "Si": "#F0C8A0", "P": "#FF8000",
    "S": "#FFFF30", "Cl": "#1FF01F", "Br": "#A62929", "I": "#940094",
    "Se": "#FFA100", "Na": "#AB5CF2", "K": "#8F40D4", "Mg": "#8AFF00",
    "Zn": "#7D80B0",
}


def _radius(el: str) -> float:
    return COVALENT_RADII.get(el, _DEFAULT_RADIUS)


def _pair_cutoff(el1: str, el2: str, tolerance: float) -> float:
    return _radius(el1) + _radius(el2) + tolerance


def _bond_order(el1: str, el2: str, dist: float) -> int:
    pair = tuple(sorted((el1, el2)))
    if pair in _TRIPLE_BOND_MAX and dist < _TRIPLE_BOND_MAX[pair]:
        return 3
    if pair in _DOUBLE_BOND_MAX and dist < _DOUBLE_BOND_MAX[pair]:
        return 2
    return 1


# ---------------------------------------------------------------------------
# Bond bookkeeping
# ---------------------------------------------------------------------------

def _canonical_bond(i: int, j: int, offset) -> Tuple[str, int, int, Tuple[int, int, int]]:
    """Return (key, i, j, offset) with i<j and the offset matching i->j."""
    off = (int(round(offset[0])), int(round(offset[1])), int(round(offset[2])))
    if i > j:
        i, j = j, i
        off = (-off[0], -off[1], -off[2])
    key = f"{i}:{j}:{off[0]}:{off[1]}:{off[2]}"
    return key, i, j, off


def _symmetry_code(offset: Tuple[int, int, int]) -> str:
    """MS-style symmetry code: '.' for the home image, else 1_(d+5)(d+5)(d+5)."""
    if offset == (0, 0, 0):
        return "."
    return "1_{}{}{}".format(offset[0] + 5, offset[1] + 5, offset[2] + 5)


# ---------------------------------------------------------------------------
# Structure loading
# ---------------------------------------------------------------------------

def _load_structure(file_id: str):
    """Load a CIF into a pymatgen Structure (labels are regenerated)."""
    from pymatgen.core import Structure

    path = _file_path(file_id)
    try:
        return Structure.from_file(path)
    except Exception as exc:
        raise HTTPException(400, detail=f"无法解析 CIF 文件: {exc}")


# ---------------------------------------------------------------------------
# Bond perception (PBC-aware)
# ---------------------------------------------------------------------------

def _perceive_bonds(structure, tolerance: float) -> Dict[str, Dict[str, Any]]:
    """Distance-based bond perception across periodic images.

    Returns {key: {i, j, offset, dist, order}} — one entry per unique
    (atom_i, atom_j, image) contact inside the covalent cutoff.
    """
    species = [str(s.specie) for s in structure]
    rmax = max(
        _pair_cutoff(e, f, tolerance)
        for e in species for f in species
    )
    all_neighbors = structure.get_all_neighbors(rmax, include_index=True, include_image=True)

    bonds: Dict[str, Dict[str, Any]] = {}
    for i, nbrs in enumerate(all_neighbors):
        ei = species[i]
        for nbr in nbrs:
            site, dist, j, image = nbr[0], nbr[1], nbr[2], nbr[3]
            if dist < 0.4:
                continue
            ej = species[int(j)]
            if dist > _pair_cutoff(ei, ej, tolerance):
                continue
            key, ci, cj, off = _canonical_bond(i, int(j), image)
            if key in bonds:
                continue
            bonds[key] = {
                "i": ci, "j": cj, "offset": list(off),
                "dist": round(float(dist), 4),
                "order": _bond_order(ei, ej, dist),
            }
    return bonds


def _apply_edits(
    structure,
    bonds: Dict[str, Dict[str, Any]],
    remove_keys: List[str],
    add_bonds: List["BondEdit"],
    order_overrides: Dict[str, int],
    species: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Apply user edits on top of the perceived bond set (idempotent)."""
    for key in remove_keys:
        bonds.pop(key, None)
    lattice = structure.lattice
    frac = structure.frac_coords
    for be in add_bonds:
        key, ci, cj, off = _canonical_bond(be.i, be.j, be.offset)
        if key in bonds:
            continue
        fj = np.array(frac[cj]) + np.array(off)
        dist = float(np.linalg.norm(
            lattice.get_cartesian_coords(fj) - lattice.get_cartesian_coords(frac[ci])))
        bonds[key] = {
            "i": ci, "j": cj, "offset": list(off),
            "dist": round(dist, 4),
            "order": _bond_order(species[ci], species[cj], dist),
        }
    for key, order in order_overrides.items():
        if key in bonds and order in (1, 2, 3):
            bonds[key]["order"] = int(order)
    return bonds


# ---------------------------------------------------------------------------
# Hydrogen placement
# ---------------------------------------------------------------------------

def _unit(v: np.ndarray) -> Optional[np.ndarray]:
    n = np.linalg.norm(v)
    if n < 1e-8:
        return None
    return v / n


# Global caches removed — the structure is threaded through helpers explicitly.


def _rdkit_available() -> bool:
    try:
        from rdkit import Chem  # noqa: F401
        from rdkit.Chem import AllChem  # noqa: F401
        return True
    except ImportError:
        return False


def _fragments(n_atoms: int, bonds: Dict[str, Dict[str, Any]]) -> List[List[int]]:
    """Connected components of the bond graph (periodic images collapsed)."""
    from collections import deque

    adj: Dict[int, List[int]] = defaultdict(list)
    for b in bonds.values():
        adj[b["i"]].append(b["j"])
        adj[b["j"]].append(b["i"])
    seen: set = set()
    frags: List[List[int]] = []
    for s in range(n_atoms):
        if s in seen:
            continue
        comp: List[int] = []
        dq = deque([s])
        seen.add(s)
        while dq:
            x = dq.popleft()
            comp.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    dq.append(y)
        frags.append(comp)
    return frags


def _h_need_map(structure, bonds: Dict[str, Dict[str, Any]], warnings: List[str]) -> Dict[int, int]:
    """Per-atom hydrogen count = standard valence - bond order sum."""
    order_sum: Dict[int, int] = defaultdict(int)
    for b in bonds.values():
        order_sum[b["i"]] += b["order"]
        order_sum[b["j"]] += b["order"]

    nh_map: Dict[int, int] = {}
    for idx, site in enumerate(structure):
        el = str(site.specie)
        if el == "H":
            continue
        valence = DEFAULT_VALENCE.get(el)
        if valence is None:
            warnings.append(f"{el}{idx + 1}: 未定义价态，跳过补氢")
            continue
        nh = valence - order_sum.get(idx, 0)
        if nh < 0:
            warnings.append(
                f"{el}{idx + 1}: 键级总和 {order_sum[idx]} 超过价态 {valence}"
                f"（键识别可能有误，未补氢）")
            continue
        if nh == 0:
            continue
        max_h = 4 if el in ("C", "Si") else 3
        if nh > max_h:
            warnings.append(f"{el}{idx + 1}: 需补 {nh} 个 H，超出常见上限，仅补 {max_h} 个")
            nh = max_h
        nh_map[idx] = nh
    return nh_map


def _place_h_rdkit(
    structure,
    bonds: Dict[str, Dict[str, Any]],
    nh_map: Dict[int, int],
    ch_dist: float,
    warnings: List[str],
) -> List[Dict[str, Any]]:
    """Mature-chemistry H placement via RDKit.

    Per molecular fragment (unwrapped so chains render continuous):

      1. build an RWMol carrying the true H counts as explicit-H counts;
      2. ``Chem.AddHs(addCoords=True)`` seeds H positions;
      3. MMFF (UFF fallback) energy-minimises with every heavy atom FIXED,
         so H relax to proper ~109.5° angles and staggered dihedrals while
         the refined heavy-atom coordinates stay untouched;
      4. each X-H bond is rescaled to exactly ``ch_dist``.

    Re-entry bonds (chain wraps the cell; displayed stretched) are dropped
    from the RDKit copy — a 7+ Å "bond" would poison the force field. H
    counts still come from the full bond graph, so chemistry is unchanged.
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem

    lattice = structure.lattice
    frac = structure.frac_coords
    species = [str(s.specie) for s in structure]
    n0 = len(structure)
    disp = _unwrap(n0, bonds)

    def disp_cart(idx: int) -> np.ndarray:
        return lattice.get_cartesian_coords(frac[idx] + np.array(disp[idx]))

    out: List[Dict[str, Any]] = []

    for frag in _fragments(n0, bonds):
        rw = Chem.RWMol()
        conf = Chem.Conformer(len(frag))
        idx_map: Dict[int, int] = {}
        for k, i in enumerate(frag):
            a = Chem.Atom(species[i])
            a.SetNoImplicit(True)
            a.SetNumExplicitHs(nh_map.get(i, 0) if species[i] != "H" else 0)
            mi = rw.AddAtom(a)
            idx_map[i] = mi
            conf.SetAtomPosition(mi, [float(v) for v in disp_cart(i)])
        rw.AddConformer(conf, assignId=True)
        dropped = 0
        for b in bonds.values():
            i, j = b["i"], b["j"]
            if i in idx_map and j in idx_map:
                dd = float(np.linalg.norm(disp_cart(j) - disp_cart(i)))
                if abs(dd - b["dist"]) > 0.5:
                    dropped += 1        # stretched re-entry bond
                    continue
                rw.AddBond(idx_map[i], idx_map[j], Chem.BondType(b["order"]))
        mol = rw.GetMol()
        mol.UpdatePropertyCache(strict=False)
        Chem.FastFindRings(mol)

        if len(frag) == 1:
            # Isolated atom: RDKit would pile H at the origin — place by hand.
            for d in _geometric_directions(species[frag[0]], [], nh_map.get(frag[0], 0)):
                out.append({"parent": frag[0], "cart": disp_cart(frag[0]) + ch_dist * d})
            continue

        mol = Chem.AddHs(mol, addCoords=True)

        props = AllChem.MMFFGetMoleculeProperties(mol)
        if props is not None:
            ff = AllChem.MMFFGetMoleculeForceField(mol, props)
        else:
            ff = AllChem.UFFGetMoleculeForceField(mol)
        if ff is not None and hasattr(ff, "AddFixedPoint"):
            for k in range(len(frag)):
                ff.AddFixedPoint(k)     # heavy atoms stay at refined positions
            ff.Initialize()
            ff.Minimize(maxIts=3000)
        elif len(nh_map) > 0:
            warnings.append("RDKit 力场不可用，氢位置未做能量优化")

        conf = mol.GetConformer()
        for at in mol.GetAtoms():
            if at.GetIdx() < len(frag) or at.GetSymbol() != "H":
                continue
            parent_rk = at.GetNeighbors()[0].GetIdx()
            if parent_rk >= len(frag):
                continue
            parent = frag[parent_rk]
            p_parent = np.array(conf.GetAtomPosition(parent_rk))
            p_h = np.array(conf.GetAtomPosition(at.GetIdx()))
            # Rescale to the exact requested X-H distance.
            v = p_h - p_parent
            nv = np.linalg.norm(v)
            p_h = p_parent + (v / nv if nv > 1e-8 else v) * ch_dist
            out.append({"parent": parent, "cart": p_h})

    return out


def _geometric_directions(
    element: str, unit_vecs: List[np.ndarray], nh: int,
) -> List[np.ndarray]:
    """Compact idealised-geometry fallback (umbrella / bisector / sum)."""
    if nh <= 0:
        return []
    u = [x for x in unit_vecs if x is not None]
    n = len(u)
    if n == 0:
        tetra = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]) / np.sqrt(3.0)
        return list(tetra[:nh])
    if n == 1:
        axis = u[0]
        ref = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(ref, axis)) > 0.9:
            ref = np.array([0.0, 1.0, 0.0])
        p = _unit(np.cross(axis, ref))
        q = _unit(np.cross(axis, p))
        out = []
        for k in range(nh):
            phi = 2.0 * np.pi * k / nh
            out.append(-axis / 3.0 + (np.sqrt(8.0) / 3.0) * (p * np.cos(phi) + q * np.sin(phi)))
        return out
    if n == 2:
        bis = _unit(-(u[0] + u[1]))
        if bis is None:
            bis = _unit(np.cross(u[0], np.array([1.0, 0.0, 0.0]))) or np.array([0.0, 0.0, 1.0])
        p = _unit(np.cross(u[0], u[1]))
        if p is None:
            p = _unit(np.cross(bis, np.array([0.0, 0.0, 1.0]))) or np.array([1.0, 0.0, 0.0])
        q = _unit(np.cross(bis, p))
        theta = np.radians(54.75)
        return [np.cos(theta) * bis + np.sin(theta) * q,
                np.cos(theta) * bis - np.sin(theta) * q][:nh]
    s = _unit(-sum(u))
    if s is None:
        s = _unit(np.cross(u[1] - u[0], u[2] - u[0])) or np.array([0.0, 0.0, 1.0])
    return [s]


def _place_h_geometric(
    structure,
    bonds: Dict[str, Dict[str, Any]],
    nh_map: Dict[int, int],
    ch_dist: float,
) -> List[Dict[str, Any]]:
    """Fallback placement when RDKit is unavailable (angles idealised,
    dihedrals not staggered — install rdkit for proper geometry)."""
    lattice = structure.lattice
    frac = structure.frac_coords
    species = [str(s.specie) for s in structure]
    n0 = len(structure)
    disp = _unwrap(n0, bonds)

    nbr_vecs: Dict[int, List[np.ndarray]] = defaultdict(list)
    for b in bonds.values():
        i, j, off = b["i"], b["j"], np.array(b["offset"])
        ci = lattice.get_cartesian_coords(frac[i])
        cj = lattice.get_cartesian_coords(frac[j] + off)
        nbr_vecs[i].append(cj - ci)
        nbr_vecs[j].append(ci - cj)

    out: List[Dict[str, Any]] = []
    for idx, nh in nh_map.items():
        unit_vecs = [u for u in (_unit(v) for v in nbr_vecs.get(idx, [])) if u is not None]
        pos = lattice.get_cartesian_coords(frac[idx] + np.array(disp[idx]))
        for d in _geometric_directions(species[idx], unit_vecs, nh):
            out.append({"parent": idx, "cart": pos + ch_dist * d})
    return out


def _build_hydrogenated(
    structure,
    bonds: Dict[str, Dict[str, Any]],
    ch_dist: float,
) -> Tuple[Any, List[str], List[Dict[str, Any]]]:
    """Return (new_structure, warnings, h_sites) with H appended.

    h_sites entries: {index, parent, offset, dist} — the parent bond is
    recorded at placement time so the export never has to re-perceive.

    Placement uses RDKit + MMFF with the heavy atoms frozen (proper bond
    angles and staggered dihedrals); the hand-rolled geometry is only a
    fallback for environments without RDKit.
    """
    lattice = structure.lattice
    species = [str(s.specie) for s in structure]
    n0 = len(structure)
    disp = _unwrap(n0, bonds)

    warnings: List[str] = []
    nh_map = _h_need_map(structure, bonds, warnings)

    if _rdkit_available():
        try:
            placed = _place_h_rdkit(structure, bonds, nh_map, ch_dist, warnings)
            method = "RDKit+MMFF"
        except Exception as exc:  # pragma: no cover - defensive fallback
            warnings.append(f"RDKit 补氢失败，改用简化几何: {exc}")
            placed = _place_h_geometric(structure, bonds, nh_map, ch_dist)
            method = "简化几何（回退）"
    else:
        placed = _place_h_geometric(structure, bonds, nh_map, ch_dist)
        method = "简化几何（未安装 rdkit）"

    new_frac: List[np.ndarray] = []
    h_meta: List[Tuple[int, Tuple[int, int, int], float]] = []
    for h in placed:
        parent = h["parent"]
        fh_unwrapped = lattice.get_fractional_coords(h["cart"])
        fh = fh_unwrapped % 1.0
        # The placed H is adjacent to the parent's DISPLAY position, i.e.
        # fh_unwrapped ≈ frac_parent + disp_parent, so the canonical-image bond
        # offset X (fh + X adjacent to frac_parent) is the H's wrap shift minus
        # the parent's display shift.
        o_h = np.round(fh_unwrapped - fh).astype(int)
        offset = (
            int(o_h[0]) - disp[parent][0],
            int(o_h[1]) - disp[parent][1],
            int(o_h[2]) - disp[parent][2],
        )
        dist = float(np.linalg.norm(
            h["cart"] - lattice.get_cartesian_coords(
                structure.frac_coords[parent] + np.array(disp[parent]))))
        new_frac.append(fh)
        h_meta.append((parent, offset, dist))

    new_struct = structure.copy()
    for fh in new_frac:
        new_struct.insert(len(new_struct), "H", fh)

    h_sites = [
        {"index": n0 + k, "parent": parent, "offset": list(off), "dist": round(dist, 4)}
        for k, (parent, off, dist) in enumerate(h_meta)
    ]
    if h_sites:
        warnings.insert(0, f"已补 {len(h_sites)} 个氢原子（{method}，X–H = {ch_dist:.2f} Å）")
    else:
        warnings.insert(0, "未补充任何氢原子（结构可能已含氢或全部原子已满价）")
    return new_struct, warnings, h_sites


# ---------------------------------------------------------------------------
# Display unwrapping + response assembly
# ---------------------------------------------------------------------------

def _unwrap(n_atoms: int, bonds: Dict[str, Dict[str, Any]]) -> List[Tuple[int, int, int]]:
    """BFS image offsets so every connected fragment renders continuous.

    bond (i, j, offset) means frac_j + offset sits next to frac_i; the
    display offset of j is then o_i + offset.
    """
    adj: Dict[int, List[Tuple[int, Tuple[int, int, int]]]] = defaultdict(list)
    for b in bonds.values():
        i, j, off = b["i"], b["j"], tuple(b["offset"])
        adj[i].append((j, off))
        adj[j].append((i, (-off[0], -off[1], -off[2])))

    disp: List[Optional[Tuple[int, int, int]]] = [None] * n_atoms
    for seed in range(n_atoms):
        if disp[seed] is not None:
            continue
        disp[seed] = (0, 0, 0)
        stack = [seed]
        while stack:
            i = stack.pop()
            for j, off in adj[i]:
                if disp[j] is None:
                    disp[j] = (
                        disp[i][0] + off[0],
                        disp[i][1] + off[1],
                        disp[i][2] + off[2],
                    )
                    stack.append(j)
    # Isolated atoms (no bonds) keep the home image.
    return [d if d is not None else (0, 0, 0) for d in disp]


def _assemble_response(structure, bonds: Dict[str, Dict[str, Any]], warnings: List[str]):
    """Common response payload: atoms (with display coords) + bonds + cell."""
    lattice = structure.lattice
    species = [str(s.specie) for s in structure]
    frac = structure.frac_coords
    n_h = sum(1 for s in species if s == "H")

    disp_off = _unwrap(len(structure), bonds)
    atoms = []
    for idx in range(len(structure)):
        df = frac[idx] + np.array(disp_off[idx])
        atoms.append({
            "index": idx,
            "label": f"{species[idx]}{idx + 1}",
            "element": species[idx],
            "isH": species[idx] == "H",
            "frac": [round(float(v), 6) for v in frac[idx]],
            "dispOffset": list(disp_off[idx]),
            "dispCart": [round(float(v), 5) for v in lattice.get_cartesian_coords(df)],
        })

    bond_list = []
    cart_by_idx = {a["index"]: np.array(a["dispCart"]) for a in atoms}
    for key, b in bonds.items():
        # A bond whose displayed length differs from the true distance is a
        # "re-entry" bond: the chain wraps through the cell more than once and
        # one atom can only be drawn once, so the bond renders stretched.
        disp_d = float(np.linalg.norm(cart_by_idx[b["j"]] - cart_by_idx[b["i"]]))
        bond_list.append({
            "key": key,
            "i": b["i"], "j": b["j"], "offset": b["offset"],
            "dist": b["dist"], "order": b["order"],
            "isH": species[b["i"]] == "H" or species[b["j"]] == "H",
            "symmetry": _symmetry_code(tuple(b["offset"])),
            "stretched": abs(disp_d - b["dist"]) > 0.05,
        })
    bond_list.sort(key=lambda x: (x["isH"], min(x["i"], x["j"]), x["j"]))

    counts: Dict[str, int] = defaultdict(int)
    for s in species:
        counts[s] += 1
    formula = "".join(f"{el}{n}" for el, n in sorted(counts.items()))

    return {
        "atoms": atoms,
        "bonds": bond_list,
        "warnings": warnings,
        "cell": {
            "a": lattice.a, "b": lattice.b, "c": lattice.c,
            "alpha": lattice.alpha, "beta": lattice.beta, "gamma": lattice.gamma,
            "vectors": [[round(float(v), 5) for v in lv] for lv in lattice.matrix],
        },
        "stats": {
            "nAtoms": len(structure),
            "nHeavy": len(structure) - n_h,
            "nH": n_h,
            "nBonds": len(bond_list),
            "formula": formula,
        },
    }


# ---------------------------------------------------------------------------
# CIF export (Materials-Studio style, mirrors reference/cif/opttest.cif)
# ---------------------------------------------------------------------------

def _write_ms_cif(structure, bonds: Dict[str, Dict[str, Any]], name: str) -> str:
    lattice = structure.lattice
    species = [str(s.specie) for s in structure]
    frac = structure.frac_coords
    labels = [f"{species[i]}{i + 1}" for i in range(len(structure))]

    lines = [
        f"data_{name}",
        f"_audit_creation_date              {date.today().isoformat()}",
        "_audit_creation_method            'PolymCrystRefine CIF Hydrogenation'",
        "_symmetry_space_group_name_H-M    'P1'",
        "_symmetry_Int_Tables_number       1",
        "_symmetry_cell_setting            triclinic",
        "loop_",
        "_symmetry_equiv_pos_as_xyz",
        "  x,y,z",
        f"_cell_length_a                    {lattice.a:.4f}",
        f"_cell_length_b                    {lattice.b:.4f}",
        f"_cell_length_c                    {lattice.c:.4f}",
        f"_cell_angle_alpha                 {lattice.alpha:.4f}",
        f"_cell_angle_beta                  {lattice.beta:.4f}",
        f"_cell_angle_gamma                 {lattice.gamma:.4f}",
        "loop_",
        "_atom_site_label",
        "_atom_site_type_symbol",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
        "_atom_site_U_iso_or_equiv",
        "_atom_site_adp_type",
        "_atom_site_occupancy",
    ]
    for i in range(len(structure)):
        x, y, z = frac[i]
        lines.append(
            f"{labels[i]:<6} {species[i]:<2} {x:11.5f} {y:11.5f} {z:11.5f}"
            f" {0.0:7.5f}  Uiso   1.00"
        )

    # Only report bonds involving heavy atoms + their H; H-H none.
    lines += [
        "loop_",
        "_geom_bond_atom_site_label_1",
        "_geom_bond_atom_site_label_2",
        "_geom_bond_distance",
        "_geom_bond_site_symmetry_2",
        "_ccdc_geom_bond_type",
    ]
    for b in sorted(bonds.values(), key=lambda b: (b["i"], b["j"])):
        i, j, off = b["i"], b["j"], tuple(b["offset"])
        order = b["order"]
        btype = {1: "S", 2: "D", 3: "T"}.get(order, "S")
        lines.append(
            f"{labels[i]:<6} {labels[j]:<6} {b['dist']:7.3f} "
            f"{_symmetry_code(off):>6} {btype}"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class BondEdit(BaseModel):
    i: int
    j: int
    offset: List[int] = Field(default_factory=lambda: [0, 0, 0])


class AddHydrogensRequest(BaseModel):
    fileId: str
    # Covalent-radius tolerance (Å): larger -> more bonds perceived.
    tolerance: float = Field(0.40, gt=0.05, le=1.2)
    chDist: float = Field(1.09, gt=0.80, le=1.30)
    removeBonds: List[str] = Field(default_factory=list)
    addBonds: List[BondEdit] = Field(default_factory=list)
    orderOverrides: Dict[str, int] = Field(default_factory=dict)


class ExportRequest(AddHydrogensRequest):
    filename: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload")
def upload_cif(file: UploadFile = File(...)):
    """Upload a refined (H-free) CIF and return the parsed cell + sites."""
    try:
        raw = file.file.read()
        ext = ".cif"
        fid = _save_upload(raw, suffix=ext)
        structure = _load_structure(fid)
        species = [str(s.specie) for s in structure]
        lattice = structure.lattice
        counts: Dict[str, int] = defaultdict(int)
        for s in species:
            counts[s] += 1
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


def _run_pipeline(req: AddHydrogensRequest):
    """Shared pipeline for add-hydrogens / export endpoints.

    Returns (input_structure, hydrogenated_structure, bonds_incl_H, warnings).
    The user-edited heavy-atom graph stays authoritative; H bonds are the
    records written at placement time.
    """
    structure = _load_structure(req.fileId)
    species = [str(s.specie) for s in structure]

    bonds = _perceive_bonds(structure, req.tolerance)
    bonds = _apply_edits(structure, bonds, req.removeBonds, req.addBonds,
                         req.orderOverrides, species)
    new_struct, warnings, h_sites = _build_hydrogenated(structure, bonds, req.chDist)

    all_bonds = dict(bonds)
    for hs in h_sites:
        # Semantic: frac_H + offset sits next to frac_parent, so the parent is
        # the first endpoint (H indices are appended last — no swap occurs).
        key, ci, cj, off = _canonical_bond(hs["parent"], hs["index"], hs["offset"])
        all_bonds[key] = {
            "i": ci, "j": cj, "offset": list(off),
            "dist": hs["dist"], "order": 1,
        }
    return structure, new_struct, all_bonds, warnings


@router.post("/add-hydrogens")
def add_hydrogens(req: AddHydrogensRequest):
    """Perceive bonds, apply user edits, add hydrogens, return view payload."""
    try:
        _structure, new_struct, all_bonds, warnings = _run_pipeline(req)
        payload = _assemble_response(new_struct, all_bonds, warnings)
        payload["fileId"] = req.fileId
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=str(exc))


@router.post("/export")
def export_cif(req: ExportRequest):
    """Write the hydrogenated structure to a Materials-Studio-style CIF."""
    try:
        _structure, new_struct, all_bonds, warnings = _run_pipeline(req)
        name = os.path.splitext(req.filename or "hydrogenated")[0].replace(" ", "_") or "hydrogenated"
        text = _write_ms_cif(new_struct, all_bonds, name)
        fid = _save_output(text.encode("utf-8"), suffix=".cif")
        return {
            "fileId": fid,
            "filename": f"{name}.cif",
            "warnings": warnings,
            "nAtoms": len(new_struct),
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
