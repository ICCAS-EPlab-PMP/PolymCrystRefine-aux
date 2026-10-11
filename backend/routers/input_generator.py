"""
Input Generator router — refine input.txt builder.

Generates the ``input.txt`` configuration file consumed by the Fortran
refinement engine and the Python GA/init-helix pipeline.  The format
strictly follows ``reference/INPUT_LIST.md`` (updated 260822: xraylib
physical keys, equatorial module 260814, advanced multi-molecule 260815,
DeepSearch post-refinement).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models — mirror every section of INPUT_LIST.md
# ---------------------------------------------------------------------------

class CoordinateAtom(BaseModel):
    """One row of the ``coordinate`` block."""
    element: str = Field(..., description="Element symbol, e.g. O, C, H")
    r_min: float = Field(0.0, description="r random range lower bound")
    r_max: float = Field(2.0, description="r random range upper bound")
    z_idx: int = Field(1, description="z position index (0 = z forced to 0)")


class ChainCenter(BaseModel):
    """One row of the ``chain_center`` block."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class SpaceGroupOp(BaseModel):
    """One symmetry operation (2 lines)."""
    transdirect: List[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])
    center_move: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class CellParams(BaseModel):
    """Unit-cell parameters — all six values required (no silent defaults)."""
    a: Optional[float] = None
    b: Optional[float] = None
    c: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    gamma: Optional[float] = None


class MoleculeBlock(BaseModel):
    """One ``molecule N begin … end molecule`` block (advanced multi-molecule
    mode, version 260815).  Contains its own coordinate list and forcefield
    file name."""
    coordinate: List[CoordinateAtom] = Field(default_factory=list)
    forcefield: str = Field("", description="Per-molecule forcefield file, e.g. forcefield_mol1.txt")


