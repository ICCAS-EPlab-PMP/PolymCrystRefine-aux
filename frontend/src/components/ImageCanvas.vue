<template>
  <div class="image-canvas">
    <div v-if="showToolbar" class="image-canvas__toolbar">
      <div class="image-canvas__toolbar-group">
        <label class="image-canvas__toolbar-label">{{ t('components.imageCanvas.colormap') }}</label>
        <select v-model="selectedColorscale" class="image-canvas__select">
          <option v-for="cs in colorscales" :key="cs" :value="cs">{{ cs }}</option>
        </select>
      </div>

      <div class="image-canvas__toolbar-group">
        <button
          class="image-canvas__btn"
          :class="{ 'image-canvas__btn--active': localLogScale }"
          @click="toggleLogScale"
          :title="t('components.imageCanvas.toggleLog')"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16">
            <path d="M3 20h18M5 20V10m4 10V4m4 16v-8m4 8V8m4 12V6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span>{{ t('components.imageCanvas.log') }}</span>
        </button>

        <button class="image-canvas__btn" @click="resetZoom" :title="t('components.imageCanvas.resetZoom')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16">
            <path d="M3 10h4V6M21 14h-4v4M15 3l-6 6M9 21l6-6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span>{{ t('components.imageCanvas.reset') }}</span>
        </button>
      </div>
    </div>

    <div ref="plotContainer" class="image-canvas__plot" :style="plotStyle"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Plotly from 'plotly.js-dist-min'
import { plotlyColorscale, COLORMAP_NAMES } from '@/services/colormaps.js'

const { t } = useI18n()

const props = defineProps({
  imageData: { type: [Array, String], default: null },
  xAxis: { type: Array, default: null },
  yAxis: { type: Array, default: null },
  xAxisTitle: { type: String, default: '' },
  yAxisTitle: { type: String, default: '' },
  colorscale: { type: String, default: 'Viridis' },
  title: { type: String, default: '' },
  logScale: { type: Boolean, default: false },
  // Display-only controls (backward compatible — defaults preserve old behavior)
  showColorbar: { type: Boolean, default: true },
  height: { type: [Number, String], default: 300 },
  // Upper bound for the plot container (px). With aspectRatio set the
  // preferred size is width-derived; maxHeight clamps it so stacked panes can
  // be budgeted to fit a bounded display area exactly.
  maxHeight: { type: [Number, String], default: null },
  zmin: { type: Number, default: null },
  zmax: { type: Number, default: null },
  // Plotly layout shapes (e.g. yellow ROI rectangles overlaid on the heatmap).
  shapes: { type: Array, default: null },
  // Fixed y-axis range [lo, hi] (physical coords) for the cake crop feature.
  // null = let Plotly autorange. When set the visible band is clamped so the
  // user can box-select within a narrow azimuth window efficiently.
  yRange: { type: Array, default: null },
  // Fixed x-axis range [lo, hi] (physical coords), the horizontal twin of
  // yRange. null = let Plotly autorange.
  xRange: { type: Array, default: null },
  // Plotly drag mode. Cake analysis switches this to 'pan' in precise mode
  // (click-driven) and 'select' in rough mode (drag-driven box selection).
  dragmode: { type: String, default: 'select' },
  // Scatter overlay points (e.g. Miller indices) drawn on top of the heatmap.
  // Each item is { x, y } in the same physical coords as the heatmap axes.
  overlayPoints: { type: Array, default: null },
  overlayColor: { type: String, default: '#9CA3AF' },
  overlaySize: { type: Number, default: 5 },
  // Minimum aspect ratio for the plot container (e.g. "4/3"). When set, the
  // plot div enforces this aspect ratio via CSS so the 2D image is never too
  // squished horizontally — especially important for cake images with wide
  // χ ranges (-180°…180°) and narrow q ranges.
  aspectRatio: { type: String, default: null },
  // Y-coordinate of a horizontal reference line drawn across the heatmap
  // (e.g. 0 for the χ=0° equator). Set to null to hide the line.
  referenceLineY: { type: Number, default: null },
  // Colour of the reference line.
  referenceLineColor: { type: String, default: '#EF4444' },
  // Whether to show the internal toolbar (colormap, log scale, reset zoom).
  // Set to false when the parent component provides its own controls.
  showToolbar: { type: Boolean, default: true },
  // Text annotations to show on the plot (e.g. ROI index labels).
  // Each item is { x, y, text, color? }.
  roiLabels: { type: Array, default: null },
  // Keep the true data aspect: every grid cell renders as a square on
  // screen (Plotly yaxis.scaleanchor='x' + scaleratio from the grid
  // spacing), so the image is never stretched to fill the container.
  squarePixels: { type: Boolean, default: false },
  // Semi-transparent peak-mask overlay (DBSCAN background estimation preview).
  // A 2-D grid of 0..1 values shaped like imageData (1 = peak pixel); drawn as
  // a second heatmap trace on top with a translucent color so the user can
  // verify which clusters were classified as diffraction peaks.
  maskOverlay: { type: Array, default: null },
  maskColor: { type: String, default: 'rgba(239,68,68,0.55)' },
  // Custom rAF-coalesced wheel zoom (replaces Plotly's built-in scrollZoom,
  // which re-renders the heatmap synchronously on EVERY wheel event —
  // visibly janky on large cakes). Coalescing applies at most one relayout
  // per animation frame, which keeps scrolling smooth.
  smoothZoom: { type: Boolean, default: false }
})

