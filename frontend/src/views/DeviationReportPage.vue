<template>
  <div class="deviation-page">
    <div class="main-container">
      <!-- Sidebar sections -->
      <aside class="sidebar">
        <nav class="section-nav">
          <button
            v-for="sec in sections"
            :key="sec.id"
            :class="['nav-item', { active: activeSection === sec.id }]"
            @click="activeSection = sec.id"
          >
            <span class="nav-label">{{ sec.label }}</span>
          </button>
        </nav>
        <div class="sidebar-footer">
          <div class="status-indicator">
            <span class="status-dot" :class="statusClass"></span>
            <span class="status-text">{{ statusLabel }}</span>
          </div>
        </div>
      </aside>

      <!-- Main content -->
      <main class="content">
        <transition name="fade" mode="out-in">
          <div :key="activeSection" class="section-panel">

            <!-- ============ Input ============ -->
            <div v-if="activeSection === 'input'" class="card">
              <h2 class="card-title">{{ t('deviation.title') }}</h2>
              <p class="card-desc">{{ t('deviation.desc') }}</p>

              <div class="upload-grid">
                <div class="upload-slot">
                  <h3 class="slot-title">{{ t('deviation.refSlot') }}</h3>
                  <FileUpload
                    accept=".cif,.CIF,.pdb,.PDB"
                    :multiple="false"
                    :label="t('deviation.refUpload')"
                    @files-selected="(fs) => onFilesSelected(fs, 'ref')"
                  />
                  <div v-if="refInfo" class="upload-summary">
                    <div class="summary-chip">
                      <span class="chip-label">{{ t('deviation.uploadInfo.file') }}</span>
                      <span class="chip-value">{{ refInfo.originalName }}</span>
                    </div>
                    <div class="summary-chip">
                      <span class="chip-label">{{ t('deviation.uploadInfo.format') }}</span>
                      <span class="chip-value mono">{{ refInfo.format.toUpperCase() }}</span>
                    </div>
                    <div class="summary-chip">
                      <span class="chip-label">{{ t('deviation.uploadInfo.atoms') }}</span>
                      <span class="chip-value">{{ refInfo.nAtoms }}</span>
                    </div>
                    <div class="summary-chip">
                      <span class="chip-label">{{ t('deviation.uploadInfo.cell') }}</span>
                      <span class="chip-value mono">{{ formatCell(refInfo.cell) }}</span>
                    </div>
                  </div>
                </div>

                <div class="upload-slot">
                  <h3 class="slot-title">{{ t('deviation.dftSlot') }}</h3>
                  <FileUpload
                    accept=".cif,.CIF,.pdb,.PDB"
                    :multiple="false"
                    :label="t('deviation.dftUpload')"
                    @files-selected="(fs) => onFilesSelected(fs, 'dft')"
                  />
                  <div v-if="dftInfo" class="upload-summary">
                    <div class="summary-chip">
                      <span class="chip-label">{{ t('deviation.uploadInfo.file') }}</span>
                      <span class="chip-value">{{ dftInfo.originalName }}</span>
                    </div>
                    <div class="summary-chip">
                      <span class="chip-label">{{ t('deviation.uploadInfo.format') }}</span>
                      <span class="chip-value mono">{{ dftInfo.format.toUpperCase() }}</span>
                    </div>
                    <div class="summary-chip">
                      <span class="chip-label">{{ t('deviation.uploadInfo.atoms') }}</span>
                      <span class="chip-value">{{ dftInfo.nAtoms }}</span>
                    </div>
                    <div v-if="dftInfo.nModels" class="summary-chip">
                      <span class="chip-label">MODEL</span>
                      <span class="chip-value">{{ t('deviation.nModels', { n: dftInfo.nModels }) }}</span>
                    </div>
                    <div class="summary-chip">
                      <span class="chip-label">{{ t('deviation.uploadInfo.cell') }}</span>
                      <span class="chip-value mono">{{ formatCell(dftInfo.cell) }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <ParamsForm :fields="paramFields" v-model="params" style="margin-top: 20px" />

              <div class="actions-row">
                <button class="btn-primary" @click="runCompare"
                        :disabled="comparing || !refInfo || !dftInfo">
                  {{ comparing ? t('deviation.actions.comparing') : t('deviation.actions.compare') }}
                </button>
              </div>

              <div v-if="result && result.warnings.length" class="warnings-block">
                <h3 class="subsection-title">{{ t('deviation.warningsTitle') }}</h3>
                <ul class="warning-list">
                  <li v-for="(w, i) in result.warnings" :key="i">{{ w }}</li>
                </ul>
              </div>

              <ConsolePanel
                v-if="consoleLogs.length || taskStatus !== 'idle'"
                :status="taskStatus"
                :logs="consoleLogs"
                style="margin-top: 16px"
              />
            </div>

            <!-- ============ Result ============ -->
            <div v-if="activeSection === 'result'" class="card">
              <h2 class="card-title">{{ t('deviation.result.title') }}</h2>
              <p v-if="!result" class="card-desc">{{ t('deviation.result.empty') }}</p>

              <template v-if="result">
                <!-- Headline: mean / rms / max -->
                <div class="stat-grid">
                  <div class="stat stat-primary">
                    <span class="stat-value">{{ result.stats.mean.toFixed(4) }}</span>
                    <span class="stat-label">{{ t('deviation.result.mean') }} (Å)</span>
                  </div>
                  <div class="stat">
                    <span class="stat-value">{{ result.stats.rms.toFixed(4) }}</span>
                    <span class="stat-label">{{ t('deviation.result.rms') }} (Å)</span>
                  </div>
                  <div class="stat">
                    <span class="stat-value">{{ result.stats.max.toFixed(4) }}</span>
                    <span class="stat-label">
                      {{ t('deviation.result.max') }} (Å) · {{ result.stats.maxAtom }}
                    </span>
                  </div>
                </div>

                <div class="meta-row">
                  <span class="meta-item">
                    {{ t('deviation.result.pairing') }}:
                    <b>{{ pairingLabel }}</b>
                  </span>
                  <span class="meta-item">
                    {{ t('deviation.result.basis') }}:
                    <b>{{ basisLabel }}</b>
                  </span>
                  <span class="meta-item">
                    {{ t('deviation.result.nAtoms') }}: <b>{{ result.stats.n }}</b>
                  </span>
                  <span class="meta-item">
                    {{ t('deviation.result.median') }}: <b>{{ result.stats.median.toFixed(4) }}</b> Å
                  </span>
                </div>

                <!-- Cell comparison -->
                <h3 class="subsection-title">{{ t('deviation.result.cellTitle') }}</h3>
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>{{ t('deviation.result.cellParam') }}</th>
                      <th>{{ t('deviation.result.ref') }}</th>
                      <th>DFT</th>
                      <th>Δ</th>
                      <th>Δ%</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in cellRows" :key="row.key">
                      <td class="mono">{{ row.key }}{{ row.unit }}</td>
                      <td class="mono">{{ row.ref }}</td>
                      <td class="mono">{{ row.dft }}</td>
                      <td class="mono">{{ row.delta }}</td>
                      <td class="mono" :class="{ 'cell-changed': Math.abs(row.pct) > 1 }">
                        {{ row.pct }}
                      </td>
                    </tr>
                  </tbody>
                </table>

                <!-- Per-element stats -->
                <h3 class="subsection-title">{{ t('deviation.result.elTitle') }}</h3>
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>{{ t('deviation.result.cols.element') }}</th>
                      <th>{{ t('deviation.result.nAtoms') }}</th>
                      <th>{{ t('deviation.result.mean') }} (Å)</th>
                      <th>{{ t('deviation.result.max') }} (Å)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="e in result.elements" :key="e.element">
                      <td>{{ e.element }}</td>
                      <td>{{ e.n }}</td>
                      <td class="mono">{{ e.mean.toFixed(5) }}</td>
                      <td class="mono">{{ e.max.toFixed(5) }}</td>
                    </tr>
                  </tbody>
                </table>

                <!-- Per-atom deviations -->
                <div class="atoms-header">
                  <h3 class="subsection-title">{{ t('deviation.result.atomsTitle') }}</h3>
                  <select v-model="elementFilter" class="element-filter">
                    <option value="">{{ t('deviation.result.allElements') }}</option>
                    <option v-for="e in result.elements" :key="e.element" :value="e.element">
                      {{ e.element }} ({{ e.n }})
                    </option>
                  </select>
                </div>
                <table class="data-table atoms-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>{{ t('deviation.result.cols.refLabel') }}</th>
                      <th>{{ t('deviation.result.cols.dftLabel') }}</th>
                      <th>{{ t('deviation.result.cols.element') }}</th>
                      <th class="th-sortable" @click="toggleSort('dx')">Δx (Å)</th>
                      <th class="th-sortable" @click="toggleSort('dy')">Δy (Å)</th>
                      <th class="th-sortable" @click="toggleSort('dz')">Δz (Å)</th>
                      <th class="th-sortable th-dist" @click="toggleSort('dist')">
                        |Δ| (Å) {{ sortArrow('dist') }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="a in visibleAtoms" :key="a.i"
                        :class="{ 'row-max': a.i === result.stats.maxIndex }">
                      <td class="mono dim">{{ a.i + 1 }}</td>
                      <td>{{ a.refLabel }}</td>
                      <td>{{ a.dftLabel }}</td>
                      <td>{{ a.element }}</td>
                      <td class="mono">{{ fmtSigned(a.dx) }}</td>
                      <td class="mono">{{ fmtSigned(a.dy) }}</td>
                      <td class="mono">{{ fmtSigned(a.dz) }}</td>
                      <td class="mono dist">{{ a.dist.toFixed(5) }}</td>
                    </tr>
                  </tbody>
                </table>
              </template>
            </div>

            <!-- ============ Report ============ -->
            <div v-if="activeSection === 'report'" class="card">
              <h2 class="card-title">{{ t('deviation.report.title') }}</h2>
              <p class="card-desc">{{ t('deviation.report.hint') }}</p>

              <div class="actions-row">
                <button class="btn-primary" @click="runReport('md')"
                        :disabled="generating || !refInfo || !dftInfo">
                  {{ generating ? t('deviation.actions.generating') : t('deviation.actions.genMd') }}
                </button>
                <button class="btn-secondary" @click="runReport('csv')"
                        :disabled="generating || !refInfo || !dftInfo">
                  {{ t('deviation.actions.genCsv') }}
                </button>
                <button class="btn-secondary" @click="downloadReport" :disabled="!reportInfo">
                  {{ t('deviation.actions.download') }}
                </button>
              </div>

              <div v-if="reportInfo" class="preview-block">
                <h3 class="subsection-title">
                  {{ reportInfo.filename }}
                  <span class="preview-meta mono">
                    {{ t('deviation.report.mean') }} {{ reportInfo.stats.mean }} Å ·
                    {{ t('deviation.report.max') }} {{ reportInfo.stats.max }} Å
                  </span>
                </h3>
                <pre class="preview-code"><code>{{ reportInfo.text }}</code></pre>
              </div>

              <ConsolePanel
                v-if="consoleLogs.length || taskStatus !== 'idle'"
                :status="taskStatus"
                :logs="consoleLogs"
                style="margin-top: 16px"
              />

              <div class="usage-note">
                <h3 class="subsection-title">{{ t('deviation.usage.title') }}</h3>
                <ol class="usage-steps">
                  <li>{{ t('deviation.usage.step1') }}</li>
                  <li>{{ t('deviation.usage.step2') }}</li>
                  <li>{{ t('deviation.usage.step3') }}</li>
                  <li>{{ t('deviation.usage.step4') }}</li>
                </ol>
              </div>
            </div>

          </div>
        </transition>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import FileUpload from '@/components/FileUpload.vue'
import ParamsForm from '@/components/ParamsForm.vue'
import ConsolePanel from '@/components/ConsolePanel.vue'
import {
  deviationUpload,
  deviationCompare,
  deviationReport,
  deviationDownload
} from '@/api/index.js'

const { t } = useI18n()

// ---- Sections ----
const sections = computed(() => [
  { id: 'input', label: t('deviation.sections.input') },
  { id: 'result', label: t('deviation.sections.result') },
  { id: 'report', label: t('deviation.sections.report') },
])
const activeSection = ref('input')

// ---- Status ----
const taskStatus = ref('idle')
const consoleLogs = reactive([])
const comparing = ref(false)
const generating = ref(false)

const statusClass = computed(() => {
  if (taskStatus.value === 'completed') return 'success'
  if (taskStatus.value === 'failed') return 'error'
  return taskStatus.value
})

const statusLabel = computed(() => {
  const labels = {
    idle: t('status.idle'), running: t('status.running'),
    completed: t('status.completed'), failed: t('status.failed')
  }
  return labels[taskStatus.value] || taskStatus.value
})

// ---- State ----
const refInfo = ref(null)
const dftInfo = ref(null)
const result = ref(null)
const reportInfo = ref(null)
const elementFilter = ref('')
const sortKey = ref('dist')
const sortDesc = ref(true)

const params = reactive({
  match: 'nearest',
  basis: 'ref'
})

const paramFields = computed(() => [
  { key: 'match', label: t('deviation.fields.match'), type: 'select',
    options: [
      { value: 'nearest', label: t('deviation.matchOpts.nearest') },
      { value: 'order', label: t('deviation.matchOpts.order') }
    ],
    help: t('deviation.fields.matchHelp') },
  { key: 'basis', label: t('deviation.fields.basis'), type: 'select',
    options: [
      { value: 'ref', label: t('deviation.basisOpts.ref') },
      { value: 'dft', label: t('deviation.basisOpts.dft') },
      { value: 'avg', label: t('deviation.basisOpts.avg') }
    ],
    help: t('deviation.fields.basisHelp') },
])

// ---- Helpers ----
function formatCell(cell) {
  if (!cell) return ''
  return `a=${(+cell.a).toFixed(3)} b=${(+cell.b).toFixed(3)} c=${(+cell.c).toFixed(3)} ` +
         `α=${(+cell.alpha).toFixed(1)}° β=${(+cell.beta).toFixed(1)}° γ=${(+cell.gamma).toFixed(1)}°`
}

function fmtSigned(v) {
  return (v >= 0 ? '+' : '') + v.toFixed(5)
}

function log(line) {
  consoleLogs.push(line)
}

const pairingLabel = computed(() =>
  result.value?.matchEffective === 'order'
    ? t('deviation.matchOpts.order')
    : t('deviation.matchOpts.nearest'))

const basisLabel = computed(() => {
  const map = { ref: 'ref', dft: 'dft', avg: 'avg' }
  return t(`deviation.basisOpts.${map[params.basis] || 'ref'}`)
})

const cellRows = computed(() => {
  if (!result.value) return []
  const c = result.value.cell
  const units = { a: ' (Å)', b: ' (Å)', c: ' (Å)', alpha: ' (°)', beta: ' (°)', gamma: ' (°)', volume: ' (Å³)' }
  const fmt = (v, k) => (+v).toFixed(k === 'volume' ? 3 : 5)
  const fmtD = (v, k) => (v >= 0 ? '+' : '') + (+v).toFixed(k === 'volume' ? 3 : 5)
  return ['a', 'b', 'c', 'alpha', 'beta', 'gamma', 'volume'].map((k) => ({
    key: k, unit: units[k],
    ref: fmt(c.ref[k], k), dft: fmt(c.dft[k], k),
    delta: fmtD(c.delta[k], k), pct: (c.deltaPct[k] >= 0 ? '+' : '') + (+c.deltaPct[k]).toFixed(3) + '%'
  }))
})

const visibleAtoms = computed(() => {
  if (!result.value) return []
  let rows = result.value.atoms
  if (elementFilter.value) {
    rows = rows.filter((a) => a.element === elementFilter.value)
  }
  const key = sortKey.value
  const dir = sortDesc.value ? -1 : 1
  return [...rows].sort((x, y) => (x[key] - y[key]) * dir)
})

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDesc.value = !sortDesc.value
  } else {
    sortKey.value = key
    sortDesc.value = key === 'dist'
  }
}