class GenerateInputRequest(BaseModel):
    """All parameters that go into ``input.txt``."""

    # ---- 3.1 Basic required ----
    wavelength: float = Field(1.24, description="X-ray wavelength (Å)")
    generation_num: int = Field(400, ge=1, description="Population / generation count")
    num_atoms: int = Field(22, ge=1, description="Atoms per asymmetric unit (ignored in advanced mode)")
    chain_num: int = Field(1, ge=1, description="Number of helical chains (must NOT appear in advanced mode)")

    # ---- 3.2 Python build required ----
    z_min: Optional[float] = Field(None, description="Per-period z random range lower (Å)")
    z_max: Optional[float] = Field(None, description="Per-period z random range upper (Å)")
    c_length: Optional[float] = Field(None, description="Expected full-period c-axis length (Å)")
    main_chain_num: Optional[int] = Field(None, description="Main-chain monomer count")

    # ---- 3.3 Intensity weight ----
    intensity_contribution: float = Field(400.0, description="Diffraction residual weight")

    # ---- 3.4 Output control ----
    print_level: str = Field("medium", description="low | medium | high")
    chemical_formula: Optional[str] = Field(None, description="Repeat-unit formula, required when use_xraylib=on")

    # ---- 3.5 Temperature factor ----
    temperature_factor_stat: int = Field(0, description="0 = isotropic (only supported); 1 = anisotropic")
    temperature_factor_min: float = Field(0.15, description="B-factor lower bound")
    temperature_factor_max: float = Field(0.35, description="B-factor upper bound")

    # ---- 3.6 LM ----
    status_LM: str = Field("NO", description="YES or NO")
    tol: float = Field(1e-3, description="Convergence tolerance (only when LM=YES)")
    maxcall: int = Field(500, description="Max iterations (only when LM=YES)")

    # ---- 3.7 Helix / geometry ----
    period_num: int = Field(1, ge=1, description="Number of periods")
    helix_num: float = Field(0.0, ge=0, description="Helix number (≥0)")
    theta_add: float = Field(0.0, description="Adjacent-period rotation angle (deg)")

    # ---- 3.8 Mode switches ----
    single_chain_mod: int = Field(0, description="0 or 1")
    xray_source_mod: int = Field(0, description="0=synchrotron; 1=lab; other=pol factor 1")
    stable_z_chain: int = Field(0, description="0 or 1 — force all z_ini = 0")
    mirror_chain: int = Field(0, description="0 / 1 / 2")

    # ---- 3.9 Chain & space group ----
    space_group_num: int = Field(0, ge=0, description="Number of non-identity symmetry ops")

    # ---- 3.10 Phase 2: independent chains / pseudo-symmetry ----
    n_independent_chains: Optional[int] = Field(None, description="1..chain_num")
    theta_ini_map: Optional[List[int]] = Field(None, description="length = chain_num")
    build_order: int = Field(0, description="0 or 1")
    pseudo_symmetry_mode: int = Field(0, description="0-3")

    # ---- 3.11 Phase 5: multi-phase (skeleton) ----
    num_phases: int = Field(1, description="Must be 1")
    phase_weight: float = Field(1.0, description="Phase weight")

    # ---- 3.12 Phase 6: experimental / correction ----
    molecular_mass: float = Field(224.0)
    sample_absorption_coeff: float = Field(6.2925)
    sample_thickness_cm: float = Field(0.336)
    air_absorption_coeff: float = Field(9.93)
    air_density: float = Field(0.001293)
    detector_distance_cm: float = Field(19.894)
    h_max: int = Field(5, ge=0)
    k_max: int = Field(5, ge=0)
    l_max: int = Field(20, ge=0)
    max_hkl_per_peak: int = Field(50, ge=1)
    max_blank_hkl: int = Field(2000, ge=1)
    blank_contribution: float = Field(0.20, ge=0)
    q_min: float = Field(0.0, ge=0)

    # ---- 3.12 xraylib physical calculation [version 260822] ----
    use_xraylib: str = Field("off", description="on = μ/ρ, M_cell and f0 from xraylib; off = legacy values")

    # ---- 3.12.1 Equatorial module [version 260814, all optional] ----
    equatorial_blank_contribution: Optional[float] = Field(
        None, ge=0, description="Separate l=0 blank weight; unset = follow blank_contribution")
    equatorial_profile_file: Optional[str] = Field(
        None, description="Equatorial 1D observed profile file; unset = feature disabled")
    equatorial_profile_contribution: float = Field(1.0, ge=0)
    equatorial_peak_fwhm: float = Field(0.04)
    equatorial_pv_eta: float = Field(0.5)
    equatorial_background: float = Field(0.0)
    equatorial_h_max: Optional[int] = Field(None, ge=0, description="unset = follow h_max")
    equatorial_k_max: Optional[int] = Field(None, ge=0, description="unset = follow k_max")

    # ---- 3.12.2 Advanced multi-molecule mode [version 260815] ----
    advanced_multi_molecule: str = Field("off", description="off | case_a | case_b")
    molecule1: MoleculeBlock = Field(default_factory=MoleculeBlock)
    molecule2: MoleculeBlock = Field(default_factory=MoleculeBlock)
    molecular_mass_mol1: float = Field(224.0)
    molecular_mass_mol2: float = Field(224.0)
    data_param_ratio_warn: float = Field(3.0, description="N_info/N_par red warning line (must be > 1)")
    axis_penalty_weight: float = Field(0.0, ge=0, description="Axial-offset penalty weight (0 = off)")
    mixture_fractions: Optional[List[float]] = Field(
        None, description="case_b only: p1 p2 p12, each > 0, sum = 1; unset = random init")
    mixture_fractions_fixed: str = Field("no", description="yes = fractions fixed during LM (case_b)")

    # ---- 3.13 GA parameters ----
    ga_steps: int = Field(100)
    ga_result_dir: str = Field("result")
    ga_mode: str = Field("basic", description="basic | flash | pro")
    # DeepSearch post-refinement (basic mode only)
    deep_search: str = Field("off", description="off | on — post case_a dual-molecule refinement")
    deepsearch_steps: int = Field(2, ge=1)
    deepsearch_start_topk: int = Field(1, ge=1, description="V1 supports only 1")
    # flash mode
    freeze_threshold_r: float = Field(0.02, ge=0)
    freeze_threshold_phi: float = Field(0.5, ge=0)
    freeze_threshold_z: float = Field(0.02, ge=0)
    freeze_threshold_sq: float = Field(0.01, ge=0)
    freeze_streak_k: int = Field(3, ge=0)
    warmup_percent: float = Field(0.1)
    warmup_generations: int = Field(0, ge=0)
    # pro mode
    pro_max_age: int = Field(50, ge=1)
    elite_ratio: float = Field(0.2)
    pro_aggressive_ratio_early: float = Field(0.9)
    pro_aggressive_ratio_late: float = Field(0.8)
    pro_schedule_crossover_point: float = Field(0.5)
    dedup_threshold_r: float = Field(0.01, ge=0)
    dedup_threshold_phi: float = Field(0.3, ge=0)
    dedup_threshold_z: float = Field(0.01, ge=0)

    # ---- Data blocks ----
    coordinate: List[CoordinateAtom] = Field(default_factory=list)
    cell: CellParams = Field(default_factory=CellParams)
    chain_centers: List[ChainCenter] = Field(default_factory=list)
    space_group_ops: List[SpaceGroupOp] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation (INPUT_LIST.md §8) — reject invalid combinations with HTTP 400
