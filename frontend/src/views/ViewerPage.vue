<template>
  <div class="viewer-page">
    <div class="main-container">
      <main class="content">
        <!-- 2D Cake Viewer -->
        <div class="tab-panel">
            <div class="panel-layout">
              <div class="viewer-top" :style="{ '--viewer-area-h': viewerAreaH + 'px' }">
                <!-- File list / thumbnail gallery -->
                <div class="file-gallery">
                  <div class="gallery-head">
                    <h3 class="section-title">{{ t('viewer.cake.title') }}</h3>
                    <div class="gallery-head-actions">
                      <button
                        v-if="cakeFiles.length"
                        class="toggle-btn gallery-clear"
                        :title="t('viewer.cake.removeAll')"
                        @click="clearAllCakeFiles"
                      >
                        {{ t('viewer.cake.removeAll') }}
                      </button>
                      <button
                        :class="['toggle-btn', 'compare-toggle', { active: compareMode }]"
                        :disabled="!cakeFiles.length"
                        @click="toggleCompareMode"
                        :title="t('viewer.compare.toggleHint')"
                      >
                        {{ t('viewer.compare.toggle') }}
                      </button>
                    </div>
                  </div>
                  <div class="gallery-scroll" ref="galleryScrollEl">
                    <div
                      v-for="(file, i) in cakeFiles"
                      :key="file.fileId || i"
                      :class="['gallery-item', {
                        selected: !compareMode && selectedCakeFile === i,
                        'compare-a': compareMode && compareSlots[0].fileId === file.fileId,
                        'compare-b': compareMode && compareSlots[1].fileId === file.fileId,
                      }]"
                      @click="onGalleryClick(i)"
                    >
                      <button
                        class="gallery-del"
                        :title="t('viewer.cake.remove')"
                        @click.stop="removeCakeFile(i)"
                      >×</button>
                      <div class="thumb">
                        <img v-if="file.thumbUrl" :src="file.thumbUrl" class="thumb-img" alt="" />
                        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="thumb-icon">
                          <rect x="3" y="3" width="18" height="18" rx="2" />
                          <line x1="3" y1="9" x2="21" y2="9" />
                          <line x1="9" y1="3" x2="9" y2="21" />
                        </svg>
                      </div>
                      <span v-if="compareSlotTag(file.fileId)" :class="['compare-tag', `compare-tag--${compareSlotTag(file.fileId).toLowerCase()}`]">
                        {{ compareSlotTag(file.fileId) }}
                      </span>
                      <span class="gallery-name">{{ file.name }}</span>
                      <span class="gallery-meta">{{ file.shape ? file.shape.join(' × ') : '' }}</span>
                    </div>
                    <div class="gallery-empty" v-if="!cakeFiles.length">
                      <span>{{ t('viewer.cake.empty') }}</span>
                    </div>
                  </div>
                </div>

                <!-- Main image display: single view or side-by-side compare -->
                <div class="image-main">
                  <div v-if="compareMode" class="compare-wrap">
                    <div v-for="(slot, si) in compareSlots" :key="si" class="compare-pane">
                      <div class="compare-head">
                        <span :class="['compare-tag', `compare-tag--${si === 0 ? 'a' : 'b'}`]">{{ si === 0 ? 'A' : 'B' }}</span>
                        <span class="compare-name">{{ slot.name || t(`viewer.compare.slot${si === 0 ? 'A' : 'B'}`) }}</span>
                      </div>
                      <ImageCanvas
                        v-if="slot.data"
                        :image-data="slot.data"
                        :x-axis="si === 0 ? compareAXAxis : compareBXAxis"
                        :y-axis="si === 0 ? compareAYAxis : compareBYAxis"
                        :x-axis-title="cakeXAxisTitle"
                        :y-axis-title="cakeYAxisTitle"
                        :y-range="cakeCropYRange"
                        :colorscale="cakeViewerControls.colormap"
                        :log-scale="cakeViewerControls.logScale"
                        :show-colorbar="cakeViewerControls.colorbar"
                        @update:colorscale="cakeViewerControls.colormap = $event"
                        @update:log-scale="cakeViewerControls.logScale = $event"
                        :zmin="slot.zmin"
                        :zmax="slot.zmax"
                        :height="240"
                        :max-height="comparePaneHeight"
                        :aspect-ratio="'4 / 3'"
                        :reference-line-y="displayRefLineY"
                        :show-toolbar="false"
                        :dragmode="'pan'"
                        :title="slot.name"
                      />
                      <div v-else class="image-placeholder compare-placeholder">
                        <span>{{ t('viewer.compare.emptyHint') }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else class="image-canvas-wrap">
                    <ImageCanvas
                      v-if="cakeImageData"
                      :image-data="cakeImageData"
                      :x-axis="cakeXAxis"
                      :y-axis="cakeYAxis"
                      :x-axis-title="cakeXAxisTitle"
                      :y-axis-title="cakeYAxisTitle"
                      :y-range="cakeCropYRange"
                      :colorscale="cakeViewerControls.colormap"
                      :log-scale="cakeViewerControls.logScale"
                      :show-colorbar="cakeViewerControls.colorbar"
                      @update:colorscale="cakeViewerControls.colormap = $event"
                      @update:log-scale="cakeViewerControls.logScale = $event"
                      :zmin="cakeViewerControls.zmin"
                      :zmax="cakeViewerControls.zmax"
                      :height="300"
                      :max-height="singleCanvasHeight"
                      :aspect-ratio="'4 / 3'"
                      :reference-line-y="displayRefLineY"
                      :dragmode="'pan'"
                      :title="cakeFiles[selectedCakeFile]?.name || t('viewer.cake.displayTitle')"
                    />
                    <div v-else class="image-placeholder">
                      <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <line x1="3" y1="9" x2="21" y2="9" />
                        <line x1="9" y1="3" x2="9" y2="21" />
                      </svg>
                      <span>{{ t('viewer.cake.placeholder') }}</span>
                      <span class="placeholder-hint">{{ t('viewer.cake.placeholderHint') }}</span>
                      <span v-if="selectedCakeFile !== null && cakeFiles[selectedCakeFile]" class="placeholder-file">
                        {{ cakeFiles[selectedCakeFile].name }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Controls -->
                <div class="controls-panel">
                  <h3 class="controls-title">{{ t('viewer.controls.title') }}</h3>
                  <button class="btn-secondary btn-full" :title="t('viewer.controls.resetAllHint')" @click="resetViewerState">
                    {{ t('viewer.controls.resetAll') }}
                  </button>

                  <div class="control-group">
                    <label>{{ t('viewer.controls.colormap') }}</label>
                    <select v-model="cakeViewerControls.colormap" class="param-input">
                      <option value="Viridis">Viridis</option>
                      <option value="Plasma">Plasma</option>
                      <option value="Inferno">Inferno</option>
                      <option value="Magma">Magma</option>
                      <option value="Gray">Grayscale</option>
                      <option value="Jet">Jet</option>
                      <option value="Turbo">Turbo</option>
                    </select>
                  </div>

                  <div class="control-group">
                    <label>{{ t('viewer.controls.logScale') }}</label>
                    <button
                      :class="['toggle-btn', { active: cakeViewerControls.logScale }]"
                      @click="cakeViewerControls.logScale = !cakeViewerControls.logScale"
                    >
                      {{ cakeViewerControls.logScale ? t('common.on') : t('common.off') }}
                    </button>
                  </div>

                  <div class="control-group">
                    <label>{{ t('viewer.controls.colorbar') }}</label>
                    <button
                      :class="['toggle-btn', { active: cakeViewerControls.colorbar }]"
                      @click="cakeViewerControls.colorbar = !cakeViewerControls.colorbar"
                    >
                      {{ cakeViewerControls.colorbar ? t('common.on') : t('common.off') }}
                    </button>
                  </div>

                  <div class="control-group">
                    <label>{{ t('viewer.controls.xAxis') }}</label>
                    <select v-model="cakeViewerControls.xAxis" class="param-input">
                      <option value="q">q (1/A)</option>
                      <option value="2theta">2theta (deg)</option>
                      <option value="d">d-spacing (A)</option>
                    </select>
                  </div>

                  <div class="control-group" v-if="cakeViewerControls.xAxis === '2theta'">
                    <label>{{ t('viewer.controls.wavelength') }}</label>
                    <input type="number" step="any" min="0.1" v-model.number="wavelength" class="param-input" />
                  </div>

                  <div class="control-group">
                    <label>{{ t('viewer.controls.yAxis') }}</label>
                    <select v-model="cakeViewerControls.yAxis" class="param-input">
                      <option value="chi">chi (deg)</option>
                      <option value="azimuth">azimuth (deg)</option>
                    </select>
                  </div>

                  <div class="control-divider"></div>

                  <!-- Contrast controls: slider + typable value for each bound.
                       Compare mode shows one independent pair per image (A/B). -->
                  <template v-if="!compareMode">
                    <div class="control-group" v-if="cakeImageData">
                      <label>{{ t('viewer.controls.contrastMin') }}</label>
                      <div class="contrast-row">
                        <input type="number" step="any" class="param-input contrast-input"
                          v-model.number="cakeViewerControls.zmin" />
                      </div>
                      <input type="range"
                        :min="cakeContrastFloor"
                        :max="cakeContrastCeil"
                        :step="cakeContrastStep"
                        v-model.number="cakeViewerControls.zmin"
                        class="contrast-slider"
                      />
                    </div>
                    <div class="control-group" v-if="cakeImageData">
                      <label>{{ t('viewer.controls.contrastMax') }}</label>
                      <div class="contrast-row">
                        <input type="number" step="any" class="param-input contrast-input"
                          v-model.number="cakeViewerControls.zmax" />
                      </div>
                      <input type="range"
                        :min="cakeContrastFloor"
                        :max="cakeContrastCeil"
                        :step="cakeContrastStep"
                        v-model.number="cakeViewerControls.zmax"
                        class="contrast-slider"
                      />
                    </div>
                    <button v-if="cakeImageData" class="btn-secondary btn-full" @click="resetCakeContrast">
                      {{ t('viewer.controls.contrastReset') }}
                    </button>
                  </template>
                  <template v-else>
                    <div v-for="(slot, si) in compareSlots" :key="si" class="control-group compare-controls">
                      <label>{{ t(si === 0 ? 'viewer.compare.contrastA' : 'viewer.compare.contrastB') }}</label>
                      <div class="contrast-row">
                        <span class="contrast-slot-name">{{ slot.name || '–' }}</span>
                      </div>
                      <div class="contrast-row">
                        <span class="contrast-bound">{{ t('viewer.controls.contrastMinShort') }}</span>
                        <input type="number" step="any" class="param-input contrast-input"
                          v-model.number="slot.zmin" :disabled="!slot.data" />
                      </div>
                      <input type="range"
                        :min="compareRanges[si][0]"
                        :max="compareRanges[si][1]"
                        :step="compareSteps[si]"
                        v-model.number="slot.zmin"
                        class="contrast-slider"
                        :disabled="!slot.data"
                      />
                      <div class="contrast-row">
                        <span class="contrast-bound">{{ t('viewer.controls.contrastMaxShort') }}</span>
                        <input type="number" step="any" class="param-input contrast-input"
                          v-model.number="slot.zmax" :disabled="!slot.data" />
                      </div>
                      <input type="range"
                        :min="compareRanges[si][0]"
                        :max="compareRanges[si][1]"
                        :step="compareSteps[si]"
                        v-model.number="slot.zmax"
                        class="contrast-slider"
                        :disabled="!slot.data"
                      />
                      <button class="btn-secondary btn-full" @click="resetSlotContrast(si)" :disabled="!slot.data">
                        {{ t(si === 0 ? 'viewer.compare.resetA' : 'viewer.compare.resetB') }}
                      </button>
                    </div>
                  </template>

                  <div class="control-divider"></div>

                  <!-- Reference line controls -->
                  <div class="control-group">
                    <label>{{ t('viewer.controls.refLine') }}</label>
                    <button
                      :class="['toggle-btn', { active: cakeViewerControls.refLineVisible }]"
                      @click="cakeViewerControls.refLineVisible = !cakeViewerControls.refLineVisible"
                    >
                      {{ cakeViewerControls.refLineVisible ? t('common.on') : t('common.off') }}
                    </button>
                  </div>
                  <div class="control-group" v-if="cakeViewerControls.refLineVisible">
                    <label>{{ t('viewer.controls.refLineOffset') }} (°)</label>
                    <input type="number" step="0.1" v-model.number="cakeViewerControls.refLineOffset" class="param-input" />
                  </div>
                </div>
              </div>

              <!-- Bottom action row: add npy · import npy info file · export -->
              <div class="viewer-bottom">
                <div class="bottom-module">
                  <h4 class="bottom-module-title">{{ t('viewer.bottom.addNpy') }}</h4>
                  <FileUpload
                    accept=".npy,.tif,.tiff,.edf,.h5"
                    clear-after-select
                    @files-selected="onCakeFilesSelected"
                    :label="t('viewer.cake.uploadLabel')"
                  />
                </div>

                <div class="bottom-module">
                  <h4 class="bottom-module-title">{{ t('viewer.bottom.importInfo') }}</h4>
                  <FileUpload
                    :multiple="false"
                    accept=".json,.txt"
                    :label="t('viewer.axis.infoLabel')"
                    @files-selected="onInfoSelected"
                  />
                  <span v-if="infoName" class="info-chip" :title="infoName">{{ infoName }}</span>
                </div>

                <div class="bottom-module">
                  <h4 class="bottom-module-title">{{ t('viewer.controls.export') }}</h4>
                  <template v-if="!compareMode">
                    <button class="btn-secondary btn-full" @click="exportCake('png')">{{ t('viewer.export.png') }}</button>
                    <button class="btn-secondary btn-full" @click="exportCakeBatch">{{ t('viewer.export.batch') }}</button>
                  </template>
                  <template v-else>
                    <button class="btn-secondary btn-full" @click="exportCompare(0)" :disabled="!compareSlots[0].data">
                      {{ t('viewer.compare.exportA') }}
                    </button>
                    <button class="btn-secondary btn-full" @click="exportCompare(1)" :disabled="!compareSlots[1].data">
                      {{ t('viewer.compare.exportB') }}
                    </button>
                  </template>
                  <button
                    class="btn-secondary btn-full btn-batch-first"
                    :title="t('viewer.export.batchByFirstHint')"
                    @click="exportCakeBatchByFirst"
                  >
                    {{ t('viewer.export.batchByFirst') }}
                  </button>
                </div>
              </div>

              <!-- Axis ranges + χ crop -->
              <div class="viewer-axis" v-if="cakeImageData">
                <div class="axis-head">
                  <h3 class="axis-title">{{ t('viewer.axis.title') }}</h3>
                  <span class="axis-hint">{{ t('viewer.axis.hint') }}</span>
                </div>
                <div class="axis-grid">
                  <div class="control-group">
                    <label>{{ t('viewer.axis.qMin') }}</label>
                    <input type="number" step="any" v-model.number="qMin" class="param-input" />
                  </div>
                  <div class="control-group">
                    <label>{{ t('viewer.axis.qMax') }}</label>
                    <input type="number" step="any" v-model.number="qMax" class="param-input" />
                  </div>
                  <div class="control-group">
                    <label>{{ t('viewer.axis.chiMin') }}</label>
                    <input type="number" step="any" v-model.number="chiMin" class="param-input" />
                  </div>
                  <div class="control-group">
                    <label>{{ t('viewer.axis.chiMax') }}</label>
                    <input type="number" step="any" v-model.number="chiMax" class="param-input" />
                  </div>
                </div>

                <div class="axis-divider"></div>

                <div class="axis-crop">
                  <label class="crop-toggle">
                    <input type="checkbox" v-model="cropEnabled" />
                    <span>{{ t('viewer.crop.enable') }}</span>
                  </label>
                  <div class="axis-grid">
                    <div class="control-group">
                      <label>{{ t('viewer.crop.chiMin') }}</label>
                      <input type="number" step="any" v-model.number="cropChiMin" class="param-input" :disabled="!cropEnabled" />
                    </div>
                    <div class="control-group">
                      <label>{{ t('viewer.crop.chiMax') }}</label>
                      <input type="number" step="any" v-model.number="cropChiMax" class="param-input" :disabled="!cropEnabled" />
                    </div>
                  </div>
                  <button class="btn-secondary btn-full" @click="resetCrop" style="margin-top:8px">{{ t('viewer.crop.reset') }}</button>
                </div>
              </div>

              <!-- Console for async operations -->
              <ConsolePanel
                v-if="consoleLogs.cake.length || taskStatus.cake !== 'idle'"
                :status="taskStatus.cake"
                :logs="consoleLogs.cake"
              />
            </div>
          </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import FileUpload from '@/components/FileUpload.vue'
import ImageCanvas from '@/components/ImageCanvas.vue'
import ConsolePanel from '@/components/ConsolePanel.vue'
import {
  viewerUploadFiles,
  viewerGetImageData,
  viewerGetFileList,
  viewerDeleteFile,
  viewerDeleteAllFiles,
  viewerExportPng,
  viewerExportBatchZip,
  integrationParseInfo
} from '@/api/index.js'
import { saveBlob } from '@/services/download.js'
import { plotlyColorscale } from '@/services/colormaps.js'
import {
  qToX, chiToY,
  xAxisTitle, yAxisTitle,
  DEFAULT_WAVELENGTH_ANGSTROM
} from '@/services/axes.js'

const { t } = useI18n()

const runStatus = ref('idle')

// ---- Console / task tracking ----
const taskStatus = reactive({ cake: 'idle' })
const consoleLogs = reactive({ cake: [] })

// ---- 2D Cake Viewer State ----
const cakeFiles = ref([])
const selectedCakeFile = ref(null)
const cakeImageData = ref(null)

// Adaptive display-area height. The single view fills roughly one window.
// Compare mode DOUBLES the area instead of shrinking the images: both stacked
// panes keep the full single-view canvas size and the page scrolls — the
// images are never compressed to fit.
const windowH = ref(940)
function updateViewerAreaH() {
  windowH.value = (typeof window !== 'undefined' && window.innerHeight) ? window.innerHeight : 940
}
updateViewerAreaH()
const singleAreaH = computed(() => Math.round(Math.min(1200, Math.max(560, windowH.value - 165))))
const viewerAreaH = computed(() =>
  compareMode.value ? singleAreaH.value * 2 + 120 : singleAreaH.value)
const singleCanvasHeight = computed(() => Math.max(380, singleAreaH.value - 80))
// In compare mode each pane is as tall as the single-view canvas.
const comparePaneHeight = computed(() => singleCanvasHeight.value)

// Gallery scroll container — new uploads land at the bottom of the list, so
// keep them in view instead of leaving them below the fold. Re-applied on the
// next frames: the first paint of the uploaded <img> can transiently stretch
// the flex items before the aspect-ratio boxes settle.
const galleryScrollEl = ref(null)
async function scrollGalleryToBottom() {
  await nextTick()
  const el = galleryScrollEl.value
  if (!el) return
  el.scrollTop = el.scrollHeight
  requestAnimationFrame(() => { el.scrollTop = el.scrollHeight })
  setTimeout(() => { el.scrollTop = el.scrollHeight }, 250)
}

// Guard against re-uploading a file the picker already handed us once (same
// name + size + mtime ⇒ same content): FileUpload used to re-emit the whole
// accumulated list on every later add, duplicating earlier entries in the
// gallery. Kept even with clear-after-select as a second line of defence.
const uploadedSignatures = new Set()
function fileSignature(f) {
  return `${f.name}|${f.size}|${f.lastModified}`
}

// ---- Contrast memory (LRU, most recent 10 images) ----
// Switching between images keeps each image's contrast window, so a tuned
// setting survives round-trips without caching every file ever viewed.
const CONTRAST_MEMORY_MAX = 10
const contrastMemory = new Map()
function rememberContrast(fileId, zmin, zmax) {
  if (!fileId) return
  contrastMemory.delete(fileId)
  contrastMemory.set(fileId, { zmin, zmax })
  if (contrastMemory.size > CONTRAST_MEMORY_MAX) {
    contrastMemory.delete(contrastMemory.keys().next().value)
  }
}
function recallContrast(fileId) {
  const saved = contrastMemory.get(fileId)
  if (!saved) return null
  // Refresh LRU position on access.
  contrastMemory.delete(fileId)
  contrastMemory.set(fileId, saved)
  return saved
}

// ---- Gallery thumbnails (rendered client-side so they track contrast) ----
// A small (≤96 px) copy of each image is fetched once, then re-painted onto a
// canvas whenever its contrast window changes (main view, compare pane, or a
// remembered window) — the thumbnail always previews what the image looks
// like with its own current contrast, which makes picking the next file easy.
const thumbDataCache = new Map()
const THUMB_DATA_MAX = 200

async function ensureThumbData(fileId) {
  if (thumbDataCache.has(fileId)) return thumbDataCache.get(fileId)
  try {
    const res = await viewerGetImageData(fileId, 96)
    const data = res.data?.data ?? null
    if (thumbDataCache.size >= THUMB_DATA_MAX) {
      thumbDataCache.delete(thumbDataCache.keys().next().value)
    }
    thumbDataCache.set(fileId, data)
    return data
  } catch {
    thumbDataCache.set(fileId, null)
    return null
  }
}

// Read the remembered window without refreshing LRU position (thumbnail
// painting must not influence which images get evicted).
function peekContrast(fileId) {
  return contrastMemory.get(fileId) || null
}

// Parsed [pos, [r,g,b]] colormap stops, memoized per colormap name.
let _scaleCache = { name: null, stops: null }
function parsedStops() {
  const name = cakeViewerControls.colormap
  if (_scaleCache.name !== name) {
    _scaleCache.stops = plotlyColorscale(name).map(([p, c]) => {
      const m = /rgb\((\d+),\s*(\d+),\s*(\d+)\)/.exec(String(c))
      return [Number(p), m ? [+m[1], +m[2], +m[3]] : [0, 0, 0]]
    })
    _scaleCache.name = name
  }
  return _scaleCache.stops
}

function sampleScale(stops, t) {
  if (!stops || !stops.length) return [120, 120, 120]
  if (t <= stops[0][0]) return stops[0][1]
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [p0, c0] = stops[i - 1]
      const [p1, c1] = stops[i]
      const f = (t - p0) / ((p1 - p0) || 1)
      return c0.map((v, k) => v + (c1[k] - v) * f)
    }
  }
  return stops[stops.length - 1][1]
}

