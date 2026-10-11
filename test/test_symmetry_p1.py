"""Verify the symmetrised P1 export (backend/routers/symmetry.py, mode='p1').

Builds exact structures with pymatgen, then checks the mathematical contract
of the P1 export on both the exact input and a perturbed (~0.005 Å) input:

  1. the idealised cell re-detects to the SAME space group with a
     symmetrisation shift of ~0 (the construction is exactly invariant under
     the operations spglib found — note spglib fits the origin too, so a
     noisy input is symmetrised onto a slightly origin-shifted group);
  2. atom counts are preserved;
  3. special-position atoms land EXACTLY on their symmetry elements
     (inversion centre, rutile mirror x=y & z=0) — checked on the exact
     input, where the origin is unperturbed;
  4. on a noisy input the idealisation shift is positive and small.

Run from PRE/:  python test/test_symmetry_p1.py
(uses two scratch files in the current directory, removed on exit)
"""

import os
import sys
from pathlib import Path

import numpy as np

_PRE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PRE_ROOT, "backend"))

from routers import symmetry as S  # noqa: E402

_NOISY = Path("test_sym_p1_noisy.cif")
_OUT = Path("test_sym_p1_out.cif")


def _perturb(structure, amp=0.005, seed=42):
    """Deterministic Cartesian jitter of ~amp Å (rms) per atom.  Kept small:
    spglib's effective mapping tolerance is tighter than the nominal symprec,
    so larger noise makes the DETECTION itself fail (existing module behaviour,
    see the tolerance sweep in the UI)."""
    from pymatgen.core import Structure
    rng = np.random.default_rng(seed)
    cart = np.array(structure.cart_coords) + rng.normal(0, amp, (len(structure), 3))
    return Structure(structure.lattice, structure.species,
                     structure.lattice.get_fractional_coords(cart))


def _detect(structure, symprec):
    lattice = np.array(structure.lattice.matrix, dtype=float)
    frac = np.array(structure.frac_coords, dtype=float)
    numbers = [int(sp.Z) for sp in structure.species]
    import spglib
    ds = spglib.get_symmetry_dataset((lattice, frac, numbers), symprec=symprec)
    return ds, lattice, frac


def _run_case(label, structure, symprec, expect_number, noisy, checks=None):
    """noisy=True → also expect a positive idealisation shift."""
    from pymatgen.core import Structure

    structure.to(filename=str(_NOISY), fmt="cif")
    try:
        # --- what the endpoint does (minus HTTP): load, detect, idealise ---
        loaded = Structure.from_file(str(_NOISY))
        ds, lattice, frac = _detect(loaded, symprec)
        n_before = int(S._get(ds, "number"))
        atoms, shift = S._idealized_full_cell(loaded, ds, lattice, frac, symprec)
        cell = S._cell_dict(lattice)
        sg = {"number": n_before, "hmStandard": str(S._get(ds, "international")),
              "hall": str(S._get(ds, "hall"))}
        cif_text = S._write_symmetrized_p1_cif("t", cell, sg, atoms, shift)
        _OUT.write_text(cif_text, encoding="utf-8")
        ideal = Structure.from_file(str(_OUT))
    finally:
        for p in (_NOISY, _OUT):
            if p.exists():
                p.unlink()

    ds2, lat2, frac2 = _detect(ideal, symprec)
    n_after = int(S._get(ds2, "number"))
    rot2 = np.asarray(S._get(ds2, "rotations"))
    trans2 = np.asarray(S._get(ds2, "translations"))
    eq2 = np.asarray(S._get(ds2, "equivalent_atoms"))
    max_shift2, _ = S._symmetry_shift(lat2, frac2, rot2, trans2, eq2)

    checks = checks or {}
    ok = True
    if n_before != expect_number or n_after != expect_number:
        print(f"[FAIL] {label}: sg before={n_before} after={n_after}, expected {expect_number}")
        ok = False
    if max_shift2 > 1e-5:
        print(f"[FAIL] {label}: idealised cell not exact: maxShift={max_shift2:.2e} A")
        ok = False
    if len(ideal) != len(loaded):
        print(f"[FAIL] {label}: atom count {len(ideal)} != input {len(loaded)}")
        ok = False
    if noisy and not shift[0] > 0:
        print(f"[FAIL] {label}: idealisation shift should be > 0 for a noisy input, got {shift[0]}")
        ok = False
    for desc, fn in checks.get("assert", []):
        if not fn(ideal, atoms):
            print(f"[FAIL] {label}: custom check failed: {desc}")
            ok = False
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: #{n_before}->{n_after}, "
          f"N={len(loaded)}->{len(ideal)}, idealShift max={shift[0]:.4f} mean={shift[1]:.4f} A, "
          f"re-shift={max_shift2:.2e} A")
    return ok