function sortArrow(key) {
  if (sortKey.value !== key) return ''
  return sortDesc.value ? ' ↓' : ' ↑'
}

// ---- Actions ----
async function onFilesSelected(files, slot) {
  if (!files || files.length === 0) return
  const file = files[files.length - 1]
  taskStatus.value = 'running'
  consoleLogs.length = 0
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await deviationUpload(fd)
    if (slot === 'ref') refInfo.value = res.data
    else dftInfo.value = res.data
    result.value = null
    reportInfo.value = null
    log(t('deviation.logs.uploaded', {
      slot: slot === 'ref' ? t('deviation.refSlot') : t('deviation.dftSlot'),
      name: res.data.originalName,
      n: res.data.nAtoms
    }))
    taskStatus.value = 'completed'
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'failed'
  }
}

async function runCompare() {
  if (!refInfo.value || !dftInfo.value) return
  taskStatus.value = 'running'
  comparing.value = true
  consoleLogs.length = 0
  log(t('deviation.logs.comparing'))
  try {
    const res = await deviationCompare({
      refFileId: refInfo.value.fileId,
      dftFileId: dftInfo.value.fileId,
      match: params.match,
      basis: params.basis
    })
    result.value = res.data
    reportInfo.value = null
    elementFilter.value = ''
    log(t('deviation.logs.done', {
      mean: res.data.stats.mean,
      max: res.data.stats.max,
      atom: res.data.stats.maxAtom
    }))
    for (const w of res.data.warnings || []) log(w)
    taskStatus.value = 'completed'
    activeSection.value = 'result'
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'failed'
  } finally {
    comparing.value = false
  }
}