# ---------------------------------------------------------------------------

def _validate(req: GenerateInputRequest) -> None:
    adv = req.advanced_multi_molecule.strip().lower()
    if adv not in ("off", "case_a", "case_b"):
        raise HTTPException(400, "advanced_multi_molecule must be off / case_a / case_b")
    if req.print_level not in ("low", "medium", "high"):
        raise HTTPException(400, "print_level must be low / medium / high")
    if req.ga_mode not in ("basic", "flash", "pro"):
        raise HTTPException(400, "ga_mode must be basic / flash / pro")
    if req.use_xraylib not in ("on", "off"):
        raise HTTPException(400, "use_xraylib must be on / off")
    if req.use_xraylib == "on" and not (req.chemical_formula or "").strip():
        raise HTTPException(400, "chemical_formula is required when use_xraylib = on "
                                 "(ERROR STOP at startup otherwise)")
    if req.data_param_ratio_warn <= 1:
        raise HTTPException(400, "data_param_ratio_warn must be > 1")

    # Cell: all six values mandatory — a missing value must not silently fall
    # back to the old example defaults (5.9897 4.5159 …).
    cell_vals = {
        "a": req.cell.a, "b": req.cell.b, "c": req.cell.c,
        "alpha": req.cell.alpha, "beta": req.cell.beta, "gamma": req.cell.gamma,
    }
    missing = [k for k, v in cell_vals.items() if v is None]
    if missing:
        raise HTTPException(400, f"cell parameters missing: {', '.join(missing)} "
                                 f"(all 6 of a b c alpha beta gamma are required)")
    if min(req.cell.a, req.cell.b, req.cell.c) <= 0:
        raise HTTPException(400, "cell lengths a, b, c must be > 0")
    if not all(0.0 < ang < 180.0 for ang in (req.cell.alpha, req.cell.beta, req.cell.gamma)):
        raise HTTPException(400, "cell angles alpha, beta, gamma must lie in (0, 180) degrees")

    if adv != "off":
        # Advanced mode gating (INPUT_LIST.md §3.12.2 / §8)
        if req.single_chain_mod != 0:
            raise HTTPException(400, "advanced multi-molecule mode requires single_chain_mod = 0")
        if req.space_group_num != 0:
            raise HTTPException(400, "advanced multi-molecule mode requires space_group_num = 0 (V1: P1 only)")
        if req.stable_z_chain != 0 or req.mirror_chain != 0 or req.build_order != 0:
            raise HTTPException(400, "advanced multi-molecule mode requires stable_z_chain = 0, "
                                     "mirror_chain = 0 and build_order = 0")
        if req.pseudo_symmetry_mode != 0 or req.n_independent_chains is not None or req.theta_ini_map is not None:
            raise HTTPException(400, "theta bucket / pseudo-symmetry keys are disabled in advanced mode")
        if not req.molecule1.coordinate or not req.molecule2.coordinate:
            raise HTTPException(400, "both molecule blocks need at least one coordinate row")
        if not req.molecule1.forcefield.strip() or not req.molecule2.forcefield.strip():
            raise HTTPException(400, "each molecule block needs its forcefield file name "
                                     "(e.g. forcefield_mol1.txt / forcefield_mol2.txt)")
        if adv == "case_b":
            if req.equatorial_profile_file:
                raise HTTPException(400, "case_b is mutually exclusive with equatorial_profile_file "
                                         "(input check rejects this combination)")
            if req.mixture_fractions is not None:
                mf = req.mixture_fractions
                if len(mf) != 3 or any(v <= 0 for v in mf) or abs(sum(mf) - 1.0) > 1e-3:
                    raise HTTPException(400, "mixture_fractions must be 3 positive values summing to 1 "
                                             "(p1 p2 p12, tolerance 1e-3)")
            if req.mixture_fractions_fixed.strip().lower() == "yes" and req.mixture_fractions is None:
                raise HTTPException(400, "mixture_fractions_fixed = yes requires explicit mixture_fractions")
        return

    # ---- Standard-mode checks ----
    if req.pseudo_symmetry_mode not in (0, 1, 2, 3):
        raise HTTPException(400, "pseudo_symmetry_mode must be 0..3")
    if req.theta_ini_map is not None and req.n_independent_chains is None:
        raise HTTPException(400, "theta_ini_map requires n_independent_chains to be given explicitly")
    if req.n_independent_chains is not None:
        if not (1 <= req.n_independent_chains <= req.chain_num):
            raise HTTPException(400, "n_independent_chains must satisfy 1 <= n <= chain_num")
        if req.n_independent_chains < req.chain_num and req.theta_ini_map is None:
            raise HTTPException(400, "n_independent_chains < chain_num requires theta_ini_map")
    if req.build_order not in (0, 1):
        raise HTTPException(400, "build_order must be 0 or 1")

    if req.pseudo_symmetry_mode > 1:
        # v1 gating (INPUT_LIST.md §3.10)
        n = req.n_independent_chains
        m = req.theta_ini_map
        if req.mirror_chain != 0:
            raise HTTPException(400, "pseudo_symmetry_mode > 1 requires mirror_chain = 0")
        if n is None or n >= req.chain_num:
            raise HTTPException(400, "pseudo_symmetry_mode > 1 requires explicit n_independent_chains < chain_num")
        if m is None or len(m) != req.chain_num:
            raise HTTPException(400, "pseudo_symmetry_mode > 1 requires theta_ini_map of length chain_num")
        if req.chain_num % 2 != 0:
            raise HTTPException(400, "pseudo_symmetry_mode > 1 requires an even chain_num")
        if set(m) != set(range(1, n + 1)):
            raise HTTPException(400, f"theta_ini_map must use every bucket id 1..{n}")
        if len(set(m)) < 2:
            raise HTTPException(400, "theta_ini_map must contain at least 2 distinct bucket ids "
                                     "(degenerate pairing like [1,1,1,1] is rejected)")

    if req.equatorial_profile_file and req.equatorial_peak_fwhm <= 0:
        raise HTTPException(400, "equatorial_peak_fwhm must be > 0")
    if req.equatorial_profile_file and not (0.0 <= req.equatorial_pv_eta <= 1.0):
        raise HTTPException(400, "equatorial_pv_eta must lie in [0, 1]")

    if req.deep_search.strip().lower() == "on":
        if req.ga_mode != "basic":
            raise HTTPException(400, "deep_search = on requires ga_mode = basic")
        if req.chain_num != 2:
            raise HTTPException(400, "deep_search = on requires chain_num = 2")
        if req.stable_z_chain != 0:
            raise HTTPException(400, "deep_search = on requires stable_z_chain = 0")


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def _format_val(v) -> str:
    """Format a Python value for input.txt key=value lines."""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        # Use .6g to avoid overly long decimals; prepend a leading zero for
        # values like ".15" → "0.15" (Fortran list-directed read is fine with
        # either, but the spec examples use "0.15").
        s = f"{v:.6g}"
        if s.startswith("."):
            s = "0" + s
        elif s.startswith("-."):
            s = "-0" + s[1:]
        return s
    return str(v)


