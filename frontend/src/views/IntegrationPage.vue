<template>
  <div class="integration-page">
    <header class="page-head">
      <div class="page-head__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <line x1="3" y1="9" x2="21" y2="9" />
          <line x1="9" y1="21" x2="9" y2="9" />
        </svg>
      </div>
      <div class="page-head__copy">
        <h2 class="page-head__title">{{ t('integration.title') }}</h2>
        <p class="page-head__desc">{{ t('integration.header') }}</p>
      </div>
    </header>

    <div class="integration-grid">
      <!-- ============ Input column ============ -->
      <section class="panel panel--input">
        <!-- Mode toggle: detector (raw image + PONI) vs cake (pre-integrated .npy) -->
        <div class="seg seg--mode">
          <button
            v-for="m in ['detector', 'cake']"
            :key="m"
            :class="['seg__btn', { active: mode === m }]"
            @click="mode = m"
          >{{ t('integration.tabs.' + m) }}</button>
        </div>

        <!-- Input files -->
        <div class="section">
          <div class="section__head">
            <h3>{{ t('integration.detector.title') }}</h3>
            <span class="section__hint">{{ t('integration.detector.desc') }}</span>
          </div>

          <div class="upload-grid">
            <div class="upload-slot">
              <label class="slot-label">
                {{ mode === 'cake' ? t('integration.cake.imageLabel') : t('integration.detector.imageLabel') }}
              </label>
              <FileUpload
                :multiple="true"
                accept=".npy,.edf,.tif,.tiff,.h5"
                @files-selected="(fs) => onImageSelected(fs)"
              />
              <div v-if="imageFiles.length" class="file-chip-list">
                <span class="file-chip-count">{{ t('integration.detector.imageCount', { n: imageFiles.length }) }}</span>
                <div v-for="(f, i) in imageFiles" :key="f.fileId" class="file-chip">
                  <span class="file-chip__name" :title="f.name">{{ f.name }}</span>
                  <button class="file-chip__x" :title="t('integration.detector.removeOne')" @click="removeImage(i)">×</button>
                </div>
                <button class="file-chip-clear" @click="clearImages">{{ t('integration.detector.clearAll') }}</button>
              </div>
            </div>

            <div v-if="mode === 'detector'" class="upload-slot">
              <label class="slot-label">{{ t('integration.detector.poniLabel') }}</label>
              <FileUpload
                :multiple="false"
                accept=".poni"
                @files-selected="(fs) => onPoniSelected(fs)"
              />
              <div v-if="poniFile" class="file-chip">
                <span class="file-chip__name">{{ poniFile.name }}</span>
                <button class="file-chip__x" @click="clearPoni">×</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Cake axis ranges (cake mode only) — q/chi extents + optional
             processing_info import to auto-fill them. Mirrors what
             reference/function3 reads from processing_info.txt automatically. -->
        <div v-if="mode === 'cake'" class="section">
          <div class="section__head">
            <h3>{{ t('integration.cake.title') }}</h3>
            <span class="section__hint">{{ t('integration.cake.desc') }}</span>
          </div>
          <div class="cake-info-row">
            <FileUpload
              :multiple="false"
              accept=".json,.txt"
              @files-selected="(fs) => onCakeInfoSelected(fs)"
            />
            <span v-if="cakeInfoName" class="file-chip"><span class="file-chip__name">{{ cakeInfoName }}</span></span>
          </div>
          <div class="axis-grid axis-grid--4">
            <div class="field">
              <label>{{ t('integration.cake.qMin') }}</label>
              <input type="number" step="any" v-model.number="cakeQMin" />
            </div>
            <div class="field">
              <label>{{ t('integration.cake.qMax') }}</label>
              <input type="number" step="any" v-model.number="cakeQMax" />
            </div>
            <div class="field">
              <label>{{ t('integration.cake.chiMin') }}</label>
              <input type="number" step="any" v-model.number="cakeChiMin" />
            </div>
            <div class="field">
              <label>{{ t('integration.cake.chiMax') }}</label>
              <input type="number" step="any" v-model.number="cakeChiMax" />
            </div>
            <div class="field">
              <label>{{ t('integration.cake.unit') }}</label>
              <select v-model="cakeUnit">
                <option v-for="u in unitOptions" :key="u.value" :value="u.value">{{ u.label }}</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Mask settings -->
        <div class="section">
          <div class="section__head">
            <h3>{{ t('integration.mask.title') }}</h3>
            <span class="section__hint">{{ t('integration.mask.desc') }}</span>
          </div>

          <div class="seg">
            <button
              v-for="m in ['auto', 'manual']"
              :key="m"
              :class="['seg__btn', { active: maskMode === m }]"
              @click="maskMode = m"
            >{{ t('integration.mask.' + m) }}</button>
          </div>

          <div v-if="maskMode === 'auto'" class="mask-auto">
            <div class="field field--slider">
              <label>{{ t('integration.mask.lowPct') }} · {{ lowPct }}%</label>
              <input type="range" min="0" max="5" step="0.05" v-model.number="lowPct" />
            </div>
            <div class="field field--slider">
              <label>{{ t('integration.mask.highPct') }} · {{ (100 - highPct).toFixed(2) }}%</label>
              <input type="range" min="95" max="100" step="0.05" v-model.number="highPct" />
            </div>
            <button class="btn btn--ghost btn--sm" :disabled="!imageFiles.length || busy" @click="recalcThresholds">
              {{ t('integration.mask.recalc') }}
            </button>
            <div v-if="autoThresholds" class="auto-result">
              <span>min ≈ {{ formatNum(autoThresholds.min) }}</span>
              <span>max ≈ {{ formatNum(autoThresholds.max) }}</span>
            </div>
          </div>

          <div v-if="maskMode === 'manual'" class="axis-grid">
            <div class="field">
              <label>{{ t('integration.mask.min') }}</label>
              <input type="number" step="any" v-model.number="minThreshold" />
            </div>
            <div class="field">
              <label>{{ t('integration.mask.max') }}</label>
              <input type="number" step="any" v-model.number="maxThreshold" />
            </div>
          </div>

          <div class="upload-slot upload-slot--inline">
            <label class="slot-label">{{ t('integration.mask.customLabel') }}</label>
            <FileUpload :multiple="false" accept=".npy,.tif,.tiff,.edf" @files-selected="(fs) => onCustomMaskSelected(fs)" />
            <div v-if="customMask" class="file-chip">
              <span class="file-chip__name">{{ customMask.name }}</span>
              <button class="file-chip__x" @click="customMask = null">×</button>
            </div>
          </div>

          <div class="field field--inline">
            <label>{{ t('integration.mask.fillValue') }}</label>
            <input type="number" step="any" v-model.number="fillValue" />
          </div>
        </div>

        <!-- Integration params (detector mode only) -->
        <div v-if="mode === 'detector'" class="section">
          <div class="section__head">
            <h3>{{ t('integration.params.title') }}</h3>
          </div>
          <div class="axis-grid axis-grid--3">
            <div class="field">
              <label>{{ t('integration.params.nptRadial') }}</label>
              <input type="number" min="10" step="1" v-model.number="nptRadial" />
            </div>
            <div class="field">
              <label>{{ t('integration.params.nptAzimuthal') }}</label>
              <input type="number" min="10" step="1" v-model.number="nptAzimuthal" />
            </div>
            <div class="field">
              <label>{{ t('integration.params.unit') }}</label>
              <select v-model="unit">
                <option v-for="u in unitOptions" :key="u.value" :value="u.value">{{ u.label }}</option>
              </select>
            </div>
            <div class="field">
              <label>{{ t('integration.params.method') }}</label>
              <select v-model="method">
                <option v-for="m in methodOptions" :key="m" :value="m">{{ m }}</option>
              </select>
            </div>
            <div class="field">
              <label>{{ t('integration.params.polarization') }}</label>
              <input type="number" min="-0.5" max="1" step="0.01" v-model.number="polarizationFactor" />
            </div>
          </div>
        </div>

        <!-- Action bar -->
        <div class="action-bar">
          <button class="btn btn--primary" :disabled="!canRun || busy" @click="run">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5,3 19,12 5,21" /></svg>
            {{ t('integration.actions.run') }}
          </button>
          <button class="btn btn--ghost" @click="reset">{{ t('integration.actions.reset') }}</button>
        </div>
      </section>

      <!-- ============ Result column ============ -->
      <section class="panel panel--result">
        <div class="section__head">
          <h3>{{ t('integration.result.title') }}</h3>
          <div v-if="currentResult" class="stats">
            <span class="stat"><b>{{ t('integration.result.maskRatio') }}</b> {{ (currentResult.maskRatio * 100).toFixed(1) }}%</span>
            <span class="stat"><b>{{ t('integration.result.min') }}</b> {{ formatNum(currentResult.minIntensity) }}</span>
            <span class="stat"><b>{{ t('integration.result.max') }}</b> {{ formatNum(currentResult.maxIntensity) }}</span>
          </div>
        </div>

        <div v-if="currentResult" class="result-canvas">
          <ImageCanvas
            :image-data="currentResult.preview"
            :x-axis="currentResult.qAxis"
            :y-axis="currentResult.chiAxis"
            :title="`χ × ${currentResult.unit}`"
            :show-colorbar="false"
            :height="620"
            :zmin="contrastMin"
            :zmax="contrastMax"
            :aspect-ratio="'4 / 3'"
            :reference-line-y="refLineVisible ? refLineOffset : null"
          />
        </div>
        <div v-else class="result-empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
          <p>{{ busy ? t('integration.status.integrating') : t('integration.status.done').replace('。', '').replace('.', '') }}</p>
        </div>

        <div v-if="results.length > 1" class="result-thumbs">
          <div class="thumbs-label">{{ t('integration.result.thumbsTitle') }}</div>
          <div class="thumbs-row">
            <div
              v-for="(r, i) in results"
              :key="i"
              :class="['thumb', { active: i === currentIdx }]"
              :title="imageName(i)"
              @click="currentIdx = i"
            >
              <canvas :ref="(el) => setThumbRef(el, i)" class="thumb__canvas" width="120" height="120"></canvas>
              <span class="thumb__name">{{ imageName(i) }}</span>
            </div>
          </div>
        </div>

        <div v-if="results.length > 1" class="result-filelist">
          <table class="filelist-table">
            <thead>
              <tr>
                <th>#</th>
                <th>{{ t('integration.result.colFile') }}</th>
                <th>{{ t('integration.result.maskRatio') }}</th>
                <th>{{ t('integration.result.min') }}</th>
                <th>{{ t('integration.result.max') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(r, i) in results"
                :key="i"
                :class="{ active: i === currentIdx }"
                @click="currentIdx = i"
              >
                <td>{{ i + 1 }}</td>
                <td class="filelist-name" :title="imageName(i)">{{ imageName(i) }}</td>
                <td>{{ (r.maskRatio * 100).toFixed(1) }}%</td>
                <td>{{ formatNum(r.minIntensity) }}</td>
                <td>{{ formatNum(r.maxIntensity) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="currentResult" class="contrast-controls">
          <div class="field field--slider">
            <label>{{ t('integration.result.contrastMin') }} · {{ formatNum(contrastMin) }}</label>
            <input type="range" :min="contrastFloor" :max="contrastCeil" :step="contrastStep" v-model.number="contrastMin" />
          </div>
          <div class="field field--slider">
            <label>{{ t('integration.result.contrastMax') }} · {{ formatNum(contrastMax) }}</label>
            <input type="range" :min="contrastFloor" :max="contrastCeil" :step="contrastStep" v-model.number="contrastMax" />
          </div>
          <button class="btn btn--ghost btn--sm" @click="resetContrast">{{ t('integration.result.contrastReset') }}</button>
        </div>

        <div v-if="currentResult" class="contrast-controls">
          <div class="field">
            <label>{{ t('integration.result.refLine') }}</label>
            <button
              :class="['btn btn--ghost btn--sm', { 'btn--primary': refLineVisible }]"
              @click="refLineVisible = !refLineVisible"
            >{{ refLineVisible ? t('common.on') : t('common.off') }}</button>
          </div>
          <div class="field" v-if="refLineVisible">
            <label>{{ t('integration.result.refLineOffset') }} (°)</label>
            <input type="number" step="0.1" v-model.number="refLineOffset" />
          </div>
        </div>

        <div v-if="currentResult" class="result-actions">
          <button class="btn btn--accent" @click="exportZip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            {{ t('integration.actions.export') }}
          </button>
          <button v-if="results.length > 1" class="btn btn--accent" :disabled="busy" @click="exportAllZip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            {{ t('integration.actions.exportAll', { n: results.length }) }}
          </button>
        </div>
      </section>
    </div>

    <!-- Console -->
    <ConsolePanel :status="status" :logs="logs" @cancel="status = 'idle'" />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import FileUpload from '@/components/FileUpload.vue'
import ConsolePanel from '@/components/ConsolePanel.vue'
import ImageCanvas from '@/components/ImageCanvas.vue'
import {
  integrationUpload,
  integrationParsePoni,
  integrationParseInfo,
  integrationAutoThreshold,
  integrationRun,
  integrationExportZip,
  integrationExportBatchZip
} from '@/api'
import { saveBlob } from '@/services/download.js'

const { t } = useI18n()

// files
const imageFiles = ref([])
const poniFile = ref(null)
const poniParams = ref(null)
const customMask = ref(null)

// input mode: 'detector' (raw image + PONI → pyFAI integrate2d) or 'cake'
// (pre-integrated .npy → masking only). The backend supports both via
// RunRequest.mode; this toggle exposes the cake path the UI was missing.
const mode = ref('detector')

// cake-mode axis extents (applied to every loaded cake). Filled manually or
// auto-filled from a processing_info sidecar (onCakeInfoSelected).
const cakeQMin = ref(0)
const cakeQMax = ref(25)
const cakeChiMin = ref(-180)
const cakeChiMax = ref(180)
const cakeUnit = ref('q_A^-1')
const cakeInfoName = ref('')

// mask
const maskMode = ref('manual')
const lowPct = ref(0.1)
const highPct = ref(100)
const autoThresholds = ref(null)
const minThreshold = ref(null)
const maxThreshold = ref(null)
const fillValue = ref(0)

// integration
const nptRadial = ref(1000)
const nptAzimuthal = ref(360)
const unit = ref('2th_deg')
const method = ref('csr')
const polarizationFactor = ref(0.99)

// status / result
const status = ref('idle')
const logs = ref([])
const results = ref([])
const currentIdx = ref(0)
const currentResult = computed(() => results.value[currentIdx.value] || null)
const busy = computed(() => status.value === 'running')

// Contrast window for the result heatmap (display-only; does not affect integration).
const contrastMin = ref(null)
const contrastMax = ref(null)
const contrastFloor = computed(() =>
  currentResult.value ? Math.min(currentResult.value.minIntensity, currentResult.value.maxIntensity) : 0
)
const contrastCeil = computed(() =>
  currentResult.value ? Math.max(currentResult.value.minIntensity, currentResult.value.maxIntensity) : 1
)
const contrastStep = computed(() => {
  const span = contrastCeil.value - contrastFloor.value
  return span !== 0 ? Math.abs(span) / 200 : 0.001
})
function resetContrast() {
  if (!currentResult.value) return
  contrastMin.value = currentResult.value.minIntensity
  contrastMax.value = currentResult.value.maxIntensity
}

// Reference line at χ = 0° (equator) — toggle on/off with adjustable offset.
const refLineVisible = ref(false)
const refLineOffset = ref(0)

const unitOptions = [
  { value: 'q_nm^-1', label: 'q (nm⁻¹)' },
  { value: 'q_A^-1', label: 'q (Å⁻¹)' },
  { value: '2th_deg', label: '2θ (deg)' },
  { value: '2th_rad', label: '2θ (rad)' },
  { value: 'r_mm', label: 'r (mm)' }
]
const methodOptions = ['csr', 'bbox', 'splitpixel', 'numpy']

const canRun = computed(() =>
  mode.value === 'cake'
    ? imageFiles.value.length > 0
    : imageFiles.value.length > 0 && !!poniFile.value
)

function log(line) {
  logs.value.push(line)
}

function formatNum(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const abs = Math.abs(v)
  if (abs !== 0 && (abs < 1e-3 || abs >= 1e5)) return v.toExponential(3)
  return Number(v.toPrecision(5)).toString()
}

async function uploadSingle(files) {
  if (!files || !files.length) return null
  const fd = new FormData()
  fd.append('files', files[0])
  const res = await integrationUpload(fd)
  const f = res.data.files[0]
  return { fileId: f.fileId, name: f.originalName }
}

async function uploadAll(files) {
  if (!files || !files.length) return []
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const res = await integrationUpload(fd)
  return res.data.files.map(f => ({ fileId: f.fileId, name: f.originalName }))
}

async function onImageSelected(files) {
  try {
    imageFiles.value = await uploadAll(files)
    autoThresholds.value = null
    log(`Loaded ${imageFiles.value.length} image(s)`)
  } catch (e) {
    log(`Upload error: ${e.message || e}`)
  }
}

async function onPoniSelected(files) {
  try {
    const f = await uploadSingle(files)
    poniFile.value = f
    poniParams.value = null
    if (f) {
      const params = (await integrationParsePoni(f.fileId)).data
      poniParams.value = params
      log(`Parsed PONI: λ=${formatNum(params.wavelength)} nm, dist=${formatNum(params.dist)} m`)
    }
  } catch (e) {
    log(`PONI error: ${e.response?.data?.detail || e.message || e}`)
  }
}

async function onCustomMaskSelected(files) {
  try {
    customMask.value = await uploadSingle(files)
  } catch (e) {
    log(`Mask upload error: ${e.message || e}`)
  }
}

// Import a processing_info sidecar (.json / legacy .txt) to auto-fill the
// cake-mode axis extents. The backend returns q already converted to Å^-1.
async function onCakeInfoSelected(files) {
  if (!files || !files.length) return
  try {
    const fd = new FormData()
    fd.append('file', files[0])
    const r = (await integrationParseInfo(fd)).data || {}
    cakeInfoName.value = files[0].name
    let applied = false
    if (Array.isArray(r.qRange) && r.qRange.length === 2) {
      cakeQMin.value = r.qRange[0]; cakeQMax.value = r.qRange[1]; applied = true
    }
    if (Array.isArray(r.chiRange) && r.chiRange.length === 2) {
      cakeChiMin.value = r.chiRange[0]; cakeChiMax.value = r.chiRange[1]; applied = true
    }
    if (applied) cakeUnit.value = 'q_A^-1'   // parse-info always returns Å^-1
    log(applied ? t('integration.cake.infoApplied') : t('integration.cake.infoEmpty'))
  } catch (e) {
    log(`${t('integration.cake.infoError')}: ${e.response?.data?.detail || e.message || e}`)
  }
}

async function recalcThresholds() {
  const img = imageFiles.value[0]
  if (!img) return
  try {
    const r = (await integrationAutoThreshold({
      fileId: img.fileId,
      lowPct: lowPct.value,
      highPct: highPct.value
    })).data
    autoThresholds.value = r
    minThreshold.value = r.min
    maxThreshold.value = r.max
    log(`Auto thresholds: min=${formatNum(r.min)}, max=${formatNum(r.max)}`)
  } catch (e) {
    log(`Threshold error: ${e.response?.data?.detail || e.message || e}`)
  }
}

function removeImage(i) {
  imageFiles.value.splice(i, 1)
  results.value = []
  currentIdx.value = 0
}
function clearImages() {
  imageFiles.value = []
  results.value = []
  currentIdx.value = 0
  autoThresholds.value = null
}
function clearPoni() { poniFile.value = null; poniParams.value = null }

async function run() {
  if (!canRun.value) return
  status.value = 'running'
  results.value = []
  currentIdx.value = 0
  log(t('integration.status.integrating'))
  try {
    const base = mode.value === 'cake'
      ? {
          mode: 'cake',
          // no PONI / npt — the cake is already integrated; we only mask + tag axes
          qMin: cakeQMin.value,
          qMax: cakeQMax.value,
          chiMin: cakeChiMin.value,
          chiMax: cakeChiMax.value,
          unit: cakeUnit.value,
          maskMode: maskMode.value,
          lowPct: lowPct.value,
          highPct: highPct.value,
          minThreshold: maskMode.value === 'manual' ? minThreshold.value : null,
          maxThreshold: maskMode.value === 'manual' ? maxThreshold.value : null,
          customMaskFileId: customMask.value?.fileId || null,
          fillValue: fillValue.value
        }
      : {
          mode: 'detector',
          poniFileId: poniFile.value.fileId,
          maskMode: maskMode.value,
          lowPct: lowPct.value,
          highPct: highPct.value,
          minThreshold: maskMode.value === 'manual' ? minThreshold.value : null,
          maxThreshold: maskMode.value === 'manual' ? maxThreshold.value : null,
          customMaskFileId: customMask.value?.fileId || null,
          fillValue: fillValue.value,
          nptRadial: nptRadial.value,
          nptAzimuthal: nptAzimuthal.value,
          method: method.value,
          unit: unit.value,
          polarizationFactor: polarizationFactor.value
        }
    for (let i = 0; i < imageFiles.value.length; i++) {
      const img = imageFiles.value[i]
      log(`[${i + 1}/${imageFiles.value.length}] ${img.name}`)
      const res = (await integrationRun({ ...base, imageFileId: img.fileId })).data
      results.value.push(res)
    }
    currentIdx.value = 0
    const first = results.value[0]
    contrastMin.value = first.minIntensity
    contrastMax.value = first.maxIntensity
    status.value = 'completed'
    log(`${t('integration.status.done')} (${results.value.length} images, mask=${(first.maskRatio * 100).toFixed(1)}%)`)
  } catch (e) {
    status.value = 'error'
    log(`ERROR: ${e.response?.data?.detail || e.message || e}`)
  }
}

// Under Electron, `<a download>.click()` throws "An object could not be cloned"
// (the click is intercepted and the DOM Blob is marshalled through IPC, which
// the structured-clone algorithm rejects). saveBlob routes through the native
// save dialog (base64 data: URL) under Electron and falls back to <a download>
// in a plain browser.
async function downloadBlob(blob, filename) {
  await saveBlob(blob, filename)
}

async function exportZip() {
  const idx = currentIdx.value
  const r = currentResult.value
  if (!r) return
  try {
    log(t('integration.status.exporting'))
    // Name the archive after the source image so exporting several results
    // one by one doesn't overwrite the same file every time.
    const base = baseNameOf(idx)
    const blob = (await integrationExportZip({
      resultFileId: r.resultFileId,
      qArrayFileId: r.qArrayFileId,
      chiArrayFileId: r.chiArrayFileId,
      unit: r.unit,
      mode: mode.value,
      nptRadial: mode.value === 'detector' ? nptRadial.value : null,
      nptAzimuthal: mode.value === 'detector' ? nptAzimuthal.value : null,
      maskRatio: r.maskRatio,
      polarizationFactor: mode.value === 'detector' ? polarizationFactor.value : null,
      baseName: base
    })).data
    await downloadBlob(blob, `${base}_2d_integration.zip`)
    log(t('integration.status.exported'))
  } catch (e) {
    log(`Export error: ${e.message || e}`)
  }
}

// Export every batch result at once: one request → one ZIP, each image under
// its own sub-folder ({name}/{name}_masked.npy + axes + processing_info.json).
async function exportAllZip() {
  if (!results.value.length) return
  try {
    log(t('integration.status.exporting'))
    const blob = (await integrationExportBatchZip({
      items: results.value.map((r, i) => ({
        resultFileId: r.resultFileId,
        qArrayFileId: r.qArrayFileId,
        chiArrayFileId: r.chiArrayFileId,
        name: baseNameOf(i),
        maskRatio: r.maskRatio,
        polarizationFactor: mode.value === 'detector' ? polarizationFactor.value : null
      })),
      unit: currentResult.value?.unit || unit.value,
      mode: mode.value,
      nptRadial: mode.value === 'detector' ? nptRadial.value : null,
      nptAzimuthal: mode.value === 'detector' ? nptAzimuthal.value : null
    })).data
    await downloadBlob(blob, '2d_integration_batch.zip')
    log(t('integration.status.exportedBatch', { n: results.value.length }))
  } catch (e) {
    log(`Export error: ${e.message || e}`)
  }
}

function reset() {
  imageFiles.value = []
  poniFile.value = null
  poniParams.value = null
  customMask.value = null
  autoThresholds.value = null
  minThreshold.value = null
  maxThreshold.value = null
  contrastMin.value = null
  contrastMax.value = null
  refLineVisible.value = false
  refLineOffset.value = 0
  results.value = []
  currentIdx.value = 0
  status.value = 'idle'
  logs.value = []
  // cake-mode state
  mode.value = 'detector'
  cakeInfoName.value = ''
  cakeQMin.value = 0
  cakeQMax.value = 25
  cakeChiMin.value = -180
  cakeChiMax.value = 180
  cakeUnit.value = 'q_A^-1'
}

// When switching the viewed image, snap the contrast window to that image's range.
watch(currentIdx, () => {
  const r = currentResult.value
  if (r) {
    contrastMin.value = r.minIntensity
    contrastMax.value = r.maxIntensity
  }
})

// ---- Result thumbnails ---- lightweight <canvas> rendering of each cake preview
// (avoids spinning up N plotly instances). Clicking a thumb / table row sets currentIdx.
const thumbRefs = ref([])
function setThumbRef(el, i) {
  if (el) thumbRefs.value[i] = el
}
function imageName(i) {
  return imageFiles.value[i] ? imageFiles.value[i].name : `#${i + 1}`
}

// Filesystem-safe base name derived from the source image name, so per-image
// exports (single or batch ZIP entries) stay distinguishable.
function baseNameOf(i) {
  const raw = imageName(i).replace(/\.[^.]+$/, '')
  const safe = raw.replace(/[\\/:*?"<>|]+/g, '_').trim()
  return safe || `image_${i + 1}`
}

// 5-stop Viridis approximation — good enough for a thumbnail color mapping.
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
function drawThumb(canvas, data) {
  if (!canvas || !data || !data.length) return
  const rows = data.length
  const cols = data[0].length
  let mn = Infinity
  let mx = -Infinity
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = data[r][c]
      if (Number.isFinite(v)) {
        if (v < mn) mn = v
        if (v > mx) mx = v
      }
    }
  }
  const span = mx > mn ? mx - mn : 1
  const off = document.createElement('canvas')
  off.width = cols
  off.height = rows
  const octx = off.getContext('2d')
  const imgData = octx.createImageData(cols, rows)
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = data[r][c]
      const t = Number.isFinite(v) ? (v - mn) / span : 0
      const col = viridis(t)
      const idx = (r * cols + c) * 4
      imgData.data[idx] = col[0]
      imgData.data[idx + 1] = col[1]
      imgData.data[idx + 2] = col[2]
      imgData.data[idx + 3] = 255
    }
  }
  octx.putImageData(imgData, 0, 0)
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(off, 0, 0, canvas.width, canvas.height)
}
function renderThumbs() {
  results.value.forEach((r, i) => drawThumb(thumbRefs.value[i], r.preview))
}
// Re-render thumbs whenever the result set changes (DOM canvases mount via nextTick).
watch(() => results.value.length, async () => {
  await nextTick()
  renderThumbs()
})
</script>

<style scoped>
.integration-page {
  display: flex;
  flex-direction: column;
  gap: 22px;
  animation: intFadeIn 0.4s ease-out;
}

@keyframes intFadeUp {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes intFadeIn {
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
.integration-grid {
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
.panel--result { position: sticky; top: calc(var(--header-height) + 24px); }

.section { display: flex; flex-direction: column; gap: 14px; }
.section__head h3 { margin: 0; font-size: 1rem; font-weight: 700; color: var(--text-primary); }
.section__hint { display: block; margin-top: 3px; font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5; }

/* ---- Upload slots ---- */
.upload-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.upload-grid--single { grid-template-columns: 1fr; }
.upload-slot { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.slot-label { font-size: 0.8rem; font-weight: 600; color: var(--text-primary); }
.upload-slot--inline { margin-top: 4px; }

.file-chip {
  display: inline-flex; align-items: center; gap: 8px;
  align-self: flex-start;
  max-width: 100%;
  padding: 5px 10px;
  background: var(--primary-bg);
  border-radius: var(--radius-full);
  font-size: 0.78rem; color: var(--primary); font-weight: 600;
}
.file-chip__name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-chip__x {
  border: none; background: transparent; color: var(--primary);
  cursor: pointer; font-size: 1rem; line-height: 1; padding: 0;
  flex-shrink: 0;
}
.file-chip__x:hover { color: var(--color-error); }

.file-chip-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.file-chip-count {
  width: 100%;
  font-size: 0.74rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 2px;
}
.file-chip-clear {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 6px;
  text-decoration: underline;
}
.file-chip-clear:hover { color: var(--color-error); }

/* ---- Fields ---- */
.axis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.axis-grid--3 { grid-template-columns: 1fr 1fr; }
.axis-grid--4 { grid-template-columns: repeat(4, 1fr); gap: 12px; }
.cake-info-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }
.seg--mode { margin-bottom: 16px; }
.field { display: flex; flex-direction: column; gap: 5px; }
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
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.field input:focus, .field select:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--color-primary-glow);
}
.field--inline { flex-direction: row; align-items: center; gap: 10px; }
.field--inline label { flex-shrink: 0; }
.field--inline input { max-width: 140px; }
.field--slider input[type="range"] { width: 100%; accent-color: var(--primary); }

/* ---- Segmented control ---- */
.seg { display: inline-flex; gap: 3px; padding: 3px; background: var(--bg-surface-alt); border-radius: var(--radius-md); align-self: flex-start; }
.seg__btn {
  padding: 7px 16px; border: none; background: transparent;
  color: var(--text-secondary); font-size: 0.82rem; font-weight: 600;
  border-radius: var(--radius-sm); cursor: pointer; transition: all var(--transition-fast);
}
.seg__btn:hover { color: var(--text-primary); }
.seg__btn.active { background: var(--bg-surface); color: var(--primary); box-shadow: var(--shadow-sm); }

.mask-auto { display: flex; flex-direction: column; gap: 12px; }
.auto-result { display: flex; gap: 18px; font-size: 0.8rem; color: var(--text-secondary); font-family: var(--font-mono); }

/* ---- Buttons ---- */
.action-bar { display: flex; gap: 10px; margin-top: 4px; }
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 0.88rem; font-weight: 600;
  cursor: pointer; border: 1px solid transparent;
  transition: all var(--transition-fast);
}
.btn svg { width: 16px; height: 16px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn--primary { background: var(--primary); color: #FFFFFF; box-shadow: 0 8px 20px rgba(124, 58, 237, 0.22); }
.btn--primary:not(:disabled):hover { background: var(--primary-dark); transform: translateY(-1px); }
.btn--accent { background: var(--cta); color: #FFFFFF; box-shadow: 0 8px 20px rgba(124, 58, 237, 0.22); }
.btn--accent:hover { filter: brightness(0.96); transform: translateY(-1px); }
.btn--ghost { background: transparent; border-color: var(--border); color: var(--text-secondary); }
.btn--ghost:hover { border-color: var(--border-hover); color: var(--text-primary); background: var(--bg-surface-alt); }
.btn--sm { padding: 7px 14px; font-size: 0.8rem; align-self: flex-start; }

/* ---- Result ---- */
.stats { display: flex; gap: 16px; flex-wrap: wrap; }
.stat { font-size: 0.78rem; color: var(--text-secondary); font-family: var(--font-mono); }
.stat b { color: var(--text-primary); margin-right: 5px; }
.result-image-select {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 6px 0 8px;
}
.result-image-select select {
  font-family: var(--font-mono);
  font-size: 0.82rem;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-primary);
  max-width: 260px;
  min-width: 0;
}
.result-canvas { margin-top: 4px; }
.result-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; min-height: 340px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-lg);
  color: var(--text-muted);
}
.result-empty svg { width: 44px; height: 44px; opacity: 0.5; }
.result-empty p { margin: 0; font-size: 0.86rem; }
.result-actions { display: flex; gap: 10px; margin-top: 16px; }

/* ---- Thumbnails ---- */
.result-thumbs { margin-top: 14px; }
.thumbs-label { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.thumbs-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px;
  background: var(--bg-surface-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.thumb {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 92px;
  padding: 4px;
  border: 2px solid transparent;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}
.thumb:hover { border-color: var(--border-hover); }
.thumb.active { border-color: var(--primary); }
.thumb__canvas {
  width: 80px;
  height: 80px;
  display: block;
  border-radius: 4px;
  background: #1a1a2e;
  image-rendering: pixelated;
}
.thumb__name {
  font-size: 0.68rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  max-width: 84px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: center;
}

/* ---- File info table ---- */
.result-filelist { margin-top: 14px; }
.filelist-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}
.filelist-table th {
  text-align: left;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 7px 8px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.filelist-table td {
  padding: 7px 8px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  font-family: var(--font-mono);
}
.filelist-table tbody tr { cursor: pointer; transition: background-color var(--transition-fast); }
.filelist-table tbody tr:hover { background: var(--bg-surface-alt); }
.filelist-table tbody tr.active { background: var(--primary-bg); }
.filelist-name {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- Contrast controls ---- */
.contrast-controls {
  display: flex; flex-direction: column; gap: 10px;
  margin-top: 12px; padding: 12px;
  background: var(--bg-surface-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.contrast-controls .field--slider label { font-size: 0.76rem; }
.contrast-controls .btn--sm { align-self: flex-start; }

/* ---- Responsive ---- */
@media (max-width: 1080px) {
  .integration-grid { grid-template-columns: 1fr; }
  .panel--result { position: static; }
}
@media (max-width: 640px) {
  .upload-grid, .axis-grid { grid-template-columns: 1fr; }
}
</style>
