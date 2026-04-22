<template>
  <div class="max-w-3xl mx-auto px-4 py-12">
    <div class="text-center mb-10">
      <h1 class="text-4xl font-bold text-gray-900 mb-3">
        AI 驱动的股票分析
      </h1>
      <p class="text-lg text-gray-500">
        多 Agent 协作，实时流式输出，深度决策推理
      </p>
    </div>

    <div class="card space-y-6">
      <TickerInput v-model="ticker" :error="tickerError" />

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">分析日期</label>
          <input
            v-model="tradeDate"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">辩论轮数</label>
          <select v-model="debateRounds" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500">
            <option :value="1">1 轮（快速）</option>
            <option :value="3">3 轮（标准）</option>
            <option :value="5">5 轮（深度）</option>
          </select>
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">启用分析师</label>
        <div class="flex flex-wrap gap-3">
          <label
            v-for="a in analystOptions"
            :key="a.value"
            class="flex items-center gap-2 px-3 py-2 border rounded-lg cursor-pointer hover:bg-gray-50"
            :class="selectedAnalysts.includes(a.value) ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200'"
          >
            <input
              type="checkbox"
              :value="a.value"
              v-model="selectedAnalysts"
              class="rounded text-primary-600 focus:ring-primary-500"
            />
            <span class="text-sm">{{ a.label }}</span>
          </label>
        </div>
      </div>

      <div class="flex items-center justify-between pt-2">
        <button class="btn-secondary" @click="loadExample">
          填入示例
        </button>
        <button
          class="btn-primary flex items-center gap-2"
          :disabled="isLoading"
          @click="startAnalysis"
        >
          <span v-if="isLoading" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          {{ isLoading ? '启动中...' : '开始分析' }}
        </button>
      </div>

      <div v-if="error" class="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
        {{ error }}
      </div>
    </div>

    <div class="mt-10 grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="card text-center">
        <div class="text-3xl font-bold text-primary-600 mb-1">4+</div>
        <div class="text-sm text-gray-500">专业分析师 Agent</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-bull-500 mb-1">实时</div>
        <div class="text-sm text-gray-500">SSE 流式事件推送</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-primary-600 mb-1">多空</div>
        <div class="text-sm text-gray-500">辩论 + 风控双重把关</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import TickerInput from '../components/TickerInput.vue'
import { api } from '../api.js'

const router = useRouter()

const ticker = ref('')
const tradeDate = ref(new Date().toISOString().split('T')[0])
const debateRounds = ref(3)
const selectedAnalysts = ref(['market', 'social', 'news', 'fundamentals'])
const isLoading = ref(false)
const error = ref('')
const tickerError = ref('')

const analystOptions = [
  { value: 'market', label: '市场分析师' },
  { value: 'social', label: '社交媒体分析师' },
  { value: 'news', label: '新闻分析师' },
  { value: 'fundamentals', label: '基本面分析师' },
]

function loadExample() {
  ticker.value = '600000.SH'
  tradeDate.value = new Date().toISOString().split('T')[0]
}

async function startAnalysis() {
  error.value = ''
  tickerError.value = ''

  if (!ticker.value.trim()) {
    tickerError.value = '请输入股票代码'
    return
  }

  isLoading.value = true
  try {
    const res = await api.startAnalysis({
      ticker: ticker.value.trim(),
      trade_date: tradeDate.value,
      analysts: selectedAnalysts.value,
      max_debate_rounds: debateRounds.value,
    })
    router.push(`/analyze/${res.task_id}`)
  } catch (e) {
    error.value = e.message || '启动失败'
  } finally {
    isLoading.value = false
  }
}
</script>