async function runReport(format) {
  if (!refInfo.value || !dftInfo.value) return
  taskStatus.value = 'running'
  generating.value = true
  consoleLogs.length = 0
  try {
    const res = await deviationReport({
      refFileId: refInfo.value.fileId,
      dftFileId: dftInfo.value.fileId,
      match: params.match,
      basis: params.basis,
      format
    })
    reportInfo.value = res.data
    log(t('deviation.logs.reportDone', { name: res.data.filename }))
    taskStatus.value = 'completed'
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'failed'
  } finally {
    generating.value = false
  }
}

async function downloadReport() {
  if (!reportInfo.value) return
  try {
    const res = await deviationDownload(reportInfo.value.fileId)
    const url = URL.createObjectURL(new Blob([res.data], { type: 'text/plain;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = reportInfo.value.filename
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}
</script>

<style scoped>
.deviation-page { display: flex; flex-direction: column; }

.main-container { display: flex; flex: 1; }

/* ---- Sidebar ---- */
.sidebar {
  width: var(--sidebar-width, 220px);
  background: var(--color-neutral);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: calc(100vh - var(--header-height, 56px));
  align-self: flex-start;
}

.section-nav {
  flex: 1;
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  height: 34px;
  padding: 0 12px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}
.nav-item:hover { background: var(--color-surface); color: var(--color-text); }
.nav-item.active {
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
  color: var(--color-text);
}

.sidebar-footer {
  padding: 10px 14px;
  border-top: 1px solid var(--color-border);
}

.status-indicator {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; background: var(--color-surface);
  border-radius: 6px; font-size: 11px;
}
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--color-text-secondary); }
.status-dot.running { background: var(--color-warning); animation: pulse 2s infinite; }
.status-dot.success { background: var(--color-success); }
.status-dot.error { background: var(--color-error); }
.status-text { color: var(--color-text-secondary); }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* ---- Content ---- */
.content { flex: 1; padding: 24px; overflow-y: auto; min-width: 0; }
.section-panel { max-width: 1000px; }

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 28px;
}
.card-title { font-size: 18px; font-weight: 600; color: var(--color-text); margin: 0 0 8px; }
.card-desc { font-size: 13px; color: var(--color-text-secondary); line-height: 1.6; margin: 0 0 20px; }

.subsection-title {
  font-size: 14px; font-weight: 600; color: var(--color-primary);
  margin: 24px 0 12px;
}
.subsection-title:first-of-type { margin-top: 4px; }

.mono { font-family: 'JetBrains Mono', monospace; }
.dim { color: var(--color-text-secondary); }

/* ---- Upload grid ---- */
.upload-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
}
@media (max-width: 1100px) { .upload-grid { grid-template-columns: 1fr; } }