def main():
    from pymatgen.core import Lattice, Structure

    results = []

    # --- P2_1/c: general-position C + one C on the inversion centre (0,0,0)
    lat = Lattice.monoclinic(12.3, 7.8, 9.1, 103.0)
    base = Structure.from_spacegroup(
        "P2_1/c", lat, ["C", "C"], [[0.15, 0.22, 0.31], [0.0, 0.0, 0.0]])

    def inv_exact(ideal, atoms):
        # the inversion-centre atom must sit at exactly (0,0,0)
        frac = np.array(ideal.frac_coords) % 1.0
        return bool(np.any(np.all(np.isclose(frac, 0.0, atol=1e-7), axis=1)))

    results.append(_run_case(
        "P2_1/c exact", base, 0.05, 14, noisy=False,
        checks={"assert": [("C at exact (0,0,0)", inv_exact)]}))
    results.append(_run_case(
        "P2_1/c noisy", _perturb(base), 0.05, 14, noisy=True))

    # --- rutile P4_2/mnm: Ti on special positions, O on mirror planes (x=x, z=0)
    rutile = Structure.from_spacegroup(
        "P4_2/mnm", Lattice.tetragonal(4.6, 2.95), ["Ti", "O"],
        [[0.0, 0.0, 0.0], [0.305, 0.305, 0.0]])

    def o_on_mirror(ideal, atoms):
        frac = np.array(ideal.frac_coords) % 1.0
        for site, c in zip(ideal, frac):
            if site.specie.symbol == "O":
                # O 4f orbit: z=0 pair on the x=y mirror, z=1/2 pair on x+y=1
                if min(c[2], 1 - c[2]) < 1e-7:
                    if abs(c[0] - c[1]) > 1e-7:
                        return False
                elif abs(c[2] - 0.5) < 1e-7:
                    if abs(c[0] + c[1] - 1.0) > 1e-7:
                        return False
                else:
                    return False
        return True

    results.append(_run_case(
        "rutile exact (O on mirror)", rutile, 0.05, 136, noisy=False,
        checks={"assert": [("all O exactly on x=y, z=0", o_on_mirror)]}))
    results.append(_run_case(
        "rutile noisy", _perturb(rutile), 0.05, 136, noisy=True))

    # --- cubic Pm-3m: everything special; O added at a general position
    cubic = Structure.from_spacegroup(
        "Pm-3m", Lattice.cubic(4.2), ["Cl", "Cs", "O"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [0.25, 0.30, 0.40]])

    def cl_exact_origin(ideal, atoms):
        frac = np.array(ideal.frac_coords) % 1.0
        return bool(np.any(np.all(np.isclose(frac, 0.0, atol=1e-7), axis=1)))

    results.append(_run_case(
        "Pm-3m exact", cubic, 0.05, 221, noisy=False,
        checks={"assert": [("Cl exactly at origin", cl_exact_origin)]}))
    results.append(_run_case(
        "Pm-3m noisy", _perturb(cubic), 0.05, 221, noisy=True))

    print()
    if all(results):
        print(f"ALL {len(results)} CASES PASSED")
        return 0
    print("FAILURES PRESENT")
    return 1


if __name__ == "__main__":
    sys.exit(main())
