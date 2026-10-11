<template>
  <div class="qz-page">
    <header class="page-head">
      <div class="page-head__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <line x1="3" y1="8" x2="21" y2="8" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="16" x2="21" y2="16" />
        </svg>
      </div>
      <div class="page-head__copy">
        <h2 class="page-head__title">{{ t('qzSlice.title') }}</h2>
        <p class="page-head__desc">{{ t('qzSlice.header') }}</p>
      </div>
    </header>

    <div class="qz-grid">
      <!-- ============ Input column ============ -->
      <section class="panel panel--input">
        <!-- Data source -->
        <div class="section">
          <div class="section__head">
            <h3>{{ t('qzSlice.data.title') }}</h3>
            <span class="section__hint">{{ t('qzSlice.data.desc') }}</span>
          </div>

          <FileUpload :multiple="true" accept=".zip,.npy" :clear-after-select="true" @files-selected="(fs) => onFilesSelected(fs)" />

          <!-- Source summary card -->
          <div v-if="mapInfo" class="source-card">
            <div class="source-card__title" :title="mapInfo.sourceName">{{ mapInfo.sourceName }}</div>
            <div class="source-card__grid">
              <div class="source-card__item">
                <span class="source-card__k">{{ t('qzSlice.result.grid') }}</span>
                <span class="source-card__v">{{ mapInfo.nOop }}×{{ mapInfo.nIp }}</span>
              </div>
              <div class="source-card__item">
                <span class="source-card__k">{{ t('qzSlice.result.rangeIp') }}</span>
                <span class="source-card__v">{{ fmt(mapInfo.ipRange[0]) }} … {{ fmt(mapInfo.ipRange[1]) }} ({{ mapInfo.unitIp }})</span>
              </div>
              <div class="source-card__item">
                <span class="source-card__k">{{ t('qzSlice.result.rangeOop') }}</span>
                <span class="source-card__v">{{ fmt(mapInfo.oopRange[0]) }} … {{ fmt(mapInfo.oopRange[1]) }} ({{ mapInfo.unitOop }})</span>
              </div>
              <div class="source-card__item">
                <span class="source-card__k">{{ t('qzSlice.result.min') }} / {{ t('qzSlice.result.max') }}</span>
                <span class="source-card__v">{{ formatNum(mapInfo.minIntensity) }} / {{ formatNum(mapInfo.maxIntensity) }}</span>
              </div>
            </div>
            <button class="btn btn--ghost btn--sm" @click="clearData">{{ t('qzSlice.data.clear') }}</button>
          </div>
        </div>

        <!-- Band parameters -->
        <div class="section">
          <div class="section__head">
            <h3>{{ t('qzSlice.params.title') }}</h3>
            <span class="section__hint">{{ t('qzSlice.params.desc') }}</span>
          </div>

          <div class="axis-grid">
            <div class="field">
              <label>
                {{ t('qzSlice.params.qz') }}
                <span v-if="mapInfo" class="field-unit">{{ t('qzSlice.params.unit', { unit: mapInfo.unitOop }) }}</span>
              </label>
              <input type="number" step="any" min="0" v-model.number="qz" />
            </div>
            <div class="field">
              <label>
                {{ t('qzSlice.params.interval') }}
                <span v-if="mapInfo" class="field-unit">{{ t('qzSlice.params.unit', { unit: mapInfo.unitOop }) }}</span>
              </label>
              <input type="number" step="any" min="0" v-model.number="interval" />
            </div>
          </div>

          <div class="field">
            <label>{{ t('qzSlice.params.maskLowerBound') }}</label>
            <input type="number" step="any" :placeholder="t('qzSlice.params.maskLowerBoundPh')"
              v-model.number="maskLowerBound" />
            <span class="field-unit">{{ t('qzSlice.params.maskHelp') }}</span>
          </div>

          <div class="stats">
            <span class="stat"><b>{{ t('qzSlice.params.bandCount', { n: bandCount }) }}</b></span>
            <span v-if="overlapWarn" class="warn-line">{{ t('qzSlice.params.overlapWarn') }}</span>
            <span v-if="paramsInvalid" class="warn-line">{{ t('qzSlice.params.invalid') }}</span>
          </div>
        </div>

        <!-- Action bar + console -->
        <div class="action-bar">
          <button class="btn btn--primary" :disabled="!canRun || busy" @click="run">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5,3 19,12 5,21" /></svg>
            {{ t('qzSlice.actions.run') }}
          </button>
          <button class="btn btn--ghost" @click="reset">{{ t('qzSlice.actions.reset') }}</button>
          <button class="btn btn--ghost" :disabled="!result || busyExport" @click="exportCsv">
            {{ busyExport ? t('qzSlice.status.exporting') : t('qzSlice.actions.exportCsv') }}
          </button>
          <button class="btn btn--ghost" :disabled="!result || busyExport" @click="exportTxt">
            {{ busyExport ? t('qzSlice.status.exporting') : t('qzSlice.actions.exportTxt') }}
          </button>
        </div>
        <Console :logs="logs" />
      </section>

      <!-- ============ Result column ============ -->
      <section class="panel panel--result">
        <div class="section__head">
          <h3>{{ t('qzSlice.result.title') }}</h3>
          <div v-if="mapInfo" class="stats">
            <span class="stat"><b>{{ t('qzSlice.result.grid') }}</b> {{ mapInfo.nOop }}×{{ mapInfo.nIp }}</span>
            <span v-if="result" class="stat"><b>{{ t('qzSlice.result.bands') }}</b> {{ result.bands.length }}</span>
          </div>
        </div>

        <template v-if="mapInfo">
          <div class="map-label">{{ t('qzSlice.result.mapTitle') }}</div>
          <div class="result-canvas">
            <ImageCanvas
              :image-data="mapInfo.preview"
              :x-axis="mapInfo.ipAxis"
              :y-axis="mapInfo.oopAxis"
              :x-axis-title="mapInfo.unitIp"
              :y-axis-title="mapInfo.unitOop"
              :show-colorbar="false"
              :height="520"
              :zmin="contrastMin"
              :zmax="contrastMax"
              :aspect-ratio="'1 / 1'"
              :shapes="bandShapes"
            />
            <div class="contrast-controls">
              <div class="contrast-row">
                <label>{{ t('qzSlice.result.contrastMin') }} · {{ formatNum(contrastMin) }}</label>
                <input type="range" :min="floor" :max="ceil" :step="stepC" v-model.number="contrastMin" />
              </div>
              <div class="contrast-row">
                <label>{{ t('qzSlice.result.contrastMax') }} · {{ formatNum(contrastMax) }}</label>
                <input type="range" :min="floor" :max="ceil" :step="stepC" v-model.number="contrastMax" />
              </div>
              <button class="btn btn--ghost btn--sm" @click="resetContrast">{{ t('qzSlice.result.contrastReset') }}</button>
            </div>
          </div>

          <!-- Per-band averaged curves -->
          <div class="curves-block">
            <div class="curves-head">
              <span class="curves-title">{{ t('qzSlice.result.curvesTitle') }}</span>
              <span v-if="dirty" class="dirty-chip">{{ t('qzSlice.result.dirty') }}</span>
            </div>
            <div class="curve-controls">
              <label class="check-row">
                <span>{{ t('qzSlice.result.offset') }}</span>
                <input class="offset-input" type="number" step="any" v-model.number="curveOffset" />
              </label>
              <label class="check-row">
                <input type="checkbox" v-model="logY" />
                <span>{{ t('qzSlice.result.logY') }}</span>
              </label>
            </div>
            <PlotViewer v-if="result" :traces="curveTraces" :layout="curveLayout" :title="t('qzSlice.result.curvesTitle')" />
            <div v-else class="result-empty result-empty--sm">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">
                <path d="M3 17c3 0 3-10 6-10s3 10 6 10 3-6 6-6" />
              </svg>
              <p>{{ busy ? t('qzSlice.status.running') : t('qzSlice.status.empty') }}</p>
            </div>
          </div>
        </template>
        <div v-else class="result-empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="3" y1="8" x2="21" y2="8" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="16" x2="21" y2="16" />
          </svg>
          <p>{{ busy ? t('qzSlice.status.running') : t('qzSlice.status.empty') }}</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import FileUpload from '@/components/FileUpload.vue'
