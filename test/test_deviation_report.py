"""Verify the structure deviation report (backend/routers/deviation_report.py).

Runs the router's own helpers (no HTTP) against synthetic structures:

  1. CIF vs CIF, same order — per-atom deviations reproduce the exact
     Cartesian perturbation that was applied (mean/max equality);
  2. minimum image — an atom crossing the cell boundary measures the short
     way around, not the long way;
  3. CIF vs CP2K-style PDB with SHUFFLED atom order — nearest matching
     recovers the same per-atom deviations (set equality of distances);
  4. multi-model PDB — the LAST frame is used;
  5. report rendering — Markdown/CSV carry the summary numbers;
  6. error paths — atom-count / element mismatch raise HTTP 400.

Run from PRE/:  python test/test_deviation_report.py
"""

import sys
import tempfile
from pathlib import Path

import numpy as np

# Backend package root (PRE/backend), resolved absolute; scratch files are
# confined to a private temp directory created below.
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi import HTTPException  # noqa: E402

from routers import deviation_report as D  # noqa: E402
from utils import _save_upload  # noqa: E402

_FAILED = []
_SCRATCH = Path(tempfile.mkdtemp(prefix="dev_report_test_"))


def check(label, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {label}" + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        _FAILED.append(label)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_structure(n_per_el=12, seed=1):
    """Triclinic cell (angles like the real refined polymer CIFs) with C, O
    and H atoms placed so same-element pairs stay >= 2.5 Å apart.  Nearest
    matching cannot distinguish atoms closer together than the DFT
    displacement itself, so a degenerate fixture would blur the pairing."""
    from pymatgen.core import Lattice, Structure
    rng = np.random.default_rng(seed)
    lattice = Lattice.from_parameters(8.9, 7.0, 17.0, 133.6, 125.9, 66.2)
    species = ["C"] * n_per_el + ["O"] * (n_per_el // 2) + ["H"] * (n_per_el // 2)
    frac = np.empty((len(species), 3))
    L = np.asarray(lattice.matrix)
    for i, el in enumerate(species):
        while True:
            f = rng.random(3)
            ok = True
            for j in range(i):
                if species[j] != el:
                    continue
                d = f - frac[j]
                d -= np.round(d)
                if np.linalg.norm(d @ L) < 2.5:
                    ok = False
                    break
            if ok:
                break
        frac[i] = f
    labels = [f"{el}{i + 1}" for i, el in enumerate(species)]
    st = Structure(lattice, species, frac)
    return st, labels


def _perturb(structure, amp, seed):
    """Known Cartesian jitter -> (new structure, exact displacement vectors)."""
    from pymatgen.core import Structure
    rng = np.random.default_rng(seed)
    disp = rng.normal(0.0, amp, (len(structure), 3))
    cart = np.asarray(structure.cart_coords) + disp
    return Structure(structure.lattice, structure.species,
                     structure.lattice.get_fractional_coords(cart)), disp


def _write_pdb(path, structure, labels=None, shuffle=None, extra_models=0):
    """CP2K-style PDB: CRYST1 + column-format ATOM records + element field."""
    lat = structure.lattice
    species = [str(s) for s in structure.species]
    cart = np.asarray(structure.cart_coords)
    order = list(range(len(species))) if shuffle is None else list(shuffle)
    lines = [
        f"CRYST1{lat.a:9.3f}{lat.b:9.3f}{lat.c:9.3f}"
        f"{lat.alpha:7.2f}{lat.beta:7.2f}{lat.gamma:7.2f} P 1           1"
    ]
    for frame in range(extra_models + 1):
        if extra_models:
            lines.append(f"MODEL     {frame + 1:4d}")
        for n, i in enumerate(order):
            el = species[i]
            lab = (labels[i] if labels else el) if frame == extra_models else el
            xyz = cart[i] if frame == extra_models else cart[i] * 0.0
            x, y, z = xyz
            lines.append(
                f"ATOM  {n + 1:5d} {lab:<4s}MOL  {n + 1:4d}    "
                f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {el:>2s}")
        if extra_models:
            lines.append("ENDMDL")
    lines.append("END")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _upload(path, name):
    fid = _save_upload(Path(path).read_bytes(), suffix=Path(path).suffix)
    D._name_registry[fid] = name
    return fid


def _compare(base, pert, match="nearest", basis="ref", dft_pdb=False,
             ref_name="ref.cif", dft_name="dft.cif"):
    """Serialise both structures, upload, and run the comparison pipeline."""
    ref_path = _SCRATCH / f"ref_{abs(id(base)) % 99999}.cif"
    dft_path = _SCRATCH / f"dft_{abs(id(pert)) % 99999}.{'pdb' if dft_pdb else 'cif'}"
    base.to(filename=str(ref_path))
    if dft_pdb:
        _write_pdb(dft_path, pert)
    else:
        pert.to(filename=str(dft_path))
    ref_id = _upload(ref_path, ref_name)
    dft_id = _upload(dft_path, dft_name)
    pr = D._load_structure(ref_id)
    pd = D._load_structure(dft_id)
    return D._compare_structures(
        pr, pd, D._upload_meta(pr, ref_id, ref_name),
        D._upload_meta(pd, dft_id, dft_name), match, basis)


# ---------------------------------------------------------------------------
# 1. CIF vs CIF, same order
#
# NOTE: pymatgen's CIF writer/reader round-trip may REGROUP atoms (its reader
# returns sites grouped by species), so per-index expectations would couple
# the test to that internal ordering.  The checks below are therefore order-
# insensitive (sorted multisets + summary stats), while test 3 additionally
# exercises a deliberately shuffled PDB.
# ---------------------------------------------------------------------------
def test_same_order():
    base, labels = _make_structure()
    pert, disp = _perturb(base, 0.08, seed=7)
    payload = _compare(base, pert, match="nearest")
    got = np.sort(np.array([a["dist"] for a in payload["atoms"]]))
    want = np.sort(np.linalg.norm(disp, axis=1))
    check("CIF/CIF: per-atom deviations match the applied perturbation",
          np.allclose(got, want, atol=2e-4),
          f"max|diff|={np.abs(got - want).max():.2e}")
    check("CIF/CIF: stats.mean", abs(payload["stats"]["mean"] - want.mean()) < 2e-4)
    check("CIF/CIF: stats.max", abs(payload["stats"]["max"] - want.max()) < 2e-4)
    check("CIF/CIF: rms", abs(payload["stats"]["rms"] - np.sqrt((want ** 2).mean())) < 2e-4)
    check("CIF/CIF: max atom points at the max row",
          payload["atoms"][payload["stats"]["maxIndex"]]["dist"]
          == payload["stats"]["max"]
          and payload["atoms"][payload["stats"]["maxIndex"]]["refLabel"]
          == payload["stats"]["maxAtom"])
    check("CIF/CIF: labels are unique",
          len({a["refLabel"] for a in payload["atoms"]}) == len(payload["atoms"]))

    payload_order = _compare(base, pert, match="order")
    check("CIF/CIF: order match equals nearest match",
          np.allclose(np.sort([a["dist"] for a in payload_order["atoms"]]),
                      want, atol=2e-4))

    d0 = payload["atoms"][0]
    check("CIF/CIF: components agree",
          abs(d0["dist"] - np.sqrt(d0["dx"] ** 2 + d0["dy"] ** 2 + d0["dz"] ** 2)) < 1e-3)


# ---------------------------------------------------------------------------
# 2. Minimum image
# ---------------------------------------------------------------------------
def test_minimum_image():
    from pymatgen.core import Lattice, Structure
    a = 10.0
    lat = Lattice.cubic(a)
    ref = Structure(lat, ["C"], [[0.01, 0.5, 0.5]])            # near +x face
    dft = Structure(lat, ["C"], [[0.99, 0.5, 0.5]])            # wrapped past it
    payload = _compare(ref, dft, match="order")
    check("minimum image: boundary crossing measures 0.2 Å, not 9.8 Å",
          abs(payload["atoms"][0]["dist"] - 0.2) < 2e-3,
          f"got {payload['atoms'][0]['dist']}")


# ---------------------------------------------------------------------------
# 3. CIF vs shuffled CP2K PDB
# ---------------------------------------------------------------------------
def test_shuffled_pdb():
    base, labels = _make_structure(n_per_el=10, seed=3)
    pert, disp = _perturb(base, 0.05, seed=11)
    rng = np.random.default_rng(5)
    perm = list(rng.permutation(len(base)))

    ref_path = _SCRATCH / "shuf_ref.cif"
    dft_path = _SCRATCH / "shuf_dft.pdb"
    base.to(filename=str(ref_path))
    _write_pdb(dft_path, pert, shuffle=perm)
    ref_id = _upload(ref_path, "ref.cif")
    dft_id = _upload(dft_path, "relaxed.pdb")
    pr = D._load_structure(ref_id)
    pd = D._load_structure(dft_id)
    payload = D._compare_structures(
        pr, pd, D._upload_meta(pr, ref_id, "ref.cif"),
        D._upload_meta(pd, dft_id, "relaxed.pdb"), "nearest", "ref")

    got = np.sort(np.array([a["dist"] for a in payload["atoms"]]))
    want = np.sort(np.linalg.norm(disp, axis=1))
    check("PDB/shuffled: nearest matching recovers every displacement",
          np.allclose(got, want, atol=2e-2),
          f"max|diff|={np.abs(got - want).max():.2e}")
    check("PDB/shuffled: dft format detected", payload["dft"]["format"] == "pdb")
    check("PDB/shuffled: mean matches",
          abs(payload["stats"]["mean"] - want.mean()) < 2e-3)


# ---------------------------------------------------------------------------
# 4. Multi-model PDB takes the last frame
# ---------------------------------------------------------------------------
def test_multimodel_pdb():
    from pymatgen.core import Lattice, Structure
    lat = Lattice.cubic(10.0)
    st = Structure(lat, ["C", "O"], [[0.1, 0.1, 0.1], [0.5, 0.5, 0.5]])
    path = _SCRATCH / "multi.pdb"
    _write_pdb(path, st, extra_models=2)     # zeros in frames 1-2, real in 3
    parsed = D._parse_pdb(Path(path).read_text(encoding="utf-8"), str(path))
    check("PDB: multi-model keeps the last frame",
          parsed.n_models == 3 and len(parsed.species) == 2
          and np.allclose(parsed.frac, st.frac_coords, atol=2e-3))


# ---------------------------------------------------------------------------
# 5. Report rendering
# ---------------------------------------------------------------------------
def test_report_render():
    base, _ = _make_structure(n_per_el=6, seed=2)
    pert, _ = _perturb(base, 0.06, seed=13)
    payload = _compare(base, pert)
    md = D._render_markdown(payload)
    csv = D._render_csv(payload)
    check("MD: summary numbers present",
          f"**{payload['stats']['mean']:.5f}**" in md
          and payload["stats"]["maxAtom"] in md
          and "逐原子偏差" in md)
    check("MD: cell table present", "晶胞参数对比" in md and "volume" in md)
    check("CSV: header + row count",
          csv.count("\n") >= len(payload["atoms"]) + 1
          and csv.startswith("#") and "dist_A" in csv)


# ---------------------------------------------------------------------------
# 6. Error paths
# ---------------------------------------------------------------------------
def test_errors():
    from pymatgen.core import Structure
    base, _ = _make_structure(n_per_el=4, seed=4)
    short = Structure(base.lattice, base.species[:-1], base.frac_coords[:-1])
    try:
        _compare(base, short, match="nearest")
        check("atom-count mismatch raises 400", False)
    except HTTPException as e:
        check("atom-count mismatch raises 400", e.status_code == 400)

    from pymatgen.core import Lattice, Structure
    lat = Lattice.cubic(10.0)
    r = Structure(lat, ["C", "C"], [[0.1, 0, 0], [0.6, 0, 0]])
    d = Structure(lat, ["C", "O"], [[0.1, 0, 0], [0.6, 0, 0]])
    try:
        _compare(r, d, match="nearest")
        check("element mismatch raises 400", False)
    except HTTPException as e:
        check("element mismatch raises 400", e.status_code == 400)

    # Element order differs at the same index -> auto-fallback to nearest.
    # Tested directly on parsed structures: the CIF round-trip regroups atoms
    # by species, which would silently "fix" the mismatch before the router
    # ever sees it (C/C swaps are undetectable by order matching anyway).
    lat2 = Lattice.cubic(10.0)
    pr = D._ParsedStructure(lat2, ["C", "O"],
                            np.array([[0.1, 0, 0], [0.6, 0, 0]]), ["C1", "O1"], "cif")
    pdd = D._ParsedStructure(lat2, ["O", "C"],
                             np.array([[0.6, 0, 0], [0.1, 0, 0]]), ["O1", "C1"], "cif")
    idx, warns = D._match_order(pr, pdd)
    check("order mismatch auto-falls back to nearest",
          any("自动改用近邻" in w for w in warns) and idx.tolist() == [1, 0])


if __name__ == "__main__":
    test_same_order()
    test_minimum_image()
    test_shuffled_pdb()
    test_multimodel_pdb()
    test_report_render()
    test_errors()
    print()
    if _FAILED:
        print(f"{len(_FAILED)} FAILED: " + ", ".join(_FAILED))
        sys.exit(1)
    print("All deviation-report checks passed.")
