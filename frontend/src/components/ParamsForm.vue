<template>
  <div class="params-form">
    <div v-for="field in fields" :key="field.key" class="params-form__row">
      <label class="params-form__label" :for="`field-${field.key}`">
        {{ field.label }}
      </label>

      <div class="params-form__control">
        <!-- Number input -->
        <input
          v-if="field.type === 'number'"
          :id="`field-${field.key}`"
          type="number"
          class="params-form__input"
          :value="formValues[field.key]"
          :min="field.min"
          :max="field.max"
          :step="field.step ?? 1"
          :placeholder="field.placeholder"
          @input="onNumberInput(field.key, $event.target.value)"
        />

        <!-- Text input -->
        <input
          v-else-if="field.type === 'text'"
          :id="`field-${field.key}`"
          type="text"
          class="params-form__input"
          :value="formValues[field.key]"
          :placeholder="field.placeholder"
          @input="updateField(field.key, $event.target.value)"
        />

        <!-- Select -->
        <select
          v-else-if="field.type === 'select'"
          :id="`field-${field.key}`"
          class="params-form__select"
          :value="formValues[field.key]"
          @change="updateField(field.key, $event.target.value)"
        >
          <option v-if="field.placeholder" value="" disabled>{{ field.placeholder }}</option>
          <option
            v-for="opt in field.options"
            :key="typeof opt === 'object' ? opt.value : opt"
            :value="typeof opt === 'object' ? opt.value : opt"
          >
            {{ typeof opt === 'object' ? opt.label : opt }}
          </option>
        </select>

        <!-- Checkbox (toggle) -->
        <label
          v-else-if="field.type === 'checkbox'"
          class="params-form__toggle"
          :class="{ 'params-form__toggle--on': formValues[field.key] }"
        >
          <input
            type="checkbox"
            class="params-form__toggle-input"
            :checked="formValues[field.key]"
            @change="updateField(field.key, $event.target.checked)"
          />
          <span class="params-form__toggle-track">
            <span class="params-form__toggle-thumb"></span>
          </span>
        </label>

        <!-- Slider -->
        <div v-else-if="field.type === 'slider'" class="params-form__slider-wrap">
          <input
            :id="`field-${field.key}`"
            type="range"
            class="params-form__slider"
            :value="formValues[field.key] ?? field.min ?? 0"
            :min="field.min ?? 0"
            :max="field.max ?? 100"
            :step="field.step ?? 1"
            @input="onNumberInput(field.key, $event.target.value)"
          />
          <span class="params-form__slider-value">{{ formValues[field.key] ?? field.min ?? 0 }}</span>
        </div>
      </div>

      <p v-if="field.help" class="params-form__help">{{ field.help }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  fields: {
    type: Array,
    required: true,
    // Each: { key, label, type, options?, min?, max?, step?, placeholder?, help? }
  },
  modelValue: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:modelValue'])

const formValues = computed(() => props.modelValue)

function updateField(key, value) {
  emit('update:modelValue', { ...formValues.value, [key]: value })
}

// A cleared number input parses to NaN; store null instead so the control
// shows empty (el.value = NaN would render the literal string "NaN").
function onNumberInput(key, raw) {
  const parsed = parseFloat(raw)
  updateField(key, Number.isNaN(parsed) ? null : parsed)
}
</script>

<style scoped>
.params-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.params-form__row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.params-form__label {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
}

.params-form__control {
  width: 100%;
}

.params-form__input,
.params-form__select {
  width: 100%;
  padding: 8px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: var(--color-text);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  outline: none;
  transition: border-color 150ms ease, box-shadow 150ms ease;
  box-sizing: border-box;
}

.params-form__input:hover,
.params-form__select:hover {
  border-color: var(--border-hover);
}

.params-form__input:focus,
.params-form__select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.2);
}

.params-form__input::placeholder {
  color: var(--color-text-secondary);
  opacity: 0.6;
}

.params-form__select {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%238A8F98' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  padding-right: 30px;
}

.params-form__select option {
  background: var(--color-surface);
  color: var(--color-text);
}

/* Toggle switch */
.params-form__toggle {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.params-form__toggle-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.params-form__toggle-track {
  position: relative;
  width: 40px;
  height: 22px;
  background: var(--color-border);
  border-radius: 11px;
  transition: background-color 150ms ease;
}

.params-form__toggle--on .params-form__toggle-track {
  background: var(--color-primary);
}

.params-form__toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  background: #FFFFFF;
  border-radius: 50%;
  transition: transform 150ms ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.10);
}

.params-form__toggle--on .params-form__toggle-thumb {
  transform: translateX(18px);
}

.params-form__toggle:focus-within .params-form__toggle-track {
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.3);
}

/* Slider */
.params-form__slider-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.params-form__slider {
  flex: 1;
  height: 4px;
  appearance: none;
  background: var(--color-border);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}

.params-form__slider::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  border: 2px solid var(--color-surface);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.10);
  transition: transform 150ms ease;
}

.params-form__slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.params-form__slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  border: 2px solid var(--color-surface);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.10);
}

.params-form__slider-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--color-text);
  min-width: 40px;
  text-align: right;
}

.params-form__help {
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin: 2px 0 0;
}
</style>