import ImageCanvas from '@/components/ImageCanvas.vue'
import PlotViewer from '@/components/PlotViewer.vue'
import {
  qzSliceUpload,
  qzSliceAttach,
  qzSliceRun,
  qzSliceExportCsv,
  qzSliceExportTxt
} from '@/api/index.js'
import { saveBlob } from '@/services/download.js'

// Tiny inline console renderer (avoids depending on task-status plumbing).
import { defineComponent, h } from 'vue'
const Console = defineComponent({
  name: 'MiniConsole',
  props: { logs: { type: Array, default: () => [] } },
  setup(props) {
    return () => h('div', { class: 'mini-console' },
      props.logs.map((line, i) => h('div', { class: 'mini-console__line', key: i }, String(line)))
    )
  }
})

const { t } = useI18n()

const HANDOFF_KEY = 'pre.qzSlice.handoff.v1'
// Band-spacing defaults per oop unit family (Å⁻¹ is the app-wide default;
// maps exported in nm⁻¹ get the 10× larger values on load).
const DEFAULTS_A = { qz: 0.05, interval: 0.01, curveOffset: 0, logY: false }
const DEFAULTS_NM = { qz: 0.5, interval: 0.1, curveOffset: 0, logY: false }
const DEFAULTS = DEFAULTS_A
const LEGACY_DEFAULTS = { qz: 0.5, interval: 0.1 }   // pre-Å defaults, migrate on load

