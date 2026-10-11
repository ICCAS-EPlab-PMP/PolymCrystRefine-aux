<template>
  <div class="xrd-sim-page">
    <div class="main-container">
      <aside class="sidebar">
        <nav class="tab-nav">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            :class="['tab-item', { active: activeTab === tab.id }]"
            @click="activeTab = tab.id"
          >
            <!-- Single Phase icon -->
            <svg v-if="tab.id === 'single'" class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
              <line x1="2" y1="12" x2="22" y2="12" />
            </svg>
            <!-- Dual Phase icon -->
            <svg v-else class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="9" cy="12" r="7" />
              <circle cx="15" cy="12" r="7" />
            </svg>
            <span class="tab-label">{{ tab.label }}</span>
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

          <!-- Single Phase Tab -->
          <div v-if="activeTab === 'single'" key="single" class="tab-panel">
            <div class="card">
              <h2 class="card-title">{{ t('xrd.single.title') }}</h2>
              <p class="card-desc">{{ t('xrd.single.desc') }}</p>

              <FileUpload
                accept=".txt,.dat"
                :multiple="false"
                :label="t('xrd.single.uploadPeakResult')"
                @files-selected="onSingleFilesSelected"
              />

              <ParamsForm :fields="singleCommonFields" :modelValue="singleParams" @update:modelValue="v => Object.assign(singleParams, v)" style="margin-top: 16px" />

              <!-- Cake grid params (original detector, q-χ) -->
              <div v-if="singleParams.mode === 'cake'" class="phase-section" style="margin-top: 16px">
                <h3 class="phase-label">{{ t('xrd.single.cake.title') }}</h3>
                <FileUpload
                  accept=".json,.txt"
                  :multiple="false"
                  :label="t('xrd.single.cake.processingInfoUpload')"
                  @files-selected="onSingleProcessingInfoSelected"
                />
                <p v-if="singleProcessingInfoName" class="result-meta" style="margin: 8px 0 0">
                  {{ t('xrd.single.cake.processingInfoParsed', { name: singleProcessingInfoName }) }}
                </p>
                <ParamsForm :fields="singleCakeFields" :modelValue="singleParams" @update:modelValue="v => Object.assign(singleParams, v)" style="margin-top: 12px" />
              </div>

              <!-- Detector geometry (2D pixel space) -->
              <div v-else class="phase-section" style="margin-top: 16px">
                <h3 class="phase-label">{{ t('xrd.single.detector.title') }}</h3>
                <FileUpload
                  accept=".poni"
                  :multiple="false"
                  :label="t('xrd.single.detector.poniUpload')"
                  @files-selected="onSinglePoniFilesSelected"
                />
                <p v-if="poniDetectorName" class="result-meta" style="margin: 8px 0 0">
                  {{ t('xrd.single.detector.poniParsed', { detector: poniDetectorName }) }}
                </p>
                <ParamsForm :fields="singleDetectorFields" :modelValue="singleParams" @update:modelValue="v => Object.assign(singleParams, v)" style="margin-top: 12px" />

                <!-- Detector presets reference -->
                <details style="margin-top: 12px; font-size: 12px; color: var(--color-text-secondary);">
                  <summary style="cursor: pointer; font-weight: 600;">{{ t('xrd.single.detector.presetsTitle') }}</summary>
                  <div style="margin-top: 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; background: var(--color-surface); padding: 10px; border-radius: 6px; border: 1px solid var(--color-border);">
                    <template v-for="p in detectorPresets" :key="p.name">
                      <span style="font-weight: 500;">{{ p.name }}</span>
                      <span>{{ p.pixelSize }} μm · {{ p.resolution }}</span>
                    </template>
                  </div>
                </details>
              </div>

              <button class="btn-primary" style="margin-top: 16px" :disabled="!canRunSingle || runStatus === 'running'" @click="runSimulation('single')">
                {{ runStatus === 'running' ? t('xrd.single.simulating') : t('xrd.single.btnRun') }}
              </button>

              <ConsolePanel
                v-if="consoleLogs.single.length || taskStatus.single !== 'idle'"
                :status="taskStatus.single"
                :logs="consoleLogs.single"
                style="margin-top: 16px"
              />

              <ImageCanvas
                v-if="singleResultImage"
                :image-data="singleResultImage"
                :x-axis="singleResultX"
                :y-axis="singleResultY"
                :x-axis-title="singleResultXTitle"
                :y-axis-title="singleResultYTitle"
                :title="singleParams.mode === 'cake' ? t('xrd.single.modes.cake') : t('xrd.single.modes.detector')"
                :colorscale="singleParams.colorscale"
                :height="560"
                :zmin="singleContrastMin"
                :zmax="singleContrastMax"
                :x-range="singleCropX"
                :y-range="singleCropY"
                square-pixels
                dragmode="select"
                style="margin-top: 16px"
                @region-selected="onSingleRegionSelected"
              />

              <!-- Result controls: contrast + crop (mirrors Image Analysis) -->
              <div v-if="singleResultImage" class="result-controls">
                <div class="contrast-block">
                  <label class="contrast-block-label">{{ t('xrd.single.result.contrastTitle') }}</label>
                  <div class="contrast-field">
                    <label class="contrast-field-label">{{ t('xrd.single.result.contrastMin') }}</label>
                    <input type="range" :min="singleResultMin" :max="singleResultMax" :step="singleContrastStep" v-model.number="singleContrastMin" class="contrast-slider" />
                    <input type="number" :min="singleResultMin" :max="singleResultMax" :step="singleContrastStep" v-model.number="singleContrastMin" class="contrast-num" />
                  </div>
                  <div class="contrast-field">
                    <label class="contrast-field-label">{{ t('xrd.single.result.contrastMax') }}</label>
                    <input type="range" :min="singleResultMin" :max="singleResultMax" :step="singleContrastStep" v-model.number="singleContrastMax" class="contrast-slider" />
                    <input type="number" :min="singleResultMin" :max="singleResultMax" :step="singleContrastStep" v-model.number="singleContrastMax" class="contrast-num" />
                  </div>
                  <div class="btn-row">
                    <button class="btn-compact" @click="resetSingleContrast">{{ t('xrd.single.result.contrastReset') }}</button>
                  </div>
                </div>

                <div class="crop-block">
                  <label class="contrast-block-label">{{ t('xrd.single.result.cropHint') }}</label>
                  <div class="btn-row">
                    <button class="btn-compact" @click="exportSingleResult">
                      {{ singleParams.mode === 'cake' ? t('xrd.single.result.exportNpy') : t('xrd.single.result.exportTiff') }}
                    </button>
                    <button class="btn-compact" @click="resetSingleCrop">{{ t('xrd.single.result.cropReset') }}</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Dual Phase Tab -->
          <div v-else-if="activeTab === 'dual'" key="dual" class="tab-panel">
            <div class="card">
              <h2 class="card-title">{{ t('xrd.dual.title') }}</h2>
              <p class="card-desc">{{ t('xrd.dual.desc') }}</p>

              <div class="phase-section">
                <h3 class="phase-label">{{ t('xrd.dual.phaseA') }}</h3>
                <FileUpload
                  accept=".txt,.dat"
                  :multiple="false"
                  :label="t('xrd.dual.uploadLabelA')"
                  @files-selected="onDualPhaseAFilesSelected"
                />
                <ParamsForm :fields="dualPhaseParamFields" :modelValue="dualParams.phaseA" @update:modelValue="v => Object.assign(dualParams.phaseA, v)" style="margin-top: 12px" />
              </div>

              <div class="phase-section">
                <h3 class="phase-label">{{ t('xrd.dual.phaseB') }}</h3>
                <FileUpload
                  accept=".txt,.dat"
                  :multiple="false"
                  :label="t('xrd.dual.uploadLabelB')"
                  @files-selected="onDualPhaseBFilesSelected"
                />
                <ParamsForm :fields="dualPhaseParamFields" :modelValue="dualParams.phaseB" @update:modelValue="v => Object.assign(dualParams.phaseB, v)" style="margin-top: 12px" />
              </div>

              <ParamsForm :fields="dualGlobalFields" :modelValue="dualParams.global" @update:modelValue="v => Object.assign(dualParams.global, v)" style="margin-top: 16px" />

              <p v-if="needBothPhasesHint" class="result-meta" style="margin-top: 12px">
                {{ t('xrd.dual.needBothPhases') }}
              </p>

              <button class="btn-primary" style="margin-top: 16px" :disabled="!canRunDual || runStatus === 'running'" @click="runSimulation('dual')">
                {{ runStatus === 'running' ? t('xrd.dual.simulating') : t('xrd.dual.btnRun') }}
              </button>

              <ConsolePanel
                v-if="consoleLogs.dual.length || taskStatus.dual !== 'idle'"
                :status="taskStatus.dual"
                :logs="consoleLogs.dual"
                style="margin-top: 16px"
              />

              <ImageCanvas
                v-if="dualResultImage"
                :image-data="dualResultImage"
                :x-axis="dualResultX"
                :y-axis="dualResultY"
                :x-axis-title="dualResultXTitle"
                :y-axis-title="dualResultYTitle"
                :title="`${t('xrd.dual.title')} (${t('xrd.single.modes.' + dualParams.global.mode)})`"
                colorscale="Viridis"
                :height="560"
                :zmin="dualContrastMin"
                :zmax="dualContrastMax"
                :x-range="dualCropX"
                :y-range="dualCropY"
                square-pixels
                dragmode="select"
                style="margin-top: 16px"
                @region-selected="onDualRegionSelected"
              />

              <!-- Result controls: contrast + crop (mirrors Image Analysis) -->
              <div v-if="dualResultImage" class="result-controls">
                <div class="contrast-block">
                  <label class="contrast-block-label">{{ t('xrd.single.result.contrastTitle') }}</label>
                  <div class="contrast-field">
                    <label class="contrast-field-label">{{ t('xrd.single.result.contrastMin') }}</label>
                    <input type="range" :min="dualResultMin" :max="dualResultMax" :step="dualContrastStep" v-model.number="dualContrastMin" class="contrast-slider" />
                    <input type="number" :min="dualResultMin" :max="dualResultMax" :step="dualContrastStep" v-model.number="dualContrastMin" class="contrast-num" />
                  </div>
                  <div class="contrast-field">
                    <label class="contrast-field-label">{{ t('xrd.single.result.contrastMax') }}</label>
                    <input type="range" :min="dualResultMin" :max="dualResultMax" :step="dualContrastStep" v-model.number="dualContrastMax" class="contrast-slider" />
                    <input type="number" :min="dualResultMin" :max="dualResultMax" :step="dualContrastStep" v-model.number="dualContrastMax" class="contrast-num" />
                  </div>
                  <div class="btn-row">
                    <button class="btn-compact" @click="resetDualContrast">{{ t('xrd.single.result.contrastReset') }}</button>
                  </div>
                </div>

                <div class="crop-block">
                  <label class="contrast-block-label">{{ t('xrd.single.result.cropHint') }}</label>
                  <div class="btn-row">
                    <button class="btn-compact" @click="exportDualResult">
                      {{ dualParams.global.mode === 'cake' ? t('xrd.single.result.exportNpy') : t('xrd.single.result.exportTiff') }}
                    </button>
                    <button class="btn-compact" @click="resetDualCrop">{{ t('xrd.single.result.cropReset') }}</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </transition>

        <!-- Shared experiment comparison (single uploaded experiment vs the
             ACTIVE tab's simulation). Panes are stacked full-width and sized
             like the main simulation canvas so both images show as large as
             possible; the experiment pane directly follows the simulation. -->
        <div v-if="compareSimImage" class="card compare-card">
          <div class="compare-card-head">
            <h3 class="result-title">{{ t('xrd.single.compare.title') }}</h3>
            <button
              class="btn-compact"
              :title="t('xrd.single.compare.resetAllHint')"
              @click="resetCompareState"
            >
              {{ t('xrd.single.compare.resetAll') }}
            </button>
          </div>

          <!-- Single experiment upload + active-image chip / off switch -->
          <div class="compare-upload-row">
            <FileUpload
              :accept="compareSimMode === 'cake' ? '.npy' : '.tif,.tiff,.edf,.npy'"
              :multiple="false"
              clear-after-select
              :label="t('xrd.single.compare.uploadExpShort')"
              @files-selected="onSingleExpFilesSelected"
            />
            <div v-if="singleExpLoaded" class="compare-active">
              <span class="compare-chip" :title="singleExpName">{{ singleExpName }}</span>
              <button class="btn-compact btn-compare-off" @click="clearSingleExp">
                {{ t('xrd.single.compare.off') }}
              </button>
            </div>
          </div>

          <template v-if="singleExpDisplay">
            <div class="result-controls compare-settings">
              <div class="contrast-block">
                <label class="contrast-block-label">{{ t('xrd.single.compare.displayTitle') }}</label>
                <div class="contrast-field">
                  <label class="contrast-field-label">{{ t('xrd.single.colorscale') }}</label>
                  <select v-model="compareColorscale" class="compare-colorscale">
                    <option v-for="c in compareColorscaleOptions" :key="c" :value="c">{{ c }}</option>
                  </select>
                </div>
                <div class="contrast-field">
                  <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; cursor: pointer;">
                    <input type="checkbox" v-model="singleNormExp" style="accent-color: var(--color-primary);" />
                    {{ t('xrd.single.compare.normalize') }}
                  </label>
                </div>
                <div class="contrast-field">
                  <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; cursor: pointer;">
                    <input type="checkbox" v-model="singleUseLog" style="accent-color: var(--color-primary);" />
                    {{ t('xrd.single.compare.logScale') }}
                  </label>
                </div>
              </div>

              <div class="contrast-block">
                <label class="contrast-block-label">{{ t('xrd.single.compare.expContrastTitle') }}</label>
                <div class="contrast-field">
                  <label class="contrast-field-label">{{ t('xrd.single.result.contrastMin') }}</label>
                  <input type="range" :min="singleExpMin" :max="singleExpMax" :step="singleExpContrastStep" v-model.number="singleExpContrastMin" class="contrast-slider" />
                  <input type="number" :min="singleExpMin" :max="singleExpMax" :step="singleExpContrastStep" v-model.number="singleExpContrastMin" class="contrast-num" />
                </div>
                <div class="contrast-field">
                  <label class="contrast-field-label">{{ t('xrd.single.result.contrastMax') }}</label>
                  <input type="range" :min="singleExpMin" :max="singleExpMax" :step="singleExpContrastStep" v-model.number="singleExpContrastMax" class="contrast-slider" />
                  <input type="number" :min="singleExpMin" :max="singleExpMax" :step="singleExpContrastStep" v-model.number="singleExpContrastMax" class="contrast-num" />
                </div>
                <div class="btn-row">
                  <button class="btn-compact" @click="resetSingleExpContrast">{{ t('xrd.single.result.contrastReset') }}</button>
                </div>
              </div>

              <!-- 归正: flip/rotate the experiment image so its orientation
                   matches the simulation (axes stay pinned to the shared
                   q-χ grid / pixel frame, only the data moves). -->
              <div class="crop-block">
                <label class="contrast-block-label">{{ t('xrd.single.compare.alignTitle') }}</label>
                <div class="btn-row" style="flex-wrap: wrap;">
                  <button :class="['btn-compact', 'btn-align', { 'btn-align--active': singleExpFlipV }]" @click="singleExpFlipV = !singleExpFlipV">
                    ⇅ {{ t('xrd.single.compare.flipV') }}
                  </button>
                  <button :class="['btn-compact', 'btn-align', { 'btn-align--active': singleExpFlipH }]" @click="singleExpFlipH = !singleExpFlipH">
                    ⇄ {{ t('xrd.single.compare.flipH') }}
                  </button>
                  <button :class="['btn-compact', 'btn-align', { 'btn-align--active': singleExpFlipH && singleExpFlipV }]" @click="toggleSingleExpRot180">
                    ⟳ {{ t('xrd.single.compare.rot180') }}
                  </button>
                </div>
                <p class="result-meta" style="margin: 0;">
                  {{ t('xrd.single.compare.alignHint') }}
                </p>
              </div>
            </div>

            <div class="compare-panes">
              <div class="compare-pane">
                <div class="compare-pane-head">
                  <span class="compare-pane-tag compare-pane-tag--sim">{{ t('xrd.single.compare.simTitle') }}</span>
                  <button
                    class="pane-export-btn"
                    :title="t('xrd.single.compare.exportSimPng')"
                    @click="exportComparePane('sim')"
                  >⤓ PNG</button>
                </div>
                <ImageCanvas
                  ref="compareSimCanvasRef"
                  :image-data="compareSimImage"
                  :x-axis="compareSimX"
                  :y-axis="compareSimY"
                  :x-axis-title="compareSimXTitle"
                  :y-axis-title="compareSimYTitle"
                  :colorscale="compareColorscale"
                  :height="comparePaneHeight"
                  :zmin="compareSimZmin"
                  :zmax="compareSimZmax"
                  :log-scale="singleUseLog"
                  :show-toolbar="false"
                  :x-range="compareSimCropX"
                  :y-range="compareSimCropY"
                  square-pixels
                />
              </div>
              <div class="compare-pane">
                <div class="compare-pane-head">
                  <span class="compare-pane-tag compare-pane-tag--exp">{{ t('xrd.single.compare.expTitle') }} · {{ singleExpName }}</span>
                  <button
                    class="pane-export-btn"
                    :title="t('xrd.single.compare.exportExpPng')"
                    @click="exportComparePane('exp')"
                  >⤓ PNG</button>
                </div>
                <ImageCanvas
                  ref="compareExpCanvasRef"
                  :image-data="singleExpDisplay"
                  :x-axis="singleExpX"
                  :y-axis="singleExpY"
                  :x-axis-title="singleExpXTitle"
                  :y-axis-title="singleExpYTitle"
                  :colorscale="compareColorscale"
                  :height="comparePaneHeight"
                  :zmin="singleExpViewMin"
                  :zmax="singleExpViewMax"
                  :log-scale="singleUseLog"
                  :show-toolbar="false"
                  :x-range="compareSimCropX"
                  :y-range="compareSimCropY"
                  square-pixels
                />
              </div>
            </div>
          </template>
          <div v-else class="compare-placeholder">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="3" y1="9" x2="21" y2="9" />
              <line x1="9" y1="3" x2="9" y2="21" />
            </svg>
            <p>{{ t('xrd.single.compare.placeholder') }}</p>
          </div>
        </div>
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
import ImageCanvas from '@/components/ImageCanvas.vue'
import {
  xrdRunSimulation,
  xrdRunDualSimulation,
  xrdUploadFile,
  xrdParsePoni,
  xrdParseProcessingInfo,
  xrdLoadExperiment,
  xrdDownloadRawF32
} from '@/api/index.js'
import { saveBlob } from '@/services/download.js'

const { t } = useI18n()

const tabs = computed(() => [
  { id: 'single', label: t('xrd.tabs.single') },
  { id: 'dual', label: t('xrd.tabs.dual') },
])

const activeTab = ref('single')
const runStatus = ref('idle')

const statusClass = computed(() => {
  if (runStatus.value === 'completed') return 'success'
  if (runStatus.value === 'failed') return 'error'
  return runStatus.value
})

const statusLabel = computed(() => {
  const labels = { idle: t('status.idle'), running: t('status.running'), completed: t('status.completed'), failed: t('status.failed') }
  return labels[runStatus.value] || runStatus.value
})

// ---- Console / task tracking ----
const taskStatus = reactive({
  single: 'idle',
  dual: 'idle',
})
const consoleLogs = reactive({
  single: [],
  dual: [],
})

// ---- Single Phase (fiber diffraction) ----
const singleFiles = ref([])          // peak_result.txt
const singlePoniFiles = ref([])      // PONI for detector mode
const singlePoniFileId = ref(null)
const poniDetectorName = ref('')
const singleParams = reactive({
  mode: 'cake',                       // 'cake' (original detector) | 'detector' (2D pixel)
  kernel: 'fast',                     // 'fast' (default) | 'legacy' (per-peak numpy)
  sigmaQ: 0.03,                       // Å^-1
  sigmaChi: 3.0,                      // deg
  expandSymmetry: true,                // 4-fold fiber symmetry (on by default for fiber diffraction)
  colorscale: 'Viridis',
  // cake grid
  qMin: 0.0,
  qMax: 25.0,
  chiMin: -180.0,
  chiMax: 180.0,
  nQ: 1000,
  nChi: 360,
  // detector geometry (auto-filled from PONI, editable)
  wavelength: 1.5406,                 // Å
  sd: 100.0,                          // mm
  centerx: 1024.0,                    // px
  centery: 1024.0,                    // px
  pixelSize: 75.0,                    // μm
  imgW: 2048,
  imgH: 2048,
})

// Detector pixel-size presets (common synchrotron detectors)
const detectorPresets = [
  { name: 'Pilatus 2M', pixelSize: 172, resolution: '1475×1679' },
  { name: 'Pilatus 6M', pixelSize: 172, resolution: '2463×2527' },
  { name: 'Eiger 4M', pixelSize: 75, resolution: '2070×2167' },
  { name: 'Eiger2 9M', pixelSize: 75, resolution: '3110×3269' },
  { name: 'Eiger2 16M', pixelSize: 75, resolution: '4148×4362' },
  { name: 'MarCCD 165', pixelSize: 79.1, resolution: '2048×2048' },
  { name: 'PerkinElmer', pixelSize: 200, resolution: '2048×2048' },
  { name: 'Rayonix MX225', pixelSize: 73.2, resolution: '3072×3072' },
  { name: 'Rayonix MX340', pixelSize: 88.5, resolution: '3840×3840' },
  { name: 'ADSC Q315', pixelSize: 51.3, resolution: '6144×6144' },
]

const singleCommonFields = computed(() => [
  { key: 'mode', label: t('xrd.single.mode'), type: 'select', options: [
    { value: 'cake', label: t('xrd.single.modes.cake') },
    { value: 'detector', label: t('xrd.single.modes.detector') },
  ]},
  { key: 'kernel', label: t('xrd.single.kernel'), type: 'select', options: [
    { value: 'fast', label: t('xrd.single.kernels.fast') },
    { value: 'legacy', label: t('xrd.single.kernels.legacy') },
  ]},
  { key: 'sigmaQ', label: t('xrd.single.sigmaQ'), type: 'number', step: 0.001, min: 0 },
  { key: 'sigmaChi', label: t('xrd.single.sigmaChi'), type: 'number', step: 0.1, min: 0 },
  { key: 'expandSymmetry', label: t('xrd.single.symmetry'), type: 'checkbox', help: t('xrd.single.symmetryHelp') },
  { key: 'colorscale', label: t('xrd.single.colorscale'), type: 'select', options: [
    'Viridis', 'Plasma', 'Inferno', 'Magma', 'Hot', 'Jet', 'Gray',
  ]},
])
const singleCakeFields = computed(() => [
  { key: 'qMin', label: t('xrd.single.cake.qMin'), type: 'number', step: 0.1 },
  { key: 'qMax', label: t('xrd.single.cake.qMax'), type: 'number', step: 0.1 },
  { key: 'chiMin', label: t('xrd.single.cake.chiMin'), type: 'number', step: 1 },
  { key: 'chiMax', label: t('xrd.single.cake.chiMax'), type: 'number', step: 1 },
  { key: 'nQ', label: t('xrd.single.cake.nQ'), type: 'number', step: 10, min: 10 },
  { key: 'nChi', label: t('xrd.single.cake.nChi'), type: 'number', step: 10, min: 10 },
])
const singleDetectorFields = computed(() => [
  { key: 'wavelength', label: t('xrd.single.detector.wavelength'), type: 'number', step: 0.0001 },
  { key: 'sd', label: t('xrd.single.detector.sampleDistance'), type: 'number', step: 0.1 },
  { key: 'centerx', label: t('xrd.single.detector.beamCenterX'), type: 'number', step: 1 },
  { key: 'centery', label: t('xrd.single.detector.beamCenterY'), type: 'number', step: 1 },
  { key: 'pixelSize', label: t('xrd.single.detector.pixelSize'), type: 'number', step: 0.1 },
  { key: 'imgW', label: t('xrd.single.detector.imgWidth'), type: 'number', step: 1, min: 8 },
  { key: 'imgH', label: t('xrd.single.detector.imgHeight'), type: 'number', step: 1, min: 8 },
])
const canRunSingle = computed(() => {
  if (!singleFiles.value.length) return false
  if (singleParams.mode === 'detector') {
    return singleParams.sd > 0 && singleParams.wavelength > 0 && singleParams.pixelSize > 0
  }
  return true
})
const singleResultImage = ref(null)
const singleResultX = ref(null)
const singleResultY = ref(null)
const singleResultXTitle = ref('')
const singleResultYTitle = ref('')
// Full-resolution raw image (base64 float32 + shape) kept for .tiff export.
// The on-screen heatmap may be down-sampled for rendering, so exports decode
// these to the original array to preserve fidelity.
const singleResultRawB64 = ref(null)
const singleResultRawShape = ref([])
// Detector-mode payloads carry a decimated preview; the full-resolution image
// is fetched from the server (fileId) at export time.
const singleResultFileId = ref(null)
const singleResultFullShape = ref([])
// Contrast window (zmin/zmax) + crop bands for the single-phase result.
// singleResultMin/Max bracket the data and drive the slider extents; the
// contrast values themselves are editable. cropX/cropY are null until the
// user box-selects a region.
const singleResultMin = ref(0)
const singleResultMax = ref(1)
const singleContrastMin = ref(0)
const singleContrastMax = ref(1)
const singleContrastStep = computed(() => {
  const span = singleResultMax.value - singleResultMin.value
  return span > 0 ? +(span / 200).toPrecision(3) : 0.001
})
const singleCropX = ref(null)
const singleCropY = ref(null)

// ---- Experiment comparison: ONE uploaded experiment vs the simulation ----
// Single-file model: uploading replaces the current experiment. The decoded z
// is simulation-mode independent; physical axes are derived per compare
// context (below) so one decode serves cake and detector comparisons alike.
const singleExpName = ref('')
const singleExpLoaded = ref(false)
const singleExpBaseZ = ref(null)
// Source-index arrays from buildHeatmap's decimation (physical-axis mapping).
const singleExpRowIdx = ref(null)
const singleExpColIdx = ref(null)
const singleExpSrcRows = ref(0)
const singleExpSrcCols = ref(0)
// Raw data range (contrast slider extents) + user contrast window.
const singleExpMin = ref(0)
const singleExpMax = ref(1)
const singleExpContrastMin = ref(0)
const singleExpContrastMax = ref(1)
const singleExpContrastStep = computed(() => {
  const span = singleExpMax.value - singleExpMin.value
  return span > 0 ? +(span / 200).toPrecision(3) : 0.001
})
const singleNormExp = ref(true)
const singleUseLog = ref(false)
// 归正 flips applied to the experiment image so it lines up with the
// simulation. Axes stay pinned to the shared grid; only the data moves.
const singleExpFlipH = ref(false)
const singleExpFlipV = ref(false)

// ---- Which simulation the experiment is compared against (active tab) ----
const compareSimIsSingle = computed(() => activeTab.value === 'single')
const compareSimImage = computed(() =>
  compareSimIsSingle.value ? singleResultImage.value : dualResultImage.value)
const compareSimX = computed(() => compareSimIsSingle.value ? singleResultX.value : dualResultX.value)
const compareSimY = computed(() => compareSimIsSingle.value ? singleResultY.value : dualResultY.value)
const compareSimXTitle = computed(() => compareSimIsSingle.value ? singleResultXTitle.value : dualResultXTitle.value)
const compareSimYTitle = computed(() => compareSimIsSingle.value ? singleResultYTitle.value : dualResultYTitle.value)
const compareSimZmin = computed(() => compareSimIsSingle.value ? singleContrastMin.value : dualContrastMin.value)
const compareSimZmax = computed(() => compareSimIsSingle.value ? singleContrastMax.value : dualContrastMax.value)
const compareSimCropX = computed(() => compareSimIsSingle.value ? singleCropX.value : dualCropX.value)
const compareSimCropY = computed(() => compareSimIsSingle.value ? singleCropY.value : dualCropY.value)
// Colormap for BOTH compare panes — independent of the main result's
// colorscale so the comparison view can be tuned on its own (Jet included).
const compareColorscale = ref('Viridis')
const compareColorscaleOptions = ['Viridis', 'Plasma', 'Inferno', 'Magma', 'Hot', 'Jet', 'Gray']
const compareSimMode = computed(() =>
  compareSimIsSingle.value ? singleParams.mode : dualParams.global.mode)
const compareSimResultMax = computed(() =>
  compareSimIsSingle.value ? singleResultMax.value : dualResultMax.value)

// Stacked compare panes sized like the main simulation canvas (560) so both
// the simulation and the experiment image render as large as possible.
const comparePaneHeight = 560

// Canvas instances for the two compare panes (PNG export via Plotly.toImage).
const compareSimCanvasRef = ref(null)
const compareExpCanvasRef = ref(null)

// 恢复初始设置: compare display options back to their defaults (colormap,
// normalize, log, alignment flips and the experiment contrast window).
function resetCompareState() {
  compareColorscale.value = 'Viridis'
  singleNormExp.value = true
  singleUseLog.value = false
  singleExpFlipH.value = false
  singleExpFlipV.value = false
  resetSingleExpContrast()
  consoleLogs.single.push(t('xrd.single.compare.resetDone'))
}

// Export one compare pane as PNG (Plotly renders at 1200×800). Routed through
// saveBlob so the Electron native save dialog is used.
async function exportComparePane(which) {
  const inst = which === 'sim' ? compareSimCanvasRef.value : compareExpCanvasRef.value
  if (!inst) return
  try {
    const url = await inst.getImageDataUrl('png')
    if (!url) throw new Error('render failed')
    const blob = await (await fetch(url)).blob()
    const base = which === 'sim' ? 'xrd_compare_sim' : 'xrd_compare_exp'
    await downloadBlob(blob, `${base}.png`)
    consoleLogs.single.push(t('xrd.single.compare.exportedPane', { name: `${base}.png` }))
  } catch (err) {
    consoleLogs.single.push(t('logs.common.error', { message: err.message || err }))
  }
}

// q/χ extents of the compared simulation — cake mode pins both panes to the
// same grid (single: the user/processing_info grid; dual: its fixed grid).
const compareGrid = computed(() => {
  if (compareSimIsSingle.value) {
    return {
      q: [singleParams.qMin, singleParams.qMax],
      chi: [singleParams.chiMin, singleParams.chiMax],
    }
  }
  return { q: [0.0, 25.0], chi: [-180.0, 180.0] }
})

// Map a physical vector onto the down-sampled display columns/rows with the
// SAME source-index mapping buildHeatmap used when decimating — keeps the
// experiment axis tick-aligned with the simulation pane.
function mapPhysAxis(phys, idx) {
  if (!phys || !idx || !phys.length) return null
  return idx.map(i => phys[Math.min(phys.length - 1, i)])
}
const singleExpX = computed(() => {
  if (!singleExpBaseZ.value || compareSimMode.value !== 'cake') return null
  const [q0, q1] = compareGrid.value.q
  return mapPhysAxis(linspace(q0, q1, singleExpSrcCols.value), singleExpColIdx.value)
})
const singleExpY = computed(() => {
  if (!singleExpBaseZ.value || compareSimMode.value !== 'cake') return null
  const [c0, c1] = compareGrid.value.chi
  return mapPhysAxis(linspace(c0, c1, singleExpSrcRows.value), singleExpRowIdx.value)
})
const singleExpXTitle = computed(() => compareSimMode.value === 'cake' ? 'q (Å⁻¹)' : 'X (pixel)')
const singleExpYTitle = computed(() => compareSimMode.value === 'cake' ? 'χ (°)' : 'Y (pixel)')

// Scale factor mapping the experiment's max intensity onto the simulation's
// (the "normalize" option — mirrors the reference simulator's 归一化实验图).
const singleExpNormScale = computed(() => {
  const simMax = compareSimResultMax.value
  const expMax = singleExpMax.value
  return simMax > 0 && expMax > 0 ? simMax / expMax : 1
})

// Rendered experiment image: base data with the selected flips and the
// optional normalization applied.
const singleExpDisplay = computed(() => {
  const base = singleExpBaseZ.value
  if (!base) return null
  let z = base
  if (singleExpFlipV.value) z = z.slice().reverse()
  if (singleExpFlipH.value) z = z.map(row => row.slice().reverse())
  const s = singleNormExp.value ? singleExpNormScale.value : 1
  if (s !== 1) z = z.map(row => row.map(v => v * s))
  return z
})
// Contrast window handed to the heatmap, in the same (possibly normalized)
// domain as the rendered data.
const singleExpViewMin = computed(() =>
  singleExpContrastMin.value * (singleNormExp.value ? singleExpNormScale.value : 1))
const singleExpViewMax = computed(() =>
  singleExpContrastMax.value * (singleNormExp.value ? singleExpNormScale.value : 1))

// linspace(a, b, n) — physical axis vector for the heatmap.
const linspace = (a, b, n) =>
  n <= 1 ? [a] : Array.from({ length: n }, (_, i) => a + (b - a) * i / (n - 1))

// Decode the backend's float32-raw-bytes base64 image into a 2-D heatmap.
// The backend returns imageBase64 = base64(float32 row-major) + shape [rows, cols].
// Plotly renders an Array-of-Arrays heatmap, so we convert here (and optionally
// down-sample very large detector images to keep the browser responsive).
// xPhys/yPhys (length cols/rows) give physical axis values; pass null to use
// raw pixel indices.
function buildHeatmap(b64, shape, xPhys, yPhys) {
  const rows = shape?.[0] || 0
  const cols = shape?.[1] || 0
  if (!rows || !cols) return null
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  const flat = new Float32Array(bytes.buffer)

  const MAX = 1000
  const stepC = cols > MAX ? Math.ceil(cols / MAX) : 1
  const stepR = rows > MAX ? Math.ceil(rows / MAX) : 1
  const dCols = Math.ceil(cols / stepC)
  const dRows = Math.ceil(rows / stepR)

  const z = new Array(dRows)
  const xAxis = new Array(dCols)
  const yAxis = new Array(dRows)
  // Source-row/col index per down-sampled row/col — lets callers map a
  // physical axis vector (length rows/cols) onto the display grid later,
  // exactly matching this decimation (used by the experiment-compare panes).
  const rowIdx = new Array(dRows)
  const colIdx = new Array(dCols)
  for (let r = 0; r < dRows; r++) {
    const srcR = Math.min(rows - 1, r * stepR)
    rowIdx[r] = srcR
    yAxis[r] = yPhys ? yPhys[srcR] : srcR
    const row = new Array(dCols)
    for (let c = 0; c < dCols; c++) {
      const srcC = Math.min(cols - 1, c * stepC)
      if (r === 0) {
        colIdx[c] = srcC
        xAxis[c] = xPhys ? xPhys[srcC] : srcC
      }
      row[c] = flat[srcR * cols + srcC]
    }
    z[r] = row
  }
  return { z, xAxis, yAxis, rowIdx, colIdx, srcRows: rows, srcCols: cols }
}

// Min/max of a 2-D array, ignoring NaN — used to size the contrast slider
// extents to the actual data range each time a new image is produced.
function arrayMinMax(z) {
  let mn = Infinity
  let mx = -Infinity
  for (let r = 0; r < z.length; r++) {
    const row = z[r]
    for (let c = 0; c < row.length; c++) {
      const v = row[c]
      if (Number.isFinite(v)) {
        if (v < mn) mn = v
        if (v > mx) mx = v
      }
    }
  }
  if (!Number.isFinite(mn) || !Number.isFinite(mx)) return [0, 1]
  return [mn, mx]
}

// Decode the backend's float32-raw-bytes base64 into a flat Float32Array
// (row-major, full resolution — no down-sampling). Used by the .tiff export.
function decodeF32(b64) {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Float32Array(bytes.buffer)
}

// Build an uncompressed little-endian 32-bit float grayscale TIFF (single
// strip) from a flat Float32Array and return it as a Blob. Float32 sample
// format (SampleFormat=3) keeps the exact simulated intensities, so tools
// like ImageJ/Fiji, pyFAI/fabio and matplotlib read the same numbers the
// simulator produced. Layout: 8-byte header + one IFD + raw pixel data.
function buildTiffBlob(flat, rows, cols) {
  const byteCount = rows * cols * 4
  const entries = [
    [256, 4, 1, cols],   // ImageWidth (LONG)
    [257, 4, 1, rows],   // ImageLength (LONG)
    [258, 3, 1, 32],     // BitsPerSample (SHORT)
    [259, 3, 1, 1],      // Compression: none
    [262, 3, 1, 1],      // PhotometricInterpretation: BlackIsZero
    [273, 4, 1, 0],      // StripOffsets (LONG) — patched below
    [277, 3, 1, 1],      // SamplesPerPixel (SHORT)
    [278, 4, 1, rows],   // RowsPerStrip (LONG)
    [279, 4, 1, byteCount], // StripByteCounts (LONG)
    [284, 3, 1, 1],      // PlanarConfiguration: chunky
    [339, 3, 1, 3],      // SampleFormat: IEEE float
  ]
  const dataOffset = 8 + 2 + entries.length * 12 + 4
  entries[5][3] = dataOffset
  const out = new Uint8Array(dataOffset + byteCount)
  const view = new DataView(out.buffer)
  out[0] = 0x49
  out[1] = 0x49                       // byte order "II" (little-endian)
  view.setUint16(2, 42, true)         // TIFF magic
  view.setUint32(4, 8, true)          // first IFD at offset 8
  view.setUint16(8, entries.length, true)
  let p = 10
  for (const [tag, type, count, value] of entries) {
    view.setUint16(p, tag, true)
    view.setUint16(p + 2, type, true)
    view.setUint32(p + 4, count, true)
    if (type === 3) view.setUint16(p + 8, value, true) // SHORT value inline
    else view.setUint32(p + 8, value, true)             // LONG value inline
    p += 12
  }
  view.setUint32(p, 0, true)          // no next IFD
  out.set(new Uint8Array(flat.buffer, flat.byteOffset, flat.byteLength), dataOffset)
  return new Blob([out], { type: 'image/tiff' })
}

// Save a Blob under the given filename. Under Electron, `<a download>.click()`
// throws "An object could not be cloned" (the click is intercepted and the DOM
// Blob is marshalled through IPC, which the structured-clone algorithm
// rejects). saveBlob routes through the native save dialog (base64 data: URL)
// under Electron and falls back to <a download> in a plain browser.
async function downloadBlob(blob, filename) {
  await saveBlob(blob, filename)
}

// Build a NumPy .npy v1.0 file (little-endian float32, C order) as a Blob,
// mirroring np.save on a float32 array so cake results keep exact values and
// can be reloaded by numpy/pyFAI downstream.
function buildNpyBlob(flat, rows, cols) {
  const dict = `{'descr': '<f4', 'fortran_order': False, 'shape': (${rows}, ${cols}), }`
  // Header padded with spaces so magic+version+hlen+header is 64-byte
  // aligned and terminated with \n, per the .npy format spec.
  const pad = (64 - ((10 + dict.length + 1) % 64)) % 64
  const header = dict + ' '.repeat(pad) + '\n'
  const out = new Uint8Array(10 + header.length + flat.byteLength)
  const view = new DataView(out.buffer)
  out.set([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59], 0)   // "\x93NUMPY"
  out[6] = 0x01                                       // format version 1.0
  out[7] = 0x00
  view.setUint16(8, header.length, true)
  out.set(new TextEncoder().encode(header), 10)
  out.set(new Uint8Array(flat.buffer, flat.byteOffset, flat.byteLength), 10 + header.length)
  return new Blob([out], { type: 'application/octet-stream' })
}

// Export the full-resolution simulated image: cake mode → .npy (matches the
// reference simulator's sim_result.npy), 2D-detector mode → 32-bit float .tiff.
// Detector responses may carry a decimated preview, so when fullShape differs
// from the payload shape the exact full image is fetched from the server first.
async function exportResult(b64, shape, mode, filename, logKey, fileId, fullShape) {
  if (!b64 || !shape || shape.length < 2) return
  let rows = shape[0]
  let cols = shape[1]
  let flat
  const isPreview = mode !== 'cake'
    && fileId && Array.isArray(fullShape) && fullShape.length === 2
    && (fullShape[0] !== shape[0] || fullShape[1] !== shape[1])
  if (isPreview) {
    const resp = await xrdDownloadRawF32(fileId)
    flat = new Float32Array(resp.data)
    rows = fullShape[0]
    cols = fullShape[1]
  } else {
    flat = decodeF32(b64)
  }
  const blob = mode === 'cake'
    ? buildNpyBlob(flat, rows, cols)
    : buildTiffBlob(flat, rows, cols)
  await downloadBlob(blob, filename)
  consoleLogs[logKey].push(mode === 'cake'
    ? t('xrd.single.result.exportedNpy', { name: filename, rows, cols })
    : t('xrd.single.result.exportedTiff', { name: filename, rows, cols }))
}
async function exportSingleResult() {
  const mode = singleParams.mode
  await exportResult(
    singleResultRawB64.value, singleResultRawShape.value, mode,
    `sim_single_${mode}.${mode === 'cake' ? 'npy' : 'tiff'}`, 'single',
    singleResultFileId.value, singleResultFullShape.value,
  )
}
async function exportDualResult() {
  const mode = dualParams.global.mode
  await exportResult(
    dualResultRawB64.value, dualResultRawShape.value, mode,
    `sim_dual_${mode}.${mode === 'cake' ? 'npy' : 'tiff'}`, 'dual',
    dualResultFileId.value, dualResultFullShape.value,
  )
}

function onSingleFilesSelected(files) {
  singleFiles.value = files
}

async function onSinglePoniFilesSelected(files) {
  singlePoniFiles.value = files
  if (!files.length) {
    singlePoniFileId.value = null
    poniDetectorName.value = ''
    return
  }
  try {
    const fd = new FormData()
    fd.append('file', files[0])
    const up = await xrdUploadFile(fd)
    const fileId = up.data?.fileId
    singlePoniFileId.value = fileId
    const parsed = await xrdParsePoni(fileId)
    const g = parsed.data || {}
    const updates = {}
    if (g.wavelength_A != null) updates.wavelength = g.wavelength_A
    if (g.sd_mm != null) updates.sd = g.sd_mm
    if (g.centerx_px != null) updates.centerx = g.centerx_px
    if (g.centery_px != null) updates.centery = g.centery_px
    if (g.pixelSize_um != null) updates.pixelSize = g.pixelSize_um
    if (g.imgW != null) updates.imgW = g.imgW
    if (g.imgH != null) updates.imgH = g.imgH
    Object.assign(singleParams, updates)
    poniDetectorName.value = g.detector || ''
  } catch (err) {
    poniDetectorName.value = ''
    singlePoniFileId.value = null
    consoleLogs.single.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}

// Upload a 2-D-integration processing_info file (json/txt) and use its q-χ
// grid to drive the cake image, so the simulated cake lines up with the
// measured one. Only fields present in the file are applied.
const singleProcessingInfoName = ref('')
async function onSingleProcessingInfoSelected(files) {
  if (!files.length) {
    singleProcessingInfoName.value = ''
    return
  }
  try {
    const fd = new FormData()
    fd.append('file', files[0])
    const up = await xrdUploadFile(fd)
    const grid = await xrdParseProcessingInfo(up.data?.fileId)
    const g = grid.data || {}
    const updates = {}
    if (g.qMin != null) updates.qMin = g.qMin
    if (g.qMax != null) updates.qMax = g.qMax
    if (g.chiMin != null) updates.chiMin = g.chiMin
    if (g.chiMax != null) updates.chiMax = g.chiMax
    if (g.nQ != null) updates.nQ = g.nQ
    if (g.nChi != null) updates.nChi = g.nChi
    Object.assign(singleParams, updates)
    singleProcessingInfoName.value = files[0].name
    consoleLogs.single.push(t('logs.xrd.processingInfoLoaded', { unit: g.xUnit || '?' }))
  } catch (err) {
    singleProcessingInfoName.value = ''
    consoleLogs.single.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}

// Parse a peak_result.txt body into {h,k,l,q,chi,intensity} rows (7- or 6-col).
function parsePeakResultText(text) {
  return text.trim().split('\n')
    .map(l => l.trim())
    .filter(l => l && !l.startsWith('#'))
    .map(line => {
      const p = line.split(/\s+/)
      if (p.length < 6) return null
      const h = parseInt(p[0])
      if (Number.isNaN(h)) return null           // header row
      return {
        h, k: parseInt(p[1]), l: parseInt(p[2]),
        q: parseFloat(p[3]), chi: parseFloat(p[4]), intensity: parseFloat(p[5]),
      }
    })
    .filter(Boolean)
}

const runSimulation = async (type) => {
  runStatus.value = 'running'
  const logKey = type === 'single' ? 'single' : 'dual'
  taskStatus[logKey] = 'running'
  consoleLogs[logKey] = [type === 'single' ? t('logs.xrd.singleSimStart') : t('logs.xrd.dualSimStart')]
  try {
    let result
    if (type === 'single') {
      // peak_result.txt (h k l q chi intensity [belongto]) is the sole peak source
      const text = await singleFiles.value[0].text()
      const peaks = parsePeakResultText(text)

      const payload = {
        peaks,
        sigmaQ: singleParams.sigmaQ,
        sigmaChi: singleParams.sigmaChi,
        mode: singleParams.mode,
        kernel: singleParams.kernel,
        expandSymmetry: singleParams.expandSymmetry,
      }

      if (singleParams.mode === 'cake') {
        payload.grid = {
          qMin: singleParams.qMin,
          qMax: singleParams.qMax,
          chiMin: singleParams.chiMin,
          chiMax: singleParams.chiMax,
          nQ: singleParams.nQ,
          nChi: singleParams.nChi,
        }
      } else {
        // 2D detector: PONI (if uploaded) + editable geometry overrides
        if (singlePoniFileId.value) payload.poniFileId = singlePoniFileId.value
        payload.detector = {
          wavelength_A: singleParams.wavelength,
          sd_mm: singleParams.sd,
          centerx_px: singleParams.centerx,
          centery_px: singleParams.centery,
          pixelSize_um: singleParams.pixelSize,
          imgW: parseInt(singleParams.imgW),
          imgH: parseInt(singleParams.imgH),
        }
      }

      result = await xrdRunSimulation(payload)
      const shape = result.data?.shape || []
      const b64 = result.data?.imageBase64
      if (b64) {
        singleResultRawB64.value = b64
        singleResultRawShape.value = shape
        // Full-resolution image lives on the server (fileId); the payload
        // may carry a decimated detector preview.
        singleResultFileId.value = result.data?.fileId || null
        singleResultFullShape.value = result.data?.fullShape || null
        if (singleParams.mode === 'cake') {
          const hm = buildHeatmap(
            b64, shape,
            linspace(singleParams.qMin, singleParams.qMax, singleParams.nQ),
            linspace(singleParams.chiMin, singleParams.chiMax, singleParams.nChi),
          )
          singleResultImage.value = hm?.z || null
          singleResultX.value = hm?.xAxis || null
          singleResultY.value = hm?.yAxis || null
          singleResultXTitle.value = 'q (Å⁻¹)'
          singleResultYTitle.value = 'χ (°)'
        } else {
          const hm = buildHeatmap(b64, shape, null, null)
          singleResultImage.value = hm?.z || null
          singleResultX.value = null
          singleResultY.value = null
          singleResultXTitle.value = ''
          singleResultYTitle.value = ''
        }
        // Size the contrast slider to this image and clear any prior crop.
        if (singleResultImage.value) {
          const [mn, mx] = arrayMinMax(singleResultImage.value)
          singleResultMin.value = mn
          singleResultMax.value = mx
          singleContrastMin.value = mn
          singleContrastMax.value = mx
          singleCropX.value = null
          singleCropY.value = null
        }
      }
    } else {
      // Dual phase: each phase uploads its own peak_result.txt
      const textA = await dualPhaseAFiles.value[0].text()
      const textB = await dualPhaseBFiles.value[0].text()
      const peaksA = parsePeakResultText(textA)
      const peaksB = parsePeakResultText(textB)
      const nPts = dualParams.global.resolution || 512
      result = await xrdRunDualSimulation({
        peaksA,
        peaksB,
        ratio: dualParams.phaseA.weight,
        sigmaQ: dualParams.phaseA.sigma,
        sigmaChi: dualParams.phaseA.sigma,
        mode: dualParams.global.mode,
        kernel: dualParams.global.kernel,
        grid: {
          qMin: 0.0,
          qMax: 25.0,
          chiMin: -180.0,
          chiMax: 180.0,
          nQ: nPts,
          nChi: nPts,
        },
        expandSymmetry: dualParams.global.expandSymmetry,
      })
      if (result.data?.imageBase64) {
        const dshape = result.data?.shape || []
        dualResultRawB64.value = result.data.imageBase64
        dualResultRawShape.value = dshape
        dualResultFileId.value = result.data?.fileId || null
        dualResultFullShape.value = result.data?.fullShape || null
        if (dualParams.global.mode === 'cake') {
          const hm = buildHeatmap(
            result.data.imageBase64, dshape,
            linspace(0.0, 25.0, nPts), linspace(-180.0, 180.0, nPts),
          )
          dualResultImage.value = hm?.z || null
          dualResultX.value = hm?.xAxis || null
          dualResultY.value = hm?.yAxis || null
          dualResultXTitle.value = 'q (Å⁻¹)'
          dualResultYTitle.value = 'χ (°)'
        } else {
          const hm = buildHeatmap(result.data.imageBase64, dshape, null, null)
          dualResultImage.value = hm?.z || null
          dualResultX.value = null
          dualResultY.value = null
          dualResultXTitle.value = ''
          dualResultYTitle.value = ''
        }
        // Size the contrast slider to this image and clear any prior crop.
        if (dualResultImage.value) {
          const [mn, mx] = arrayMinMax(dualResultImage.value)
          dualResultMin.value = mn
          dualResultMax.value = mx
          dualContrastMin.value = mn
          dualContrastMax.value = mx
          dualCropX.value = null
          dualCropY.value = null
        }
      }
    }
    consoleLogs[logKey].push(type === 'single' ? t('logs.xrd.singleSimDone') : t('logs.xrd.dualSimDone'))
    taskStatus[logKey] = 'completed'
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs[logKey].push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus[logKey] = 'error'
    runStatus.value = 'failed'
  }
}

// ---- Dual Phase state ----
const dualPhaseAFiles = ref([])
const dualPhaseBFiles = ref([])
const dualParams = reactive({
  phaseA: { weight: 0.5, sigma: 0.05 },
  phaseB: { weight: 0.5, sigma: 0.05 },
  global: { mode: 'cake', kernel: 'fast', resolution: 512, expandSymmetry: false },
})
const dualPhaseParamFields = computed(() => [
  { key: 'weight', label: t('xrd.dual.weight'), type: 'slider', min: 0, max: 1, step: 0.01 },
  { key: 'sigma', label: t('xrd.dual.sigma'), type: 'number', step: 0.001 },
])
const dualGlobalFields = computed(() => [
  { key: 'mode', label: t('xrd.dual.outputMode'), type: 'select', options: [
    { value: 'cake', label: t('xrd.single.modes.cake') },
    { value: 'detector', label: t('xrd.single.modes.detector') },
  ]},
  { key: 'kernel', label: t('xrd.single.kernel'), type: 'select', options: [
    { value: 'fast', label: t('xrd.single.kernels.fast') },
    { value: 'legacy', label: t('xrd.single.kernels.legacy') },
  ]},
  { key: 'resolution', label: t('xrd.dual.resolution'), type: 'number', step: 1, min: 64 },
  { key: 'expandSymmetry', label: t('xrd.single.symmetry'), type: 'checkbox', help: t('xrd.single.symmetryHelp') },
])
const dualResultImage = ref(null)
const dualResultX = ref(null)
const dualResultY = ref(null)
const dualResultXTitle = ref('')
const dualResultYTitle = ref('')
// Full-resolution raw image (base64 float32 + shape) kept for .tiff export.
const dualResultRawB64 = ref(null)
const dualResultRawShape = ref([])
// Twin of the single-phase refs: full image fetched by fileId at export time.
const dualResultFileId = ref(null)
const dualResultFullShape = ref([])
// Contrast window + crop bands for the dual-phase result (twin of single).
const dualResultMin = ref(0)
const dualResultMax = ref(1)
const dualContrastMin = ref(0)
const dualContrastMax = ref(1)
const dualContrastStep = computed(() => {
  const span = dualResultMax.value - dualResultMin.value
  return span > 0 ? +(span / 200).toPrecision(3) : 0.001
})
const dualCropX = ref(null)
const dualCropY = ref(null)

// Both phases must upload a peak_result.txt before dual can run.
const canRunDual = computed(() =>
  dualPhaseAFiles.value.length > 0 && dualPhaseBFiles.value.length > 0)
const needBothPhasesHint = computed(() => !canRunDual.value)

function onDualPhaseAFilesSelected(files) {
  dualPhaseAFiles.value = files
}

function onDualPhaseBFilesSelected(files) {
  dualPhaseBFiles.value = files
}

// ===================== Result image controls =====================
// Box-select on the single result clamps the visible x/y band to the selection
// (physical coords: q/χ for cake, pixels for detector). Reset returns to full.
function onSingleRegionSelected(region) {
  if (region.xRange && region.xRange.length === 2) {
    singleCropX.value = [Math.min(...region.xRange), Math.max(...region.xRange)]
  }
  if (region.yRange && region.yRange.length === 2) {
    singleCropY.value = [Math.min(...region.yRange), Math.max(...region.yRange)]
  }
}
function onDualRegionSelected(region) {
  if (region.xRange && region.xRange.length === 2) {
    dualCropX.value = [Math.min(...region.xRange), Math.max(...region.xRange)]
  }
  if (region.yRange && region.yRange.length === 2) {
    dualCropY.value = [Math.min(...region.yRange), Math.max(...region.yRange)]
  }
}
function resetSingleContrast() {
  singleContrastMin.value = singleResultMin.value
  singleContrastMax.value = singleResultMax.value
}
function resetDualContrast() {
  dualContrastMin.value = dualResultMin.value
  dualContrastMax.value = dualResultMax.value
}
function resetSingleCrop() {
  singleCropX.value = null
  singleCropY.value = null
}
function resetDualCrop() {
  dualCropX.value = null
  dualCropY.value = null
}

// ---- Experiment upload / clear (single-image model) ----
async function onSingleExpFilesSelected(files) {
  if (!files || !files.length) return
  try {
    const fd = new FormData()
    fd.append('file', files[0])
    const up = await xrdUploadFile(fd)
    const fileId = up.data?.fileId
    if (!fileId) throw new Error('Upload failed')

    const expResp = await xrdLoadExperiment(fileId, compareSimMode.value)
    const b64 = expResp.data?.imageBase64
    const shape = expResp.data?.shape || []
    if (!b64 || shape.length < 2) throw new Error('No image data returned')

    // Decimate once; physical axes are re-derived per compare context.
    const hm = buildHeatmap(b64, shape, null, null)
    if (!hm?.z?.length) throw new Error('Empty image data')
    const [mn, mx] = arrayMinMax(hm.z)
    singleExpBaseZ.value = hm.z
    singleExpRowIdx.value = hm.rowIdx
    singleExpColIdx.value = hm.colIdx
    singleExpSrcRows.value = hm.srcRows
    singleExpSrcCols.value = hm.srcCols
    singleExpMin.value = mn
    singleExpMax.value = mx
    // Fresh image: snap the window to its own range and clear any alignment.
    singleExpContrastMin.value = mn
    singleExpContrastMax.value = mx
    singleExpFlipH.value = false
    singleExpFlipV.value = false
    singleExpName.value = files[0].name || up.data?.originalName || fileId
    singleExpLoaded.value = true
    consoleLogs.single.push(t('xrd.single.compare.expLoadedLog'))
  } catch (err) {
    clearSingleExp()
    consoleLogs.single.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}

function clearSingleExp() {
  singleExpName.value = ''
  singleExpLoaded.value = false
  singleExpBaseZ.value = null
  singleExpRowIdx.value = null
  singleExpColIdx.value = null
  singleExpSrcRows.value = 0
  singleExpSrcCols.value = 0
  singleExpMin.value = 0
  singleExpMax.value = 1
  singleExpContrastMin.value = 0
  singleExpContrastMax.value = 1
  singleExpFlipH.value = false
  singleExpFlipV.value = false
}

// ---- Experiment image controls (contrast + 归正) ----
function resetSingleExpContrast() {
  singleExpContrastMin.value = singleExpMin.value
  singleExpContrastMax.value = singleExpMax.value
}
// Rotate 180° = both flips toggled together (commutes with individual flips,
// so the three buttons compose into every orientation reachable without
// swapping the q/χ axes).
function toggleSingleExpRot180() {
  singleExpFlipH.value = !singleExpFlipH.value
  singleExpFlipV.value = !singleExpFlipV.value
}
</script>

<style scoped>
.xrd-sim-page {
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
  max-width: 960px;
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

/* Phase sections */
.phase-section {
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
}

.phase-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
  margin: 0 0 12px;
}

/* Results */
.result-preview {
  margin-top: 24px;
  border-top: 1px solid var(--color-border);
  padding-top: 20px;
}

.result-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 12px;
}

.result-meta {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0 0 8px;
}

.result-table-wrap {
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid var(--color-border);
}

.result-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.result-table th {
  padding: 8px 12px;
  text-align: right;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: var(--color-neutral);
  border-bottom: 1px solid var(--color-border);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-size: 11px;
}

.result-table td {
  padding: 6px 12px;
  text-align: right;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border);
  font-family: 'JetBrains Mono', monospace;
}

.result-table tr:last-child td {
  border-bottom: none;
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

.btn-primary:hover {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ---- Result image controls (contrast + crop) ---- */
.result-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
}
@media (max-width: 720px) {
  .result-controls { grid-template-columns: 1fr; }
}
.contrast-block,
.crop-block {
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.crop-block { justify-content: space-between; }
.contrast-field { display: flex; flex-direction: column; gap: 4px; }
.contrast-block-label,
.contrast-field-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.contrast-slider {
  width: 100%;
  height: 4px;
  accent-color: var(--color-primary);
  cursor: pointer;
}
.contrast-num {
  width: 100%;
  height: 26px;
  padding: 0 8px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text);
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
}
.contrast-num:focus { border-color: var(--color-primary); }
.btn-row { display: flex; gap: 8px; }
.btn-align { white-space: nowrap; }
.btn-align--active {
  border-color: var(--color-primary);
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
  color: var(--color-primary);
}

/* ---- Shared experiment comparison card (single upload, stacked panes) ---- */
.compare-card {
  max-width: 960px;
  margin-top: 20px;
}

/* Card header: title + reset-to-defaults action */
.compare-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.compare-card-head .result-title { margin: 0; }

/* Colormap select inside the comparison settings */
.compare-colorscale {
  width: 100%;
  height: 28px;
  padding: 0 8px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text);
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
}
.compare-colorscale:focus { border-color: var(--color-primary); }

/* Upload row: single experiment file + active-image chip / off switch */
.compare-upload-row {
  display: flex;
  align-items: stretch;
  gap: 12px;
  margin-bottom: 14px;
}
.compare-upload-row .file-upload { flex: 1 1 320px; min-width: 0; }
.compare-upload-row .drop-zone { min-height: 76px; padding: 12px 16px; }
.compare-upload-row .drop-zone__icon { width: 22px; height: 22px; margin-bottom: 4px; }
.compare-active {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  flex-shrink: 0;
}
.compare-chip {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--color-primary);
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
  border-radius: 6px;
  padding: 4px 10px;
}
.btn-compare-off:hover {
  border-color: var(--color-error, #DC2626);
  color: var(--color-error, #DC2626);
}

.compare-settings { margin-top: 0; }

/* Stacked full-width panes — the simulation canvas followed directly by the
   experiment canvas, both as tall as the main result view. */
.compare-panes {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}
.compare-pane { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.compare-pane-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 20px;
}
.pane-export-btn {
  margin-left: auto;
  height: 22px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: 5px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.pane-export-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.compare-pane-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.compare-pane-tag--sim { background: var(--color-primary); }
.compare-pane-tag--exp { background: #D97706; }

.compare-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 240px;
  border: 1px dashed var(--color-border);
  border-radius: 8px;
  color: var(--color-text-secondary);
}
.compare-placeholder svg {
  width: 40px;
  height: 40px;
  opacity: 0.5;
}
.compare-placeholder p { margin: 0; font-size: 13px; }

@media (max-width: 720px) {
  .compare-upload-row { flex-direction: column; }
  .compare-active { flex-direction: row; align-items: center; }
}

/* Fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 1024px) {
  .sidebar {
    width: 72px;
  }

  .tab-label,
  .sidebar-footer {
    display: none;
  }

  .tab-item {
    justify-content: center;
    padding: 0;
    gap: 0;
  }

  .tab-item.active::before {
    display: none;
  }
}
</style>