.slot-title {
  font-size: 13px; font-weight: 600; color: var(--color-text);
  margin: 0 0 10px;
}

.upload-summary { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.summary-chip {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: var(--color-neutral);
  border: 1px solid var(--color-border); border-radius: 8px;
}
.chip-label { font-size: 10.5px; color: var(--color-text-secondary); }
.chip-value { font-size: 12px; color: var(--color-text); font-weight: 600; }

/* ---- Warnings ---- */
.warnings-block { margin-top: 20px; }
.warning-list {
  margin: 0; padding: 10px 12px 10px 30px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: 8px;
  font-size: 12.5px; color: #92400E; line-height: 1.8;
}

/* ---- Actions ---- */
.actions-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 20px; }

.btn-primary {
  height: 38px; padding: 0 24px; background: var(--color-primary); color: white;
  border: none; border-radius: 6px; font-size: 13px; font-weight: 600;
  font-family: 'Inter', system-ui, sans-serif; cursor: pointer; transition: opacity 0.15s;
}
.btn-primary:hover { opacity: 0.9; }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-secondary {
  height: 38px; padding: 0 24px; background: transparent; color: var(--color-primary);
  border: 1px solid var(--color-primary); border-radius: 6px;
  font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s;
}
.btn-secondary:hover { background: var(--color-primary-10, rgba(124,58,237,0.08)); }
.btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }

