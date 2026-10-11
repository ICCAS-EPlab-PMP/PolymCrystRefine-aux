<template>
  <div class="plot-viewer">
    <div class="plot-viewer__toolbar">
      <span v-if="title" class="plot-viewer__title">{{ title }}</span>
      <div class="plot-viewer__actions">
        <button class="plot-viewer__btn" @click="downloadPNG" :title="t('components.plotViewer.downloadPng')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16">
            <path d="M12 4v12m0 0l-4-4m4 4l4-4" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M20 16v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          {{ t('components.plotViewer.png') }}
        </button>
        <button class="plot-viewer__btn" @click="resetZoom" :title="t('components.plotViewer.resetView')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16">
            <path d="M3 10h4V6M21 14h-4v4M15 3l-6 6M9 21l6-6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          {{ t('components.plotViewer.reset') }}
        </button>
      </div>
    </div>
    <div ref="plotContainer" class="plot-viewer__plot"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import Plotly from 'plotly.js-dist-min'

const { t } = useI18n()

const props = defineProps({
  traces: {
    type: Array,
    default: () => []
    // Each: { x, y, name, mode }
  },
  layout: {
    type: Object,
    default: () => ({})
  },
  title: {
    type: String,
    default: ''
  }
})

const plotContainer = ref(null)

const defaultDarkLayout = {
  paper_bgcolor: '#FFFFFF',
  plot_bgcolor: '#FFFFFF',
  font: { color: '#262432', family: 'Inter, sans-serif', size: 12 },
  margin: { t: 40, r: 20, b: 50, l: 60 },
  xaxis: {
    gridcolor: '#E3E0EF',
    zerolinecolor: '#E3E0EF',
    tickfont: { family: 'JetBrains Mono, monospace', size: 11, color: '#5A5767' }
  },
  yaxis: {
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

  const plotTraces = props.traces.map(t => ({
    x: t.x,
    y: t.y,
    name: t.name || '',
    mode: t.mode || 'lines+markers',
    type: 'scatter',
    line: { color: t.color || undefined, width: 2 },
    marker: { size: 5 }
  }))

  const mergedLayout = {
    ...defaultDarkLayout,
    ...props.layout,
    title: props.title || undefined,
    xaxis: { ...defaultDarkLayout.xaxis, ...(props.layout.xaxis || {}) },
    yaxis: { ...defaultDarkLayout.yaxis, ...(props.layout.yaxis || {}) },
    legend: { ...defaultDarkLayout.legend, ...(props.layout.legend || {}) }
  }

  Plotly.newPlot(plotContainer.value, plotTraces, mergedLayout, {
    responsive: true,
    displayModeBar: false
  })
}

function downloadPNG() {
  if (!plotContainer.value) return
  Plotly.downloadImage(plotContainer.value, {
    format: 'png',
    width: 1200,
    height: 800,
    filename: props.title || 'plot'
  })
}

function resetZoom() {
  if (!plotContainer.value) return
  Plotly.relayout(plotContainer.value, {
    'xaxis.autorange': true,
    'yaxis.autorange': true
  })
}

watch(
  () => [props.traces, props.layout, props.title],
  () => { renderPlot() },
  { deep: true }
)

onMounted(() => { renderPlot() })

onBeforeUnmount(() => {
  if (plotContainer.value) {
    Plotly.purge(plotContainer.value)
  }
})
</script>

<style scoped>
.plot-viewer {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.plot-viewer__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
}

.plot-viewer__title {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
}

.plot-viewer__actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.plot-viewer__btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 150ms ease, color 150ms ease, background-color 150ms ease;
}

.plot-viewer__btn:hover {
  border-color: var(--color-primary);
  color: var(--color-text);
  background: var(--bg-hover);
}

.plot-viewer__plot {
  width: 100%;
  min-height: 300px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
  background: var(--color-bg);
}
</style>
