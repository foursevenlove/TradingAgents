<template>
  <div>
    <label class="block text-sm font-medium text-gray-700 mb-1">股票代码</label>
    <div class="relative">
      <input
        v-model="inputValue"
        @input="onInput"
        @keyup.enter="selectFirstResult"
        @blur="onBlur"
        type="text"
        placeholder="输入股票代码或名称搜索..."
        class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        :class="error ? 'border-red-300' : 'border-gray-300'"
      />
      <!-- Loading indicator -->
      <div v-if="searching" class="absolute right-3 top-2.5">
        <div class="w-4 h-4 border-2 border-primary-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
      <!-- Selected stock badge -->
      <div v-if="selectedStock && !inputValue" class="absolute right-3 top-2.5">
        <span class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
          {{ selectedStock.ticker }}
        </span>
      </div>
    </div>
    <!-- Search results dropdown -->
    <div
      v-if="searchResults.length > 0"
      class="relative z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
    >
      <div
        v-for="stock in searchResults"
        :key="stock.ticker"
        @click="selectStock(stock)"
        @mousedown.prevent
        class="px-3 py-2 hover:bg-gray-50 cursor-pointer flex items-center gap-3"
      >
        <span class="font-mono text-sm text-gray-900">{{ stock.ticker }}</span>
        <span class="text-sm text-gray-600">{{ stock.name }}</span>
      </div>
    </div>
    <p v-if="error" class="mt-1 text-sm text-red-600">{{ error }}</p>
    <p v-else class="mt-1 text-xs text-gray-400">输入股票代码或名称，从搜索结果中选择</p>
  </div>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { api } from '../api.js'

const props = defineProps({
  modelValue: String,
  error: String,
})

const emit = defineEmits(['update:modelValue'])

const inputValue = ref(props.modelValue || '')
const searchResults = ref([])
const selectedStock = ref(null)
const searching = ref(false)
let searchTimeout = null

// Sync input with modelValue
watch(() => props.modelValue, (val) => {
  if (val !== inputValue.value) {
    inputValue.value = val || ''
  }
})

// Update modelValue when input changes
watch(inputValue, (val) => {
  emit('update:modelValue', val)
})

async function onInput() {
  // Clear selection when user types
  if (selectedStock.value) {
    selectedStock.value = null
  }

  // Debounce search
  if (searchTimeout) clearTimeout(searchTimeout)

  if (!inputValue.value.trim()) {
    searchResults.value = []
    return
  }

  searching.value = true
  searchTimeout = setTimeout(async () => {
    try {
      const results = await api.searchStocks(inputValue.value.trim())
      searchResults.value = results
    } catch (err) {
      console.error('Search failed:', err)
      searchResults.value = []
    } finally {
      searching.value = false
    }
  }, 300)
}

function selectStock(stock) {
  selectedStock.value = stock
  inputValue.value = stock.ticker
  searchResults.value = []
  emit('update:modelValue', stock.ticker)
}

function selectFirstResult() {
  if (searchResults.value.length > 0) {
    selectStock(searchResults.value[0])
  }
}

function onBlur() {
  // Delay to allow click on dropdown items
  setTimeout(() => {
    searchResults.value = []
  }, 200)
}

onUnmounted(() => {
  if (searchTimeout) clearTimeout(searchTimeout)
})
</script>
