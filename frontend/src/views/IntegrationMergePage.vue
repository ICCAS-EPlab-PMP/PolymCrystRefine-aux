<template>
  <div class="waxs-page">
    <div class="main-container">
      <aside class="sidebar">
        <nav class="tab-nav">
          <!-- Batch Import -->
          <button
            :class="['tab-item', { active: activeTab === 'batchImport' }]"
            @click="activeTab = 'batchImport'"
          >
            <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="17,8 12,3 7,8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <span class="tab-label">{{ t('waxs.tabs.batchImport') }}</span>
          </button>

          <!-- Merge (above background — the typical first step) -->
          <button
            :class="['tab-item', { active: activeTab === 'merge' }]"
            @click="activeTab = 'merge'"
          >
            <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8 3v4a4 4 0 004 4h0a4 4 0 004-4V3" />
              <line x1="12" y1="11" x2="12" y2="21" />
              <polyline points="8,17 12,21 16,17" />
            </svg>
            <span class="tab-label">{{ t('waxs.tabs.merge') }}</span>
          </button>

          <!-- Background -->
          <button
            :class="['tab-item', { active: activeTab === 'background' }]"
            @click="activeTab = 'background'"
          >
            <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M2 12c2-4 6-7 10-7s8 3 10 7" />
              <path d="M2 12c2 4 6 7 10 7s8-3 10-7" />
              <line x1="2" y1="12" x2="22" y2="12" stroke-dasharray="3 3" />
            </svg>
            <span class="tab-label">{{ t('waxs.tabs.background') }}</span>
          </button>
        </nav>

        <div class="sidebar-footer">
          <div class="status-indicator">
            <span class="status-dot" :class="statusClass"></span>
            <span class="status-text">{{ statusLabel }}</span>
          </div>
        </div>
      </aside>

      <main class="content">
        <transition name="fade" mode="out-in">
          <!-- Batch Import -->
          <div v-if="activeTab === 'batchImport'" key="batchImport" class="tab-panel">
            <div class="card">
              <h2 class="card-title">{{ t('waxs.batchImport.title') }}</h2>
              <p class="card-desc">{{ t('waxs.batchImport.desc') }}</p>

              <FileUpload
                accept=".npy,.tif,.tiff,.edf,.h5"
                :label="t('waxs.batchImport.dropLabel')"
                @files-selected="onDataFiles"
              />

              <div class="json-block">
                <FileUpload
                  accept=".json,.txt"
                  :multiple="false"
                  :label="t('waxs.batchImport.jsonLabel')"
                  @files-selected="onInfoFile"
                />
                <p v-if="infoParseStatus.state === 'ok'" class="json-parsed">
                  {{ t('waxs.batchImport.infoOk', { fields: infoParseStatus.keys.join(', ') }) }}
                </p>
                <p v-else-if="infoParseStatus.state === 'empty'" class="json-parsed json-parsed--warn">
                  {{ t('waxs.batchImport.infoEmpty', { file: infoParseStatus.source }) }}
                </p>
                <p v-else-if="infoParseStatus.state === 'error'" class="json-parsed json-parsed--warn">
                  {{ t('waxs.batchImport.infoError', { msg: infoParseStatus.message }) }}
                </p>
              </div>

              <div class="param-actions">
                <button
                  class="btn-primary"
                  :disabled="!dataFiles.length || runStatus === 'running'"
                  @click="runBatchUpload"
                >{{ t('waxs.batchImport.btnLoad') }}</button>
                <span v-if="batchItems.length" class="loaded-count">
                  {{ t('waxs.batchImport.loaded', { n: batchItems.length }) }}
                </span>
              </div>

              <Console
                v-if="consoleLogs.import.length"
                :logs="consoleLogs.import"
                style="margin-top: 16px"
              />

              <!-- File info table -->
              <div v-if="batchItems.length" class="info-table-wrap">
                <h3 class="info-table-title">{{ t('waxs.batchImport.tableTitle') }}</h3>
                <div class="info-table-scroll">
                  <table class="info-table">
                    <thead>
                      <tr>
                        <th>{{ t('waxs.batchImport.colFile') }}</th>
                        <th>{{ t('waxs.batchImport.colXAxis') }}</th>
                        <th>{{ t('waxs.batchImport.colYAxis') }}</th>
                        <th>{{ t('waxs.batchImport.colPoints') }}</th>
                        <th>{{ t('waxs.batchImport.colPolar') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in batchItems" :key="item.fileId">
                        <td class="cell-file">{{ item.name }}</td>
                        <td>{{ fmtRange(item.info?.xAxisRange) }}</td>
                        <td>{{ fmtRange(item.info?.yAxisRangeDeg, '°') }}</td>
                        <td>{{ fmtPoints(item.info?.integrationPoints) }}</td>
                        <td>{{ fmtScalar(item.info?.polarizationFactor) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          <!-- Merge -->
          <div v-else-if="activeTab === 'merge'" key="merge" class="tab-panel">
            <div class="card">
              <h2 class="card-title">{{ t('waxs.merge.title') }}</h2>
              <p class="card-desc">{{ t('waxs.merge.desc') }}</p>

              <!-- Input source: original cakes OR per-image background-subtracted cakes -->
              <div class="forward-toggle">
                <label class="forward-toggle__switch" :class="{ 'forward-toggle__switch--on': effectiveUseBgForMerge, 'forward-toggle__switch--disabled': !perItemBgAvailable }">
                  <input
                    type="checkbox"
                    :checked="useBgForMerge"
                    :disabled="!perItemBgAvailable"
                    @change="useBgForMerge = $event.target.checked"
                  />
                  <span class="forward-toggle__track"><span class="forward-toggle__thumb"></span></span>
                  <span class="forward-toggle__label">{{ t('waxs.merge.useBgForMerge') }}</span>
                </label>
                <p class="forward-toggle__status">
                  <span v-if="effectiveUseBgForMerge" class="status-chip status-chip--bg">{{ t('waxs.merge.usesBg') }}</span>
                  <span v-else-if="perItemBgAvailable" class="status-chip status-chip--orig">{{ t('waxs.merge.usesOriginal') }}</span>
                  <span v-else class="status-chip status-chip--orig">{{ t('waxs.merge.bgNotRun') }}</span>
                </p>
              </div>

              <ParamsForm :fields="mergeFields" :modelValue="mergeParams" @update:modelValue="Object.assign(mergeParams, $event)" />

              <!-- Per-image chi offset table -->
              <div v-if="batchItems.length" class="chi-offset-wrap">
                <h3 class="chi-offset-title">{{ t('waxs.merge.chiOffsetTitle') }}</h3>
                <div class="info-table-scroll">
                  <table class="info-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>{{ t('waxs.batchImport.colFile') }}</th>
                        <th>{{ t('waxs.merge.chiOffsetCol') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(item, i) in batchItems" :key="item.fileId">
                        <td>{{ i + 1 }}</td>
                        <td class="cell-file">
                          {{ item.name }}
                          <span v-if="effectiveUseBgForMerge" class="bg-tag">bg</span>
                        </td>
                        <td>
                          <input
                            type="number"
                            class="chi-input"
                            step="any"
                            :value="chiOffsets[i] ?? 0"
                            @input="setChiOffset(i, $event.target.value)"
                          />
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div class="param-actions">
                <button
                  class="btn-primary"
                  :disabled="!batchItems.length || runStatus === 'running'"
                  @click="runMerge"
                >{{ t('waxs.merge.btnRun') }}</button>
                <button
                  class="btn-secondary"
                  :disabled="!stepLog.length"
                  @click="exportAllSteps"
                >{{ t('waxs.merge.exportAll', { n: stepLog.length }) }}</button>
                <span v-if="!batchItems.length" class="hint">{{ t('waxs.merge.needImport') }}</span>
              </div>

              <Console
                v-if="consoleLogs.merge.length"
                :logs="consoleLogs.merge"
                style="margin-top: 16px"
              />

              <!-- Current merge result viewer -->
              <div v-if="currentMergeStep && currentMergeStep.items[0] && currentMergeStep.items[0].preview" class="result-block">
                <ImageCanvas
                  :image-data="currentMergeStep.items[0].preview"
                  :title="`${t('waxs.merge.resultTitle')} · ${currentMergeStep.title}`"
                  colorscale="Viridis"
                  :height="560"
                  :zmin="mergeContrastMin"
                  :zmax="mergeContrastMax"
                  :aspect-ratio="'4 / 3'"
                />
                <div class="contrast-controls">
                  <div class="contrast-field">
                    <label>{{ t('waxs.merge.contrastMin') }} · {{ formatNum(mergeContrastMin) }}</label>
                    <input type="range" :min="mergeFloor" :max="mergeCeil" :step="mergeStepC" v-model.number="mergeContrastMin" />
                  </div>
                  <div class="contrast-field">
                    <label>{{ t('waxs.merge.contrastMax') }} · {{ formatNum(mergeContrastMax) }}</label>
                    <input type="range" :min="mergeFloor" :max="mergeCeil" :step="mergeStepC" v-model.number="mergeContrastMax" />
                  </div>
                  <button class="btn-secondary btn-sm" @click="resetMergeContrast">{{ t('waxs.merge.contrastReset') }}</button>
                </div>
                <div class="param-actions">
                  <button class="btn-secondary" @click="exportStep(currentMergeStep)">{{ t('waxs.merge.exportStep') }}</button>
                </div>
              </div>
              <div v-else class="result-empty">{{ t('waxs.merge.noResult') }}</div>

              <!-- Merge step history -->
              <div v-if="mergeSteps.length" class="history">
                <h3 class="history__title">{{ t('waxs.merge.historyTitle') }}</h3>
                <div
                  v-for="s in mergeSteps"
                  :key="s.id"
                  :class="['history__row', { 'history__row--active': currentMergeStep && s.id === currentMergeStep.id }]"
                >
                  <div class="history__info">
                    <span class="history__name">{{ s.title }}</span>
                    <span class="history__meta">{{ s.sourceLabel }} · {{ formatStepParams(s) }}</span>
                  </div>
                  <div class="history__actions">
                    <button class="btn-link" @click="viewMerge(s.id)">{{ t('waxs.merge.view') }}</button>
                    <button class="btn-link" @click="exportStep(s)">{{ t('waxs.merge.exportStep') }}</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Background -->
          <div v-else-if="activeTab === 'background'" key="background" class="tab-panel">
            <div class="card">
              <h2 class="card-title">{{ t('waxs.background.title') }}</h2>
              <p class="card-desc">{{ t('waxs.background.desc') }}</p>

              <!-- Input source: original cakes (per-image) OR the merge result (single) -->
              <div class="forward-toggle">
                <label class="forward-toggle__switch" :class="{ 'forward-toggle__switch--on': effectiveUseMergeForBg, 'forward-toggle__switch--disabled': !lastMergeStep }">
                  <input
                    type="checkbox"
                    :checked="useMergeForBg"
                    :disabled="!lastMergeStep"
                    @change="useMergeForBg = $event.target.checked"
                  />
                  <span class="forward-toggle__track"><span class="forward-toggle__thumb"></span></span>
                  <span class="forward-toggle__label">{{ t('waxs.background.useMergeForBg') }}</span>
                </label>
                <p class="forward-toggle__status">
                  <span v-if="effectiveUseMergeForBg" class="status-chip status-chip--bg">{{ t('waxs.background.usesMerge') }}</span>
                  <span v-else-if="lastMergeStep" class="status-chip status-chip--orig">{{ t('waxs.background.usesOriginalPerItem') }}</span>
                  <span v-else class="status-chip status-chip--orig">{{ t('waxs.background.mergeNotRun') }}</span>
                </p>
              </div>

              <ParamsForm :fields="backgroundFields" :modelValue="backgroundParams" @update:modelValue="Object.assign(backgroundParams, $event)" />

              <div class="param-actions">
                <button
                  class="btn-primary"
                  :disabled="(!effectiveUseMergeForBg && !batchItems.length) || runStatus === 'running'"
                  @click="runBackground"
                >{{ t('waxs.background.btnRun') }}</button>
                <button
                  class="btn-secondary"
                  :disabled="!stepLog.length"
                  @click="exportAllSteps"
                >{{ t('waxs.background.exportAll', { n: stepLog.length }) }}</button>
                <span v-if="!effectiveUseMergeForBg && !batchItems.length" class="hint">{{ t('waxs.background.needImport') }}</span>
              </div>

              <Console
                v-if="consoleLogs.background.length"
                :logs="consoleLogs.background"
                style="margin-top: 16px"
              />

              <!-- Current background result viewer -->
              <div v-if="currentBgItem && currentBgItem.preview" class="result-block">
                <ImageCanvas
                  :image-data="currentBgItem.preview"
                  :title="`${t('waxs.background.resultTitle')} · ${currentBgStep.title}${currentBgStep.mode === 'perItem' && currentBgStep.items.length > 1 ? ' · ' + currentBgItem.name : ''}`"
                  colorscale="Viridis"
                  :height="560"
                  :zmin="bgContrastMin"
                  :zmax="bgContrastMax"
                  :aspect-ratio="'4 / 3'"
                />
                <div class="contrast-controls">
                  <div class="contrast-field">
                    <label>{{ t('waxs.background.contrastMin') }} · {{ formatNum(bgContrastMin) }}</label>
                    <input type="range" :min="bgFloor" :max="bgCeil" :step="bgStep" v-model.number="bgContrastMin" />
                  </div>
                  <div class="contrast-field">
                    <label>{{ t('waxs.background.contrastMax') }} · {{ formatNum(bgContrastMax) }}</label>
                    <input type="range" :min="bgFloor" :max="bgCeil" :step="bgStep" v-model.number="bgContrastMax" />
                  </div>
                  <button class="btn-secondary btn-sm" @click="resetBgContrast">{{ t('waxs.background.contrastReset') }}</button>
                </div>
                <div class="param-actions">
                  <button class="btn-secondary" @click="exportStep(currentBgStep)">{{ t('waxs.background.exportStep') }}</button>
                </div>
              </div>
              <div v-else class="result-empty">{{ t('waxs.background.noResult') }}</div>

              <!-- Per-image thumbnails -->
              <div v-if="showBgThumbs" class="thumbs-block">
                <div class="thumbs-label">{{ t('waxs.background.thumbsTitle') }}</div>
                <div class="thumbs-row">
                  <div
                    v-for="(it, i) in currentBgStep.items"
                    :key="i"
                    :class="['thumb', { active: i === bgCurrentIdx }]"
                    :title="it.name"
                    @click="bgCurrentIdx = i"
                  >
                    <canvas :ref="(el) => setBgThumbRef(el, i)" class="thumb__canvas" width="192" height="192"></canvas>
                    <span class="thumb__name">{{ it.name }}</span>
                  </div>
                </div>
              </div>

              <!-- Background step history -->
              <div v-if="bgSteps.length" class="history">
                <h3 class="history__title">{{ t('waxs.background.historyTitle') }}</h3>
                <div
                  v-for="s in bgSteps"
                  :key="s.id"
                  :class="['history__row', { 'history__row--active': currentBgStep && s.id === currentBgStep.id }]"
                >
                  <div class="history__info">
                    <span class="history__name">{{ s.title }}</span>
                    <span class="history__meta">{{ s.sourceLabel }} · {{ formatStepParams(s) }}</span>
                  </div>
                  <div class="history__actions">
                    <button class="btn-link" @click="viewBg(s.id)">{{ t('waxs.background.view') }}</button>
                    <button class="btn-link" @click="exportStep(s)">{{ t('waxs.background.exportStep') }}</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import FileUpload from '@/components/FileUpload.vue'
import ParamsForm from '@/components/ParamsForm.vue'
import ImageCanvas from '@/components/ImageCanvas.vue'
import {
  waxsUploadFiles,
  waxsRunBackground,
  waxsRunMerge,
  waxsStepsExport,
  integrationGetImage,
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
  },
})

const { t } = useI18n()

// ---- Tab + run state ----
const activeTab = ref('batchImport')
const runStatus = ref('idle')

const statusClass = computed(() => {
  if (runStatus.value === 'running') return 'running'
  if (runStatus.value === 'completed') return 'success'
  if (runStatus.value === 'failed') return 'error'
  return ''
})
const statusLabel = computed(() => {
  const labels = {
    idle: t('status.idle'),
    running: t('status.running'),
    completed: t('status.completed'),
    failed: t('status.failed'),
  }
  return labels[runStatus.value] || runStatus.value
})

// ---- Batch import state (original cakes only) ----
const dataFiles = ref([])
const sharedInfo = ref(null)               // single processing_info applied to ALL cakes
const batchItems = ref([])                 // [{ fileId, name, info }] — never mutated by bg/merge

// Parse status for the uploaded processing_info — surfaces exactly which fields
// were recognized so a wrong-format file no longer fails silently into placeholders.
// { state: 'none' | 'ok' | 'empty' | 'error', keys: string[], source: string, message: string }
const infoParseStatus = ref({ state: 'none', keys: [], source: '', message: '' })

// ---- Background params (radius, type classic/smooth, impl scipy/skimage, sigma) ----
const backgroundParams = reactive({
  ballRadius: 20,
  rollingBallType: 'classic',
  method: 'scipy',
  smoothingSigma: 0,
  fillValue: 0,
  maskZeros: false,
})
const backgroundFields = computed(() => [
  { key: 'ballRadius', label: t('waxs.background.ballRadius'), type: 'slider', min: 1, max: 100, step: 1 },
  {
    key: 'rollingBallType', label: t('waxs.background.rollingBallType'), type: 'select',
    options: [
      { value: 'classic', label: t('waxs.background.typeOptions.classic') },
      { value: 'smooth', label: t('waxs.background.typeOptions.smooth') },
    ],
  },
  {
    key: 'method', label: t('waxs.background.method'), type: 'select',
    options: [
      { value: 'scipy', label: t('waxs.background.versionOptions.scipy') },
      { value: 'skimage', label: t('waxs.background.versionOptions.skimage') },
    ],
  },
  { key: 'smoothingSigma', label: t('waxs.background.smoothingSigma'), type: 'slider', min: 0, max: 5, step: 0.1 },
  { key: 'fillValue', label: t('waxs.background.fillValue'), type: 'number', step: 'any' },
  { key: 'maskZeros', label: t('waxs.background.maskZeros'), type: 'checkbox' },
])

// ---- Merge params + per-image chi offset ----
const mergeParams = reactive({ mergeMethod: 'mean', maskLowerBound: null })
const mergeFields = computed(() => [
  {
    key: 'mergeMethod', label: t('waxs.merge.mergeMethod'), type: 'select',
    options: [
      { value: 'mean', label: t('waxs.merge.methodOptions.mean') },
      { value: 'median', label: t('waxs.merge.methodOptions.median') },
      { value: 'weighted', label: t('waxs.merge.methodOptions.weighted') },
      { value: 'sequential', label: t('waxs.merge.methodOptions.sequential') },
    ],
  },
  {
    key: 'maskLowerBound', label: t('waxs.merge.maskLowerBound'), type: 'number',
    step: 'any', placeholder: t('waxs.merge.maskLowerBoundPlaceholder'),
    help: t('waxs.merge.maskLowerBoundHelp'),
  },
])
const chiOffsets = ref([])                 // per-image chi offset (deg), aligned with batchItems

// ---- Step log: every merge/background run appends one record. ----
// Each record: { id, kind, mode?, title, sourceLabel, params,
//                items:[{fileId,name,preview,min,max}],
//                qArrayFileId?, chiArrayFileId?, info? }
const stepLog = ref([])
let stepSeq = 0
const mergeCount = computed(() => stepLog.value.filter((s) => s.kind === 'merge').length)
const bgCount = computed(() => stepLog.value.filter((s) => s.kind === 'background').length)

const lastMergeStep = computed(() => {
  for (let i = stepLog.value.length - 1; i >= 0; i--) if (stepLog.value[i].kind === 'merge') return stepLog.value[i]
  return null
})
const lastPerItemBgStep = computed(() => {
  for (let i = stepLog.value.length - 1; i >= 0; i--) {
    const s = stepLog.value[i]
    if (s.kind === 'background' && s.mode === 'perItem') return s
  }
  return null
})
const lastBgStep = computed(() => {
  for (let i = stepLog.value.length - 1; i >= 0; i--) if (stepLog.value[i].kind === 'background') return stepLog.value[i]
  return null
})
const perItemBgAvailable = computed(() => !!(lastPerItemBgStep.value && lastPerItemBgStep.value.items.length))

// ---- Two independent input-source toggles (the two steps can consume each other) ----
const useBgForMerge = ref(false)           // merge input = per-image bg results vs original
const useMergeForBg = ref(false)          // background input = merge result vs original (per-image)
const effectiveUseBgForMerge = computed(() => useBgForMerge.value && perItemBgAvailable.value)
const effectiveUseMergeForBg = computed(() => useMergeForBg.value && !!lastMergeStep.value)
const mergeSourceLabel = computed(() =>
  effectiveUseBgForMerge.value ? t('waxs.merge.sourceBg') : t('waxs.merge.sourceOriginal'))
const bgSourceLabel = computed(() =>
  effectiveUseMergeForBg.value ? t('waxs.background.sourceMerge') : t('waxs.background.sourceOriginalPerItem'))

// ---- Viewed step per tab (null = latest of that kind) ----
const viewedMergeId = ref(null)
const viewedBgId = ref(null)
const mergeSteps = computed(() => stepLog.value.filter((s) => s.kind === 'merge').slice().reverse())
const bgSteps = computed(() => stepLog.value.filter((s) => s.kind === 'background').slice().reverse())
const currentMergeStep = computed(() => {
  if (viewedMergeId.value != null) {
    const found = stepLog.value.find((s) => s.id === viewedMergeId.value)
    if (found) return found
  }
  return lastMergeStep.value
})
const currentBgStep = computed(() => {
  if (viewedBgId.value != null) {
    const found = stepLog.value.find((s) => s.id === viewedBgId.value)
    if (found) return found
  }
  return lastBgStep.value
})

// Per-image selection inside the current background step.
const bgCurrentIdx = ref(0)
const currentBgItem = computed(() => {
  const s = currentBgStep.value
  if (!s || !s.items.length) return null
  const idx = Math.min(Math.max(bgCurrentIdx.value, 0), s.items.length - 1)
  return s.items[idx]
})
const showBgThumbs = computed(() => {
  const s = currentBgStep.value
  return !!(s && s.mode === 'perItem' && s.items.length > 1)
})

// ---- Contrast windows (display-only) ----
const mergeContrastMin = ref(null)
const mergeContrastMax = ref(null)
const mergeFloor = computed(() => {
  const it = currentMergeStep.value && currentMergeStep.value.items[0]
  return it && it.min != null ? Math.min(it.min, it.max) : 0
})
const mergeCeil = computed(() => {
  const it = currentMergeStep.value && currentMergeStep.value.items[0]
  return it && it.min != null ? Math.max(it.min, it.max) : 1
})
const mergeStepC = computed(() => {
  const s = mergeCeil.value - mergeFloor.value
  return s !== 0 ? Math.abs(s) / 200 : 0.001
})
function resetMergeContrast() {
  const it = currentMergeStep.value && currentMergeStep.value.items[0]
  if (!it) return
  mergeContrastMin.value = it.min
  mergeContrastMax.value = it.max
}

const bgContrastMin = ref(null)
const bgContrastMax = ref(null)
const bgFloor = computed(() =>
  currentBgItem.value && currentBgItem.value.min != null
    ? Math.min(currentBgItem.value.min, currentBgItem.value.max) : 0)
const bgCeil = computed(() =>
  currentBgItem.value && currentBgItem.value.min != null
    ? Math.max(currentBgItem.value.min, currentBgItem.value.max) : 1)
const bgStep = computed(() => {
  const s = bgCeil.value - bgFloor.value
  return s !== 0 ? Math.abs(s) / 200 : 0.001
})
function resetBgContrast() {
  const it = currentBgItem.value
  if (!it) return
  bgContrastMin.value = it.min
  bgContrastMax.value = it.max
}

const consoleLogs = reactive({ import: [], background: [], merge: [] })

// ---- Helpers ----
function parseProcessingInfoTxt(text) {
  const info = {}
  const num = '-?[\\d.eE+-]+'
  const mx = text.match(new RegExp(`X-axis\\s*\\(([^)]*)\\)\\s*range:\\s*(${num})\\s+to\\s*(${num})`))
  if (mx) {
    info.xAxisUnit = mx[1].trim()
    info.xAxisRange = [parseFloat(mx[2]), parseFloat(mx[3])]
  }
  const my = text.match(new RegExp(`Y-axis\\s*\\(chi\\)\\s*range\\s*\\(degrees\\):\\s*(${num})\\s+to\\s*(${num})`))
  if (my) info.yAxisRangeDeg = [parseFloat(my[1]), parseFloat(my[2])]
  const mp = text.match(/Integration points[^:]*:\s*(\d+)\s*[x×]\s*(\d+)/)
  if (mp) info.integrationPoints = { radial: parseInt(mp[1]), azimuthal: parseInt(mp[2]) }
  return info
}
// Map a parsed processing_info object (JSON or .txt) onto the canonical keys the
// table and merge endpoint expect, tolerating snake_case / nested wrappers / a
// few common alias names. Returns null when no recognized field is present, so
// the UI can warn instead of silently showing placeholders everywhere.
const INFO_KEY_ALIASES = {
  xAxisRange: ['xAxisRange', 'x_range', 'xRange', 'qRange', 'qxRange', 'q_range'],
  yAxisRangeDeg: ['yAxisRangeDeg', 'y_range_deg', 'yRangeDeg', 'chiRange', 'chiRangeDeg', 'chi_range_deg', 'y_range'],
  integrationPoints: ['integrationPoints', 'integration_points', 'npt', 'points', 'nPoints'],
  polarizationFactor: ['polarizationFactor', 'polarization_factor', 'polarization', 'polarisationFactor'],
  xAxisUnit: ['xAxisUnit', 'x_axis_unit', 'xUnit', 'unit'],
}
function normalizeInfo(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  let o = raw
  for (const k of ['processing_info', 'processingInfo', 'info', 'metadata', 'data']) {
    if (o[k] && typeof o[k] === 'object' && !Array.isArray(o[k])) { o = o[k]; break }
  }
  const out = {}
  for (const [canon, aliases] of Object.entries(INFO_KEY_ALIASES)) {
    for (const n of aliases) {
      if (o[n] !== undefined && o[n] !== null) { out[canon] = o[n]; break }
    }
  }
  if (out.integrationPoints != null) {
    const ip = out.integrationPoints
    if (typeof ip === 'number') {
      out.integrationPoints = { radial: ip, azimuthal: ip }
    } else if (ip && typeof ip === 'object') {
      const radial = ip.radial ?? ip.nptRadial ?? ip.npt_radial ?? ip.radialPoints
      const azimuthal = ip.azimuthal ?? ip.nptAzimuthal ?? ip.npt_azimuthal ?? ip.azimuthalPoints
      if (radial != null || azimuthal != null) out.integrationPoints = { radial, azimuthal }
      else delete out.integrationPoints
    } else {
      delete out.integrationPoints
    }
  }
  return Object.keys(out).length ? out : null
}
function fmtRange(rng, suffix = '') {
  if (!Array.isArray(rng) || rng.length !== 2) return t('waxs.batchImport.noInfo')
  return `${rng[0]} ~ ${rng[1]}${suffix}`
}
function fmtPoints(pts) {
  if (!pts || pts.radial == null) return t('waxs.batchImport.noInfo')
  return `${pts.radial} × ${pts.azimuthal}`
}
function fmtScalar(v) {
  return v == null ? t('waxs.batchImport.noInfo') : v
}
function formatNum(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const abs = Math.abs(v)
  if (abs !== 0 && (abs < 1e-3 || abs >= 1e5)) return v.toExponential(3)
  return Number(v.toPrecision(5)).toString()
}
function formatStepParams(s) {
  if (s.kind === 'merge') {
    return `${s.params.mergeMethod} · ${s.params.fileCount} img`
  }
  const p = s.params
  return `r=${p.ballRadius} · ${p.rollingBallType} · ${p.method}` + (p.smoothingSigma ? ` · σ=${p.smoothingSigma}` : '')
}
function setChiOffset(i, raw) {
  const v = parseFloat(raw)
  chiOffsets.value[i] = Number.isFinite(v) ? v : 0
}

// ---- Result thumbnails (lightweight <canvas>) ----
// Each item's full preview array is box-averaged down to a small buffer ONCE
// and cached (keyed by fileId). Redraws only scan that tiny buffer, so dragging
// the contrast slider stays smooth even with several cakes. The contrast window
// [lo, hi] is applied at draw time so thumbs track the slider live.
const bgThumbRefs = ref([])
function setBgThumbRef(el, i) {
  if (el) bgThumbRefs.value[i] = el
}
const VIRIDIS_STOPS = [
  [68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]
]
function viridis(t) {
  const x = Math.max(0, Math.min(1, t))
  const s = x * (VIRIDIS_STOPS.length - 1)
  const i = Math.floor(s)
  const f = s - i
  const a = VIRIDIS_STOPS[i]
  const b = VIRIDIS_STOPS[Math.min(i + 1, VIRIDIS_STOPS.length - 1)]
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]
}

const THUMB_MAX_SIDE = 256          // downsample target; caps redraw cost
const thumbBufCache = new Map()     // fileId -> { rows, cols, data: Float32Array, min, max }

function downsampleAvg(src, rows, cols, maxSide) {
  const scale = Math.min(1, maxSide / Math.max(rows, cols))
  if (scale >= 0.999) {
    const flat = new Float32Array(rows * cols)
    let mn = Infinity, mx = -Infinity
    for (let r = 0; r < rows; r++) {
      const row = src[r]
      for (let c = 0; c < cols; c++) {
        const v = row[c]
        flat[r * cols + c] = v
        if (Number.isFinite(v)) { if (v < mn) mn = v; if (v > mx) mx = v }
      }
    }
    return { rows, cols, data: flat, min: mn, max: mx }
  }
  const nr = Math.max(1, Math.round(rows * scale))
  const nc = Math.max(1, Math.round(cols * scale))
  const out = new Float32Array(nr * nc)
  let mn = Infinity, mx = -Infinity
  for (let or = 0; or < nr; or++) {
    const r0 = Math.floor((or * rows) / nr)
    const r1 = Math.max(r0 + 1, Math.floor(((or + 1) * rows) / nr))
    for (let oc = 0; oc < nc; oc++) {
      const c0 = Math.floor((oc * cols) / nc)
      const c1 = Math.max(c0 + 1, Math.floor(((oc + 1) * cols) / nc))
      let sum = 0, cnt = 0
      for (let r = r0; r < r1; r++) {
        const row = src[r]
        for (let c = c0; c < c1; c++) {
          const v = row[c]
          if (Number.isFinite(v)) { sum += v; cnt++ }
        }
      }
      const v = cnt ? sum / cnt : 0
      out[or * nc + oc] = v
      if (Number.isFinite(v)) { if (v < mn) mn = v; if (v > mx) mx = v }
    }
  }
  return { rows: nr, cols: nc, data: out, min: mn, max: mx }
}
function getThumbBuffer(it) {
  if (!it || !it.fileId || !it.preview || !it.preview.length) return null
  const cached = thumbBufCache.get(it.fileId)
  if (cached) return cached
  const buf = downsampleAvg(it.preview, it.preview.length, it.preview[0].length, THUMB_MAX_SIDE)
  thumbBufCache.set(it.fileId, buf)
  return buf
}
function drawThumb(canvas, buf, lo, hi) {
  if (!canvas || !buf) return
  // Fall back to the buffer's own min/max when no contrast window is set yet.
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) { lo = buf.min; hi = buf.max }
  const { rows, cols, data } = buf
  const span = hi > lo ? hi - lo : Math.abs(hi) || 1
  const off = document.createElement('canvas')
  off.width = cols
  off.height = rows
  const octx = off.getContext('2d')
  const imgData = octx.createImageData(cols, rows)
  for (let i = 0; i < data.length; i++) {
    const v = data[i]
    let tn = Number.isFinite(v) ? (v - lo) / span : 0
    if (tn < 0) tn = 0
    else if (tn > 1) tn = 1
    const col = viridis(tn)
    const idx = i * 4
    imgData.data[idx] = col[0]
    imgData.data[idx + 1] = col[1]
    imgData.data[idx + 2] = col[2]
    imgData.data[idx + 3] = 255
  }
  octx.putImageData(imgData, 0, 0)
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.imageSmoothingEnabled = true
  ctx.drawImage(off, 0, 0, canvas.width, canvas.height)
}
function renderBgThumbs() {
  const s = currentBgStep.value
  if (!s) return
  const lo = bgContrastMin.value
  const hi = bgContrastMax.value
  s.items.forEach((it, i) => drawThumb(bgThumbRefs.value[i], getThumbBuffer(it), lo, hi))
}

// ---- Handlers ----
function onDataFiles(files) {
  dataFiles.value = files
}

async function onInfoFile(files) {
  const f = files && files[0]
  sharedInfo.value = null
  if (!f) {
    infoParseStatus.value = { state: 'none', keys: [], source: '', message: '' }
    batchItems.value.forEach((it) => (it.info = null))
    return
  }
  try {
    const text = await f.text()
    const lower = (f.name || '').toLowerCase()
    let raw = null
    if (lower.endsWith('.json')) {
      raw = JSON.parse(text)
    } else {
      try { raw = JSON.parse(text) } catch { raw = parseProcessingInfoTxt(text) }
    }
    const info = normalizeInfo(raw)
    sharedInfo.value = info
    if (info) {
      infoParseStatus.value = { state: 'ok', keys: Object.keys(info), source: f.name, message: '' }
    } else {
      infoParseStatus.value = { state: 'empty', keys: [], source: f.name, message: '' }
    }
    // eslint-disable-next-line no-console
    console.log('[processing_info]', f.name, '→', info)
    batchItems.value.forEach((it) => (it.info = sharedInfo.value))
  } catch (err) {
    console.error('[info parse]', f.name, err)
    sharedInfo.value = null
    infoParseStatus.value = { state: 'error', keys: [], source: f.name, message: err.message || String(err) }
  }
}

async function runBatchUpload() {
  if (!dataFiles.value.length) return
  runStatus.value = 'running'
  consoleLogs.import = [t('status.loading')]
  try {
    const fd = new FormData()
    dataFiles.value.forEach((f) => fd.append('files', f))
    const res = await waxsUploadFiles(fd)
    const files = res.data?.files || []
    batchItems.value = files.map((f) => ({
      fileId: f.fileId,
      name: f.originalName || f.fileId,
      info: sharedInfo.value || null,
    }))
    chiOffsets.value = batchItems.value.map(() => 0)
    consoleLogs.import.push(t('waxs.batchImport.loaded', { n: batchItems.value.length }))
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs.import.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    runStatus.value = 'failed'
  }
}

async function runMerge() {
  if (!batchItems.value.length) return
  runStatus.value = 'running'
  consoleLogs.merge = [t('logs.waxs.starting', { step: t('waxs.tabs.merge') })]
  try {
    const useBg = effectiveUseBgForMerge.value
    const sourceItems = useBg ? lastPerItemBgStep.value.items : batchItems.value
    const fileIds = sourceItems.map((i) => i.fileId)
    // fileInfos + chiOffsets always stay aligned to batchItems (per-item bg mirrors that order).
    const fileInfos = batchItems.value.map((i) => i.info || {})
    const offsets = chiOffsets.value.slice(0, batchItems.value.length)
    const res = await waxsRunMerge({
      fileIds,
      fileInfos,
      chiOffsets: offsets,
      mergeMethod: mergeParams.mergeMethod,
      maskLowerBound: mergeParams.maskLowerBound,
    })
    const data = res.data || {}
    const mergedFileId = data.mergedFileId
    let preview = null
    let mn = null
    let mx = null
    if (mergedFileId) {
      const img = await integrationGetImage(mergedFileId)
      preview = img.data?.preview || null
      mn = img.data?.min ?? null
      mx = img.data?.max ?? null
    }
    stepSeq += 1
    stepLog.value.push({
      id: stepSeq,
      kind: 'merge',
      title: t('waxs.merge.stepMerge', { n: mergeCount.value + 1 }),
      sourceLabel: mergeSourceLabel.value,
      params: { mergeMethod: mergeParams.mergeMethod, maskLowerBound: mergeParams.maskLowerBound, fileCount: fileIds.length },
      items: [{ fileId: mergedFileId, name: 'merged', preview, min: mn, max: mx }],
      qArrayFileId: data.qArrayFileId || null,
      chiArrayFileId: data.chiArrayFileId || null,
      info: data.info || {},
    })
    viewedMergeId.value = null
    consoleLogs.merge.push(t('logs.waxs.stepCompleted', { step: t('waxs.tabs.merge') }))
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs.merge.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    runStatus.value = 'failed'
  }
}

async function runBackground() {
  const onMerge = effectiveUseMergeForBg.value
  if (!onMerge && !batchItems.value.length) return
  runStatus.value = 'running'
  consoleLogs.background = [t('logs.waxs.starting', { step: t('waxs.tabs.background') })]
  try {
    const params = {
      ballRadius: backgroundParams.ballRadius,
      rollingBallType: backgroundParams.rollingBallType,
      method: backgroundParams.method,
      smoothingSigma: backgroundParams.smoothingSigma,
      fillValue: backgroundParams.fillValue,
      maskZeros: backgroundParams.maskZeros,
    }
    const items = []
    if (onMerge) {
      const m = lastMergeStep.value
      const res = await waxsRunBackground({ fileId: m.items[0].fileId, ...params })
      const sig = res.data?.signalFileId
      const img = await integrationGetImage(sig)
      items.push({
        fileId: sig,
        name: t('waxs.background.sourceMerge'),
        preview: img.data?.preview || null,
        min: img.data?.min ?? null,
        max: img.data?.max ?? null,
      })
      consoleLogs.background.push(`✓ ${items[0].name}`)
    } else {
      for (const b of batchItems.value) {
        const res = await waxsRunBackground({ fileId: b.fileId, ...params })
        const sig = res.data?.signalFileId
        const img = await integrationGetImage(sig)
        items.push({
          fileId: sig,
          name: b.name,
          preview: img.data?.preview || null,
          min: img.data?.min ?? null,
          max: img.data?.max ?? null,
        })
        consoleLogs.background.push(`✓ ${b.name}`)
      }
    }
    stepSeq += 1
    stepLog.value.push({
      id: stepSeq,
      kind: 'background',
      mode: onMerge ? 'onMerge' : 'perItem',
      title: t('waxs.background.stepBackground', { n: bgCount.value + 1 }),
      sourceLabel: bgSourceLabel.value,
      params: { ...params },
      items,
    })
    viewedBgId.value = null
    bgCurrentIdx.value = 0
    consoleLogs.background.push(t('logs.waxs.stepCompleted', { step: t('waxs.tabs.background') }))
    runStatus.value = 'completed'
    await nextTick()
    renderBgThumbs()
  } catch (err) {
    consoleLogs.background.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    runStatus.value = 'failed'
  }
}

// ---- Export (single step or all steps) ----
// Under Electron, `<a download>.click()` throws "An object could not be cloned"
// (the click is intercepted and the DOM Blob is marshalled through IPC, which
// the structured-clone algorithm rejects). saveBlob routes through the native
// save dialog (base64 data: URL) under Electron and falls back to <a download>
// in a plain browser.
async function downloadBlob(blob, filename) {
  await saveBlob(blob, filename)
}
function stepToExportItem(s) {
  return {
    kind: s.kind,
    imageFileIds: s.items.map((i) => i.fileId),
    qArrayFileId: s.qArrayFileId || null,
    chiArrayFileId: s.chiArrayFileId || null,
    info: s.info || {},
    label: `step_${String(s.id).padStart(2, '0')}_${s.kind}`,
  }
}
async function exportStep(step) {
  if (!step) return
  const log = step.kind === 'merge' ? consoleLogs.merge : consoleLogs.background
  try {
    const item = stepToExportItem(step)
    const res = await waxsStepsExport({ steps: [item], baseName: item.label })
    await downloadBlob(res.data, `${item.label}.zip`)
    log.push(t('waxs.merge.exportedStep'))
  } catch (err) {
    log.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}
async function exportAllSteps() {
  if (!stepLog.value.length) return
  try {
    const steps = stepLog.value.map(stepToExportItem)
    const res = await waxsStepsExport({ steps, baseName: 'polymcrystrefine_all_steps' })
    await downloadBlob(res.data, 'polymcrystrefine_all_steps.zip')
    consoleLogs.merge.push(t('waxs.merge.exportedAll', { n: steps.length }))
  } catch (err) {
    consoleLogs.merge.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}

function viewMerge(id) { viewedMergeId.value = id }
function viewBg(id) { viewedBgId.value = id }

// Snap contrast windows when the viewed step / image changes.
watch(currentMergeStep, (s) => {
  const it = s && s.items[0]
  if (it && it.min != null) {
    mergeContrastMin.value = it.min
    mergeContrastMax.value = it.max
  }
})
watch([currentBgStep, bgCurrentIdx], () => {
  const it = currentBgItem.value
  if (it && it.min != null) {
    bgContrastMin.value = it.min
    bgContrastMax.value = it.max
  }
  if (showBgThumbs.value) nextTick(renderBgThumbs)
})

// Live thumbnail redraw as the user drags the background contrast slider —
// thumbs share the same contrast window as the big image.
watch([bgContrastMin, bgContrastMax], () => {
  if (showBgThumbs.value) renderBgThumbs()
})

// Thumbnail canvases are recreated when (re)entering the background tab or
// switching the viewed background step — redraw them then.
watch(activeTab, async (tab) => {
  if (tab === 'background' && showBgThumbs.value) {
    await nextTick()
    renderBgThumbs()
  }
})
</script>

<style scoped>
.waxs-page {
  display: flex;
  flex-direction: column;
}

.main-container {
  display: flex;
  flex: 1;
}

/* ---- Sidebar ---- */
.sidebar {
  width: var(--sidebar-width, 240px);
  background: var(--color-neutral);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: calc(100vh - var(--header-height, 56px));
  align-self: flex-start;
}

.tab-nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 36px;
  padding: 0 14px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 13px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
  white-space: nowrap;
}

.tab-item:hover {
  background: var(--color-surface);
  color: var(--color-text);
}

.tab-item.active {
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
  color: var(--color-text);
}

.tab-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--color-primary);
  border-radius: 0 2px 2px 0;
}

.tab-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.tab-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--color-surface);
  border-radius: 6px;
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-secondary);
}

