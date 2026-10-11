<template>
  <div class="console-panel">
    <div class="console-panel__header">
      <div class="console-panel__status">
        <span class="console-panel__dot" :class="`console-panel__dot--${status}`"></span>
        <span class="console-panel__status-text">{{ t(`common.${status}`) }}</span>
      </div>

      <div v-if="status === 'running' && progress != null" class="console-panel__progress-wrap">
        <div class="console-panel__progress">
          <div class="console-panel__progress-bar" :style="{ width: `${clampedProgress}%` }"></div>
        </div>
        <span class="console-panel__progress-text">{{ Math.round(clampedProgress) }}%</span>
      </div>

      <button
        v-if="status === 'running'"
        class="console-panel__cancel"
        @click="emit('cancel')"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        {{ t('common.cancel') }}
      </button>
    </div>

    <div ref="logArea" class="console-panel__logs">
      <div v-if="logs.length === 0" class="console-panel__empty">
        {{ t('components.console.waiting') }}
      </div>
      <div
        v-for="(line, i) in logs"
        :key="i"
        class="console-panel__line"
        :class="{
          'console-panel__line--error': /\b(error|err|fail|fatal)\b/i.test(line),
          'console-panel__line--warn': /\b(warn|warning)\b/i.test(line)
        }"
      >{{ line }}</div>
    </div>

    <div class="console-panel__footer">
      <span v-if="startTime" class="console-panel__time">
        {{ t('components.console.started') }} {{ formatTime(startTime) }}
      </span>
      <span v-if="endTime" class="console-panel__time">
        {{ t('components.console.ended') }} {{ formatTime(endTime) }}
      </span>
      <span v-if="elapsedDisplay" class="console-panel__time console-panel__time--elapsed">
        {{ t('components.console.duration') }} {{ elapsedDisplay }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  status: {
    type: String,
    default: 'idle',
    validator: (v) => ['idle', 'running', 'completed', 'error'].includes(v)
  },
  logs: {
    type: Array,
    default: () => []
  },
  progress: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['cancel'])

const logArea = ref(null)
const startTime = ref(null)
const endTime = ref(null)
const elapsed = ref(0)
let elapsedTimer = null

const clampedProgress = computed(() => {
  if (props.progress == null) return 0
  return Math.min(100, Math.max(0, props.progress))
})

const elapsedDisplay = computed(() => {
  const ms = elapsed.value
  if (ms < 1000) return `${ms}ms`
  const sec = Math.floor(ms / 1000)
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  const remSec = sec % 60
  return `${min}m ${remSec}s`
})

function formatTime(ts) {
  return ts.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function startElapsedTimer() {
  stopElapsedTimer()
  elapsedTimer = setInterval(() => {
    if (startTime.value) {
      elapsed.value = Date.now() - startTime.value.getTime()
    }
  }, 1000)
}

function stopElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (logArea.value) {
      logArea.value.scrollTop = logArea.value.scrollHeight
    }
  })
}

watch(() => props.status, (newStatus) => {
  if (newStatus === 'running') {
    startTime.value = new Date()
    endTime.value = null
    elapsed.value = 0
    startElapsedTimer()
  } else if (newStatus === 'completed' || newStatus === 'error') {
    endTime.value = new Date()
    if (startTime.value) {
      elapsed.value = endTime.value.getTime() - startTime.value.getTime()
    }
    stopElapsedTimer()
  }
}, { immediate: false })

watch(() => props.logs.length, () => {
  scrollToBottom()
})

onMounted(() => {
  if (props.status === 'running') {
    startTime.value = new Date()
    startElapsedTimer()
  }
})

onBeforeUnmount(() => {
  stopElapsedTimer()
})
</script>

<style scoped>
.console-panel {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg);
  overflow: hidden;
}

.console-panel__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  flex-wrap: wrap;
}

.console-panel__status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.console-panel__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.console-panel__dot--idle {
  background: var(--text-secondary);
}

.console-panel__dot--running {
  background: var(--color-warning);
  animation: pulse-dot 1.5s ease-in-out infinite;
}

.console-panel__dot--completed {
  background: var(--color-success);
}

.console-panel__dot--error {
  background: var(--color-error);
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.console-panel__status-text {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
}

.console-panel__progress-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 100px;
}

.console-panel__progress {
  flex: 1;
  height: 3px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}

.console-panel__progress-bar {
  height: 100%;
  background: var(--color-primary);
  border-radius: 2px;
  transition: width 300ms ease;
}

.console-panel__progress-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--color-text-secondary);
  min-width: 36px;
  text-align: right;
}

.console-panel__cancel {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 150ms ease, color 150ms ease, background-color 150ms ease;
}

.console-panel__cancel:hover {
  border-color: var(--color-error);
  color: var(--color-error);
  background: rgba(235, 87, 87, 0.15);
}

.console-panel__logs {
  max-height: 400px;
  overflow-y: auto;
  padding: 12px 14px;
  font-family: 'JetBrains Mono', var(--font-mono, monospace);
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-text);
  background: var(--color-bg);
}

.console-panel__logs::-webkit-scrollbar {
  width: 6px;
}

.console-panel__logs::-webkit-scrollbar-track {
  background: transparent;
}

.console-panel__logs::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}

.console-panel__empty {
  color: var(--color-text-secondary);
  font-style: italic;
  padding: 8px 0;
}

.console-panel__line {
  white-space: pre-wrap;
  word-break: break-all;
}

.console-panel__line--error {
  color: var(--color-error);
}

.console-panel__line--warn {
  color: var(--color-warning);
}

.console-panel__footer {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 14px;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  flex-wrap: wrap;
}

.console-panel__time {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.console-panel__time--elapsed {
  color: var(--color-primary);
}
</style>