// ---- State ----
const mapInfo = ref(null)           // upload/attach response (MapInfo)
const result = ref(null)            // run response {qz, interval, qx, bands}
const busy = ref(false)
const busyExport = ref(false)
const logs = ref([])

const qz = ref(DEFAULTS.qz)
const interval = ref(DEFAULTS.interval)
const maskLowerBound = ref(null)      // pixels below are excluded from sum + average
const curveOffset = ref(DEFAULTS.curveOffset)
const logY = ref(DEFAULTS.logY)

function toNumOrNull(v) { return (v === '' || v == null || !Number.isFinite(v)) ? null : Number(v) }

// ---- Persistence (same pattern as GiwaxsMergePage) ----
const LS_KEY = 'pre.qzSlice.v1'
try {
  const saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null')
  if (saved) {
    // Migrate the pre-Å defaults (0.5/0.1) onto the Å-scale ones; anything
    // the user typed themselves is kept as-is.
    if (saved.qz === LEGACY_DEFAULTS.qz && saved.interval === LEGACY_DEFAULTS.interval) {
      saved.qz = DEFAULTS.qz
      saved.interval = DEFAULTS.interval
    }
    if (Number.isFinite(saved.qz)) qz.value = saved.qz
    if (Number.isFinite(saved.interval)) interval.value = saved.interval
    if (Number.isFinite(saved.curveOffset)) curveOffset.value = saved.curveOffset
    if (typeof saved.logY === 'boolean') logY.value = saved.logY
    if (saved.maskLowerBound !== undefined && saved.maskLowerBound !== null) {
      maskLowerBound.value = saved.maskLowerBound
    }
  }
} catch { /* ignore corrupt state */ }
watch([qz, interval, maskLowerBound, curveOffset, logY], () => {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({ qz: qz.value, interval: interval.value, maskLowerBound: maskLowerBound.value, curveOffset: curveOffset.value, logY: logY.value }))
  } catch { /* quota — ignore */ }
})

// ---- Contrast (display-only) ----
const contrastMin = ref(null)
const contrastMax = ref(null)
const floor = computed(() => (mapInfo.value && mapInfo.value.minIntensity != null)
  ? Math.min(mapInfo.value.minIntensity, mapInfo.value.maxIntensity) : 0)
const ceil = computed(() => (mapInfo.value && mapInfo.value.minIntensity != null)
  ? Math.max(mapInfo.value.minIntensity, mapInfo.value.maxIntensity) : 1)
const stepC = computed(() => {
  const s = ceil.value - floor.value
  return s !== 0 ? Math.abs(s) / 200 : 0.001
})
function resetContrast() {
  contrastMin.value = floor.value
  contrastMax.value = ceil.value
}

// ---- Band geometry (local template preview — mirrors the backend rule) ----
function computeBands(oopMin, oopMax, qzStep, halfWidth) {
  if (!(qzStep > 0) || !(halfWidth > 0) || oopMin == null) return []
  const eps = 1e-9
  const nMin = Math.ceil((oopMin - halfWidth) / qzStep - eps)
  const nMax = Math.floor((oopMax + halfWidth) / qzStep + eps)
  const out = []
  for (let n = nMin; n <= nMax; n++) {
    const c = n * qzStep, lo = c - halfWidth, hi = c + halfWidth
    if (hi < oopMin || lo > oopMax) continue
    out.push({ center: c, lo, hi })
  }
  return out
}

