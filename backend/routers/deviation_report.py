"""
Structure deviation report router — compare a DFT-relaxed structure against
a reference structure and quantify how far each atom moved.

Typical workflow: a polymer CIF refined by the Fortran optimiser is sent to
DFT (CP2K).  The relaxed structure comes back as a CIF — or as the PDB that
CP2K writes — and the user wants to know how much the DFT geometry deviates
from the structure that went in.  This module:

  1. parses the two structures (CIF via pymatgen; CP2K-style PDB with a
     built-in ATOM/HETATM + CRYST1 reader — the backend deliberately has no
     ASE dependency);
  2. pairs the atoms — index-to-index, or (default) nearest-neighbour
     assignment per element via the Hungarian algorithm, which copes with
     CP2K reordering the atoms;
  3. computes per-atom displacements under periodic boundary conditions
     (minimum-image fractional difference, mapped to Å through a selectable
     lattice basis: reference / DFT / average);
  4. reports the average, RMS and maximum deviation, per-element statistics,
     a cell-parameter comparison, and a per-atom table;
  5. renders a Markdown or CSV report for download.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from utils import _file_path, _save_output, _save_upload

router = APIRouter()

# fileId -> original upload name (uploads land on disk under uuid ids; the
# report headings and export filenames should show what the user picked).
_name_registry: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Periodic-table helpers (element symbols only — no chemistry needed here)
# ---------------------------------------------------------------------------

_ELEMENTS = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg",
    "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca", "Sc", "Ti", "V", "Cr",
    "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br",
    "Kr", "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd",
    "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe", "Cs", "Ba", "La",
    "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er",
    "Tm", "Yb", "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au",
    "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu",
}


def _guess_element_from_name(name: str) -> Optional[str]:
    """Element symbol from a PDB atom-name field (``C1`` -> ``C``, ``Cl2`` ->
    ``Cl``).  Two-letter candidates are only accepted when the second
    character is lowercase (``Cl``) — uppercase pairs like ``CA`` are the
    PDB alpha-carbon convention, so only the first character is used unless
    the 2-letter form is an element AND the file's author lower-cased it."""
    s = "".join(ch for ch in name.strip() if ch.isalpha())
    if not s:
        return None
    if len(s) >= 2 and s[1].islower() and s[:2].capitalize() in _ELEMENTS:
        return s[:2].capitalize()
    if s[0] in _ELEMENTS:
        return s[0]
    if len(s) >= 2 and s[:2] in _ELEMENTS:
        return s[:2]
    return None


# ---------------------------------------------------------------------------
# PDB parsing (CP2K output: CRYST1 + ATOM records, optional MODEL frames)
# ---------------------------------------------------------------------------

class _ParsedStructure:
    """Lightweight structure container shared by the CIF and PDB loaders."""

    def __init__(self, lattice, species: List[str], frac: np.ndarray,
                 labels: List[str], fmt: str, n_models: int = 1):
        self.lattice = lattice            # pymatgen Lattice
        self.species = species            # element symbols
        self.frac = frac                  # (N, 3) fractional coords
        self.labels = labels
        self.format = fmt                 # "cif" | "pdb"
        self.n_models = n_models