// Paint one gallery entry's thumbnail with the given contrast window into a
// data URL. Same colormap and vertical orientation (χ up) as the main plot.
function renderThumb(entry, zmin, zmax) {
  if (!entry?.fileId) return
  const data = thumbDataCache.get(entry.fileId)
  if (!data || !data.length || !data[0]?.length) return
  const stops = parsedStops()
  const h = data.length
  const w = data[0].length
  const lo = Number.isFinite(Number(zmin)) ? Number(zmin) : contrastRangeOf(data)[0]
  const hi = Number.isFinite(Number(zmax)) ? Number(zmax) : contrastRangeOf(data)[1]
  const span = hi - lo
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  const img = ctx.createImageData(w, h)
  for (let r = 0; r < h; r++) {
    const row = data[r]
    // Flip y: data row 0 is χ-min (bottom of the plot) → canvas bottom.
    const py = (h - 1 - r)
    for (let c = 0; c < w; c++) {
      const v = row[c]
      const i = (py * w + c) * 4
      if (v == null || !Number.isFinite(v)) {
        img.data[i + 3] = 0 // transparent: no-data bins
        continue
      }
      let t = span > 0 ? (v - lo) / span : 0.5
      t = t < 0 ? 0 : (t > 1 ? 1 : t)
      const [rr, gg, bb] = sampleScale(stops, t)
      img.data[i] = rr
      img.data[i + 1] = gg
      img.data[i + 2] = bb
      img.data[i + 3] = 255
    }
  }
  ctx.putImageData(img, 0, 0)
  entry.thumbUrl = canvas.toDataURL('image/png')
}

