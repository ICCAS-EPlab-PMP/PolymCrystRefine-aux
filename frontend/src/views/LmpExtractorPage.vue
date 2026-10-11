<template>
  <div class="lmp-page">
    <div class="main-container">
      <main class="content">
        <!-- Step 1: Upload -->
        <div class="card">
          <h2 class="card-title">{{ t('lmp.sections.upload') }}</h2>
          <p class="card-desc">{{ t('lmp.descs.upload') }}</p>

          <!-- OPLSAA / LigParGen notice -->
          <div class="oplsaa-notice">
            <div class="oplsaa-notice-title">⬡ {{ t('lmp.notices.title') }}</div>
            <p class="oplsaa-notice-body">{{ t('lmp.notices.body') }}</p>
            <a
              class="oplsaa-notice-link"
              :href="t('lmp.notices.url')"
              @click.prevent="openExternalLink(t('lmp.notices.url'))"
            >🔗 {{ t('lmp.notices.link') }}<span class="oplsaa-notice-url">zarbi.chem.yale.edu/ligpargen</span></a>
          </div>

          <div class="upload-row">
            <div class="upload-col">
              <h3 class="subsection-title">{{ t('lmp.subsections.structFile') }}</h3>
              <FileUpload
                accept=".pdb,.mol,.sdf,.xyz,.cif,.gro"
                :multiple="false"
                :label="t('lmp.labels.dropStruct')"
                @files-selected="onStructSelected"
              />
              <p v-if="structFileName" class="file-loaded">✓ {{ structFileName }}</p>
            </div>
            <div class="upload-col">
              <h3 class="subsection-title">{{ t('lmp.subsections.lmpFile') }}</h3>
              <FileUpload
                accept=".data,.lmp,.txt"
                :multiple="false"
                :label="t('lmp.labels.dropLmp')"
                @files-selected="onLmpSelected"
              />
              <p v-if="lmpFileName" class="file-loaded">✓ {{ lmpFileName }}</p>
            </div>
          </div>

          <button
            class="btn-primary"
            style="margin-top:16px"
            :disabled="!structFile || !structFileId || !lmpFile || validating"
            @click="runValidation"
          >
            {{ validating ? t('lmp.actions.validating') : t('lmp.actions.validate') }}
          </button>

          <ConsolePanel
            v-if="consoleLogs.length || taskStatus !== 'idle'"
            :status="taskStatus"
            :logs="consoleLogs"
            style="margin-top: 16px"
          />
        </div>

        <!-- 3D Structure viewer — can be undocked into a draggable floating
             card so it stays visible while picking atoms in the mapping table -->
        <div
          v-if="structAtoms.length"
          class="card viewer-card"
          :class="{ floating: viewerFloating }"
          :style="viewerFloatStyle"
          style="margin-top: 24px"
        >
          <div class="viewer-card-head" @pointerdown="onViewerDragStart">
            <h2 class="card-title" style="margin:0">
              {{ t('lmp.sections.viewer') }}
              <span v-if="viewerFloating" class="viewer-drag-grip" :title="t('lmp.hints.floatTip')">⠿</span>
            </h2>
            <button
              class="btn-compact viewer-float-btn"
              @pointerdown.stop
              @click="viewerFloating = !viewerFloating"
            >
              {{ viewerFloating ? '⧉ ' + t('lmp.actions.dockViewer') : '⇱ ' + t('lmp.actions.floatViewer') }}
            </button>
          </div>

          <p v-if="!viewerFloating" class="card-desc">{{ t('lmp.descs.viewer') }}</p>
          <p v-else class="card-desc">{{ t('lmp.hints.floatTip') }}</p>

          <div class="viewer-toolbar">
            <label class="toggle-label">
              <input type="checkbox" v-model="showAtomLabels" />
              <span>{{ t('lmp.actions.showNumbers') }}</span>
            </label>
            <label class="toggle-label">
              <input type="checkbox" v-model="hideHydrogen" />
              <span>{{ t('lmp.actions.hideH') }}</span>
            </label>
            <span class="toolbar-hint">{{ t('lmp.hints.bondsAuto') }}</span>
          </div>

          <div ref="molViewerContainer" class="mol-viewer"></div>

          <p class="legend-line">
            <span class="leg-item"><span class="leg-dash solid"></span>{{ t('lmp.hints.bondNormal') }}</span>
            <span class="leg-item"><span class="leg-ring periodic"></span>{{ t('lmp.hints.periodicAtomRing') }}</span>
          </p>
        </div>

        <!-- Validation details (collapsible) -->
        <div v-if="validationDone" class="card" style="margin-top: 24px">
          <div class="card-header-toggle" @click="showValDetails = !showValDetails">
            <h2 class="card-title" style="margin:0">
              {{ t('lmp.sections.validateResult') }}
              <span :class="validationOk ? 'val-ok' : 'val-warn'" class="val-inline-msg">
                {{ validationMsg }}
              </span>
            </h2>
            <span class="collapse-icon">{{ showValDetails ? '▲' : '▼' }}</span>
          </div>

          <div v-if="showValDetails" class="card-body">
            <p v-for="(w, i) in validationWarnings" :key="i" class="val-warning-msg">⚠ {{ w }}</p>

            <div v-if="typeElements.length" class="val-compare-row">
              <!-- Left: Type → Element -->
              <div class="val-compare-col">
                <h3 class="subsection-title">{{ t('lmp.subsections.typeElement') }}</h3>
                <div class="mini-table-wrap mini-table-scroll">
                  <table class="mini-table">
                    <thead>
                      <tr>
                        <th>{{ t('lmp.cols.typeId') }}</th>
                        <th>{{ t('lmp.cols.mass') }}</th>
                        <th>{{ t('lmp.cols.element') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="te in typeElements" :key="te.type">
                        <td>{{ te.type }}</td>
                        <td>{{ te.mass != null ? Number(te.mass).toFixed(3) : '?' }}</td>
                        <td :class="te.element === '?' ? 'cell-mismatch' : 'cell-element'">{{ te.element }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Right: Element composition comparison -->
              <div class="val-compare-col">
                <h3 class="subsection-title">{{ t('lmp.subsections.elementDiff') }}</h3>
                <div class="mini-table-wrap mini-table-scroll" v-if="elementDiff.length">
                  <table class="mini-table">
                    <thead>
                      <tr>
                        <th>{{ t('lmp.cols.element') }}</th>
                        <th>{{ t('lmp.cols.structCount') }}</th>
                        <th>{{ t('lmp.cols.lmpCount') }}</th>
                        <th>{{ t('lmp.cols.status') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(d, i) in elementDiff" :key="i" :class="{ 'row-mismatch': !d.match }">
                        <td>{{ d.element }}</td>
                        <td>{{ d.struct }}</td>
                        <td>{{ d.lmp }}</td>
                        <td :class="d.match ? 'cell-ok' : 'cell-mismatch'">
                          {{ d.match ? t('lmp.hints.matchOk') : t('lmp.hints.matchFail') }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p v-else class="cell-muted" style="font-size:12px; margin:0">{{ t('lmp.hints.noCompare') }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Atom ID Mapping (always visible) -->
        <div v-if="validationDone" class="card" style="margin-top: 24px">
          <h2 class="card-title">{{ t('lmp.sections.mapping') }}</h2>

          <p class="mapping-help">{{ t('lmp.descs.mapping') }}</p>

          <!-- Controls -->
          <div class="table-controls">
            <label class="toggle-label">
              <input type="checkbox" v-model="hideHydrogen" />
              <span>{{ t('lmp.actions.hideH') }}</span>
            </label>
            <label class="toggle-label" :title="t('lmp.hints.autoSeqHelp')">
              <input type="checkbox" v-model="seqInsertH" />
              <span>{{ t('lmp.actions.insertH') }}</span>
            </label>
            <span class="toolbar-hint">{{ t('lmp.hints.assignedCount', { n: assignedCount, total: structAtoms.length }) }}</span>
            <span v-if="periodicAtomCount" class="toolbar-hint periodic-hint">
              {{ t('lmp.hints.periodicAtoms', { n: periodicAtomCount }) }}
            </span>
            <div class="btn-row">
              <button class="btn-compact" @click="autoAssign">{{ t('lmp.actions.autoAssign') }}</button>
              <button class="btn-compact btn-seq" :title="t('lmp.hints.autoSeqHelp')" @click="autoSequence">{{ t('lmp.actions.autoSequence') }}</button>
              <button class="btn-compact" @click="clearNewIds">{{ t('lmp.actions.clearNew') }}</button>
            </div>
          </div>
          <p class="periodic-tip">{{ t('lmp.hints.autoSeqHelp') }}</p>
          <p v-if="autoSeqMsg" :class="autoSeqMsg.ok ? 'seq-msg seq-ok' : 'seq-msg seq-err'">
            {{ autoSeqMsg.ok ? '✓' : '⚠' }} {{ autoSeqMsg.text }}
          </p>
          <p v-if="periodicAtomCount" class="periodic-tip">{{ t('lmp.hints.periodicTip') }}</p>

          <!-- Atom mapping table -->
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width:40px">#</th>
                  <th style="width:70px">{{ t('lmp.cols.oldId') }}</th>
                  <th style="width:60px">{{ t('lmp.cols.element') }}</th>
                  <th>{{ t('lmp.cols.coords') }}</th>
                  <th style="width:66px">{{ t('lmp.cols.periodic') }}</th>
                  <th style="width:96px">{{ t('lmp.cols.newId') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="atom in filteredAtoms"
                  :key="atom.index"
                  :class="{ 'row-assigned': isAssigned(atom.index), 'row-h': atom.is_hydrogen }"
                  @click="toggleAssign(atom.index)"
                >
                  <td class="cell-idx">{{ filteredAtoms.indexOf(atom) + 1 }}</td>
                  <td class="cell-id">{{ atom.index }}</td>
                  <td :class="atom.is_hydrogen ? 'cell-h' : 'cell-element'">{{ atom.element }}</td>
                  <td class="cell-coords">{{ atom.x.toFixed(4) }}, {{ atom.y.toFixed(4) }}, {{ atom.z.toFixed(4) }}</td>
                  <td class="cell-period" @click.stop>
                    <input
                      type="number"
                      inputmode="numeric"
                      min="0"
                      class="period-input"
                      :class="{ 'period-active': periodOf(atom.index) > 0 }"
                      :title="filePeriodOf(atom.index) > 0 ? t('lmp.hints.periodicFileN', { n: filePeriodOf(atom.index) }) : t('lmp.hints.periodicToggle')"
                      v-model.number="idMap[atom.index].period"
                    />
                  </td>
                  <td class="cell-new" @click.stop>
                    <input
                      type="text"
                      inputmode="numeric"
                      class="id-input"
                      :placeholder="t('lmp.hints.newIdPh')"
                      v-model="idMap[atom.index].new"
                    />
                  </td>
                </tr>
                <tr v-if="filteredAtoms.length === 0">
                  <td colspan="6" class="cell-empty">{{ t('lmp.hints.noAtoms') }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Extract -->
          <div class="extract-row">
            <button
              class="btn-primary"
              :disabled="assignedCount === 0 || extracting"
              @click="runExtraction"
            >
              {{ extracting ? t('lmp.actions.extracting') : t('lmp.actions.extract') }}
            </button>
            <button
              v-if="csvResult"
              class="btn-secondary"
              @click="downloadCsv"
            >
              {{ t('lmp.actions.downloadCsv') }}
            </button>
          </div>

          <!-- CSV preview -->
          <div v-if="csvResult" class="preview-block">
            <h3 class="subsection-title">{{ t('lmp.subsections.preview') }} ({{ csvRecordCount }} {{ t('lmp.hints.records') }})</h3>
            <pre class="preview-code"><code>{{ csvPreviewText }}</code></pre>
          </div>
        </div>

      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import FileUpload from '@/components/FileUpload.vue'
import ConsolePanel from '@/components/ConsolePanel.vue'
import {
  lmpParseStructure,
  lmpParseLmp,
  lmpValidate,
  lmpExtract,
} from '@/api/index.js'
import Plotly from 'plotly.js-dist-min'

const { t } = useI18n()

// ---- Upload state ----
const structFile = ref(null)
const lmpFile = ref(null)
const structFileName = ref('')
const lmpFileName = ref('')
const structAtoms = ref([])
const structFileId = ref('')
const lmpFileId = ref('')
const lmpSections = ref({})   // parsed LAMMPS sections (Bonds/Angles/...) for bond + periodic detection

// ---- Validation ----
const validating = ref(false)
const validationDone = ref(false)
const validationOk = ref(false)
const validationMsg = ref('')
const validationWarnings = ref([])
// type -> {type, mass, element} inferred from the LAMMPS Masses section
const typeElements = ref([])
// per-element comparison between the structure and the LAMMPS file
const elementDiff = ref([])
const taskStatus = ref('idle')
const consoleLogs = reactive([])

// ---- Atom ID mapping (old_id -> new_id), explicit, no auto-renumber ----
// Mirrors reference lmptrans.py: the user supplies an exact remapping
// column-by-column. Keyed by the 1-based structure atom index (which is taken
// to correspond to the LAMMPS atom id after validation). `old` is that index;
// `new` is the user-entered target id (blank = skip the atom).
const idMap = reactive({})
const hideHydrogen = ref(false)
const showValDetails = ref(false)  // default collapsed
const filteredAtoms = computed(() => {
  if (!hideHydrogen.value) return structAtoms.value
  return structAtoms.value.filter(a => !a.is_hydrogen)
})
const assignedAtomIndices = computed(() =>
  structAtoms.value
    .filter(a => isAssigned(a.index))
    .map(a => a.index)
)
const assignedCount = computed(() => assignedAtomIndices.value.length)
function isAssigned(idx) {
  const e = idMap[idx]
  return !!e && String(e.new).trim() !== ''
}

// Parse a topology atom token the same way the backend does:
// '3' -> (3,0), '3#' -> (3,1), '3##' -> (3,2), '3#2' -> (3,2).
// Period is an INTEGER count (a periodic atom may span >=2 images).
function splitAtomToken(tok) {
  const m = /^(\d+)(?:#(\d+))?(#*)$/.exec(tok || '')
  if (!m) {
    const lead = /^\d+/.exec(tok || '')
    return { id: lead ? lead[0] : (tok || ''), period: (tok || '').includes('#') ? 1 : 0 }
  }
  return { id: m[1], period: m[2] ? parseInt(m[2], 10) : m[3].length }
}

// File-detected period per atom id — the max over every LAMMPS topology
// section. Used to seed the editable "周期" column on validation.
const filePeriodMap = computed(() => {
  const pm = new Map() // atomId(number) -> period(int)
  for (const sec of ['Bonds', 'Angles', 'Dihedrals', 'Impropers']) {
    for (const ln of (lmpSections.value[sec] || [])) {
      const p = ln.split(/\s+/)
      // line layout: topo_id type atom1 atom2 [atom3] [atom4]; atoms start at col 2
      for (let k = 2; k < p.length; k++) {
        const { id, period } = splitAtomToken(p[k])
        const n = parseInt(id, 10)
        if (Number.isFinite(n) && period > 0) pm.set(n, Math.max(pm.get(n) || 0, period))
      }
    }
  }
  return pm
})

// Effective period per atom (from the idMap; seeded from the file on validate).
const periodicAtomIds = computed(() => {
  const ids = new Set()
  for (const a of structAtoms.value) {
    if ((idMap[a.index]?.period || 0) > 0) ids.add(a.index)
  }
  return ids
})
const periodicAtomCount = computed(() => periodicAtomIds.value.size)
// Current (effective) period of an atom — 0 means non-periodic.
function periodOf(idx) {
  return idMap[idx]?.period || 0
}
// Period detected for an atom in the LAMMPS file (0 if none).
function filePeriodOf(idx) {
  return filePeriodMap.value.get(idx) || 0
}

function resetIdMap(atoms) {
  Object.keys(idMap).forEach(k => { delete idMap[k] })
  for (const a of atoms) idMap[a.index] = { old: a.index, new: '', period: 0 }
}
// After the LAMMPS file is parsed, set each atom's period to the file-detected
// value. Periods only get seeded up (a non-periodic atom stays 0); user edits
// made before a re-validate are preserved.
function seedFilePeriods() {
  for (const a of structAtoms.value) {
    const fp = filePeriodOf(a.index)
    if (fp > 0 && (idMap[a.index]?.period || 0) === 0) idMap[a.index].period = fp
  }
}
function clearNewIds() {
  for (const k of Object.keys(idMap)) idMap[k].new = ''
}
function autoAssign() {
  for (const k of Object.keys(idMap)) idMap[k].new = String(idMap[k].old)
}
function toggleAssign(idx) {
  const e = idMap[idx]
  if (!e) return
  e.new = String(e.new).trim() === '' ? String(e.old) : ''
}

// ---- Auto sequence (自动排序) ----
// The user marks three atoms in the "New ID" column:
//     1 -> chain start atom,  2 -> second atom (fixes the walk direction),
//    -1 -> end atom (receives the FINAL number).
// autoSequence() walks the shortest heavy-atom bond path 1 → 2 → … → -1 and
// numbers the intermediate atoms 3, 4, … sequentially. With "insert
// hydrogens" enabled, each chain atom's bonded hydrogens are numbered right
// after their parent (matching LigParGen's .gro ordering); otherwise H stays
// blank. Atoms NOT on the chain are never touched — the user picks those.
const seqInsertH = ref(true)
const autoSeqMsg = ref(null) // { ok: boolean, text: string }

function bondAdjacency(includeHydrogens) {
  // atom index -> sorted neighbor indices, from the distance-derived bond graph
  const byIndex = new Map(structAtoms.value.map(a => [a.index, a]))
  const adj = new Map()
  for (const b of distanceBonds(structAtoms.value)) {
    const A = byIndex.get(b.a), B = byIndex.get(b.b)
    if (!A || !B) continue
    if (!includeHydrogens && (A.is_hydrogen || B.is_hydrogen)) continue
    if (!adj.has(b.a)) adj.set(b.a, [])
    if (!adj.has(b.b)) adj.set(b.b, [])
    adj.get(b.a).push(b.b)
    adj.get(b.b).push(b.a)
  }
  for (const arr of adj.values()) arr.sort((x, y) => x - y)
  return adj
}

function shortestBondPath(adj, from, to, exclude) {
  // BFS shortest path; deterministic because neighbors are index-sorted.
  if (from === to) return [from]
  const prev = new Map([[from, null]])
  const queue = [from]
  while (queue.length) {
    const cur = queue.shift()
    for (const nb of adj.get(cur) || []) {
      if (nb === exclude || prev.has(nb)) continue
      prev.set(nb, cur)
      if (nb === to) {
        const path = []
        for (let n = nb; n != null; n = prev.get(n)) path.push(n)
        return path.reverse()
      }
      queue.push(nb)
    }
  }
  return null
}

function autoSequence() {
  autoSeqMsg.value = null
  // Locate the 1 / 2 / -1 markers in the New-ID column.
  let startIdx = null, secondIdx = null, endIdx = null
  for (const a of structAtoms.value) {
    const e = idMap[a.index]
    if (!e) continue
    const v = String(e.new).trim()
    if (v === '1') startIdx = a.index
    else if (v === '2') secondIdx = a.index
    else if (v === '-1' || v === '−1') endIdx = a.index
  }
  if (startIdx == null || secondIdx == null || endIdx == null) {
    autoSeqMsg.value = { ok: false, text: t('lmp.hints.autoSeqErrMark') }
    return
  }
  if (startIdx === secondIdx || secondIdx === endIdx || startIdx === endIdx) {
    autoSeqMsg.value = { ok: false, text: t('lmp.hints.autoSeqErrDup') }
    return
  }
  // Shortest heavy-atom path 2 → -1 (the start atom is excluded from the walk
  // so ring systems don't double back through atom 1); if unreachable, retry
  // on the full graph including H (covers H-bridged chains).
  const heavyAdj = bondAdjacency(false)
  const fullAdj = bondAdjacency(true)
  let path = shortestBondPath(heavyAdj, secondIdx, endIdx, startIdx)
  let viaH = false
  if (!path) {
    path = shortestBondPath(fullAdj, secondIdx, endIdx, startIdx)
    viaH = !!path
  }
  if (!path) {
    autoSeqMsg.value = { ok: false, text: t('lmp.hints.autoSeqErrPath') }
    return
  }
  const chain = [startIdx, ...path]
  const hSet = new Set(structAtoms.value.filter(a => a.is_hydrogen).map(a => a.index))
  const onChain = new Set(chain)

  // Number the chain; hydrogens follow their parent atom when enabled.
  let counter = 1
  let hCount = 0
  for (const idx of chain) {
    idMap[idx].new = String(counter++)
    if (seqInsertH.value) {
      for (const h of fullAdj.get(idx) || []) {
        if (!hSet.has(h) || onChain.has(h)) continue
        idMap[h].new = String(counter++)
        hCount++
      }
    }
  }
  let text = t('lmp.hints.autoSeqOk', { n: chain.length, total: counter - 1, h: hCount })
  if (viaH) text += ' ' + t('lmp.hints.autoSeqViaH')
  autoSeqMsg.value = { ok: true, text }
}

// ---- Extraction ----
const extracting = ref(false)
const csvResult = ref('')
const csvRecordCount = ref(0)

const csvPreviewText = computed(() => {
  if (!csvResult.value) return ''
  const lines = csvResult.value.split('\n')
  if (lines.length <= 20) return csvResult.value
  return lines.slice(0, 20).join('\n') + '\n...'
})

// ---- Error detail extractor (handles responseType:'text' where error JSON
//      arrives as a string instead of a parsed object) ----
function extractErrorDetail(err) {
  const data = err.response?.data
  if (!data) return err.message
  if (typeof data === 'string') {
    // Axios parsed the error body as plain text; try to pull detail from JSON.
    try {
      const parsed = JSON.parse(data)
      return parsed.detail || data
    } catch (_) {
      return data
    }
  }
  return data.detail || err.message
}

// ---- External link (LigParGen) ----
// Under Electron, target=_blank is suppressed by contextIsolation, so route
// the URL through the preload bridge; in a plain browser just window.open.
function openExternalLink(url) {
  if (window.electronAPI?.openExternal) {
    window.electronAPI.openExternal(url)
  } else {
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

// ---- File handlers ----
async function onStructSelected(files) {
  structFile.value = files[0]
  structFileName.value = files[0].name
  consoleLogs.length = 0
  taskStatus.value = 'running'
  consoleLogs.push(t('lmp.logs.parsingStruct'))
  try {
    const formData = new FormData()
    formData.append('file', files[0])
    const res = await lmpParseStructure(formData)
    structAtoms.value = res.data.atoms || []
    structFileId.value = res.data.file_id
    resetIdMap(structAtoms.value)
    validationDone.value = false
    consoleLogs.push(t('lmp.logs.structParsed', { n: structAtoms.value.length, formula: res.data.formula || '?' }))
    taskStatus.value = 'completed'
  } catch (err) {
    // Parse failed (e.g. unsupported/malformed file). Reset the loaded-file
    // indicator so the green "✓" doesn't mislead, and keep structFileId empty
    // — the Validate button is disabled until a structure parses successfully,
    // which prevents a downstream "File not found" 404 from an empty id.
    structFileName.value = ''
    structFile.value = null
    consoleLogs.push(t('logs.common.error', { message: extractErrorDetail(err) }))
    taskStatus.value = 'failed'
  }
}

async function onLmpSelected(files) {
  lmpFile.value = files[0]
  lmpFileName.value = files[0].name
}

// ---- Validation ----
async function runValidation() {
  if (!lmpFile.value) return
  validating.value = true
  taskStatus.value = 'running'
  consoleLogs.push(t('lmp.logs.parsingLmp'))

  try {
    // First, upload and parse LMP
    const formData = new FormData()
    formData.append('file', lmpFile.value)
    const lmpRes = await lmpParseLmp(formData)
    lmpFileId.value = lmpRes.data.file_id
    lmpSections.value = lmpRes.data.sections || {}
    const lmpAtomCount = lmpRes.data.total_atoms
    consoleLogs.push(t('lmp.logs.lmpParsed', { n: lmpAtomCount }))
    // Seed the "周期" column from the parsed topology (# tokens).
    seedFilePeriods()

    // Then, validate
    consoleLogs.push(t('lmp.logs.validating'))
    const valRes = await lmpValidate({
      struct_file_id: structFileId.value,
      lmp_file_id: lmpFileId.value,
    })
    validationOk.value = valRes.data.ok
    validationMsg.value = valRes.data.message
    validationWarnings.value = valRes.data.warnings || []
    typeElements.value = valRes.data.type_elements || []
    elementDiff.value = valRes.data.element_diff || []
    validationDone.value = true
    taskStatus.value = 'completed'
  } catch (err) {
    consoleLogs.push(t('logs.common.error', { message: extractErrorDetail(err) }))
    taskStatus.value = 'failed'
  } finally {
    validating.value = false
  }
}

// ---- Extraction ----
async function runExtraction() {
  // Build the explicit old_id -> new_id map (skip blanks) and the old_id ->
  // period map (only atoms whose period >= 1).
  const id_map = {}
  const period_map = {}
  for (const a of structAtoms.value) {
    const e = idMap[a.index]
    if (e && String(e.new).trim() !== '') {
      id_map[String(e.old)] = String(e.new).trim()
      const p = parseInt(e.period, 10)
      if (Number.isFinite(p) && p > 0) period_map[String(e.old)] = p
    }
  }
  if (Object.keys(id_map).length === 0) return
  // -1 is an auto-sequence END marker, not a real target id — refuse to
  // extract while any negative New ID is still present.
  if (Object.values(id_map).some(v => String(v).trim().startsWith('-'))) {
    taskStatus.value = 'failed'
    consoleLogs.push(t('logs.common.error', { message: t('lmp.hints.negIdWarn') }))
    return
  }

  extracting.value = true
  taskStatus.value = 'running'
  consoleLogs.push(t('lmp.logs.extracting'))
  try {
    const res = await lmpExtract({
      structure_file_id: structFileId.value,
      lmp_file_id: lmpFileId.value,
      id_map,
      period_map,
    })
    csvResult.value = typeof res.data === 'string' ? res.data : ''
    // Count non-empty lines after header
    const lines = csvResult.value.split('\n').filter(l => l.trim())
    csvRecordCount.value = Math.max(0, lines.length - 1)
    consoleLogs.push(t('lmp.logs.extracted', { n: csvRecordCount.value }))
    taskStatus.value = 'completed'
  } catch (err) {
    consoleLogs.push(t('logs.common.error', { message: extractErrorDetail(err) }))
    taskStatus.value = 'failed'
  } finally {
    extracting.value = false
  }
}

function downloadCsv() {
  if (!csvResult.value) return
  const blob = new Blob([csvResult.value], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'extracted_params.csv'
  a.click()
  URL.revokeObjectURL(url)
}

// ---- 3D molecular structure viewer ----
// Renders the uploaded molecule as a ball-and-stick model with every atom
// labelled by its number (原子序号). Bonds are ALWAYS recomputed by covalent
// radius distance on each render — we deliberately ignore the LAMMPS "Bonds"
// section so periodic-image bonds don't draw as tangled long lines. Periodicity
// is shown instead via the cyan ring (and the "周期" integer column).
const molViewerContainer = ref(null)
const showAtomLabels = ref(true)

const ELEM_COLORS = {
  H: '#f0f0f0', C: '#5a5a5a', N: '#3050f8', O: '#ff2d2d', F: '#90e050',
  P: '#ff8000', S: '#ffd21f', Cl: '#1fb71f', Br: '#a62929', I: '#940094',
  B: '#ffb5b5', Si: '#f0c8a0', Na: '#ab5cf2', K: '#8f40d4', Mg: '#8aff00',
  Ca: '#3dff00', Fe: '#e06633', Zn: '#7d80b0', Cu: '#c88033', default: '#ff69b4',
}
const COV_RADII = {
  H: 0.31, C: 0.76, N: 0.71, O: 0.66, F: 0.57, P: 1.07, S: 1.05, Cl: 1.02,
  Br: 1.20, I: 1.39, B: 0.84, Si: 1.11, Na: 1.66, K: 2.03, Mg: 1.41,
  Ca: 1.76, Fe: 1.32, Zn: 1.22, Cu: 1.32,
}
const elemColor = (e) => ELEM_COLORS[e] || ELEM_COLORS.default
const covRadius = (e) => COV_RADII[e] || 0.76

function distanceBonds(atoms) {
  // Covalent-radius connectivity — recomputed on every render so the bond graph
  // always matches the current coordinates (never the file-internal LAMMPS
  // Bonds, which can contain periodic-image "ghost" bonds).
  const bonds = []
  for (let i = 0; i < atoms.length; i++) {
    for (let j = i + 1; j < atoms.length; j++) {
      const ri = covRadius(atoms[i].element), rj = covRadius(atoms[j].element)
      const dx = atoms[i].x - atoms[j].x
      const dy = atoms[i].y - atoms[j].y
      const dz = atoms[i].z - atoms[j].z
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz)
      if (d > 0.4 && d <= ri + rj + 0.45 && d <= 2.0) {
        bonds.push({ a: atoms[i].index, b: atoms[j].index, periodic: false })
      }
    }
  }
  return bonds
}

function renderMolViewer() {
  const el = molViewerContainer.value
  if (!el) return
  const atoms = hideHydrogen.value ? structAtoms.value.filter(a => !a.is_hydrogen) : structAtoms.value
  if (!atoms.length) { Plotly.purge(el); return }

  const atomByIndex = new Map(atoms.map(a => [a.index, a]))
  const assignedSet = new Set(assignedAtomIndices.value)
  const periodicSet = periodicAtomIds.value

  // Connectivity is always recomputed by distance (see distanceBonds).
  const source = distanceBonds(atoms)

  // One marker trace per element (colour + legend), labelled by atom number.
  const byElem = {}
  for (const a of atoms) (byElem[a.element] ||= []).push(a)
  const traces = []
  for (const [elem, list] of Object.entries(byElem)) {
    traces.push({
      type: 'scatter3d',
      mode: showAtomLabels.value ? 'markers+text' : 'markers',
      name: elem,
      x: list.map(a => a.x), y: list.map(a => a.y), z: list.map(a => a.z),
      text: list.map(a => String(a.index)),
      textposition: 'top center',
      textfont: { size: 11, color: '#1f2937' },
      customdata: list.map(a => a.index),
      marker: {
        size: list.map(a => Math.round(covRadius(a.element) * 9 + 5)),
        color: elemColor(elem),
        line: { color: '#1f2937', width: 0.5 },
        opacity: 0.95,
      },
      hovertemplate: '#%{customdata} ' + elem + '<extra></extra>',
      hoverinfo: 'skip',
    })
  }

  // Bond traces: solid grey sticks (all bonds are distance-derived now — no
  // file periodic bonds, so there is no separate dashed trace).
  function bondTrace(list, dash, color) {
    const xs = [], ys = [], zs = []
    for (const b of list) {
      const A = atomByIndex.get(b.a), B = atomByIndex.get(b.b)
      if (!A || !B) continue
      xs.push(A.x, B.x, null); ys.push(A.y, B.y, null); zs.push(A.z, B.z, null)
    }
    if (!xs.length) return null
    return {
      type: 'scatter3d', mode: 'lines', x: xs, y: ys, z: zs,
      line: { color, width: 5, dash }, hoverinfo: 'skip', showlegend: false,
    }
  }
  const tBonds = bondTrace(source, 'solid', '#9aa0a6')
  if (tBonds) traces.push(tBonds)

  // Cyan ring around atoms in a periodic (#) interaction.
  const per = atoms.filter(a => periodicSet.has(a.index))
  if (per.length) {
    traces.push({
      type: 'scatter3d', mode: 'markers',
      x: per.map(a => a.x), y: per.map(a => a.y), z: per.map(a => a.z),
      marker: { size: 13, color: 'rgba(0,0,0,0)', line: { color: '#22d3ee', width: 2 } },
      hoverinfo: 'skip', showlegend: false,
    })
  }

  // Red outline ring around assigned atoms.
  const sel = atoms.filter(a => assignedSet.has(a.index))
  if (sel.length) {
    traces.push({
      type: 'scatter3d', mode: 'markers',
      x: sel.map(a => a.x), y: sel.map(a => a.y), z: sel.map(a => a.z),
      marker: { size: 17, color: 'rgba(0,0,0,0)', line: { color: '#ff3b3b', width: 3 } },
      hoverinfo: 'skip', showlegend: false,
    })
  }

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 0, r: 0, t: 0, b: 0 },
    showlegend: true,
    legend: { x: 1.0, y: 1.0, font: { size: 10 }, bgcolor: 'rgba(255,255,255,0)' },
    scene: {
      aspectmode: 'data',
      dragmode: 'orbit',
      xaxis: { visible: false }, yaxis: { visible: false }, zaxis: { visible: false },
    },
  }
  Plotly.react(el, traces, layout, { responsive: true, displayModeBar: false })
}

watch([structAtoms, showAtomLabels, hideHydrogen, periodicAtomIds], () => nextTick(renderMolViewer))
watch(idMap, () => nextTick(renderMolViewer), { deep: true })

// ---- Floating viewer card ----
// When undocked the viewer card becomes position:fixed so it stays visible
// while the user scrolls the mapping table; drag its title bar to move it.
const viewerFloating = ref(false)
const viewerPos = ref({ x: null, y: null }) // null = CSS default (bottom-right)
let viewerDrag = null

const viewerFloatStyle = computed(() => {
  if (!viewerFloating.value || viewerPos.value.x == null) return null
  return { left: `${viewerPos.value.x}px`, top: `${viewerPos.value.y}px`, right: 'auto', bottom: 'auto' }
})

function onViewerDragStart(e) {
  if (!viewerFloating.value) return
  const card = e.currentTarget.closest('.viewer-card')
  if (!card) return
  const rect = card.getBoundingClientRect()
  viewerPos.value = { x: rect.left, y: rect.top } // pin before dragging
  viewerDrag = { dx: e.clientX - rect.left, dy: e.clientY - rect.top }
  e.preventDefault()
  window.addEventListener('pointermove', onViewerDragMove)
  window.addEventListener('pointerup', onViewerDragEnd)
}
function onViewerDragMove(e) {
  if (!viewerDrag) return
  const x = Math.min(Math.max(0, e.clientX - viewerDrag.dx), Math.max(0, window.innerWidth - 80))
  const y = Math.min(Math.max(0, e.clientY - viewerDrag.dy), Math.max(0, window.innerHeight - 60))
  viewerPos.value = { x, y }
}
function onViewerDragEnd() {
  viewerDrag = null
  window.removeEventListener('pointermove', onViewerDragMove)
  window.removeEventListener('pointerup', onViewerDragEnd)
  nextTick(() => {
    if (molViewerContainer.value) Plotly.Plots.resize(molViewerContainer.value)
  })
}
// Drag clamps use the window size at drag time; after the window shrinks a
// pinned card could sit entirely off-screen (its own header is the only way
// back). Re-clamp whenever the window resizes.
function onViewerWindowResize() {
  if (!viewerFloating.value || viewerPos.value.x == null) return
  viewerPos.value = {
    x: Math.min(Math.max(0, viewerPos.value.x), Math.max(0, window.innerWidth - 80)),
    y: Math.min(Math.max(0, viewerPos.value.y), Math.max(0, window.innerHeight - 60)),
  }
}
window.addEventListener('resize', onViewerWindowResize)
// Dock/undock changes the container size — let Plotly re-fit its layout.
watch(viewerFloating, () => nextTick(() => {
  if (molViewerContainer.value) Plotly.Plots.resize(molViewerContainer.value)
}))

onBeforeUnmount(() => {
  if (molViewerContainer.value) Plotly.purge(molViewerContainer.value)
  onViewerDragEnd()
  window.removeEventListener('resize', onViewerWindowResize)
})
</script>

<style scoped>
.lmp-page { display: flex; flex-direction: column; }

.main-container { display: flex; flex: 1; }
.content { flex: 1; padding: 24px; overflow-y: auto; min-width: 0; max-width: 960px; margin: 0 auto; }

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 28px;
}
.card-title { font-size: 18px; font-weight: 600; color: var(--color-text); margin: 0 0 8px; }
.card-desc { font-size: 13px; color: var(--color-text-secondary); line-height: 1.6; margin: 0 0 20px; }

.val-ok { color: var(--color-success); font-weight: 600; }
.val-warn { color: var(--color-warning); font-weight: 600; }
.val-warning-msg { font-size: 12px; color: var(--color-warning); margin: 4px 0; }

.subsection-title {
  font-size: 14px; font-weight: 600; color: var(--color-primary); margin: 0 0 10px;
}

.upload-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 720px) { .upload-row { grid-template-columns: 1fr; } }
.upload-col { min-width: 0; }
.file-loaded { font-size: 12px; color: var(--color-success); margin-top: 6px; }

.mapping-help {
  font-size: 12.5px; color: var(--color-text-secondary); line-height: 1.6;
  background: var(--color-neutral); border: 1px solid var(--color-border);
  border-radius: 8px; padding: 10px 14px; margin: 0 0 16px;
}

/* ---- Validation comparison panel ---- */
.compare-block { margin: 0 0 16px; }
.mini-table-wrap {
  overflow-x: auto; border-radius: 6px; border: 1px solid var(--color-border);
  max-width: 460px;
}
.mini-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.mini-table th {
  padding: 6px 10px; text-align: center; font-weight: 600;
  color: var(--color-text-secondary); background: var(--color-neutral);
  border-bottom: 1px solid var(--color-border); text-transform: uppercase;
  font-size: 10.5px; letter-spacing: 0.5px;
}
.mini-table td { padding: 5px 10px; border-bottom: 1px solid var(--color-border); text-align: center; }
.mini-table tbody tr:last-child td { border-bottom: none; }
.cell-ok { color: var(--color-success); font-weight: 600; }
.cell-mismatch { color: #e11d48; font-weight: 700; }
.row-mismatch { background: rgba(225,29,72,0.08); }

/* ---- Table controls ---- */
.table-controls {
  display: flex; align-items: center; gap: 14px; margin-bottom: 12px; flex-wrap: wrap;
}
.toggle-label {
  display: flex; align-items: center; gap: 6px; font-size: 13px;
  color: var(--color-text); cursor: pointer; user-select: none;
}
.toolbar-hint { font-size: 12px; color: var(--color-text-secondary); }
.periodic-hint { color: #0891b2; font-weight: 600; }
.btn-row { display: flex; gap: 8px; }
.periodic-tip { font-size: 12px; color: var(--color-text-secondary); margin: 0 0 12px; }

/* ---- Data table ---- */
.table-wrap { overflow-x: auto; border-radius: 6px; border: 1px solid var(--color-border); max-height: 400px; overflow-y: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  padding: 7px 10px; text-align: center; font-weight: 600;
  color: var(--color-text-secondary); background: var(--color-neutral);
  border-bottom: 1px solid var(--color-border); text-transform: uppercase;
  font-size: 10.5px; letter-spacing: 0.5px;
  position: sticky; top: 0; z-index: 1;
}
.data-table td {
  padding: 5px 8px; border-bottom: 1px solid var(--color-border); text-align: center;
}
.data-table tbody tr { cursor: pointer; transition: background 0.1s; }
.data-table tbody tr:hover { background: var(--color-primary-10, rgba(124,58,237,0.05)); }
.row-assigned { background: var(--color-primary-10, rgba(124,58,237,0.12)) !important; }
.row-h { opacity: 0.55; }
.cell-idx { color: var(--color-text-secondary); font-size: 11px; }
.cell-id { font-weight: 600; color: var(--color-text); }
.cell-element { font-weight: 600; color: var(--color-primary); }
.cell-h { color: var(--color-text-secondary); }
.cell-coords { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--color-text-secondary); text-align: left; }
.cell-muted { color: var(--color-text-secondary); }
.cell-new { cursor: text; }
.cell-empty { padding: 24px; color: var(--color-text-secondary); font-style: italic; }

.cell-period { padding: 3px; }
.period-input {
  width: 50px; padding: 4px 6px; border: 1px solid var(--color-border);
  border-radius: 5px; font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: var(--color-text); background: var(--color-bg); outline: none; text-align: center;
  -moz-appearance: textfield;
}
.period-input::-webkit-outer-spin-button,
.period-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.period-input:focus { border-color: var(--color-primary); }
.period-input.period-active {
  border-color: #22d3ee; color: #0891b2; font-weight: 700;
  background: rgba(34,211,238,0.10);
}

.id-input {
  width: 72px; padding: 4px 8px; border: 1px solid var(--color-border);
  border-radius: 5px; font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: var(--color-text); background: var(--color-bg); outline: none; text-align: center;
}
.id-input:focus { border-color: var(--color-primary); }

/* ---- Extract row ---- */
.extract-row {
  display: flex; align-items: flex-end; gap: 14px; margin-top: 20px; flex-wrap: wrap;
}

/* ---- Buttons ---- */
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

.btn-compact {
  height: 30px; padding: 0 12px; background: var(--color-neutral);
  border: 1px solid var(--color-border); border-radius: 6px;
  font-size: 12px; font-weight: 500; color: var(--color-text); cursor: pointer;
  transition: all 0.15s;
}
.btn-compact:hover { border-color: var(--color-primary); }

/* ---- Preview ---- */
.preview-block { margin-top: 20px; }
.preview-code {
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  line-height: 1.55;
  color: var(--color-text);
  max-height: 350px;
  overflow-y: auto;
  white-space: pre;
}

/* ---- Validation compare row (left-right) ---- */
.val-inline-msg { font-size: 12px; font-weight: normal; margin-left: 12px; }
.val-compare-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 0; }
@media (max-width: 700px) { .val-compare-row { grid-template-columns: 1fr; } }
.val-compare-col { min-width: 0; }
.mini-table-scroll { max-height: 260px; overflow-y: auto; }

.card-header-toggle {
  display: flex; align-items: center; justify-content: space-between;
  cursor: pointer; user-select: none;
  padding: 2px 0;
}
.card-header-toggle:hover { opacity: 0.8; }
.collapse-icon {
  font-size: 12px; color: var(--color-text-secondary);
  transition: transform 0.15s;
}
.table-more-hint {
  font-size: 12px; color: var(--color-text-secondary);
  text-align: center; margin: 8px 0 0; font-style: italic;
}

/* ---- 3D viewer ---- */
.viewer-toolbar {
  display: flex; align-items: center; gap: 16px; margin-bottom: 12px; flex-wrap: wrap;
}
.mol-viewer {
  width: 100%; height: 460px;
  border: 1px solid var(--color-border); border-radius: 8px;
  background: #fafbfc;
}
.legend-line {
  margin-top: 10px; display: flex; gap: 20px; flex-wrap: wrap;
  font-size: 12px; color: var(--color-text-secondary);
}
.leg-item { display: inline-flex; align-items: center; gap: 6px; }
.leg-dash {
  display: inline-block; width: 24px; height: 0;
  border-top: 3px solid #9aa0a6;
}
.leg-dash.periodic { border-top: 3px dashed #22d3ee; }
.leg-ring {
  display: inline-block; width: 14px; height: 14px; border-radius: 50%;
  border: 2px dashed #22d3ee; box-sizing: border-box;
}

/* ---- OPLSAA / LigParGen notice ---- */
.oplsaa-notice {
  border: 1px solid rgba(245, 158, 11, 0.45);
  background: rgba(245, 158, 11, 0.07);
  border-radius: 8px;
  padding: 12px 16px;
  margin: 0 0 20px;
}
.oplsaa-notice-title {
  font-size: 13px; font-weight: 700; color: #b45309; margin-bottom: 6px;
}
.oplsaa-notice-body {
  font-size: 12.5px; color: var(--color-text-secondary); line-height: 1.6;
  margin: 0 0 8px;
}
.oplsaa-notice-link {
  font-size: 12.5px; font-weight: 600; color: var(--color-primary, #7C3AED);
  text-decoration: none;
}
.oplsaa-notice-link:hover { text-decoration: underline; }
.oplsaa-notice-url {
  margin-left: 8px; font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: var(--color-text-secondary); font-weight: 400;
}

/* ---- Floating viewer card ---- */
.viewer-card-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 8px;
}
.viewer-float-btn { flex-shrink: 0; }
.viewer-drag-grip {
  margin-left: 6px; color: var(--color-text-secondary); font-size: 14px;
}
.viewer-card.floating {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 430px;
  max-width: calc(100vw - 48px);
  z-index: 320;
  margin: 0 !important;
  padding: 18px;
  border-radius: 12px;
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.28);
}
.viewer-card.floating .viewer-card-head { cursor: grab; user-select: none; }
.viewer-card.floating .viewer-card-head:active { cursor: grabbing; }
.viewer-card.floating .mol-viewer { height: 320px; }
.viewer-card.floating .card-desc { margin-bottom: 12px; font-size: 12px; }
@media (max-width: 520px) {
  .viewer-card.floating { width: calc(100vw - 32px); right: 16px; bottom: 16px; }
}

/* ---- Auto sequence ---- */
.btn-seq {
  border-color: var(--color-primary); color: var(--color-primary); font-weight: 700;
}
.btn-seq:hover { background: var(--color-primary-10, rgba(124,58,237,0.08)); }
.seq-msg { font-size: 12.5px; margin: 0 0 12px; }
.seq-msg.seq-ok { color: var(--color-success); font-weight: 600; }
.seq-msg.seq-err { color: #e11d48; font-weight: 600; }

</style>