const bands = computed(() => {
  const mi = mapInfo.value
  if (!mi || !Array.isArray(mi.oopRange)) return []
  return computeBands(mi.oopRange[0], mi.oopRange[1], qz.value, interval.value)
})
const bandCount = computed(() => bands.value.length)
const overlapWarn = computed(() => qz.value > 0 && interval.value > 0 && 2 * interval.value > qz.value)
const paramsInvalid = computed(() => !(qz.value > 0) || !(interval.value > 0))

// Gray translucent rectangle overlay for every band, spanning the full IP range.
const bandShapes = computed(() => {
  const mi = mapInfo.value
  if (!mi || !Array.isArray(mi.ipRange)) return []
  return bands.value.map((b) => ({
    type: 'rect',
    xref: 'x',
    yref: 'y',
    x0: mi.ipRange[0],
    x1: mi.ipRange[1],
    y0: Math.min(b.lo, b.hi),
    y1: Math.max(b.lo, b.hi),
    fillcolor: 'rgba(100,116,139,0.28)',
    line: { color: '#5A5767', width: 1.2 }
  }))
})

// ---- 1D curves ----
const curveTraces = computed(() => {
  const r = result.value
  if (!r || !Array.isArray(r.bands)) return []
  return r.bands.map((b, k) => {
    const lo = b.qzLo != null ? b.qzLo : b.center - interval.value
    const hi = b.qzHi != null ? b.qzHi : b.center + interval.value
    return {
      x: r.qx,
      y: (b.intensity || []).map((v) => (v == null ? null : v + curveOffset.value * k)),
      name: `qz [${fmt(lo)}, ${fmt(hi)}]`,
      mode: 'lines',
      color: `hsl(${(k * 47) % 360} 65% 45%)`
    }
  })
})
const curveLayout = computed(() => ({
  xaxis: { title: mapInfo.value ? mapInfo.value.unitIp : '' },
  yaxis: { title: '⟨I⟩ (band mean)', type: logY.value ? 'log' : 'linear' }
}))

// Curves no longer match the current inputs after the user edits them.
const dirty = computed(() => {
  const r = result.value
  if (!r) return false
  return qz.value !== r.qz || interval.value !== r.interval
    || toNumOrNull(maskLowerBound.value) !== (r.maskLowerBound ?? null)
})

const canRun = computed(() => !!mapInfo.value && !paramsInvalid.value)

// ---- Helpers ----
function log(line) { logs.value.push(line) }

function fmt(v) {
  if (v == null || !Number.isFinite(v)) return '—'
  return Math.abs(v) < 100 ? v.toFixed(2) : v.toPrecision(3)
}

