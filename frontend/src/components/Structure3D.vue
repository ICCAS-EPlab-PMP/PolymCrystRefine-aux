<template>
  <div class="structure3d">
    <div ref="plotContainer" class="structure3d__plot"></div>
    <div v-if="hint" class="structure3d__hint">{{ hint }}</div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import Plotly from 'plotly.js-dist-min'

const props = defineProps({
  // [{index, label, element, isH, dispCart:[x,y,z]}]
  atoms: { type: Array, default: () => [] },
  // [{key, i, j, dist, order, isH, stretched}]
  bonds: { type: Array, default: () => [] },
  // Lattice vectors [[ax,ay,az],[bx,by,bz],[cx,cy,cz]] for the cell box.
  cellVectors: { type: Array, default: null },
  showCell: { type: Boolean, default: true },
  showH: { type: Boolean, default: true },
  selectedBondKey: { type: String, default: null },
  // Indices of atoms to highlight (add-bond picking).
  pickedAtoms: { type: Array, default: () => [] },
  height: { type: [Number, String], default: 520 },
  hint: { type: String, default: '' },
})

const emit = defineEmits(['atom-clicked', 'bond-clicked'])

const plotContainer = ref(null)

const CPK = {
  H: '#F3F4F6', B: '#FFB5B5', C: '#4B5563', N: '#3050F8', O: '#FF0D0D',
  F: '#90E050', Si: '#F0C8A0', P: '#FF8000', S: '#FFFF30', Cl: '#1FF01F',
  Br: '#A62929', I: '#940094', Se: '#FFA100', Na: '#AB5CF2', K: '#8F40D4',
  Mg: '#8AFF00', Zn: '#7D80B0',
}
const ATOM_SIZE = { H: 4, C: 8, N: 8, O: 8, S: 9, default: 8 }

function atomColor(el) { return CPK[el] || '#9CA3AF' }
function atomSize(el) { return ATOM_SIZE[el] || ATOM_SIZE.default }

// Cell box: 8 corners from lattice vectors, 12 edges with null separators.
function cellBoxTrace() {
  const [a, b, c] = props.cellVectors
  if (!a || !b || !c) return null
  const corners = []
  for (const i of [0, 1]) for (const j of [0, 1]) for (const k of [0, 1]) {
    corners.push([
      i * a[0] + j * b[0] + k * c[0],
      i * a[1] + j * b[1] + k * c[1],
      i * a[2] + j * b[2] + k * c[2],
    ])
  }
  const edges = [
    [0, 1], [0, 2], [0, 4], [1, 3], [1, 5], [2, 3],
    [2, 6], [3, 7], [4, 5], [4, 6], [5, 7], [6, 7],
  ]
  const x = [], y = [], z = []
  for (const [p, q] of edges) {
    x.push(corners[p][0], corners[q][0], null)
    y.push(corners[p][1], corners[q][1], null)
    z.push(corners[p][2], corners[q][2], null)
  }
  return {
    type: 'scatter3d', mode: 'lines',
    x, y, z,
    line: { width: 3, color: '#A9A6BA', dash: 'dot' },
    hoverinfo: 'skip', name: 'cell', showlegend: false,
  }
}

function bondSegments(bondList, color, width, dash) {
  const byIdx = new Map(props.atoms.map(a => [a.index, a.dispCart]))
  const x = [], y = [], z = []
  for (const b of bondList) {
    const p = byIdx.get(b.i), q = byIdx.get(b.j)
    if (!p || !q) continue
    x.push(p[0], q[0], null)
    y.push(p[1], q[1], null)
    z.push(p[2], q[2], null)
  }
  return {
    type: 'scatter3d', mode: 'lines', x, y, z,
    line: { width, color, ...(dash ? { dash } : {}) },
    hoverinfo: 'skip', showlegend: false, name: 'bonds',
  }
}

// Invisible-ish clickable markers at bond midpoints — much easier to hit
// than the line traces themselves.
function bondMidpointTrace(bondList) {
  const byIdx = new Map(props.atoms.map(a => [a.index, a.dispCart]))
  const x = [], y = [], z = [], text = [], custom = []
  for (const b of bondList) {
    const p = byIdx.get(b.i), q = byIdx.get(b.j)
    if (!p || !q) continue
    x.push((p[0] + q[0]) / 2)
    y.push((p[1] + q[1]) / 2)
    z.push((p[2] + q[2]) / 2)
    text.push(`${labelOf(b.i)}–${labelOf(b.j)} · ${b.dist.toFixed(3)} Å${b.order > 1 ? ' · ' + '='.repeat(b.order - 1) : ''}`)
    custom.push(b.key)
  }
  return {
    type: 'scatter3d', mode: 'markers', x, y, z, text, customdata: custom,
    marker: { size: 4, color: 'rgba(148,163,184,0.45)' },
    hovertemplate: '%{text}<extra>键</extra>',
    name: 'bond-mids', showlegend: false,
  }
}

function labelOf(idx) {
  const a = props.atoms.find(a => a.index === idx)
  return a ? a.label : String(idx)
}

