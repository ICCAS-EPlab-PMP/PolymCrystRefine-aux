<template>
  <div class="symmetry-page">
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

            <!-- Upload & detection -->
            <div v-if="activeSection === 'input'" class="card">
              <h2 class="card-title">{{ t('symmetry.sections.input') }}</h2>
              <p class="card-desc">{{ t('symmetry.desc') }}</p>

              <FileUpload
                accept=".cif,.CIF"
                :multiple="false"
                :label="t('symmetry.upload')"
                @files-selected="onFilesSelected"
              />

              <div v-if="uploadInfo" class="upload-summary">
                <div class="summary-chip">
                  <span class="chip-label">{{ t('symmetry.uploadInfo.file') }}</span>
                  <span class="chip-value">{{ uploadInfo.originalName }}</span>
                </div>
                <div class="summary-chip">
                  <span class="chip-label">{{ t('symmetry.uploadInfo.cell') }}</span>
                  <span class="chip-value mono">{{ formatCell(uploadInfo.cell) }}</span>
                </div>
                <div class="summary-chip">
                  <span class="chip-label">{{ t('symmetry.uploadInfo.atoms') }}</span>
                  <span class="chip-value">{{ uploadInfo.nAtoms }}</span>
                </div>
              </div>

              <ParamsForm :fields="paramFields" v-model="params" style="margin-top: 20px" />

              <div class="actions-row">
                <button class="btn-primary" @click="runAnalyze" :disabled="analyzing || !fileId">
                  {{ analyzing ? t('symmetry.actions.analyzing') : t('symmetry.actions.analyze') }}
                </button>
                <button class="btn-secondary" @click="runScan" :disabled="scanning || !fileId">
                  {{ scanning ? t('symmetry.actions.scanning') : t('symmetry.actions.scan') }}
                </button>
              </div>

              <ConsolePanel
                v-if="consoleLogs.length || taskStatus !== 'idle'"
                :status="taskStatus"
                :logs="consoleLogs"
                style="margin-top: 16px"
              />

              <!-- Tolerance sweep results -->
              <div v-if="scanRows.length" class="scan-block">
                <h3 class="subsection-title">{{ t('symmetry.scan.title') }}</h3>
                <p class="scan-hint">{{ t('symmetry.scan.hint') }}</p>
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>{{ t('symmetry.scan.symprec') }}</th>
                      <th>{{ t('symmetry.scan.sg') }}</th>
                      <th>{{ t('symmetry.scan.ops') }}</th>
                      <th>{{ t('symmetry.scan.asym') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, i) in scanRows" :key="i"
                        :class="{ 'row-current': Math.abs(row.symprec - params.symprec) < 1e-12 }">
                      <td class="mono">{{ row.symprec }}</td>
                      <td>{{ row.number !== null ? `#${row.number} ${row.hm}` : '—' }}</td>
                      <td>{{ row.nOperations }}</td>
                      <td>{{ row.nAsymmetricAtoms ?? '—' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Detection result -->
            <div v-if="activeSection === 'result'" class="card">
              <h2 class="card-title">{{ t('symmetry.sections.result') }}</h2>
              <p v-if="!result" class="card-desc">{{ t('symmetry.result.empty') }}</p>

              <template v-if="result">
                <!-- Headline space group -->
                <div class="sg-headline">
                  <div class="sg-number">#{{ result.spaceGroup.number }}</div>
                  <div class="sg-name">{{ result.spaceGroup.hmStandard }}</div>
                  <div class="sg-sub mono">Hall: {{ result.spaceGroup.hall }} · {{ result.spaceGroup.pointgroup }}</div>
                </div>

                <p class="hm-note">{{ t('symmetry.result.noteHm') }}</p>

                <!-- Key numbers -->
                <div class="stat-grid">
                  <div class="stat">
                    <span class="stat-value">{{ result.spaceGroup.nOperations }}</span>
                    <span class="stat-label">{{ t('symmetry.result.nOps') }}</span>
                  </div>
                  <div class="stat">
                    <span class="stat-value">{{ result.nAsymmetricAtoms }} / {{ result.nAtoms }}</span>
                    <span class="stat-label">{{ t('symmetry.result.asym') }}</span>
                  </div>
                  <div class="stat">
                    <span class="stat-value">{{ result.verification.maxShiftA }}</span>
                    <span class="stat-label">{{ t('symmetry.result.maxShift') }} (Å)</span>
                  </div>
                </div>

                <p v-if="result.verification.maxShiftA > 0.005" class="shift-note">
                  {{ t('symmetry.result.shiftNote', { v: result.verification.maxShiftA }) }}
                </p>
                <p v-if="!result.primitive.isInputPrimitive" class="supercell-note">
                  {{ t('symmetry.result.supercellWarn', { n: (1 / result.primitive.volumeRatio).toFixed(0) }) }}
                </p>

                <!-- Cell: unchanged by design -->
                <h3 class="subsection-title">{{ t('symmetry.result.inputCell') }}</h3>
                <p class="cell-value mono">{{ formatCell(result.inputCell) }}</p>

                <!-- Operations in the user's own basis -->
                <h3 class="subsection-title">{{ t('symmetry.result.opsTitle') }}</h3>
                <table class="data-table ops-table">
                  <tbody>
                    <tr v-for="op in result.operations" :key="op.id">
                      <td class="op-id">{{ op.id }}</td>
                      <td class="mono op-xyz">{{ op.xyz }}</td>
                    </tr>
                  </tbody>
                </table>

                <!-- Asymmetric unit -->
                <h3 class="subsection-title">{{ t('symmetry.result.asuTitle') }}</h3>
                <table class="data-table asu-table">
                  <thead>
                    <tr>
                      <th>{{ t('symmetry.result.label') }}</th>
                      <th>{{ t('symmetry.result.element') }}</th>
                      <th>Wyckoff</th>
                      <th>x</th>
                      <th>y</th>
                      <th>z</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="at in result.asymmetricAtoms" :key="at.label">
                      <td>{{ at.label }}</td>
                      <td>{{ at.element }}</td>
                      <td class="mono">{{ at.wyckoff }}</td>
                      <td class="mono">{{ at.frac[0].toFixed(5) }}</td>
                      <td class="mono">{{ at.frac[1].toFixed(5) }}</td>
                      <td class="mono">{{ at.frac[2].toFixed(5) }}</td>
                    </tr>
                  </tbody>
                </table>

                <!-- Standard setting reference (never applied) -->
                <details class="std-ref">
                  <summary>{{ t('symmetry.result.stdRef') }}</summary>
                  <p class="cell-value mono">{{ formatCell(result.standardSettingReference.cell) }}</p>
                  <p class="std-note">{{ t('symmetry.result.stdNote') }}</p>
                </details>
              </template>
            </div>

            <!-- Symmetrised export -->
            <div v-if="activeSection === 'export'" class="card">
              <h2 class="card-title">{{ t('symmetry.sections.export') }}</h2>
              <p class="card-desc">{{ t('symmetry.export.hint') }}</p>

              <div class="actions-row">
                <button class="btn-primary" @click="runSymmetrize('asu')" :disabled="symmetrizing || !fileId">
                  {{ symmetrizing && exportMode === 'asu' ? t('symmetry.actions.symmetrizing') : t('symmetry.actions.symmetrize') }}
                </button>
                <button class="btn-primary" @click="runSymmetrize('p1')" :disabled="symmetrizing || !fileId">
                  {{ symmetrizing && exportMode === 'p1' ? t('symmetry.actions.symmetrizingP1') : t('symmetry.actions.symmetrizeP1') }}
                </button>
                <button class="btn-secondary" @click="downloadExport" :disabled="!exportInfo">
                  {{ t('symmetry.actions.download') }}
                </button>
              </div>

              <div v-if="exportInfo" class="export-summary">
                <div class="summary-chip">
                  <span class="chip-label">{{ t('symmetry.uploadInfo.cell') }}</span>
                  <span class="chip-value mono">{{ formatCell(exportInfo.cell) }}</span>
                </div>
                <div class="summary-chip">
                  <span class="chip-label">{{ t('symmetry.result.nOps') }}</span>
                  <span class="chip-value">{{ exportInfo.nOperations }}</span>
                </div>
                <div v-if="exportInfo.mode === 'p1'" class="summary-chip">
                  <span class="chip-label">{{ t('symmetry.uploadInfo.atoms') }}</span>
                  <span class="chip-value">{{ exportInfo.nAtoms }}</span>
                </div>
                <div v-else class="summary-chip">
                  <span class="chip-label">{{ t('symmetry.result.asym') }}</span>
                  <span class="chip-value">{{ exportInfo.nAsymmetricAtoms }}</span>
                </div>
                <div v-if="exportInfo.mode === 'p1' && exportInfo.idealization" class="summary-chip">
                  <span class="chip-label">{{ t('symmetry.result.maxShift') }} (Å)</span>
                  <span class="chip-value">{{ exportInfo.idealization.maxShiftA }}</span>
                </div>
              </div>

              <ConsolePanel
                v-if="consoleLogs.length || taskStatus !== 'idle'"
                :status="taskStatus"
                :logs="consoleLogs"
                style="margin-top: 16px"
              />

              <div v-if="exportInfo" class="preview-block">
                <h3 class="subsection-title">{{ t('symmetry.export.preview') }}</h3>
                <pre class="preview-code"><code>{{ exportInfo.cif }}</code></pre>
              </div>

              <p v-if="exportInfo && exportInfo.mode === 'p1'" class="card-desc" style="margin-top: 16px">
                {{ t('symmetry.export.hintP1') }}
              </p>

              <div class="usage-note">
                <h3 class="subsection-title">{{ t('symmetry.usage.title') }}</h3>
                <ol class="usage-steps">
                  <li>{{ t('symmetry.usage.step1') }}</li>
                  <li>{{ t('symmetry.usage.step2') }}</li>
                  <li>{{ t('symmetry.usage.step3') }}</li>
                  <li>{{ t('symmetry.usage.step4') }}</li>
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
  symmetryUpload,
  symmetryAnalyze,
  symmetryScan,
  symmetrySymmetrize,
  symmetryDownload
} from '@/api/index.js'

const { t } = useI18n()

// ---- Sections ----
const sections = computed(() => [
  { id: 'input', label: t('symmetry.sections.input') },
  { id: 'result', label: t('symmetry.sections.result') },
  { id: 'export', label: t('symmetry.sections.export') },
])

const activeSection = ref('input')

// ---- Status ----
const taskStatus = ref('idle')
const consoleLogs = reactive([])
const analyzing = ref(false)
const scanning = ref(false)
const symmetrizing = ref(false)
const exportMode = ref('asu')

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
const fileId = ref('')
const uploadInfo = ref(null)
const result = ref(null)
const scanRows = ref([])
const exportInfo = ref(null)

const params = reactive({
  symprec: 0.001
})

const paramFields = computed(() => [
  { key: 'symprec', label: t('symmetry.fields.symprec'), type: 'number',
    step: 0.0005, min: 0.00001, max: 1.0,
    help: t('symmetry.fields.symprecHelp') },
])

// ---- Helpers ----
function formatCell(cell) {
  if (!cell) return ''
  return `a=${cell.a.toFixed(4)}  b=${cell.b.toFixed(4)}  c=${cell.c.toFixed(4)}  ` +
         `α=${cell.alpha.toFixed(2)}°  β=${cell.beta.toFixed(2)}°  γ=${cell.gamma.toFixed(2)}°`
}

function log(line) {
  consoleLogs.push(line)
}

// ---- Actions ----
async function onFilesSelected(files) {
  if (!files || files.length === 0) return
  const file = files[files.length - 1]
  taskStatus.value = 'running'
  consoleLogs.length = 0
  result.value = null
  scanRows.value = []
  exportInfo.value = null
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await symmetryUpload(fd)
    fileId.value = res.data.fileId
    uploadInfo.value = res.data
    log(t('symmetry.logs.uploaded', { name: res.data.originalName, n: res.data.nAtoms }))
    taskStatus.value = 'completed'
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'failed'
  }
}

async function runAnalyze() {
  if (!fileId.value) return
  taskStatus.value = 'running'
  analyzing.value = true
  consoleLogs.length = 0
  log(t('symmetry.logs.analyzing', { v: params.symprec }))
  try {
    const res = await symmetryAnalyze({ fileId: fileId.value, symprec: params.symprec })
    result.value = res.data
    log(t('symmetry.logs.detected', {
      number: res.data.spaceGroup.number,
      hm: res.data.spaceGroup.hmStandard,
      ops: res.data.spaceGroup.nOperations
    }))
    taskStatus.value = 'completed'
    activeSection.value = 'result'
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'failed'
  } finally {
    analyzing.value = false
  }
}

async function runScan() {
  if (!fileId.value) return
  taskStatus.value = 'running'
  scanning.value = true
  log(t('symmetry.logs.scanning'))
  try {
    const res = await symmetryScan({ fileId: fileId.value })
    scanRows.value = res.data.scan
    log(t('symmetry.logs.scanDone'))
    taskStatus.value = 'completed'
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'failed'
  } finally {
    scanning.value = false
  }
}

async function runSymmetrize(mode) {
  if (!fileId.value) return
  taskStatus.value = 'running'
  symmetrizing.value = true
  exportMode.value = mode
  consoleLogs.length = 0
  log(mode === 'p1'
    ? t('symmetry.logs.symmetrizingP1', { v: params.symprec })
    : t('symmetry.logs.symmetrizing', { v: params.symprec }))
  try {
    const name = uploadInfo.value?.originalName || 'symmetrized'
    const res = await symmetrySymmetrize({
      fileId: fileId.value,
      symprec: params.symprec,
      filename: name,
      mode
    })
    exportInfo.value = res.data
    log(mode === 'p1'
      ? t('symmetry.logs.exportedP1', {
          n: res.data.nAtoms,
          s: res.data.idealization ? res.data.idealization.maxShiftA : 0
        })
      : t('symmetry.logs.exported', { n: res.data.nAsymmetricAtoms }))
    taskStatus.value = 'completed'
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'failed'
  } finally {
    symmetrizing.value = false
  }
}

async function downloadExport() {
  if (!exportInfo.value) return
  try {
    const res = await symmetryDownload(exportInfo.value.fileId)
    const url = URL.createObjectURL(new Blob([res.data], { type: 'chemical/x-cif' }))
    const a = document.createElement('a')
    a.href = url
    a.download = exportInfo.value.filename
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}
</script>

<style scoped>
.symmetry-page { display: flex; flex-direction: column; }

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
.section-panel { max-width: 900px; }

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

/* ---- Upload summary chips ---- */
.upload-summary, .export-summary {
  display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px;
}
.summary-chip {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px; background: var(--color-neutral);
  border: 1px solid var(--color-border); border-radius: 8px;
}
.chip-label { font-size: 11px; color: var(--color-text-secondary); }
.chip-value { font-size: 12.5px; color: var(--color-text); font-weight: 600; }

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

/* ---- Scan table ---- */
.scan-block { margin-top: 24px; }
.scan-hint { font-size: 12px; color: var(--color-text-secondary); line-height: 1.6; margin: 0 0 12px; }

/* ---- Space-group headline ---- */
.sg-headline {
  display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
  padding: 18px 22px; border-radius: 10px;
  background: var(--color-primary-10, rgba(124,58,237,0.08));
  border: 1px solid var(--color-border);
}
.sg-number {
  font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700;
  color: var(--color-primary);
}
.sg-name { font-size: 26px; font-weight: 700; color: var(--color-text); letter-spacing: 0.02em; }
.sg-sub { font-size: 12px; color: var(--color-text-secondary); }

.hm-note {
  font-size: 12px; color: var(--color-text-secondary); line-height: 1.6;
  margin: 12px 0 0;
}

/* ---- Stat grid ---- */
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 20px; }
.stat {
  display: flex; flex-direction: column; gap: 4px; align-items: center;
  padding: 16px 12px; background: var(--color-neutral);
  border: 1px solid var(--color-border); border-radius: 8px;
}
.stat-value { font-size: 20px; font-weight: 700; color: var(--color-text); font-family: 'JetBrains Mono', monospace; }
.stat-label { font-size: 11.5px; color: var(--color-text-secondary); text-align: center; }

.shift-note, .supercell-note {
  font-size: 12px; line-height: 1.6; margin: 12px 0 0;
  padding: 8px 12px; border-radius: 6px;
}
.shift-note { color: #92400E; background: rgba(245, 158, 11, 0.10); }
.supercell-note { color: #92400E; background: rgba(245, 158, 11, 0.10); }

.cell-value { font-size: 13px; color: var(--color-text); margin: 0; }

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
.data-table .row-current td { background: var(--color-primary-10, rgba(124,58,237,0.08)); }

.ops-table td.op-id { width: 40px; color: var(--color-text-secondary); }
.ops-table td.op-xyz { font-size: 13px; font-weight: 600; }

.asu-table { display: block; max-height: 320px; overflow-y: auto; }
.asu-table thead, .asu-table tbody { display: table; width: 100%; }

/* ---- Standard-setting reference ---- */
.std-ref { margin-top: 24px; }
.std-ref summary {
  font-size: 12.5px; color: var(--color-text-secondary); cursor: pointer;
  padding: 10px 12px; background: var(--color-neutral);
  border: 1px dashed var(--color-border); border-radius: 8px;
  user-select: none;
}
.std-ref[open] summary { border-style: solid; }
.std-ref .cell-value { margin: 12px 0 0; }
.std-note { font-size: 12px; color: var(--color-text-secondary); line-height: 1.6; margin: 8px 0 0; }

/* ---- Preview ---- */
.preview-block { margin-top: 24px; }
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
  max-height: 500px;
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
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 1024px) {
  .sidebar { width: 52px; }
  .nav-label { display: none; }
  .sidebar-footer { display: none; }
}
</style>