function formatNum(v) {
  if (v == null || !Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(3)
  return String(Math.round(v * 1000) / 1000)
}

function acceptMapInfo(info) {
  mapInfo.value = info
  result.value = null
  resetContrast()
  adaptDefaultsToUnit(info.unitOop)
}

// Keep the qz / interval inputs editable at any scale: when a freshly loaded
// map's oop unit family differs from the scale the current defaults were
// written for (Å vs nm), swap ONLY untouched defaults — user-entered values
// survive a reload with either unit.
function adaptDefaultsToUnit(unitOop) {
  if (!unitOop) return
  const isNm = unitOop.includes('nm^-1')
  const isA = unitOop.includes('A^-1')
  if (isNm && qz.value === DEFAULTS_A.qz && interval.value === DEFAULTS_A.interval) {
    qz.value = DEFAULTS_NM.qz
    interval.value = DEFAULTS_NM.interval
  } else if (isA && qz.value === DEFAULTS_NM.qz && interval.value === DEFAULTS_NM.interval) {
    qz.value = DEFAULTS_A.qz
    interval.value = DEFAULTS_A.interval
  }
}

// ---- Upload / attach ----
async function onFilesSelected(files) {
  if (!files || !files.length) return
  try {
    const fd = new FormData()
    for (const f of files) fd.append('files', f, f.name)
    const res = await qzSliceUpload(fd)
    acceptMapInfo(res.data)
    log(t('qzSlice.data.loaded', { name: res.data.sourceName, rows: res.data.nOop, cols: res.data.nIp }))
  } catch (e) {
    log(`⚠ ${e.response?.data?.detail || e.message}`)
  }
}

function clearData() {
  mapInfo.value = null
  result.value = null
}

// Hand-off from GiwaxsMergePage ("Send to qz Band Integration").
onMounted(async () => {
  const raw = sessionStorage.getItem(HANDOFF_KEY)
  if (!raw) return
  sessionStorage.removeItem(HANDOFF_KEY)
  try {
    const handoff = JSON.parse(raw)
    const res = await qzSliceAttach({
      mergedFileId: handoff.mergedFileId,
      ipAxisFileId: handoff.ipAxisFileId,
      oopAxisFileId: handoff.oopAxisFileId,
      unitIp: handoff.unitIp,
      unitOop: handoff.unitOop,
      sourceName: handoff.sourceName
    })
    acceptMapInfo(res.data)
    log(t('qzSlice.data.handoffOk', { name: res.data.sourceName || handoff.sourceName || '' }))
    log(t('qzSlice.data.loaded', { name: res.data.sourceName, rows: res.data.nOop, cols: res.data.nIp }))
  } catch (e) {
    log(`⚠ ${t('qzSlice.data.handoffFail')} — ${e.response?.data?.detail || e.message}`)
  }
})

// ---- Run ----
async function run() {
  if (!canRun.value || busy.value) return
  busy.value = true
  log(t('qzSlice.status.running'))
  try {
    const res = await qzSliceRun({
      mergedFileId: mapInfo.value.mergedFileId,
      ipAxisFileId: mapInfo.value.ipAxisFileId,
      oopAxisFileId: mapInfo.value.oopAxisFileId,
      qz: qz.value,
      interval: interval.value,
      maskLowerBound: toNumOrNull(maskLowerBound.value)
    })
    result.value = res.data
    log(`✓ ${res.data.bands.length} ${t('qzSlice.result.bands')}`)
  } catch (e) {
    log(`✗ ${e.response?.data?.detail || e.message}`)
  } finally {
    busy.value = false
  }
}

function reset() {
  qz.value = DEFAULTS.qz
  interval.value = DEFAULTS.interval
  maskLowerBound.value = null
  curveOffset.value = DEFAULTS.curveOffset
  logY.value = DEFAULTS.logY
  result.value = null
  logs.value = []
}

// ---- Export ----
function baseNameOf() {
  const name = (mapInfo.value && mapInfo.value.sourceName) || ''
  const stem = String(name).replace(/\.[^.]+$/, '').trim()
  return stem || 'qz_slice'
}

async function downloadExport(kind) {
  const r = result.value
  if (!r || busyExport.value) return
  busyExport.value = true
  try {
    const baseName = baseNameOf()
    const params = {
      mergedFileId: mapInfo.value.mergedFileId,
      ipAxisFileId: mapInfo.value.ipAxisFileId,
      oopAxisFileId: mapInfo.value.oopAxisFileId,
      qz: r.qz,
      interval: r.interval,
      maskLowerBound: r.maskLowerBound ?? null,
      baseName,
      unitIp: mapInfo.value.unitIp,
      unitOop: mapInfo.value.unitOop,
      sourceName: mapInfo.value.sourceName
    }
    if (kind === 'txt') {
      const res = await qzSliceExportTxt(params)
      await saveBlob(res.data, `${baseName}_qz_slice.txt`)
      log(`✓ ${baseName}_qz_slice.txt`)
    } else {
      const res = await qzSliceExportCsv(params)
      await saveBlob(res.data, `${baseName}_qz_slice.csv`)
      log(`✓ ${baseName}_qz_slice.csv`)
    }
  } catch (e) {
    log(`⚠ ${e.response?.data?.detail || e.message}`)
  } finally {
    busyExport.value = false
  }
}

function exportCsv() { return downloadExport('csv') }
function exportTxt() { return downloadExport('txt') }
</script>

<style scoped>
.qz-page {
  display: flex;
  flex-direction: column;
  gap: 22px;
  animation: qzFadeIn 0.4s ease-out;
}
@keyframes qzFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ---- Page head ---- */
.page-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 22px 26px;
  border-radius: var(--radius-xl);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
}
.page-head__icon {
  width: 48px; height: 48px;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-lg);
  background: var(--primary-bg);
  color: var(--primary);
}
.page-head__icon svg { width: 26px; height: 26px; }
.page-head__title { margin: 0; font-size: 1.35rem; font-weight: 800; color: var(--text-primary); }
.page-head__desc { margin: 4px 0 0; font-size: 0.9rem; color: var(--text-secondary); line-height: 1.5; }

/* ---- Grid ---- */
.qz-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
  gap: 22px;
  align-items: start;
}

