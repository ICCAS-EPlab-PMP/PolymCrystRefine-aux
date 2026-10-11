<template>
  <div class="cif-page">
    <div class="card">
      <h2 class="card-title">{{ t('cif.title') }}</h2>
      <p class="card-desc">{{ t('cif.desc') }}</p>

      <FileUpload
        accept=".cif,.cif.gz"
        :multiple="false"
        :label="t('cif.uploadLabel')"
        @files-selected="onFilesSelected"
      />

      <ParamsForm
        :fields="paramFields"
        :modelValue="cifParams"
        @update:modelValue="v => Object.assign(cifParams, v)"
        style="margin-top: 16px"
      />

      <button
        class="btn-primary"
        style="margin-top: 16px"
        :disabled="!canParse"
        @click="runParse"
      >
        {{ runStatus === 'running' ? t('cif.parsing') : t('cif.btnParse') }}
      </button>

      <ConsolePanel
        v-if="consoleLogs.length || taskStatus !== 'idle'"
        :status="taskStatus"
        :logs="consoleLogs"
        style="margin-top: 16px"
      />

      <div v-if="peaks.length" class="result-preview" style="margin-top: 20px">
        <div class="result-head">
          <h3 class="result-title">{{ t('cif.resultTitle') }} ({{ peaks.length }})</h3>
          <button class="btn-compact" @click="downloadPeakResult">
            {{ t('cif.downloadPeakResult') }}
          </button>
        </div>
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>{{ t('cif.cols.h') }}</th>
                <th>{{ t('cif.cols.k') }}</th>
                <th>{{ t('cif.cols.l') }}</th>
                <th>{{ t('cif.cols.q') }}</th>
                <th>{{ t('cif.cols.psi') }}</th>
                <th>{{ t('cif.cols.intensity') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(p, i) in peaks" :key="i">
                <td class="text-mono">{{ p.h }}</td>
                <td class="text-mono">{{ p.k }}</td>
                <td class="text-mono">{{ p.l }}</td>
                <td class="text-mono">{{ fmt(p.q, 4) }}</td>
                <td class="text-mono">{{ fmt(p.chi, 2) }}</td>
                <td class="text-mono">{{ fmt(p.intensity, 2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import FileUpload from '@/components/FileUpload.vue'
import ParamsForm from '@/components/ParamsForm.vue'
import ConsolePanel from '@/components/ConsolePanel.vue'
import { xrdGeneratePeaks } from '@/api/index.js'

const { t } = useI18n()

const cifFiles = ref([])
const cifParams = reactive({
  wavelength: 1.5406,
  xrayMode: 'synchrotron',
  maxQ: null,          // empty = no limit
  maxH: null,          // empty = no limit
  maxK: null,          // empty = no limit
  maxL: null,          // empty = no limit
  minIntensity: 0.0001,
  sortBy: 'intensity', // intensity | l | none
})
const runStatus = ref('idle')        // idle | running | completed | failed
const taskStatus = ref('idle')
const consoleLogs = ref([])
const peaks = ref([])

const paramFields = computed(() => [
  { key: 'wavelength', label: t('cif.wavelength'), type: 'number', step: 0.0001, min: 0 },
  {
    key: 'xrayMode', label: t('cif.xrayMode'), type: 'select', options: [
      { value: 'synchrotron', label: t('cif.xrayModeOptions.synchrotron') },
      { value: 'laboratory', label: t('cif.xrayModeOptions.laboratory') },
    ],
  },
  { key: 'maxQ', label: t('cif.maxQ'), type: 'number', step: 0.01, min: 0, placeholder: t('cif.noLimit'), help: t('cif.maxQHelp') },
  { key: 'maxH', label: t('cif.maxH'), type: 'number', step: 1, min: 0, placeholder: t('cif.noLimit') },
  { key: 'maxK', label: t('cif.maxK'), type: 'number', step: 1, min: 0, placeholder: t('cif.noLimit') },
  { key: 'maxL', label: t('cif.maxL'), type: 'number', step: 1, min: 0, placeholder: t('cif.noLimit') },
  { key: 'minIntensity', label: t('cif.minIntensity'), type: 'number', step: 0.0001, min: 0 },
  {
    key: 'sortBy', label: t('cif.sortBy'), type: 'select', options: [
      { value: 'intensity', label: t('cif.sortOptions.intensity') },
      { value: 'l', label: t('cif.sortOptions.l') },
      { value: 'none', label: t('cif.sortOptions.none') },
    ],
  },
])

const canParse = computed(() => cifFiles.value.length > 0 && runStatus.value !== 'running')

function onFilesSelected(files) {
  cifFiles.value = files
}

const fmt = (v, d) => (typeof v === 'number' && isFinite(v) ? v.toFixed(d) : '—')

// ParamsForm emits NaN when a number input is cleared; normalize to null
// so the backend treats the filter as "not set".
const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

// 兜底：hkl 限制按「绝对值」判断（与后端 /generate-peaks 的语义一致）：
//   设置了 maxH/maxK/maxL 时，只保留 |h| ≤ maxH、|k| ≤ maxK、|l| ≤ maxL 的峰。
// 这样即使后端是旧版本（曾用带符号比较导致 |hkl| 超限的负数混入），
// 结果表与导出的 peak_result.txt 也绝不会出现超出限制的峰。
function enforceHklLimits(peaks, params) {
  const maxH = num(params.maxH)
  const maxK = num(params.maxK)
  const maxL = num(params.maxL)
  if (maxH == null && maxK == null && maxL == null) return peaks
  return peaks.filter((pk) => {
    if (maxH != null && Math.abs(pk.h) > maxH) return false
    if (maxK != null && Math.abs(pk.k) > maxK) return false
    if (maxL != null && Math.abs(pk.l) > maxL) return false
    return true
  })
}

// Sort the peak list for both the table and the exported txt.
const sortPeaks = (list, mode) => {
  const arr = [...list]
  if (mode === 'intensity') {
    arr.sort((a, b) => (b.intensity - a.intensity) || (a.q - b.q))
  } else if (mode === 'l') {
    arr.sort((a, b) => (a.l - b.l) || (b.intensity - a.intensity) || (a.q - b.q))
  }
  return arr
}

// Re-sort the current result when the user switches the sort mode.
watch(() => cifParams.sortBy, (mode) => {
  if (peaks.value.length) peaks.value = sortPeaks(peaks.value, mode)
})

async function runParse() {
  if (!cifFiles.value.length) return
  runStatus.value = 'running'
  taskStatus.value = 'running'
  consoleLogs.value = [t('logs.cif.readingCif')]
  try {
    const cifContent = await cifFiles.value[0].text()
    consoleLogs.value.push(t('logs.cif.generatingPeaks'))
    const res = await xrdGeneratePeaks({
      cifContent,
      wavelength: cifParams.wavelength,
      xrayMode: cifParams.xrayMode,
      maxQ: num(cifParams.maxQ),
      maxH: num(cifParams.maxH),
      maxK: num(cifParams.maxK),
      maxL: num(cifParams.maxL),
      minIntensity: num(cifParams.minIntensity),
    })
    const rawPeaks = res.data?.peaks || []
    // 前端兜底：无论后端版本新旧，一律按 |hkl| 绝对值限制过滤后再展示/导出。
    const enforcedPeaks = enforceHklLimits(rawPeaks, cifParams)
    const dropped = rawPeaks.length - enforcedPeaks.length
    if (dropped > 0) {
      consoleLogs.value.push(t('logs.cif.hklLimitDropped', { count: dropped }))
    }
    peaks.value = sortPeaks(enforcedPeaks, cifParams.sortBy)
    const filters = []
    if (num(cifParams.maxQ) != null) filters.push(`${t('cif.maxQ')} ≤ ${cifParams.maxQ}`)
    if (num(cifParams.maxH) != null) filters.push(`|h| ≤ ${cifParams.maxH}`)
    if (num(cifParams.maxK) != null) filters.push(`|k| ≤ ${cifParams.maxK}`)
    if (num(cifParams.maxL) != null) filters.push(`|l| ≤ ${cifParams.maxL}`)
    if (num(cifParams.minIntensity) != null) filters.push(`${t('cif.minIntensity')} > ${cifParams.minIntensity}`)
    if (filters.length) consoleLogs.value.push(t('logs.cif.filtersApplied', { filters: filters.join('，') }))
    consoleLogs.value.push(t('logs.cif.peaksGenerated', { count: peaks.value.length }))
    taskStatus.value = 'completed'
    runStatus.value = 'completed'
  } catch (err) {
    consoleLogs.value.push(t('logs.common.error', { message: err.response?.data?.detail || err.message }))
    taskStatus.value = 'error'
    runStatus.value = 'failed'
  }
}

// Export the generated peaks as a 7-column peak_result.txt
// (h k l q psi intensity belongto) — the fiber peak-list format the
// diffraction simulator imports.
function downloadPeakResult() {
  if (!peaks.value.length) return
  const header = 'h k l q psi intensity belongto'
  const rows = peaks.value.map(p =>
    `${p.h} ${p.k} ${p.l} ${fmt(p.q, 6)} ${fmt(p.chi, 4)} ${fmt(p.intensity, 6)} sim`
  )
  const text = [header, ...rows].join('\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'peak_result.txt'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  consoleLogs.value.push(t('logs.cif.peaksDownloaded', { count: peaks.value.length }))
}
</script>

<style scoped>
.cif-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-title {
  margin: 0 0 8px;
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--color-text, var(--text-primary));
}

.card-desc {
  margin: 0 0 16px;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--color-text-secondary, var(--text-secondary));
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.result-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text, var(--text-primary));
}

.table-wrapper {
  max-height: 420px;
  overflow: auto;
  border: 1px solid var(--color-border, var(--border));
  border-radius: 8px;
}
</style>
