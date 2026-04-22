<template>
  <div>
    <label class="block text-sm font-medium text-gray-700 mb-1">股票代码</label>
    <div class="relative">
      <input
        :value="modelValue"
        @input="$emit('update:modelValue', $event.target.value)"
        type="text"
        placeholder="如 600000.SH 或 000001.SZ"
        class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        :class="error ? 'border-red-300' : 'border-gray-300'"
      />
      <div v-if="modelValue" class="absolute right-3 top-2.5">
        <span
          class="text-xs px-2 py-0.5 rounded-full"
          :class="isValid ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'"
        >
          {{ isValid ? '格式正确' : '格式建议: XXXXXX.SH/SZ' }}
        </span>
      </div>
    </div>
    <p v-if="error" class="mt-1 text-sm text-red-600">{{ error }}</p>
    <p v-else class="mt-1 text-xs text-gray-400">支持 A 股代码格式，如 600000.SH、000001.SZ</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: String,
  error: String,
})

defineEmits(['update:modelValue'])

const isValid = computed(() => {
  const v = props.modelValue?.trim()
  if (!v) return false
  return /^\d{6}\.(SH|SZ|sh|sz)$/.test(v)
})
</script>