/* ---- Stat grid ---- */
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 8px; }
.stat {
  display: flex; flex-direction: column; gap: 4px; align-items: center;
  padding: 18px 12px; background: var(--color-neutral);
  border: 1px solid var(--color-border); border-radius: 8px;
}
.stat-primary {
  background: var(--color-primary-10, rgba(124,58,237,0.08));
  border-color: var(--color-primary);
}
.stat-value { font-size: 24px; font-weight: 700; color: var(--color-text); font-family: 'JetBrains Mono', monospace; }
.stat-label { font-size: 11.5px; color: var(--color-text-secondary); text-align: center; }

.meta-row {
  display: flex; flex-wrap: wrap; gap: 18px; margin-top: 16px;
  font-size: 12.5px; color: var(--color-text-secondary);
}
.meta-item b { color: var(--color-text); font-weight: 600; }

/* ---- Data tables ---- */
.data-table {
  width: 100%; border-collapse: collapse;
  background: var(--color-neutral);
  border: 1px solid var(--color-border); border-radius: 8px;
  overflow: hidden; font-size: 12.5px;
}
.data-table th {
  text-align: left; padding: 8px 12px;
  background: var(--color-surface);
  color: var(--color-text-secondary); font-weight: 600; font-size: 11.5px;
  border-bottom: 1px solid var(--color-border);
}
.data-table td {
  padding: 7px 12px; border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
}
.data-table tr:last-child td { border-bottom: none; }