def _parse_pdb(text: str, filename: str = "") -> _ParsedStructure:
    """Parse a CP2K-style PDB: CRYST1 cell + ATOM/HETATM sites.

    Multi-model files (geometry-optimisation trajectories) keep the LAST
    model — the final, relaxed geometry.  Coordinates are Cartesian Å per
    the PDB specification.
    """
    from pymatgen.core import Lattice

    cell = None
    models: List[List[dict]] = [[]]  # first block = implicit model 1
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        rec = line[:6].strip().upper()
        if rec == "CRYST1" and cell is None:
            # CRYST1 a b c alpha beta gamma [sg] [z]: values are 9-char
            # right-justified fields, but tolerate whitespace-separated
            # variants (some writers drift off-column).
            try:
                parts = line[6:54].split()
                if len(parts) < 6:
                    parts = line[6:].split()
                a, b, c, al, be, ga = (float(v) for v in parts[:6])
                cell = (a, b, c, al, be, ga)
            except (ValueError, TypeError):
                raise HTTPException(
                    400, f"PDB 的 CRYST1 晶胞行无法解析: {line.strip()!r}")
        elif rec in ("ATOM", "HETATM"):
            name = line[12:16].strip() if len(line) > 12 else ""
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except (ValueError, TypeError):
                # Off-column fallback: after the record, serial, name,
                # resName and resSeq tokens, the next three floats are x/y/z.
                toks = line.split()
                xyz: List[float] = []
                for k, t in enumerate(toks):
                    try:
                        v = float(t)
                    except ValueError:
                        continue
                    if len(xyz) < 3 and k >= 4:
                        xyz.append(v)
                if len(xyz) < 3:
                    raise HTTPException(
                        400, f"PDB 坐标行无法解析: {line.strip()!r}")
                x, y, z = xyz
            # Element: cols 77-78 are authoritative; CP2K fills them.
            elem = line[76:78].strip() if len(line) > 77 else ""
            cand = elem.capitalize() if elem else ""
            if cand in _ELEMENTS:
                elem = cand
            else:
                elem = _guess_element_from_name(name) or ""
            if not elem:
                raise HTTPException(
                    400, f"PDB 原子 {name or '?'} 无法确定元素种类"
                         f"（行: {line.strip()!r}）")
            models[-1].append({"name": name, "elem": elem, "xyz": (x, y, z)})
        elif rec == "MODEL":
            if models[-1]:
                models.append([])          # frame boundary
        elif rec == "ENDMDL":
            if len(models) == 1 and not models[0]:
                models = [[]]              # ENDMDL without MODEL — ignore
    # drop trailing empty blocks (e.g. ENDMDL after the last frame)
    models = [m for m in models if m]
    if not models:
        raise HTTPException(400, f"PDB 中没有 ATOM/HETATM 记录: {filename}")
    if cell is None:
        raise HTTPException(
            400, f"PDB 缺少 CRYST1 晶胞信息（CP2K 需开启胞胞输出）: {filename}")

    atoms = models[-1]
    a, b, c, al, be, ga = cell
    lattice = Lattice.from_parameters(a, b, c, al, be, ga)
    cart = np.array([at["xyz"] for at in atoms], dtype=float)
    frac = lattice.get_fractional_coords(cart)
    species = [at["elem"] for at in atoms]
    labels = [at["name"] or f"{at['elem']}{i + 1}" for i, at in enumerate(atoms)]
    return _ParsedStructure(lattice, species, frac, labels, "pdb",
                            n_models=len(models))


def _load_structure(file_id: str) -> _ParsedStructure:
    """Load an uploaded structure (CIF or PDB) by file-id."""
    from pymatgen.core import Structure

    path = _file_path(file_id)
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdb":
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return _parse_pdb(fh.read(), os.path.basename(path))
        structure = Structure.from_file(path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, detail=f"无法解析结构文件 ({ext}): {exc}")

    species = [str(s.specie) for s in structure]
    labels = []
    for i, site in enumerate(structure):
        # CIF sites carry their original labels (C1, O2, ...); regenerate
        # when absent — and uniquify when the file repeats bare symbols
        # (pymatgen's own writer emits 'C' twelve times).
        lab = str(getattr(site, "label", "") or "").strip() or f"{species[i]}{i + 1}"
        if lab in labels:
            lab = f"{species[i]}{i + 1}"
            k = 1
            while lab in labels:
                k += 1
                lab = f"{species[i]}{i + 1}#{k}"
        labels.append(lab)
    return _ParsedStructure(structure.lattice, species,
                            np.asarray(structure.frac_coords, dtype=float),
                            labels, "cif")


def _cell_dict(lattice) -> Dict[str, float]:
    return {
        "a": float(lattice.a), "b": float(lattice.b), "c": float(lattice.c),
        "alpha": float(lattice.alpha), "beta": float(lattice.beta),
        "gamma": float(lattice.gamma), "volume": float(lattice.volume),
    }


