<template>
  <div class="max-w-5xl mx-auto px-4 py-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900">分析报告</h1>
        <p class="text-sm text-gray-500">{{ ticker }} · {{ tradeDate }}</p>
      </div>
      <div class="flex gap-3">
        <button class="btn-secondary text-sm" @click="$router.push('/history')">
          历史记录
        </button>
        <button class="btn-primary text-sm" @click="$router.push('/')">
          新建分析
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card text-center py-12">
      <div class="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
      <p class="text-gray-500">加载报告中...</p>
    </div>

    <template v-else-if="result">
      <!-- Decision Card -->
      <DecisionCard :signal="signal" :content="result.final_trade_decision" />

      <!-- Factor Score -->
      <FactorScore :result="result" />

      <!-- Reports -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="card" v-if="result.market_report">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">市场分析报告</h3>
          <div class="text-sm text-gray-600 max-h-60 overflow-y-auto prose prose-sm max-w-none" v-html="renderMd(result.market_report)"></div>
        </div>
        <div class="card" v-if="result.sentiment_report">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">情绪分析报告</h3>
          <div class="text-sm text-gray-600 max-h-60 overflow-y-auto prose prose-sm max-w-none" v-html="renderMd(result.sentiment_report)"></div>
        </div>
        <div class="card" v-if="result.news_report">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">新闻分析报告</h3>
          <div class="text-sm text-gray-600 max-h-60 overflow-y-auto prose prose-sm max-w-none" v-html="renderMd(result.news_report)"></div>
        </div>
        <div class="card" v-if="result.fundamentals_report">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">基本面分析报告</h3>
          <div class="text-sm text-gray-600 max-h-60 overflow-y-auto prose prose-sm max-w-none" v-html="renderMd(result.fundamentals_report)"></div>
        </div>
      </div>

      <!-- Trader Plan -->
      <div class="card" v-if="result.trader_investment_plan">
        <h3 class="text-sm font-semibold text-gray-700 mb-2">交易员计划</h3>
        <div class="text-sm text-gray-600 prose prose-sm max-w-none" v-html="renderMd(result.trader_investment_plan)"></div>
      </div>

      <!-- Debate Summaries -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="card" v-if="result.investment_debate_state?.bull_history">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">多空辩论 - 多方观点</h3>
          <div class="text-sm text-gray-600 max-h-60 overflow-y-auto prose prose-sm max-w-none" v-html="renderMd(result.investment_debate_state.bull_history)"></div>
        </div>
        <div class="card" v-if="result.investment_debate_state?.bear_history">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">多空辩论 - 空方观点</h3>
          <div class="text-sm text-gray-600 max-h-60 overflow-y-auto prose prose-sm max-w-none" v-html="renderMd(result.investment_debate_state.bear_history)"></div>
        </div>
      </div>

      <!-- Risk Debate -->
      <div class="card" v-if="result.risk_debate_state?.judge_decision">
        <h3 class="text-sm font-semibold text-gray-700 mb-2">风控决策</h3>
        <div class="text-sm text-gray-600 prose prose-sm max-w-none" v-html="renderMd(result.risk_debate_state.judge_decision)"></div>
      </div>

      <!-- Chart -->
      <DataChart :ticker="ticker" :trade-date="tradeDate" />
    </template>

    <div v-else-if="error" class="card text-center py-12 text-red-600">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import DecisionCard from '../components/DecisionCard.vue'
import FactorScore from '../components/FactorScore.vue'
import DataChart from '../components/DataChart.vue'
import { api } from '../api.js'

function renderMd(text) {
  if (!text) return ''
  // Strip <think>...</think> reasoning blocks
  const cleaned = text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  return marked.parse(cleaned)
}

const props = defineProps({
  taskId: String,
})

const router = useRouter()
const result = ref(null)
const signal = ref('')
const ticker = ref('')
const tradeDate = ref('')
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    // First check task status
    const statusRes = await api.getStatus(props.taskId)

    // If still running/pending, redirect to analyze view to watch progress
    if (statusRes.status === 'running' || statusRes.status === 'pending') {
      router.replace(`/analyze/${props.taskId}`)
      return
    }

    // Task finished — load result
    const res = await api.getResult(props.taskId)
    ticker.value = res.ticker || ''
    tradeDate.value = res.trade_date || ''
    if (res.result) {
      result.value = res.result
      signal.value = res.signal || ''
    } else {
      // Fallback to history detail
      const detail = await api.getHistoryDetail(props.taskId)
      result.value = detail.result
      signal.value = detail.signal || ''
    }

    if (!result.value) {
      error.value = statusRes.error || '分析未产生结果'
    }
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
})
</script>
