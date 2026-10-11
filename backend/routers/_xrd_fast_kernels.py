"""Numba fast kernels for the XRD simulator (lazy-imported, optional).

Importing this module pulls in numba (~1 s) and compiles the detector kernel,
so ``xrd_simulator`` only imports it lazily — inside the first "fast"-kernel
detector request, from a background warmup thread, or never when the user
runs the legacy kernel on a numba-less install.

The row-parallel kernel is race-free by construction: each thread owns whole
image rows (``prange`` over rows), computes the row's q/χ values once into a
scratch buffer, then adds every peak patch that intersects the row.  Pixels
are written by exactly one thread, so results are deterministic.
"""

from __future__ import annotations

import numpy as np
from numba import njit, prange


@njit(parallel=True, cache=True)
def detector_row_parallel(
    img,            # float64 (img_h, img_w), zero-initialized, accumulated in place
    pk_q,           # float64 (n,) peak q centres (A^-1)
    pk_chi,         # float64 (n,) peak chi centres (deg)
    pk_i,           # float64 (n,) peak intensities (already weighted)
    cx, cy,         # beam centre (px)
    ps,             # pixel size (mm)
    sd,             # sample-detector distance (mm)
    lam,            # wavelength (A)
    sigma_q,        # Gaussian sigma in q (A^-1)
    sigma_chi_deg,  # Gaussian sigma in chi (deg)
):
    img_h, img_w = img.shape
    n_pk = pk_q.shape[0]
    sigma_chi_rad = np.radians(sigma_chi_deg)

    # Per-peak footprint precomputed once — same formulas as the legacy
    # numpy implementation (square 6-sigma patch of max(sigma_q_px, sigma_chi_px)).
    x0s = np.empty(n_pk, dtype=np.int64)
    x1s = np.empty(n_pk, dtype=np.int64)
    y0s = np.empty(n_pk, dtype=np.int64)
    y1s = np.empty(n_pk, dtype=np.int64)
    for k in range(n_pk):
        q0 = pk_q[k]
        stt_arg = q0 * lam / (4.0 * np.pi)
        if stt_arg >= 1.0 or stt_arg <= 0.0:
            x0s[k], x1s[k], y0s[k], y1s[k] = 0, 0, 0, 0
            continue
        two_theta_peak = 2.0 * np.arcsin(stt_arg)
        r_px = (sd * np.tan(two_theta_peak)) / ps
        chi0_rad = np.radians(pk_chi[k])
        cx_peak = cx + r_px * np.cos(chi0_rad)
        cy_peak = cy + r_px * np.sin(chi0_rad)

        cos_half = np.cos(two_theta_peak / 2.0)
        cos_tt = np.cos(two_theta_peak)
        dq_dpx = abs((2.0 * np.pi / lam) * cos_half * (cos_tt ** 2) / sd) * ps
        if dq_dpx < 1e-12:
            dq_dpx = 1e-12
        sigma_q_px = sigma_q / dq_dpx
        sigma_chi_px = sigma_chi_rad * max(r_px, 1.0)

        half = 6.0 * max(sigma_q_px, sigma_chi_px, 1.0)
        x0s[k] = max(int(np.floor(cx_peak - half)), 0)
        x1s[k] = min(int(np.ceil(cx_peak + half)) + 1, img_w)
        y0s[k] = max(int(np.floor(cy_peak - half)), 0)
        y1s[k] = min(int(np.ceil(cy_peak + half)) + 1, img_h)

    inv_2sq = -0.5 / (sigma_q * sigma_q)
    inv_2sc = -0.5 / (sigma_chi_deg * sigma_chi_deg)

    for j in prange(img_h):
        dy_mm = (j - cy) * ps
        row_q = np.empty(img_w, dtype=np.float64)
        row_chi = np.empty(img_w, dtype=np.float64)
        row_img = np.zeros(img_w, dtype=np.float64)
        have_row = False

        for k in range(n_pk):
            if j < y0s[k] or j >= y1s[k]:
                continue
            if not have_row:
                # q / chi for this row, computed once and shared by all peaks.
                for i in range(img_w):
                    dx_mm = (i - cx) * ps
                    r_mm = np.sqrt(dx_mm * dx_mm + dy_mm * dy_mm)
                    two_theta = np.arctan(r_mm / sd)
                    row_q[i] = 4.0 * np.pi * np.sin(two_theta / 2.0) / lam
                    row_chi[i] = np.degrees(np.arctan2(dy_mm, dx_mm))
                have_row = True

            q0 = pk_q[k]
            chi0 = pk_chi[k]
            intensity = pk_i[k]
            for i in range(x0s[k], x1s[k]):
                dq = row_q[i] - q0
                dchi = row_chi[i] - chi0
                if dchi > 180.0:
                    dchi -= 360.0
                elif dchi < -180.0:
                    dchi += 360.0
                row_img[i] += intensity * np.exp(
                    dq * dq * inv_2sq + dchi * dchi * inv_2sc)

        if have_row:
            for i in range(img_w):
                if row_img[i] != 0.0:
                    img[j, i] += row_img[i]


def warmup() -> None:
    """Compile the kernel on a tiny dummy image (called from a daemon thread
    at router import so the first user request doesn't pay JIT latency)."""
    img = np.zeros((32, 32), dtype=np.float64)
    detector_row_parallel(
        img,
        np.array([1.0]), np.array([30.0]), np.array([0.5]),
        16.0, 16.0, 0.075, 100.0, 1.5406, 0.03, 3.0,
    )