def _upload_meta(parsed: _ParsedStructure, file_id: str,
                 original_name: str, n_models: Optional[int] = None) -> Dict[str, Any]:
    counts: Dict[str, int] = defaultdict(int)
    for el in parsed.species:
        counts[el] += 1
    meta: Dict[str, Any] = {
        "fileId": file_id,
        "originalName": original_name,
        "format": parsed.format,
        "cell": {k: round(v, 5) for k, v in _cell_dict(parsed.lattice).items()},
        "nAtoms": len(parsed.species),
        "counts": dict(sorted(counts.items())),
    }
    if parsed.format == "pdb" and n_models is not None and n_models > 1:
        meta["nModels"] = n_models
    return meta


# ---------------------------------------------------------------------------
# Atom pairing
# ---------------------------------------------------------------------------

def _match_order(ref: _ParsedStructure, dft: _ParsedStructure
                 ) -> Tuple[np.ndarray, List[str]]:
    """Pair atom i with atom i.  Returns (dft_index_per_ref_index, warnings)."""
    warnings: List[str] = []
    n = len(ref.species)
    idx = np.arange(n)
    mism = [i for i in range(n) if ref.species[i] != dft.species[i]]
    if mism:
        warnings.append(
            f"两结构第 {mism[0] + 1} 号起的 {len(mism)} 个原子元素与序号不对应"
            f"（顺序不一致），已自动改用近邻匹配")
        idx2, _ = _match_nearest(ref, dft)
        return idx2, warnings
    return idx, warnings


def _match_nearest(ref: _ParsedStructure, dft: _ParsedStructure
                   ) -> Tuple[np.ndarray, List[str]]:
    """Nearest-neighbour pairing per element (Hungarian assignment).

    Cost = minimum-image Cartesian distance in the reference lattice.  This
    tolerates atom reordering (CP2K output) as long as displacements stay
    well below half a cell — the DFT-relaxed vs reference case.
    """
    from scipy.optimize import linear_sum_assignment

    n = len(ref.species)
    idx = np.full(n, -1, dtype=int)
    ref_groups: Dict[str, List[int]] = defaultdict(list)
    dft_groups: Dict[str, List[int]] = defaultdict(list)
    for i, el in enumerate(ref.species):
        ref_groups[el].append(i)
    for j, el in enumerate(dft.species):
        dft_groups[el].append(j)

    L = np.asarray(ref.lattice.matrix, dtype=float)
    for el, ri in ref_groups.items():
        dj = dft_groups.get(el)
        if not dj:
            raise HTTPException(
                400, detail=f"元素种类不一致: 参考结构含 {el}，DFT 结构不含。"
                            f"请确认两个文件描述的是同一结构。")
        if len(dj) != len(ri):
            raise HTTPException(
                400, detail=f"元素 {el} 数目不一致: 参考 {len(ri)} 个 / "
                            f"DFT {len(dj)} 个。请确认两个文件描述的是同一结构。")
        f1 = ref.frac[ri]                       # (m, 3)
        f2 = dft.frac[dj]                       # (m, 3)
        d = f2[:, None, :] - f1[None, :, :]     # (j, i, 3)
        d -= np.round(d)                        # minimum image
        cost = np.linalg.norm(d @ L, axis=-1)   # (j, i)
        jj, ii = linear_sum_assignment(cost)
        for j_pos, i_pos in zip(jj, ii):
            idx[ri[i_pos]] = dj[j_pos]
    return idx, []


# ---------------------------------------------------------------------------
# Deviation computation
# ---------------------------------------------------------------------------

_BASIS_FACTORS = {"ref": (1.0, 0.0), "dft": (0.0, 1.0), "avg": (0.5, 0.5)}