/* ---- Panels ---- */
.panel {
  padding: 24px;
  border-radius: var(--radius-xl);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
}
.panel--input { display: flex; flex-direction: column; gap: 22px; }
.panel--result { position: sticky; top: calc(var(--header-height) + 24px); display: flex; flex-direction: column; gap: 18px; }

.section { display: flex; flex-direction: column; gap: 14px; }
.section__head h3 { margin: 0; font-size: 1rem; font-weight: 700; color: var(--text-primary); }
.section__hint { display: block; margin-top: 3px; font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5; }

/* ---- Source summary card ---- */
.source-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid var(--border);
  background: var(--bg-surface-alt);
  border-radius: var(--radius-md);
  padding: 12px 14px;
}
.source-card__title {
  font-size: 0.8rem; font-weight: 700; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.source-card__grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 16px; }
.source-card__item { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.source-card__k { font-size: 0.72rem; color: var(--text-secondary); flex-shrink: 0; }
.source-card__v { font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ---- Fields ---- */
.axis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.field label { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
.field input, .field select {
  width: 100%; box-sizing: border-box;
  padding: 8px 11px;
  font-family: var(--font-mono); font-size: 0.82rem;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  outline: none;
}
.field input:focus, .field select:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--color-primary-glow); }
.field-unit { font-weight: 500; font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-secondary); }

.check-row {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 0.82rem; color: var(--text-primary); cursor: pointer;
}
.check-row input { accent-color: var(--primary); }
.hint-line { margin: 0; font-size: 0.76rem; color: var(--text-secondary); line-height: 1.5; }

/* ---- Buttons ---- */
.action-bar { display: flex; gap: 10px; margin-top: 4px; flex-wrap: wrap; }
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 0.88rem; font-weight: 600;
  cursor: pointer; border: 1px solid transparent;
}
.btn svg { width: 16px; height: 16px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn--primary { background: var(--primary); color: #FFFFFF; box-shadow: 0 8px 20px rgba(124, 58, 237, 0.22); }
.btn--primary:not(:disabled):hover { background: var(--primary-dark); transform: translateY(-1px); }
.btn--ghost { background: transparent; border-color: var(--border); color: var(--text-secondary); }
.btn--ghost:hover { border-color: var(--border-hover); color: var(--text-primary); background: var(--bg-surface-alt); }
.btn--sm { padding: 7px 14px; font-size: 0.8rem; align-self: flex-start; }

/* ---- Result ---- */
.stats { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
.stat { font-size: 0.74rem; color: var(--text-secondary); font-family: var(--font-mono); }
.stat b { color: var(--text-primary); margin-right: 5px; }
.warn-line { font-size: 0.74rem; font-weight: 600; color: var(--color-warning); }
.map-label { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
.result-canvas { margin-top: 0; display: flex; flex-direction: column; gap: 10px; }
.result-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; min-height: 340px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-lg);
  color: var(--text-muted);
}
.result-empty--sm { min-height: 180px; }
.result-empty svg { width: 44px; height: 44px; opacity: 0.5; }
.result-empty p { margin: 0; font-size: 0.86rem; }

.contrast-controls { display: flex; flex-direction: column; gap: 8px; }
.contrast-row { display: flex; flex-direction: column; gap: 4px; }
.contrast-row label { font-size: 0.74rem; font-family: var(--font-mono); color: var(--text-secondary); }
.contrast-row input[type="range"] { width: 100%; accent-color: var(--primary); }

/* ---- Curves ---- */
.curves-block { display: flex; flex-direction: column; gap: 10px; }
.curves-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.curves-title { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
.dirty-chip {
  display: inline-flex; align-items: center;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  background: rgba(245, 158, 11, 0.12);
  color: var(--color-warning);
  font-size: 0.72rem; font-weight: 600;
}
.curve-controls { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.offset-input {
  width: 96px; box-sizing: border-box;
  padding: 6px 8px;
  font-family: var(--font-mono); font-size: 0.8rem;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  outline: none;
}
.offset-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--color-primary-glow); }

/* ---- Mini console ---- */
:deep(.mini-console) {
  max-height: 200px; overflow-y: auto;
  background: var(--bg-surface-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  font-family: var(--font-mono); font-size: 0.74rem;
  color: var(--text-secondary);
  display: flex; flex-direction: column; gap: 3px;
}
:deep(.mini-console__line) { white-space: pre-wrap; word-break: break-word; }

/* ---- Responsive ---- */
@media (max-width: 1024px) {
  .qz-grid { grid-template-columns: 1fr; }
  .panel--result { position: static; }
}
</style>
