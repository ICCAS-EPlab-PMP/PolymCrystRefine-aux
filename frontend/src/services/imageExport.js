/**
 * Offscreen full-image export for the Image Analysis page.
 *
 * "导出 PNG" must export the WHOLE image (all rows/cols), not whatever slice
 * of it the user has currently zoomed to in the on-screen canvas, and not the
 * canvas' fixed 1200×800 viewport. When a χ crop is active, "whole image"
 * means the full q range over the cropped χ band.
 *
 * Rendering happens on a detached Plotly div so the visible plot is never
 * touched (no relayout flicker, no zoom reset). The z-domain preparation
 * (log10 mapping, non-finite floor sentinel) mirrors ImageCanvas.renderPlot —
 * keep the two in sync when changing contrast semantics.
 */
import Plotly from 'plotly.js-dist-min'
import { plotlyColorscale } from '@/services/colormaps.js'

function numOrNull(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function logScaleRange(v) {
  if (v == null) return null
  return v > 0 ? Math.log10(v) : null
}

// Same window normalization as ImageCanvas.orderedWindow — a crossed
// (zmin > zmax) pair flattens the whole heatmap.
function orderedWindow(zmin, zmax) {
  if (zmin != null && zmax != null && zmin > zmax) return [zmax, zmin]
  return [zmin, zmax]
}

// Map the 2-D grid into the render domain: log10(v) in log mode, and
// non-finite cells replaced by a floor sentinel just under the window floor
// (Plotly paints them with the lowest color instead of NaN-transparent holes).
function prepareZ(zData, logDomain, floor) {
  return zData.map(row => row.map(v => {
    if (logDomain) {
      const lv = (Number.isFinite(v) && v > 0) ? Math.log10(v) : NaN
      return Number.isFinite(lv) ? lv : floor
    }
    return Number.isFinite(v) ? v : floor
  }))
}

function domainFloor(zData, logDomain, zmin) {
  let f = zmin
  if (!Number.isFinite(f)) {
    let mn = Infinity
    for (const row of zData) {
      for (const v of row) {
        if (logDomain) {
          if (Number.isFinite(v) && v > 0) {
            const lv = Math.log10(v)
            if (lv < mn) mn = lv
          }
        } else if (Number.isFinite(v) && v < mn) {
          mn = v
        }
      }
    }
    f = Number.isFinite(mn) ? mn : 0
  }
  return f - 1
}

/**
 * Render the full image offscreen and return a Plotly image data: URL.
 *
 * @param {object} opts
 *   imageData   2-D array (required)
 *   xAxis/yAxis physical axis values (pixel indices when omitted)
 *   colorscale  colormap name (default Viridis)
 *   logScale    render log10(z) (default false)
 *   zmin/zmax   linear-domain contrast window
 *   xRange/yRange  visible axis window (null = full range); the cake χ crop
 *                  passes its band as yRange
 *   title/xAxisTitle/yAxisTitle  labels
 *   width       target pixel width (default 1400)
 * @returns {Promise<string|null>} data: URL, or null when nothing to render
 */
export async function renderFullImageDataUrl({
  imageData,
  xAxis = null,
  yAxis = null,
  colorscale = 'Viridis',
  logScale = false,
  zmin = null,
  zmax = null,
  xRange = null,
  yRange = null,
  title = '',
  xAxisTitle = '',
  yAxisTitle = '',
  width = 1400,
  format = 'png',
} = {}) {
  if (!imageData || !imageData.length || !imageData[0]?.length) return null

  const rows = imageData.length
  const cols = imageData[0].length
  const xData = (xAxis && xAxis.length === cols)
    ? xAxis
    : Array.from({ length: cols }, (_, i) => i)
  const yData = (yAxis && yAxis.length === rows)
    ? yAxis
    : Array.from({ length: rows }, (_, i) => i)

  // Visible band after the crop window — drives the exported aspect ratio.
  const xLo = xRange ? Math.min(xRange[0], xRange[1]) : Math.min(xData[0], xData[cols - 1])
  const xHi = xRange ? Math.max(xRange[0], xRange[1]) : Math.max(xData[0], xData[cols - 1])
  const yLo = yRange ? Math.min(yRange[0], yRange[1]) : Math.min(yData[0], yData[rows - 1])
  const yHi = yRange ? Math.max(yRange[0], yRange[1]) : Math.max(yData[0], yData[rows - 1])
  const xSpan = Math.max(xHi - xLo, 1e-9)
  const ySpan = Math.max(yHi - yLo, 1e-9)

  // Square grid cells: pick the canvas height from the visible data window's
  // aspect, accounting for the plot margins below so the PLOT AREA (not the
  // div) carries the data aspect. (No scaleanchor here — it silently rewrites
  // the y range to enforce aspect, which would change the exported window.)
  const MARGIN_X = 80, MARGIN_Y = 70
  const height = Math.round(
    Math.min(2400, Math.max(420, (ySpan / xSpan) * (width - MARGIN_X) + MARGIN_Y))
  )

  let zminD = numOrNull(logScale ? logScaleRange(numOrNull(zmin)) : zmin)
  let zmaxD = numOrNull(logScale ? logScaleRange(numOrNull(zmax)) : zmax)
  ;[zminD, zmaxD] = orderedWindow(zminD, zmaxD)
  const floor = domainFloor(imageData, logScale, zminD)
  const zData = prepareZ(imageData, logScale, floor)

  const trace = {
    z: zData,
    x: xData,
    y: yData,
    type: 'heatmap',
    colorscale: plotlyColorscale(colorscale),
    showscale: true,
    colorbar: {
      tickfont: { family: 'JetBrains Mono, monospace', size: 11, color: '#262432' },
      outlinewidth: 0,
      len: 0.8,
    },
    hoverinfo: 'skip',
  }
  if (zminD != null) trace.zmin = zminD
  if (zmaxD != null) trace.zmax = zmaxD

  const layout = {
    paper_bgcolor: '#FFFFFF',
    plot_bgcolor: '#FFFFFF',
    font: { color: '#262432', family: 'Inter, sans-serif', size: 12 },
    margin: { t: title ? 40 : 20, r: 20, b: 50, l: 60 },
    title: title || undefined,
    xaxis: {
      title: xAxisTitle || undefined,
      gridcolor: '#E3E0EF',
      zerolinecolor: '#E3E0EF',
      tickfont: { family: 'JetBrains Mono, monospace', size: 11 },
      range: [xLo, xHi],
      constrain: 'range',
    },
    yaxis: {
      title: yAxisTitle || undefined,
      gridcolor: '#E3E0EF',
      zerolinecolor: '#E3E0EF',
      tickfont: { family: 'JetBrains Mono, monospace', size: 11 },
      range: [yLo, yHi],
    },
  }

  const host = document.createElement('div')
  host.style.position = 'fixed'
  host.style.left = '-10000px'
  host.style.top = '0'
  host.style.width = `${width}px`
  host.style.height = `${height}px`
  document.body.appendChild(host)
  try {
    Plotly.newPlot(host, [trace], layout, {
      responsive: false,
      displayModeBar: false,
      // Static export: no interaction handlers needed on the offscreen div.
      staticPlot: true,
    })
    const dataUrl = await Plotly.toImage(host, { format, width, height })
    return dataUrl
  } finally {
    Plotly.purge(host)
    host.remove()
  }
}
