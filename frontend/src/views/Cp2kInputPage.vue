<template>
  <div class="cp2k-page">
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

            <!-- Minimal form -->
            <div v-if="activeSection === 'basic'" class="card">
              <h2 class="card-title">{{ t('cp2k.sections.basic') }}</h2>
              <p class="card-desc">{{ t('cp2k.descs.basic') }}</p>
              <ParamsForm :fields="basicFields" v-model="params" />
            </div>

            <!-- Experimental -->
            <div v-if="activeSection === 'experimental'" class="card">
              <h2 class="card-title">{{ t('cp2k.sections.experimental') }}</h2>
              <p class="card-desc">{{ t('cp2k.descs.experimental') }}</p>
              <ParamsForm :fields="experimentalFields" v-model="params" />
            </div>

            <!-- HKL -->
            <div v-if="activeSection === 'hkl'" class="card">
              <h2 class="card-title">{{ t('cp2k.sections.hkl') }}</h2>
              <p class="card-desc">{{ t('cp2k.descs.hkl') }}</p>
              <ParamsForm :fields="hklFields" v-model="params" />
            </div>

            <!-- B factor -->
            <div v-if="activeSection === 'bfactor'" class="card">
              <h2 class="card-title">{{ t('cp2k.sections.bfactor') }}</h2>
              <p class="card-desc">{{ t('cp2k.descs.bfactor') }}</p>
              <ParamsForm :fields="bFactorFields" v-model="params" />
            </div>

            <!-- Overrides -->
            <div v-if="activeSection === 'overrides'" class="card">
              <h2 class="card-title">{{ t('cp2k.sections.overrides') }}</h2>
              <p class="card-desc">{{ t('cp2k.descs.overrides') }}</p>
              <ParamsForm :fields="overrideFlagFields" v-model="params" style="margin-bottom:20px" />
              <ParamsForm v-if="params.emit_overrides" :fields="overrideFields" v-model="params" />
            </div>

            <!-- Workflow / output -->
            <div v-if="activeSection === 'output'" class="card">
              <h2 class="card-title">{{ t('cp2k.sections.output') }}</h2>
              <p class="card-desc">{{ t('cp2k.descs.output') }}</p>

              <div class="actions-row">
                <button class="btn-primary" @click="generatePreview" :disabled="generating">
                  {{ generating ? t('inputGen.actions.generating') : t('cp2k.actions.generate') }}
                </button>
                <button class="btn-secondary" @click="downloadSection" :disabled="!previewText">
                  {{ t('cp2k.actions.download') }}
                </button>
              </div>

              <ConsolePanel
                v-if="consoleLogs.length || taskStatus !== 'idle'"
                :status="taskStatus"
                :logs="consoleLogs"
                style="margin-top: 16px"
              />

              <div v-if="previewText" class="preview-block">
                <h3 class="subsection-title">{{ t('inputGen.subsections.preview') }}</h3>
                <pre class="preview-code"><code>{{ previewText }}</code></pre>
              </div>

              <div class="usage-note">
                <h3 class="subsection-title">{{ t('cp2k.usage.title') }}</h3>
                <ol class="usage-steps">
                  <li>{{ t('cp2k.usage.step1') }}</li>
                  <li>{{ t('cp2k.usage.step2') }}</li>
                  <li>{{ t('cp2k.usage.step3') }}</li>
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
import ParamsForm from '@/components/ParamsForm.vue'
import ConsolePanel from '@/components/ConsolePanel.vue'
import { cp2kGenerate } from '@/api/index.js'

const { t } = useI18n()

