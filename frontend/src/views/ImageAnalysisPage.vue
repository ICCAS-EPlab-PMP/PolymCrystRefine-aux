<template>
  <div class="image-analysis-page">
    <div class="main-container">
      <!-- ===== Sidebar ===== -->
      <aside class="sidebar">
        <nav class="tab-nav">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            :class="['tab-item', { active: activeTab === tab.id }]"
            @click="activeTab = tab.id"
          >
            <svg v-if="tab.id === 'cake'" class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
              <line x1="2" y1="12" x2="22" y2="12" />
            </svg>
            <svg v-else class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="2" width="20" height="20" rx="2" />
              <circle cx="12" cy="12" r="4" />
              <line x1="2" y1="12" x2="8" y2="12" />
              <line x1="16" y1="12" x2="22" y2="12" />
              <line x1="12" y1="2" x2="12" y2="8" />
              <line x1="12" y1="16" x2="12" y2="22" />
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

      <!-- ===== Main Content ===== -->
      <main class="content">
        <transition name="fade" mode="out-in">

          <!-- ============ CAKE ANALYSIS TAB ============ -->
          <div v-if="activeTab === 'cake'" key="cake" class="tab-panel">
            <!-- ===== Top row: Cake image (full width) ===== -->
            <div class="section-card image-main-card" ref="cakeTopRef">
              <div class="section-header">
                <h3>{{ t('analysis.cake.title') }}</h3>
                <div class="section-header-actions">
                  <label class="btn-compact">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                    {{ t('analysis.cake.uploadLabel') }}
                    <input type="file" accept=".npy,.tif,.tiff,.edf,.h5" @change="onCakeFileInput" hidden />
                  </label>
                  <label class="btn-compact" style="margin-left:4px">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                    info.txt
                    <input type="file" accept=".json,.txt" @change="onCakeInfoInput" hidden />
                  </label>
                  <button class="btn-compact btn-primary-compact" :disabled="!cakeFile" @click="loadCakeImage" style="margin-left:4px">{{ t('analysis.cake.btnLoad') }}</button>
                </div>
              </div>
              <div v-if="cakeMeta" class="meta-strip">
                <span><strong>shape:</strong> {{ (cakeMeta.shape || []).join(' × ') }}</span>
                <span><strong>q:</strong> {{ fmtRange(cakeMeta.qRange) }} Å⁻¹</span>
                <span><strong>χ:</strong> {{ fmtRange(cakeMeta.chiRange) }}°</span>
              </div>
              <div class="image-canvas-wrap">
                <ImageCanvas
                  v-if="cakeImageData"
                  ref="cakeImageCanvasRef"
                  :image-data="cakeImageData"
                  :x-axis="cakeXAxis"
                  :y-axis="cakeYAxis"
                  :x-axis-title="t('analysis.cake.xAxisTitle')"
                  :y-axis-title="t('analysis.cake.yAxisTitle')"
                  :colorscale="cakeControls.colormap"
                  :log-scale="cakeControls.logScale"
                  :zmin="cakeControls.zmin"
                  :zmax="cakeControls.zmax"
                  :show-colorbar="false"
                  :show-toolbar="false"
                  :shapes="cakeShapes"
                  :y-range="cakeYRange"
                  :dragmode="cakeDragmode"
                  :overlay-points="millerOverlayPoints"
                  :overlay-color="millerOverlayColor"
                  :roi-labels="cakeRoiLabels"
                  :mask-overlay="cakeBgShowMask && cakeBgEstimate ? cakeBgEstimate.previewMask : null"
                  :title="t('analysis.cake.displayTitle')"
                  :height="520"
                  :smooth-zoom="true"
                  @region-selected="onCakeRegionSelected"
                  @point-clicked="onCakePointClicked"
                />
                <div v-else class="image-placeholder">
                  <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21,15 16,10 5,21" /></svg>
                  <span>{{ t('analysis.cake.placeholder') }}</span>
                  <span class="placeholder-hint">{{ t('analysis.cake.placeholderHint') }}</span>
                </div>
              </div>
            </div>

            <!-- Refine match-box banner (full width, above the sub-tabs so it's
                 always visible regardless of which sub-tab the user is on). -->
            <div class="refine-banner" v-if="cakeRefineDrawing">
              <span class="refine-banner-text">{{ t(cakeRefineShape === 'lasso' ? 'analysis.roi.refineHintLasso' : 'analysis.roi.refineHint', { n: (cakeRefineTarget ?? -1) + 1 }) }}</span>
              <button class="btn-compact" @click="cakeRefineDrawing = false; cakeRefineTarget = null">{{ t('analysis.roi.refineCancel') }}</button>
            </div>

            <!-- ===== Always-visible controls (outside the sub-tabs): Contrast + Region Selection ===== -->
            <div class="controls-row">
              <!-- Contrast (always visible once an image is loaded) -->
              <div class="section-card" v-if="cakeImageData">
                <div class="section-header"><h3>{{ t('analysis.contrast.title') }}</h3></div>
                <div class="contrast-block">
                  <div class="contrast-field">
                    <label class="contrast-block-label">{{ t('analysis.contrast.min') }}</label>
                    <input type="range" :min="cakeContrastRange[0]" :max="cakeContrastRange[1]" v-model.number="cakeControls.zmin" class="contrast-slider" />
                    <input type="number" :min="cakeContrastRange[0]" :max="cakeContrastRange[1]" v-model.number="cakeControls.zmin" class="contrast-num" />
                  </div>
                  <div class="contrast-field">
                    <label class="contrast-block-label">{{ t('analysis.contrast.max') }}</label>
                    <input type="range" :min="cakeContrastRange[0]" :max="cakeContrastRange[1]" v-model.number="cakeControls.zmax" class="contrast-slider" />
                    <input type="number" :min="cakeContrastRange[0]" :max="cakeContrastRange[1]" v-model.number="cakeControls.zmax" class="contrast-num" />
                  </div>
                  <div class="btn-row">
                    <button class="btn-compact" @click="resetCakeContrast">{{ t('analysis.contrast.reset') }}</button>
                  </div>
                </div>
              </div>

              <!-- Region Selection (always visible) -->
              <div class="section-card">
                <div class="section-header">
                  <h3>{{ t('analysis.selection.title') }}</h3>
                  <div class="section-header-actions">
                    <!-- Fixed on/off site for the slice card: visible in every
                         state, so closing/reopening never depends on finding a
                         hidden restore button. -->
                    <button
                      :class="['btn-compact', { 'btn-accent-compact': sliceVisible }]"
                      :title="t('analysis.slice.toggleHint')"
                      :disabled="!cakeImageData"
                      @click="toggleSliceCard"
                    >{{ sliceVisible ? t('analysis.slice.toggleHide') : t('analysis.slice.toggleShow') }}</button>
                    <!-- Dock the floating card back inline from OUTSIDE the
                         card: the card's own header buttons are unreachable
                         when a stale position leaves it off-screen. -->
                    <button
                      v-if="sliceFloating"
                      class="btn-compact"
                      :title="t('analysis.slice.dockToolbarHint')"
                      :disabled="!cakeImageData"
                      @click="dockSliceCard"
                    >{{ t('analysis.slice.dockBtn') }}</button>
                  </div>
                </div>
                <div class="form-row">
                  <button :class="['mode-btn', { active: cakeSelectionMode === 'rough' }]" @click="cakeSelectionMode = 'rough'">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="3" y="3" width="18" height="18" rx="2" /></svg>
                    {{ t('analysis.selection.rough') }}
                  </button>
                  <button :class="['mode-btn', { active: cakeSelectionMode === 'precise' }]" @click="cakeSelectionMode = 'precise'">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><line x1="12" y1="2" x2="12" y2="22" /><line x1="2" y1="12" x2="22" y2="12" /></svg>
                    {{ t('analysis.selection.precise') }}
                  </button>
                </div>
                <div class="selection-info" v-if="cakeHasSelection">
                  <span class="sel-tag">q: [{{ cakeQ1?.toFixed(4) }}, {{ cakeQ2?.toFixed(4) }}]</span>
                  <span class="sel-tag">χ: [{{ cakeAz1?.toFixed(1) }}, {{ cakeAz2?.toFixed(1) }}]°</span>
                </div>
                <!-- Row-click edit mode: the loaded bounds belong to ROI #n, so
                     记录 UPDATES that row instead of appending a new one. -->
                <div class="selection-info" v-if="cakeEditRoiIndex != null">
                  <span class="sel-tag sel-tag--edit">{{ t('analysis.roi.editingHint', { n: cakeEditRoiIndex + 1 }) }}</span>
                  <button class="btn-compact" @click="cancelRoiEdit">{{ t('analysis.roi.btnCancelEdit') }}</button>
                </div>
                <div class="btn-row" style="margin-top:8px">
                  <button class="btn-primary-compact" :disabled="!cakeHasSelection" :title="t('analysis.selection.recordKeyHint')" @click="recordCakeArea">
                    {{ cakeEditRoiIndex != null ? t('analysis.roi.btnUpdate', { n: cakeEditRoiIndex + 1 }) : t('analysis.selection.record') }}
                  </button>
                  <button class="btn-compact" @click="clearCakeSelection">{{ t('analysis.selection.clear') }}</button>
                </div>
                <div class="form-row" style="margin-top:8px">
                  <label class="crop-toggle">
                    <input type="checkbox" v-model="cakeShowRoiLabels" />
                    <span>{{ t('analysis.selection.showLabels') }}</span>
                  </label>
                </div>
              </div>
            </div>

            <!-- Slice Plots (coupled to clicks on the cake above). Inline by
                 default; can pop out into a draggable/resizable floating card
                 (拖动标题栏移动 / 右下角缩放 / × 关闭) so the user can pick
                 slice ranges while watching the cake. -->
            <div
              v-if="cakeImageData && sliceVisible"
              :class="['section-card', 'slice-card', { 'slice-card--floating': sliceFloating }]"
              :style="sliceFloating ? sliceCardStyle : null"
            >
              <div
                class="section-header slice-card__header"
                :class="{ 'slice-card__header--drag': sliceFloating }"
                @pointerdown="startSliceCardDrag"
              >
                <h3>{{ t('analysis.slice.title') }}</h3>
                <span class="section-header-sub" v-if="cakeClickPos">q={{ cakeClickPos.q?.toFixed(4) }}, χ={{ cakeClickPos.chi?.toFixed(1) }}°</span>
                <div class="slice-card__actions" @pointerdown.stop>
                  <button class="btn-compact" @click="sliceFloating = !sliceFloating; persistSliceCard()">
                    {{ sliceFloating ? t('analysis.slice.dockBtn') : t('analysis.slice.floatBtn') }}
                  </button>
                  <button
                    class="btn-icon slice-card__close"
                    :title="t('analysis.slice.hideBtn')"
                    @click="closeSliceCard"
                  >&times;</button>
                </div>
              </div>
              <div class="slice-grid">
                <div class="slice-plot">
                  <div class="slice-plot-label">{{ t('analysis.slice.qSlice') }}</div>
                  <div class="slice-plot-params">
                    <label>{{ t('analysis.slice.integrationWidth') }}</label>
                    <input v-model.number="cakeQSliceAzWidth" type="number" step="0.5" min="0.1" class="param-input param-input-xs" @change="refreshSlicePlots" />
                    <span class="param-unit">°</span>
                  </div>
                  <div class="slice-plot-params">
                    <label>{{ t('analysis.slice.displayRange') }}</label>
                    <input v-model.number="cakeQSliceQRange" type="number" step="0.05" min="0.01" class="param-input param-input-xs" @change="refreshSlicePlots" />
                    <span class="param-unit">Å⁻¹</span>
                  </div>
                  <div ref="qSliceContainer" class="slice-plot-area"></div>
                </div>
                <div class="slice-plot">
                  <div class="slice-plot-label">{{ t('analysis.slice.azimuthSlice') }}</div>
                  <div class="slice-plot-params">
                    <label>{{ t('analysis.slice.integrationWidth') }}</label>
                    <input v-model.number="cakeAzSliceQWidth" type="number" step="0.005" min="0.001" class="param-input param-input-xs" @change="refreshSlicePlots" />
                    <span class="param-unit">Å⁻¹</span>
                  </div>
                  <div class="slice-plot-params">
                    <label>{{ t('analysis.slice.displayRange') }}</label>
                    <input v-model.number="cakeAzSliceAzRange" type="number" step="1" min="1" class="param-input param-input-xs" @change="refreshSlicePlots" />
                    <span class="param-unit">°</span>
                  </div>
                  <div ref="azSliceContainer" class="slice-plot-area"></div>
                </div>
              </div>
              <!-- Quick settings: defaults stamped onto every newly recorded
                   peak (multiplier + background subtraction + refine flow), so
                   a whole series of peaks can be recorded without visiting the
                   ROI table between each one. Shares state with the Settings
                   panel's background card (single source of truth). -->
              <div class="quick-settings">
                <div class="quick-settings__title">{{ t('analysis.slice.quickTitle') }}</div>
                <div class="quick-settings__row">
                  <label class="quick-field">
                    <span>{{ t('analysis.roi.columns.multiplier') }}</span>
                    <select v-model.number="cakeQuickMultiplier" class="param-input param-input-xs">
                      <option :value="0">0</option>
                      <option :value="1">1</option>
                      <option :value="2">2</option>
                      <option :value="4">4</option>
                    </select>
                  </label>
                  <label class="quick-field">
                    <span>{{ t('analysis.background.mode') }}</span>
                    <select v-model="cakeBgMode" class="param-input param-input-xs">
                      <option value="none">{{ t('analysis.background.modes.none') }}</option>
                      <option value="fixed">{{ t('analysis.background.modes.fixed') }}</option>
                      <option value="neighbor">{{ t('analysis.background.modes.neighbor') }}</option>
                      <option value="dbscan">{{ t('analysis.background.modes.dbscan') }}</option>
                    </select>
                  </label>
                  <label v-if="cakeBgMode === 'fixed'" class="quick-field">
                    <span>{{ t('analysis.background.fixedValue') }}</span>
                    <input v-model.number="cakeBgValue" type="number" step="0.01" class="param-input param-input-xs" />
                  </label>
                  <template v-else-if="cakeBgMode === 'neighbor'">
                    <label class="quick-field">
                      <span>{{ t('analysis.background.side') }}</span>
                      <select v-model="cakeBgSide" class="param-input param-input-xs">
                        <option value="left">{{ t('analysis.roi.bgSides.left') }}</option>
                        <option value="right">{{ t('analysis.roi.bgSides.right') }}</option>
                        <option value="both">{{ t('analysis.roi.bgSides.both') }}</option>
                      </select>
                    </label>
                    <label class="quick-field">
                      <span>{{ t('analysis.background.neighborWidth') }}</span>
                      <input v-model.number="cakeBgWidth" type="number" step="1" min="0" class="param-input param-input-xs" />
                    </label>
                  </template>
                  <label v-else-if="cakeBgMode === 'dbscan' && cakeBgEstimate" class="quick-field quick-field--value">
                    <span>{{ t('analysis.background.dbscan.backgroundLevel') }}</span>
                    <span class="quick-value">{{ cakeBgEstimate.backgroundValue.toFixed(2) }}</span>
                  </label>
                  <label class="quick-field">
                    <span>{{ t('analysis.roi.refineShape') }}</span>
                    <select v-model="cakeRefineShape" class="param-input param-input-xs">
                      <option value="rect">{{ t('analysis.roi.refineShapeRect') }}</option>
                      <option value="lasso">{{ t('analysis.roi.refineShapeLasso') }}</option>
                    </select>
                  </label>
                  <div class="quick-settings__actions">
                    <button
                      class="btn-compact"
                      :disabled="!cakeRois.length"
                      :title="t('analysis.slice.quickRefineHint')"
                      @click="quickStartRefine"
                    >{{ t('analysis.slice.quickRefineBtn') }}</button>
                  </div>
                </div>
              </div>
              <div
                v-if="sliceFloating"
                class="slice-card__resize"
                :title="t('analysis.slice.resizeHint')"
                @pointerdown="startSliceCardResize"
              ></div>
            </div>

            <!-- ===== Sub-tabs: Settings | ROI Info (full-page switch) ===== -->
            <div class="sub-tabs">
              <button :class="['sub-tab', { active: cakePanel === 'settings' }]" @click="cakePanel = 'settings'">
                {{ t('analysis.cake.panels.settings') }}
              </button>
              <button :class="['sub-tab', { active: cakePanel === 'roi' }]" @click="cakePanel = 'roi'">
                {{ t('analysis.cake.panels.roi') }}
              </button>
            </div>

            <!-- ===== Settings panel: all control cards, 2 per row ===== -->
            <div v-if="cakePanel === 'settings'" class="settings-grid">
              <!-- Display Controls -->
              <div class="section-card">
                <div class="section-header"><h3>{{ t('analysis.controls.title') }}</h3></div>
                <div class="form-grid-2">
                  <div class="form-field-stack">
                    <label>{{ t('analysis.controls.colormap') }}</label>
                    <select v-model="cakeControls.colormap" class="param-input">
                      <option value="Viridis">Viridis</option><option value="Plasma">Plasma</option><option value="Inferno">Inferno</option><option value="Magma">Magma</option><option value="Gray">Grayscale</option><option value="Jet">Jet</option><option value="Hot">Hot</option>
                    </select>
                  </div>
                  <div class="form-field-stack">
                    <label>{{ t('analysis.controls.logScale') }}</label>
                    <button :class="['toggle-btn', { active: cakeControls.logScale }]" @click="cakeControls.logScale = !cakeControls.logScale">{{ cakeControls.logScale ? t('common.on') : t('common.off') }}</button>
                  </div>
                </div>
              </div>

              <!-- χ-Axis crop (image only) -->
              <div class="section-card" v-if="cakeImageData">
                <div class="section-header"><h3>{{ t('analysis.crop.title') }}</h3></div>
                <div class="form-row">
                  <label class="crop-toggle">
                    <input type="checkbox" v-model="cakeCropEnabled" />
                    <span>{{ t('analysis.crop.enable') }}</span>
                  </label>
                </div>
                <div class="form-grid-2" style="margin-top:8px">
                  <div class="form-field-stack">
                    <label>{{ t('analysis.crop.chiMin') }}</label>
                    <input v-model.number="cakeCropChiMin" type="number" step="1" class="param-input" />
                  </div>
                  <div class="form-field-stack">
                    <label>{{ t('analysis.crop.chiMax') }}</label>
                    <input v-model.number="cakeCropChiMax" type="number" step="1" class="param-input" />
                  </div>
                </div>
                <div class="btn-row" style="margin-top:8px">
                  <button class="btn-compact" @click="resetCakeCrop">{{ t('analysis.crop.reset') }}</button>
                </div>
              </div>

              <!-- Background Settings -->
              <div class="section-card">
                <div class="section-header"><h3>{{ t('analysis.background.title') }}</h3></div>
                <div class="panel-hint">{{ t('analysis.background.perPeakHint') }}</div>
                <div class="form-field-stack">
                  <label>{{ t('analysis.background.mode') }}</label>
                  <select v-model="cakeBgMode" class="param-input">
                    <option value="none">{{ t('analysis.background.modes.none') }}</option>
                    <option value="fixed">{{ t('analysis.background.modes.fixed') }}</option>
                    <option value="neighbor">{{ t('analysis.background.modes.neighbor') }}</option>
                    <option value="dbscan">{{ t('analysis.background.modes.dbscan') }}</option>
                  </select>
                </div>
                <div v-if="cakeBgMode === 'fixed'" class="form-field-stack" style="margin-top:8px">
                  <label>{{ t('analysis.background.fixedValue') }}</label>
                  <input v-model.number="cakeBgValue" type="number" step="0.01" class="param-input" />
                </div>
                <div v-if="cakeBgMode === 'neighbor'" class="form-grid-2" style="margin-top:8px">
                  <div class="form-field-stack">
                    <label>{{ t('analysis.background.side') }}</label>
                    <select v-model="cakeBgSide" class="param-input">
                      <option value="left">{{ t('analysis.background.sides.left') }}</option>
                      <option value="right">{{ t('analysis.background.sides.right') }}</option>
                      <option value="both">{{ t('analysis.background.sides.both') }}</option>
                    </select>
                  </div>
                  <div class="form-field-stack"><label>{{ t('analysis.background.neighborWidth') }}</label><input v-model.number="cakeBgWidth" type="number" step="1" min="0" class="param-input" /></div>
                </div>

                <!-- DBSCAN cluster-based background estimation -->
                <template v-if="cakeBgMode === 'dbscan'">
                  <div class="form-grid-2" style="margin-top:8px">
                    <div class="form-field-stack">
                      <label>{{ t('analysis.background.dbscan.thresholdPercentile') }}</label>
                      <input v-model.number="cakeBgParams.thresholdPercentile" type="number" step="1" min="0" max="100" class="param-input" />
                    </div>
                    <div class="form-field-stack">
                      <label>eps</label>
                      <input v-model.number="cakeBgParams.eps" type="number" step="0.005" min="0.001" max="1" class="param-input" />
                    </div>
                    <div class="form-field-stack">
                      <label>{{ t('analysis.background.dbscan.minSamples') }}</label>
                      <input v-model.number="cakeBgParams.minSamples" type="number" step="1" min="1" class="param-input" />
                    </div>
                    <div class="form-field-stack">
                      <label>{{ t('analysis.background.dbscan.minClusterPixels') }}</label>
                      <input v-model.number="cakeBgParams.minClusterPixels" type="number" step="1" min="1" class="param-input" />
                    </div>
                    <div class="form-field-stack">
                      <label>{{ t('analysis.background.dbscan.dilationPixels') }}</label>
                      <input v-model.number="cakeBgParams.dilationPixels" type="number" step="1" min="0" max="20" class="param-input" />
                    </div>
                    <div class="form-field-stack">
                      <label>{{ t('analysis.background.dbscan.backgroundPercentile') }}</label>
                      <input v-model.number="cakeBgParams.backgroundPercentile" type="number" step="1" min="0" max="100" class="param-input" />
                    </div>
                  </div>
                  <div class="btn-row" style="margin-top:10px">
                    <button
                      class="btn-compact btn-primary-compact"
                      :disabled="!cakeImageFileId || cakeBgEstimating"
                      @click="estimateCakeBackground"
                    >{{ cakeBgEstimating ? t('analysis.background.dbscan.estimating') : t('analysis.background.dbscan.btnEstimate') }}</button>
                    <button
                      v-if="cakeBgEstimate"
                      class="btn-compact btn-accent-compact"
                      :title="t('analysis.background.dbscan.applyHint')"
                      @click="applyCakeBackground"
                    >{{ t('analysis.background.dbscan.btnApply') }} ({{ cakeBgEstimate.backgroundValue.toFixed(2) }})</button>
                    <label v-if="cakeBgEstimate" class="crop-toggle">
                      <input type="checkbox" v-model="cakeBgShowMask" />
                      <span>{{ t('analysis.background.dbscan.showMask') }}</span>
                    </label>
                  </div>
                  <div v-if="cakeBgEstimate" class="bg-estimate-result">
                    <div class="bg-estimate-line">
                      <span><b>{{ t('analysis.background.dbscan.backgroundLevel') }}:</b> {{ cakeBgEstimate.backgroundValue.toFixed(3) }}</span>
                      <span><b>{{ t('analysis.background.dbscan.thresholdLabel') }}:</b> {{ cakeBgEstimate.threshold.toFixed(2) }}</span>
                      <span><b>{{ t('analysis.background.dbscan.clustersLabel') }}:</b> {{ cakeBgEstimate.nClusters }}</span>
                    </div>
                    <div class="bg-estimate-line">
                      <span><b>{{ t('analysis.background.dbscan.peakPx') }}:</b> {{ cakeBgEstimate.peakPixelCount }}</span>
                      <span><b>{{ t('analysis.background.dbscan.bgPx') }}:</b> {{ cakeBgEstimate.backgroundPixelCount }}</span>
                    </div>
                    <div v-if="cakeBgEstimate.clusters.length" class="bg-cluster-list">
                      <div v-for="(c, ci) in cakeBgEstimate.clusters.slice(0, 12)" :key="ci" class="bg-cluster-row">
                        <span>#{{ ci + 1 }}</span>
                        <span>q={{ c.q.toFixed(3) }}</span>
                        <span>χ={{ c.chi.toFixed(1) }}°</span>
                        <span>{{ c.pixels }}px</span>
                        <span>Ø{{ c.meanIntensity.toFixed(1) }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="dbscan-hint">{{ t('analysis.background.dbscan.hint') }}</div>
                </template>
              </div>

              <!-- Saturation / bad-pixel masking -->
              <div class="section-card">
                <div class="section-header"><h3>{{ t('analysis.saturation.title') }}</h3></div>
                <div class="form-field-stack">
                  <label>{{ t('analysis.saturation.min') }}</label>
                  <input v-model.number="cakeSaturationMin" type="number" step="any" class="param-input" placeholder="0" />
                </div>
                <div class="form-field-stack">
                  <label>{{ t('analysis.saturation.max') }}</label>
                  <input v-model.number="cakeSaturationMax" type="number" step="any" class="param-input" placeholder="—" />
                </div>
                <div class="btn-row" style="margin-top:8px">
                  <button class="btn-compact" @click="autoCakeSaturation">{{ t('analysis.saturation.auto') }}</button>
                  <button class="btn-compact" @click="cakeSaturationMax = null">{{ t('analysis.saturation.clear') }}</button>
                </div>
                <div style="margin-top:6px; font-size:11px; color: var(--color-text-secondary)">{{ t('analysis.saturation.hint') }}</div>
              </div>

              <!-- Miller Overlay -->
              <div class="section-card">
                <div class="section-header"><h3>{{ t('analysis.miller.title') }}</h3></div>
                <div class="btn-row">
                  <label class="btn-compact">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                    {{ t('analysis.miller.uploadLabel') }}
                    <input type="file" accept=".txt,.json" multiple @change="onMillerFileInput" hidden />
                  </label>
                  <button class="btn-compact btn-primary-compact" :disabled="!millerFiles.length" @click="loadMillerOverlay" style="margin-left:4px">{{ t('analysis.miller.btnLoad') }}</button>
                </div>
                <div class="form-grid-2" style="margin-top:8px">
                  <div class="form-field-stack"><label>{{ t('analysis.miller.convention') }}</label><select v-model="millerConvention" class="param-input"><option value="CCW">CCW</option><option value="CW">CW</option></select></div>
                  <div class="form-field-stack"><label>{{ t('analysis.miller.azimuthOffset') }}</label><input v-model.number="millerAzimuthOffset" type="number" step="1" class="param-input" /></div>
                </div>
                <div class="form-grid-2" style="margin-top:8px">
                  <div class="form-field-stack"><label>{{ t('analysis.miller.qTolerance') }}</label><input v-model.number="millerQTolerance" type="number" step="0.01" min="0" class="param-input" /></div>
                  <div class="form-field-stack"><label>{{ t('analysis.miller.chiTolerance') }}</label><input v-model.number="millerChiTolerance" type="number" step="0.5" min="0" class="param-input" /></div>
                </div>
                <!-- 精致化/导出边距：导出的 q/ψ 范围 = 选区（或精致化选区）内
                     Miller 点的最小/最大值 ± 这两个边距；未匹配时 = 选区框 ± 边距。 -->
                <div class="form-grid-2" style="margin-top:8px">
                  <div class="form-field-stack"><label>{{ t('analysis.miller.exportQMargin') }}</label><input v-model.number="millerExportQMargin" type="number" step="0.005" min="0" class="param-input" /></div>
                  <div class="form-field-stack"><label>{{ t('analysis.miller.exportPsiMargin') }}</label><input v-model.number="millerExportPsiMargin" type="number" step="0.5" min="0" class="param-input" /></div>
                </div>
                <div class="miller-margin-hint">{{ t('analysis.miller.marginHint') }}</div>
                <div class="form-grid-2" style="margin-top:8px">
                  <div class="form-field-stack">
                    <label>{{ t('analysis.miller.showPoints') }}</label>
                    <button :class="['toggle-btn', { active: millerShowPoints }]" @click="millerShowPoints = !millerShowPoints">{{ millerShowPoints ? t('common.on') : t('common.off') }}</button>
                  </div>
                  <div class="form-field-stack">
                    <label>{{ t('analysis.miller.pointColor') }}</label>
                    <div class="color-row">
                      <input type="color" v-model="millerPointColor" class="color-input" :title="t('analysis.miller.pointColor')" />
                      <button class="btn-compact" @click="millerPointColor = '#9CA3AF'">{{ t('analysis.miller.colorReset') }}</button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Console (full width, spanning both grid columns) -->
              <div class="settings-full" v-if="consoleLogs.cake.length || taskStatus.cake !== 'idle'">
                <ConsolePanel :status="taskStatus.cake" :logs="consoleLogs.cake" />
              </div>
            </div>

            <!-- ===== ROI Info panel (full-page) ===== -->
            <div v-else-if="cakePanel === 'roi'">
              <div class="section-card roi-section" v-if="cakeImageData">
                <div class="section-header">
                  <h3>{{ t('analysis.roi.titleRecords') }} ({{ cakeRois.length }})</h3>
                  <div class="section-header-actions">
                    <button class="btn-compact" @click="addRoi">{{ t('analysis.roi.btnAdd') }}</button>
                    <button class="btn-compact" @click="importCakeRois">{{ t('analysis.roi.btnImport') }}</button>
                    <button class="btn-compact" @click="exportRois">{{ t('analysis.roi.btnExport') }}</button>
                    <button class="btn-compact btn-primary-compact" @click="calculateIntensity" style="margin-left:6px">
                      {{ t('analysis.roi.btnCalculate') }}
                    </button>
                    <button class="btn-compact btn-accent-compact" @click="exportMatchedIntensity" style="margin-left:6px" v-if="millerDatasets.length">
                      {{ t('analysis.roi.btnExportMatched') }}
                    </button>
                  </div>
                </div>
                <div class="roi-table-wrap">
                  <table class="roi-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>{{ t('analysis.roi.columns.qMin') }}</th>
                        <th>{{ t('analysis.roi.columns.qMax') }}</th>
                        <th>{{ t('analysis.roi.columns.azimuthMin') }}</th>
                        <th>{{ t('analysis.roi.columns.azimuthMax') }}</th>
                        <th>{{ t('analysis.roi.columns.multiplier') }}</th>
                        <th>{{ t('analysis.roi.columns.bgMode') }}</th>
                        <th>{{ t('analysis.roi.columns.bgParams') }}</th>
                        <th>{{ t('analysis.roi.columns.intensity') }}</th>
                        <th>{{ t('analysis.roi.columns.pixels') }}</th>
                        <th>{{ t('analysis.roi.columns.label') }}</th>
                        <th>{{ t('analysis.roi.columns.match') }}</th>
                        <th>{{ t('analysis.roi.columns.matchPsi') }}</th>
                        <th>{{ t('analysis.roi.columns.matchQ') }}</th>
                        <th>{{ t('analysis.roi.columns.refine') }}</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(roi, i) in cakeRois"
                        :key="i"
                        :class="{ 'row-selected': cakeSelectedRoiIndex === i }"
                        :title="t('analysis.roi.rowClickHint')"
                        @click="selectRoiRow(i)"
                      >
                        <td class="td-idx">{{ i + 1 }}</td>
                        <td><input v-model.number="roi.qMin" type="number" step="0.001" class="cell-input" /></td>
                        <td><input v-model.number="roi.qMax" type="number" step="0.001" class="cell-input" /></td>
                        <td><input v-model.number="roi.azimuthMin" type="number" step="0.1" class="cell-input" /></td>
                        <td><input v-model.number="roi.azimuthMax" type="number" step="0.1" class="cell-input" /></td>
                        <td>
                          <select v-model.number="roi.multiplier" class="cell-input cell-select">
                            <option :value="0">0</option>
                            <option :value="1">1</option>
                            <option :value="2">2</option>
                            <option :value="4">4</option>
                          </select>
                        </td>
                        <td>
                          <select v-model="roi.bgMode" class="cell-input cell-select" :title="t('analysis.background.perPeakHint')">
                            <option value="none">{{ t('analysis.background.modes.none') }}</option>
                            <option value="fixed">{{ t('analysis.background.modes.fixed') }}</option>
                            <option value="neighbor">{{ t('analysis.background.modes.neighbor') }}</option>
                          </select>
                        </td>
                        <td class="td-bg-params">
                          <input
                            v-if="roi.bgMode === 'fixed'"
                            v-model.number="roi.bgFixedValue"
                            type="number" step="0.01" class="cell-input"
                            :title="t('analysis.background.fixedValue')"
                          />
                          <template v-else-if="roi.bgMode === 'neighbor'">
                            <select v-model="roi.bgSide" class="cell-input cell-select" :title="t('analysis.background.side')">
                              <option value="left">{{ t('analysis.roi.bgSides.left') }}</option>
                              <option value="right">{{ t('analysis.roi.bgSides.right') }}</option>
                              <option value="both">{{ t('analysis.roi.bgSides.both') }}</option>
                            </select>
                            <input
                              v-model.number="roi.bgWidth"
                              type="number" step="1" min="0" class="cell-input cell-input-narrow"
                              :title="t('analysis.background.neighborWidth')"
                            />
                          </template>
                          <span v-else>—</span>
                        </td>
                        <td class="td-num">{{ roi.intensity != null ? roi.intensity.toFixed(2) : '—' }}</td>
                        <td class="td-num">{{ roi.pixelCount || '—' }}</td>
                        <td><input v-model="roi.label" class="cell-input" /></td>
                        <td class="td-match">{{ roi.matchHkl || '—' }}</td>
                        <td class="td-num td-compact">{{ roi.exportPsiMin != null && roi.exportPsiMax != null ? `${roi.exportPsiMin.toFixed(1)}~${roi.exportPsiMax.toFixed(1)}` : '—' }}</td>
                        <td class="td-num td-compact">{{ roi.exportQMin != null && roi.exportQMax != null ? `${roi.exportQMin.toFixed(3)}~${roi.exportQMax.toFixed(3)}` : '—' }}</td>
                        <td>
                          <button
                            :class="['refine-btn', { active: roi.matchQMin != null }]"
                            :title="roi.matchQMin != null ? t('analysis.roi.btnClearRefine') : t('analysis.roi.btnSetRefine')"
                            @click.stop="roi.matchQMin != null ? clearRefineMatch(i) : startRefineMatch(i)"
                          >
                            <span v-if="roi.matchQMin != null">✓</span><span v-else>·</span>
                          </button>
                        </td>
                        <td><button class="btn-icon" @click.stop="cakeRois.splice(i, 1); if (cakeSelectedRoiIndex === i) cakeSelectedRoiIndex = null">&times;</button></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <div v-else class="empty-panel-hint">{{ t('analysis.cake.placeholderHint') }}</div>
            </div>

            <!-- Export bar: full-image PNG only. The SVG / raw-data CSV / NPY
                 buttons were removed — every one of them serialized either the
                 canvas viewport or a redundant dump nobody used. -->
            <div class="export-bar">
              <button class="btn-secondary" :title="t('analysis.export.pngFullHint')" @click="exportImage('png')">{{ t('analysis.export.png') }}</button>
            </div>
          </div>

          <!-- ============ DETECTOR ANALYSIS TAB ============ -->
          <div v-else-if="activeTab === 'detector'" key="detector" class="tab-panel">
            <div class="content-grid">
              <!-- LEFT COLUMN: Image -->
              <div class="left-panel">
                <div class="section-card">
                  <div class="section-header">
                    <h3>{{ t('analysis.detector.title') }}</h3>
                    <div class="section-header-actions">
                      <label class="btn-compact">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                          <polyline points="17,8 12,3 7,8"/>
                          <line x1="12" y1="3" x2="12" y2="15"/>
                        </svg>
                        {{ t('analysis.detector.uploadLabel') }}
                        <input type="file" accept=".tif,.tiff,.edf,.npy,.h5,.cbf" @change="onDetectorFileInput" hidden />
                      </label>
                      <button class="btn-compact btn-primary-compact" :disabled="!detectorFile" @click="loadDetectorImage" style="margin-left:6px">
                        {{ t('analysis.detector.btnLoad') }}
                      </button>
                    </div>
                  </div>
                  <div v-if="detectorMeta" class="meta-strip">
                    <span><strong>shape:</strong> {{ (detectorMeta.shape || []).join(' × ') }}</span>
                    <span><strong>dtype:</strong> {{ detectorMeta.dtype }}</span>
                  </div>
                  <div class="image-canvas-wrap">
                    <ImageCanvas
                      v-if="detectorImageData"
                      ref="detectorImageCanvasRef"
                      :image-data="detectorImageData"
                      :colorscale="detectorControls.colormap"
                      :log-scale="detectorControls.logScale"
                      :show-colorbar="false"
                      :show-toolbar="false"
                      :title="t('analysis.detector.displayTitle')"
                      :smooth-zoom="true"
                      @region-selected="onDetectorRegionSelected"
                    />
                    <div v-else class="image-placeholder">
                      <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="2" y="2" width="20" height="20" rx="2" />
                        <circle cx="12" cy="12" r="4" />
                      </svg>
                      <span>{{ t('analysis.detector.placeholder') }}</span>
                      <span class="placeholder-hint">{{ t('analysis.detector.placeholderHint') }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- RIGHT COLUMN: Controls + Records -->
              <div class="right-panel">
                <div class="section-card">
                  <div class="section-header">
                    <h3>{{ t('analysis.controls.title') }}</h3>
                  </div>
                  <div class="form-grid-2">
                    <div class="form-field-stack">
                      <label>{{ t('analysis.controls.colormap') }}</label>
                      <select v-model="detectorControls.colormap" class="param-input">
                        <option value="Viridis">Viridis</option>
                        <option value="Plasma">Plasma</option>
                        <option value="Inferno">Inferno</option>
                        <option value="Gray">Grayscale</option>
                        <option value="Hot">Hot</option>
                      </select>
                    </div>
                    <div class="form-field-stack">
                      <label>{{ t('analysis.controls.logScale') }}</label>
                      <button :class="['toggle-btn', { active: detectorControls.logScale }]" @click="detectorControls.logScale = !detectorControls.logScale">
                        {{ detectorControls.logScale ? t('common.on') : t('common.off') }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Background Settings for Detector -->
                <div class="section-card">
                  <div class="section-header">
                    <h3>{{ t('analysis.background.title') }}</h3>
                  </div>
                  <div class="form-field-stack">
                    <label>{{ t('analysis.background.mode') }}</label>
                    <select v-model="detectorBgMode" class="param-input">
                      <option value="none">{{ t('analysis.background.modes.none') }}</option>
                      <option value="fixed">{{ t('analysis.background.modes.fixed') }}</option>
                      <option value="neighbor">{{ t('analysis.background.modes.neighbor') }}</option>
                    </select>
                  </div>
                  <div v-if="detectorBgMode === 'fixed'" class="form-field-stack" style="margin-top:8px">
                    <label>{{ t('analysis.background.fixedValue') }}</label>
                    <input v-model.number="detectorBgValue" type="number" step="0.01" class="param-input" />
                  </div>
                  <div v-if="detectorBgMode === 'neighbor'" class="form-grid-2" style="margin-top:8px">
                    <div class="form-field-stack">
                      <label>{{ t('analysis.background.side') }}</label>
                      <select v-model="detectorBgSide" class="param-input">
                        <option value="left">{{ t('analysis.background.sides.left') }}</option>
                        <option value="right">{{ t('analysis.background.sides.right') }}</option>
                        <option value="both">{{ t('analysis.background.sides.both') }}</option>
                      </select>
                    </div>
                    <div class="form-field-stack">
                      <label>{{ t('analysis.background.neighborWidth') }}</label>
                      <input v-model.number="detectorBgWidth" type="number" step="1" min="0" class="param-input" />
                    </div>
                  </div>
                </div>

                <!-- Saturation / bad-pixel masking -->
                <div class="section-card">
                  <div class="section-header"><h3>{{ t('analysis.saturation.title') }}</h3></div>
                  <div class="form-field-stack">
                    <label>{{ t('analysis.saturation.min') }}</label>
                    <input v-model.number="detectorSaturationMin" type="number" step="any" class="param-input" placeholder="0" />
                  </div>
                  <div class="form-field-stack">
                    <label>{{ t('analysis.saturation.max') }}</label>
                    <input v-model.number="detectorSaturationMax" type="number" step="any" class="param-input" placeholder="—" />
                  </div>
                  <div class="btn-row" style="margin-top:8px">
                    <button class="btn-compact" @click="autoDetectorSaturation">{{ t('analysis.saturation.auto') }}</button>
                    <button class="btn-compact" @click="detectorSaturationMax = null">{{ t('analysis.saturation.clear') }}</button>
                  </div>
                  <div style="margin-top:6px; font-size:11px; color: var(--color-text-secondary)">{{ t('analysis.saturation.hint') }}</div>
                </div>

                <ConsolePanel
                  v-if="consoleLogs.detector.length || taskStatus.detector !== 'idle'"
                  :status="taskStatus.detector"
                  :logs="consoleLogs.detector"
                />
              </div>
            </div>

            <!-- Detector ROI Table -->
            <div class="section-card roi-section" v-if="detectorImageData">
              <div class="section-header">
                <h3>{{ t('analysis.roi.titleDetector') }} ({{ detectorRois.length }})</h3>
                <div class="section-header-actions">
                  <button class="btn-compact" @click="addDetectorRoi">{{ t('analysis.roi.btnAdd') }}</button>
                  <button class="btn-compact btn-primary-compact" @click="calculateDetectorIntensity" style="margin-left:6px">
                    {{ t('analysis.roi.btnCalculate') }}
                  </button>
                </div>
              </div>
              <div class="roi-table-wrap">
                <table class="roi-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>{{ t('analysis.roi.columns.xMin') }}</th>
                      <th>{{ t('analysis.roi.columns.xMax') }}</th>
                      <th>{{ t('analysis.roi.columns.yMin') }}</th>
                      <th>{{ t('analysis.roi.columns.yMax') }}</th>
                      <th>{{ t('analysis.roi.columns.multiplier') }}</th>
                      <th>{{ t('analysis.roi.columns.intensity') }}</th>
                      <th>{{ t('analysis.roi.columns.pixels') }}</th>
                      <th>{{ t('analysis.roi.columns.label') }}</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(roi, i) in detectorRois" :key="i">
                      <td class="td-idx">{{ i + 1 }}</td>
                      <td><input v-model.number="roi.xMin" type="number" step="1" class="cell-input" /></td>
                      <td><input v-model.number="roi.xMax" type="number" step="1" class="cell-input" /></td>
                      <td><input v-model.number="roi.yMin" type="number" step="1" class="cell-input" /></td>
                      <td><input v-model.number="roi.yMax" type="number" step="1" class="cell-input" /></td>
                      <td>
                        <select v-model.number="roi.multiplier" class="cell-input cell-select">
                          <option :value="0">0</option>
                          <option :value="1">1</option>
                          <option :value="2">2</option>
                          <option :value="4">4</option>
                        </select>
                      </td>
                      <td class="td-num">{{ roi.intensity != null ? roi.intensity.toFixed(2) : '—' }}</td>
                      <td class="td-num">{{ roi.pixelCount || '—' }}</td>
                      <td><input v-model="roi.label" class="cell-input" /></td>
                      <td><button class="btn-icon" @click="detectorRois.splice(i, 1)">&times;</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="export-bar">
              <button class="btn-secondary" :title="t('analysis.export.pngFullHint')" @click="exportImage('png')">{{ t('analysis.export.png') }}</button>
            </div>
          </div>

        </transition>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import Plotly from 'plotly.js-dist-min'
import ImageCanvas from '@/components/ImageCanvas.vue'
import ConsolePanel from '@/components/ConsolePanel.vue'
import { isElectron } from '@/services/runtime'
import { parseRoiCsv } from '@/services/roiCsv'
import { renderFullImageDataUrl } from '@/services/imageExport'
import {
  analysisUploadImage,
  analysisUploadMiller,
  analysisGetImage,
  analysisParseInfo,
  analysisCalculateIntensity,
  analysisEstimateBackground,
  analysisMatchMiller,
} from '@/api/index.js'

const { t } = useI18n()

const tabs = computed(() => [
  { id: 'cake', label: t('analysis.tabs.cake') },
  { id: 'detector', label: t('analysis.tabs.detector') },
])

const activeTab = ref('cake')
const runStatus = ref('idle')

const statusClass = computed(() => {
  if (runStatus.value === 'completed') return 'success'
  if (runStatus.value === 'failed') return 'error'
  return runStatus.value
})

const statusLabel = computed(() => t(`status.${runStatus.value}`))

const taskStatus = reactive({ cake: 'idle', detector: 'idle' })
const consoleLogs = reactive({ cake: [], detector: [] })

// ===================== CAKE ANALYSIS STATE =====================
const cakeFile = ref(null)
const cakeInfoFile = ref(null)
const cakeImageData = ref(null)
const cakeImageFileId = ref(null)
const cakeMeta = ref(null)
const cakeImageCanvasRef = ref(null)
const cakeTopRef = ref(null)   // top of the cake image card — used to scroll into view when starting a refine-box drag
const detectorImageCanvasRef = ref(null)

const cakeControls = reactive({
  colormap: 'Viridis',
  logScale: false,
  zmin: 0,
  zmax: 100,
})

const cakeContrastRange = ref([0, 65535]) // dynamic range from image data

function resetCakeContrast() {
  cakeControls.zmin = cakeContrastRange.value[0]
  cakeControls.zmax = cakeContrastRange.value[1]
}

// Physical axes for the cake heatmap, derived from the info-file ranges and
// the (downsampled) display data dimensions. x = q (cols), y = chi (rows).
// Without these the canvas falls back to pixel indices (0..N), which is why
// the axis read 0-510 instead of 0-5.1 and slice clicks returned pixel coords.
const cakeXAxis = computed(() => {
  const data = cakeImageData.value
  const qr = cakeMeta.value?.qRange
  if (!data || !Array.isArray(qr) || qr.length < 2) return null
  const cols = data[0]?.length || 0
  if (cols < 1) return null
  if (cols === 1) return [qr[0]]
  const [q0, q1] = qr
  return Array.from({ length: cols }, (_, i) => q0 + (i / (cols - 1)) * (q1 - q0))
})
const cakeYAxis = computed(() => {
  const data = cakeImageData.value
  const cr = cakeMeta.value?.chiRange
  if (!data || !Array.isArray(cr) || cr.length < 2) return null
  const rows = data.length
  if (rows < 1) return null
  if (rows === 1) return [cr[0]]
  const [c0, c1] = cr
  return Array.from({ length: rows }, (_, i) => c0 + (i / (rows - 1)) * (c1 - c0))
})

// Recorded ROIs + the live selection, drawn as yellow rectangles on the cake.
// Solid for recorded regions, dashed for the in-progress selection (item 3).
// The currently selected table row gets a white, thicker frame so clicking a
// record visibly highlights its box on the image.
const cakeShapes = computed(() => {
  const shapes = []
  cakeRois.value.forEach((r, idx) => {
    if (r.qMin == null || r.qMax == null || r.azimuthMin == null || r.azimuthMax == null) return
    const sel = cakeSelectedRoiIndex.value === idx
    shapes.push({
      type: 'rect', xref: 'x', yref: 'y',
      x0: r.qMin, x1: r.qMax, y0: r.azimuthMin, y1: r.azimuthMax,
      line: { color: sel ? '#FFFFFF' : '#EAB308', width: sel ? 3 : 2 },
      fillcolor: sel ? 'rgba(255,255,255,0.16)' : 'rgba(234, 179, 8, 0.08)',
    })
    // Optional refine match-box (cyan dashed) drawn over the integration ROI.
    // Its presence means Miller matching/export is restricted to this small box.
    if (r.matchQMin != null && r.matchQMax != null && r.matchAzMin != null && r.matchAzMax != null) {
      shapes.push({
        type: 'rect', xref: 'x', yref: 'y',
        x0: r.matchQMin, x1: r.matchQMax, y0: r.matchAzMin, y1: r.matchAzMax,
        line: { color: '#22D3EE', width: 1.5, dash: 'dash' },
        fillcolor: 'rgba(34, 211, 238, 0.10)',
      })
    }
  })
  if (cakeHasSelection.value) {
    shapes.push({
      type: 'rect', xref: 'x', yref: 'y',
      x0: cakeQ1.value, x1: cakeQ2.value, y0: cakeAz1.value, y1: cakeAz2.value,
      line: { color: '#EAB308', width: 2, dash: 'dash' },
      fillcolor: 'rgba(234, 179, 8, 0.14)',
    })
  }
  return shapes
})

// Cake plot y-axis clamp when the χ crop is enabled (item 6).
const cakeYRange = computed(() => {
  if (!cakeCropEnabled.value) return null
  return [Math.min(cakeCropChiMin.value, cakeCropChiMax.value),
          Math.max(cakeCropChiMin.value, cakeCropChiMax.value)]
})

// Precise mode = click-driven (pan); rough mode = drag-box selection.
// In rough mode slices are suppressed, so the canvas behaves purely as a
// box-select tool (item 2). Refine-box drawing temporarily forces a selection
// dragmode regardless of the user's mode so they can draw without switching —
// 'select' (rect) or 'lasso' (freehand stroke; the stroke's q/χ extremes
// become the refine box) per the quick-settings shape choice.
const cakeRefineShape = ref('rect') // 'rect' | 'lasso'
const cakeDragmode = computed(() => {
  if (cakeRefineDrawing.value) return cakeRefineShape.value === 'lasso' ? 'lasso' : 'select'
  return cakeSelectionMode.value === 'rough' ? 'select' : 'pan'
})

// ROI index labels for overlay on the cake plot.
// Each label is placed at the center of its ROI rectangle.
const cakeRoiLabels = computed(() => {
  if (!cakeShowRoiLabels.value) return []
  return cakeRois.value.map((r, i) => {
    if (r.qMin == null || r.qMax == null || r.azimuthMin == null || r.azimuthMax == null) return null
    const cx = (r.qMin + r.qMax) / 2
    const cy = (r.azimuthMin + r.azimuthMax) / 2
    return { x: cx, y: cy, text: String(i + 1) }
  }).filter(Boolean)
})

// ROI records start empty — the user builds the list by recording selections.
const cakeRois = ref([])

// Selection state
const cakeSelectionMode = ref('precise') // 'rough' (drag-box) | 'precise' (click)
const cakeClickPos = ref(null)
const cakeQ1 = ref(null)
const cakeQ2 = ref(null)
const cakeAz1 = ref(null)
const cakeAz2 = ref(null)
const cakeSelectedRoiIndex = ref(null)

// Refined match-box drawing state. The integration ROI stays large for good
// intensity statistics; the user can additionally draw a small "refine box"
// (cyan dashed) to pin the single true Miller point — spurious points swept in
// by a wide diffraction-arc ROI are then ignored by match/export. Mirrors
// reference/function3's 精细化匹配区域.
const cakeRefineDrawing = ref(false)   // true while waiting for a refine-box drag
const cakeRefineTarget = ref(null)     // index of the ROI being refined

// Secondary tab within the cake analysis: "settings" (control cards, 2-per-row)
// vs. "roi" (the ROI records table). The cake image always sits above these.
const cakePanel = ref('settings')

// Show ROI index labels on the plot (on by default — users expect to see the
// index of each recorded ROI without hunting for a toggle).
const cakeShowRoiLabels = ref(true)

const cakeHasSelection = computed(() => cakeQ1.value != null && cakeQ2.value != null && cakeAz1.value != null && cakeAz2.value != null)

// ---- Row-click edit mode ----
// Clicking a ROI table row loads its bounds into the selection state (the
// slice plots show them as the red/green dashed bound lines) and marks the
// row as the edit target: 记录当前区域 then UPDATES that row in place —
// multiplier, background and match/refine results are kept. A fresh box
// dragged on the cake or 清除选择/Esc cancels the edit target (new drag =
// new peak, never a silent overwrite).
const cakeEditRoiIndex = ref(null)

function selectRoiRow(i) {
  const roi = cakeRois.value[i]
  if (!roi) return
  cakeSelectedRoiIndex.value = i
  cakeEditRoiIndex.value = i
  cakeQ1.value = roi.qMin
  cakeQ2.value = roi.qMax
  cakeAz1.value = roi.azimuthMin
  cakeAz2.value = roi.azimuthMax
  // Re-draw the slice plots so the loaded bounds appear as dashed lines.
  // Keep the last clicked point as the window centre when there is one;
  // otherwise centre the windows on the ROI itself.
  if (cakeLastClickedQ == null || cakeLastClickedChi == null) {
    cakeLastClickedQ = (roi.qMin + roi.qMax) / 2
    cakeLastClickedChi = (roi.azimuthMin + roi.azimuthMax) / 2
    cakeClickPos.value = { q: cakeLastClickedQ, chi: cakeLastClickedChi }
  }
  refreshSlicePlots()
}

function cancelRoiEdit() {
  cakeEditRoiIndex.value = null
  clearCakeSelection()
}

// Background
// The panel below is the *template*: its resolved settings are copied into
// every newly created ROI as that peak's own background fields. Each peak's
// subtraction mode / parameters are then edited per-row in the ROI table, so
// calculation always integrates with per-peak settings rather than one global
// choice. `bgMode === undefined` (ROIs from an older session state) falls back
// to the panel values at calculation time.
const cakeBgMode = ref('fixed')
const cakeBgValue = ref(0)
const cakeBgSide = ref('both')
const cakeBgWidth = ref(10)

// Resolve the panel (with the DBSCAN mode collapsed to its effective fixed
// value) into the per-peak fields given to new ROIs.
function defaultBgFields() {
  let mode = cakeBgMode.value
  let value = cakeBgValue.value
  if (mode === 'dbscan') {
    mode = 'fixed'
    value = cakeBgEstimate.value ? cakeBgEstimate.value.backgroundValue : 0
  }
  return { bgMode: mode, bgFixedValue: value, bgSide: cakeBgSide.value, bgWidth: cakeBgWidth.value }
}

// Editing the panel's 固定背景值 syncs into every ROI currently in fixed mode,
// so existing peaks pick the new value up without re-drawing. Rows stay
// individually editable afterwards; a later panel change re-syncs them again.
watch(cakeBgValue, (v) => {
  cakeRois.value.forEach(r => { if (r.bgMode === 'fixed') r.bgFixedValue = v })
})

// ---- Quick settings (slice card) ----
// Defaults stamped onto every NEWLY recorded peak so a whole series can be
// recorded without touching the ROI table in between. The background fields
// intentionally share the panel refs above (single source of truth); the
// multiplier is quick-settings-specific.
//
// Deliberately NO "auto refine after record": arming refine-box drawing
// right after each record hijacked the user's NEXT box-drag (it became the
// previous ROI's match box instead of a new peak), forcing two drags per
// peak and misplacing boxes. Recording now completes in one step; refine
// boxes are drawn on demand via the F shortcut / the quick button / the
// table button, each with the banner explaining the armed state.
const cakeQuickMultiplier = ref(1)

// Arm refine-box drawing for a specific ROI index (quick-settings shortcut).
function quickStartRefineFor(idx) {
  if (idx == null || idx < 0 || !cakeRois.value[idx]) return
  startRefineMatch(idx)
}

// Arm refine-box drawing for the selected ROI, falling back to the most
// recently recorded one — the slice card's 精致化 shortcut.
function quickStartRefine() {
  quickStartRefineFor(cakeSelectedRoiIndex.value != null ? cakeSelectedRoiIndex.value : cakeRois.value.length - 1)
}

// Keyboard shortcuts for the record→refine loop: R records the current
// selection, F arms refine-box drawing, Escape cancels the drawing (or clears
// the selection). Ignored while typing in form fields and with modifier keys
// held, so number inputs and browser shortcuts keep working.
function onCakeKeydown(e) {
  const el = e.target
  const tag = el?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'select' || tag === 'textarea' || el?.isContentEditable) return
  if (e.ctrlKey || e.metaKey || e.altKey) return
  if (activeTab.value !== 'cake') return
  if (e.key === 'r' || e.key === 'R') {
    if (cakeHasSelection.value) recordCakeArea()
  } else if (e.key === 'f' || e.key === 'F') {
    if (cakeImageData.value) quickStartRefine()
  } else if (e.key === 'l' || e.key === 'L') {
    // Lasso refine: same target resolution as F but forces the freehand shape.
    if (cakeImageData.value) {
      cakeRefineShape.value = 'lasso'
      quickStartRefine()
    }
  } else if (e.key === 'Escape') {
    if (cakeRefineDrawing.value) {
      cakeRefineDrawing.value = false
      cakeRefineTarget.value = null
    } else {
      clearCakeSelection()
    }
  }
}
window.addEventListener('keydown', onCakeKeydown)

// ---- DBSCAN cluster-based background estimation ----
// Workflow: bright pixels are clustered (DBSCAN) into diffraction-peak
// clusters; the user tunes the parameters and visually verifies the peak mask
// (red overlay) against the image; everything outside the clusters is the
// background, whose percentile becomes the background level. "应用" transfers
// the estimate into the fixed-value mode so intensity calculation uses it.
const cakeBgParams = reactive({
  thresholdPercentile: 90,
  eps: 0.02,
  minSamples: 10,
  minClusterPixels: 30,
  dilationPixels: 2,
  backgroundPercentile: 50,
})
const cakeBgEstimate = ref(null)   // last estimate result (incl. previewMask)
const cakeBgEstimating = ref(false)
const cakeBgShowMask = ref(true)

// Leaving DBSCAN mode (including via 应用为固定背景值, which switches the mode
// to fixed) automatically hides the peak mask — otherwise the red overlay kept
// covering the cake while working in another background mode and had to be
// hunted down in the checkbox. Switching back re-shows the preview if an
// estimate exists.
watch(cakeBgMode, (mode) => {
  if (mode !== 'dbscan') {
    cakeBgShowMask.value = false
  } else if (cakeBgEstimate.value) {
    cakeBgShowMask.value = true
  }
})

async function estimateCakeBackground() {
  if (!cakeImageFileId.value || cakeBgEstimating.value) return
  cakeBgEstimating.value = true
  taskStatus.cake = 'running'
  try {
    const regions = cakeRois.value.map(r => ({
      qMin: r.qMin, qMax: r.qMax, azimuthMin: r.azimuthMin, azimuthMax: r.azimuthMax,
    }))
    const res = await analysisEstimateBackground({
      fileId: cakeImageFileId.value,
      qRange: cakeMeta.value?.qRange,
      chiRange: cakeMeta.value?.chiRange,
      thresholdPercentile: cakeBgParams.thresholdPercentile,
      eps: cakeBgParams.eps,
      minSamples: cakeBgParams.minSamples,
      minClusterPixels: cakeBgParams.minClusterPixels,
      dilationPixels: cakeBgParams.dilationPixels,
      backgroundPercentile: cakeBgParams.backgroundPercentile,
      regions,
      minIntensity: cakeSaturationMin.value ?? undefined,
      maxIntensity: cakeSaturationMax.value ?? undefined,
    })
    cakeBgEstimate.value = res.data || null
    if (cakeBgEstimate.value) {
      consoleLogs.cake.push(t('logs.analysis.bgEstimated', {
        value: cakeBgEstimate.value.backgroundValue.toFixed(2),
        n: cakeBgEstimate.value.nClusters,
      }))
    }
    taskStatus.cake = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
  } finally {
    cakeBgEstimating.value = false
  }
}

function applyCakeBackground() {
  if (!cakeBgEstimate.value) return
  cakeBgValue.value = cakeBgEstimate.value.backgroundValue
  cakeBgMode.value = 'fixed'
  // Background settings are per-peak now: push the estimate into every ROI
  // whose mode is 固定背景 so existing peaks pick it up too (peaks on other
  // modes keep their own setting; new ROIs inherit the panel as template).
  const est = cakeBgEstimate.value.backgroundValue
  cakeRois.value.forEach(r => { if (r.bgMode === 'fixed') r.bgFixedValue = est })
  consoleLogs.cake.push(t('logs.analysis.bgApplied', { value: cakeBgValue.value.toFixed(2) }))
}

// Saturation / dead-pixel ceiling. Pixels above this are excluded from the
// intensity sum (sentinels like 65535 or fill values that pyFAI leaves as the
// array max). null ⇒ disabled. Auto-set to the 99.9th percentile of the loaded
// cake data; the "clear" button resets it to null.
const cakeSaturationMax = ref(null)
// Lower intensity floor. null ⇒ disabled (default): every finite box pixel
// enters the sum, matching reference/function3 ``calculate_all_intensities``
// which sums ALL pixels regardless of sign. Set a value only to exclude
// dead/negative fill sentinels deliberately.
const cakeSaturationMin = ref(null)

// Y-axis (χ) crop — mirrors UIref/IntView azimuth crop: clamps the cake plot's
// visible χ band so the user can box-select a narrow azimuth window precisely.
// Defaults track the applied χ range; toggled on by the user.
const cakeCropEnabled = ref(false)
const cakeCropChiMin = ref(-180)
const cakeCropChiMax = ref(180)
function resetCakeCrop() {
  const cr = cakeMeta.value?.chiRange
  if (Array.isArray(cr) && cr.length === 2) {
    cakeCropChiMin.value = cr[0]
    cakeCropChiMax.value = cr[1]
  } else {
    cakeCropChiMin.value = -180
    cakeCropChiMax.value = 180
  }
}

// Slice plot state
const cakeQSliceAzWidth = ref(1.0)   // integration width (azimuth degrees) for q-slice
const cakeAzSliceQWidth = ref(0.01)  // integration width (q) for azimuth-slice
const cakeQSliceQRange = ref(0.2)    // q display window (Å⁻¹) for the q-slice
const cakeAzSliceAzRange = ref(20.0) // χ display window (degrees) for the χ-slice
let cakeLastClickedQ = null
let cakeLastClickedChi = null

// Slice plot containers
const qSliceContainer = ref(null)
const azSliceContainer = ref(null)

// ---- Slice card: inline ⇄ floating (draggable / resizable / closable) ----
// The floating card lets the user pick slice ranges on the cake while keeping
// the curves in view. Position/size persist in localStorage across sessions.
const SLICE_CARD_STORE_KEY = 'pre_analysis_slice_card_v1'
const sliceVisible = ref(true)
const sliceFloating = ref(false)
const sliceCardPos = reactive({ x: 80, y: 120 })
const sliceCardSize = reactive({ w: 780, h: 460 })
const sliceCardStyle = computed(() => ({
  left: `${sliceCardPos.x}px`,
  top: `${sliceCardPos.y}px`,
  width: `${sliceCardSize.w}px`,
  height: `${sliceCardSize.h}px`,
}))

function loadSliceCardState() {
  try {
    const raw = localStorage.getItem(SLICE_CARD_STORE_KEY)
    if (!raw) return
    const s = JSON.parse(raw)
    if (typeof s.visible === 'boolean') sliceVisible.value = s.visible
    if (typeof s.floating === 'boolean') sliceFloating.value = s.floating
    if (Number.isFinite(s.x)) sliceCardPos.x = s.x
    if (Number.isFinite(s.y)) sliceCardPos.y = s.y
    if (Number.isFinite(s.w) && s.w >= 360) sliceCardSize.w = s.w
    if (Number.isFinite(s.h) && s.h >= 280) sliceCardSize.h = s.h
  } catch { /* corrupted state — keep defaults */ }
  clampSliceCardToViewport()
}
function persistSliceCard() {
  try {
    localStorage.setItem(SLICE_CARD_STORE_KEY, JSON.stringify({
      visible: sliceVisible.value,
      floating: sliceFloating.value,
      ...sliceCardPos,
      ...sliceCardSize,
    }))
  } catch { /* storage unavailable — non-fatal */ }
}
loadSliceCardState()

function clamp(v, lo, hi) {
  return Math.min(Math.max(v, lo), hi)
}

// Drag-time clamps keep ≥120px/≥48px of the card on-screen, but they use the
// window size at drag time: a position saved while the window was wider
// (maximized) can fall entirely outside a narrower window — header (with the
// dock/close buttons) unreachable, and the position persists across
// restarts.  Clamp any restored/current position back into view.
function clampSliceCardToViewport() {
  sliceCardPos.x = clamp(sliceCardPos.x, -sliceCardSize.w + 120, Math.max(0, window.innerWidth - 120))
  sliceCardPos.y = clamp(sliceCardPos.y, 0, Math.max(0, window.innerHeight - 48))
}

function onWindowResize() {
  clampSliceCardToViewport()
}
window.addEventListener('resize', onWindowResize)

// Escape hatch reachable from the toolbar (not from the card itself): dock
// the floating card back inline and reset its position — the only way back
// when a stale saved position puts the whole card off-screen.
function dockSliceCard() {
  sliceFloating.value = false
  sliceCardPos.x = 80
  sliceCardPos.y = 120
  if (!sliceVisible.value) {
    sliceVisible.value = true
    nextTick(() => {
      watchSliceContainers()
      refreshSlicePlots()
    })
  }
  persistSliceCard()
}

// Fixed open/close site (Region Selection header) for the slice card. On
// reopen the plot containers are freshly-mounted empty divs (the v-if tore
// down the old Plotly DOM), so the curves must be redrawn explicitly —
// otherwise the card reopens blank and feels broken.
function toggleSliceCard() {
  sliceVisible.value = !sliceVisible.value
  persistSliceCard()
  if (sliceVisible.value) {
    nextTick(() => {
      watchSliceContainers()
      refreshSlicePlots()
    })
  }
}

// × on the card header (both inline and floating states).
function closeSliceCard() {
  sliceVisible.value = false
  persistSliceCard()
}

// Drag by the card header. Pointer events on window so the drag keeps working
// when the cursor leaves the header (and even the card).
function startSliceCardDrag(e) {
  if (!sliceFloating.value || e.button !== 0) return
  e.preventDefault()
  const startX = e.clientX
  const startY = e.clientY
  const origX = sliceCardPos.x
  const origY = sliceCardPos.y
  const onMove = (ev) => {
    sliceCardPos.x = clamp(origX + ev.clientX - startX, -sliceCardSize.w + 120, window.innerWidth - 120)
    sliceCardPos.y = clamp(origY + ev.clientY - startY, 0, window.innerHeight - 48)
  }
  const onUp = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    persistSliceCard()
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

// Resize from the bottom-right corner handle.
function startSliceCardResize(e) {
  if (e.button !== 0) return
  e.preventDefault()
  e.stopPropagation()
  const startX = e.clientX
  const startY = e.clientY
  const origW = sliceCardSize.w
  const origH = sliceCardSize.h
  const onMove = (ev) => {
    sliceCardSize.w = clamp(origW + ev.clientX - startX, 360, window.innerWidth - 20)
    sliceCardSize.h = clamp(origH + ev.clientY - startY, 280, window.innerHeight - 20)
  }
  const onUp = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    persistSliceCard()
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

// Keep the Plotly slice plots fitted while the card (or window) resizes.
// Plotly's responsive config only watches window resizes; card drags/resize
// need an explicit ResizeObserver → Plots.resize.
let sliceResizeObserver = null
function watchSliceContainers() {
  nextTick(() => {
    if (sliceResizeObserver) {
      sliceResizeObserver.disconnect()
      sliceResizeObserver = null
    }
    const els = [qSliceContainer.value, azSliceContainer.value].filter(Boolean)
    if (!els.length) return
    sliceResizeObserver = new ResizeObserver(() => {
      for (const el of els) {
        if (el && el.data) Plotly.Plots.resize(el)
      }
    })
    els.forEach(el => sliceResizeObserver.observe(el))
  })
}
watch([() => cakeImageData.value, sliceVisible, sliceFloating], watchSliceContainers)

// Miller
const millerFiles = ref([])
const millerDatasets = ref([])
const millerConvention = ref('CCW')
const millerAzimuthOffset = ref(0)
// Match tolerances (edge slack for the "point inside ROI box" test). User-tunable
// Match tolerances (edge slack on the strict point-in-box test). Default 0 ⇒
// strict box bounds, exactly matching reference/function3 (no slack). Widen
// only if a Miller point sits a hair outside a hand-drawn refine box.
const millerQTolerance = ref(0)   // Å^-1
const millerChiTolerance = ref(0) // degrees
// Overlay rendering: any user-picked color via the color picker (hex);
// legacy 'gray'/'white' names still resolve for old persisted values.
const millerShowPoints = ref(true)
const millerPointColor = ref('#9CA3AF')

// Miller points mapped into the cake's (q, χ) coordinates for overlay.
// Conversion follows reference 2dinter_area_obtaine.py:
//   CCW: χ = offset + psi ; CW: χ = offset − psi ; normalised to [-180, 180).
// Points outside the current image q/chi range are filtered out so the overlay
// never stretches the canvas beyond the loaded data.
const millerOverlayPoints = computed(() => {
  if (!millerShowPoints.value || !millerDatasets.value.length) return []
  const ref0 = millerAzimuthOffset.value
  const ccw = millerConvention.value === 'CCW'
  // Get image q/chi bounds for clipping
  const qRange = cakeMeta.value?.qRange
  const chiRange = cakeMeta.value?.chiRange
  const qMin = Array.isArray(qRange) ? qRange[0] : -Infinity
  const qMax = Array.isArray(qRange) ? qRange[1] : Infinity
  const chiMin = Array.isArray(chiRange) ? Math.min(chiRange[0], chiRange[1]) : -Infinity
  const chiMax = Array.isArray(chiRange) ? Math.max(chiRange[0], chiRange[1]) : Infinity
  // Small margin (1%) to allow points just on the edge
  const qMargin = (qMax - qMin) * 0.01
  const chiMargin = (chiMax - chiMin) * 0.01

  const pts = []
  for (const ds of millerDatasets.value) {
    for (const p of ds.points || []) {
      let az = ccw ? (ref0 + p.psi) : (ref0 - p.psi)
      az = ((az % 360) + 360) % 360
      if (az >= 180) az -= 360
      // Only include points within the image bounds (with 1% margin)
      if (p.q < qMin - qMargin || p.q > qMax + qMargin) continue
      if (az < chiMin - chiMargin || az > chiMax + chiMargin) continue
      pts.push({ x: p.q, y: az })
    }
  }
  return pts
})
const millerOverlayColor = computed(() => {
  const v = millerPointColor.value
  if (typeof v === 'string' && v.startsWith('#')) return v
  if (v === 'white') return '#FFFFFF'
  return '#9CA3AF'
})

// 精致化/导出边距（dq, dψ）：导出的 q/ψ 范围 = 匹配到的 Miller 点（在精致化
// 选区内，否则积分选区内）的最小/最大值 ± 边距；未匹配时 = 选区框 ± 边距。
// 默认 dq=0.02 Å⁻¹、dψ=2°。
const millerExportQMargin = ref(0.02)
const millerExportPsiMargin = ref(2)

// ===================== DETECTOR ANALYSIS STATE =====================
const detectorFile = ref(null)
const detectorImageData = ref(null)
const detectorImageFileId = ref(null)
const detectorMeta = ref(null)

const detectorControls = reactive({
  colormap: 'Viridis',
  logScale: true,
})

const detectorRois = ref([])

const detectorBgMode = ref('fixed')
const detectorBgValue = ref(0)
const detectorBgSide = ref('both')
const detectorBgWidth = ref(10)

// Same as cakeSaturationMax but for the raw detector image (typically the
// detector's saturation count, e.g. 65535). null ⇒ disabled.
const detectorSaturationMax = ref(null)
const detectorSaturationMin = ref(0)

// ===================== HELPERS =====================
function fmtRange(r) {
  return Array.isArray(r) && r.length === 2 ? `${r[0]} ~ ${r[1]}` : '—'
}

// p-th percentile (p in 0..1) of a possibly-nested numeric array, ignoring
// NaN/Infinity. Used by the saturation "auto" buttons to pick a ceiling just
// below the saturated/dead-pixel spikes. Iterative flatten keeps it flat for
// large detector arrays.
function imagePercentile(data, p) {
  if (!data) return null
  const flat = []
  const stack = [data]
  let n = 0
  while (stack.length) {
    const v = stack.pop()
    if (Array.isArray(v)) {
      for (let i = 0; i < v.length; i++) stack.push(v[i])
    } else if (typeof v === 'number' && Number.isFinite(v)) {
      flat.push(v); n++
    }
  }
  if (!n) return null
  flat.sort((a, b) => a - b)
  const idx = Math.min(n - 1, Math.max(0, Math.floor(p * (n - 1))))
  return flat[idx]
}

// Auto-set the saturation ceiling to the 99.9th percentile of the loaded image,
// so the top ~0.1% (saturated / dead pixels) get excluded from the intensity sum.
function autoSaturation(dataRef, target) {
  const v = imagePercentile(dataRef.value, 0.999)
  if (v == null) return
  target.value = Math.round(v * 1000) / 1000
}
const autoCakeSaturation = () => autoSaturation(cakeImageData, cakeSaturationMax)
const autoDetectorSaturation = () => autoSaturation(detectorImageData, detectorSaturationMax)

// ===================== FILE HANDLERS =====================
function onCakeFileInput(e) {
  cakeFile.value = e.target.files?.[0] || null
  // Auto-display the image as soon as it is selected — no extra "Load" click.
  if (cakeFile.value) loadCakeImage()
}
function onCakeInfoInput(e) {
  const f = e.target.files?.[0] || null
  cakeInfoFile.value = f
  // The info sidecar rescales the whole image's q/chi axes on its own.
  if (f) applyCakeInfo(f)
}
function onMillerFileInput(e) {
  millerFiles.value = Array.from(e.target.files || [])
}
function onDetectorFileInput(e) {
  detectorFile.value = e.target.files?.[0] || null
}

// ===================== CAKE LOAD =====================
const loadCakeImage = async () => {
  if (!cakeFile.value) return
  runStatus.value = 'running'
  taskStatus.cake = 'running'
  consoleLogs.cake = [t('logs.analysis.uploadingCake')]
  try {
    const formData = new FormData()
    formData.append('files', cakeFile.value)
    const res = await analysisUploadImage(formData)
    if (res.data?.fileId) {
      cakeImageFileId.value = res.data.fileId
      // Preserve any axis ranges already applied from an info sidecar so that
      // re-loading the image does not clobber them with the upload defaults.
      const prev = cakeMeta.value || {}
      cakeMeta.value = {
        shape: res.data.shape || null,
        qRange: prev.qRange ?? res.data.qRange ?? null,
        chiRange: prev.chiRange ?? res.data.chiRange ?? null,
      }
      const imgRes = await analysisGetImage(res.data.fileId)
      cakeImageData.value = imgRes.data?.data ?? null
      // Set contrast range from image
      if (imgRes.data) {
        const dmin = imgRes.data.min ?? 0
        const dmax = imgRes.data.max ?? 65535
        cakeContrastRange.value = [dmin, dmax]
        cakeControls.zmin = dmin
        cakeControls.zmax = dmax
      }
    }
    consoleLogs.cake.push(t('logs.analysis.imageLoaded'))
    taskStatus.cake = 'completed'
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
    runStatus.value = 'failed'
  }
}

// ===================== CAKE INFO (standalone) =====================
// Apply a processing_info sidecar (JSON or legacy text) to rescale the axes of
// an already-loaded image. q is returned in Å^-1 by the backend.
const applyCakeInfo = async (file) => {
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await analysisParseInfo(fd)
    const d = res.data || {}
    const next = { ...(cakeMeta.value || {}) }
    if (Array.isArray(d.qRange) && d.qRange.length === 2) next.qRange = d.qRange
    if (Array.isArray(d.chiRange) && d.chiRange.length === 2) next.chiRange = d.chiRange
    cakeMeta.value = next
    // Keep the χ-crop bounds in sync with the freshly applied χ range so the
    // crop control starts at the full band (user narrows from there).
    if (Array.isArray(d.chiRange) && d.chiRange.length === 2) {
      cakeCropChiMin.value = d.chiRange[0]
      cakeCropChiMax.value = d.chiRange[1]
    }
    consoleLogs.cake.push(t('logs.analysis.infoApplied', { name: file.name }))
    // Re-render slices if a point had been clicked before the rescale.
    refreshSlicePlots()
  } catch (err) {
    consoleLogs.cake.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}

// ===================== DETECTOR LOAD =====================
const loadDetectorImage = async () => {
  if (!detectorFile.value) return
  runStatus.value = 'running'
  taskStatus.detector = 'running'
  consoleLogs.detector = [t('logs.analysis.uploadingDetector')]
  try {
    const formData = new FormData()
    formData.append('files', detectorFile.value)
    const res = await analysisUploadImage(formData)
    if (res.data?.fileId) {
      detectorImageFileId.value = res.data.fileId
      detectorMeta.value = {
        shape: res.data.shape || null,
        dtype: res.data.dtype || null,
      }
      const imgRes = await analysisGetImage(res.data.fileId)
      detectorImageData.value = imgRes.data?.data ?? null
    }
    consoleLogs.detector.push(t('logs.analysis.detectorLoaded'))
    taskStatus.detector = 'completed'
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs.detector.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.detector = 'error'
    runStatus.value = 'failed'
  }
}

// ===================== CAKE REGION SELECTION =====================
function onCakeRegionSelected(region) {
  const [ax1, ax2] = region.xRange
  const [az1, az2] = region.yRange
  // Refine-box drawing: route the drag result to the targeted ROI's match box
  // instead of pushing a new integration ROI, then re-run Miller matching so
  // the hkl/export columns update against the small box.
  if (cakeRefineDrawing.value && cakeRefineTarget.value != null) {
    const roi = cakeRois.value[cakeRefineTarget.value]
    if (roi) {
      roi.matchQMin = Math.min(ax1, ax2)
      roi.matchQMax = Math.max(ax1, ax2)
      roi.matchAzMin = Math.min(az1, az2)
      roi.matchAzMax = Math.max(az1, az2)
      cakeSelectedRoiIndex.value = cakeRefineTarget.value
    }
    cakeRefineDrawing.value = false
    cakeRefineTarget.value = null
    runMillerMatch()
    return
  }
  // A fresh box dragged on the cake records a NEW peak — cancel any row-edit
  // target first so the drag can never overwrite the row being edited.
  cakeEditRoiIndex.value = null
  const newIdx = cakeRois.value.push({
    qMin: Math.min(ax1, ax2),
    qMax: Math.max(ax1, ax2),
    azimuthMin: Math.min(az1, az2),
    azimuthMax: Math.max(az1, az2),
    // Quick settings (slice card) stamp every newly outlined peak.
    multiplier: cakeQuickMultiplier.value,
    intensity: null,
    pixelCount: null,
    label: '',
    matchHkl: null,
    matchQMin: null, matchQMax: null, matchAzMin: null, matchAzMax: null,
    exportQMin: null, exportQMax: null, exportPsiMin: null, exportPsiMax: null,
    refined: false,
    ...defaultBgFields(),
  }) - 1
  // Track the fresh ROI as selected so a subsequent F (精致匹配框) targets
  // the peak just drawn, not whatever row was clicked earlier.
  cakeSelectedRoiIndex.value = newIdx
}

function onCakePointClicked(point) {
  // Record the clicked physical coords regardless of mode, but only generate
  // the q-I / q-χ slice curves in precise mode. In rough (drag-box) mode the
  // user is drawing an ROI, so the slice view is intentionally disabled.
  // Refine-box drawing is also a drag action — suppress slices then too.
  cakeLastClickedQ = point.x
  cakeLastClickedChi = point.y
  cakeClickPos.value = { q: point.x, chi: point.y }
  if (cakeSelectionMode.value !== 'precise' || cakeRefineDrawing.value) return
  renderSlicePlots(point.x, point.y)
}

function refreshSlicePlots() {
  if (cakeLastClickedQ != null && cakeLastClickedChi != null) {
    renderSlicePlots(cakeLastClickedQ, cakeLastClickedChi)
  }
}

// ===================== SLICE PLOTS (narrow range) =====================
function renderSlicePlots(qClicked, chiClicked) {
  cakeLastClickedQ = qClicked
  cakeLastClickedChi = chiClicked
  if (!cakeImageData.value || !cakeMeta.value) return
  const data = cakeImageData.value
  const rows = data.length
  const cols = data[0]?.length || 0
  if (!rows || !cols) return

  const qRange = cakeMeta.value.qRange || [0, 25]
  const chiRange = cakeMeta.value.chiRange || [0, 360]
  const qAxis = Array.from({ length: cols }, (_, i) => qRange[0] + (i / (cols - 1)) * (qRange[1] - qRange[0]))
  const chiAxis = Array.from({ length: rows }, (_, i) => chiRange[0] + (i / (rows - 1)) * (chiRange[1] - chiRange[0]))

  // ---- Q-slice: integrate over azimuth width around click, zoom to narrow q window ----
  const azWidth = cakeQSliceAzWidth.value
  const azStart = chiClicked - azWidth / 2
  const azEnd = chiClicked + azWidth / 2
  const rowStart = Math.max(0, Math.round(((azStart - chiRange[0]) / (chiRange[1] - chiRange[0])) * (rows - 1)))
  const rowEnd = Math.min(rows - 1, Math.round(((azEnd - chiRange[0]) / (chiRange[1] - chiRange[0])) * (rows - 1)))
  const qIntensity = []
  for (let c = 0; c < cols; c++) {
    let sum = 0, count = 0
    for (let r = Math.min(rowStart, rowEnd); r <= Math.max(rowStart, rowEnd); r++) {
      sum += (data[r]?.[c] ?? 0); count++
    }
    qIntensity.push(count > 0 ? sum / count : 0)
  }

  // ---- Azimuth-slice: integrate over q width around click, zoom to narrow chi window ----
  const qWidth = cakeAzSliceQWidth.value
  const qStart = qClicked - qWidth / 2
  const qEnd = qClicked + qWidth / 2
  const colStart = Math.max(0, Math.round(((qStart - qRange[0]) / (qRange[1] - qRange[0])) * (cols - 1)))
  const colEnd = Math.min(cols - 1, Math.round(((qEnd - qRange[0]) / (qRange[1] - qRange[0])) * (cols - 1)))
  const azIntensity = []
  for (let r = 0; r < rows; r++) {
    let sum = 0, count = 0
    for (let c = Math.min(colStart, colEnd); c <= Math.max(colStart, colEnd); c++) {
      sum += (data[r]?.[c] ?? 0); count++
    }
    azIntensity.push(count > 0 ? sum / count : 0)
  }

  // Narrow display ranges — user-adjustable (item 2: "可以调节q的切片范围，
  // 而不只是默认"). Defaults match the reference (q ± 0.2 Å⁻¹, χ ± 20°) but the
  // user can widen/narrow each window. Centered on the clicked cake point.
  const qDisplayRange = cakeQSliceQRange.value
  const chiDisplayRange = cakeAzSliceAzRange.value
  const qDispMin = qClicked - qDisplayRange / 2
  const qDispMax = qClicked + qDisplayRange / 2
  const chiDispMin = chiClicked - chiDisplayRange / 2
  const chiDispMax = chiClicked + chiDisplayRange / 2

  // Compute visible y-range for each slice
  const qInView = qAxis.filter(v => v >= qDispMin && v <= qDispMax)
  const qIntInView = qIntensity.filter((_, i) => qAxis[i] >= qDispMin && qAxis[i] <= qDispMax)
  const qYmin = qIntInView.length ? Math.min(...qIntInView) : 0
  const qYmax = qIntInView.length ? Math.max(...qIntInView) : 1
  const qYpad = Math.max((qYmax - qYmin) * 0.05, 1)

  const chiInView = chiAxis.filter(v => v >= chiDispMin && v <= chiDispMax)
  const azIntInView = azIntensity.filter((_, i) => chiAxis[i] >= chiDispMin && chiAxis[i] <= chiDispMax)
  const azYmin = azIntInView.length ? Math.min(...azIntInView) : 0
  const azYmax = azIntInView.length ? Math.max(...azIntInView) : 1
  const azYpad = Math.max((azYmax - azYmin) * 0.05, 1)

  // Shape builders shared between the initial newPlot and the relayout updates
  // (item 4). Each slice gets a solid blue line at the clicked cake point
  // (where the slice is centered) plus dashed bound lines for the selection.
  const qSliceShapes = () => {
    const s = []
    if (cakeLastClickedQ != null) s.push({ type: 'line', x0: cakeLastClickedQ, x1: cakeLastClickedQ, y0: 0, y1: 1, yref: 'paper', line: { color: '#3B82F6', width: 1.5 } })
    if (cakeQ1.value != null) s.push({ type: 'line', x0: cakeQ1.value, x1: cakeQ1.value, y0: 0, y1: 1, yref: 'paper', line: { color: '#EF4444', dash: 'dash', width: 1.5 } })
    if (cakeQ2.value != null) s.push({ type: 'line', x0: cakeQ2.value, x1: cakeQ2.value, y0: 0, y1: 1, yref: 'paper', line: { color: '#EF4444', dash: 'dash', width: 1.5 } })
    return s
  }
  const azSliceShapes = () => {
    const s = []
    if (cakeLastClickedChi != null) s.push({ type: 'line', x0: cakeLastClickedChi, x1: cakeLastClickedChi, y0: 0, y1: 1, yref: 'paper', line: { color: '#3B82F6', width: 1.5 } })
    if (cakeAz1.value != null) s.push({ type: 'line', x0: cakeAz1.value, x1: cakeAz1.value, y0: 0, y1: 1, yref: 'paper', line: { color: '#10B981', dash: 'dash', width: 1.5 } })
    if (cakeAz2.value != null) s.push({ type: 'line', x0: cakeAz2.value, x1: cakeAz2.value, y0: 0, y1: 1, yref: 'paper', line: { color: '#10B981', dash: 'dash', width: 1.5 } })
    return s
  }

  nextTick(() => {
    // Plot height follows the container: 160 inline (CSS min-height), larger
    // when the floating card has been stretched by the user.
    const plotHeight = (el) => (el && el.clientHeight >= 60 ? el.clientHeight : 160)
    if (qSliceContainer.value) {
      const qLayout = {
        paper_bgcolor: '#FFFFFF', plot_bgcolor: '#F8FAFC',
        font: { color: '#262432', family: 'Inter, sans-serif', size: 10 },
        margin: { t: 25, r: 10, b: 30, l: 50 }, height: plotHeight(qSliceContainer.value),
        xaxis: { title: 'q (Å⁻¹)', gridcolor: '#E3E0EF', zerolinecolor: '#E3E0EF', range: [qDispMin, qDispMax] },
        yaxis: { title: 'Int', gridcolor: '#E3E0EF', zerolinecolor: '#E3E0EF', range: [qYmin - qYpad, qYmax + qYpad] },
        shapes: qSliceShapes(),
      }
      Plotly.newPlot(qSliceContainer.value, [{ x: qAxis, y: qIntensity, type: 'scatter', mode: 'lines', line: { color: '#7C3AED', width: 1.5 } }], qLayout, { responsive: true, displayModeBar: false })
      // Read the x of ANY click inside the plot area — not just on the curve.
      // plotly_click only fires when the cursor hits the line itself, which
      // made selecting a q bound frustrating. Here we linearly map the click's
      // pixel to a data x against the axis range, and ignore clicks in margins.
      qSliceContainer.value.onclick = (evt) => {
        const gd = qSliceContainer.value
        const xa = gd && gd._fullLayout && gd._fullLayout.xaxis
        if (!xa || !Array.isArray(xa.range) || !Number.isFinite(xa.range[0]) || !Number.isFinite(xa.range[1])) return
        const xPixel = evt.clientX - gd.getBoundingClientRect().left
        if (xa._offset == null || xa._length == null) return
        if (xPixel < xa._offset || xPixel > xa._offset + xa._length) return
        // Map click pixel → data-x by linear interpolation against the axis
        // range. Don't use Plotly's p2d(): its pixel-reference convention
        // produced markers offset from the actual click point.
        const qVal = xa.range[0] + (xPixel - xa._offset) / xa._length * (xa.range[1] - xa.range[0])
        if (!Number.isFinite(qVal)) return
        if (cakeQ1.value == null) { cakeQ1.value = qVal }
        else if (cakeQ2.value == null) { cakeQ2.value = qVal }
        else { cakeQ1.value = qVal; cakeQ2.value = null }
        if (cakeQ1.value != null && cakeQ2.value != null) {
          const tmp = [cakeQ1.value, cakeQ2.value].sort((a, b) => a - b)
          cakeQ1.value = tmp[0]; cakeQ2.value = tmp[1]
        }
        if (qSliceContainer.value) Plotly.relayout(qSliceContainer.value, { shapes: qSliceShapes() })
      }
    }

    if (azSliceContainer.value) {
      const azLayout = {
        paper_bgcolor: '#FFFFFF', plot_bgcolor: '#F8FAFC',
        font: { color: '#262432', family: 'Inter, sans-serif', size: 10 },
        margin: { t: 25, r: 10, b: 30, l: 50 }, height: plotHeight(azSliceContainer.value),
        xaxis: { title: 'χ (°)', gridcolor: '#E3E0EF', zerolinecolor: '#E3E0EF', range: [chiDispMin, chiDispMax] },
        yaxis: { title: 'Int', gridcolor: '#E3E0EF', zerolinecolor: '#E3E0EF', range: [azYmin - azYpad, azYmax + azYpad] },
        shapes: azSliceShapes(),
      }
      Plotly.newPlot(azSliceContainer.value, [{ x: chiAxis, y: azIntensity, type: 'scatter', mode: 'lines', line: { color: '#10B981', width: 1.5 } }], azLayout, { responsive: true, displayModeBar: false })
      // Read the x of ANY click inside the plot area (see q-slice note above).
      azSliceContainer.value.onclick = (evt) => {
        const gd = azSliceContainer.value
        const xa = gd && gd._fullLayout && gd._fullLayout.xaxis
        if (!xa || !Array.isArray(xa.range) || !Number.isFinite(xa.range[0]) || !Number.isFinite(xa.range[1])) return
        const xPixel = evt.clientX - gd.getBoundingClientRect().left
        if (xa._offset == null || xa._length == null) return
        if (xPixel < xa._offset || xPixel > xa._offset + xa._length) return
        const azVal = xa.range[0] + (xPixel - xa._offset) / xa._length * (xa.range[1] - xa.range[0])
        if (!Number.isFinite(azVal)) return
        if (cakeAz1.value == null) { cakeAz1.value = azVal }
        else if (cakeAz2.value == null) { cakeAz2.value = azVal }
        else { cakeAz1.value = azVal; cakeAz2.value = null }
        if (cakeAz1.value != null && cakeAz2.value != null) {
          const tmp = [cakeAz1.value, cakeAz2.value].sort((a, b) => a - b)
          cakeAz1.value = tmp[0]; cakeAz2.value = tmp[1]
        }
        if (azSliceContainer.value) Plotly.relayout(azSliceContainer.value, { shapes: azSliceShapes() })
      }
    }
  })
}

// ===================== CAKE SELECTION ACTIONS =====================
function recordCakeArea() {
  if (!cakeHasSelection.value) return
  const qLo = Math.min(cakeQ1.value, cakeQ2.value)
  const qHi = Math.max(cakeQ1.value, cakeQ2.value)
  const azLo = Math.min(cakeAz1.value, cakeAz2.value)
  const azHi = Math.max(cakeAz1.value, cakeAz2.value)

  // Edit mode (bounds were loaded from a table row): UPDATE that ROI's
  // geometry in place — multiplier, per-peak background and refine/match
  // results are all kept — and re-run matching so the hkl/export columns
  // track the moved box. NEVER appends a new row on this path.
  if (cakeEditRoiIndex.value != null && cakeRois.value[cakeEditRoiIndex.value]) {
    const roi = cakeRois.value[cakeEditRoiIndex.value]
    roi.qMin = qLo
    roi.qMax = qHi
    roi.azimuthMin = azLo
    roi.azimuthMax = azHi
    cakeSelectedRoiIndex.value = cakeEditRoiIndex.value
    cakeEditRoiIndex.value = null
    clearCakeSelection()
    runMillerMatch()
    return
  }

  const newIdx = cakeRois.value.push({
    qMin: qLo,
    qMax: qHi,
    azimuthMin: azLo,
    azimuthMax: azHi,
    // Quick settings (slice card) stamp every newly recorded peak.
    multiplier: cakeQuickMultiplier.value,
    intensity: null,
    pixelCount: null,
    label: '',
    matchHkl: null,
    matchQMin: null, matchQMax: null, matchAzMin: null, matchAzMax: null,
    exportQMin: null, exportQMax: null, exportPsiMin: null, exportPsiMax: null,
    refined: false,
    ...defaultBgFields(),
  }) - 1
  clearCakeSelection()
  // Track the fresh ROI as selected so a subsequent F (精致匹配框) targets
  // the peak just recorded, not whatever row was clicked earlier.
  cakeSelectedRoiIndex.value = newIdx
}

function clearCakeSelection() {
  cakeQ1.value = null; cakeQ2.value = null
  cakeAz1.value = null; cakeAz2.value = null
  cakeClickPos.value = null
  // Clearing the selection also exits row-edit mode (取消修改 does exactly
  // this); a later 记录 then appends a new ROI again.
  cakeEditRoiIndex.value = null
  if (qSliceContainer.value) Plotly.purge(qSliceContainer.value)
  if (azSliceContainer.value) Plotly.purge(azSliceContainer.value)
}

// ===================== DETECTOR REGION SELECTION =====================
function onDetectorRegionSelected(region) {
  const [x1, x2] = region.xRange
  const [y1, y2] = region.yRange
  detectorRois.value.push({
    xMin: Math.round(Math.min(x1, x2)),
    xMax: Math.round(Math.max(x1, x2)),
    yMin: Math.round(Math.min(y1, y2)),
    yMax: Math.round(Math.max(y1, y2)),
    multiplier: 1,
    intensity: null,
    pixelCount: null,
    label: '',
  })
}

// ===================== ROI MANAGEMENT =====================
const addRoi = () => {
  cakeRois.value.push({ qMin: 0, qMax: 1, azimuthMin: 0, azimuthMax: 360, multiplier: cakeQuickMultiplier.value, intensity: null, pixelCount: null, label: '', matchHkl: null, matchQMin: null, matchQMax: null, matchAzMin: null, matchAzMax: null, exportQMin: null, exportQMax: null, exportPsiMin: null, exportPsiMax: null, refined: false, ...defaultBgFields() })
}

const addDetectorRoi = () => {
  detectorRois.value.push({ xMin: 0, xMax: 100, yMin: 0, yMax: 100, multiplier: 1, intensity: null, pixelCount: null, label: '' })
}

// CSV field escaping — labels may contain commas/quotes.
function csvEscape(s) {
  const v = String(s ?? '')
  return /[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v
}

const exportRois = async () => {
  try {
    if (!cakeRois.value.length) {
      consoleLogs.cake.push(t('logs.analysis.exportNoData'))
      return
    }
    // Full-fidelity ROI export: the geometric box plus the per-peak multiplier,
    // background-subtraction config and refine/match results, so an import
    // restores the whole working state (backgrounds, refined boxes, hkl
    // labels). The first six columns keep the historical header order so
    // older builds and spreadsheet round-trips still read the file.
    const header = 'index,qMin,qMax,azimuthMin,azimuthMax,multiplier,label,bgMode,bgFixedValue,bgSide,bgWidth,matchHkl,refined,matchQMin,matchQMax,matchAzMin,matchAzMax,exportQMin,exportQMax,exportPsiMin,exportPsiMax'
    const fmt = (v, d = 4) => (v == null || !Number.isFinite(v)) ? '' : Number(v).toFixed(d)
    const lines = cakeRois.value.map((r, i) => [
      i,
      fmt(r.qMin), fmt(r.qMax), fmt(r.azimuthMin), fmt(r.azimuthMax),
      fmt(r.multiplier ?? 1),
      csvEscape(r.label || ''),
      r.bgMode ?? '',
      fmt(r.bgFixedValue),
      r.bgSide ?? '',
      fmt(r.bgWidth),
      csvEscape(r.matchHkl || ''),
      r.refined ? 'Refined' : 'Main',
      fmt(r.matchQMin), fmt(r.matchQMax), fmt(r.matchAzMin), fmt(r.matchAzMax),
      fmt(r.exportQMin), fmt(r.exportQMax), fmt(r.exportPsiMin), fmt(r.exportPsiMax),
    ].join(','))
    const csv = `${header}\n${lines.join('\n')}\n`
    const out = await saveToDisk({
      defaultName: 'roi_records.csv',
      filters: [{ name: 'CSV', extensions: ['csv'] }],
      text: csv,
      mime: 'text/csv',
    })
    if (out?.ok) consoleLogs.cake.push(t('logs.analysis.roisExported'))
  } catch (err) {
    consoleLogs.cake.push(t('logs.analysis.exportError', { message: err.response?.data?.detail || err.message }))
  }
}

function importCakeRois() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.csv'
  input.onchange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const text = await file.text()
      // parseRoiCsv recognises matched_intensity.csv (导出匹配强度),
      // roi_records.csv (导出 ROI) and headerless CSVs by header name;
      // new peaks get the panel's background settings as their defaults.
      const { rois, format, count } = parseRoiCsv(text, defaultBgFields())
      rois.forEach(r => cakeRois.value.push(r))
      consoleLogs.cake.push(`Imported ${count} ROIs from ${file.name} (${format})`)
    } catch (err) {
      consoleLogs.cake.push(`Import failed: ${err.message}`)
    }
  }
  input.click()
}

// ===================== INTENSITY CALCULATION =====================
// Build the background payload for one ROI. Each peak carries its own
// bgMode/bgFixedValue/bgSide/bgWidth (editable per-row in the ROI table);
// ROIs without them (stale state) fall back to the panel values. 'dbscan'
// stays a UI-only estimation mode resolved to a fixed per-pixel value.
function roiBgPayload(r) {
  const effectiveMode =
    cakeBgMode.value === 'dbscan'
      ? (cakeBgEstimate.value ? 'fixed' : 'none')
      : cakeBgMode.value
  const effectiveValue =
    cakeBgMode.value === 'dbscan'
      ? (cakeBgEstimate.value ? cakeBgEstimate.value.backgroundValue : 0)
      : cakeBgValue.value
  const mode = r.bgMode ?? effectiveMode
  const payload = { mode }
  if (mode === 'fixed') payload.fixedValue = r.bgMode != null ? (r.bgFixedValue ?? 0) : effectiveValue
  if (mode === 'neighbor') {
    payload.side = r.bgMode != null ? (r.bgSide || 'both') : cakeBgSide.value
    payload.width = r.bgMode != null ? (r.bgWidth ?? 10) : cakeBgWidth.value
  }
  return payload
}

const calculateIntensity = async () => {
  taskStatus.cake = 'running'
  consoleLogs.cake = [t('logs.analysis.calculatingIntensity')]
  try {
    const regions = cakeRois.value.map(r => ({
      qMin: r.qMin, qMax: r.qMax, azimuthMin: r.azimuthMin, azimuthMax: r.azimuthMax, multiplier: r.multiplier ?? 1.0,
      // Per-peak background subtraction (fixed / x-axis neighbours with a
      // per-peak side choice). The request-wide `background` below stays as
      // the backend fallback for regions without their own config.
      background: roiBgPayload(r),
    }))

    const res = await analysisCalculateIntensity({
      fileId: cakeImageFileId.value,
      regions,
      backgroundMode: 0,
      // Panel-resolved payload as the request-wide fallback (every region
      // above already carries its own per-peak config).
      background: roiBgPayload({}),
      qRange: cakeMeta.value?.qRange,
      chiRange: cakeMeta.value?.chiRange,
      minIntensity: cakeSaturationMin.value ?? undefined,
      maxIntensity: cakeSaturationMax.value ?? undefined,
    })
    const results = res.data?.results || []
    results.forEach((r, i) => {
      if (cakeRois.value[i]) {
        cakeRois.value[i].intensity = r.totalIntensity
        cakeRois.value[i].pixelCount = r.pixelCount
      }
    })
    consoleLogs.cake.push(t('logs.analysis.intensityDone'))
    taskStatus.cake = 'completed'
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
    runStatus.value = 'failed'
  }
}

const calculateDetectorIntensity = async () => {
  taskStatus.detector = 'running'
  consoleLogs.detector = [t('logs.analysis.calculatingIntensity')]
  try {
    const regions = detectorRois.value.map(r => ({
      xMin: r.xMin, xMax: r.xMax, yMin: r.yMin, yMax: r.yMax, multiplier: r.multiplier ?? 1.0,
    }))
    const bgPayload = { mode: detectorBgMode.value }
    if (detectorBgMode.value === 'fixed') bgPayload.fixedValue = detectorBgValue.value
    if (detectorBgMode.value === 'neighbor') { bgPayload.side = detectorBgSide.value; bgPayload.width = detectorBgWidth.value }

    const res = await analysisCalculateIntensity({
      fileId: detectorImageFileId.value,
      regions,
      backgroundMode: 0,
      background: bgPayload,
      coordinateType: 'pixel',
      minIntensity: detectorSaturationMin.value ?? undefined,
      maxIntensity: detectorSaturationMax.value ?? undefined,
    })
    const results = res.data?.results || []
    results.forEach((r, i) => {
      if (detectorRois.value[i]) {
        detectorRois.value[i].intensity = r.totalIntensity
        detectorRois.value[i].pixelCount = r.pixelCount
      }
    })
    consoleLogs.detector.push(t('logs.analysis.intensityDone'))
    taskStatus.detector = 'completed'
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs.detector.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.detector = 'error'
    runStatus.value = 'failed'
  }
}

// ===================== MILLER =====================
// Match recorded ROIs against the loaded Miller datasets using the current
// azimuth transform. Re-run whenever the offset/convention change so the
// matchHkl column tracks what the overlay actually shows.
async function runMillerMatch() {
  if (!millerDatasets.value.length || !cakeRois.value.length) return
  consoleLogs.cake.push(t('logs.analysis.matchingMiller'))
  try {
    // Reset stale matches before re-evaluating with the current transform.
    cakeRois.value.forEach(r => { r.matchHkl = null })
    const regions = cakeRois.value.map(r => ({
      qMin: r.qMin, qMax: r.qMax, azimuthMin: r.azimuthMin, azimuthMax: r.azimuthMax, multiplier: r.multiplier ?? 1.0,
      // Forward the optional refine box so the backend matches only inside it
      // (null => fall back to the integration ROI).
      matchQMin: r.matchQMin ?? null, matchQMax: r.matchQMax ?? null,
      matchAzMin: r.matchAzMin ?? null, matchAzMax: r.matchAzMax ?? null,
    }))
    const matchRes = await analysisMatchMiller({
      regions,
      millerDatasets: millerDatasets.value,
      qTolerance: millerQTolerance.value,
      chiTolerance: millerChiTolerance.value,
      // Keep the match transform identical to millerOverlayPoints so a point
      // drawn at χ matches an ROI centred at the same χ.
      azimuthOffset: millerAzimuthOffset.value,
      convention: millerConvention.value,
      normalizeToSigned: true,
      // 精致化 export margins (dq / dψ around the min/max of matched points).
      exportQMargin: millerExportQMargin.value,
      exportPsiMargin: millerExportPsiMargin.value,
    })
    const results = matchRes.data?.results || []
    results.forEach((mr, i) => {
      const roi = cakeRois.value[i]
      if (!roi) return
      // Store the Miller-derived export ranges (q ± 0.02, ψ ± 3°) regardless of
      // match status — the backend inverse-maps the box when nothing matched, so
      // the export column always carries Miller-space numbers.
      roi.refined = !!mr.refined
      roi.exportQMin = mr.exportQMin ?? null
      roi.exportQMax = mr.exportQMax ?? null
      roi.exportPsiMin = mr.exportPsiMin ?? null
      roi.exportPsiMax = mr.exportPsiMax ?? null
      if (mr.matchedPoints?.length > 0) {
        const p = mr.matchedPoints[0]
        roi.matchHkl = `(${p.h} ${p.k} ${p.l})`
      }
    })
    const found = results.filter(r => r.status === 'Found').length
    consoleLogs.cake.push(t('logs.analysis.matchDone', { found, total: results.length }))
  } catch (err) {
    consoleLogs.cake.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
  }
}

// Begin drawing a refine match-box for ROI index i. Forces drag-select for the
// next drag; onCakeRegionSelected stores the result and re-runs matching.
function startRefineMatch(i) {
  if (i == null || !cakeRois.value[i]) return
  cakeRefineTarget.value = i
  cakeSelectedRoiIndex.value = i
  cakeRefineDrawing.value = true
  // The refine button lives in the ROI table (usually scrolled out of view);
  // bring the cake image + banner back into view so the drag target is visible.
  nextTick(() => cakeTopRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

// Remove the refine box from ROI i so matching/export revert to the full ROI.
function clearRefineMatch(i) {
  const roi = cakeRois.value[i]
  if (!roi) return
  roi.matchQMin = null; roi.matchQMax = null; roi.matchAzMin = null; roi.matchAzMax = null
  runMillerMatch()
}

// Re-match automatically when the user tweaks the azimuth transform, the
// match tolerances or the export margins. Watching ROI count as well means a
// freshly recorded ROI gets its hkl without re-loading Miller.
watch(
  [millerAzimuthOffset, millerConvention, millerQTolerance, millerChiTolerance, millerExportQMargin, millerExportPsiMargin],
  () => { runMillerMatch() }
)
watch(
  () => cakeRois.value.length,
  () => { runMillerMatch() }
)

const loadMillerOverlay = async () => {
  if (!millerFiles.value.length) return
  runStatus.value = 'running'
  taskStatus.cake = 'running'
  consoleLogs.cake = [t('logs.analysis.uploadingMiller')]
  try {
    const formData = new FormData()
    millerFiles.value.forEach(f => formData.append('files', f))
    const res = await analysisUploadMiller(formData)
    if (res.data?.datasets) {
      millerDatasets.value = res.data.datasets
    }
    consoleLogs.cake.push(t('logs.analysis.millerLoaded'))

    await runMillerMatch()
    taskStatus.cake = 'completed'
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs.cake.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.cake = 'error'
    runStatus.value = 'failed'
  }
}

// ===================== EXPORT MATCHED INTENSITY =====================
async function exportMatchedIntensity() {
  if (!cakeRois.value.length) return
  // Ensure intensity calculated
  if (cakeRois.value.some(r => r.intensity == null)) await calculateIntensity()
  // Refresh matches so the Miller-derived export ranges (q ± 0.02, ψ ± 3°) are
  // current against any refine boxes / transform changes before we serialize.
  if (millerDatasets.value.length) await runMillerMatch()

  const maxIntensity = Math.max(...cakeRois.value.map(r => r.intensity ?? 0), 1)
  // Export the Miller-point ± ranges (not the integration-box ranges): ψ ± 3°,
  // q ± 0.02 Å⁻¹ around the matched point, mirroring reference/function3.
  let csv = 'ID,Match_hkl,New_Psi_Min(deg),New_Psi_Max(deg),New_Q_Min(A-1),New_Q_Max(A-1),Status,Refined_Flag,Norm_Intensity,Raw_Intensity\n'
  const fmt = (v, d = 4) => (v == null || !Number.isFinite(v)) ? '' : Number(v).toFixed(d)
  cakeRois.value.forEach((r, i) => {
    const hkl = r.matchHkl || 'N/A'
    const status = hkl !== 'N/A' ? 'Found' : 'Not Found'
    const refinedFlag = r.refined ? 'Refined' : 'Main'
    const raw = r.intensity ?? 0
    const norm = raw / maxIntensity
    csv += `${i + 1},${hkl},${fmt(r.exportPsiMin)},${fmt(r.exportPsiMax)},${fmt(r.exportQMin)},${fmt(r.exportQMax)},${status},${refinedFlag},${norm.toFixed(6)},${raw.toFixed(6)}\n`
  })
  await saveToDisk({
    defaultName: 'matched_intensity.csv',
    filters: [{ name: 'CSV', extensions: ['csv'] }],
    text: csv,
    mime: 'text/csv',
  })
}

// ===================== EXPORT =====================
// Write bytes to disk: under Electron pop the native "save as" dialog (the
// silent <a download>/Blob path never showed one and silently no-op'd). In a
// plain browser, fall back to a Blob download.
async function saveToDisk({ defaultName, filters, dataUrl, text, mime }) {
  if (isElectron()) {
    const res = await window.electronAPI.saveFile({ defaultName, filters, dataUrl, text })
    return res
  }
  // Browser fallback
  let blob
  if (dataUrl != null) {
    const r = await fetch(dataUrl)
    blob = await r.blob()
  } else {
    blob = new Blob([text == null ? '' : text], { type: mime || 'text/plain' })
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = defaultName
  a.click()
  URL.revokeObjectURL(url)
  return { ok: true }
}

// Full-image PNG export. Renders OFFSCREEN from the raw data with explicit
// full axis ranges — deliberately not the on-screen canvas, whose viewport
// reflects the user's current zoom/pan (and whose fixed 1200×800 crop cut off
// the image). With the χ crop enabled, "full image" means the full q extent
// over the cropped χ band.
const exportImage = async (format) => {
  const tab = activeTab.value
  try {
    let dataUrl
    if (tab === 'cake') {
      if (!cakeImageData.value) {
        consoleLogs.cake.push(t('logs.analysis.exportNoImage'))
        return
      }
      dataUrl = await renderFullImageDataUrl({
        imageData: cakeImageData.value,
        xAxis: cakeXAxis.value,
        yAxis: cakeYAxis.value,
        colorscale: cakeControls.colormap,
        logScale: cakeControls.logScale,
        zmin: cakeControls.zmin,
        zmax: cakeControls.zmax,
        yRange: cakeCropEnabled.value
          ? [Math.min(cakeCropChiMin.value, cakeCropChiMax.value), Math.max(cakeCropChiMin.value, cakeCropChiMax.value)]
          : null,
        title: t('analysis.cake.displayTitle'),
        xAxisTitle: t('analysis.cake.xAxisTitle'),
        yAxisTitle: t('analysis.cake.yAxisTitle'),
        format,
      })
    } else {
      if (!detectorImageData.value) {
        consoleLogs.detector.push(t('logs.analysis.exportNoImage'))
        return
      }
      dataUrl = await renderFullImageDataUrl({
        imageData: detectorImageData.value,
        colorscale: detectorControls.colormap,
        logScale: detectorControls.logScale,
        title: t('analysis.detector.displayTitle'),
        format,
      })
    }
    if (!dataUrl) {
      if (consoleLogs[tab]) consoleLogs[tab].push(t('logs.analysis.exportNoImage'))
      return
    }
    const res = await saveToDisk({
      defaultName: `image_export.${format}`,
      filters: [{ name: format.toUpperCase(), extensions: [format] }],
      dataUrl,
    })
    if (res?.ok && res.filePath && consoleLogs[tab]) {
      consoleLogs[tab].push(`${t('analysis.export.png')}: ${res.filePath}`)
    }
  } catch (err) {
    if (consoleLogs[tab]) consoleLogs[tab].push(t('logs.analysis.exportError', { message: err.response?.data?.detail || err.message }))
  }
}

// Cleanup Plotly on unmount
onBeforeUnmount(() => {
  if (qSliceContainer.value) Plotly.purge(qSliceContainer.value)
  if (azSliceContainer.value) Plotly.purge(azSliceContainer.value)
  if (sliceResizeObserver) {
    sliceResizeObserver.disconnect()
    sliceResizeObserver = null
  }
  window.removeEventListener('resize', onWindowResize)
  window.removeEventListener('keydown', onCakeKeydown)
})
</script>

<style scoped>
/* ===== Page Layout ===== */
.image-analysis-page { display: flex; flex-direction: column; }
.main-container { display: flex; flex: 1; }

/* ---- Sidebar ---- */
.sidebar {
  width: var(--sidebar-width, 240px);
  background: var(--color-neutral);
  border-right: 1px solid var(--color-border);
  display: flex; flex-direction: column;
  position: sticky; top: 0;
  height: calc(100vh - var(--header-height, 56px));
  align-self: flex-start;
}
.tab-nav { flex: 1; padding: 16px 12px; display: flex; flex-direction: column; gap: 2px; }
.tab-item {
  display: flex; align-items: center; gap: 10px; height: 36px;
  padding: 0 14px; border: none; border-radius: 6px;
  background: transparent; color: var(--color-text-secondary);
  font-family: 'Inter', system-ui, sans-serif; font-size: 13px; font-weight: 500;
  text-align: left; cursor: pointer; transition: all 0.15s ease; position: relative; white-space: nowrap;
}
.tab-item:hover { background: var(--color-surface); color: var(--color-text); }
.tab-item.active { background: var(--color-primary-10, rgba(124, 58, 237, 0.08)); color: var(--color-text); }
.tab-item.active::before {
  content: ''; position: absolute; left: 0; top: 50%; transform: translateY(-50%);
  width: 3px; height: 20px; background: var(--color-primary); border-radius: 0 2px 2px 0;
}
.tab-icon { width: 18px; height: 18px; flex-shrink: 0; }
.tab-label { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.sidebar-footer { padding: 12px 16px; border-top: 1px solid var(--color-border); }
.status-indicator {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  background: var(--color-surface); border-radius: 6px; font-size: 12px;
}
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--color-text-secondary); }
.status-dot.running { background: var(--color-warning); animation: pulse 2s infinite; }
.status-dot.success { background: var(--color-success); }
.status-dot.error { background: var(--color-error); }
.status-text { color: var(--color-text-secondary); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* ---- Content ---- */
.content { flex: 1; padding: 20px; overflow-y: auto; min-width: 0; }
.tab-panel { max-width: 1500px; }

/* ---- Content Grid (two-column; used by the Detector tab) ---- */
.content-grid { display: flex; gap: 20px; align-items: flex-start; }
.left-panel { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.right-panel { width: 270px; flex-shrink: 0; display: flex; flex-direction: column; gap: 10px; }

/* ---- Cake tab: top image card is full width; sub-tabs switch Settings/ROI ---- */
.image-main-card { margin-bottom: 0; }

/* Secondary tab bar (Settings | ROI Info) */
.sub-tabs {
  display: flex; gap: 2px; margin: 16px 0 14px;
  border-bottom: 1px solid var(--color-border);
}
.sub-tab {
  padding: 8px 20px; border: none; background: transparent;
  color: var(--color-text-secondary); font-size: 13px; font-weight: 500;
  font-family: 'Inter', system-ui, sans-serif; cursor: pointer;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
  transition: color 0.15s, border-color 0.15s;
}
.sub-tab:hover { color: var(--color-text); }
.sub-tab.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }

/* Settings panel: control cards laid out 2-per-row */
.settings-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
  align-items: start;
}
.settings-full { grid-column: 1 / -1; }

/* Always-visible control row (Contrast + Region Selection), outside the sub-tabs */
.controls-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
  align-items: start; margin-top: 14px;
}

/* Empty ROI panel (before an image is loaded) */
.empty-panel-hint {
  padding: 48px; text-align: center; color: var(--color-text-secondary);
  font-size: 13px; background: var(--color-surface);
  border: 1px dashed var(--color-border); border-radius: 10px;
}

/* ---- Section Cards ---- */
.section-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 16px;
}
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 12px; padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}
.section-header h3 {
  font-size: 13px; font-weight: 600; color: var(--color-text); margin: 0;
}
.section-header-sub {
  font-size: 11px; color: var(--color-text-secondary); font-family: 'JetBrains Mono', monospace;
}
.section-header-actions { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }

/* ---- Image Canvas Wrap ---- */
.image-canvas-wrap { margin-top: 4px; }
.image-main-card .image-canvas-wrap { min-height: 520px; }
.image-placeholder {
  width: 100%; aspect-ratio: 4 / 3;
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: 10px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 8px;
  color: var(--color-text-secondary); font-size: 14px;
}
.placeholder-icon { width: 48px; height: 48px; color: var(--color-text-secondary); opacity: 0.5; }
.placeholder-hint { font-size: 12px; opacity: 0.6; }

/* ---- Slice Plots ---- */
.slice-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.slice-plot { display: flex; flex-direction: column; }
.slice-plot-label {
  font-size: 11px; font-weight: 500; color: var(--color-text-secondary);
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;
}
.slice-plot-params {
  display: flex; align-items: center; gap: 4px; margin-bottom: 4px;
}
.slice-plot-params label { font-size: 10px; color: var(--color-text-placeholder); white-space: nowrap; }
.param-input-xs { width: 64px; height: 24px; font-size: 10px; padding: 0 4px; }
.param-unit { font-size: 10px; color: var(--color-text-secondary); }
.slice-plot-area { width: 100%; min-height: 160px; }

/* ---- Slice card: floating mode (draggable header + resize handle) ---- */
.slice-card--floating {
  position: fixed;
  z-index: 900;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.28);
  background: var(--color-surface);
  opacity: 0.98;
}
.slice-card__header--drag { cursor: move; user-select: none; touch-action: none; }
.slice-card__actions { display: flex; align-items: center; gap: 4px; margin-left: auto; }
.slice-card__close { font-size: 18px; padding: 0 6px; }
.slice-card--floating .slice-grid { flex: 1; min-height: 0; align-content: stretch; }
.slice-card--floating .slice-plot { min-height: 0; }
.slice-card--floating .slice-plot-area { flex: 1; min-height: 120px; }
.slice-card__resize {
  position: absolute; right: 0; bottom: 0;
  width: 18px; height: 18px;
  cursor: nwse-resize;
  touch-action: none;
  background:
    linear-gradient(135deg, transparent 50%, var(--color-border) 50%, var(--color-border) 62%, transparent 62%, transparent 74%, var(--color-border) 74%, var(--color-border) 86%, transparent 86%);
}
.slice-card__resize:hover { background-color: rgba(124, 58, 237, 0.12); }

