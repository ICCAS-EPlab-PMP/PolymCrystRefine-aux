<template>
  <div class="cifh-page">
    <div class="page-card">
      <h2 class="card-title">{{ t('cifh.title') }}</h2>
      <p class="card-desc">{{ t('cifh.desc') }}</p>

      <!-- Step 1: upload -->
      <FileUpload
        accept=".cif"
        :multiple="false"
        :label="t('cifh.upload')"
        @files-selected="onCifSelected"
      />

      <p v-if="summaryLine" class="result-meta" style="margin-top: 10px;">
        {{ summaryLine }}
      </p>

      <!-- Parameters -->
      <div v-if="fileId" class="param-row">
        <div class="param-field">
          <label class="param-label">{{ t('cifh.tolerance') }}</label>
          <input type="number" v-model.number="tolerance" step="0.05" min="0.1" max="1.2" class="param-input" />
        </div>
        <div class="param-field">
          <label class="param-label">{{ t('cifh.chDist') }}</label>
          <input type="number" v-model.number="chDist" step="0.01" min="0.8" max="1.3" class="param-input" />
        </div>
        <button class="btn-primary" :disabled="loading" @click="runHydrogenation" style="align-self: flex-end;">
          {{ loading ? t('cifh.running') : t('cifh.rerun') }}
        </button>
      </div>

      <ConsolePanel
        v-if="consoleLogs.length || taskStatus !== 'idle'"
        :status="taskStatus"
        :logs="consoleLogs"
        style="margin-top: 16px"
      />
    </div>

    <!-- Step 2/3: structure view + bond editing -->
    <div v-if="atoms.length" class="page-card" style="margin-top: 20px;">
      <div class="view-head">
        <h3 class="section-title">{{ t('cifh.view.title') }}</h3>
        <div class="view-toggles">
          <label class="toggle"><input type="checkbox" v-model="showCell" />{{ t('cifh.view.cell') }}</label>
          <label class="toggle"><input type="checkbox" v-model="showH" />{{ t('cifh.view.h') }}</label>
        </div>
      </div>

      <div class="main-grid">
        <div class="viewer-col">
          <Structure3D
            :atoms="atoms"
            :bonds="displayBonds"
            :cell-vectors="cellVectors"
            :show-cell="showCell"
            :show-h="showH"
            :selected-bond-key="selectedBondKey"
            :picked-atoms="pickedAtoms"
            :height="560"
            :hint="viewerHint"
            @atom-clicked="onAtomClicked"
            @bond-clicked="onBondClicked"
          />
          <div class="legend">
            <span v-for="(c, el) in elementColors" :key="el" class="legend-item">
              <span class="legend-dot" :style="{ background: c }"></span>{{ el }}
            </span>
            <span class="legend-item legend-dim">— {{ t('cifh.view.double') }}</span>
            <span class="legend-item legend-dim">··· {{ t('cifh.view.stretched') }}</span>
          </div>
        </div>

        <div class="side-col">
          <!-- Add-bond mode -->
          <div class="side-block">
            <div class="side-block-head">
              <label class="side-title">{{ t('cifh.edit.title') }}</label>
              <button :class="['btn-compact', { 'btn-mode--active': addMode }]" @click="toggleAddMode">
                {{ addMode ? t('cifh.edit.cancelAdd') : t('cifh.edit.addBond') }}
              </button>
            </div>
            <p v-if="addMode" class="side-hint">
              {{ pickedAtoms.length
                  ? t('cifh.edit.picked', { n: pickedAtoms.length })
                  : t('cifh.edit.pickHint') }}
            </p>
            <p v-if="pendingPair" class="side-hint pending">{{ pendingBondInfo }}</p>
            <div v-if="pendingPair" class="btn-row">
              <button class="btn-compact btn-mode--active" @click="confirmPendingBond">
                {{ t('cifh.edit.confirmAdd') }}
              </button>
              <button class="btn-compact" @click="resetPicking">
                {{ t('cifh.edit.repick') }}
              </button>
            </div>
          </div>

          <!-- Selected bond editor -->
          <div v-if="selectedBond" class="side-block">
            <label class="side-title">{{ t('cifh.edit.selected') }}</label>
            <div class="bond-info">
              <code>{{ bondLabel(selectedBond) }}</code>
              <span>{{ selectedBond.dist.toFixed(3) }} Å</span>
              <span>{{ selectedBond.order === 1 ? t('cifh.edit.single') : '='.repeat(selectedBond.order - 1) }}</span>
              <span v-if="selectedBond.stretched" class="tag-warn">{{ t('cifh.view.stretched') }}</span>
            </div>
            <div class="btn-row">
              <button class="btn-compact" @click="toggleSelectedOrder">
                {{ selectedBond.order > 1 ? t('cifh.edit.toSingle') : t('cifh.edit.toDouble') }}
              </button>
              <button v-if="isRemoved(selectedBond.key)" class="btn-compact" @click="restoreBond(selectedBond.key)">
                {{ t('cifh.edit.restore') }}
              </button>
              <button v-else class="btn-compact btn-danger" @click="removeBond(selectedBond.key)">
                {{ t('cifh.edit.delete') }}
              </button>
            </div>
          </div>

          <!-- Warnings -->
          <div v-if="warnings.length" class="side-block">
            <label class="side-title">{{ t('cifh.warnings') }}</label>
            <ul class="warning-list">
              <li v-for="(w, i) in warnings" :key="i">{{ w }}</li>
            </ul>
          </div>

          <!-- Bond table -->
          <div class="side-block bond-table-block">
            <div class="side-block-head">
              <label class="side-title">{{ t('cifh.bonds.title') }}</label>
              <label class="toggle"><input type="checkbox" v-model="showHBonds" />{{ t('cifh.bonds.showH') }}</label>
            </div>
            <div class="bond-table-wrap">
              <table class="bond-table">
                <thead>
                  <tr>
                    <th>{{ t('cifh.bonds.pair') }}</th>
                    <th>d (Å)</th>
                    <th>{{ t('cifh.bonds.order') }}</th>
                    <th>sym</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="b in tableBonds"
                    :key="b.key"
                    :class="{ selected: b.key === selectedBondKey, removed: isRemoved(b.key) }"
                    @click="selectedBondKey = b.key"
                  >
                    <td>{{ bondLabel(b) }}</td>
                    <td>{{ b.dist.toFixed(3) }}</td>
                    <td>{{ b.order > 1 ? '='.repeat(b.order - 1) : '—' }}</td>
                    <td>{{ b.symmetry }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 4: export -->
      <div class="export-row">
        <span class="result-meta">{{ t('cifh.export.hint') }}</span>
        <button class="btn-primary" :disabled="exporting" @click="exportCif">
          {{ exporting ? t('cifh.export.exporting') : t('cifh.export.btn') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import FileUpload from '@/components/FileUpload.vue'
import ConsolePanel from '@/components/ConsolePanel.vue'
import Structure3D from '@/components/Structure3D.vue'
import { cifhUpload, cifhAddHydrogens, cifhExport, cifhDownload } from '@/api/index.js'
import { saveBlob } from '@/services/download.js'

const { t } = useI18n()

// ---- Upload / params ----
const fileId = ref(null)
const fileName = ref('')
const tolerance = ref(0.40)
const chDist = ref(1.09)
const loading = ref(false)
const exporting = ref(false)
const taskStatus = ref('idle')
const consoleLogs = ref([])

// ---- Structure state (from backend) ----
const atoms = ref([])
const bonds = ref([])
const cellVectors = ref(null)
const warnings = ref([])
const stats = reactive({ nAtoms: 0, nHeavy: 0, nH: 0, formula: '' })
const uploadInfo = reactive({ a: 0, b: 0, c: 0, alpha: 0, beta: 0, gamma: 0, counts: {} })

// ---- Edits (applied on re-run; heavy-atom bond keys stay stable) ----
const removedKeys = ref([])
const addedBonds = ref([])          // [{i, j, offset}]
const orderOverrides = ref({})      // key -> 1|2

// ---- UI state ----
const selectedBondKey = ref(null)
const addMode = ref(false)
const pickedAtoms = ref([])
const pendingPair = ref(null)       // {i, j, offset, dist}
const showCell = ref(true)
const showH = ref(true)
const showHBonds = ref(false)

const CPK = {
  H: '#F3F4F6', C: '#4B5563', N: '#3050F8', O: '#FF0D0D', F: '#90E050',
  Si: '#F0C8A0', P: '#FF8000', S: '#FFFF30', Cl: '#1FF01F', Br: '#A62929',
  I: '#940094', Se: '#FFA100',
}
const elementColors = computed(() => {
  const m = {}
  for (const a of atoms.value) m[a.element] = CPK[a.element] || '#9CA3AF'
  return m
})

const summaryLine = computed(() => {
  if (!fileId.value) return ''
  const cell = uploadInfo
  const counts = Object.entries(uploadInfo.counts || {})
    .map(([el, n]) => `${el}×${n}`).join('  ')
  return t('cifh.summary', {
    name: fileName.value,
    atoms: stats.nHeavy || Object.values(uploadInfo.counts || {}).reduce((s, v) => s + v, 0),
    cell: `a=${cell.a?.toFixed(3)} b=${cell.b?.toFixed(3)} c=${cell.c?.toFixed(3)} α=${cell.alpha?.toFixed(1)}° β=${cell.beta?.toFixed(1)}° γ=${cell.gamma?.toFixed(1)}°`,
    counts,
    h: stats.nH,
    formula: stats.formula,
  })
})

const selectedBond = computed(() => bonds.value.find(b => b.key === selectedBondKey.value) || null)

// 3D viewer bonds: locally-removed bonds greyed as dashed rather than hidden,
// so the pending edit is visible before re-running.
const displayBonds = computed(() =>
  bonds.value.map(b => ({ ...b, stretched: b.stretched || isRemoved(b.key) })))

const tableBonds = computed(() => {
  const list = showHBonds.value ? bonds.value : bonds.value.filter(b => !b.isH)
    return list.slice().sort((x, y) => (x.i - y.i) || (x.j - y.j))
})

const viewerHint = computed(() => {
  if (addMode.value) return t('cifh.edit.pickHint')
  return t('cifh.view.hint')
})

const pendingBondInfo = computed(() => {
  if (!pendingPair.value) return ''
  const p = pendingPair.value
  const li = atoms.value.find(a => a.index === p.i)?.label || p.i
  const lj = atoms.value.find(a => a.index === p.j)?.label || p.j
  return t('cifh.edit.pendingInfo', { a: li, b: lj, d: p.dist.toFixed(2) })
})

function bondLabel(b) {
  const li = atoms.value.find(a => a.index === b.i)?.label || b.i
  const lj = atoms.value.find(a => a.index === b.j)?.label || b.j
  return `${li}–${lj}`
}
function isRemoved(key) { return removedKeys.value.includes(key) }

function log(msg) { consoleLogs.value.push(msg) }

// ---- Upload → auto hydrogenate ----
async function onCifSelected(files) {
  if (!files.length) return
  loading.value = true
  taskStatus.value = 'running'
  consoleLogs.value = [t('cifh.logs.uploadStart')]
  try {
    const fd = new FormData()
    fd.append('file', files[0])
    const up = await cifhUpload(fd)
    const d = up.data || {}
    fileId.value = d.fileId
    fileName.value = d.originalName || 'structure.cif'
    Object.assign(uploadInfo, d.cell || {}, { counts: d.counts || {} })
    log(t('cifh.logs.uploaded', { n: d.nAtoms }))
    removedKeys.value = []
    addedBonds.value = []
    orderOverrides.value = {}
    selectedBondKey.value = null
    addMode.value = false
    pickedAtoms.value = []
    pendingPair.value = null
    await runHydrogenation()
  } catch (err) {
    taskStatus.value = 'error'
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    loading.value = false
  }
}

// ---- Run / re-run hydrogenation with current edits ----
async function runHydrogenation() {
  if (!fileId.value) return
  loading.value = true
  taskStatus.value = 'running'
  try {
    const resp = await cifhAddHydrogens({
      fileId: fileId.value,
      tolerance: tolerance.value,
      chDist: chDist.value,
      removeBonds: removedKeys.value,
      addBonds: addedBonds.value,
      orderOverrides: orderOverrides.value,
    })
    const d = resp.data || {}
    atoms.value = d.atoms || []
    bonds.value = d.bonds || []
    cellVectors.value = d.cell?.vectors || null
    warnings.value = d.warnings || []
    Object.assign(stats, d.stats || {})
    // Drop references to bonds that no longer exist.
    if (selectedBondKey.value && !bonds.value.some(b => b.key === selectedBondKey.value)) {
      selectedBondKey.value = null
    }
    log(t('cifh.logs.done', { h: stats.nH, formula: stats.formula }))
    taskStatus.value = 'completed'
  } catch (err) {
    taskStatus.value = 'error'
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  } finally {
    loading.value = false
  }
}

// ---- Bond interactions ----
function onBondClicked(key) {
  if (addMode.value) return
  selectedBondKey.value = key
}

// Canonical bond key, mirroring the backend: i<j, offset negated on swap.
function canonicalKey(i, j, offset) {
  let ii = i, jj = j
  let off = [...offset]
  if (ii > jj) {
    ;[ii, jj] = [jj, ii]
    off = off.map(v => -v)
  }
  return `${ii}:${jj}:${off[0]}:${off[1]}:${off[2]}`
}

async function removeBond(key) {
  if (!removedKeys.value.includes(key)) removedKeys.value.push(key)
  // If the bond was user-added, drop the addition instead of stacking edits.
  addedBonds.value = addedBonds.value.filter(
    b => canonicalKey(b.i, b.j, b.offset) !== key)
  await runHydrogenation()
}

async function restoreBond(key) {
  removedKeys.value = removedKeys.value.filter(k => k !== key)
  await runHydrogenation()
}

async function toggleSelectedOrder() {
  const b = selectedBond.value
  if (!b) return
  orderOverrides.value = {
    ...orderOverrides.value,
    [b.key]: b.order > 1 ? 1 : 2,
  }
  await runHydrogenation()
}

// ---- Add-bond mode ----
function toggleAddMode() {
  addMode.value = !addMode.value
  pickedAtoms.value = []
  pendingPair.value = null
  selectedBondKey.value = null
}

function onAtomClicked(index) {
  if (!addMode.value) return
  if (pickedAtoms.value.includes(index)) return
  pickedAtoms.value.push(index)
  if (pickedAtoms.value.length === 2) {
    const [i, j] = pickedAtoms.value
    const ai = atoms.value.find(a => a.index === i)
    const aj = atoms.value.find(a => a.index === j)
    if (!ai || !aj) { pickedAtoms.value = []; return }
    // Bond offset in the true cell = difference of the atoms' display image
    // offsets, so the bond connects the two atoms exactly as drawn.
    const offset = [
      aj.dispOffset[0] - ai.dispOffset[0],
      aj.dispOffset[1] - ai.dispOffset[1],
      aj.dispOffset[2] - ai.dispOffset[2],
    ]
    const dx = aj.dispCart[0] - ai.dispCart[0]
    const dy = aj.dispCart[1] - ai.dispCart[1]
    const dz = aj.dispCart[2] - ai.dispCart[2]
    pendingPair.value = { i, j, offset, dist: Math.sqrt(dx * dx + dy * dy + dz * dz) }
  }
}

function resetPicking() {
  pickedAtoms.value = []
  pendingPair.value = null
}

async function confirmPendingBond() {
  const p = pendingPair.value
  if (!p) return
  addedBonds.value.push({ i: p.i, j: p.j, offset: p.offset })
  pendingPair.value = null
  pickedAtoms.value = []
  addMode.value = false
  await runHydrogenation()
}

// ---- Export ----
async function exportCif() {
  if (!fileId.value) return
  exporting.value = true
  try {
    const resp = await cifhExport({
      fileId: fileId.value,
      tolerance: tolerance.value,
      chDist: chDist.value,
      removeBonds: removedKeys.value,
      addBonds: addedBonds.value,
      orderOverrides: orderOverrides.value,
      filename: fileName.value.replace(/\.cif$/i, ''),
    })
    const d = resp.data || {}
    const dl = await cifhDownload(d.fileId)
    const name = d.filename || 'hydrogenated.cif'
    await saveBlob(new Blob([dl.data], { type: 'chemical/x-cif' }), name)
    log(t('cifh.logs.exported', { name, n: d.nAtoms }))
  } catch (err) {
    log(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.cifh-page {
  display: flex;
  flex-direction: column;
  max-width: 1200px;
}
.page-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 28px;
}
.card-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 8px;
}
.card-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin: 0 0 20px;
}
.result-meta {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0;
}

.param-row {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  margin-top: 16px;
  flex-wrap: wrap;
}
.param-field { display: flex; flex-direction: column; gap: 4px; }
.param-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.param-input {
  width: 120px;
  height: 30px;
  padding: 0 8px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text);
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}
.btn-primary {
  height: 34px;
  padding: 0 20px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.view-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 10px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
  margin: 0;
}
.view-toggles { display: flex; gap: 14px; }
.toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(300px, 1fr);
  gap: 18px;
}
@media (max-width: 980px) {
  .main-grid { grid-template-columns: 1fr; }
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.legend-item { display: inline-flex; align-items: center; gap: 5px; }
.legend-dot {
  width: 10px; height: 10px; border-radius: 50%;
  border: 1px solid var(--color-border);
  display: inline-block;
}
.legend-dim { opacity: 0.75; }

.side-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.side-block {
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 12px 14px;
}
.side-block-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.side-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.side-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 6px 0 0;
  line-height: 1.5;
}
.side-hint.pending { color: var(--color-primary); font-weight: 600; }

.btn-row { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.btn-compact {
  padding: 5px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-size: 12px;
  cursor: pointer;
}
.btn-compact:hover { border-color: var(--color-primary); color: var(--color-text); }
.btn-mode--active {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
}
.btn-danger { border-color: var(--color-error); color: var(--color-error); }

.bond-info {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: var(--color-text);
  flex-wrap: wrap;
}
.bond-info code {
  font-family: 'JetBrains Mono', monospace;
  background: var(--color-surface);
  padding: 2px 6px;
  border-radius: 4px;
}
.tag-warn {
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--color-warning);
  color: #fff;
  font-size: 11px;
}

.warning-list {
  margin: 4px 0 0;
  padding-left: 16px;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  max-height: 110px;
  overflow-y: auto;
}

.bond-table-block { display: flex; flex-direction: column; }
.bond-table-wrap {
  max-height: 260px;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 6px;
}
.bond-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}
.bond-table th {
  position: sticky;
  top: 0;
  background: var(--color-surface);
  padding: 6px 8px;
  text-align: left;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
.bond-table td {
  padding: 4px 8px;
  border-bottom: 1px solid var(--color-border);
  font-family: 'JetBrains Mono', monospace;
  color: var(--color-text);
  white-space: nowrap;
}
.bond-table tbody tr { cursor: pointer; }
.bond-table tbody tr:hover { background: var(--color-surface); }
.bond-table tbody tr.selected { background: var(--color-primary-10, rgba(124, 58, 237, 0.08)); }
.bond-table tbody tr.removed td { text-decoration: line-through; opacity: 0.5; }

.export-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
  gap: 12px;
  flex-wrap: wrap;
}
</style>