// Paint with whatever window this file currently "owns": a remembered one,
// else its own data range. Used on upload and on colormap changes.
function renderThumbWithOwnRange(entry) {
  const data = thumbDataCache.get(entry?.fileId)
  if (!data) return
  const mem = peekContrast(entry.fileId)
  const [lo, hi] = mem ? [mem.zmin, mem.zmax] : contrastRangeOf(data)
  renderThumb(entry, lo, hi)
}

// Contrast sliders fire continuously while dragging — coalesce repaints.
let thumbRedrawTimer = null
function scheduleThumbRedraw(fn, delay = 250) {
  clearTimeout(thumbRedrawTimer)
  thumbRedrawTimer = setTimeout(fn, delay)
}

function findEntryByFileId(fileId) {
  return cakeFiles.value.find(f => f.fileId === fileId) || null
}

// Physical axis extents (q in Å^-1 horizontally, χ in degrees vertically).
// Without these the heatmap falls back to pixel indices — which is why the
// axes read 0..510 instead of the real q/χ range (cf. reference/function3,
// which auto-applies processing_info.txt on image load).
const qMin = ref(0)
const qMax = ref(1)
const chiMin = ref(-180)
const chiMax = ref(180)
const infoName = ref('')

// χ crop band (vertical) — mirrors analysis.crop: clamps the visible χ window
// so a narrow azimuth slice can be inspected/exported precisely.
const cropEnabled = ref(false)
const cropChiMin = ref(-180)
const cropChiMax = ref(180)