.status-dot.running {
  background: var(--color-warning);
  animation: pulse 2s infinite;
}

.status-dot.success {
  background: var(--color-success);
}

.status-dot.error {
  background: var(--color-error);
}

.status-text {
  color: var(--color-text-secondary);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ---- Content ---- */
.content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  min-width: 0;
}

.tab-panel {
  max-width: 1000px;
}

.card {
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

.json-block {
  margin-top: 12px;
}

.json-parsed {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--color-primary);
}
.json-parsed--warn {
  color: var(--color-warning, #d97706);
}

/* Buttons */
.btn-primary {
  height: 38px;
  padding: 0 24px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  font-family: 'Inter', system-ui, sans-serif;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-primary:hover { opacity: 0.9; }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-secondary {
  height: 38px;
  padding: 0 22px;
  background: transparent;
  color: var(--color-primary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  font-family: 'Inter', system-ui, sans-serif;
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s;
}
.btn-secondary:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--primary-bg);
}
.btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-sm {
  height: 30px;
  padding: 0 14px;
  font-size: 12px;
  align-self: flex-start;
}

.btn-link {
  background: transparent;
  border: none;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
}
.btn-link:hover {
  background: var(--color-primary-10, rgba(124, 58, 237, 0.10));
}

.param-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.loaded-count {
  font-size: 12px;
  color: var(--color-success);
  font-weight: 600;
}

.hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* Input source toggle */
.forward-toggle {
  margin-top: 4px;
  margin-bottom: 18px;
  padding: 14px 16px;
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.forward-toggle__switch {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  user-select: none;
}
.forward-toggle__switch--disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.forward-toggle__switch input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}
.forward-toggle__track {
  position: relative;
  width: 40px;
  height: 22px;
  background: var(--color-border);
  border-radius: 11px;
  transition: background-color 150ms ease;
  flex-shrink: 0;
}
.forward-toggle__switch--on .forward-toggle__track {
  background: var(--color-primary);
}
.forward-toggle__thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  background: #FFFFFF;
  border-radius: 50%;
  transition: transform 150ms ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.10);
}
.forward-toggle__switch--on .forward-toggle__thumb {
  transform: translateX(18px);
}
.forward-toggle__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}
.forward-toggle__status {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.status-chip {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}
.status-chip--bg {
  background: var(--color-primary-10, rgba(124, 58, 237, 0.12));
  color: var(--color-primary);
}
.status-chip--orig {
  background: var(--color-surface-hover, rgba(0, 0, 0, 0.05));
  color: var(--color-text-secondary);
}

/* Chi offset table */
.chi-offset-wrap { margin-top: 18px; }
.chi-offset-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 10px;
}
.chi-input {
  width: 110px;
  padding: 6px 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: var(--color-text);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  outline: none;
  box-sizing: border-box;
}
.chi-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.2);
}

