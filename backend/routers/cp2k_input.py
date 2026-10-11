"""
CP2K FIBER_DIFFRACTION input router.

Generates the ``&FIBER_DIFFRACTION`` section for CP2K-Polymcryst-Refine
(v1.1, xraylib auto-absorption) — the fiber-diffraction bias block that our
custom CP2K build reads inside ``&FORCE_EVAL``.  Only the diffraction section
is produced; the rest of the CP2K input (&GLOBAL / &CELL / &COORD / &DFT /
&MOTION) is untouched by this generator.

Reference: ``reference/CP2K/README.md`` §6 and
``reference/CP2K/fiber_v11_sample.inp``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

router = APIRouter()


class Cp2kFiberRequest(BaseModel):
    """Parameters of the ``&FIBER_DIFFRACTION`` section (v1.1)."""

    # ---- minimal form (README §6: 5 keywords suffice) ----
    enabled: bool = Field(True, description="ENABLED switch of the section")
    diffraction_file: str = Field("diffraction_intensity.txt",
                                  description="peak/ROI table, same format as refine.f90")
    wavelength: float = Field(1.24, gt=0,
                              description="WAVELENGTH [Å] — the only energy entry; "
                                          "E = 12.3984/WAVELENGTH keV (no [angstrom] suffix)")
    auto_scale: bool = Field(True, description="AUTO_SCALE — per-step weighted LSQ re-fit of k "
                                               "(recommended start); .FALSE. uses fixed SCALE_FACTOR")
    scale_factor: float = Field(1.0,
                                description="SCALE_FACTOR — fixed intensity scale k "
                                            "(only meaningful with AUTO_SCALE .FALSE.)")
    lambda_: float = Field(1.0e-2, gt=0,
                           description="LAMBDA — coupling strength [hartree]; start small, "
                                       "tune via FIBER| fiber/DFT ratio",
                           alias="lambda")

    # ---- common optional keywords (defaults per README §6) ----
    sample_thickness_cm: float = Field(0.03, gt=0)
    detector_distance_cm: float = Field(19.894, gt=0)
    xray_mode: int = Field(0, description="0=synchrotron, 1=lab source, other=no polarization factor")
    h_max: int = Field(5, ge=0, description="hkl search range — use supercell indices when "
                                            "MULTIPLE_UNIT_CELL is used")
    k_max: int = Field(5, ge=0)
    l_max: int = Field(20, ge=0)
    q_min: float = Field(0.0, ge=0, description="reflections below this q are ignored")
    max_hkl_per_peak: int = Field(50, ge=1)
    max_blank_hkl: int = Field(2000, ge=1)
    blank_contribution: float = Field(0.20, ge=0)

    # ---- B factor ----
    b_factor_default: float = Field(0.36, ge=0,
                                    description="default B factor used when no B_FACTOR_FILE given")
    b_factor_file: str = Field("", description="optional fixed per-atom B file; same order & count "
                                               "as the CP2K particles (leave empty to disable)")
    n_b_factor: int = Field(0, ge=0, description="expected B-factor entries (missing ones filled "
                                                 "with B_FACTOR_DEFAULT); 0 = ignore")

    # ---- explicit overrides (empty = keep v1.1 defaults) ----
    atomic_factor_file: str = Field("", description="ATOMIC_FACTOR_FILE — explicit Cromer-Mann "
                                                    "override; empty = xraylib FF_Rayl neutral atoms")
    reflection_file: str = Field("", description="REFLECTION_FILE — pre-generated reflection table; "
                                                 "empty = generated from DIFFRACTION_FILE on the fly")
    peak_result_file: str = Field("peaks_result.txt", description="per-hkl intensity output file")

    # ---- emission options ----
    emit_common_optional: bool = Field(True, description="emit the common optional keywords "
                                                         "(thickness/HKL/blank...) with their values")
    emit_b_factor: bool = Field(True, description="emit the B-factor keywords")
    emit_overrides: bool = Field(False, description="emit the explicit-override keywords "
                                                    "(ATOMIC_FACTOR_FILE / B_FACTOR_FILE / "
                                                    "REFLECTION_FILE / fixed SCALE_FACTOR)")


def _fortran_bool(v: bool) -> str:
    return ".TRUE." if v else ".FALSE."


def _fmt(v) -> str:
    if isinstance(v, bool):
        return _fortran_bool(v)
    if isinstance(v, float):
        s = f"{v:.6g}"
        if s.startswith("."):
            s = "0" + s
        elif s.startswith("-."):
            s = "-0" + s[1:]
        return s
    return str(v)


def generate_fiber_section(req: Cp2kFiberRequest) -> str:
    """Build the ``&FIBER_DIFFRACTION … &END FIBER_DIFFRACTION`` text."""

    diffraction_file = req.diffraction_file.strip()
    if not diffraction_file:
        raise HTTPException(400, "diffraction_file must not be empty")
    peak_result_file = req.peak_result_file.strip() or "peaks_result.txt"

    # NOTE (README §14.6): string keywords must not carry trailing inline
    # comments — the comment would become part of the value.  All comments are
    # therefore emitted on their own line.
    L: list[str] = []
    L.append("! ================= 纤维衍射偏置 (CP2K-Polymcryst-Refine v1.1) =================")
    L.append("! 吸收/密度/散射因子由 xraylib 从晶胞组成 + WAVELENGTH 自动推导。")
    L.append("! 字符型取值行尾不能写内联注释（会被计入文件名）；数值型注释请独立成行。")
    L.append("&FIBER_DIFFRACTION")

    # ---- minimal form ----
    L.append(f"  ENABLED            {_fortran_bool(req.enabled)}")
    L.append("! 峰/ROI 表（格式同 refine.f90，workdir 相对路径）：")
    L.append(f"  DIFFRACTION_FILE   {diffraction_file}")
    L.append("! 唯一实验能量入口 [Å]，E = 12.3984/WAVELENGTH keV；直接写数值，不加单位后缀：")
    L.append(f"  WAVELENGTH         {_fmt(req.wavelength)}")
    if req.auto_scale:
        L.append("! 每步加权最小二乘自动求 k（v1.1 推荐起步）：")
        L.append("  AUTO_SCALE         .TRUE.")
    else:
        L.append("! 固定标度 k（从零耦合检查抄下 k 后使用）：")
        L.append("  AUTO_SCALE         .FALSE.")
        L.append(f"  SCALE_FACTOR       {_fmt(req.scale_factor)}")
    L.append("! 耦合强度 [hartree]，先小后大；参考 FIBER| fiber/DFT 比值调节：")
    L.append(f"  LAMBDA             {_fmt(req.lambda_)}")

    # ---- common optional ----
    if req.emit_common_optional:
        L.append("")
        L.append("! ---- 常用可选项 ----")
        L.append("! 样品厚度 [cm]（v1.1 默认 0.03 = 0.3 mm）：")
        L.append(f"  SAMPLE_THICKNESS_CM       {_fmt(req.sample_thickness_cm)}")
        L.append("! 样品-探测器距离 [cm]：")
        L.append(f"  DETECTOR_DISTANCE_CM     {_fmt(req.detector_distance_cm)}")
        L.append("! 0=同步辐射，1=普通光源，其他=无偏振因子：")
        L.append(f"  XRAY_MODE                 {_fmt(req.xray_mode)}")
        L.append("")
        L.append("! hkl 搜索范围 — 使用超胞时按 CP2K 实际晶胞指标放大（如 2×2 超胞 H/K_MAX 用 10）：")
        L.append(f"  H_MAX                     {_fmt(req.h_max)}")
        L.append(f"  K_MAX                     {_fmt(req.k_max)}")
        L.append(f"  L_MAX                     {_fmt(req.l_max)}")
        L.append("! 低于该 q 的反射忽略 [Å⁻¹]：")
        L.append(f"  Q_MIN                     {_fmt(req.q_min)}")
        L.append(f"  MAX_HKL_PER_PEAK          {_fmt(req.max_hkl_per_peak)}")
        L.append(f"  MAX_BLANK_HKL             {_fmt(req.max_blank_hkl)}")
        L.append("! blank 区惩罚权重：")
        L.append(f"  BLANK_CONTRIBUTION        {_fmt(req.blank_contribution)}")

    # ---- B factor ----
    if req.emit_b_factor:
        L.append("")
        L.append("! ---- B 因子（固定，不参与优化）----")
        L.append("! 不提供 B 文件时全体原子使用该缺省值：")
        L.append(f"  B_FACTOR_DEFAULT          {_fmt(req.b_factor_default)}")
        if req.emit_overrides and req.b_factor_file.strip():
            L.append("! 每原子固定 B 因子（须与结构原子同序、同数目；超胞需扩到超胞原子数）：")
            L.append(f"  B_FACTOR_FILE             {req.b_factor_file.strip()}")
            if req.n_b_factor > 0:
                L.append("! 期望 B 因子条数（缺项用默认值补齐）：")
                L.append(f"  N_B_FACTOR                {_fmt(req.n_b_factor)}")

    # ---- explicit overrides ----
    if req.emit_overrides:
        L.append("")
        L.append("! ---- 显式覆盖项（按需打开；缺省走 xraylib 自动推导）----")
        if req.atomic_factor_file.strip():
            L.append("! Cromer-Mann 表覆盖（含离子/自定义参数时才提供；缺省 = xraylib FF_Rayl 中性原子）：")
            L.append(f"  ATOMIC_FACTOR_FILE        {req.atomic_factor_file.strip()}")
        if req.reflection_file.strip():
            L.append("! 预生成反射表（缺省由 Fortran 从 DIFFRACTION_FILE 现场生成）：")
            L.append(f"  REFLECTION_FILE           {req.reflection_file.strip()}")

    # ---- peak result file (always useful) ----
    L.append("! 逐 hkl 强度输出文件：")
    L.append(f"  PEAK_RESULT_FILE          {peak_result_file}")

    L.append("")
    L.append("! ---- v1.0 废弃项（写了会被忽略并打 WARNING）：MOLECULAR_MASS /")
    L.append("!      SAMPLE_ABSORPTION_COEFF / AIR_ABSORPTION_COEFF / AIR_DENSITY ----")
    L.append("&END FIBER_DIFFRACTION")

    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_class=PlainTextResponse)
def cp2k_generate(req: Cp2kFiberRequest):
    """Generate the ``&FIBER_DIFFRACTION`` section text."""
    try:
        text = generate_fiber_section(req)
        return PlainTextResponse(content=text, media_type="text/plain")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/generate-download", response_class=PlainTextResponse)
def cp2k_generate_download(req: Cp2kFiberRequest):
    """Same as /generate but returns a Content-Disposition attachment."""
    try:
        text = generate_fiber_section(req)
        return PlainTextResponse(
            content=text,
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=fiber_diffraction.inc"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))