const emit = defineEmits(['point-clicked', 'region-selected', 'update:colorscale', 'update:logScale'])

const plotContainer = ref(null)
const selectedColorscale = ref(props.colorscale)
const localLogScale = ref(props.logScale)

// Keep the parent's colormap/log state in sync when the user changes them via
// the internal toolbar, so exports (which read the parent state) always match
// what is displayed — regardless of which control was used.

// Plot height from prop (number → px), keeps default 300px when unset.
// When aspectRatio is set (e.g. "4/3"), the container enforces that minimum
// aspect ratio so the 2D image is never too squished; maxHeight (if set)
// clamps the width-derived size.
const plotStyle = computed(() => {
  const h = typeof props.height === 'number' ? `${props.height}px` : props.height
  const style = { minHeight: h }
  if (props.aspectRatio) {
    style.aspectRatio = props.aspectRatio
  }
  if (props.maxHeight != null && props.maxHeight !== '') {
    style.maxHeight = typeof props.maxHeight === 'number' ? `${props.maxHeight}px` : props.maxHeight
  }
  return style
})

// Explicit matplotlib-sampled stops (see services/colormaps.js) — plotly 2.x
// only recognizes a handful of capitalized names (Viridis, Cividis, Jet, Hot,
// Greys...); Plasma / Inferno / Magma / Turbo / Gray silently fall back to the
// default scale, so named values MUST be resolved through our own table.
const colorscales = COLORMAP_NAMES

function toggleLogScale() {
  localLogScale.value = !localLogScale.value
  emit('update:logScale', localLogScale.value)
}

// In log mode the rendered z is log10(v), so the contrast window (zmin/zmax,
// which arrive as linear intensities from the parent) must be mapped into the
// same log domain — otherwise the heatmap gets clamped to a flat color and the
// contrast sliders appear to do nothing. Non-positive values map to null so
// Plotly auto-clamps them.
function logScaleRange(v) {
  if (v == null) return null
  return v > 0 ? Math.log10(v) : null
}

