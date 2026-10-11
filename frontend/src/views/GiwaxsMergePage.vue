<template>
  <div class="giwaxs-page">
    <header class="page-head">
      <div class="page-head__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2v20M2 12h20" />
          <circle cx="12" cy="12" r="3.2" />
          <path d="M4.9 4.9l2.2 2.2M19.1 4.9l-2.2 2.2M4.9 19.1l2.2-2.2M19.1 19.1l-2.2-2.2" />
        </svg>
      </div>
      <div class="page-head__copy">
        <h2 class="page-head__title">{{ t('giwaxs.title') }}</h2>
        <p class="page-head__desc">{{ t('giwaxs.header') }}</p>
      </div>
    </header>

    <div class="giwaxs-grid">
      <!-- ============ Input column ============ -->
      <section class="panel panel--input">
        <!-- Data & calibration -->
        <div class="section">
          <div class="section__head">
            <h3>{{ t('giwaxs.data.title') }}</h3>
            <span class="section__hint">{{ t('giwaxs.data.desc') }}</span>
          </div>

          <div class="upload-grid upload-grid--single">
            <div class="upload-slot">
              <label class="slot-label">{{ t('giwaxs.data.imagesLabel') }}</label>
              <FileUpload :multiple="true" accept=".npy,.tif,.tiff,.edf,.cbf,.h5,.hdf5" @files-selected="(fs) => onImagesSelected(fs)" />
              <div v-if="imageFiles.length" class="file-chip-list">
                <span class="file-chip-count">{{ t('giwaxs.data.imageCount', { n: imageFiles.length }) }}</span>
                <div v-for="(f, i) in imageFiles" :key="f.fileId" class="file-chip">
                  <span class="file-chip__name" :title="f.name">{{ f.name }}</span>
                  <button class="file-chip__x" :title="t('giwaxs.data.removeOne')" @click="removeImage(i)">×</button>
                </div>
                <button class="file-chip-clear" @click="clearImages">{{ t('giwaxs.data.clearAll') }}</button>
              </div>
            </div>

            <div class="upload-grid">
              <div class="upload-slot">
                <label class="slot-label">{{ t('giwaxs.data.poniLabel') }}</label>
                <FileUpload :multiple="false" accept=".poni" @files-selected="(fs) => onPoniSelected(fs)" />
                <div v-if="poniFile" class="file-chip">
                  <span class="file-chip__name">{{ poniFile.name }}</span>
                  <button class="file-chip__x" @click="clearPoni">×</button>
                </div>
              </div>
              <div class="upload-slot">
                <label class="slot-label">{{ t('giwaxs.data.maskLabel') }}</label>
                <FileUpload :multiple="false" accept=".npy,.tif,.tiff,.edf" @files-selected="(fs) => onMaskSelected(fs)" />
                <div v-if="maskFile" class="file-chip">
                  <span class="file-chip__name">{{ maskFile.name }}</span>
                  <button class="file-chip__x" @click="maskFile = null">×</button>
                </div>
              </div>
            </div>
          </div>

          <!-- PONI summary card (X-FAIS style) -->
          <div v-if="poniInfo" class="poni-card">
            <div class="poni-card__title">{{ t('giwaxs.data.poniSummary.title') }} · {{ poniInfo.detector }}</div>
            <div class="poni-card__grid">
              <div class="poni-card__item">
                <span class="poni-card__k">λ</span>
                <span class="poni-card__v">{{ (poniInfo.wavelength * 10).toFixed(4) }} Å</span>
              </div>
              <div class="poni-card__item">
                <span class="poni-card__k">{{ t('giwaxs.data.poniSummary.distance') }}</span>
                <span class="poni-card__v">{{ (poniInfo.dist * 1000).toFixed(2) }} mm</span>
              </div>
              <div class="poni-card__item">
                <span class="poni-card__k">{{ t('giwaxs.data.poniSummary.pixel') }}</span>
                <span class="poni-card__v">{{ (poniInfo.pixel1 * 1e6).toFixed(1) }} × {{ (poniInfo.pixel2 * 1e6).toFixed(1) }} µm</span>
              </div>
              <div class="poni-card__item">
                <span class="poni-card__k">{{ t('giwaxs.data.poniSummary.beamCenter') }}</span>
                <span class="poni-card__v">({{ poniInfo.beamCenterX.toFixed(1) }}, {{ poniInfo.beamCenterY.toFixed(1) }}) px</span>
              </div>
              <div class="poni-card__item poni-card__item--wide">
                <span class="poni-card__k">rot1 / rot2 / rot3</span>
                <span class="poni-card__v">{{ fmtDeg(poniInfo.rot1Deg) }}° / {{ fmtDeg(poniInfo.rot2Deg) }}° / {{ fmtDeg(poniInfo.rot3Deg) }}°</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Per-image rotation table (the GIWAXS-specific step) -->
        <div class="section">
          <div class="section__head">
            <h3>{{ t('giwaxs.rot.title') }}</h3>
            <span class="section__hint">{{ t('giwaxs.rot.desc') }}</span>
          </div>

          <div v-if="!imageFiles.length" class="rot-empty">{{ t('giwaxs.rot.needImages') }}</div>
          <template v-else>
            <div class="rot-table-wrap">
              <table class="rot-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{{ t('giwaxs.rot.name') }}</th>
                    <th>rot3 (°)</th>
                    <th v-if="lastRun">{{ t('giwaxs.rot.appliedCol') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(f, i) in imageFiles" :key="f.fileId">
                    <td class="rot-idx">{{ i + 1 }}</td>
                    <td class="rot-name" :title="f.name">{{ f.name }}</td>
                    <td>
                      <input class="rot-input" type="number" step="any" :placeholder="rotPh()"
                        :value="rotOf(f.fileId)" @input="setRot(f.fileId, $event)" />
                    </td>
                    <td v-if="lastRun" class="rot-applied">{{ appliedText(f) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="rot-batch">
              <span class="rot-batch__label">{{ t('giwaxs.rot.batchTitle') }}</span>
              <label class="rot-batch__field">{{ t('giwaxs.rot.batchStart') }}
                <input class="rot-input" type="number" step="any" v-model.number="batchRot.start" />
              </label>
              <label class="rot-batch__field">{{ t('giwaxs.rot.batchStep') }}
                <input class="rot-input" type="number" step="any" v-model.number="batchRot.step" />
              </label>
              <button class="btn btn--ghost btn--sm" @click="applyBatchRot">{{ t('giwaxs.rot.batchGenerate') }}</button>
              <span v-if="batchPreview" class="rot-batch__preview">→ {{ batchPreview }}</span>
            </div>
            <p class="hint-line">{{ t('giwaxs.rot.batchHint') }}</p>
          </template>
        </div>

        <!-- Fiber geometry & corrections (X-FAIS settings) -->
        <div class="section">
          <button class="section-toggle" @click="geomOpen = !geomOpen">
            <svg class="chev" :class="{ open: geomOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9" /></svg>
            <h3>{{ t('giwaxs.geom.title') }}</h3>
          </button>
          <div v-show="geomOpen" class="section__body">
            <div class="axis-grid">
              <div class="field">
                <label>{{ t('giwaxs.geom.sampleOrientation') }}</label>
                <select v-model.number="fiber.sampleOrientation">
                  <option v-for="o in ORIENTATIONS" :key="o.value" :value="o.value">{{ o.value }} · {{ t('giwaxs.geom.ori_' + o.value) }}</option>
                </select>
              </div>
              <div class="field">
                <label>{{ t('giwaxs.geom.incidentAngle') }}</label>
                <input type="number" step="any" v-model.number="fiber.incidentAngleDeg" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.geom.tiltAngle') }}</label>
                <input type="number" step="any" v-model.number="fiber.tiltAngleDeg" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.geom.polarization') }}</label>
                <input type="number" min="-1" max="1" step="0.01" :placeholder="t('giwaxs.geom.polarizationPh')"
                  v-model.number="fiber.polarizationFactor" />
              </div>
            </div>
            <label class="check-row">
              <input type="checkbox" v-model="fiber.correctSolidAngle" />
              <span>{{ t('giwaxs.geom.correctSolidAngle') }}</span>
            </label>
          </div>
        </div>

        <!-- Integration params -->
        <div class="section">
          <button class="section-toggle" @click="integOpen = !integOpen">
            <svg class="chev" :class="{ open: integOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9" /></svg>
            <h3>{{ t('giwaxs.integ.title') }}</h3>
          </button>
          <div v-show="integOpen" class="section__body">
            <div class="axis-grid">
              <div class="field">
                <label>{{ t('giwaxs.integ.unitIp') }}</label>
                <select v-model="fiber.unitIp">
                  <option v-for="u in UNIT_IP" :key="u" :value="u">{{ u }}</option>
                </select>
              </div>
              <div class="field">
                <label>{{ t('giwaxs.integ.unitOop') }}</label>
                <select v-model="fiber.unitOop">
                  <option v-for="u in UNIT_OOP" :key="u" :value="u">{{ u }}</option>
                </select>
              </div>
            </div>

            <div class="seg">
              <button :class="['seg__btn', { active: fiber.autoRange }]" @click="fiber.autoRange = true">{{ t('giwaxs.integ.autoRange') }}</button>
              <button :class="['seg__btn', { active: !fiber.autoRange }]" @click="fiber.autoRange = false">{{ t('giwaxs.integ.manualRange') }}</button>
            </div>
            <p v-if="fiber.autoRange" class="hint-line">{{ t('giwaxs.integ.autoRangeHint') }}</p>
            <div v-else class="axis-grid axis-grid--4">
              <div class="field">
                <label>{{ t('giwaxs.integ.ipMin') }}</label>
                <input type="number" step="any" v-model.number="fiber.ipMin" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.integ.ipMax') }}</label>
                <input type="number" step="any" v-model.number="fiber.ipMax" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.integ.oopMin') }}</label>
                <input type="number" step="any" v-model.number="fiber.oopMin" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.integ.oopMax') }}</label>
                <input type="number" step="any" v-model.number="fiber.oopMax" />
              </div>
            </div>

            <div class="axis-grid axis-grid--3">
              <div class="field">
                <label>{{ t('giwaxs.integ.nptIp') }}</label>
                <input type="number" min="32" max="4096" step="32" v-model.number="fiber.nptIp" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.integ.nptOop') }}</label>
                <input type="number" min="32" max="4096" step="32" v-model.number="fiber.nptOop" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.integ.method') }}</label>
                <select v-model="fiber.method">
                  <option value="auto">{{ t('giwaxs.integ.methodAuto') }}</option>
                  <option v-for="m in METHODS" :key="m" :value="m">{{ m }}</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- Merge settings (same semantics as 2D integration processing) -->
        <div class="section">
          <div class="section__head">
            <h3>{{ t('giwaxs.merge.title') }}</h3>
            <span class="section__hint">{{ t('giwaxs.merge.desc') }}</span>
          </div>
          <div class="axis-grid">
            <div class="field">
              <label>{{ t('giwaxs.merge.method') }}</label>
              <select v-model="mergeParams.mergeMethod">
                <option v-for="m in MERGE_METHODS" :key="m" :value="m">{{ t('giwaxs.merge.methods.' + m) }}</option>
              </select>
            </div>
            <div class="field">
              <label>{{ t('giwaxs.merge.maskLowerBound') }}</label>
              <input type="number" step="any" :placeholder="t('giwaxs.merge.maskLowerBoundPh')"
                v-model.number="mergeParams.maskLowerBound" />
            </div>
          </div>
          <p class="hint-line">{{ t('giwaxs.merge.maskLowerBoundHelp') }}</p>
        </div>

        <!-- Action bar + console -->
        <div class="action-bar">
          <button class="btn btn--primary" :disabled="!canRun || busy" @click="run">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5,3 19,12 5,21" /></svg>
            {{ t('giwaxs.actions.run') }}
          </button>
          <button class="btn btn--ghost" @click="reset">{{ t('giwaxs.actions.reset') }}</button>
        </div>
        <Console :logs="logs" />
      </section>

      <!-- ============ Result column ============ -->
      <section class="panel panel--result">
        <div class="section__head">
          <h3>{{ t('giwaxs.result.title') }}</h3>
          <div v-if="result" class="stats">
            <span class="stat"><b>{{ t('giwaxs.result.grid') }}</b> {{ result.nptIp }}×{{ result.nptOop }}</span>
            <span class="stat"><b>IP</b> {{ result.unitIp }}</span>
            <span class="stat"><b>OOP</b> {{ result.unitOop }}</span>
            <span class="stat"><b>{{ t('giwaxs.result.images') }}</b> {{ okImageCount }}</span>
            <span class="stat" v-if="result.info.uncoveredFraction != null">
              <b>{{ t('giwaxs.result.uncovered') }}</b> {{ (result.info.uncoveredFraction * 100).toFixed(1) }}%
            </span>
            <span class="stat"><b>{{ t('giwaxs.result.min') }}</b> {{ formatNum(result.minIntensity) }}</span>
            <span class="stat"><b>{{ t('giwaxs.result.max') }}</b> {{ formatNum(result.maxIntensity) }}</span>
          </div>
        </div>

        <div v-if="result" class="result-canvas">
          <ImageCanvas
            :image-data="result.preview"
            :x-axis="result.ipAxis"
            :y-axis="result.oopAxis"
            :x-axis-title="result.unitIp"
            :y-axis-title="result.unitOop"
            :show-colorbar="false"
            :height="560"
            :zmin="contrastMin"
            :zmax="contrastMax"
            :aspect-ratio="'1 / 1'"
          />
          <div class="contrast-controls">
            <div class="contrast-row">
              <label>{{ t('giwaxs.result.contrastMin') }} · {{ formatNum(contrastMin) }}</label>
              <input type="range" :min="floor" :max="ceil" :step="stepC" v-model.number="contrastMin" />
            </div>
            <div class="contrast-row">
              <label>{{ t('giwaxs.result.contrastMax') }} · {{ formatNum(contrastMax) }}</label>
              <input type="range" :min="floor" :max="ceil" :step="stepC" v-model.number="contrastMax" />
            </div>
            <button class="btn btn--ghost btn--sm" @click="resetContrast">{{ t('giwaxs.result.contrastReset') }}</button>
          </div>
        </div>
        <div v-else class="result-empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">
            <path d="M12 2v20M2 12h20" /><circle cx="12" cy="12" r="3.2" />
          </svg>
          <p>{{ busy ? t('giwaxs.status.running') : t('giwaxs.status.empty') }}</p>
        </div>

        <!-- Per-image fiber maps -->
        <div v-if="result && okImages.length" class="result-thumbs">
          <div class="thumbs-label">{{ t('giwaxs.result.perImageTitle') }}</div>
          <div class="thumbs-row">
            <div v-for="(it, i) in okImages" :key="i"
              :class="['thumb', { active: i === perImageIdx }]" :title="thumbTitle(it)"
              @click="perImageIdx = i">
              <canvas :ref="(el) => setThumbRef(el, i)" class="thumb__canvas" width="120" height="120"></canvas>
              <span class="thumb__name">{{ it.name }}</span>
              <span class="thumb__meta">{{ rotTag(it) }} · {{ (it.coverage * 100).toFixed(0) }}%</span>
            </div>
          </div>
          <ImageCanvas
            :image-data="okImages[perImageIdx] && okImages[perImageIdx].preview"
            :x-axis="result.ipAxis"
            :y-axis="result.oopAxis"
            :x-axis-title="result.unitIp"
            :y-axis-title="result.unitOop"
            :title="okImages[perImageIdx] && okImages[perImageIdx].name"
            :show-colorbar="false"
            :height="360"
            :show-toolbar="false"
            :aspect-ratio="'1 / 1'"
          />
        </div>

        <!-- Export -->
        <div v-if="result" class="section export-section">
          <div class="section__head">
            <h3>{{ t('giwaxs.exportSec.title') }}</h3>
          </div>
          <div class="export-row">
            <button class="btn btn--accent" :disabled="busyExport" @click="exportZip(false)">
              {{ t('giwaxs.exportSec.btnZip') }}
            </button>
            <label class="check-row">
              <input type="checkbox" v-model="exportWithPng" />
              <span>{{ t('giwaxs.exportSec.includePng') }}</span>
            </label>
            <button class="btn btn--ghost" :disabled="busyExport || !pngPreviewUrl" @click="downloadPng">
              {{ t('giwaxs.exportSec.btnDownloadPng') }}
            </button>
            <button class="btn btn--ghost" :disabled="!result" @click="sendToQzSlice">
              {{ t('giwaxs.exportSec.sendQzSlice') }}
            </button>
          </div>

          <button class="section-toggle" @click="pngOpen = !pngOpen">
            <svg class="chev" :class="{ open: pngOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9" /></svg>
            <h3>{{ t('giwaxs.exportSec.pngSettings') }}</h3>
          </button>
          <div v-show="pngOpen" class="section__body">
            <div class="axis-grid">
              <div class="field">
                <label>{{ t('giwaxs.exportSec.cmap') }}</label>
                <select v-model="png.cmap">
                  <option v-for="c in PNG_CMAPS" :key="c" :value="c">{{ c }}</option>
                </select>
              </div>
              <div class="field">
                <label>{{ t('giwaxs.exportSec.titleField') }}</label>
                <input type="text" v-model="png.title" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.exportSec.dpi') }}</label>
                <input type="number" min="50" max="600" step="10" v-model.number="png.dpi" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.exportSec.logFloor') }}</label>
                <input type="number" step="any" v-model.number="png.logFloor" :disabled="!png.useLog" />
              </div>
            </div>
            <div class="axis-grid" v-if="png.climMode === 'manual'">
              <div class="field">
                <label>{{ t('giwaxs.exportSec.climMin') }}</label>
                <input type="number" step="any" v-model.number="png.climMin" />
              </div>
              <div class="field">
                <label>{{ t('giwaxs.exportSec.climMax') }}</label>
                <input type="number" step="any" v-model.number="png.climMax" />
              </div>
            </div>
            <div class="png-checks">
              <label class="check-row"><input type="checkbox" v-model="png.useLog" /><span>{{ t('giwaxs.exportSec.useLog') }}</span></label>
              <label class="check-row"><input type="checkbox" v-model="png.flipX" /><span>{{ t('giwaxs.exportSec.flipX') }}</span></label>
              <label class="check-row"><input type="checkbox" v-model="png.flipY" /><span>{{ t('giwaxs.exportSec.flipY') }}</span></label>
              <label class="check-row"><input type="checkbox" v-model="png.showColorbar" /><span>{{ t('giwaxs.exportSec.showColorbar') }}</span></label>
              <div class="seg seg--sm">
                <button :class="['seg__btn', { active: png.climMode === 'auto' }]" @click="png.climMode = 'auto'">{{ t('giwaxs.exportSec.auto') }}</button>
                <button :class="['seg__btn', { active: png.climMode === 'manual' }]" @click="png.climMode = 'manual'">{{ t('giwaxs.exportSec.manual') }}</button>
              </div>
            </div>
            <div class="export-row">
              <button class="btn btn--ghost btn--sm" :disabled="busyExport" @click="renderPngPreview">
                {{ busyExport ? t('giwaxs.exportSec.rendering') : t('giwaxs.exportSec.btnRender') }}
              </button>
            </div>
            <img v-if="pngPreviewUrl" :src="pngPreviewUrl" class="png-preview" alt="GIWAXS PNG preview" />
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import FileUpload from '@/components/FileUpload.vue'
import ImageCanvas from '@/components/ImageCanvas.vue'
import {
  giwaxsUploadFiles,
  giwaxsParsePoni,
  giwaxsRunMerge,
  giwaxsRenderPng,
  giwaxsExportZip
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
const router = useRouter()

// ---- Constants (X-FAIS fiber units / methods) ----
const UNIT_IP = [
  'qip_nm^-1', 'qip_A^-1',
  'qxgi_nm^-1', 'qygi_nm^-1', 'qzgi_nm^-1', 'qtot_nm^-1',
  'qxgi_A^-1', 'qygi_A^-1', 'qzgi_A^-1', 'qtot_A^-1',
  'scattering_angle_horz_rad', 'exit_angle_horz_rad', 'exit_angle_horz_deg',
  'chigi_rad', 'chigi_deg'
]
const UNIT_OOP = [
  'qoop_nm^-1', 'qoop_A^-1',
  'qxgi_nm^-1', 'qygi_nm^-1', 'qzgi_nm^-1', 'qtot_nm^-1',
  'qxgi_A^-1', 'qygi_A^-1', 'qzgi_A^-1', 'qtot_A^-1',
  'scattering_angle_vert_rad', 'exit_angle_vert_rad', 'exit_angle_vert_deg',
  'chigi_rad', 'chigi_deg'
]
// Default range hints when switching units (X-FAIS UNIT_RANGE_HINT).
const UNIT_RANGE_HINT = {
  q_nm: [-20, 20], q_A: [-2, 2], qtot_nm: [0, 30], qtot_A: [0, 3],
  angle_rad: [-0.5, 0.5], angle_deg: [-30, 30], chi_rad: [-3.14, 3.14], chi_deg: [-180, 180]
}
function rangeHintFor(unit) {
  if (!unit) return null
  if (unit.startsWith('qtot')) return unit.includes('_A') ? UNIT_RANGE_HINT.qtot_A : UNIT_RANGE_HINT.qtot_nm
  if (unit.includes('_nm^-1')) return UNIT_RANGE_HINT.q_nm
  if (unit.includes('_A^-1')) return UNIT_RANGE_HINT.q_A
  if (unit.endsWith('_rad')) return unit.startsWith('chi') ? UNIT_RANGE_HINT.chi_rad : UNIT_RANGE_HINT.angle_rad
  if (unit.endsWith('_deg')) return unit.startsWith('chi') ? UNIT_RANGE_HINT.chi_deg : UNIT_RANGE_HINT.angle_deg
  return null
}
const ORIENTATIONS = [1, 2, 3, 4, 5, 6, 7, 8].map((v) => ({ value: v }))
const METHODS = ['splitpixel', 'csr', 'lut', 'bbox', 'numpy']
const MERGE_METHODS = ['mean', 'median', 'weighted', 'sequential']
const PNG_CMAPS = ['viridis', 'plasma', 'inferno', 'magma', 'cividis', 'turbo', 'hot', 'gray', 'coolwarm', 'rainbow']

// ---- Files ----
const imageFiles = ref([])          // [{fileId, name}]
const poniFile = ref(null)          // {fileId, name}
const maskFile = ref(null)          // {fileId, name}
const poniInfo = ref(null)

const rotMap = reactive({})         // fileId -> ''|number (rot3 override; '' = inherit PONI)
const batchRot = reactive({ start: null, step: null })

const fiber = reactive({
  sampleOrientation: 1,
  incidentAngleDeg: 0.0,
  tiltAngleDeg: 0.0,
  polarizationFactor: null,
  correctSolidAngle: true,
  unitIp: 'qip_A^-1',
  unitOop: 'qoop_A^-1',
  autoRange: true,
  ipMin: -2, ipMax: 2, oopMin: -2, oopMax: 2,
  nptIp: 448,
  nptOop: 448,
  method: 'auto'
})
const mergeParams = reactive({ mergeMethod: 'mean', maskLowerBound: null })

const geomOpen = ref(true)
const integOpen = ref(true)
const pngOpen = ref(false)

// ---- Run state ----
const busy = ref(false)
const busyExport = ref(false)
const result = ref(null)
const perImageIdx = ref(0)
const logs = ref([])
const lastRun = ref(null)           // {fileId -> rotApplied[3]}

// ---- Persistence ----
const LS_KEY = 'pre.giwaxsMerge.v1'
try {
  const saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null')
  if (saved) {
    Object.assign(fiber, saved.fiber || {})
    Object.assign(mergeParams, saved.mergeParams || {})
    if (saved.batchRot) {
      batchRot.start = saved.batchRot.start ?? null
      batchRot.step = saved.batchRot.step ?? null
    }
    // Unit-default migration (nm^-1 -> A^-1): the app used to ship
    // qip/qoop nm^-1 + -20..20 hint ranges as defaults. Machines that ran
    // the old build have exactly those stored; move them onto the new A^-1
    // defaults so the change actually reaches them. Custom values are kept.
    if (fiber.unitIp === 'qip_nm^-1' && fiber.unitOop === 'qoop_nm^-1') {
      fiber.unitIp = 'qip_A^-1'
      fiber.unitOop = 'qoop_A^-1'
    }
    if (fiber.ipMin === -20 && fiber.ipMax === 20 && fiber.oopMin === -20 && fiber.oopMax === 20) {
      fiber.ipMin = -2; fiber.ipMax = 2; fiber.oopMin = -2; fiber.oopMax = 2
    }
  }
} catch { /* ignore corrupt state */ }
watch([fiber, mergeParams, batchRot], () => {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({ fiber, mergeParams, batchRot }))
  } catch { /* quota — ignore */ }
}, { deep: true })

// ---- PNG export ----
const png = reactive({
  cmap: 'viridis', useLog: false, logFloor: 0.1, climMode: 'auto',
  climMin: null, climMax: null, flipX: false, flipY: false,
  title: '', dpi: 150, showColorbar: true
})
const exportWithPng = ref(false)
const pngPreviewUrl = ref(null)

// ---- Contrast (display-only) ----
const contrastMin = ref(null)
const contrastMax = ref(null)
const floor = computed(() => (result.value && result.value.minIntensity != null)
  ? Math.min(result.value.minIntensity, result.value.maxIntensity) : 0)
const ceil = computed(() => (result.value && result.value.minIntensity != null)
  ? Math.max(result.value.minIntensity, result.value.maxIntensity) : 1)
const stepC = computed(() => {
  const s = ceil.value - floor.value
  return s !== 0 ? Math.abs(s) / 200 : 0.001
})
function resetContrast() {
  contrastMin.value = floor.value
  contrastMax.value = ceil.value
}

const okImages = computed(() => (result.value ? result.value.images.filter((it) => it.ok) : []))
const okImageCount = computed(() => okImages.value.length)
const canRun = computed(() => imageFiles.value.length > 0 && !!poniFile.value)

// ---- Helpers ----
function log(line) { logs.value.push(line) }

function fmtDeg(v) { return (Math.round(v * 1000) / 1000).toString() }

function formatNum(v) {
  if (v == null || !Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(3)
  return String(Math.round(v * 1000) / 1000)
}

function rotOf(fileId) {
  if (!(fileId in rotMap)) rotMap[fileId] = ''
  return rotMap[fileId]
}
function setRot(fileId, ev) {
  const v = ev.target.value
  rotMap[fileId] = v === '' ? '' : Number(v)
}
function rotPh() {
  const info = poniInfo.value
  if (!info) return t('giwaxs.rot.inherit')
  return `${t('giwaxs.rot.poni')}: ${fmtDeg(info.rot3Deg)}`
}
function applyBatchRot() {
  const s = Number(batchRot.start) || 0
  const st = Number(batchRot.step) || 0
  imageFiles.value.forEach((f, i) => {
    rotMap[f.fileId] = s + i * st
  })
  log(t('giwaxs.rot.applied'))
}
const batchPreview = computed(() => {
  if (!imageFiles.value.length) return ''
  const s = Number(batchRot.start) || 0
  const st = Number(batchRot.step) || 0
  const vals = Array.from({ length: imageFiles.value.length }, (_, i) => fmtDeg(s + i * st))
  return vals.length > 8 ? vals.slice(0, 8).join(', ') + ', …' : vals.join(', ')
})
function appliedText(file) {
  const applied = lastRun.value && lastRun.value[file.name]
  if (!applied) return '—'
  return fmtDeg(applied[2])
}
function rotTag(it) {
  return fmtDeg(it.rotApplied[2])
}
function thumbTitle(it) {
  return `${it.name} · rot3=${rotTag(it)} · coverage=${(it.coverage * 100).toFixed(1)}%`
}
function toNumOrNull(v) { return (v === '' || v == null || !Number.isFinite(v)) ? null : Number(v) }

// ---- Upload handlers (upload immediately, store fileIds) ----
async function uploadAll(files, label) {
  const fd = new FormData()
  for (const f of files) fd.append('files', f, f.name)
  const res = await giwaxsUploadFiles(fd)
  const out = res.data.files.map((f) => ({ fileId: f.fileId, name: f.originalName, kind: f.kind }))
  if (label) log(`✓ ${label}: ${out.length} file(s)`)
  return out
}

async function onImagesSelected(files) {
  try {
    const up = await uploadAll(files)
    // keep .poni files out of the image list if the user mixed them in
    const imgs = up.filter((f) => f.kind !== 'poni')
    const ponis = up.filter((f) => f.kind === 'poni')
    imageFiles.value = imageFiles.value.concat(imgs)
    if (ponis.length && !poniFile.value) await acceptPoni(ponis[0])
    log(t('giwaxs.data.loaded', { n: imgs.length }))
  } catch (e) {
    log(`⚠ ${e.response?.data?.detail || e.message}`)
  }
}

async function acceptPoni(f) {
  poniFile.value = { fileId: f.fileId, name: f.name }
  try {
    const res = await giwaxsParsePoni(f.fileId)
    poniInfo.value = res.data
  } catch (e) {
    poniInfo.value = null
    log(`⚠ ${e.response?.data?.detail || e.message}`)
  }
}

async function onPoniSelected(files) {
  try {
    const up = await uploadAll(files)
    const p = up.find((f) => f.kind === 'poni') || up[0]
    if (p) await acceptPoni(p)
  } catch (e) {
    log(`⚠ ${e.response?.data?.detail || e.message}`)
  }
}

async function onMaskSelected(files) {
  try {
    const up = await uploadAll(files)
    if (up[0]) maskFile.value = { fileId: up[0].fileId, name: up[0].name }
  } catch (e) {
    log(`⚠ ${e.response?.data?.detail || e.message}`)
  }
}

function removeImage(i) {
  const f = imageFiles.value[i]
  delete rotMap[f.fileId]
  imageFiles.value.splice(i, 1)
}
function clearImages() {
  for (const f of imageFiles.value) delete rotMap[f.fileId]
  imageFiles.value = []
}
function clearPoni() {
  poniFile.value = null
  poniInfo.value = null
}

// Fill manual-range inputs with unit hints on unit switch
watch(() => [fiber.unitIp, fiber.unitOop], ([ip, oop]) => {
  if (!fiber.autoRange) {
    const hIp = rangeHintFor(ip)
    const hOop = rangeHintFor(oop)
    if (hIp) { fiber.ipMin = hIp[0]; fiber.ipMax = hIp[1] }
    if (hOop) { fiber.oopMin = hOop[0]; fiber.oopMax = hOop[1] }
  }
})

// ---- Run ----
function buildRequest() {
  return {
    images: imageFiles.value.map((f) => {
      return {
        imageFileId: f.fileId,
        name: f.name,
        rot1Deg: null,
        rot2Deg: null,
        rot3Deg: toNumOrNull(rotOf(f.fileId))
      }
    }),
    poniFileId: poniFile.value.fileId,
    maskFileId: maskFile.value ? maskFile.value.fileId : null,
    sampleOrientation: fiber.sampleOrientation,
    incidentAngleDeg: fiber.incidentAngleDeg || 0,
    tiltAngleDeg: fiber.tiltAngleDeg || 0,
    polarizationFactor: toNumOrNull(fiber.polarizationFactor),
    correctSolidAngle: fiber.correctSolidAngle,
    unitIp: fiber.unitIp,
    unitOop: fiber.unitOop,
    autoRange: fiber.autoRange,
    ipRange: fiber.autoRange ? null : [fiber.ipMin, fiber.ipMax],
    oopRange: fiber.autoRange ? null : [fiber.oopMin, fiber.oopMax],
    nptIp: fiber.nptIp,
    nptOop: fiber.nptOop,
    method: fiber.method === 'auto' ? null : fiber.method,
    mergeMethod: mergeParams.mergeMethod,
    maskLowerBound: toNumOrNull(mergeParams.maskLowerBound)
  }
}

async function run() {
  if (!canRun.value || busy.value) return
  busy.value = true
  result.value = null
  lastRun.value = null
  perImageIdx.value = 0
  log(t('giwaxs.status.runningLog', { n: imageFiles.value.length, npt: fiber.nptIp }))
  try {
    const res = await giwaxsRunMerge(buildRequest())
    result.value = res.data
    // backend echoes images in request order; key rotApplied by name for the table
    const byName = {}
    for (const it of res.data.images) byName[it.name] = it.rotApplied
    lastRun.value = byName
    for (const it of res.data.images) {
      log(it.ok
        ? `✓ ${it.name} · rot3=${rotTag(it)} · ${(it.coverage * 100).toFixed(1)}%`
        : `✗ ${it.name}: ${it.error}`)
    }
    log(t('giwaxs.status.doneLog', { method: mergeParams.mergeMethod, n: res.data.info.mergedImageCount }))
    resetContrast()
    await nextTick()
    drawAllThumbs()
  } catch (e) {
    log(`✗ ${e.response?.data?.detail || e.message}`)
  } finally {
    busy.value = false
  }
}

function reset() {
  clearImages()
  clearPoni()
  maskFile.value = null
  result.value = null
  lastRun.value = null
  logs.value = []
  pngPreviewUrl.value = null
}

// ---- Per-image thumbnails (native canvas + viridis, NaN → gray) ----
const thumbRefs = new Map()
function setThumbRef(el, i) {
  if (el) thumbRefs.set(i, el)
  else thumbRefs.delete(i)
}

function drawThumb(canvas, grid) {
  if (!canvas || !grid || !grid.length) return
  const nR = grid.length
  const nC = grid[0].length
  const flat = []
  let mn = Infinity
  let mx = -Infinity
  for (const row of grid) {
    for (const v of row) {
      if (v != null && Number.isFinite(v)) {
        flat.push(v)
        if (v < mn) mn = v
        if (v > mx) mx = v
      }
    }
  }
  const ctx = canvas.getContext('2d')
  const W = canvas.width
  const H = canvas.height
  ctx.clearRect(0, 0, W, H)
  ctx.fillStyle = '#E5E7EB'
  ctx.fillRect(0, 0, W, H)
  if (!flat.length || !(mx > mn)) return
  const stops = [
    [68, 1, 84], [71, 44, 122], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]
  ]
  const img = ctx.createImageData(W, H)
  for (let y = 0; y < H; y++) {
    const r = Math.min(Math.floor((y / H) * nR), nR - 1)
    for (let x = 0; x < W; x++) {
      const c = Math.min(Math.floor((x / W) * nC), nC - 1)
      const v = grid[r][c]
      const o = (y * W + x) * 4
      if (v == null || !Number.isFinite(v)) {
        img.data[o] = 229; img.data[o + 1] = 231; img.data[o + 2] = 235; img.data[o + 3] = 255
        continue
      }
      const t = Math.max(0, Math.min(1, (v - mn) / (mx - mn))) * (stops.length - 1)
      const i0 = Math.min(Math.floor(t), stops.length - 2)
      const f = t - i0
      const a = stops[i0]
      const b = stops[i0 + 1]
      img.data[o] = Math.round(a[0] + (b[0] - a[0]) * f)
      img.data[o + 1] = Math.round(a[1] + (b[1] - a[1]) * f)
      img.data[o + 2] = Math.round(a[2] + (b[2] - a[2]) * f)
      img.data[o + 3] = 255
    }
  }
  ctx.putImageData(img, 0, 0)
}

function drawAllThumbs() {
  okImages.value.forEach((it, i) => {
    drawThumb(thumbRefs.get(i), it.preview)
  })
}

// ---- Export ----
function pngPayload() {
  return {
    cmap: png.cmap,
    useLog: png.useLog,
    logFloor: png.logFloor,
    climMode: png.climMode,
    clim: png.climMode === 'manual' ? [png.climMin, png.climMax] : null,
    flipX: png.flipX,
    flipY: png.flipY,
    title: png.title,
    showColorbar: png.showColorbar,
    dpi: png.dpi
  }
}

async function renderPngPreview() {
  if (!result.value || busyExport.value) return
  busyExport.value = true
  try {
    const res = await giwaxsRenderPng({
      ...pngPayload(),
      resultFileId: result.value.mergedFileId,
      ipAxisFileId: result.value.ipAxisFileId,
      oopAxisFileId: result.value.oopAxisFileId,
      unitIp: result.value.unitIp,
      unitOop: result.value.unitOop,
      baseName: 'giwaxs_merge'
    })
    if (pngPreviewUrl.value) URL.revokeObjectURL(pngPreviewUrl.value)
    pngPreviewUrl.value = URL.createObjectURL(res.data)
    log(t('giwaxs.exportSec.rendered'))
  } catch (e) {
    log(`⚠ ${e.response?.data?.detail || e.message}`)
  } finally {
    busyExport.value = false
  }
}

async function downloadPng() {
  if (!result.value) return
  busyExport.value = true
  try {
    const res = await giwaxsRenderPng({
      ...pngPayload(),
      resultFileId: result.value.mergedFileId,
      ipAxisFileId: result.value.ipAxisFileId,
      oopAxisFileId: result.value.oopAxisFileId,
      unitIp: result.value.unitIp,
      unitOop: result.value.unitOop,
      baseName: 'giwaxs_merge'
    })
    await saveBlob(res.data, 'giwaxs_merge.png')
    log(t('giwaxs.exportSec.exportedPng'))
  } catch (e) {
    log(`⚠ ${e.response?.data?.detail || e.message}`)
  } finally {
    busyExport.value = false
  }
}

async function exportZip() {
  if (!result.value || busyExport.value) return
  busyExport.value = true
  try {
    const res = await giwaxsExportZip({
      mergedFileId: result.value.mergedFileId,
      ipAxisFileId: result.value.ipAxisFileId,
      oopAxisFileId: result.value.oopAxisFileId,
      info: result.value.info,
      baseName: 'giwaxs_merge',
      includePng: exportWithPng.value,
      png: exportWithPng.value ? pngPayload() : null,
      unitIp: result.value.unitIp,
      unitOop: result.value.unitOop
    })
    await saveBlob(res.data, 'giwaxs_merge.zip')
    log(exportWithPng.value ? t('giwaxs.exportSec.exportedZipPng') : t('giwaxs.exportSec.exportedZip'))
  } catch (e) {
    log(`⚠ ${e.response?.data?.detail || e.message}`)
  } finally {
    busyExport.value = false
  }
}

// ---- Hand-off to qz Band Integration ----
function sendToQzSlice() {
  if (!result.value) return
  sessionStorage.setItem('pre.qzSlice.handoff.v1', JSON.stringify({
    mergedFileId: result.value.mergedFileId,
    ipAxisFileId: result.value.ipAxisFileId,
    oopAxisFileId: result.value.oopAxisFileId,
    unitIp: result.value.unitIp,
    unitOop: result.value.unitOop,
    sourceName: `giwaxs_merge (${new Date().toLocaleTimeString()})`
  }))
  router.push('/app/qz-slice')
}
</script>

<style scoped>
.giwaxs-page {
  display: flex;
  flex-direction: column;
  gap: 22px;
  animation: giwaxsFadeIn 0.4s ease-out;
}
@keyframes giwaxsFadeIn {
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
.giwaxs-grid {
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
.section__body { display: flex; flex-direction: column; gap: 12px; }

.section-toggle {
  display: flex; align-items: center; gap: 8px;
  border: none; background: transparent; padding: 0; cursor: pointer;
}
.section-toggle h3 { margin: 0; font-size: 1rem; font-weight: 700; color: var(--text-primary); }
.chev { width: 16px; height: 16px; color: var(--text-secondary); transition: transform var(--transition-fast); }
.chev.open { transform: rotate(180deg); }

/* ---- Upload slots ---- */
.upload-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.upload-grid--single { grid-template-columns: 1fr; }
.upload-slot { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.slot-label { font-size: 0.8rem; font-weight: 600; color: var(--text-primary); }

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
.file-chip-list { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.file-chip-count {
  width: 100%;
  font-size: 0.74rem; font-weight: 600; color: var(--text-secondary);
  margin-bottom: 2px;
}
.file-chip-clear {
  border: none; background: transparent; color: var(--text-secondary);
  font-size: 0.74rem; font-weight: 600; cursor: pointer;
  padding: 4px 6px; text-decoration: underline;
}
.file-chip-clear:hover { color: var(--color-error); }

/* ---- PONI summary card ---- */
.poni-card {
  border: 1px solid var(--border);
  background: var(--bg-surface-alt);
  border-radius: var(--radius-md);
  padding: 12px 14px;
}
.poni-card__title { font-size: 0.8rem; font-weight: 700; color: var(--text-primary); margin-bottom: 10px; }
.poni-card__grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 16px; }
.poni-card__item { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.poni-card__item--wide { grid-column: 1 / -1; }
.poni-card__k { font-size: 0.72rem; color: var(--text-secondary); flex-shrink: 0; }
.poni-card__v { font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-primary); }

/* ---- Rotation table ---- */
.rot-empty { font-size: 0.82rem; color: var(--text-secondary); padding: 10px 0; }
.rot-table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius-md); }
.rot-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.rot-table th {
  text-align: left; padding: 8px 10px;
  background: var(--bg-surface-alt);
  color: var(--text-secondary); font-weight: 700;
  white-space: nowrap;
  border-bottom: 1px solid var(--border);
}
.rot-table td { padding: 6px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }
.rot-table tr:last-child td { border-bottom: none; }
.rot-idx { color: var(--text-secondary); font-family: var(--font-mono); }
.rot-name {
  max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 600; color: var(--text-primary);
}
.rot-input {
  width: 96px; box-sizing: border-box;
  padding: 6px 8px;
  font-family: var(--font-mono); font-size: 0.8rem;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  outline: none;
}
.rot-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--color-primary-glow); }
.rot-applied { font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-secondary); white-space: nowrap; }

.rot-batch { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rot-batch__label { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
.rot-batch__field {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 0.78rem; font-weight: 600; color: var(--text-primary);
}
.rot-batch__preview { font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-secondary); }

/* ---- Fields ---- */
.axis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.axis-grid--3 { grid-template-columns: repeat(3, 1fr); }
.axis-grid--4 { grid-template-columns: repeat(4, 1fr); }
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
.field input:disabled { opacity: 0.55; }

.check-row {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 0.82rem; color: var(--text-primary); cursor: pointer;
}
.check-row input { accent-color: var(--primary); }
.hint-line { margin: 0; font-size: 0.76rem; color: var(--text-secondary); line-height: 1.5; }

/* ---- Segmented control ---- */
.seg { display: inline-flex; gap: 3px; padding: 3px; background: var(--bg-surface-alt); border-radius: var(--radius-md); align-self: flex-start; }
.seg--sm { align-self: center; }
.seg__btn {
  padding: 7px 16px; border: none; background: transparent;
  color: var(--text-secondary); font-size: 0.82rem; font-weight: 600;
  border-radius: var(--radius-sm); cursor: pointer;
}
.seg--sm .seg__btn { padding: 4px 12px; font-size: 0.76rem; }
.seg__btn:hover { color: var(--text-primary); }
.seg__btn.active { background: var(--bg-surface); color: var(--primary); box-shadow: var(--shadow-sm); }

/* ---- Buttons ---- */
.action-bar { display: flex; gap: 10px; margin-top: 4px; }
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
.btn--accent { background: var(--cta); color: #FFFFFF; box-shadow: 0 8px 20px rgba(124, 58, 237, 0.22); }
.btn--accent:hover { filter: brightness(0.96); transform: translateY(-1px); }
.btn--ghost { background: transparent; border-color: var(--border); color: var(--text-secondary); }
.btn--ghost:hover { border-color: var(--border-hover); color: var(--text-primary); background: var(--bg-surface-alt); }
.btn--sm { padding: 7px 14px; font-size: 0.8rem; align-self: flex-start; }

/* ---- Result ---- */
.stats { display: flex; gap: 14px; flex-wrap: wrap; }
.stat { font-size: 0.74rem; color: var(--text-secondary); font-family: var(--font-mono); }
.stat b { color: var(--text-primary); margin-right: 5px; }
.result-canvas { margin-top: 4px; display: flex; flex-direction: column; gap: 10px; }
.result-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; min-height: 340px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-lg);
  color: var(--text-muted);
}
.result-empty svg { width: 44px; height: 44px; opacity: 0.5; }
.result-empty p { margin: 0; font-size: 0.86rem; }

.contrast-controls { display: flex; flex-direction: column; gap: 8px; }
.contrast-row { display: flex; flex-direction: column; gap: 4px; }
.contrast-row label { font-size: 0.74rem; font-family: var(--font-mono); color: var(--text-secondary); }
.contrast-row input[type="range"] { width: 100%; accent-color: var(--primary); }

/* ---- Thumbnails ---- */
.result-thumbs { display: flex; flex-direction: column; gap: 10px; }
.thumbs-label { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
.thumbs-row {
  display: flex; flex-wrap: wrap; gap: 10px; padding: 10px;
  background: var(--bg-surface-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.thumb {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  width: 108px; padding: 6px;
  border: 1px solid transparent; border-radius: var(--radius-sm); cursor: pointer;
}
.thumb:hover { border-color: var(--border-hover); }
.thumb.active { border-color: var(--primary); background: var(--primary-bg); }
.thumb__canvas { width: 96px; height: 96px; border-radius: 4px; image-rendering: pixelated; }
.thumb__name {
  max-width: 96px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 0.7rem; font-weight: 600; color: var(--text-primary);
}
.thumb__meta { font-size: 0.64rem; color: var(--text-secondary); font-family: var(--font-mono); }

/* ---- Export ---- */
.export-section { gap: 12px; }
.export-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.png-checks { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.png-preview {
  width: 100%; max-width: 560px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  margin-top: 4px;
}

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
  .giwaxs-grid { grid-template-columns: 1fr; }
  .panel--result { position: static; }
  .axis-grid--4 { grid-template-columns: 1fr 1fr; }
  .axis-grid--3 { grid-template-columns: 1fr 1fr; }
}
</style>
