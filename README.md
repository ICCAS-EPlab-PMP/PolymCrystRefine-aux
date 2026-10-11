# PolymCrystRefine (Aux Edition)

[![Homepage](https://img.shields.io/badge/homepage-polymcrystal.com-0a7cff)](http://www.polymcrystal.com)
[![Paper](https://img.shields.io/badge/paper-J.%20Appl.%20Cryst.-blue)](https://doi.org/10.1107/S1600576726008290)
[![Platform](https://img.shields.io/badge/platform-Windows-blueviolet)](#)
[![Stack](https://img.shields.io/badge/stack-Python%20%2B%20Vue%203%20%2B%20Electron-42b883)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> 聚合物晶体衍射数据处理与结构精修工作流桌面套件
> A desktop suite for polymer-crystal diffraction data processing and structure refinement workflows.

PolymCrystRefine-aux（PRE 辅助版）为辅助 PolymCrystRefine 精修计算流水线构建的图形化桌面应用：从 2D WAXS 积分与合并强度提取，到 OPLSAA 力场提取、精修输入生成，再到 CIF 解析与补氢、空间群检测、单相/双相纤维衍射模拟，并附带我们 CP2K 插件的衍射段生成、结构偏差分析等 DFT 辅助工具，覆盖从原始探测器图像到结构精修结果到 DFT 优化的完整工作流。

PolymCrystRefine-aux (the PRE auxiliary edition) is a graphical desktop application built to assist the PolymCrystRefine refinement pipeline: from 2D WAXS integration and merged-intensity extraction, through OPLSAA force-field extraction and refinement input generation, to CIF parsing with hydrogen addition, space-group detection and single/dual-phase fiber diffraction simulation — plus DFT-side helpers such as the diffraction-section generator of our CP2K plugin and structure deviation analysis — covering the complete workflow from raw detector images to refined structures and on to DFT optimization.

**技术栈 / Stack**: Python (FastAPI) + Vue 3 (Vite) + Electron。后端默认只监听
`127.0.0.1`，所有数据处理都在本机完成。

---

## 功能模块 / Modules

| 模块 / Module | 说明 / Description |
|---|---|
| 2D 强度积分 / 2D Integration | 衍射图像积分与强度曲线 / Diffraction-image integration and intensity curves |
| 积分处理与合并 / Integration Merge | 多图批处理、掩膜、合并 / Batch processing, masking, merging |
| GIWAXS 纤维积分合并 / GIWAXS Fiber Merge | 多幅 GIWAXS 图拼接合并 / Multi-image GIWAXS merging |
| qz 条带积分 / Qz Band Slice | 合并图 → 逐条带 I(q) 曲线 / Merged map → per-band I(q) curves |
| 图像分析 / Image Analysis | 背景估计、峰检测、ROI 统计 / Background estimation, peak detection, ROI stats |
| 数据查看器 / Data Viewer | 曲线/图像/结构浏览 / Curve, image and structure browsing |
| CIF 解析 / CIF Parser | 晶体结构解析与可视化 / Crystal structure parsing and visualization |
| XRD 模拟 / XRD Simulator | 高斯展宽粉末/纤维谱模拟 / Gaussian-broadened powder & fiber simulation |
| CIF 补氢 / CIF Hydrogenation | 按键长规则补 H / Rule-based H addition |
| 空间群检测 / Space Group Detection | spglib 对称性分析 / spglib symmetry analysis |
| 结构偏差报告 / Deviation Report | DFT 优化结构与参考结构逐原子对比 / Per-atom DFT-vs-reference comparison |
| LAMMPS 力场提取 / OPLSAA Extractor | 轨迹 → 力场参数 / Trajectory → force-field parameters |
| CP2K 输入生成 / CP2K Input | FIBER_DIFFRACTION 段生成 / FIBER_DIFFRACTION section generation |
| 精修输入生成 / Input Generator | 生成 Fortran 精修程序 `input.txt` / Generates the Fortran refinement `input.txt` |

> **关于 Fortran 精修程序 / About the Fortran refinement programs**
> 本仓库只包含 GUI 与数据处理层，**不包含** `multi_opt` / `cifgen2` 等 Fortran
> 可执行文件；输入生成器负责为这些程序准备 `input.txt`，可执行文件由使用者
> 自行提供与运行。
> This repository contains the GUI and data-processing layer only — the Fortran
> refinement executables are not bundled; the Input Generator prepares the
> `input.txt` for those programs, which the user supplies and runs themselves.

## 环境要求 / Requirements

- Windows 10/11（打包目标）/ packaged target; 源码运行亦可在 Linux/macOS 开发调试
- Python ≥ 3.10
- Node.js ≥ 18（含 npm）

## 从源码运行 / Run from Source

```bash
# 1) 后端依赖 / backend dependencies
pip install -r backend/requirements.txt

# 2) 前端依赖 / frontend dependencies
cd frontend && npm install

# 3) 启动后端（默认 127.0.0.1:18730）/ start the backend
cd ../backend && python main.py

# 4) 启动前端开发服务器（另一终端，默认 :5173）/ start the frontend dev server
cd ../frontend && npm run dev
```

浏览器打开 http://localhost:5173 即可使用；桌面壳（Electron）开发模式：

```bash
npm install        # 仓库根目录 / repository root
npm run dev        # Vite dev server + Electron 窗口（自动拉起后端）
```

## 打包 / Packaging

```bash
npm run build      # 前端 vite build + electron-builder（NSIS 安装包 + 免安装目录）
```

构建产物输出到仓库外上层目录（`electron/electron-builder.json` 的
`directories.output`），如需输出到仓库内可自行修改该配置。

## 引用 / Citation

If this software is useful in your research, please cite:

> Ma, Tianyi, Liu, Guoming & Wang, Dujin (2026).
> *PolymCrystRefine: a workflow for diffraction analysis of polymer crystals.*
> Journal of Applied Crystallography, **59**(5), 1630–1644.
> International Union of Crystallography (IUCr).
> https://doi.org/10.1107/S1600576726008290

```bibtex
@article{Ma2026PolymCrystRefine,
  author  = {Ma, Tianyi and Liu, Guoming and Wang, Dujin},
  title   = {PolymCrystRefine: a workflow for diffraction analysis of polymer crystals},
  journal = {Journal of Applied Crystallography},
  year    = {2026},
  volume  = {59},
  number  = {5},
  pages   = {1630--1644},
  doi     = {10.1107/S1600576726008290}
}
```

## 致谢 / Acknowledgments

- 中国科学院化学研究所 / Institute of Chemistry, Chinese Academy of Sciences
- 工程塑料实验室 / Engineering Plastics Laboratory
- 高分子形态加工课题组 / Polymer Morphology Processing Group
- HEPS 北京怀柔高能同步辐射光源 ID08 / HEPS Beamline ID08
- SSRF 上海同步辐射光源 16B/10U / SSRF Beamlines 16B/10U
- [pyFAI](https://pyfai.readthedocs.io/en/stable/pyFAI.html) 与 fabIO 开发团队 / the pyFAI and fabIO development teams

## 友情链接 / Friendly Links

- [PolymCryst 系列程序首页 / Program series homepage](http://www.polymcrystal.com/)
- [PolymCrystIndex — 纤维衍射图谱指标化程序 / Fiber diffraction indexing](https://github.com/ICCAS-EPlab-PMP/PolymCrystIndex)
- [XFAIS — WAXS/SAXS 数据处理程序 / WAXS/SAXS processing suite](https://github.com/ICCAS-EPlab-PMP/XFAIS)
- [中国科学院化学研究所 / ICCAS](https://www.iccas.ac.cn/)
- [工程塑料实验室 / Engineering Plastics Laboratory](http://eplab.iccas.ac.cn/)
- [高分子形态加工课题组 / PMP Group](http://pmp.iccas.ac.cn/)

## 许可证 / License

本项目采用 [MIT License](LICENSE) 发布。

This project is released under the [MIT License](LICENSE).

> 注：本仓库仅包含 GUI 与数据处理层源码；程序运行时依赖的第三方库（pyFAI、
> pymatgen、RDKit、Vue、Electron 等）分别受各自的许可证约束。
> Note: this repository contains the GUI and data-processing source only; the
> third-party libraries used at runtime (pyFAI, pymatgen, RDKit, Vue, Electron,
> etc.) are governed by their respective licenses.