// ---- Sections ----
const sections = computed(() => [
  { id: 'basic', label: t('cp2k.sections.basic') },
  { id: 'experimental', label: t('cp2k.sections.experimental') },
  { id: 'hkl', label: t('cp2k.sections.hkl') },
  { id: 'bfactor', label: t('cp2k.sections.bfactor') },
  { id: 'overrides', label: t('cp2k.sections.overrides') },
  { id: 'output', label: t('cp2k.sections.output') },
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

// ---- Parameters (mirrors Cp2kFiberRequest) ----
const params = reactive({
  enabled: true,
  diffraction_file: 'diffraction_intensity.txt',
  wavelength: 1.24,
  auto_scale: true,
  scale_factor: 1.0e-5,
  lambda: 1.0e-2,
  // experimental
  sample_thickness_cm: 0.03,
  detector_distance_cm: 19.894,
  xray_mode: 0,
  // hkl
  h_max: 5,
  k_max: 5,
  l_max: 20,
  q_min: 0.0,
  max_hkl_per_peak: 50,
  max_blank_hkl: 2000,
  blank_contribution: 0.20,
  // B factor
  b_factor_default: 0.36,
  b_factor_file: '',
  n_b_factor: 0,
  // overrides
  atomic_factor_file: '',
  reflection_file: '',
  peak_result_file: 'peaks_result.txt',
  emit_common_optional: true,
  emit_b_factor: true,
  emit_overrides: false,
})

// ---- Field definitions ----

const basicFields = computed(() => [
  { key: 'enabled', label: 'ENABLED', type: 'checkbox' },
  { key: 'diffraction_file', label: 'DIFFRACTION_FILE', type: 'text' },
  { key: 'wavelength', label: 'WAVELENGTH (Å)', type: 'number', step: 0.0001, min: 0.0001,
    help: t('cp2k.helps.wavelength') },
  { key: 'auto_scale', label: 'AUTO_SCALE', type: 'checkbox',
    help: t('cp2k.helps.autoScale') },
  { key: 'scale_factor', label: 'SCALE_FACTOR (fixed k)', type: 'number', step: 0.000001,
    help: t('cp2k.helps.scaleFactor') },
  { key: 'lambda', label: 'LAMBDA (hartree)', type: 'number', step: 0.0001, min: 0.0000001,
    help: t('cp2k.helps.lambda') },
])

const experimentalFields = computed(() => [
  { key: 'sample_thickness_cm', label: 'SAMPLE_THICKNESS_CM', type: 'number', step: 0.001, min: 0.0001 },
  { key: 'detector_distance_cm', label: 'DETECTOR_DISTANCE_CM', type: 'number', step: 0.001, min: 0.0001 },
  { key: 'xray_mode', label: 'XRAY_MODE', type: 'select', options: [
    { value: 0, label: '0 — Synchrotron' },
    { value: 1, label: '1 — Laboratory source' },
    { value: 2, label: '2 — No polarization factor' },
  ]},
])

const hklFields = computed(() => [
  { key: 'h_max', label: 'H_MAX', type: 'number', step: 1, min: 0, help: t('cp2k.helps.hkl') },
  { key: 'k_max', label: 'K_MAX', type: 'number', step: 1, min: 0 },
  { key: 'l_max', label: 'L_MAX', type: 'number', step: 1, min: 0 },
  { key: 'q_min', label: 'Q_MIN (Å⁻¹)', type: 'number', step: 0.01, min: 0 },
  { key: 'max_hkl_per_peak', label: 'MAX_HKL_PER_PEAK', type: 'number', step: 1, min: 1 },
  { key: 'max_blank_hkl', label: 'MAX_BLANK_HKL', type: 'number', step: 1, min: 1 },
  { key: 'blank_contribution', label: 'BLANK_CONTRIBUTION', type: 'number', step: 0.01, min: 0 },
])

const bFactorFields = computed(() => [
  { key: 'b_factor_default', label: 'B_FACTOR_DEFAULT', type: 'number', step: 0.01, min: 0 },
  { key: 'b_factor_file', label: 'B_FACTOR_FILE', type: 'text', placeholder: 'e.g. B_out.txt (empty = default B)',
    help: t('cp2k.helps.bFactorFile') },
  { key: 'n_b_factor', label: 'N_B_FACTOR', type: 'number', step: 1, min: 0 },
])

const overrideFlagFields = computed(() => [
  { key: 'emit_overrides', label: t('cp2k.fields.emitOverrides'), type: 'checkbox',
    help: t('cp2k.helps.overrides') },
])

const overrideFields = computed(() => [
  { key: 'atomic_factor_file', label: 'ATOMIC_FACTOR_FILE', type: 'text',
    placeholder: 'e.g. ATOMIC_FACTOR_PARAMETERS.txt (empty = xraylib FF_Rayl)',
    help: t('cp2k.helps.atomicFactor') },
  { key: 'reflection_file', label: 'REFLECTION_FILE', type: 'text',
    placeholder: 'e.g. cp2kfiber_reflections.txt (empty = on-the-fly)' },
  { key: 'peak_result_file', label: 'PEAK_RESULT_FILE', type: 'text' },
])

// ---- Actions ----

async function generatePreview() {
  taskStatus.value = 'running'
  generating.value = true
  consoleLogs.length = 0
  consoleLogs.push(t('cp2k.logs.generating'))
  try {
    const res = await cp2kGenerate(buildRequest())
    previewText.value = typeof res.data === 'string' ? res.data : JSON.stringify(res.data)
    consoleLogs.push(t('cp2k.logs.generated'))
    taskStatus.value = 'completed'
  } catch (err) {
    consoleLogs.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'failed'
  } finally {
    generating.value = false
  }
}

function buildRequest() {
  const p = params
  return {
    enabled: p.enabled,
    diffraction_file: p.diffraction_file,
    wavelength: p.wavelength,
    auto_scale: p.auto_scale,
    scale_factor: p.scale_factor,
    lambda: p.lambda,
    sample_thickness_cm: p.sample_thickness_cm,
    detector_distance_cm: p.detector_distance_cm,
    xray_mode: p.xray_mode,
    h_max: p.h_max,
    k_max: p.k_max,
    l_max: p.l_max,
    q_min: p.q_min,
    max_hkl_per_peak: p.max_hkl_per_peak,
    max_blank_hkl: p.max_blank_hkl,
    blank_contribution: p.blank_contribution,
    b_factor_default: p.b_factor_default,
    b_factor_file: p.b_factor_file,
    n_b_factor: p.n_b_factor,
    atomic_factor_file: p.atomic_factor_file,
    reflection_file: p.reflection_file,
    peak_result_file: p.peak_result_file,
    emit_common_optional: p.emit_common_optional,
    emit_b_factor: p.emit_b_factor,
    emit_overrides: p.emit_overrides,
  }
}

function downloadSection() {
  if (!previewText.value) return
  const blob = new Blob([previewText.value], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'fiber_diffraction.inc'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.cp2k-page { display: flex; flex-direction: column; }

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

/* ---- Actions ---- */
.actions-row { display: flex; gap: 12px; margin-top: 8px; }

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