.cell-changed { color: #92400E; font-weight: 600; }

.th-sortable { cursor: pointer; user-select: none; }
.th-sortable:hover { color: var(--color-primary); }
.th-dist { text-align: right; }
td.dist { text-align: right; font-weight: 700; }
.row-max td { background: rgba(239, 68, 68, 0.08); }
.row-max td.dist { color: var(--color-error, #DC2626); }

.atoms-table { display: block; max-height: 480px; overflow-y: auto; }
.atoms-table thead, .atoms-table tbody { display: table; width: 100%; }
.atoms-table thead th { position: sticky; top: 0; z-index: 1; }

.atoms-header {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 0;
}
.atoms-header .subsection-title { margin-bottom: 12px; }
.element-filter {
  height: 30px; padding: 0 10px;
  background: var(--color-surface); color: var(--color-text);
  border: 1px solid var(--color-border); border-radius: 6px;
  font-size: 12px; font-family: 'Inter', system-ui, sans-serif;
}

/* ---- Preview ---- */
.preview-block { margin-top: 24px; }
.preview-meta { font-size: 11.5px; color: var(--color-text-secondary); font-weight: 400; margin-left: 10px; }
.preview-code {
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  line-height: 1.65;
  color: var(--color-text);
  max-height: 520px;
  overflow-y: auto;
  white-space: pre;
}

/* ---- Usage note ---- */
.usage-note { margin-top: 24px; }
.usage-steps {
  margin: 0;
  padding-left: 20px;
  font-size: 12.5px;
  color: var(--color-text-secondary);
  line-height: 1.8;
}

/* ---- Fade ---- */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-leave-to, .fade-enter-from { opacity: 0; }

@media (max-width: 1024px) {
  .sidebar { width: 52px; }
  .nav-label { display: none; }
  .sidebar-footer { display: none; }
}
</style>