// Floor sentinel for non-finite pixels (and, in log mode, non-positive ones —
// log10 of them is NaN). Left as NaN, plotly renders such cells fully
// transparent, which punches white holes through pyFAI cakes (their empty edge
// bins are NaN and masked bins are 0) and reads as a broken colorscale. Plotly
// clamps anything at or below zmin to the FIRST color stop, so a value just
// under the window floor paints the cell with the lowest color instead — the
// conventional "no data ⇒ bottom of scale" look.
function mappedFloor(zData, zmin) {
  let floor = zmin
  if (!Number.isFinite(floor)) {
    let mn = Infinity
    for (const row of zData) {
      for (const v of row) {
        if (Number.isFinite(v) && v < mn) mn = v
      }
    }
    floor = Number.isFinite(mn) ? mn : 0
  }
  return floor - 1
}

// Memoized z-domain preparation. Every re-render used to walk the full grid
// twice (log10 mapping, then non-finite→floor replacement), which on a
// 512×512 cake is a visible stall — and re-renders fire on colormap/log/
// overlay changes, so zooming then tweaking controls felt laggy. The source
// array is replaced by reference on every data update, so keying the cache on
// that reference (plus the floor it depends on) is always correct.
const zPrepCache = new Map() // key: `${srcId}:${floor}` -> prepared 2-D array
let zPrepSeq = 0
const zPrepIds = new WeakMap()
function prepareZ(zData, logDomain, floor) {
  let srcId = zPrepIds.get(zData)
  if (srcId === undefined) {
    // Bound the cache — only the current source is ever reused.
    if (zPrepCache.size > 4) zPrepCache.clear()
    srcId = ++zPrepSeq
    zPrepIds.set(zData, srcId)
  }
  const key = `${srcId}:${logDomain ? 'log' : 'lin'}:${floor}`
  if (zPrepCache.has(key)) return zPrepCache.get(key)
  let out
  if (logDomain) {
    // log10 domain: non-finite/non-positive cells get the floor sentinel so
    // they paint as the lowest color instead of NaN-transparent holes.
    out = zData.map(row => row.map(v => {
      const lv = (Number.isFinite(v) && v > 0) ? Math.log10(v) : NaN
      return Number.isFinite(lv) ? lv : floor
    }))
  } else {
    out = zData.map(row => row.map(v => Number.isFinite(v) ? v : floor))
  }
  zPrepCache.set(key, out)
  return out
}

// Normalize the contrast window: a crossed pair (zmin > zmax, easy to produce
// with two independent sliders) makes plotly divide by a negative range, which
// collapses the whole heatmap into one flat mid-scale color — and restyling
// back to null afterwards does NOT recover it. Swapping here keeps the window
// always well-ordered.
function orderedWindow(zmin, zmax) {
  if (zmin != null && zmax != null && zmin > zmax) {
    return [zmax, zmin]
  }
  return [zmin, zmax]
}