// x = q (cols), y = χ (rows), sampled across the loaded (downsampled) display
// array so every column/row maps to its physical coordinate. The selected
// axis modes (q/2θ/d, χ/azimuth) transform BOTH axes and every feature that
// lives in axis space (crop window, reference line) — a single source of
// truth in services/axes.js shared with the PNG export.
const wavelength = ref(DEFAULT_WAVELENGTH_ANGSTROM)
// Axis builders parameterized by the data array so the single view and each
// compare pane derive axes from their OWN grid (two compared files usually
// have different dimensions — sharing one array would desync z vs x/y).
function makeXAxis(data) {
  if (!data) return null
  const cols = data[0]?.length || 0
  if (cols < 1) return null
  const q0 = qMin.value, q1 = qMax.value
  const mode = cakeViewerControls.xAxis
  if (cols === 1) return [qToX(q0, mode, wavelength.value)]
  return Array.from({ length: cols }, (_, i) =>
    qToX(q0 + (i / (cols - 1)) * (q1 - q0), mode, wavelength.value))
}
function makeYAxis(data) {
  if (!data) return null
  const rows = data.length
  if (rows < 1) return null
  const c0 = chiMin.value, c1 = chiMax.value
  const mode = cakeViewerControls.yAxis
  if (rows === 1) return [chiToY(c0, mode)]
  return Array.from({ length: rows }, (_, i) =>
    chiToY(c0 + (i / (rows - 1)) * (c1 - c0), mode))
}
const cakeXAxis = computed(() => makeXAxis(cakeImageData.value))
const cakeYAxis = computed(() => makeYAxis(cakeImageData.value))
const compareAXAxis = computed(() => makeXAxis(compareSlots[0].data))
const compareAYAxis = computed(() => makeYAxis(compareSlots[0].data))
const compareBXAxis = computed(() => makeXAxis(compareSlots[1].data))
const compareBYAxis = computed(() => makeYAxis(compareSlots[1].data))
const cakeXAxisTitle = computed(() => xAxisTitle(cakeViewerControls.xAxis))
const cakeYAxisTitle = computed(() => yAxisTitle(cakeViewerControls.yAxis))
const cakeCropYRange = computed(() => {
  if (!cropEnabled.value) return null
  const mode = cakeViewerControls.yAxis
  const lo = chiToY(Math.min(cropChiMin.value, cropChiMax.value), mode)
  const hi = chiToY(Math.max(cropChiMin.value, cropChiMax.value), mode)
  return [Math.min(lo, hi), Math.max(lo, hi)]
})
// Reference line y is entered in χ; shift it for the azimuth display.
const displayRefLineY = computed(() => {
  if (!cakeViewerControls.refLineVisible) return null
  return chiToY(cakeViewerControls.refLineOffset, cakeViewerControls.yAxis)
})

const cakeViewerControls = reactive({
  colormap: 'Viridis',
  logScale: false,
  colorbar: true,
  xAxis: 'q',
  yAxis: 'chi',
  // Contrast window — set after image load from the data min/max.
  zmin: 0,
  zmax: 1,
  // Reference line at χ = 0° (equator).
  refLineVisible: false,
  refLineOffset: 0,
})

// Contrast range derived from a 2-D data array (finite values only).
function contrastRangeOf(data) {
  if (!data) return [0, 1]
  let mn = Infinity
  let mx = -Infinity
  for (const row of data) {
    for (const v of row) {
      if (Number.isFinite(v)) {
        if (v < mn) mn = v
        if (v > mx) mx = v
      }
    }
  }
  return [Number.isFinite(mn) ? mn : 0, Number.isFinite(mx) ? mx : 1]
}
function contrastStepOf([lo, hi]) {
  const span = hi - lo
  return span > 0 ? span / 200 : 0.01
}