/* ---- Quick settings strip inside the slice card ---- */
.quick-settings {
  margin-top: 10px; padding-top: 8px;
  border-top: 1px dashed var(--color-border);
}
.quick-settings__title {
  font-size: 11px; font-weight: 600; color: var(--color-text-secondary);
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;
}
.quick-settings__row {
  display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap;
}
.quick-field { display: flex; flex-direction: column; gap: 3px; }
.quick-field > span:first-child {
  font-size: 10px; color: var(--color-text-placeholder);
  white-space: nowrap;
}
.quick-field .param-input-xs { width: 84px; }
.quick-field--value .quick-value {
  height: 24px; display: inline-flex; align-items: center;
  font-size: 11px; font-family: 'JetBrains Mono', monospace;
  color: var(--color-text);
}
.quick-settings__actions {
  margin-left: auto; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.slice-card--floating .quick-settings { padding: 8px 12px 10px; }
.slice-card--floating .quick-settings__actions { margin-left: 0; }

/* ---- DBSCAN background estimation result ---- */
.bg-estimate-result {
  margin-top: 10px; padding: 10px 12px;
  background: var(--color-neutral);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  display: flex; flex-direction: column; gap: 6px;
}
.bg-estimate-line {
  display: flex; flex-wrap: wrap; gap: 14px;
  font-size: 11.5px; color: var(--color-text);
  font-family: 'JetBrains Mono', monospace;
}
.bg-estimate-line b { color: var(--color-text-secondary); font-weight: 600; }
.bg-cluster-list {
  max-height: 150px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 2px;
  border-top: 1px dashed var(--color-border); padding-top: 6px;
}
.bg-cluster-row {
  display: grid; grid-template-columns: 30px 90px 90px 70px 80px;
  gap: 6px; font-size: 10.5px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--color-text-secondary);
}
.bg-cluster-row span:first-child { color: var(--color-primary); font-weight: 600; }
.dbscan-hint {
  margin-top: 8px; font-size: 11px; line-height: 1.5;
  color: var(--color-text-secondary);
}
.panel-hint {
  margin: -2px 0 8px; font-size: 11px; line-height: 1.5;
  color: var(--color-text-secondary);
}

