<template>
  <div class="file-upload">
    <div
      class="drop-zone"
      :class="{ 'drop-zone--active': isDragging, 'drop-zone--has-files': files.length > 0 }"
      @dragenter.prevent="onDragEnter"
      @dragover.prevent="onDragOver"
      @dragleave.prevent="onDragLeave"
      @drop.prevent="onDrop"
      @click="openFilePicker"
    >
      <input
        ref="fileInput"
        type="file"
        class="drop-zone__input"
        :accept="accept"
        :multiple="multiple"
        @change="onInputChange"
      />

      <svg class="drop-zone__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M12 16V4m0 0L8 8m4-4l4 4" stroke-linecap="round" stroke-linejoin="round" />
        <path d="M20 16v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>

      <p class="drop-zone__label">{{ label || t('components.fileUpload.dropHere') }}</p>
      <p class="drop-zone__hint">{{ t('components.fileUpload.browse') }}</p>
    </div>

    <ul v-if="files.length > 0" class="file-list">
      <li v-for="(file, index) in files" :key="file.name + index" class="file-list__item">
        <div class="file-list__info">
          <svg class="file-list__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M14 2v6h6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="file-list__name">{{ file.name }}</span>
          <span class="file-list__size">{{ formatSize(file.size) }}</span>
        </div>
        <button class="file-list__remove" :title="t('components.fileUpload.remove')" @click.stop="removeFile(index)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  accept: { type: String, default: '' },
  multiple: { type: Boolean, default: true },
  label: { type: String, default: '' },
  maxFiles: { type: Number, default: 50 },
  // Emit only the files of the current selection and keep no internal list.
  // Pages that maintain their own gallery (e.g. the 2D viewer) need this:
  // accumulating and re-emitting previously selected files made every later
  // add re-upload everything picked before.
  clearAfterSelect: { type: Boolean, default: false }
})

const emit = defineEmits(['files-selected', 'file-removed'])

const fileInput = ref(null)
const files = ref([])
const isDragging = ref(false)
let dragCounter = 0

function openFilePicker() {
  fileInput.value?.click()
}

function onDragEnter() {
  dragCounter++
  isDragging.value = true
}

function onDragOver() {
  isDragging.value = true
}

function onDragLeave() {
  dragCounter--
  if (dragCounter <= 0) {
    dragCounter = 0
    isDragging.value = false
  }
}

function onDrop(e) {
  isDragging.value = false
  dragCounter = 0
  const droppedFiles = Array.from(e.dataTransfer?.files || [])
  addFiles(droppedFiles)
}

function onInputChange(e) {
  const selected = Array.from(e.target.files || [])
  addFiles(selected)
  // Reset so the same file can be selected again
  if (fileInput.value) fileInput.value.value = ''
}

function addFiles(newFiles) {
  let filtered = newFiles
  if (props.accept) {
    const accepted = props.accept.split(',').map(t => t.trim().toLowerCase())
    filtered = newFiles.filter(f => {
      const ext = '.' + f.name.split('.').pop().toLowerCase()
      const mime = f.type.toLowerCase()
      return accepted.some(a => ext === a || mime === a || (a.endsWith('/*') && mime.startsWith(a.replace('/*', '/'))))
    })
  }

  const remaining = props.maxFiles - files.value.length
  if (remaining <= 0 && !props.clearAfterSelect) return
  const toAdd = props.multiple ? filtered.slice(0, remaining) : filtered.slice(0, 1)

  if (props.clearAfterSelect) {
    // Fire-and-forget mode: no internal accumulation, so nothing is ever
    // re-emitted (and the maxFiles quota cannot fill up either).
    emit('files-selected', toAdd)
    return
  }

  if (!props.multiple && toAdd.length > 0) {
    files.value = [toAdd[0]]
  } else {
    files.value = [...files.value, ...toAdd]
  }

  emit('files-selected', files.value)
}

function removeFile(index) {
  files.value.splice(index, 1)
  emit('file-removed', index)
  emit('files-selected', files.value)
}

function formatSize(bytes) {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i]
}
</script>

<style scoped>
.file-upload {
  width: 100%;
}

.drop-zone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-md, 8px);
  background: var(--color-surface);
  cursor: pointer;
  transition: border-color 150ms ease, background-color 150ms ease;
  padding: 24px 16px;
}

.drop-zone:hover {
  border-color: var(--color-primary);
  background: var(--bg-hover);
}

.drop-zone--active {
  border-color: var(--color-primary);
  background: var(--primary-bg);
}

.drop-zone--has-files {
  border-style: solid;
}

.drop-zone__input {
  position: absolute;
  inset: 0;
  opacity: 0;
  pointer-events: none;
  width: 0;
  height: 0;
}

.drop-zone__icon {
  width: 32px;
  height: 32px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
  transition: color 150ms ease;
}

.drop-zone:hover .drop-zone__icon,
.drop-zone--active .drop-zone__icon {
  color: var(--color-primary);
}

.drop-zone__label {
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  color: var(--color-text);
  margin: 0;
}

.drop-zone__hint {
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 4px 0 0;
}

.file-list {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  transition: background-color 150ms ease;
}

.file-list__item:hover {
  background: var(--color-surface-hover);
}

.file-list__info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.file-list__icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  color: var(--color-text-secondary);
}

.file-list__name {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1 1 auto;
  min-width: 0;
}

.file-list__size {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.file-list__remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-radius: 4px;
  transition: color 150ms ease, background-color 150ms ease;
  flex-shrink: 0;
}

.file-list__remove:hover {
  color: var(--color-error);
  background: rgba(235, 87, 87, 0.15);
}

.file-list__remove svg {
  width: 14px;
  height: 14px;
}
</style>