// Contrast range derived from the currently loaded image data.
const cakeContrastFloor = computed(() => contrastRangeOf(cakeImageData.value)[0])
const cakeContrastCeil = computed(() => contrastRangeOf(cakeImageData.value)[1])
const cakeContrastStep = computed(() => contrastStepOf(contrastRangeOf(cakeImageData.value)))

// ---- Compare mode: two images side by side, each with its own contrast ----
const compareMode = ref(false)
const compareSlots = reactive([
  { fileId: null, name: '', data: null, zmin: 0, zmax: 1 },
  { fileId: null, name: '', data: null, zmin: 0, zmax: 1 },
])
const compareRanges = computed(() => [
  contrastRangeOf(compareSlots[0].data),
  contrastRangeOf(compareSlots[1].data),
])
const compareSteps = computed(() => compareRanges.value.map(contrastStepOf))

function compareSlotTag(fileId) {
  if (compareMode.value && compareSlots[0].fileId === fileId) return 'A'
  if (compareMode.value && compareSlots[1].fileId === fileId) return 'B'
  return ''
}

function fmtNum(v) {
  if (v == null || !Number.isFinite(v)) return '–'
  return Math.abs(v) < 1e-3 || Math.abs(v) >= 1e5 ? v.toExponential(3) : v.toFixed(4)
}

function resetCakeContrast() {
  cakeViewerControls.zmin = cakeContrastFloor.value
  cakeViewerControls.zmax = cakeContrastCeil.value
}

function onCakeFilesSelected(files) {
  uploadCakeFiles(files)
}

async function uploadCakeFiles(files) {
  if (!files.length) return
  // Drop files whose (name, size, mtime) signature was already uploaded —
  // re-adding the same picker selection must not duplicate gallery entries.
  const fresh = files.filter(f => !uploadedSignatures.has(fileSignature(f)))
  const dupCount = files.length - fresh.length
  if (!fresh.length) {
    consoleLogs.cake.push(t('logs.viewer.skippedDuplicates', { count: dupCount }))
    return
  }
  runStatus.value = 'running'
  taskStatus.cake = 'running'
  consoleLogs.cake = [t('logs.viewer.uploading', { count: fresh.length })]
  if (dupCount > 0) {
    consoleLogs.cake.push(t('logs.viewer.skippedDuplicates', { count: dupCount }))
  }
  try {
    const formData = new FormData()
    fresh.forEach(f => formData.append('files', f))
    const res = await viewerUploadFiles(formData)
    const uploaded = res.data?.files || []
    const known = new Set(cakeFiles.value.map(f => f.fileId))
    uploaded.forEach((f, i) => {
      if (known.has(f.fileId)) return
      const src = fresh[i] || null
      const entry = {
        name: src?.name || f.originalName || `file_${i}`,
        fileId: f.fileId || f.id,
        shape: f.shape || [],
        thumbUrl: '',
        // Signature of the picked File object — dropped again on delete so the
        // same file can be re-uploaded after being removed.
        _sig: src ? fileSignature(src) : null,
      }
      cakeFiles.value.push(entry)
      // Write thumbnails through the reactive proxy (cakeFiles.value[i]), not
      // the raw `entry` — plain-object writes never trigger the v-if update.
      const proxied = cakeFiles.value[cakeFiles.value.length - 1]
      ensureThumbData(proxied.fileId).then(() => renderThumbWithOwnRange(proxied))
    })
    consoleLogs.cake.push(t('logs.viewer.uploaded', { count: uploaded.length }))
    fresh.forEach(f => uploadedSignatures.add(fileSignature(f)))
    if (cakeFiles.value.length && selectedCakeFile.value === null && !compareMode.value) {
      selectCakeFile(0)
    }
    scrollGalleryToBottom()
    taskStatus.cake = 'completed'
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
    runStatus.value = 'failed'
  }
}

let imageLoadSeq = 0
async function selectCakeFile(idx) {
  // Leaving an image: remember its contrast window so switching back restores it.
  if (selectedCakeFile.value !== null && selectedCakeFile.value !== idx) {
    const prev = cakeFiles.value[selectedCakeFile.value]
    if (prev?.fileId && cakeImageData.value) {
      rememberContrast(prev.fileId, cakeViewerControls.zmin, cakeViewerControls.zmax)
    }
  }
  selectedCakeFile.value = idx
  const file = cakeFiles.value[idx]
  if (!file?.fileId) return
  taskStatus.cake = 'running'
  consoleLogs.cake = [t('logs.viewer.loading', { name: file.name })]
  const seq = ++imageLoadSeq
  try {
    const res = await viewerGetImageData(file.fileId)
    // A newer selection superseded this request — drop the stale payload.
    if (seq !== imageLoadSeq) return
    // Backend ImageResponse has no `image` key — the 2-D array lives in `.data`.
    // The old `res.data?.image || res.data` passed the whole response object,
    // so ImageCanvas got an object instead of an array and rendered nothing.
    cakeImageData.value = res.data?.data ?? null
    // Restore a remembered contrast window when this image was viewed (and
    // tuned) recently; otherwise snap to the loaded image's data range.
    const remembered = recallContrast(file.fileId)
    if (remembered) {
      cakeViewerControls.zmin = remembered.zmin
      cakeViewerControls.zmax = remembered.zmax
    } else {
      resetCakeContrast()
    }
    // Repaint this file's thumbnail with the (possibly remembered) window.
    const entry = cakeFiles.value[idx]
    if (entry?.fileId) {
      ensureThumbData(entry.fileId).then(() =>
        renderThumb(entry, cakeViewerControls.zmin, cakeViewerControls.zmax))
    }
    consoleLogs.cake.push(t('logs.viewer.imageLoaded'))
    taskStatus.cake = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.viewer.loadError', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
  }
}

// ---- Compare mode interactions ----

function onGalleryClick(idx) {
  if (compareMode.value) {
    pickCompare(idx)
  } else {
    selectCakeFile(idx)
  }
}

// ---- Uploaded-image management (delete from the server, not just the view) ----

// Drop every local trace of one uploaded file: compare panes showing it, the
// remembered contrast window and the cached thumbnail data.
function dropCakeEntryState(fileId) {
  for (let s = 0; s < compareSlots.length; s++) {
    if (compareSlots[s].fileId === fileId) {
      clearCompareSlot(s, false)
    }
  }
  contrastMemory.delete(fileId)
  thumbDataCache.delete(fileId)
}

async function removeCakeFile(idx) {
  const entry = cakeFiles.value[idx]
  if (!entry?.fileId) return
  if (!window.confirm(t('viewer.cake.removeConfirm', { name: entry.name }))) return
  try {
    await viewerDeleteFile(entry.fileId)
  } catch (err) {
    // 404 = the server no longer knows the file (e.g. backend restarted mid-
    // session): drop the stale gallery entry instead of blocking the user.
    if (err.response?.status !== 404) {
      consoleLogs.cake.push(t('logs.viewer.deleteError', { message: err.response?.data?.detail || err.message }))
      return
    }
    consoleLogs.cake.push(t('logs.viewer.deleteMissing', { name: entry.name }))
  }
  dropCakeEntryState(entry.fileId)
  const wasSelected = selectedCakeFile.value === idx
  cakeFiles.value.splice(idx, 1)
  if (entry._sig) uploadedSignatures.delete(entry._sig)
  if (wasSelected) {
    cakeImageData.value = null
    selectedCakeFile.value = null
    if (cakeFiles.value.length && !compareMode.value) {
      selectCakeFile(Math.min(idx, cakeFiles.value.length - 1))
    }
  } else if (selectedCakeFile.value !== null && idx < selectedCakeFile.value) {
    // Entries after the splice shifted down — keep the selection on the same file.
    selectedCakeFile.value -= 1
  }
  consoleLogs.cake.push(t('logs.viewer.deleted', { name: entry.name }))
}