/* Result block (big image + contrast) */
.result-block { margin-top: 18px; }
.result-empty {
  margin-top: 18px;
  padding: 28px;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary);
  border: 1px dashed var(--color-border);
  border-radius: 8px;
}
.contrast-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
  padding: 12px;
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 8px;
}
.contrast-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.contrast-field label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
}
.contrast-field input[type="range"] {
  width: 100%;
  accent-color: var(--color-primary);
}

.thumbs-block { margin-top: 16px; }
.thumbs-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 8px;
}
.thumbs-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px;
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 8px;
}
.thumb {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 116px;
  padding: 5px;
  border: 2px solid transparent;
  border-radius: 6px;
  background: var(--color-surface);
  cursor: pointer;
  transition: border-color 0.15s;
}
.thumb:hover { border-color: var(--border-hover, var(--color-border)); }
.thumb.active { border-color: var(--color-primary); }
.thumb__canvas {
  width: 104px;
  height: 104px;
  display: block;
  border-radius: 4px;
  background: #1a1a2e;
  image-rendering: auto;
}
.thumb__name {
  font-size: 11px;
  color: var(--color-text-secondary);
  font-family: 'JetBrains Mono', monospace;
  max-width: 104px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: center;
}

/* Step history */
.history { margin-top: 22px; }
.history__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 10px;
}
.history__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 8px;
  background: var(--color-surface);
  transition: border-color 0.15s, background-color 0.15s;
}
.history__row--active {
  border-color: var(--color-primary);
  background: var(--color-primary-10, rgba(124, 58, 237, 0.06));
}
.history__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.history__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}
.history__meta {
  font-size: 11px;
  color: var(--color-text-secondary);
  font-family: 'JetBrains Mono', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history__actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

/* Mini console */
.mini-console {
  margin-top: 4px;
  padding: 10px 12px;
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--color-text-secondary);
  max-height: 180px;
  overflow-y: auto;
}
.mini-console__line {
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* File info table */
.info-table-wrap { margin-top: 24px; }
.info-table-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 10px;
}
.info-table-scroll {
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}
.info-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.info-table th,
.info-table td {
  padding: 9px 12px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
.info-table thead th {
  background: var(--color-neutral);
  color: var(--color-text-secondary);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.info-table tbody tr:last-child td { border-bottom: none; }
.info-table tbody tr:hover td { background: var(--color-surface-hover); }
.cell-file {
  font-weight: 500;
  color: var(--color-text);
}
.bg-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--color-primary-10, rgba(124, 58, 237, 0.12));
  color: var(--color-primary);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

/* Fade transition */
.fade-enter-active,
.fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from,
.fade-leave-to { opacity: 0; }

@media (max-width: 1024px) {
  .sidebar { width: 72px; }
  .tab-label,
  .sidebar-footer { display: none; }
  .tab-item { justify-content: center; padding: 0; gap: 0; }
  .tab-item.active::before { display: none; }
}
</style>
