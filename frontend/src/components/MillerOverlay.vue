<template>
  <div class="miller-overlay">
    <div class="miller-overlay__controls">
      <div class="miller-overlay__datasets">
        <h4 class="miller-overlay__section-title">{{ t('components.miller.datasets') }}</h4>
        <div
          v-for="(ds, i) in datasets"
          :key="i"
          class="miller-overlay__dataset"
        >
          <span class="miller-overlay__color-dot" :style="{ background: ds.color || defaultColors[i % defaultColors.length] }"></span>
          <span class="miller-overlay__dataset-name">{{ ds.name }}</span>
          <span class="miller-overlay__dataset-count">{{ ds.points?.length || 0 }} {{ t('components.miller.points') }}</span>
        </div>
      </div>

      <div class="miller-overlay__options">
        <div class="miller-overlay__option-row">
          <label class="miller-overlay__label">{{ t('components.miller.convention') }}</label>
          <button
            class="miller-overlay__toggle-btn"
            :class="{ 'miller-overlay__toggle-btn--active': localConvention === 'CCW' }"
            @click="setConvention('CCW')"
          >CCW</button>
          <button
            class="miller-overlay__toggle-btn"
            :class="{ 'miller-overlay__toggle-btn--active': localConvention === 'CW' }"
            @click="setConvention('CW')"
          >CW</button>
        </div>

        <div class="miller-overlay__option-row">
          <label class="miller-overlay__label" for="azimuth-offset">{{ t('components.miller.azimuthOffset') }}</label>
          <input
            id="azimuth-offset"
            type="number"
            class="miller-overlay__input"
            v-model.number="localOffset"
            step="1"
            min="-360"
            max="360"
          />
          <span class="miller-overlay__unit">&deg;</span>
        </div>
      </div>
    </div>

    <div ref="plotContainer" class="miller-overlay__plot"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Plotly from 'plotly.js-dist-min'

const { t } = useI18n()

const props = defineProps({
  datasets: {
    type: Array,
    default: () => []
    // Each: { name, points: [{h, k, l, q, psi}], color }
  },
  convention: {
    type: String,
    default: 'CCW',
    validator: (v) => ['CCW', 'CW'].includes(v)
  },
  azimuthOffset: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['point-clicked'])

const plotContainer = ref(null)
const localConvention = ref(props.convention)
const localOffset = ref(props.azimuthOffset)

const defaultColors = [
  '#7C3AED', '#E5484D', '#22C55E', '#F59E0B',
  '#06B6D4', '#A855F7', '#EC4899', '#14B8A6'
]

function setConvention(c) {
  localConvention.value = c
}

function transformPsi(psi) {
  let val = psi
  if (localConvention.value === 'CW') {
    val = -val
  }
  val = val + localOffset.value
  // Normalize to [0, 360)
  val = ((val % 360) + 360) % 360
  return val
}

const darkLayout = {
  paper_bgcolor: '#FFFFFF',
  plot_bgcolor: '#FFFFFF',
  font: { color: '#262432', family: 'Inter, sans-serif', size: 12 },
  margin: { t: 40, r: 20, b: 50, l: 60 },
  xaxis: {
    title: { text: 'q', font: { size: 13 } },
    gridcolor: '#E3E0EF',
    zerolinecolor: '#E3E0EF',
    tickfont: { family: 'JetBrains Mono, monospace', size: 11, color: '#5A5767' }
  },
  yaxis: {
    title: { text: 'psi (deg)', font: { size: 13 } },
    gridcolor: '#E3E0EF',
    zerolinecolor: '#E3E0EF',
    tickfont: { family: 'JetBrains Mono, monospace', size: 11, color: '#5A5767' }
  },
  legend: {
    bgcolor: 'rgba(255, 255, 255, 0.95)',
    bordercolor: '#E3E0EF',
    borderwidth: 1,
    font: { color: '#262432', size: 11 }
  },
  hoverlabel: {
    bgcolor: '#FFFFFF',
    bordercolor: '#7C3AED',
    font: { color: '#262432', family: 'JetBrains Mono, monospace', size: 12 }
  }
}

function renderPlot() {
  if (!plotContainer.value) return

  const traces = props.datasets.map((ds, i) => {
    const color = ds.color || defaultColors[i % defaultColors.length]
    const points = ds.points || []
    const qValues = points.map(p => p.q)
    const psiValues = points.map(p => transformPsi(p.psi))
    const hoverTexts = points.map(p =>
      `(${p.h}, ${p.k}, ${p.l})<br>q: ${p.q?.toFixed(4)}<br>psi: ${transformPsi(p.psi).toFixed(2)}`
    )

    return {
      x: qValues,
      y: psiValues,
      text: hoverTexts,
      hoverinfo: 'text',
      mode: 'markers',
      type: 'scatter',
      name: `${ds.name} (${points.length})`,
      marker: {
        color,
        size: 7,
        opacity: 0.85,
        line: { color: '#FFFFFF', width: 1 }
      },
      // Store raw point data for click events
      _rawPoints: points
    }
  })

  Plotly.newPlot(plotContainer.value, traces, { ...darkLayout }, {
    responsive: true,
    displayModeBar: false
  })

  // Bind click event
  plotContainer.value.on('plotly_click', (data) => {
    if (data?.points?.length > 0) {
      const clickedPt = data.points[0]
      const traceIdx = clickedPt.curveNumber
      const pointIdx = clickedPt.pointNumber
      const rawPoint = props.datasets[traceIdx]?.points?.[pointIdx]
      if (rawPoint) {
        emit('point-clicked', {
          ...rawPoint,
          psiTransformed: transformPsi(rawPoint.psi),
          datasetName: props.datasets[traceIdx]?.name
        })
      }
    }
  })
}

watch(
  () => [props.datasets, localConvention.value, localOffset.value],
  () => { renderPlot() },
  { deep: true }
)

watch(() => props.convention, (v) => { localConvention.value = v })
watch(() => props.azimuthOffset, (v) => { localOffset.value = v })

onMounted(() => { renderPlot() })

onBeforeUnmount(() => {
  if (plotContainer.value) {
    Plotly.purge(plotContainer.value)
  }
})
</script>

<style scoped>
.miller-overlay {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.miller-overlay__controls {
  display: flex;
  gap: 16px;
  padding: 12px 14px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  flex-wrap: wrap;
}

.miller-overlay__datasets {
  flex: 1;
  min-width: 160px;
}

.miller-overlay__section-title {
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-secondary);
  margin: 0 0 8px;
}

.miller-overlay__dataset {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.miller-overlay__color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1);
}

.miller-overlay__dataset-name {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  color: var(--color-text);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.miller-overlay__dataset-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.miller-overlay__options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 180px;
}

.miller-overlay__option-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.miller-overlay__label {
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  color: var(--color-text-secondary);
  min-width: 90px;
}

.miller-overlay__toggle-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 150ms ease, color 150ms ease, background-color 150ms ease;
}

.miller-overlay__toggle-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-text);
}

.miller-overlay__toggle-btn--active {
  border-color: var(--color-primary);
  background: var(--bg-hover);
  color: var(--color-primary);
}

.miller-overlay__input {
  width: 70px;
  padding: 4px 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--color-text);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  outline: none;
  transition: border-color 150ms ease;
  box-sizing: border-box;
}

.miller-overlay__input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.2);
}

.miller-overlay__unit {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.miller-overlay__plot {
  width: 100%;
  min-height: 350px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
  background: var(--color-bg);
}
</style>