async function clearAllCakeFiles() {
  if (!cakeFiles.value.length) return
  if (!window.confirm(t('viewer.cake.removeAllConfirm', { count: cakeFiles.value.length }))) return
  try {
    await viewerDeleteAllFiles()
  } catch (err) {
    consoleLogs.cake.push(t('logs.viewer.deleteError', { message: err.response?.data?.detail || err.message }))
    return
  }
  cakeFiles.value.forEach(entry => dropCakeEntryState(entry.fileId))
  cakeFiles.value = []
  uploadedSignatures.clear()
  selectedCakeFile.value = null
  cakeImageData.value = null
  consoleLogs.cake.push(t('logs.viewer.deletedAll'))
}

// The backend keeps every upload in its registry; reload it on mount so the
// gallery (and its delete controls) survives a page refresh.
onMounted(async () => {
  updateViewerAreaH()
  window.addEventListener('resize', updateViewerAreaH)
  let files = []
  try {
    const res = await viewerGetFileList()
    files = res.data || []
  } catch {
    return // backend unreachable / empty registry — start with a blank gallery
  }
  files.forEach(f => {
    const proxied = {
      name: f.originalName || f.fileId,
      fileId: f.fileId,
      shape: f.shape || [],
      thumbUrl: '',
      _sig: null,
    }
    cakeFiles.value.push(proxied)
    ensureThumbData(proxied.fileId).then(() => renderThumbWithOwnRange(proxied))
  })
  if (cakeFiles.value.length && selectedCakeFile.value === null && !compareMode.value) {
    selectCakeFile(0)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewerAreaH)
})

function toggleCompareMode() {
  compareMode.value = !compareMode.value
  if (compareMode.value) {
    // Reset both slots, then seed A with the currently viewed image so the
    // user starts from what is on screen (contrast carried over as-is).
    clearCompareSlot(0, false)
    clearCompareSlot(1, false)
    const cur = selectedCakeFile.value !== null ? cakeFiles.value[selectedCakeFile.value] : null
    if (cur?.fileId) {
      setCompareSlot(0, cur.fileId, cur.name, {
        data: cakeImageData.value,
        zmin: cakeViewerControls.zmin,
        zmax: cakeViewerControls.zmax,
      })
    }
  } else {
    // Leaving compare mode: keep each pane's tuned contrast in the LRU memory
    // (shared with the single view). The single view's canvas re-mounts from
    // the still-loaded cakeImageData, no reload needed.
    clearCompareSlot(0, true)
    clearCompareSlot(1, true)
  }
}

function clearCompareSlot(idx, remember = true) {
  const slot = compareSlots[idx]
  if (remember && slot.fileId && slot.data) {
    rememberContrast(slot.fileId, slot.zmin, slot.zmax)
  }
  slot.fileId = null
  slot.name = ''
  slot.data = null
  slot.zmin = 0
  slot.zmax = 1
}

async function setCompareSlot(idx, fileId, name, seed = null) {
  const slot = compareSlots[idx]
  // Replacing an occupied pane: remember what the user tuned there.
  if (slot.fileId && slot.data && slot.fileId !== fileId) {
    rememberContrast(slot.fileId, slot.zmin, slot.zmax)
  }
  slot.fileId = fileId
  slot.name = name
  slot.data = seed?.data || null
  if (seed?.data) {
    slot.zmin = seed.zmin
    slot.zmax = seed.zmax
    return
  }
  taskStatus.cake = 'running'
  try {
    const res = await viewerGetImageData(fileId)
    // Pane was reassigned while fetching — discard the stale payload.
    if (slot.fileId !== fileId) return
    slot.data = res.data?.data ?? null
    const remembered = recallContrast(fileId)
    if (remembered) {
      slot.zmin = remembered.zmin
      slot.zmax = remembered.zmax
    } else {
      resetSlotContrast(idx)
    }
    const entry = findEntryByFileId(fileId)
    if (entry) {
      ensureThumbData(fileId).then(() => renderThumb(entry, slot.zmin, slot.zmax))
    }
    taskStatus.cake = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.viewer.loadError', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
  }
}

// In compare mode a gallery click fills the first empty pane (A, then B);
// once both are occupied it replaces B. Clicking a pane's own file clears it.
function pickCompare(idx) {
  const file = cakeFiles.value[idx]
  if (!file?.fileId) return
  if (compareSlots[0].fileId === file.fileId) {
    clearCompareSlot(0, true)
    return
  }
  if (compareSlots[1].fileId === file.fileId) {
    clearCompareSlot(1, true)
    return
  }
  if (!compareSlots[0].fileId) {
    setCompareSlot(0, file.fileId, file.name)
  } else {
    setCompareSlot(1, file.fileId, file.name)
  }
}

function resetSlotContrast(idx) {
  const [lo, hi] = compareRanges.value[idx]
  compareSlots[idx].zmin = lo
  compareSlots[idx].zmax = hi
}

