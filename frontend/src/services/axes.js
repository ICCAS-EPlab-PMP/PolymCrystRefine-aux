/**
 * Shared physical-axis transforms for the cake viewer.
 *
 * The detector q axis (Å⁻¹) can be displayed as 2θ or d-spacing, and the χ
 * axis as azimuth. One single definition of each conversion is used by the
 * on-screen plot, the χ crop window, the reference line and the PNG export
 * request, so all of them always agree.
 *
 * Conversions (λ in Å, q in Å⁻¹):
 *   q  = 4π·sin(θ)/λ          →  2θ = 2·asin(q·λ/4π) in degrees
 *   d  = 2π/q
 *   azimuth = χ + 180°        (monotonic; −180..180 → 0..360)
 */

export const X_AXIS_MODES = ['q', '2theta', 'd'];
export const Y_AXIS_MODES = ['chi', 'azimuth'];

export const DEFAULT_WAVELENGTH_ANGSTROM = 1.5418; // Cu Kα

const EPS_Q = 1e-6;

/** Map one q value (Å⁻¹) to the selected x display coordinate. */
export function qToX(q, mode, wavelengthAngstrom = DEFAULT_WAVELENGTH_ANGSTROM) {
  switch (mode) {
    case 'd':
      return (2 * Math.PI) / Math.max(q, EPS_Q);
    case '2theta': {
      const s = (q * wavelengthAngstrom) / (4 * Math.PI);
      return (2 * Math.asin(Math.min(1, Math.max(-1, s))) * 180) / Math.PI;
    }
    default:
      return q;
  }
}

/** Map one χ value (deg) to the selected y display coordinate. */
export function chiToY(chi, mode) {
  return mode === 'azimuth' ? chi + 180 : chi;
}

/** Inverse of chiToY — display coordinate back to χ (for the crop inputs). */
export function yToChi(y, mode) {
  return mode === 'azimuth' ? y - 180 : y;
}

export function xAxisTitle(mode) {
  switch (mode) {
    case 'd': return 'd (Å)';
    case '2theta': return '2θ (°)';
    default: return 'q (Å⁻¹)';
  }
}

export function yAxisTitle(mode) {
  return mode === 'azimuth' ? 'azimuth (°)' : 'χ (°)';
}

/** True when the x transform is non-linear and needs a real coordinate grid. */
export function xModeIsNonLinear(mode) {
  return mode === 'd' || mode === '2theta';
}