// Typable contrast inputs can briefly hold ''/partial text — never forward a
// non-numeric zmin/zmax to Plotly.
function numOrNull(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function resetZoom() {
  if (plotContainer.value) {
    const relayout = {
      // Restore x to the cropped band when one is set; otherwise full autorange.
      'xaxis.autorange': !props.xRange,
      // Restore to the cropped band when one is set; otherwise full autorange.
      'yaxis.autorange': !props.yRange
    }
    if (props.xRange && props.xRange.length === 2) {
      relayout['xaxis.range'] = [props.xRange[0], props.xRange[1]]
    }
    if (props.yRange && props.yRange.length === 2) {
      relayout['yaxis.range'] = [props.yRange[0], props.yRange[1]]
    }
    Plotly.relayout(plotContainer.value, relayout)
  }
}

const darkLayout = {
  paper_bgcolor: '#FFFFFF',
  plot_bgcolor: '#FFFFFF',
  font: { color: '#262432', family: 'Inter, sans-serif', size: 12 },
  margin: { t: 40, r: 20, b: 50, l: 60 },
  xaxis: { gridcolor: '#E3E0EF', zerolinecolor: '#E3E0EF', tickfont: { family: 'JetBrains Mono, monospace', size: 11 } },
  yaxis: { gridcolor: '#E3E0EF', zerolinecolor: '#E3E0EF', tickfont: { family: 'JetBrains Mono, monospace', size: 11 } },
  dragmode: 'select'
}
// Build combined Plotly shapes: user-supplied shapes (ROI rects, etc.) +
// optional horizontal reference line at referenceLineY (e.g. χ=0° equator).
function buildShapes() {
  const shapes = Array.isArray(props.shapes) ? [...props.shapes] : []
  if (props.referenceLineY != null && Number.isFinite(props.referenceLineY)) {
    shapes.push({
      type: 'line',
      x0: 0, x1: 1,            // fractional x-axis (spans full width)
      y0: props.referenceLineY,
      y1: props.referenceLineY,
      xref: 'paper',           // "paper" = 0–1 across the full plot width
      yref: 'y',               // data coords on y-axis
      line: {
        color: props.referenceLineColor || '#EF4444',
        width: 1.5,
        dash: 'dash'
      }
    })
  }
  return shapes.length ? shapes : undefined
}

function buildAnnotations() {
  if (!Array.isArray(props.roiLabels) || !props.roiLabels.length) return undefined
  return props.roiLabels.map(l => ({
    x: l.x,
    y: l.y,
    text: String(l.text),
    showarrow: false,
    font: {
      family: 'Inter, sans-serif',
      size: 11,
      color: l.color || '#EAB308'
    },
    bgcolor: 'rgba(0,0,0,0.55)',
    borderpad: 2,
    xref: 'x',
    yref: 'y'
  }))
}

function renderPlot() {
  if (!plotContainer.value || !props.imageData) return

  let zData
  if (typeof props.imageData === 'string') {
    // base64 encoded image - render as image trace
    const trace = {
      source: `data:image/png;base64,${props.imageData}`,
      type: 'image',
      x0: 0,
      y0: 0
    }
    const layout = {
      ...darkLayout,
      title: props.title || undefined,
      xaxis: { ...darkLayout.xaxis, visible: false },
      yaxis: { ...darkLayout.yaxis, visible: false, scaleanchor: 'x' }
    }
    Plotly.react(plotContainer.value, [trace], layout, { responsive: true, displayModeBar: false, scrollZoom: true })
    bindEvents()
    return
  }

  // 2D array heatmap
  zData = props.imageData

  // Contrast: clamp the colorscale to a user-chosen intensity window.
  // Map into log domain when rendering log10(v) so the window lines up.
  let zmin = numOrNull(localLogScale.value ? logScaleRange(numOrNull(props.zmin)) : props.zmin)
  let zmax = numOrNull(localLogScale.value ? logScaleRange(numOrNull(props.zmax)) : props.zmax)
  ;[zmin, zmax] = orderedWindow(zmin, zmax)

  if (localLogScale.value) {
    // log10 domain: non-finite/non-positive cells get the floor sentinel so
    // they paint as the lowest color instead of NaN-transparent holes. The
    // floor matches the old two-pass code: prefer the (log-domain) zmin,
    // otherwise the minimum finite log value.
    let f = zmin
    if (!Number.isFinite(f)) {
      let mn = Infinity
      for (const row of zData) {
        for (const v of row) {
          if (Number.isFinite(v) && v > 0) {
            const lv = Math.log10(v)
            if (lv < mn) mn = lv
          }
        }
      }
      f = Number.isFinite(mn) ? mn : 0
    }
    zData = prepareZ(zData, true, f - 1)
  } else {
    // Linear domain: replace non-finite cells the same way.
    zData = prepareZ(zData, false, mappedFloor(zData, zmin))
  }

  const xData = props.xAxis || Array.from({ length: zData[0]?.length || 0 }, (_, i) => i)
  const yData = props.yAxis || Array.from({ length: zData.length }, (_, i) => i)

  // True-aspect link: one y data unit must span as many pixels as
  // (dx/dy) x data units, so each grid cell is a square on screen.
  // px_per_y = scaleratio * px_per_x  =>  scaleratio = dx/dy.
  let yScaleLink = {}
  if (props.squarePixels) {
    const cols = xData.length
    const rows = yData.length
    const dx = cols > 1 ? (xData[cols - 1] - xData[0]) / (cols - 1) : 0
    const dy = rows > 1 ? (yData[rows - 1] - yData[0]) / (rows - 1) : 0
    if (dx > 0 && dy > 0 && Number.isFinite(dx / dy)) {
      yScaleLink = { scaleanchor: 'x', scaleratio: dx / dy }
    }
  }

  const trace = {
    z: zData,
    x: xData,
    y: yData,
    type: 'heatmap',
    colorscale: plotlyColorscale(selectedColorscale.value),
    // `colorbar: undefined` does NOT hide the bar — plotly then draws its
    // DEFAULT full-size colorbar (bigger than the styled one). The switch is
    // the trace-level `showscale`.
    showscale: !!props.showColorbar,
    colorbar: {
      tickfont: { family: 'JetBrains Mono, monospace', size: 11, color: '#262432' },
      outlinewidth: 0,
      len: 0.8
    },
    hovertemplate: 'x: %{x}<br>y: %{y}<br>value: %{z:.4g}<extra></extra>'
  }
  // Contrast: clamp the colorscale to a user-chosen intensity window (already
  // normalized above — see orderedWindow).
  if (zmin != null) trace.zmin = zmin
  if (zmax != null) trace.zmax = zmax

  // Optional scatter overlay (Miller indices, etc.) drawn on top of the
  // heatmap, sharing the same x/y axes. Mirrors the gray dots in the
  // reference AzimuthQViewer (user can switch them to white).
  const traces = [trace]
  // Peak-mask overlay (DBSCAN preview): translucent cells where mask ≈ 1.
  if (Array.isArray(props.maskOverlay) && props.maskOverlay.length) {
    const maskTrace = {
      z: props.maskOverlay,
      x: xData,
      y: yData,
      type: 'heatmap',
      // Jump at 0.3 keeps downsampled mask cells crisp: below ≈ background
      // (fully transparent), above ≈ peak (translucent mask color).
      colorscale: [
        [0, 'rgba(0,0,0,0)'], [0.29, 'rgba(0,0,0,0)'],
        [0.3, props.maskColor || 'rgba(239,68,68,0.55)'],
        [1, props.maskColor || 'rgba(239,68,68,0.55)']
      ],
      showscale: false,
      hoverinfo: 'skip',
      showlegend: false,
    }
    traces.push(maskTrace)
  }
  if (Array.isArray(props.overlayPoints) && props.overlayPoints.length) {
    traces.push({
      x: props.overlayPoints.map(p => p.x),
      y: props.overlayPoints.map(p => p.y),
      type: 'scatter',
      mode: 'markers',
      marker: { size: props.overlaySize, color: props.overlayColor || '#9CA3AF', opacity: 0.8 },
      hoverinfo: 'skip',
      showlegend: false,
    })
  }

  const layout = {
    ...darkLayout,
    title: props.title || undefined,
    dragmode: props.dragmode || 'select',
    // uirevision keeps the user's zoom/pan across Plotly.react updates (data,
    // colormap, overlays…). It only changes when the enforced crop window
    // changes, so applying a new crop still resets the view — everything else
    // leaves the user's zoom untouched.
    uirevision: `img:${props.xRange ? props.xRange.join(':') : 'auto'}:${props.yRange ? props.yRange.join(':') : 'auto'}`,
    shapes: buildShapes(),
    annotations: buildAnnotations(),
    xaxis: {
      ...darkLayout.xaxis,
      title: props.xAxisTitle || undefined,
      ...(props.xRange && props.xRange.length === 2
        ? { range: [props.xRange[0], props.xRange[1]], autorange: false }
        : (props.xAxis ? {} : { dtick: Math.max(1, Math.floor(xData.length / 10)) }))
    },
    yaxis: {
      ...darkLayout.yaxis,
      title: props.yAxisTitle || undefined,
      ...(props.yRange && props.yRange.length === 2
        ? { range: [props.yRange[0], props.yRange[1]], autorange: false }
        : (props.yAxis ? {} : { dtick: Math.max(1, Math.floor(yData.length / 10)) })),
      ...yScaleLink
    }
  }

  // Plotly.react (not newPlot): data/axes/title changes diff into the existing
  // plot instead of tearing the DOM down, so switching images doesn't flash.
  // scrollZoom is disabled when the custom smooth-zoom wheel handler is on,
  // otherwise both would zoom.
  Plotly.react(plotContainer.value, traces, layout, {
    responsive: true,
    displayModeBar: false,
    scrollZoom: !props.smoothZoom,
  })
  bindEvents()
}

// ---- Smooth wheel zoom (see the smoothZoom prop) ----
// Wheel deltas accumulate between frames; one relayout per rAF tick rescales
// both axes around the cursor position. Works with any dragmode (select/pan/
// lasso) and with reversed axis ranges (the algebra is sign-safe).
let wheelAccum = null
let wheelRafId = null
// Cursor position in PLOT-AREA coordinates; null when the cursor is outside
// the plotting area (margins/colorbar) — wheel events there must scroll the
// page normally instead of being swallowed.
function plotAreaPoint(clientX, clientY) {
  const gd = plotContainer.value
  if (!gd || !gd._fullLayout) return null
  const xax = gd._fullLayout.xaxis
  const yax = gd._fullLayout.yaxis
  if (!xax || !yax || xax._offset == null || xax._length == null || yax._offset == null || yax._length == null) return null
  const rect = gd.getBoundingClientRect()
  const px = clientX - rect.left
  const py = clientY - rect.top
  if (px < xax._offset - 4 || px > xax._offset + xax._length + 4) return null
  if (py < yax._offset - 4 || py > yax._offset + yax._length + 4) return null
  return { px, py }
}
function onPlotWheel(e) {
  if (!props.smoothZoom || !plotContainer.value) return
  if (!plotAreaPoint(e.clientX, e.clientY)) return
  e.preventDefault()
  if (!wheelAccum) wheelAccum = { dy: 0, cx: e.clientX, cy: e.clientY }
  wheelAccum.dy += e.deltaY
  // Follow the cursor: zoom around where the pointer currently is.
  wheelAccum.cx = e.clientX
  wheelAccum.cy = e.clientY
  if (wheelRafId == null) {
    wheelRafId = requestAnimationFrame(applySmoothZoom)
  }
}
function applySmoothZoom() {
  wheelRafId = null
  const acc = wheelAccum
  wheelAccum = null
  const gd = plotContainer.value
  if (!acc || !gd || !gd._fullLayout) return
  const xax = gd._fullLayout.xaxis
  const yax = gd._fullLayout.yaxis
  if (!xax || !yax) return
  const xr = xax.range
  const yr = yax.range
  if (!Array.isArray(xr) || xr.length < 2 || !Array.isArray(yr) || yr.length < 2) return
  const pt = plotAreaPoint(acc.cx, acc.cy)
  if (!pt) return
  const fx = xax.p2d(pt.px)
  const fy = yax.p2d(pt.py)
  if (!Number.isFinite(fx) || !Number.isFinite(fy)) return
  // deltaY < 0 (scroll up) zooms in. Clamp so one frame can't jump too far.
  let f = Math.exp(-acc.dy * 0.0018)
  f = Math.min(6, Math.max(1 / 6, f))
  const relayout = {}
  // Guard degenerate ranges (span collapses to ~0) by refusing sub-pixel spans.
  const nx0 = fx + (xr[0] - fx) / f
  const nx1 = fx + (xr[1] - fx) / f
  const ny0 = fy + (yr[0] - fy) / f
  const ny1 = fy + (yr[1] - fy) / f
  if (Math.abs(nx1 - nx0) > 1e-9) {
    relayout['xaxis.range'] = [nx0, nx1]
  }
  if (Math.abs(ny1 - ny0) > 1e-9) {
    relayout['yaxis.range'] = [ny0, ny1]
  }
  if (Object.keys(relayout).length) Plotly.relayout(gd, relayout)
}

let eventsBound = false
function bindEvents() {
  if (!plotContainer.value || eventsBound) return

  plotContainer.value.on('plotly_click', (data) => {
    if (data?.points?.length > 0) {
      const pt = data.points[0]
      emit('point-clicked', { x: pt.x, y: pt.y, value: pt.z })
    }
  })

  plotContainer.value.on('plotly_selected', (eventData) => {
    // Lasso drawing: prefer the actual stroke vertices and report their
    // bounding box (the refine/match machinery works on rectangles, and the
    // refine spec is defined as min/max q/χ of the drawn region anyway).
    const lp = eventData?.lassoPoints
    if (lp && Array.isArray(lp.x) && lp.x.length > 1 && Array.isArray(lp.y) && lp.y.length > 1) {
      emit('region-selected', {
        xRange: [Math.min(...lp.x), Math.max(...lp.x)],
        yRange: [Math.min(...lp.y), Math.max(...lp.y)],
      })
      return
    }
    if (eventData?.range) {
      emit('region-selected', {
        xRange: eventData.range.x,
        yRange: eventData.range.y
      })
    }
  })
  eventsBound = true
}

// Full re-render (through Plotly.react — an in-place diff) when
// data/axes/colorscale/log/title/colorbar/crop/overlay change.
// NOTE 1: `shapes` is intentionally excluded — it changes frequently (every
// slice selection) and is handled by the lightweight relayout watcher below so
// that drawing a selection box never triggers a full heatmap replot.
// NOTE 2: `dragmode` is also excluded — switching selection mode (or arming a
// refine-box drag) must not re-render the heatmap or reset the user's zoom;
// it gets its own relayout watcher below.
// NOTE 3: no `deep` — every array prop is replaced by reference on update, and
// deep-traversing a 512×512 imageData on each trigger is a visible stall.
watch(
  () => [props.imageData, props.xAxis, props.yAxis, props.xAxisTitle, props.yAxisTitle, selectedColorscale.value, localLogScale.value, props.title, props.showColorbar, props.yRange, props.xRange, props.overlayPoints, props.overlaySize, props.squarePixels, props.maskOverlay, props.maskColor],
  () => { renderPlot() }
)

// Overlay-color-only updates restyle just the scatter trace's marker — no
// heatmap re-render. (A full react here made color changes feel dead on large
// cakes: the 512² heatmap redraw took longer than users waited.)
watch(
  () => props.overlayColor,
  (v) => {
    const gd = plotContainer.value
    if (!gd || !Array.isArray(gd.data)) return
    const idx = gd.data.findIndex(tr => tr && tr.type === 'scatter')
    if (idx >= 0) Plotly.restyle(gd, { 'marker.color': v || '#9CA3AF' }, [idx])
  }
)

// dragmode-only updates (rough⇄precise selection, arming/cancelling a
// refine-box drag) go through relayout — a full react here would re-render
// the heatmap and reset the user's zoom every time the refine button is
// clicked, which made refine-drawing painful on large cakes.
watch(
  () => props.dragmode,
  (v) => {
    if (!plotContainer.value) return
    Plotly.relayout(plotContainer.value, { dragmode: v || 'select' })
  }
)

// Shape-only updates (ROI rectangles, selection markers, reference line) go
// through relayout so they apply instantly without re-plotting the heatmap.
watch(
  () => [props.shapes, props.referenceLineY, props.referenceLineColor, props.roiLabels],
  () => {
    if (!plotContainer.value) return
    Plotly.relayout(plotContainer.value, {
      shapes: buildShapes() || [],
      annotations: buildAnnotations() || []
    })
  },
  { deep: true }
)

// Contrast (zmin/zmax) updates go through restyle instead of a full newPlot,
// so dragging the slider does not flicker/blink the whole heatmap.
watch(
  () => [props.zmin, props.zmax],
  () => { updateContrast() }
)

function updateContrast() {
  if (!plotContainer.value) return
  let zmin = numOrNull(localLogScale.value ? logScaleRange(numOrNull(props.zmin)) : props.zmin)
  let zmax = numOrNull(localLogScale.value ? logScaleRange(numOrNull(props.zmax)) : props.zmax)
  // Keep the window well-ordered — a crossed pair flattens the heatmap and a
  // later restyle(null) cannot recover it (see orderedWindow).
  ;[zmin, zmax] = orderedWindow(zmin, zmax)
  // Trace index [0] only: contrast applies to the image heatmap, not to the
  // mask overlay heatmap that shares the plot.
  Plotly.restyle(plotContainer.value, { zmin, zmax }, [0])
}

watch(() => props.logScale, (v) => { localLogScale.value = v })
watch(() => props.colorscale, (v) => { selectedColorscale.value = v })
// Toolbar-driven changes propagate to the parent (guard against echoing the
// prop back immediately after the parent → child sync above).
watch(selectedColorscale, (v) => { if (v !== props.colorscale) emit('update:colorscale', v) })

onMounted(() => {
  renderPlot()
  if (props.smoothZoom) {
    // passive:false so preventDefault can stop the page scrolling instead of
    // the plot zooming.
    plotContainer.value?.addEventListener('wheel', onPlotWheel, { passive: false })
  }
})

// Expose download method for parent components
function downloadImage(format) {
  if (!plotContainer.value) return false
  Plotly.downloadImage(plotContainer.value, {
    format: format,
    width: 1200,
    height: 800,
    filename: 'image_export'
  })
  return true
}

// Render the current plot to a data: URL (PNG/SVG/JPEG). Used by the parent so
// it can route through the Electron native save dialog (Plotly.downloadImage
// uses a silent <a download> which never shows a save dialog under Electron).
function getImageDataUrl(format) {
  if (!plotContainer.value) return Promise.resolve(null)
  return Plotly.toImage(plotContainer.value, {
    format,
    width: 1200,
    height: 800,
  })
}

defineExpose({ downloadImage, getImageDataUrl, plotContainer })

onBeforeUnmount(() => {
  if (wheelRafId != null) {
    cancelAnimationFrame(wheelRafId)
    wheelRafId = null
  }
  plotContainer.value?.removeEventListener('wheel', onPlotWheel)
  if (plotContainer.value) {
    Plotly.purge(plotContainer.value)
  }
})
</script>

<style scoped>
.image-canvas {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.image-canvas__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  flex-wrap: wrap;
}

.image-canvas__toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.image-canvas__toolbar-label {
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.image-canvas__select {
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  padding: 4px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text);
  outline: none;
  cursor: pointer;
  transition: border-color 150ms ease;
}

.image-canvas__select:hover,
.image-canvas__select:focus {
  border-color: var(--color-primary);
}

.image-canvas__btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 150ms ease, color 150ms ease, background-color 150ms ease;
}

.image-canvas__btn:hover {
  border-color: var(--color-primary);
  color: var(--color-text);
}

.image-canvas__btn--active {
  border-color: var(--color-primary);
  background: var(--bg-hover);
  color: var(--color-primary);
}

.image-canvas__plot {
  width: 100%;
  min-height: 300px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
  background: var(--color-bg);
}
</style>