function renderPlot() {
  if (!plotContainer.value) return

  const heavy = props.atoms.filter(a => !a.isH)
  const hyd = props.showH ? props.atoms.filter(a => a.isH) : []
  const visibleHeavyBonds = props.bonds.filter(b => !b.isH)
  const visibleHBonds = props.showH ? props.bonds.filter(b => b.isH) : []

  const traces = []

  // Bonds first (under the atoms).
  traces.push(bondSegments(visibleHeavyBonds.filter(b => !b.stretched), '#5A5767', 7))
  traces.push(bondSegments(visibleHeavyBonds.filter(b => b.order > 1 && !b.stretched), '#F59E0B', 3))
  traces.push(bondSegments(visibleHeavyBonds.filter(b => b.stretched), '#D1CDDE', 3, 'dot'))
  traces.push(bondSegments(visibleHBonds, '#D1D5DB', 4))

  // Selected bond highlight on top.
  const sel = props.bonds.filter(b => b.key === props.selectedBondKey)
  if (sel.length) {
    traces.push(bondSegments(sel, '#DC2626', 11))
  }

  // Heavy atoms.
  traces.push({
    type: 'scatter3d', mode: 'markers',
    x: heavy.map(a => a.dispCart[0]),
    y: heavy.map(a => a.dispCart[1]),
    z: heavy.map(a => a.dispCart[2]),
    text: heavy.map(a => a.label),
    customdata: heavy.map(a => a.index),
    marker: {
      size: heavy.map(a => atomSize(a.element)),
      color: heavy.map(a => atomColor(a.element)),
      line: { width: 1, color: '#262432' },
      opacity: 1,
    },
    hovertemplate: '%{text}<extra>%{customdata}</extra>',
    name: 'atoms', showlegend: false,
  })

  // Hydrogens.
  if (hyd.length) {
    traces.push({
      type: 'scatter3d', mode: 'markers',
      x: hyd.map(a => a.dispCart[0]),
      y: hyd.map(a => a.dispCart[1]),
      z: hyd.map(a => a.dispCart[2]),
      text: hyd.map(a => a.label),
      customdata: hyd.map(a => a.index),
      marker: {
        size: 4, color: '#F8FAFC',
        line: { width: 1, color: '#A9A6BA' },
      },
      hovertemplate: '%{text}<extra>%{customdata}</extra>',
      name: 'H', showlegend: false,
    })
  }

  // Picked-atom rings (add-bond mode).
  if (props.pickedAtoms.length) {
    const picked = props.atoms.filter(a => props.pickedAtoms.includes(a.index))
    traces.push({
      type: 'scatter3d', mode: 'markers',
      x: picked.map(a => a.dispCart[0]),
      y: picked.map(a => a.dispCart[1]),
      z: picked.map(a => a.dispCart[2]),
      text: picked.map(a => a.label),
      customdata: picked.map(a => a.index),
      marker: { size: 16, color: 'rgba(220,38,38,0)', line: { width: 3, color: '#DC2626' } },
      hovertemplate: '%{text}<extra>已选</extra>',
      name: 'picked', showlegend: false,
    })
  }

  // Clickable bond midpoints (last so they sit on top).
  traces.push(bondMidpointTrace(props.bonds.filter(b => props.showH || !b.isH)))

  // Cell box.
  if (props.showCell) {
    const t = cellBoxTrace()
    if (t) traces.push(t)
  }

  const layout = {
    margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    scene: {
      aspectmode: 'data',
      xaxis: { visible: false },
      yaxis: { visible: false },
      zaxis: { visible: false },
      bgcolor: 'rgba(0,0,0,0)',
    },
  }

  Plotly.newPlot(plotContainer.value, traces, layout, {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToRemove: ['toImage'],
    scrollZoom: true,
  })
  bindEvents()
}

function bindEvents() {
  if (!plotContainer.value) return
  plotContainer.value.on('plotly_click', (data) => {
    const pt = data?.points?.[0]
    if (!pt) return
    if (pt.data?.name === 'atoms' || pt.data?.name === 'H') {
      emit('atom-clicked', pt.customdata)
    } else if (pt.data?.name === 'bond-mids') {
      emit('bond-clicked', pt.customdata)
    }
  })
}

watch(
  () => [props.atoms, props.bonds, props.cellVectors, props.showCell, props.showH,
         props.selectedBondKey, props.pickedAtoms],
  () => { renderPlot() },
  { deep: true },
)

onMounted(() => { renderPlot() })

onBeforeUnmount(() => {
  if (plotContainer.value) Plotly.purge(plotContainer.value)
})
</script>

<style scoped>
.structure3d {
  position: relative;
  width: 100%;
}
.structure3d__plot {
  width: 100%;
  min-height: 300px;
  height: v-bind("typeof height === 'number' ? height + 'px' : height");
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg);
  overflow: hidden;
}
.structure3d__hint {
  position: absolute;
  left: 12px;
  bottom: 10px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: #F8FAFC;
  font-size: 12px;
  pointer-events: none;
}
</style>