def _compare_structures(
    ref: _ParsedStructure, dft: _ParsedStructure,
    ref_meta: Dict[str, Any], dft_meta: Dict[str, Any],
    match: str, basis: str,
) -> Dict[str, Any]:
    warnings: List[str] = []
    n_ref, n_dft = len(ref.species), len(dft.species)
    if n_ref != n_dft:
        raise HTTPException(
            400, detail=f"原子数不一致: 参考 {n_ref} 个 / DFT {n_dft} 个。"
                        f"请确认两个文件描述的是同一结构（同一超胞）。")
    if match == "order":
        pair_idx, warnings = _match_order(ref, dft)
        _fell_back = any("自动改用近邻" in w for w in warnings)
    else:
        pair_idx, warnings = _match_nearest(ref, dft)
        _fell_back = False
        reordered = int((pair_idx != np.arange(n_ref)).sum())
        if reordered:
            warnings.append(
                f"近邻匹配: {reordered} 个原子的配对顺序与文件顺序不同"
                f"（CP2K 输出常见，已按最近位置配对）")

    wr, wd = _BASIS_FACTORS.get(basis, _BASIS_FACTORS["ref"])
    L = wr * np.asarray(ref.lattice.matrix, dtype=float) \
        + wd * np.asarray(dft.lattice.matrix, dtype=float)

    dfrac = dft.frac[pair_idx] - ref.frac
    dfrac -= np.round(dfrac)                   # minimum image
    dcart = dfrac @ L
    dist = np.linalg.norm(dcart, axis=1)

    atoms = []
    for i in range(n_ref):
        j = int(pair_idx[i])
        atoms.append({
            "i": i,
            "refLabel": ref.labels[i],
            "dftLabel": dft.labels[j],
            "element": ref.species[i],
            "dx": round(float(dcart[i, 0]), 5),
            "dy": round(float(dcart[i, 1]), 5),
            "dz": round(float(dcart[i, 2]), 5),
            "dist": round(float(dist[i]), 5),
        })

    imax = int(np.argmax(dist))
    per_el: Dict[str, Dict[str, Any]] = {}
    for row in atoms:
        slot = per_el.setdefault(row["element"], {"element": row["element"], "n": 0,
                                                  "_sum": 0.0, "_max": 0.0})
        slot["n"] += 1
        slot["_sum"] += row["dist"]
        slot["_max"] = max(slot["_max"], row["dist"])
    elements = []
    for el in sorted(per_el):
        slot = per_el[el]
        elements.append({
            "element": el, "n": slot["n"],
            "mean": round(slot["_sum"] / slot["n"], 5),
            "max": round(slot["_max"], 5),
        })

    # Cell comparison (lengths / angles / volume deltas).
    cr, cd = _cell_dict(ref.lattice), _cell_dict(dft.lattice)
    cell = {
        "ref": {k: round(v, 5) for k, v in cr.items()},
        "dft": {k: round(v, 5) for k, v in cd.items()},
        "delta": {k: round(cd[k] - cr[k], 5) for k in cr},
        "deltaPct": {k: round(100.0 * (cd[k] - cr[k]) / cr[k], 3) for k in cr},
    }
    dv = abs(cell["deltaPct"]["volume"])
    if dv > 1.0:
        warnings.append(
            f"晶胞体积变化 {dv:.2f}% 较大 — 偏差包含晶胞弛豫的贡献，"
            f"可在选项中更换位移基（参考/DFT/平均）观察其影响")

    if dft_meta.get("nModels"):
        warnings.append(
            f"PDB 含 {dft_meta['nModels']} 个 MODEL 帧，已取最后一帧（末态几何）")
    if ref_meta.get("nModels"):
        warnings.append(
            f"参考 PDB 含 {ref_meta['nModels']} 个 MODEL 帧，已取最后一帧")

    return {
        "match": match,
        "matchEffective": "nearest" if _fell_back else match,
        "basis": basis,
        "ref": ref_meta,
        "dft": dft_meta,
        "cell": cell,
        "stats": {
            "n": n_ref,
            "mean": round(float(dist.mean()), 5),
            "rms": round(float(np.sqrt((dist ** 2).mean())), 5),
            "median": round(float(np.median(dist)), 5),
            "min": round(float(dist.min()), 5),
            "max": round(float(dist.max()), 5),
            "maxAtom": ref.labels[imax],
            "maxIndex": imax,
        },
        "elements": elements,
        "atoms": atoms,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _render_markdown(p: Dict[str, Any]) -> str:
    ref_name = os.path.basename(p["ref"]["originalName"] or "reference")
    dft_name = os.path.basename(p["dft"]["originalName"] or "dft")
    s = p["stats"]
    match_label = {"order": "按序号", "nearest": "近邻匹配（匈牙利算法）"}[
        p.get("matchEffective", p["match"])]
    basis_label = {"ref": "参考晶胞", "dft": "DFT 晶胞", "avg": "两晶胞平均"}[
        p["basis"]]

    L: List[str] = []
    L.append("# 结构偏差报告 / Structure Deviation Report")
    L.append("")
    L.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"- 参考结构: `{ref_name}`（{p['ref']['format'].upper()}, "
             f"{p['ref']['nAtoms']} 原子）")
    L.append(f"- DFT 结构: `{dft_name}`（{p['dft']['format'].upper()}, "
             f"{p['dft']['nAtoms']} 原子）")
    L.append(f"- 原子配对: {match_label}")
    L.append(f"- 位移基: {basis_label}")
    L.append(f"- 周期性: 最小镜像（minimum image），单位 Å")
    L.append("")
    L.append("## 统计摘要")
    L.append("")
    L.append("| 指标 | 值 (Å) |")
    L.append("|---|---|")
    L.append(f"| 原子数 | {s['n']} |")
    L.append(f"| **平均偏差 (mean)** | **{s['mean']:.5f}** |")
    L.append(f"| 均方根偏差 (RMSD) | {s['rms']:.5f} |")
    L.append(f"| 中位数 | {s['median']:.5f} |")
    L.append(f"| 最小 | {s['min']:.5f} |")
    L.append(f"| **最大偏差 (max)** | **{s['max']:.5f}**（{s['maxAtom']}） |")
    L.append("")
    L.append("## 分元素统计")
    L.append("")
    L.append("| 元素 | 原子数 | 平均偏差 (Å) | 最大偏差 (Å) |")
    L.append("|---|---|---|---|")
    for e in p["elements"]:
        L.append(f"| {e['element']} | {e['n']} | {e['mean']:.5f} | {e['max']:.5f} |")
    L.append("")
    L.append("## 晶胞参数对比")
    L.append("")
    L.append("| 参数 | 参考 | DFT | Δ | Δ% |")
    L.append("|---|---|---|---|---|")
    _CELL_UNITS = {"a": "Å", "b": "Å", "c": "Å", "alpha": "°", "beta": "°",
                   "gamma": "°", "volume": "Å³"}
    for k in ("a", "b", "c", "alpha", "beta", "gamma", "volume"):
        L.append(f"| {k} ({_CELL_UNITS[k]}) | {p['cell']['ref'][k]:.5f} "
                 f"| {p['cell']['dft'][k]:.5f} | {p['cell']['delta'][k]:+.5f} "
                 f"| {p['cell']['deltaPct'][k]:+.3f}% |")
    L.append("")
    L.append("## 逐原子偏差")
    L.append("")
    L.append("| # | 参考 | DFT | 元素 | Δx (Å) | Δy (Å) | Δz (Å) | |Δ| (Å) |")
    L.append("|---|---|---|---|---|---|---|---|")
    for a in p["atoms"]:
        L.append(f"| {a['i'] + 1} | {a['refLabel']} | {a['dftLabel']} "
                 f"| {a['element']} | {a['dx']:+.5f} | {a['dy']:+.5f} "
                 f"| {a['dz']:+.5f} | **{a['dist']:.5f}** |")
    if p["warnings"]:
        L.append("")
        L.append("## 说明")
        L.append("")
        for w in p["warnings"]:
            L.append(f"- {w}")
    return "\n".join(L) + "\n"