// Import a processing_info sidecar (.json / legacy .txt) to set the q (Å^-1) and
// χ (°) axis extents — the equivalent of reference/function3 auto-loading
// processing_info.txt from the image's directory.
async function onInfoSelected(files) {
  if (!files || !files.length) return
  try {
    const fd = new FormData()
    fd.append('file', files[0])
    const r = (await integrationParseInfo(fd)).data || {}
    infoName.value = files[0].name
    let applied = false
    if (Array.isArray(r.qRange) && r.qRange.length === 2) {
      qMin.value = r.qRange[0]; qMax.value = r.qRange[1]; applied = true
    }
    if (Array.isArray(r.chiRange) && r.chiRange.length === 2) {
      chiMin.value = r.chiRange[0]; chiMax.value = r.chiRange[1]; applied = true
      cropChiMin.value = r.chiRange[0]
      cropChiMax.value = r.chiRange[1]
    }
    consoleLogs.cake.push(applied
      ? t('viewer.axis.infoApplied')
      : t('viewer.axis.infoEmpty'))
  } catch (err) {
    consoleLogs.cake.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}

function resetCrop() {
  cropEnabled.value = false
  cropChiMin.value = chiMin.value
  cropChiMax.value = chiMax.value
}

// 恢复初始状态: every display setting back to its default — colormap, log,
// colorbar, axis modes, reference line, q/χ ranges, χ crop, remembered
// contrast windows and the current windows (loaded files stay in place).
function resetViewerState() {
  cakeViewerControls.colormap = 'Viridis'
  cakeViewerControls.logScale = false
  cakeViewerControls.colorbar = true
  cakeViewerControls.xAxis = 'q'
  cakeViewerControls.yAxis = 'chi'
  cakeViewerControls.refLineVisible = false
  cakeViewerControls.refLineOffset = 0
  qMin.value = 0
  qMax.value = 1
  chiMin.value = -180
  chiMax.value = 180
  cropEnabled.value = false
  cropChiMin.value = -180
  cropChiMax.value = 180
  wavelength.value = DEFAULT_WAVELENGTH_ANGSTROM
  infoName.value = ''
  contrastMemory.clear()
  resetCakeContrast()
  resetSlotContrast(0)
  resetSlotContrast(1)
  cakeFiles.value.forEach(entry => {
    if (entry.fileId && thumbDataCache.has(entry.fileId)) {
      renderThumbWithOwnRange(entry)
    }
  })
  consoleLogs.cake.push(t('viewer.controls.resetDone'))
}

// Shared display settings forwarded to the backend renderer so the exported
// PNG matches what the viewer shows (colormap / contrast / log / colorbar /
// axis mode / χ crop). `contrast` overrides the single-view window for the
// compare panes, which each carry their own zmin/zmax.
function exportRenderParams(contrast = null) {
  const num = v => { const n = Number(v); return Number.isFinite(n) ? n : null }
  const c = contrast || { zmin: cakeViewerControls.zmin, zmax: cakeViewerControls.zmax }
  return {
    colormap: cakeViewerControls.colormap,
    vmin: num(c.zmin),
    vmax: num(c.zmax),
    logScale: cakeViewerControls.logScale,
    dpi: 150,
    showAxes: true,
    showColorbar: cakeViewerControls.colorbar,
    channel: 0,
    // axis system (must mirror services/axes.js — backend applies the same
    // transforms to the full-resolution array)
    xAxis: cakeViewerControls.xAxis,
    yAxis: cakeViewerControls.yAxis,
    wavelengthAngstrom: num(wavelength.value) ?? DEFAULT_WAVELENGTH_ANGSTROM,
    axisQMin: num(qMin.value),
    axisQMax: num(qMax.value),
    axisChiMin: num(chiMin.value),
    axisChiMax: num(chiMax.value),
    // χ-space crop window (crop inputs are labelled in χ, not display coords)
    cropChiMin: cropEnabled.value ? num(cropChiMin.value) : null,
    cropChiMax: cropEnabled.value ? num(cropChiMax.value) : null,
  }
}

// Under Electron the raw `<a download>` click throws "An object could not be
// cloned" (silent no-op) — saveBlob routes through the native save dialog.
const exportCake = async (format) => {
  const idx = selectedCakeFile.value
  if (idx === null || !cakeFiles.value[idx]) return
  const file = cakeFiles.value[idx]
  taskStatus.cake = 'running'
  try {
    const res = await viewerExportPng({ fileId: file.fileId, ...exportRenderParams() })
    const save = await saveBlob(res.data, `${file.name.replace(/\.[^.]+$/, '') || 'cake_export'}_export.png`)
    if (save?.ok && save.filePath) {
      consoleLogs.cake.push(`${t('viewer.export.png')}: ${save.filePath}`)
    } else if (save?.ok) {
      consoleLogs.cake.push(`${t('viewer.export.png')}: ${file.name}`)
    }
    taskStatus.cake = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.viewer.exportError', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
  }
}

const exportCakeBatch = async () => {
  if (!cakeFiles.value.length) return
  taskStatus.cake = 'running'
  consoleLogs.cake.push(t('logs.viewer.exportingBatch', { count: cakeFiles.value.length }))
  try {
    const res = await viewerExportBatchZip({
      files: cakeFiles.value.map(f => ({ fileId: f.fileId, name: f.name })),
      ...exportRenderParams(),
    })
    const save = await saveBlob(res.data, 'cake_export_batch.zip')
    if (save?.ok) {
      consoleLogs.cake.push(save.filePath
        ? `${t('viewer.export.batch')}: ${save.filePath}`
        : t('logs.viewer.exportedBatch', { count: cakeFiles.value.length }))
    }
    taskStatus.cake = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.viewer.exportError', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
  }
}

// The first image's CURRENT display window — pane A when comparing, the
// selected image otherwise. Batch-by-first exports every image rendered with
// this one window instead of the (stale in compare mode) single-view window.
function firstImageContrast() {
  if (compareMode.value && compareSlots[0].fileId && compareSlots[0].data) {
    return { zmin: compareSlots[0].zmin, zmax: compareSlots[0].zmax }
  }
  const idx = selectedCakeFile.value
  if (idx !== null && cakeFiles.value[idx]?.fileId) {
    return { zmin: cakeViewerControls.zmin, zmax: cakeViewerControls.zmax }
  }
  return null
}

const exportCakeBatchByFirst = async () => {
  if (!cakeFiles.value.length) return
  const first = firstImageContrast()
  if (!first) return
  taskStatus.cake = 'running'
  consoleLogs.cake.push(t('logs.viewer.exportingBatch', { count: cakeFiles.value.length }))
  try {
    const res = await viewerExportBatchZip({
      files: cakeFiles.value.map(f => ({ fileId: f.fileId, name: f.name })),
      ...exportRenderParams(first),
    })
    const save = await saveBlob(res.data, 'cake_export_batch_first.zip')
    if (save?.ok) {
      consoleLogs.cake.push(save.filePath
        ? `${t('viewer.export.batchByFirst')}: ${save.filePath}`
        : t('logs.viewer.exportedBatch', { count: cakeFiles.value.length }))
    }
    taskStatus.cake = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.viewer.exportError', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
  }
}

// Export one pane of compare mode with that pane's own contrast window.
const exportCompare = async (slotIdx) => {
  const slot = compareSlots[slotIdx]
  if (!slot?.fileId) return
  taskStatus.cake = 'running'
  try {
    const res = await viewerExportPng({
      fileId: slot.fileId,
      ...exportRenderParams({ zmin: slot.zmin, zmax: slot.zmax }),
    })
    const base = slot.name.replace(/\.[^.]+$/, '') || 'cake_compare'
    const save = await saveBlob(res.data, `${base}_${slotIdx === 0 ? 'A' : 'B'}.png`)
    if (save?.ok) {
      consoleLogs.cake.push(save.filePath
        ? `${t(slotIdx === 0 ? 'viewer.compare.exportA' : 'viewer.compare.exportB')}: ${save.filePath}`
        : `${t(slotIdx === 0 ? 'viewer.compare.exportA' : 'viewer.compare.exportB')}: ${slot.name}`)
    }
    taskStatus.cake = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.viewer.exportError', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
  }
}

// Thumbnail tracking: repaint the thumbnail of the image whose contrast the
// user is tuning (main view or compare pane), debounced for slider drags.
watch(() => [cakeViewerControls.zmin, cakeViewerControls.zmax], () => {
  scheduleThumbRedraw(() => {
    const idx = selectedCakeFile.value
    const entry = idx !== null ? cakeFiles.value[idx] : null
    if (entry?.fileId && thumbDataCache.has(entry.fileId)) {
      rememberContrast(entry.fileId, cakeViewerControls.zmin, cakeViewerControls.zmax)
      renderThumb(entry, cakeViewerControls.zmin, cakeViewerControls.zmax)
    }
  })
})

watch(() => [
  compareSlots[0].zmin, compareSlots[0].zmax,
  compareSlots[1].zmin, compareSlots[1].zmax,
], () => {
  scheduleThumbRedraw(() => {
    compareSlots.forEach(slot => {
      if (!slot.fileId || !slot.data) return
      if (!thumbDataCache.has(slot.fileId)) return
      const entry = findEntryByFileId(slot.fileId)
      if (entry) {
        rememberContrast(slot.fileId, slot.zmin, slot.zmax)
        renderThumb(entry, slot.zmin, slot.zmax)
      }
    })
  })
})

// Colormap switch: repaint every cached thumbnail so previews stay consistent.
watch(() => cakeViewerControls.colormap, () => {
  cakeFiles.value.forEach(entry => {
    if (entry.fileId && thumbDataCache.has(entry.fileId)) {
      renderThumbWithOwnRange(entry)
    }
  })
})
</script>

<style scoped>
.viewer-page {
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
  max-width: 1200px;
}

.panel-layout {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Viewer layout: gallery | image | controls.
   Bounded height (was min-height): with many gallery entries the row used to
   grow with its content, pushing the upload zone off-screen and never letting
   .gallery-scroll scroll. The height comes from --viewer-area-h (set from the
   script, window-height driven) — tall enough that BOTH stacked compare panes
   show in full — and keeps the thumbnails scrolling vertically. */
.viewer-top {
  display: flex;
  gap: 16px;
  height: var(--viewer-area-h, 760px);
}

/* File gallery */
.file-gallery {
  width: 180px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gallery-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.compare-toggle {
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
  border-radius: 6px;
}

.compare-toggle:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.gallery-head-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.gallery-clear {
  height: 24px;
  padding: 0 8px;
  font-size: 11px;
  border-radius: 6px;
}

.gallery-clear:hover {
  color: var(--color-danger, #DC2626);
  border-color: var(--color-danger, #DC2626);
}

/* Per-item delete (×): visible on hover, always shown on touch devices */
.gallery-del {
  position: absolute;
  top: 4px;
  left: 4px;
  z-index: 2;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.gallery-item:hover .gallery-del {
  opacity: 1;
}

.gallery-del:hover {
  background: var(--color-danger, #DC2626);
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

.gallery-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 4px;
}

.gallery-item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.gallery-item:hover {
  border-color: var(--color-text-secondary);
}

.gallery-item.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
}

.gallery-item.compare-a,
.gallery-item.compare-b {
  border-color: var(--color-primary);
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
}

.thumb {
  width: 100%;
  aspect-ratio: 1;
  background: var(--color-neutral);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  image-rendering: auto;
}

.thumb-icon {
  width: 32px;
  height: 32px;
  color: var(--color-text-secondary);
  opacity: 0.5;
}

/* A/B badge: floating on gallery items, inline in the compare pane header */
.compare-tag {
  position: absolute;
  top: 6px;
  right: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: var(--color-primary);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.compare-tag--b {
  background: #D97706;
}

.compare-head .compare-tag {
  position: static;
  flex-shrink: 0;
}

.gallery-name {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gallery-meta {
  font-size: 10px;
  color: var(--color-text-secondary);
}

.gallery-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 10px;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: center;
}

/* Main image area */
.image-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  /* Compare mode stacks two panes; if they ever exceed the bounded row
     height, scroll inside instead of stretching the page. */
  overflow-y: auto;
}

/* ---- Bottom action row: add npy | import npy info file | export ---- */
.viewer-bottom {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  align-items: start;
}
.bottom-module {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.bottom-module-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.bottom-module .drop-zone {
  min-height: 88px;
  padding: 14px 12px;
}
.bottom-module .drop-zone__icon {
  width: 20px;
  height: 20px;
  margin-bottom: 4px;
}
.bottom-module .btn-batch-first {
  border-style: dashed;
}
@media (max-width: 980px) {
  .viewer-bottom { grid-template-columns: 1fr; }
}

.image-canvas-wrap {
  width: 100%;
  height: 100%;
}

/* Compare mode: two full-width panes stacked vertically so each image is as
   large as possible — detail comparison matters more than side-by-side. */
.compare-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.compare-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.compare-head {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 20px;
}

.compare-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compare-placeholder {
  min-height: 220px;
}

.compare-controls .contrast-slot-name {
  font-size: 10px;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contrast-bound {
  font-size: 10px;
  font-weight: 500;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  width: 28px;
  flex-shrink: 0;
}

.image-placeholder {
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.placeholder-icon {
  width: 48px;
  height: 48px;
  color: var(--color-text-secondary);
  opacity: 0.5;
}

.placeholder-hint {
  font-size: 12px;
  opacity: 0.6;
}

.placeholder-file {
  margin-top: 8px;
  padding: 4px 12px;
  background: var(--color-neutral);
  border-radius: 4px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--color-primary);
}

/* Controls panel */
.controls-panel {
  width: 200px;
  flex-shrink: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  /* Stretch to the bounded row and scroll internally so a long control stack
     never overflows the layout. */
  align-self: stretch;
  min-height: 0;
  overflow-y: auto;
}

.controls-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.control-group label {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.control-divider {
  height: 1px;
  background: var(--color-border);
  margin: 4px 0;
}

.param-input {
  height: 32px;
  padding: 0 10px;
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text);
  font-size: 12px;
  font-family: 'Inter', system-ui, sans-serif;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  box-sizing: border-box;
}

.param-input:focus {
  border-color: var(--color-primary);
}

.contrast-slider {
  width: 100%;
  accent-color: var(--color-primary);
  margin: 2px 0;
}

.contrast-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.contrast-input {
  height: 28px;
  font-family: 'JetBrains Mono', monospace;
  text-align: right;
}

.param-frame {
  text-align: center;
  width: 60px;
}

.toggle-btn {
  height: 32px;
  padding: 0 16px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-neutral);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.toggle-btn.active {
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.frame-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.btn-nav {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-neutral);
  color: var(--color-text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-nav:hover {
  background: var(--color-surface);
  color: var(--color-text);
}

/* Buttons */
.btn-secondary {
  height: 34px;
  padding: 0 16px;
  background: transparent;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  font-family: 'Inter', system-ui, sans-serif;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.btn-secondary:hover {
  background: var(--color-surface);
  color: var(--color-text);
  border-color: var(--color-text-secondary);
}

.btn-full {
  width: 100%;
}

/* ---- Axis ranges + χ crop panel ---- */
.viewer-axis {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.axis-head { display: flex; flex-direction: column; gap: 2px; }
.axis-title { font-size: 13px; font-weight: 600; color: var(--color-text); margin: 0; }
.axis-hint { font-size: 11px; color: var(--color-text-secondary); }
.axis-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.info-chip {
  font-size: 11px; font-family: 'JetBrains Mono', monospace;
  padding: 3px 10px; background: var(--color-neutral); border-radius: 4px;
  color: var(--color-primary); max-width: 260px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.axis-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.axis-divider { height: 1px; background: var(--color-border); margin: 2px 0; }
.axis-crop { display: flex; flex-direction: column; gap: 8px; }
.crop-toggle {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--color-text-secondary); cursor: pointer;
}
.crop-toggle input { cursor: pointer; }

@media (max-width: 768px) {
  .axis-grid { grid-template-columns: 1fr 1fr; }
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

  .viewer-top {
    flex-direction: column;
    /* Stacked layout: let the page flow naturally; only the horizontal
       thumbnail strip keeps a bounded height so it scrolls sideways. */
    height: auto;
  }

  .file-gallery {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
  }

  .gallery-scroll {
    flex-direction: row;
    overflow-x: auto;
    overflow-y: hidden;
    max-height: 170px;
  }

  .gallery-item {
    min-width: 120px;
  }

  .controls-panel {
    width: 100%;
  }
}
</style>
