<template>
  <div class="ig-page">
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

            <!-- Basic -->
            <div v-if="activeSection === 'basic'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.basic') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.basic') }}</p>
              <ParamsForm :fields="basicFields" v-model="params" />
            </div>

            <!-- Coordinate -->
            <div v-if="activeSection === 'coordinate'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.coordinate') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.coordinate') }}</p>

              <!-- Standard mode: single coordinate table -->
              <template v-if="!advancedOn">
                <div class="paste-block">
                  <div class="paste-block__head">{{ t('inputGen.paste.coordTitle') }}</div>
                  <textarea
                    v-model="coordPasteText"
                    class="paste-block__textarea"
                    rows="5"
                    :placeholder="t('inputGen.paste.coordPlaceholder')"
                  ></textarea>
                  <button class="btn-compact" @click="applyCoordPaste()">{{ t('inputGen.paste.coordBtn') }}</button>
                </div>
                <div class="table-toolbar">
                  <button class="btn-compact" @click="addAtom">{{ t('inputGen.actions.addAtom') }}</button>
                  <button class="btn-compact" @click="removeAtom" :disabled="params.coordinate.length === 0">{{ t('inputGen.actions.removeAtom') }}</button>
                  <span class="toolbar-hint">{{ t('inputGen.hints.coordCount', { n: params.coordinate.length, total: params.num_atoms }) }}</span>
                </div>
                <div class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>{{ t('inputGen.cols.element') }}</th>
                        <th>{{ t('inputGen.cols.rMin') }}</th>
                        <th>{{ t('inputGen.cols.rMax') }}</th>
                        <th>{{ t('inputGen.cols.zIdx') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(atom, idx) in params.coordinate" :key="idx">
                        <td class="cell-idx">{{ idx + 1 }}</td>
                        <td><input class="cell-input" v-model="atom.element" /></td>
                        <td><input class="cell-input" type="number" v-model.number="atom.r_min" step="0.1" /></td>
                        <td><input class="cell-input" type="number" v-model.number="atom.r_max" step="0.1" /></td>
                        <td><input class="cell-input" type="number" v-model.number="atom.z_idx" step="1" /></td>
                      </tr>
                      <tr v-if="params.coordinate.length === 0">
                        <td colspan="5" class="cell-empty">{{ t('inputGen.hints.noAtoms') }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>

              <!-- Advanced mode: one coordinate table per molecule -->
              <template v-else>
                <div v-for="(mk, mi) in ['molecule1', 'molecule2']" :key="mk" style="margin-bottom:24px">
                  <h3 class="subsection-title">{{ t('inputGen.subsections.molecule', { n: mi + 1 }) }}</h3>
                  <div class="paste-block">
                    <div class="paste-block__head">{{ t('inputGen.paste.coordTitle') }}</div>
                    <textarea
                      v-model="molPasteText[mk]"
                      class="paste-block__textarea"
                      rows="5"
                      :placeholder="t('inputGen.paste.coordPlaceholder')"
                    ></textarea>
                    <button class="btn-compact" @click="applyCoordPaste(mk)">{{ t('inputGen.paste.coordBtn') }}</button>
                  </div>
                  <div class="table-toolbar">
                    <button class="btn-compact" @click="addMolAtom(mk)">{{ t('inputGen.actions.addAtom') }}</button>
                    <button class="btn-compact" @click="removeMolAtom(mk)" :disabled="params[mk].coordinate.length === 0">{{ t('inputGen.actions.removeAtom') }}</button>
                    <span class="toolbar-hint">{{ t('inputGen.hints.molCount', { n: params[mk].coordinate.length }) }}</span>
                  </div>
                  <div class="table-wrap">
                    <table class="data-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>{{ t('inputGen.cols.element') }}</th>
                          <th>{{ t('inputGen.cols.rMin') }}</th>
                          <th>{{ t('inputGen.cols.rMax') }}</th>
                          <th>{{ t('inputGen.cols.zIdx') }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(atom, idx) in params[mk].coordinate" :key="idx">
                          <td class="cell-idx">{{ idx + 1 }}</td>
                          <td><input class="cell-input" v-model="atom.element" /></td>
                          <td><input class="cell-input" type="number" v-model.number="atom.r_min" step="0.1" /></td>
                          <td><input class="cell-input" type="number" v-model.number="atom.r_max" step="0.1" /></td>
                          <td><input class="cell-input" type="number" v-model.number="atom.z_idx" step="1" /></td>
                        </tr>
                        <tr v-if="params[mk].coordinate.length === 0">
                          <td colspan="5" class="cell-empty">{{ t('inputGen.hints.noAtoms') }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div style="margin-top:10px; max-width:420px">
                    <ParamsForm :fields="molForceFields(mi)" v-model="params[mk]" />
                  </div>
                </div>
              </template>
            </div>

            <!-- Cell -->
            <div v-if="activeSection === 'cell'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.cell') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.cell') }}</p>
              <div class="paste-block">
                <div class="paste-block__head">{{ t('inputGen.paste.cellTitle') }}</div>
                <textarea
                  v-model="cellPasteText"
                  class="paste-block__textarea"
                  rows="3"
                  :placeholder="t('inputGen.paste.cellPlaceholder')"
                ></textarea>
                <button class="btn-compact" @click="applyCellPaste">{{ t('inputGen.paste.cellBtn') }}</button>
              </div>
              <ParamsForm :fields="cellFields" v-model="params.cell" />
            </div>

            <!-- Chains & Space Groups -->
            <div v-if="activeSection === 'chains'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.chains') }}</h2>
              <p class="card-desc">{{ advancedOn ? t('inputGen.descs.chainsAdvanced') : t('inputGen.descs.chains') }}</p>
              <ParamsForm v-if="!advancedOn" :fields="chainBasicFields" v-model="params" style="margin-bottom:20px" />

              <div class="paste-block">
                <div class="paste-block__head">{{ t('inputGen.paste.chainsTitle') }}</div>
                <textarea
                  v-model="chainsPasteText"
                  class="paste-block__textarea"
                  rows="8"
                  :placeholder="t('inputGen.paste.chainsPlaceholder')"
                ></textarea>
                <button class="btn-compact" @click="applyChainsPaste">{{ t('inputGen.paste.chainsBtn') }}</button>
              </div>

              <h3 class="subsection-title">{{ t('inputGen.subsections.chainCenters') }}</h3>
              <div class="table-toolbar">
                <button class="btn-compact" @click="addChainCenter">{{ t('inputGen.actions.addRow') }}</button>
                <button class="btn-compact" @click="removeChainCenter" :disabled="params.chain_centers.length === 0">{{ t('inputGen.actions.removeRow') }}</button>
              </div>
              <div class="table-wrap">
                <table class="data-table">
                  <thead>
                    <tr><th>#</th><th>x</th><th>y</th><th>z</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(cc, idx) in params.chain_centers" :key="idx">
                      <td class="cell-idx">{{ idx + 1 }}</td>
                      <td><input class="cell-input" type="number" v-model.number="cc.x" step="0.1" /></td>
                      <td><input class="cell-input" type="number" v-model.number="cc.y" step="0.1" /></td>
                      <td><input class="cell-input" type="number" v-model.number="cc.z" step="0.1" /></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <template v-if="!advancedOn">
                <h3 class="subsection-title" style="margin-top:20px">{{ t('inputGen.subsections.spaceGroups') }}</h3>
                <div class="table-toolbar">
                  <button class="btn-compact" @click="addSpaceGroupOp">{{ t('inputGen.actions.addOp') }}</button>
                  <button class="btn-compact" @click="removeSpaceGroupOp" :disabled="params.space_group_ops.length === 0">{{ t('inputGen.actions.removeOp') }}</button>
                </div>
                <div class="table-wrap">
                  <table class="data-table">
                    <thead>
                      <tr><th>#</th><th colspan="3">{{ t('inputGen.cols.transdirect') }}</th><th colspan="3">{{ t('inputGen.cols.centerMove') }}</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="(op, idx) in params.space_group_ops" :key="idx">
                        <td class="cell-idx">{{ idx + 1 }}</td>
                        <td><input class="cell-input" type="number" v-model.number="op.transdirect[0]" step="0.1" /></td>
                        <td><input class="cell-input" type="number" v-model.number="op.transdirect[1]" step="0.1" /></td>
                        <td><input class="cell-input" type="number" v-model.number="op.transdirect[2]" step="0.1" /></td>
                        <td><input class="cell-input" type="number" v-model.number="op.center_move[0]" step="0.1" /></td>
                        <td><input class="cell-input" type="number" v-model.number="op.center_move[1]" step="0.1" /></td>
                        <td><input class="cell-input" type="number" v-model.number="op.center_move[2]" step="0.1" /></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
            </div>

            <!-- Helix & Geometry -->
            <div v-if="activeSection === 'helix'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.helix') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.helix') }}</p>
              <ParamsForm :fields="helixFields" v-model="params" />
              <h3 class="subsection-title" style="margin-top:20px">{{ t('inputGen.subsections.pythonBuild') }}</h3>
              <p class="card-desc">{{ t('inputGen.descs.pythonBuild') }}</p>
              <ParamsForm :fields="pythonBuildFields" v-model="params" />
            </div>

            <!-- Temperature & LM -->
            <div v-if="activeSection === 'thermal'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.thermal') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.thermal') }}</p>
              <ParamsForm :fields="thermalFields" v-model="params" />

              <h3 class="subsection-title" style="margin-top:20px">{{ t('inputGen.subsections.lm') }}</h3>
              <p class="card-desc">{{ t('inputGen.descs.lm') }}</p>
              <ParamsForm :fields="lmFields" v-model="params" />
            </div>

            <!-- Mode Switches -->
            <div v-if="activeSection === 'modes'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.modes') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.modes') }}</p>
              <ParamsForm :fields="modeFields" v-model="params" />

              <template v-if="!advancedOn">
                <h3 class="subsection-title" style="margin-top:20px">{{ t('inputGen.subsections.phase2') }}</h3>
                <p class="card-desc">{{ t('inputGen.descs.phase2') }}</p>
                <ParamsForm :fields="phase2Fields" v-model="params" />
              </template>
            </div>

            <!-- Experimental -->
            <div v-if="activeSection === 'experimental'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.experimental') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.experimental') }}</p>
              <ParamsForm :fields="xraylibFields" v-model="params" style="margin-bottom:20px" />
              <ParamsForm v-if="!xraylibOn" :fields="experimentalFields" v-model="params" />
              <p v-else class="card-desc" style="margin:0">{{ t('inputGen.hints.xraylibAuto') }}</p>
            </div>

            <!-- Equatorial module [260814] — off by default -->
            <div v-if="activeSection === 'equatorial'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.equatorial') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.equatorial') }}</p>
              <ParamsForm :fields="equatorialEnableFields" v-model="params" />
              <template v-if="params.equatorial_module_on">
                <ParamsForm :fields="equatorialBaseFields" v-model="params" style="margin-top:20px" />
                <div v-if="equatorialProfileOn" style="margin-top:20px">
                  <h3 class="subsection-title">{{ t('inputGen.subsections.eqProfile') }}</h3>
                  <ParamsForm :fields="equatorialProfileFields" v-model="params" />
                </div>
              </template>
            </div>

            <!-- Advanced multi-molecule [260815] -->
            <div v-if="activeSection === 'advanced'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.advanced') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.advanced') }}</p>
              <ParamsForm :fields="advancedFields" v-model="params" style="margin-bottom:20px" />

              <div v-if="caseBon">
                <h3 class="subsection-title">{{ t('inputGen.subsections.mixture') }}</h3>
                <ParamsForm :fields="mixtureFields" v-model="params" />
              </div>

              <div class="adv-note">{{ t('inputGen.hints.advancedNote') }}</div>
            </div>

            <!-- GA -->
            <div v-if="activeSection === 'ga'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.ga') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.ga') }}</p>
              <ParamsForm :fields="gaFields" v-model="params" />

              <div v-if="params.ga_mode === 'flash'" style="margin-top:20px">
                <h3 class="subsection-title">{{ t('inputGen.subsections.flashParams') }}</h3>
                <ParamsForm :fields="gaFlashFields" v-model="params" />
              </div>
              <div v-if="params.ga_mode === 'pro'" style="margin-top:20px">
                <h3 class="subsection-title">{{ t('inputGen.subsections.proParams') }}</h3>
                <ParamsForm :fields="gaProFields" v-model="params" />
              </div>

              <div v-if="params.ga_mode === 'basic' && !advancedOn" style="margin-top:20px">
                <h3 class="subsection-title">{{ t('inputGen.subsections.deepSearch') }}</h3>
                <ParamsForm :fields="deepSearchFields" v-model="params" />
                <div v-if="params.deep_search === 'on'" style="margin-top:12px">
                  <ParamsForm :fields="deepSearchParams" v-model="params" />
                </div>
              </div>
            </div>

            <!-- Output -->
            <div v-if="activeSection === 'output'" class="card">
              <h2 class="card-title">{{ t('inputGen.sections.output') }}</h2>
              <p class="card-desc">{{ t('inputGen.descs.output') }}</p>
              <ParamsForm :fields="outputFields" v-model="params" />

              <div class="actions-row">
                <button class="btn-primary" @click="generatePreview" :disabled="generating">
                  {{ generating ? t('inputGen.actions.generating') : t('inputGen.actions.generate') }}
                </button>
                <button class="btn-secondary" @click="downloadInput" :disabled="!previewText">
                  {{ t('inputGen.actions.download') }}
                </button>
              </div>

              <ConsolePanel
                v-if="consoleLogs.length || taskStatus !== 'idle'"
                :status="taskStatus"
                :logs="consoleLogs"
                style="margin-top: 16px"
              />

              <!-- Preview -->
              <div v-if="previewText" class="preview-block">
                <h3 class="subsection-title">{{ t('inputGen.subsections.preview') }}</h3>
                <pre class="preview-code"><code>{{ previewText }}</code></pre>
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
import ParamsForm from '@/components/ParamsForm.vue'
import ConsolePanel from '@/components/ConsolePanel.vue'
import { inputGenGenerate } from '@/api/index.js'

const { t } = useI18n()

// ---- Sections ----
const sections = computed(() => [
  { id: 'basic', label: t('inputGen.sections.basic') },
  { id: 'coordinate', label: t('inputGen.sections.coordinate') },
  { id: 'cell', label: t('inputGen.sections.cell') },
  { id: 'chains', label: t('inputGen.sections.chains') },
  { id: 'helix', label: t('inputGen.sections.helix') },
  { id: 'thermal', label: t('inputGen.sections.thermal') },
  { id: 'modes', label: t('inputGen.sections.modes') },
  { id: 'experimental', label: t('inputGen.sections.experimental') },
  { id: 'equatorial', label: t('inputGen.sections.equatorial') },
  { id: 'advanced', label: t('inputGen.sections.advanced') },
  { id: 'ga', label: t('inputGen.sections.ga') },
  { id: 'output', label: t('inputGen.sections.output') },
])

const activeSection = ref('basic')

// ---- Status ----
const taskStatus = ref('idle')
const consoleLogs = reactive([])
const generating = ref(false)
const previewText = ref('')

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

// ---- Mode flags ----
const advancedOn = computed(() => params.advanced_multi_molecule !== 'off')
const caseBon = computed(() => params.advanced_multi_molecule === 'case_b')
const xraylibOn = computed(() => params.use_xraylib === 'on')
const equatorialProfileOn = computed(() => !!(params.equatorial_profile_file || '').trim())

// ---- Paste-to-fill state (识别填充) ----
const coordPasteText = ref('')
const molPasteText = reactive({ molecule1: '', molecule2: '' })
const chainsPasteText = ref('')
const cellPasteText = ref('')

function cleanPasteLines(text) {
  // strip inline comments, trim, drop empties; returns original line strings
  return String(text || '')
    .split(/\r?\n/)
    .map(l => l.replace(/#.*$/, '').trim())
    .filter(l => l.length > 0)
}

function tokens(line) {
  return line.split(/[\s,]+/).filter(Boolean)
}

// Parse a pasted coordinate fragment into atom rows. Accepts an optional
// `num_atoms = N` line (applied by the caller), skips the bare `coordinate`
// marker, and requires 4 columns per data row.
function parseCoordinateRows(text) {
  const rows = []
  for (const line of cleanPasteLines(text)) {
    if (/^coordinate$/i.test(line)) continue
    if (/^\s*num_atoms\s*=/i.test(line)) continue
    const tk = tokens(line)
    if (tk.length !== 4) {
      throw new Error(`"${line}" — ${t('inputGen.paste.errCoordCols', { n: tk.length })}`)
    }
    const el = tk[0]
    if (!Number.isNaN(Number(el))) {
      throw new Error(`"${line}" — ${t('inputGen.paste.errCoordElement')}`)
    }
    const rMin = Number(tk[1]); const rMax = Number(tk[2]); const zIdx = Number(tk[3])
    if (![rMin, rMax, zIdx].every(Number.isFinite)) {
      throw new Error(`"${line}" — ${t('inputGen.paste.errNum')}`)
    }
    rows.push({ element: el, r_min: rMin, r_max: rMax, z_idx: Math.trunc(zIdx) })
  }
  return rows
}

function applyCoordPaste(mk = null) {
  const text = mk ? molPasteText[mk] : coordPasteText.value
  if (!text.trim()) return
  try {
    const rows = parseCoordinateRows(text)
    if (!rows.length) { consoleLogs.push(t('inputGen.paste.errEmpty')); return }
    // an optional leading `num_atoms = N` line updates the atom count
    const m = String(text).match(/^\s*num_atoms\s*=\s*(\d+)\s*$/im)
    if (mk) {
      params[mk].coordinate = rows
      consoleLogs.push(t('inputGen.paste.parsedMol', { mol: mk === 'molecule1' ? 1 : 2, n: rows.length }))
    } else {
      params.coordinate = rows
      if (m) params.num_atoms = Number(m[1])
      else params.num_atoms = rows.length
      consoleLogs.push(t('inputGen.paste.parsedCoord', { n: rows.length }))
    }
  } catch (e) {
    consoleLogs.push(`${t('inputGen.paste.errPrefix')}${e.message}`)
  }
}

// Parse a pasted chain-center / space-group fragment. Understands the real
// input.txt block markers; without markers, 3-number lines are chain centers
// and 6-number lines are one symmetry op (Transdirect + center_move).
// `chain_num = N` / `space_group_num = N` lines are applied too.
function parseChainsBlocks(text) {
  const centers = []
  const ops = []
  const lines = cleanPasteLines(text)
  let mode = null            // 'centers' | 'ops' while inside a marker block
  let pendingOp = null
  let sawMarker = false
  for (const line of lines) {
    const low = line.toLowerCase()
    if (low === 'chain_center_begin') { sawMarker = true; mode = 'centers'; continue }
    if (low === 'chain_center_end') { mode = null; continue }
    if (low === 'space_group_begin') { sawMarker = true; mode = 'ops'; continue }
    if (low === 'space_group_end') { mode = null; continue }
    if (/^\s*chain_num\s*=/i.test(line) || /^\s*space_group_num\s*=/i.test(line)) continue
    const tk = tokens(line)
    if (!tk.length) continue
    if (tk.length === 3) {
      const v = tk.map(Number)
      if (!v.every(Number.isFinite)) throw new Error(`"${line}" — ${t('inputGen.paste.errNum')}`)
      if (mode === 'ops') {
        if (pendingOp) { ops.push(pendingOp); pendingOp = null }
        pendingOp = { transdirect: v, center_move: [0, 0, 0] }
      } else {
        centers.push({ x: v[0], y: v[1], z: v[2] })
      }
    } else if (tk.length === 6) {
      const v = tk.map(Number)
      if (!v.every(Number.isFinite)) throw new Error(`"${line}" — ${t('inputGen.paste.errNum')}`)
      ops.push({ transdirect: v.slice(0, 3), center_move: v.slice(3) })
    } else {
      throw new Error(`"${line}" — ${t('inputGen.paste.errChainsCols', { n: tk.length })}`)
    }
  }
  if (pendingOp) ops.push(pendingOp)
  return { centers, ops, sawMarker }
}

function applyChainsPaste() {
  const text = chainsPasteText.value
  if (!text.trim()) return
  try {
    const { centers, ops } = parseChainsBlocks(text)
    if (centers.length) params.chain_centers = centers
    if (!advancedOn.value) {
      if (centers.length) params.chain_num = centers.length
      if (ops.length) {
        params.space_group_ops = ops
        params.space_group_num = ops.length
      }
    }
    consoleLogs.push(t('inputGen.paste.parsedChains', { c: centers.length, o: ops.length }))
    if (advancedOn.value && ops.length) {
      consoleLogs.push(t('inputGen.hints.advNoSpaceGroup'))
    }
  } catch (e) {
    consoleLogs.push(`${t('inputGen.paste.errPrefix')}${e.message}`)
  }
}

// Parse a pasted cell fragment: exactly 6 numbers in order a b c α β γ
// (whitespace/comma separated, possibly on multiple lines).
function applyCellPaste() {
  const text = cellPasteText.value
  if (!text.trim()) return
  try {
    const nums = cleanPasteLines(text)
      .flatMap(l => tokens(l).map(Number))
    if (nums.some(n => !Number.isFinite(n))) throw new Error(t('inputGen.paste.errNum'))
    if (nums.length !== 6) throw new Error(t('inputGen.paste.errCellCount', { n: nums.length }))
    const [a, b, c, alpha, beta, gamma] = nums
    Object.assign(params.cell, { a, b, c, alpha, beta, gamma })
    consoleLogs.push(t('inputGen.paste.parsedCell', { v: nums.join('  ') }))
  } catch (e) {
    consoleLogs.push(`${t('inputGen.paste.errPrefix')}${e.message}`)
  }
}

// ---- Parameters (mirrors GenerateInputRequest) ----
const params = reactive({
  // basic
  wavelength: 1.24,
  generation_num: 400,
  num_atoms: 22,
  intensity_contribution: 400,
  // python build
  z_min: 10.7576,
  z_max: 10.6576,
  c_length: 10.6812,
  main_chain_num: 10,
  // thermal
  temperature_factor_stat: 0,
  temperature_factor_min: 0.15,
  temperature_factor_max: 0.35,
  // LM
  status_LM: 'NO',
  tol: 0.001,
  maxcall: 500,
  // helix
  period_num: 1,
  helix_num: 0,
  theta_add: 0,
  // modes
  single_chain_mod: 0,
  xray_source_mod: 0,
  stable_z_chain: 0,
  mirror_chain: 0,
  // chain & space group
  chain_num: 1,
  space_group_num: 0,
  // phase 2
  n_independent_chains: null,
  theta_ini_map_str: '',
  build_order: 0,
  pseudo_symmetry_mode: 0,
  // phase 5
  num_phases: 1,
  phase_weight: 1.0,
  // experimental
  molecular_mass: 224.0,
  sample_absorption_coeff: 6.2925,
  sample_thickness_cm: 0.336,
  air_absorption_coeff: 9.93,
  air_density: 0.001293,
  detector_distance_cm: 19.894,
  h_max: 5,
  k_max: 5,
  l_max: 20,
  max_hkl_per_peak: 50,
  max_blank_hkl: 2000,
  blank_contribution: 0.20,
  q_min: 0.0,
  // xraylib [260822]
  use_xraylib: 'off',
  chemical_formula: '',
  // equatorial module [260814] — module off by default; keys are only
  // emitted when equatorial_module_on is enabled
  equatorial_module_on: false,
  equatorial_blank_contribution: null,
  equatorial_profile_file: '',
  equatorial_profile_contribution: 1.0,
  equatorial_peak_fwhm: 0.04,
  equatorial_pv_eta: 0.5,
  equatorial_background: 0.0,
  equatorial_h_max: null,
  equatorial_k_max: null,
  // advanced multi-molecule [260815]
  advanced_multi_molecule: 'off',
  molecule1: { coordinate: [], forcefield: 'forcefield_mol1.txt' },
  molecule2: { coordinate: [], forcefield: 'forcefield_mol2.txt' },
  molecular_mass_mol1: 224.0,
  molecular_mass_mol2: 224.0,
  data_param_ratio_warn: 3.0,
  axis_penalty_weight: 0.0,
  mixture_fractions_str: '',
  mixture_fractions_fixed: 'no',
  // GA
  ga_steps: 100,
  ga_result_dir: 'result',
  ga_mode: 'basic',
  deep_search: 'off',
  deepsearch_steps: 2,
  deepsearch_start_topk: 1,
  freeze_threshold_r: 0.02,
  freeze_threshold_phi: 0.5,
  freeze_threshold_z: 0.02,
  freeze_threshold_sq: 0.01,
  freeze_streak_k: 3,
  warmup_percent: 0.1,
  warmup_generations: 0,
  pro_max_age: 50,
  elite_ratio: 0.2,
  pro_aggressive_ratio_early: 0.9,
  pro_aggressive_ratio_late: 0.8,
  pro_schedule_crossover_point: 0.5,
  dedup_threshold_r: 0.01,
  dedup_threshold_phi: 0.3,
  dedup_threshold_z: 0.01,
  // data blocks — cell starts empty (all six values required, validated
  // before generate; no silent example defaults)
  coordinate: [],
  cell: { a: null, b: null, c: null, alpha: null, beta: null, gamma: null },
  chain_centers: [],
  space_group_ops: [],
})

// ---- Field definitions ----

const basicFields = computed(() => [
  { key: 'wavelength', label: 'wavelength (Å)', type: 'number', step: 0.01, help: t('inputGen.help.wavelength') },
  { key: 'generation_num', label: 'generation_num', type: 'number', step: 1, min: 1, help: t('inputGen.help.generation_num') },
  { key: 'num_atoms', label: 'num_atoms', type: 'number', step: 1, min: 1, help: t('inputGen.help.num_atoms') },
  { key: 'intensity_contribution', label: 'intensity_contribution', type: 'number', step: 1, min: 0, help: t('inputGen.help.intensity_contribution') },
])

const cellFields = computed(() => [
  { key: 'a', label: 'a (Å)', type: 'number', step: 0.0001, placeholder: t('inputGen.hints.required'), help: t('inputGen.help.cell_a') },
  { key: 'b', label: 'b (Å)', type: 'number', step: 0.0001, placeholder: t('inputGen.hints.required'), help: t('inputGen.help.cell_b') },
  { key: 'c', label: 'c (Å)', type: 'number', step: 0.0001, placeholder: t('inputGen.hints.required'), help: t('inputGen.help.cell_c') },
  { key: 'alpha', label: 'alpha (°)', type: 'number', step: 0.0001, placeholder: t('inputGen.hints.required'), help: t('inputGen.help.cell_alpha') },
  { key: 'beta', label: 'beta (°)', type: 'number', step: 0.0001, placeholder: t('inputGen.hints.required'), help: t('inputGen.help.cell_beta') },
  { key: 'gamma', label: 'gamma (°)', type: 'number', step: 0.0001, placeholder: t('inputGen.hints.required'), help: t('inputGen.help.cell_gamma') },
])

const chainBasicFields = computed(() => [
  { key: 'chain_num', label: 'chain_num', type: 'number', step: 1, min: 1, help: t('inputGen.help.chain_num') },
  { key: 'space_group_num', label: 'space_group_num', type: 'number', step: 1, min: 0, help: t('inputGen.help.space_group_num') },
])

const helixFields = computed(() => [
  { key: 'period_num', label: 'period_num', type: 'number', step: 1, min: 1, help: t('inputGen.help.period_num') },
  { key: 'helix_num', label: 'helix_num', type: 'number', step: 0.1, min: 0, help: t('inputGen.help.helix_num') },
  { key: 'theta_add', label: 'theta_add (deg)', type: 'number', step: 0.1, help: t('inputGen.help.theta_add') },
])

const pythonBuildFields = computed(() => [
  { key: 'z_min', label: 'z_min (Å)', type: 'number', step: 0.0001, help: t('inputGen.help.z_min') },
  { key: 'z_max', label: 'z_max (Å)', type: 'number', step: 0.0001, help: t('inputGen.help.z_max') },
  { key: 'c_length', label: 'c_length (Å)', type: 'number', step: 0.0001, help: t('inputGen.help.c_length') },
  { key: 'main_chain_num', label: 'main_chain_num', type: 'number', step: 1, min: 1, help: t('inputGen.help.main_chain_num') },
])

const thermalFields = computed(() => [
  { key: 'temperature_factor_stat', label: 'temperature_factor_stat (0=isotropic)', type: 'select', help: t('inputGen.help.temperature_factor_stat'), options: [
    { value: 0, label: '0 — Isotropic' },
  ]},
  { key: 'temperature_factor_min', label: 'temperature_factor_min', type: 'number', step: 0.01, help: t('inputGen.help.temperature_factor_min') },
  { key: 'temperature_factor_max', label: 'temperature_factor_max', type: 'number', step: 0.01, help: t('inputGen.help.temperature_factor_max') },
])

const lmFields = computed(() => [
  { key: 'status_LM', label: 'status_LM', type: 'select', help: t('inputGen.help.status_LM'), options: [
    { value: 'NO', label: 'NO' },
    { value: 'YES', label: 'YES' },
  ]},
  { key: 'tol', label: 'tol', type: 'number', step: 0.0001, help: t('inputGen.help.tol') },
  { key: 'maxcall', label: 'maxcall', type: 'number', step: 1, min: 1, help: t('inputGen.help.maxcall') },
])

const modeFields = computed(() => [
  { key: 'single_chain_mod', label: 'single_chain_mod', type: 'select', help: t('inputGen.help.single_chain_mod'), options: [
    { value: 0, label: '0' }, { value: 1, label: '1' },
  ]},
  { key: 'xray_source_mod', label: 'xray_source_mod', type: 'select', help: t('inputGen.help.xray_source_mod'), options: [
    { value: 0, label: '0 — Synchrotron' },
    { value: 1, label: '1 — Laboratory' },
    { value: 2, label: '2 — Pol factor = 1' },
  ]},
  { key: 'stable_z_chain', label: 'stable_z_chain', type: 'select', help: t('inputGen.help.stable_z_chain'), options: [
    { value: 0, label: '0' }, { value: 1, label: '1' },
  ]},
  { key: 'mirror_chain', label: 'mirror_chain', type: 'select', help: t('inputGen.help.mirror_chain'), options: [
    { value: 0, label: '0' }, { value: 1, label: '1' }, { value: 2, label: '2' },
  ]},
])

const phase2Fields = computed(() => [
  { key: 'pseudo_symmetry_mode', label: 'pseudo_symmetry_mode', type: 'select', help: t('inputGen.help.pseudo_symmetry_mode'), options: [
    { value: 0, label: '0 — Off' }, { value: 1, label: '1 — Pass-through' },
    { value: 2, label: '2 — bc mirror' }, { value: 3, label: '3 — ac mirror' },
  ]},
  { key: 'n_independent_chains', label: 'n_independent_chains', type: 'number', step: 1, min: 1, placeholder: '= chain_num if empty', help: t('inputGen.help.n_independent_chains') },
  { key: 'theta_ini_map_str', label: 'theta_ini_map (space-separated ints)', type: 'text', placeholder: 'e.g. 1 2 1 2', help: t('inputGen.help.theta_ini_map') },
  { key: 'build_order', label: 'build_order', type: 'select', help: t('inputGen.help.build_order'), options: [
    { value: 0, label: '0 — translate then symmetry' },
    { value: 1, label: '1 — symmetry then translate' },
  ]},
])

const xraylibFields = computed(() => [
  { key: 'use_xraylib', label: 'use_xraylib', type: 'select', help: t('inputGen.help.use_xraylib'), options: [
    { value: 'off', label: 'off — legacy constants' },
    { value: 'on', label: 'on — xraylib auto (μ/ρ, M_cell, f0)' },
  ]},
  { key: 'chemical_formula', label: 'chemical_formula (repeat unit, e.g. C4H10O2)', type: 'text', help: t('inputGen.help.chemical_formula') },
])

const experimentalFields = computed(() => [
  { key: 'molecular_mass', label: 'molecular_mass (g/mol)', type: 'number', step: 0.1, help: t('inputGen.help.molecular_mass') },
  { key: 'sample_absorption_coeff', label: 'sample_absorption_coeff (cm²/g)', type: 'number', step: 0.0001, help: t('inputGen.help.sample_absorption_coeff') },
  { key: 'air_absorption_coeff', label: 'air_absorption_coeff (cm²/g)', type: 'number', step: 0.01, help: t('inputGen.help.air_absorption_coeff') },
  { key: 'sample_thickness_cm', label: 'sample_thickness_cm', type: 'number', step: 0.001, help: t('inputGen.help.sample_thickness_cm') },
  { key: 'air_density', label: 'air_density (g/cm³)', type: 'number', step: 0.000001, help: t('inputGen.help.air_density') },
  { key: 'detector_distance_cm', label: 'detector_distance_cm', type: 'number', step: 0.001, help: t('inputGen.help.detector_distance_cm') },
  { key: 'h_max', label: 'h_max', type: 'number', step: 1, min: 0, help: t('inputGen.help.h_max') },
  { key: 'k_max', label: 'k_max', type: 'number', step: 1, min: 0, help: t('inputGen.help.k_max') },
  { key: 'l_max', label: 'l_max', type: 'number', step: 1, min: 0, help: t('inputGen.help.l_max') },
  { key: 'max_hkl_per_peak', label: 'max_hkl_per_peak', type: 'number', step: 1, min: 1, help: t('inputGen.help.max_hkl_per_peak') },
  { key: 'max_blank_hkl', label: 'max_blank_hkl', type: 'number', step: 1, min: 1, help: t('inputGen.help.max_blank_hkl') },
  { key: 'blank_contribution', label: 'blank_contribution', type: 'number', step: 0.01, min: 0, help: t('inputGen.help.blank_contribution') },
  { key: 'q_min', label: 'q_min', type: 'number', step: 0.1, min: 0, help: t('inputGen.help.q_min') },
])

const equatorialEnableFields = computed(() => [
  { key: 'equatorial_module_on', label: t('inputGen.toggles.equatorial'), type: 'checkbox', help: t('inputGen.help.equatorial_module_on') },
])

const equatorialBaseFields = computed(() => [
  { key: 'equatorial_blank_contribution', label: 'equatorial_blank_contribution', type: 'number', step: 0.01, min: 0, placeholder: 'unset = blank_contribution', help: t('inputGen.help.equatorial_blank_contribution') },
  { key: 'equatorial_profile_file', label: 'equatorial_profile_file', type: 'text', placeholder: 'e.g. equatorial_profile.txt (empty = off)', help: t('inputGen.help.equatorial_profile_file') },
])

const equatorialProfileFields = computed(() => [
  { key: 'equatorial_profile_contribution', label: 'equatorial_profile_contribution', type: 'number', step: 0.1, min: 0, help: t('inputGen.help.equatorial_profile_contribution') },
  { key: 'equatorial_peak_fwhm', label: 'equatorial_peak_fwhm (Å⁻¹)', type: 'number', step: 0.005, min: 0.001, help: t('inputGen.help.equatorial_peak_fwhm') },
  { key: 'equatorial_pv_eta', label: 'equatorial_pv_eta (Lorentzian fraction)', type: 'slider', min: 0, max: 1, step: 0.05, help: t('inputGen.help.equatorial_pv_eta') },
  { key: 'equatorial_background', label: 'equatorial_background', type: 'number', step: 0.01, min: 0, help: t('inputGen.help.equatorial_background') },
  { key: 'equatorial_h_max', label: 'equatorial_h_max', type: 'number', step: 1, min: 0, placeholder: 'unset = h_max', help: t('inputGen.help.equatorial_h_max') },
  { key: 'equatorial_k_max', label: 'equatorial_k_max', type: 'number', step: 1, min: 0, placeholder: 'unset = k_max', help: t('inputGen.help.equatorial_k_max') },
])

const advancedFields = computed(() => [
  { key: 'advanced_multi_molecule', label: 'advanced_multi_molecule', type: 'select', help: t('inputGen.help.advanced_multi_molecule'), options: [
    { value: 'off', label: 'off — standard mode' },
    { value: 'case_a', label: 'case_a — fixed positions (mol1@pos1, mol2@pos2)' },
    { value: 'case_b', label: 'case_b — shared positions, 3-domain mixture' },
  ]},
  { key: 'molecular_mass_mol1', label: 'molecular_mass_mol1', type: 'number', step: 0.1, help: t('inputGen.help.molecular_mass_mol1') },
  { key: 'molecular_mass_mol2', label: 'molecular_mass_mol2', type: 'number', step: 0.1, help: t('inputGen.help.molecular_mass_mol2') },
  { key: 'data_param_ratio_warn', label: 'data_param_ratio_warn (>1)', type: 'number', step: 0.1, min: 1.1, help: t('inputGen.help.data_param_ratio_warn') },
  { key: 'axis_penalty_weight', label: 'axis_penalty_weight (0 = off)', type: 'number', step: 0.1, min: 0, help: t('inputGen.help.axis_penalty_weight') },
])

const mixtureFields = computed(() => [
  { key: 'mixture_fractions_str', label: 'mixture_fractions (p1 p2 p12)', type: 'text', placeholder: 'e.g. 0.25 0.25 0.5 (empty = random init)', help: t('inputGen.help.mixture_fractions') },
  { key: 'mixture_fractions_fixed', label: 'mixture_fractions_fixed', type: 'select', help: t('inputGen.help.mixture_fractions_fixed'), options: [
    { value: 'no', label: 'no — optimized by LM' },
    { value: 'yes', label: 'yes — fixed (requires fractions)' },
  ]},
])

function molForceFields(mi) {
  return [{ key: 'forcefield', label: `forcefield_mol${mi + 1}`, type: 'text', help: t('inputGen.help.forcefield') }]
}

const outputFields = computed(() => [
  { key: 'print_level', label: 'print_level', type: 'select', help: t('inputGen.help.print_level'), options: [
    { value: 'low', label: 'low' }, { value: 'medium', label: 'medium' }, { value: 'high', label: 'high' },
  ]},
])

const gaFields = computed(() => [
  { key: 'ga_mode', label: 'ga_mode', type: 'select', help: t('inputGen.help.ga_mode'), options: [
    { value: 'basic', label: 'basic' }, { value: 'flash', label: 'flash' }, { value: 'pro', label: 'pro' },
  ]},
  { key: 'ga_steps', label: 'ga_steps', type: 'number', step: 1, min: 1, help: t('inputGen.help.ga_steps') },
  { key: 'ga_result_dir', label: 'ga_result_dir', type: 'text', help: t('inputGen.help.ga_result_dir') },
])

const deepSearchFields = computed(() => [
  { key: 'deep_search', label: 'deep_search', type: 'select', help: t('inputGen.help.deep_search'), options: [
    { value: 'off', label: 'off' },
    { value: 'on', label: 'on — post case_a dual-molecule refinement' },
  ]},
])

const deepSearchParams = computed(() => [
  { key: 'deepsearch_steps', label: 'deepsearch_steps', type: 'number', step: 1, min: 1, help: t('inputGen.help.deepsearch_steps') },
  { key: 'deepsearch_start_topk', label: 'deepsearch_start_topk (V1: 1)', type: 'number', step: 1, min: 1, max: 1, help: t('inputGen.help.deepsearch_start_topk') },
])

const gaFlashFields = computed(() => [
  { key: 'freeze_threshold_r', label: 'freeze_threshold_r', type: 'number', step: 0.01, min: 0, help: t('inputGen.help.freeze_threshold_r') },
  { key: 'freeze_threshold_phi', label: 'freeze_threshold_phi', type: 'number', step: 0.1, min: 0, help: t('inputGen.help.freeze_threshold_phi') },
  { key: 'freeze_threshold_z', label: 'freeze_threshold_z', type: 'number', step: 0.01, min: 0, help: t('inputGen.help.freeze_threshold_z') },
  { key: 'freeze_threshold_sq', label: 'freeze_threshold_sq', type: 'number', step: 0.01, min: 0, help: t('inputGen.help.freeze_threshold_sq') },
  { key: 'freeze_streak_k', label: 'freeze_streak_k', type: 'number', step: 1, min: 0, help: t('inputGen.help.freeze_streak_k') },
  { key: 'warmup_percent', label: 'warmup_percent', type: 'slider', min: 0, max: 1, step: 0.01, help: t('inputGen.help.warmup_percent') },
  { key: 'warmup_generations', label: 'warmup_generations', type: 'number', step: 1, min: 0, help: t('inputGen.help.warmup_generations') },
])

const gaProFields = computed(() => [
  { key: 'pro_max_age', label: 'pro_max_age', type: 'number', step: 1, min: 1, help: t('inputGen.help.pro_max_age') },
  { key: 'elite_ratio', label: 'elite_ratio', type: 'slider', min: 0.01, max: 1, step: 0.01, help: t('inputGen.help.elite_ratio') },
  { key: 'pro_aggressive_ratio_early', label: 'pro_aggressive_ratio_early', type: 'slider', min: 0.01, max: 1, step: 0.01, help: t('inputGen.help.pro_aggressive_ratio_early') },
  { key: 'pro_aggressive_ratio_late', label: 'pro_aggressive_ratio_late', type: 'slider', min: 0.01, max: 1, step: 0.01, help: t('inputGen.help.pro_aggressive_ratio_late') },
  { key: 'pro_schedule_crossover_point', label: 'pro_schedule_crossover_point', type: 'slider', min: 0, max: 1, step: 0.01, help: t('inputGen.help.pro_schedule_crossover_point') },
  { key: 'dedup_threshold_r', label: 'dedup_threshold_r', type: 'number', step: 0.01, min: 0, help: t('inputGen.help.dedup_threshold_r') },
  { key: 'dedup_threshold_phi', label: 'dedup_threshold_phi', type: 'number', step: 0.1, min: 0, help: t('inputGen.help.dedup_threshold_phi') },
  { key: 'dedup_threshold_z', label: 'dedup_threshold_z', type: 'number', step: 0.01, min: 0, help: t('inputGen.help.dedup_threshold_z') },
])

// ---- Data-block helpers ----

function addAtom() {
  params.coordinate.push({ element: 'C', r_min: 0, r_max: 2, z_idx: 1 })
}

function removeAtom() {
  params.coordinate.pop()
}

function addMolAtom(mk) {
  params[mk].coordinate.push({ element: 'C', r_min: 0, r_max: 2, z_idx: 1 })
}

function removeMolAtom(mk) {
  params[mk].coordinate.pop()
}

function addChainCenter() {
  params.chain_centers.push({ x: 0.0, y: 0.0, z: 0.0 })
}

function removeChainCenter() {
  params.chain_centers.pop()
}

function addSpaceGroupOp() {
  params.space_group_ops.push({ transdirect: [1.0, 1.0, 1.0], center_move: [0.0, 0.0, 0.0] })
}

function removeSpaceGroupOp() {
  params.space_group_ops.pop()
}

// ---- Build request payload ----

// Pre-flight checks mirroring the Fortran/input checks: cell completeness,
// coordinate row count vs num_atoms, chain/space-group table consistency.
function validateBeforeGenerate() {
  const errs = []
  const c = params.cell
  const cellKeys = ['a', 'b', 'c', 'alpha', 'beta', 'gamma']
  if (cellKeys.some(k => c[k] === null || c[k] === undefined || Number.isNaN(Number(c[k])))) {
    errs.push(t('inputGen.hints.cellMissing'))
  } else if (Math.min(Number(c.a), Number(c.b), Number(c.c)) <= 0) {
    errs.push(t('inputGen.hints.cellLenPositive'))
  } else if ([c.alpha, c.beta, c.gamma].some(v => !(Number(v) > 0 && Number(v) < 180))) {
    errs.push(t('inputGen.hints.cellAngleRange'))
  }
  if (!advancedOn.value) {
    if (params.coordinate.length !== params.num_atoms) {
      errs.push(t('inputGen.hints.coordCountMismatch', { n: params.coordinate.length, total: params.num_atoms }))
    }
    if (params.chain_centers.length && params.chain_centers.length !== params.chain_num) {
      errs.push(t('inputGen.hints.chainCentersMismatch', { n: params.chain_centers.length, total: params.chain_num }))
    }
    if (params.space_group_ops.length && params.space_group_ops.length !== params.space_group_num) {
      errs.push(t('inputGen.hints.spaceGroupMismatch', { n: params.space_group_ops.length, total: params.space_group_num }))
    }
  } else if (!params.molecule1.coordinate.length || !params.molecule2.coordinate.length) {
    errs.push(t('inputGen.hints.molCoordEmpty'))
  }
  return errs
}

function buildRequest() {
  const p = params
  // Parse theta_ini_map from string
  let thetaIniMap = null
  if (p.theta_ini_map_str && p.theta_ini_map_str.trim()) {
    thetaIniMap = p.theta_ini_map_str.trim().split(/\s+/).map(Number)
  }
  // Parse mixture_fractions from string (case_b)
  let mixtureFractions = null
  if (p.mixture_fractions_str && p.mixture_fractions_str.trim()) {
    mixtureFractions = p.mixture_fractions_str.trim().split(/[\s,]+/).map(Number)
  }
  return {
    wavelength: p.wavelength,
    generation_num: p.generation_num,
    num_atoms: p.num_atoms,
    chain_num: p.chain_num,
    z_min: p.z_min,
    z_max: p.z_max,
    c_length: p.c_length,
    main_chain_num: p.main_chain_num,
    intensity_contribution: p.intensity_contribution,
    print_level: p.print_level,
    chemical_formula: p.chemical_formula || null,
    temperature_factor_stat: p.temperature_factor_stat,
    temperature_factor_min: p.temperature_factor_min,
    temperature_factor_max: p.temperature_factor_max,
    status_LM: p.status_LM,
    tol: p.tol,
    maxcall: p.maxcall,
    period_num: p.period_num,
    helix_num: p.helix_num,
    theta_add: p.theta_add,
    single_chain_mod: p.single_chain_mod,
    xray_source_mod: p.xray_source_mod,
    stable_z_chain: p.stable_z_chain,
    mirror_chain: p.mirror_chain,
    space_group_num: p.space_group_num,
    n_independent_chains: p.n_independent_chains,
    theta_ini_map: thetaIniMap,
    build_order: p.build_order,
    pseudo_symmetry_mode: p.pseudo_symmetry_mode,
    num_phases: p.num_phases,
    phase_weight: p.phase_weight,
    molecular_mass: p.molecular_mass,
    sample_absorption_coeff: p.sample_absorption_coeff,
    sample_thickness_cm: p.sample_thickness_cm,
    air_absorption_coeff: p.air_absorption_coeff,
    air_density: p.air_density,
    detector_distance_cm: p.detector_distance_cm,
    h_max: p.h_max,
    k_max: p.k_max,
    l_max: p.l_max,
    max_hkl_per_peak: p.max_hkl_per_peak,
    max_blank_hkl: p.max_blank_hkl,
    blank_contribution: p.blank_contribution,
    q_min: p.q_min,
    use_xraylib: p.use_xraylib,
    // equatorial [260814]: module off by default — when the toggle is off no
    // equatorial_* key is sent, so the backend emits none (old behavior)
    equatorial_blank_contribution: p.equatorial_module_on ? p.equatorial_blank_contribution : null,
    equatorial_profile_file: p.equatorial_module_on ? ((p.equatorial_profile_file || '').trim() || null) : null,
    equatorial_profile_contribution: p.equatorial_profile_contribution,
    equatorial_peak_fwhm: p.equatorial_peak_fwhm,
    equatorial_pv_eta: p.equatorial_pv_eta,
    equatorial_background: p.equatorial_background,
    equatorial_h_max: p.equatorial_h_max,
    equatorial_k_max: p.equatorial_k_max,
    advanced_multi_molecule: p.advanced_multi_molecule,
    molecule1: p.molecule1,
    molecule2: p.molecule2,
    molecular_mass_mol1: p.molecular_mass_mol1,
    molecular_mass_mol2: p.molecular_mass_mol2,
    data_param_ratio_warn: p.data_param_ratio_warn,
    axis_penalty_weight: p.axis_penalty_weight,
    mixture_fractions: mixtureFractions,
    mixture_fractions_fixed: p.mixture_fractions_fixed,
    ga_steps: p.ga_steps,
    ga_result_dir: p.ga_result_dir,
    ga_mode: p.ga_mode,
    deep_search: p.deep_search,
    deepsearch_steps: p.deepsearch_steps,
    deepsearch_start_topk: p.deepsearch_start_topk,
    freeze_threshold_r: p.freeze_threshold_r,
    freeze_threshold_phi: p.freeze_threshold_phi,
    freeze_threshold_z: p.freeze_threshold_z,
    freeze_threshold_sq: p.freeze_threshold_sq,
    freeze_streak_k: p.freeze_streak_k,
    warmup_percent: p.warmup_percent,
    warmup_generations: p.warmup_generations,
    pro_max_age: p.pro_max_age,
    elite_ratio: p.elite_ratio,
    pro_aggressive_ratio_early: p.pro_aggressive_ratio_early,
    pro_aggressive_ratio_late: p.pro_aggressive_ratio_late,
    pro_schedule_crossover_point: p.pro_schedule_crossover_point,
    dedup_threshold_r: p.dedup_threshold_r,
    dedup_threshold_phi: p.dedup_threshold_phi,
    dedup_threshold_z: p.dedup_threshold_z,
    coordinate: params.coordinate,
    cell: params.cell,
    chain_centers: params.chain_centers,
    space_group_ops: params.space_group_ops,
  }
}

// ---- Actions ----

async function generatePreview() {
  const errs = validateBeforeGenerate()
  if (errs.length) {
    consoleLogs.length = 0
    errs.forEach(e => consoleLogs.push(e))
    taskStatus.value = 'failed'
    previewText.value = ''
    return
  }
  taskStatus.value = 'running'
  generating.value = true
  consoleLogs.length = 0
  consoleLogs.push(t('inputGen.logs.generating'))
  try {
    const res = await inputGenGenerate(buildRequest())
    previewText.value = typeof res.data === 'string' ? res.data : JSON.stringify(res.data)
    consoleLogs.push(t('inputGen.logs.generated'))
    taskStatus.value = 'completed'
  } catch (err) {
    consoleLogs.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'failed'
  } finally {
    generating.value = false
  }
}

function downloadInput() {
  if (!previewText.value) return
  const blob = new Blob([previewText.value], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'input.txt'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.ig-page { display: flex; flex-direction: column; }

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
  margin: 0 0 12px;
}

.adv-note {
  margin-top: 20px;
  padding: 10px 14px;
  border-radius: 6px;
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

/* ---- Data table ---- */
.table-toolbar {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
}
.toolbar-hint { font-size: 12px; color: var(--color-text-secondary); margin-left: auto; }

.table-wrap { overflow-x: auto; border-radius: 6px; border: 1px solid var(--color-border); }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  padding: 7px 10px; text-align: center; font-weight: 600;
  color: var(--color-text-secondary); background: var(--color-neutral);
  border-bottom: 1px solid var(--color-border); text-transform: uppercase;
  font-size: 10.5px; letter-spacing: 0.5px;
}
.data-table td { padding: 4px 6px; border-bottom: 1px solid var(--color-border); text-align: center; }
.cell-idx { color: var(--color-text-secondary); font-size: 11px; width: 36px; }
.cell-input {
  width: 100%; padding: 5px 6px; border: 1px solid var(--color-border);
  border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: var(--color-text); background: var(--color-bg); outline: none;
  box-sizing: border-box; text-align: center;
}
.cell-input:focus { border-color: var(--color-primary); }
.cell-empty { padding: 24px; color: var(--color-text-secondary); font-style: italic; }

/* ---- Actions ---- */
.actions-row { display: flex; gap: 12px; margin-top: 20px; }

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
.btn-compact:disabled { opacity: 0.4; cursor: not-allowed; }

/* ---- Paste-to-fill blocks ---- */
.paste-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  margin-bottom: 16px;
  background: var(--color-primary-10, rgba(124, 58, 237, 0.05));
  border: 1px dashed var(--color-border);
  border-radius: 10px;
  align-self: stretch;
}
.paste-block__head { font-size: 12px; font-weight: 700; color: var(--color-text); }
.paste-block__textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  line-height: 1.55;
  color: var(--color-text);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  outline: none;
  resize: vertical;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}
.paste-block__textarea:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.2);
}
.paste-block__textarea::placeholder { color: var(--color-text-secondary); opacity: 0.7; white-space: pre-wrap; }
.paste-block .btn-compact { align-self: flex-start; }

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

/* ---- Fade ---- */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 1024px) {
  .sidebar { width: 52px; }
  .nav-label { display: none; }
  .sidebar-footer { display: none; }
}
</style>