def _render_csv(p: Dict[str, Any]) -> str:
    s = p["stats"]
    L: List[str] = []
    L.append(f"# 结构偏差报告 — mean={s['mean']:.5f} rms={s['rms']:.5f} "
             f"max={s['max']:.5f}({s['maxAtom']}) n={s['n']} "
             f"match={p['match']} basis={p['basis']}")
    L.append("ref_index,ref_label,dft_label,element,dx_A,dy_A,dz_A,dist_A")
    for a in p["atoms"]:
        L.append(f"{a['i'] + 1},{a['refLabel']},{a['dftLabel']},{a['element']},"
                 f"{a['dx']:.5f},{a['dy']:.5f},{a['dz']:.5f},{a['dist']:.5f}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CompareRequest(BaseModel):
    refFileId: str = Field(..., description="参考结构 file-id（优化前）")
    dftFileId: str = Field(..., description="DFT 优化后结构 file-id")
    match: str = Field("nearest", description="原子配对: nearest=近邻匹配 | order=按序号")
    basis: str = Field("ref", description="位移基晶胞: ref | dft | avg")


class ReportRequest(CompareRequest):
    format: str = Field("md", description="报告格式: md | csv")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload")
def upload_structure(file: UploadFile = File(...)):
    """Upload a structure file (CIF or CP2K PDB) and return its summary."""
    try:
        raw = file.file.read()
        name = file.filename or "structure"
        ext = os.path.splitext(name)[1].lower()
        if ext not in (".cif", ".pdb"):
            raise HTTPException(400, detail=f"不支持的文件类型 {ext}，请上传 .cif 或 .pdb")
        fid = _save_upload(raw, suffix=ext)
        parsed = _load_structure(fid)
        _name_registry[fid] = name
        n_models = parsed.n_models if parsed.format == "pdb" else None
        return _upload_meta(parsed, fid, name, n_models)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


def _run_compare(req: CompareRequest) -> Dict[str, Any]:
    if req.match not in ("nearest", "order"):
        raise HTTPException(400, detail="match 必须是 nearest 或 order")
    if req.basis not in ("ref", "dft", "avg"):
        raise HTTPException(400, detail="basis 必须是 ref、dft 或 avg")
    ref = _load_structure(req.refFileId)
    dft = _load_structure(req.dftFileId)
    ref_meta = _upload_meta(ref, req.refFileId,
                            _name_registry.get(req.refFileId, "reference.cif"))
    dft_meta = _upload_meta(dft, req.dftFileId,
                            _name_registry.get(req.dftFileId, "dft.pdb"))
    return _compare_structures(ref, dft, ref_meta, dft_meta,
                               req.match, req.basis)


@router.post("/compare")
def compare_structures(req: CompareRequest):
    """Pair the atoms of the two structures and return all deviations."""
    try:
        return _run_compare(req)
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=str(exc))


@router.post("/report")
def generate_report(req: ReportRequest):
    """Render the comparison as a Markdown or CSV report file."""
    try:
        payload = _run_compare(req)
        fmt = req.format if req.format in ("md", "csv") else "md"
        text = _render_markdown(payload) if fmt == "md" else _render_csv(payload)

        ref_base = os.path.splitext(os.path.basename(
            payload["ref"].get("originalName") or "reference"))[0]
        dft_base = os.path.splitext(os.path.basename(
            payload["dft"].get("originalName") or "dft"))[0]
        filename = f"{ref_base}_vs_{dft_base}_deviation.{fmt}"

        fid = _save_output(text.encode("utf-8"), suffix=f".{fmt}")
        return {"fileId": fid, "filename": filename, "format": fmt,
                "text": text, "stats": payload["stats"]}
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=str(exc))


@router.get("/task/{taskId}/download")
def task_download(taskId: str):
    """Download a generated report."""
    from fastapi.responses import FileResponse

    path = _file_path(taskId)
    ext = os.path.splitext(path)[1].lower()
    media = "text/markdown" if ext == ".md" else "text/csv"
    return FileResponse(path, filename=os.path.basename(path), media_type=media)