/* Per-peak background columns in the ROI table */
.td-bg-params { white-space: nowrap; }
.td-bg-params select.cell-input { width: auto; min-width: 60px; }
.cell-input-narrow { width: 56px; min-width: 56px; }

/* ---- Form Elements ---- */
.form-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-field-stack { display: flex; flex-direction: column; gap: 4px; }
.form-field-stack label {
  font-size: 11px; font-weight: 500; color: var(--color-text-secondary);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.form-row { display: flex; gap: 8px; align-items: center; }

.param-input {
  height: 32px; padding: 0 10px;
  background: var(--color-neutral); border: 1px solid var(--color-border);
  border-radius: 6px; color: var(--color-text); font-size: 12px;
  font-family: 'Inter', system-ui, sans-serif; outline: none;
  transition: border-color 0.15s; width: 100%; box-sizing: border-box;
}
.param-input:focus { border-color: var(--color-primary); }

.toggle-btn {
  height: 32px; padding: 0 16px; border: 1px solid var(--color-border);
  border-radius: 6px; background: var(--color-neutral);
  color: var(--color-text-secondary); font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
}
.toggle-btn.active {
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
  border-color: var(--color-primary); color: var(--color-primary);
}

/* ---- Contrast (right panel; slider + number each on its own row) ---- */
.contrast-block { display: flex; flex-direction: column; gap: 10px; }
.contrast-field { display: flex; flex-direction: column; gap: 4px; }
.contrast-block-label {
  font-size: 11px; font-weight: 500; color: var(--color-text-secondary);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.contrast-slider { width: 100%; height: 4px; accent-color: var(--color-primary); cursor: pointer; }
.contrast-num {
  width: 100%; height: 26px; padding: 0 8px;
  background: var(--color-neutral); border: 1px solid var(--color-border);
  border-radius: 4px; color: var(--color-text); font-size: 11px;
  font-family: 'JetBrains Mono', monospace; outline: none; text-align: left;
  box-sizing: border-box;
}
.contrast-num:focus { border-color: var(--color-primary); }

/* ---- χ crop toggle ---- */
.crop-toggle {
  display: flex; align-items: center; gap: 6px; cursor: pointer;
  font-size: 12px; color: var(--color-text-secondary);
}
.crop-toggle input { accent-color: var(--color-primary); cursor: pointer; }

/* ---- Selection Mode Buttons ---- */
.mode-btn {
  display: flex; align-items: center; gap: 6px; height: 32px; padding: 0 12px;
  border: 1px solid var(--color-border); border-radius: 6px;
  background: var(--color-neutral); color: var(--color-text-secondary);
  font-size: 12px; font-weight: 500; cursor: pointer;
  font-family: 'Inter', system-ui, sans-serif; transition: all 0.15s;
}
.mode-btn:hover { border-color: var(--color-text-secondary); }
.mode-btn.active {
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
  border-color: var(--color-primary); color: var(--color-primary);
}
.selection-info { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.sel-tag {
  font-size: 11px; font-family: 'JetBrains Mono', monospace;
  background: var(--color-neutral); padding: 3px 8px;
  border: 1px solid var(--color-border); border-radius: 4px;
  color: var(--color-text);
}
.sel-tag--edit {
  border-color: var(--color-primary); color: var(--color-primary);
  font-family: 'Inter', system-ui, sans-serif; font-weight: 500;
}

/* ---- Miller point color picker + margin hint ---- */
.color-row { display: flex; align-items: center; gap: 6px; }
.color-input {
  width: 100%; height: 32px; padding: 2px;
  background: var(--color-neutral); border: 1px solid var(--color-border);
  border-radius: 6px; cursor: pointer;
}
.miller-margin-hint {
  margin-top: 6px; font-size: 11px; line-height: 1.5;
  color: var(--color-text-secondary);
}

/* ---- Refine match-box banner + button ---- */
.refine-banner {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin: 10px 0; padding: 8px 12px;
  background: rgba(34, 211, 238, 0.12);
  border: 1px solid #22D3EE; border-radius: 6px;
}
.refine-banner-text { font-size: 12px; color: #0e7490; font-weight: 500; }
.refine-btn {
  width: 26px; height: 26px; border: 1px solid var(--color-border);
  border-radius: 5px; background: var(--color-neutral); color: var(--color-text-secondary);
  font-size: 13px; font-weight: 700; cursor: pointer; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.refine-btn:hover { border-color: #22D3EE; color: #0e7490; }
.refine-btn.active { background: rgba(34, 211, 238, 0.18); border-color: #22D3EE; color: #0e7490; }
.td-compact { white-space: nowrap; font-size: 10.5px; }

/* ---- Compact Buttons ---- */
.btn-compact {
  display: inline-flex; align-items: center; gap: 4px;
  height: 28px; padding: 0 10px;
  border: 1px solid var(--color-border); border-radius: 5px;
  background: var(--color-bg); color: var(--color-text-secondary);
  font-size: 11px; font-weight: 500; cursor: pointer;
  font-family: 'Inter', system-ui, sans-serif; transition: all 0.15s;
  position: relative; overflow: hidden;
}
.btn-compact:hover { border-color: var(--color-primary); color: var(--color-text); }
.btn-compact input[type="file"] { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.btn-primary-compact {
  background: var(--color-primary); color: white; border: 1px solid var(--color-primary);
}
.btn-primary-compact:hover { opacity: 0.9; }
.btn-primary-compact:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-accent-compact {
  background: var(--color-primary-10, rgba(124, 58, 237, 0.08));
  border-color: var(--color-primary); color: var(--color-primary);
}
.btn-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

/* ---- Meta Strip ---- */
.meta-strip {
  display: flex; flex-wrap: wrap; gap: 16px; margin-top: 8px; margin-bottom: 8px;
  padding: 8px 12px; background: var(--color-neutral);
  border: 1px solid var(--color-border); border-radius: 6px;
  font-size: 12px; color: var(--color-text-secondary);
  font-family: 'JetBrains Mono', monospace;
}
.meta-strip strong { color: var(--color-text); font-weight: 600; }

/* ---- ROI Section (full width) ---- */
.roi-section { margin-top: 20px; }

/* ---- ROI Table ---- */
.roi-table-wrap {
  overflow-x: auto; overflow-y: auto;
  /* Cap height so the table scrolls once it grows past ~10 rows. */
  max-height: 360px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
}
.roi-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.roi-table th {
  padding: 8px 8px; text-align: left; font-weight: 600;
  color: var(--color-text-secondary); background: var(--color-neutral);
  border-bottom: 1px solid var(--color-border);
  text-transform: uppercase; letter-spacing: 0.5px; font-size: 10px; white-space: nowrap;
  /* Keep the header pinned while the body scrolls. */
  position: sticky; top: 0; z-index: 1;
}
.roi-table td { padding: 3px 6px; border-bottom: 1px solid var(--color-border); }
.roi-table tr:last-child td { border-bottom: none; }
.roi-table tr.row-selected { background: var(--color-primary-10, rgba(124, 58, 237, 0.05)); }
.td-idx { color: var(--color-text-secondary); font-weight: 500; text-align: center; width: 32px; }
.td-num { font-family: 'JetBrains Mono', monospace; color: var(--color-text); text-align: right; }
.td-match { font-family: 'JetBrains Mono', monospace; color: var(--color-primary); font-weight: 500; }
.cell-input {
  width: 100%; min-width: 60px; height: 26px; padding: 0 6px;
  background: var(--color-neutral); border: 1px solid transparent;
  border-radius: 4px; color: var(--color-text); font-size: 11px;
  font-family: 'JetBrains Mono', monospace; outline: none; box-sizing: border-box;
}
.cell-input:focus { border-color: var(--color-primary); }
.cell-select { cursor: pointer; }

/* ---- Buttons ---- */
.btn-icon {
  background: none; border: none; color: var(--color-text-secondary);
  cursor: pointer; font-size: 16px; padding: 2px 6px; border-radius: 4px; flex-shrink: 0;
}
.btn-icon:hover { background: var(--color-error); color: white; }
.btn-primary {
  height: 36px; padding: 0 20px; background: var(--color-primary);
  color: white; border: none; border-radius: 6px; font-size: 13px;
  font-weight: 600; font-family: 'Inter', system-ui, sans-serif; cursor: pointer;
  transition: opacity 0.15s;
}
.btn-primary:hover { opacity: 0.9; }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-secondary {
  height: 34px; padding: 0 16px; background: transparent;
  color: var(--color-text-secondary); border: 1px solid var(--color-border);
  border-radius: 6px; font-size: 12px; font-weight: 500;
  font-family: 'Inter', system-ui, sans-serif; cursor: pointer; transition: all 0.15s;
}
.btn-secondary:hover { background: var(--color-surface); color: var(--color-text); border-color: var(--color-text-secondary); }

/* ---- Export Bar ---- */
.export-bar { display: flex; gap: 10px; padding: 12px 0; }

/* ---- Cards (legacy) ---- */
.card {
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: 10px; padding: 20px;
}
.card-subtitle { font-size: 14px; font-weight: 600; color: var(--color-text); margin: 0 0 14px; }
.overlay-card { margin-top: 0; }
.roi-card { margin-top: 0; }

/* ---- Fade ---- */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ---- Responsive ---- */
@media (max-width: 1024px) {
  .sidebar { width: 72px; }
  .tab-label, .sidebar-footer { display: none; }
  .tab-item { justify-content: center; padding: 0; gap: 0; }
  .tab-item.active::before { display: none; }
  .content-grid { flex-direction: column; }
  .right-panel { width: 100%; }
  .settings-grid { grid-template-columns: 1fr; }
  .controls-row { grid-template-columns: 1fr; }
}
</style>