def _emit_kv(key: str, value, lines: List[str]) -> None:
    """Append a ``key = value`` line."""
    lines.append(f"{key} = {_format_val(value)}")


def _emit_optional(lines: List[str], key: str, value) -> None:
    """Emit a key=value line only when the value is not None."""
    if value is not None:
        _emit_kv(key, value, lines)


def _emit_coordinate_block(rows: List[CoordinateAtom], indent: str, lines: List[str]) -> None:
    # Same layout as the top-level block: no end marker — the row count comes
    # from the num_atoms key that precedes it.
    lines.append(f"{indent}coordinate")
    for atom in rows:
        lines.append(f"{indent}{atom.element} {_format_val(atom.r_min)} "
                     f"{_format_val(atom.r_max)} {atom.z_idx}")


def generate_input_txt(req: GenerateInputRequest) -> str:
    """Build the complete ``input.txt`` content from a request."""

    _validate(req)

    advanced = req.advanced_multi_molecule.strip().lower() != "off"
    xraylib_on = req.use_xraylib.strip().lower() == "on"
    lm_on = req.status_LM.strip().upper() == "YES"

    lines: List[str] = []

    # ---- Comment header ----
    lines.append("# ============================================================")
    lines.append("# input.txt — generated by PolymCrystRefine Input Generator")
    lines.append("# Format per INPUT_LIST.md (reference/)")
    if advanced:
        lines.append(f"# Advanced multi-molecule mode: {req.advanced_multi_molecule.strip().lower()}")
    lines.append("# ============================================================")
    lines.append("")

    # ---- 3.1 Basic required ----
    lines.append("# ===== 基础必填 (Fortran 读取) =====")
    _emit_kv("wavelength", req.wavelength, lines)
    _emit_kv("generation_num", req.generation_num, lines)
    if advanced:
        # num_atoms = sum of both molecule blocks; chain_num must NOT appear
        n_total = len(req.molecule1.coordinate) + len(req.molecule2.coordinate)
        _emit_kv("num_atoms", n_total, lines)
    else:
        _emit_kv("num_atoms", req.num_atoms, lines)
    _emit_kv("intensity_contribution", req.intensity_contribution, lines)
    lines.append("")

    # ---- coordinate blocks ----
    if advanced:
        lines.append("# ===== molecule 块 (高级多分子模式，两块都必需) =====")
        for idx, mol in enumerate((req.molecule1, req.molecule2), start=1):
            lines.append(f"molecule {idx} begin")
            _emit_kv("num_atoms", len(mol.coordinate), lines)
            _emit_coordinate_block(mol.coordinate, "  ", lines)
            _emit_kv("forcefield", mol.forcefield.strip(), lines)
            lines.append(f"end molecule {idx}")
            lines.append("")
    else:
        lines.append("# ===== coordinate 块 (Python 用，行数 = num_atoms) =====")
        lines.append("coordinate")
        for atom in req.coordinate:
            lines.append(f"{atom.element} {_format_val(atom.r_min)} "
                         f"{_format_val(atom.r_max)} {atom.z_idx}")
        if not req.coordinate:
            lines.append("# (no atoms — add rows here: element r_min r_max z_idx)")
        lines.append("")

    # ---- B factor ----
    lines.append("# ===== B 因子 =====")
    _emit_kv("temperature_factor_stat", req.temperature_factor_stat, lines)
    _emit_kv("temperature_factor_min", req.temperature_factor_min, lines)
    _emit_kv("temperature_factor_max", req.temperature_factor_max, lines)
    lines.append("")

    # ---- LM ----
    lines.append("# ===== LM =====")
    _emit_kv("status_LM", req.status_LM, lines)
    if lm_on:
        # tol/maxcall are ignored while status_LM = NO — only emit when active
        _emit_kv("tol", req.tol, lines)
        _emit_kv("maxcall", req.maxcall, lines)
    lines.append("")

    # ---- Chain & space group ----
    lines.append("# ===== 链与空间群 =====")
    if not advanced:
        # chain_num must NOT appear in advanced mode (positions implied, fixed 2)
        _emit_kv("chain_num", req.chain_num, lines)
    _emit_kv("space_group_num", req.space_group_num, lines)
    lines.append("")

    # chain_center block (used in advanced mode too: case_a one center per
    # molecule, case_b both molecules share the same centers)
    lines.append("chain_center_begin")
    n_chains = 2 if advanced else req.chain_num
    emitted = min(len(req.chain_centers), n_chains)
    for cc in req.chain_centers[:emitted]:
        lines.append(f"{_format_val(cc.x)} {_format_val(cc.y)} {_format_val(cc.z)}")
    for _ in range(n_chains - emitted):
        lines.append("0.0 0.0 0.0")
    lines.append("chain_center_end")
    lines.append("")

    # ---- Helix (Fortran) ----
    lines.append("# ===== 螺旋 (Fortran) =====")
    _emit_kv("theta_add", req.theta_add, lines)
    _emit_kv("period_num", req.period_num, lines)
    _emit_kv("helix_num", req.helix_num, lines)
    lines.append("")

    # ---- Python build required ----
    if any(v is not None for v in [req.z_min, req.z_max, req.c_length, req.main_chain_num]):
        lines.append("# ===== Python 端构建必填 (init-helix / GA 用) =====")
        _emit_optional(lines, "z_min", req.z_min)
        _emit_optional(lines, "z_max", req.z_max)
        _emit_optional(lines, "c_length", req.c_length)
        _emit_optional(lines, "main_chain_num", req.main_chain_num)
        lines.append("")

    # ---- Cell block ----
    lines.append("# ===== cell 块 =====")
    lines.append("cell")
    lines.append(
        f"{_format_val(req.cell.a)} {_format_val(req.cell.b)} {_format_val(req.cell.c)} "
        f"{_format_val(req.cell.alpha)} {_format_val(req.cell.beta)} {_format_val(req.cell.gamma)}"
    )
    lines.append("")

    # ---- Mode switches ----
    lines.append("# ===== 模式开关 =====")
    _emit_kv("single_chain_mod", req.single_chain_mod, lines)
    _emit_kv("xray_source_mod", req.xray_source_mod, lines)
    _emit_kv("stable_z_chain", req.stable_z_chain, lines)
    _emit_kv("mirror_chain", req.mirror_chain, lines)
    lines.append("")

    # ---- Output ----
    lines.append("# ===== 输出 =====")
    _emit_kv("print_level", req.print_level, lines)
    lines.append("")

    # ---- xraylib physical calculation [260822] ----
    if xraylib_on:
        lines.append("# ===== xraylib 物理计算 (μ/ρ、M_cell、f0 由组成+波长自动计算) =====")
        _emit_kv("use_xraylib", "on", lines)
        _emit_kv("chemical_formula", (req.chemical_formula or "").strip(), lines)
        lines.append("")

    # ---- Phase 2 (disabled in advanced mode — validated above) ----
    if not advanced and (req.pseudo_symmetry_mode > 0 or req.n_independent_chains is not None
                         or req.theta_ini_map is not None):
        lines.append("# ===== Phase 2: 独立链 / 伪对称 =====")
        _emit_optional(lines, "n_independent_chains", req.n_independent_chains)
        if req.theta_ini_map is not None:
            map_str = " ".join(str(x) for x in req.theta_ini_map)
            lines.append(f"theta_ini_map = {map_str}")
        _emit_kv("build_order", req.build_order, lines)
        _emit_kv("pseudo_symmetry_mode", req.pseudo_symmetry_mode, lines)
        lines.append("")

    # ---- space_group block ----
    if req.space_group_num > 0:
        lines.append("space_group_begin")
        for op in req.space_group_ops:
            lines.append(" ".join(_format_val(v) for v in op.transdirect))
            lines.append(" ".join(_format_val(v) for v in op.center_move))
        lines.append("space_group_end")
        lines.append("")

    # ---- Phase 5 ----
    lines.append("# ===== Phase 5: 多相 (当前骨架) =====")
    _emit_kv("num_phases", req.num_phases, lines)
    _emit_kv("phase_weight", req.phase_weight, lines)
    lines.append("")

    # ---- Phase 6: Experimental / correction ----
    lines.append("# ===== Phase 6: 实验 / 校正参数 =====")
    if xraylib_on:
        # explicit values would override the xraylib auto-derived ones — omit
        # molecular_mass / sample_absorption_coeff / air_absorption_coeff so
        # the auto values are used
        lines.append("# (molecular_mass / sample_absorption_coeff / air_absorption_coeff "
                     "由 xraylib 自动推导，不写出)")
    else:
        _emit_kv("molecular_mass", req.molecular_mass, lines)
        _emit_kv("sample_absorption_coeff", req.sample_absorption_coeff, lines)
        _emit_kv("air_absorption_coeff", req.air_absorption_coeff, lines)
    _emit_kv("sample_thickness_cm", req.sample_thickness_cm, lines)
    _emit_kv("air_density", req.air_density, lines)
    _emit_kv("detector_distance_cm", req.detector_distance_cm, lines)
    _emit_kv("h_max", req.h_max, lines)
    _emit_kv("k_max", req.k_max, lines)
    _emit_kv("l_max", req.l_max, lines)
    _emit_kv("max_hkl_per_peak", req.max_hkl_per_peak, lines)
    _emit_kv("max_blank_hkl", req.max_blank_hkl, lines)
    _emit_kv("blank_contribution", req.blank_contribution, lines)
    _emit_kv("q_min", req.q_min, lines)
    lines.append("")

    # ---- 3.12.1 Equatorial module [260814] ----
    eq_blank = req.equatorial_blank_contribution
    eq_file = (req.equatorial_profile_file or "").strip()
    if eq_blank is not None or eq_file:
        lines.append("# ===== 赤道面模块 [260814] =====")
        if eq_blank is not None:
            _emit_kv("equatorial_blank_contribution", eq_blank, lines)
        if eq_file:
            _emit_kv("equatorial_profile_file", eq_file, lines)
            _emit_kv("equatorial_profile_contribution", req.equatorial_profile_contribution, lines)
            _emit_kv("equatorial_peak_fwhm", req.equatorial_peak_fwhm, lines)
            _emit_kv("equatorial_pv_eta", req.equatorial_pv_eta, lines)
            _emit_kv("equatorial_background", req.equatorial_background, lines)
            _emit_optional(lines, "equatorial_h_max", req.equatorial_h_max)
            _emit_optional(lines, "equatorial_k_max", req.equatorial_k_max)
        lines.append("")

    # ---- 3.12.2 Advanced multi-molecule extras [260815] ----
    if advanced:
        mode = req.advanced_multi_molecule.strip().lower()
        lines.append(f"# ===== 高级多分子模式 [{mode}] =====")
        _emit_kv("advanced_multi_molecule", mode, lines)
        _emit_kv("molecular_mass_mol1", req.molecular_mass_mol1, lines)
        _emit_kv("molecular_mass_mol2", req.molecular_mass_mol2, lines)
        _emit_kv("data_param_ratio_warn", req.data_param_ratio_warn, lines)
        if req.axis_penalty_weight > 0:
            _emit_kv("axis_penalty_weight", req.axis_penalty_weight, lines)
        if mode == "case_b":
            if req.mixture_fractions is not None:
                frac_str = " ".join(_format_val(v) for v in req.mixture_fractions)
                lines.append(f"mixture_fractions = {frac_str}")
                _emit_kv("mixture_fractions_fixed", req.mixture_fractions_fixed, lines)
        lines.append("")

    # ---- GA ----
    lines.append("# ===== GA =====")
    _emit_kv("ga_steps", req.ga_steps, lines)
    _emit_kv("ga_result_dir", req.ga_result_dir, lines)
    _emit_kv("ga_mode", req.ga_mode, lines)

    if req.ga_mode == "flash":
        lines.append("# flash 模式专属")
        _emit_kv("freeze_threshold_r", req.freeze_threshold_r, lines)
        _emit_kv("freeze_threshold_phi", req.freeze_threshold_phi, lines)
        _emit_kv("freeze_threshold_z", req.freeze_threshold_z, lines)
        _emit_kv("freeze_threshold_sq", req.freeze_threshold_sq, lines)
        _emit_kv("freeze_streak_k", req.freeze_streak_k, lines)
        _emit_kv("warmup_percent", req.warmup_percent, lines)
        _emit_kv("warmup_generations", req.warmup_generations, lines)

    if req.ga_mode == "pro":
        lines.append("# pro 模式专属")
        _emit_kv("pro_max_age", req.pro_max_age, lines)
        _emit_kv("elite_ratio", req.elite_ratio, lines)
        _emit_kv("pro_aggressive_ratio_early", req.pro_aggressive_ratio_early, lines)
        _emit_kv("pro_aggressive_ratio_late", req.pro_aggressive_ratio_late, lines)
        _emit_kv("pro_schedule_crossover_point", req.pro_schedule_crossover_point, lines)
        _emit_kv("dedup_threshold_r", req.dedup_threshold_r, lines)
        _emit_kv("dedup_threshold_phi", req.dedup_threshold_phi, lines)
        _emit_kv("dedup_threshold_z", req.dedup_threshold_z, lines)

    # DeepSearch post-refinement (basic mode only)
    if req.deep_search.strip().lower() == "on":
        lines.append("# DeepSearch 后置多分子精修 (仅 basic GA)")
        _emit_kv("deep_search", "on", lines)
        _emit_kv("deepsearch_steps", req.deepsearch_steps, lines)
        _emit_kv("deepsearch_start_topk", req.deepsearch_start_topk, lines)

    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_class=PlainTextResponse)
def generate_input(req: GenerateInputRequest):
    """Generate the ``input.txt`` content from the supplied parameters and
    return it as plain text (suitable for download)."""
    try:
        text = generate_input_txt(req)
        return PlainTextResponse(content=text, media_type="text/plain")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/generate-download", response_class=PlainTextResponse)
def generate_input_download(req: GenerateInputRequest):
    """Same as /generate but returns a Content-Disposition attachment."""
    try:
        text = generate_input_txt(req)
        return PlainTextResponse(
            content=text,
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=input.txt"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))
