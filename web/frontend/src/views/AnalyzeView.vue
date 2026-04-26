<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-bold text-gray-900">分析进程</h1>
        <p class="text-sm text-gray-500">
          <span v-if="stockName" class="font-medium">{{ stockName }}</span>
          <span v-if="stockName && ticker" class="text-gray-400"> · </span>
          <span class="text-gray-400">{{ ticker }}</span>
          <span class="text-gray-400"> · </span>
          <span>{{ tradeDate }}</span>
        </p>
      </div>
      <div class="flex items-center gap-3">
        <span
          class="text-xs px-3 py-1 rounded-full font-medium"
          :class="statusClass"
        >
          {{ statusText }}
        </span>
        <button
          v-if="isRunning"
          class="btn-secondary text-sm"
          @click="cancelAnalysis"
        >
          取消
        </button>
        <!-- View toggle for completed tasks -->
        <div v-if="isCompleted" class="flex items-center gap-2">
          <button
            class="text-sm px-3 py-1 rounded-lg transition-colors"
            :class="viewMode === 'process' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            @click="viewMode = 'process'"
          >
            分析过程
          </button>
          <button
            class="text-sm px-3 py-1 rounded-lg transition-colors"
            :class="viewMode === 'report' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            @click="viewMode = 'report'"
          >
            分析报告
          </button>
        </div>
      </div>
    </div>

    <!-- Process View -->
    <div v-if="viewMode === 'process'" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Left: Pipeline -->
      <div class="lg:col-span-1">
        <AgentPipeline
          :events="events"
          :selected-agent="selectedAgent"
          @select-agent="onSelectAgent"
        />
      </div>

      <!-- Right: Output + Tools + Debate -->
      <div class="lg:col-span-2 space-y-6">
        <AgentOutput
          :events="events"
          :selected-agent="selectedAgent"
          @clear-selection="onClearSelection"
        />
        <ToolCallPanel
          :events="events"
          :selected-agent="selectedAgent"
          @clear-selection="onClearSelection"
        />
        <DebateView
          :events="events"
          :selected-agent="selectedAgent"
          @clear-selection="onClearSelection"
        />
      </div>
    </div>

    <!-- Report View (for completed tasks) -->
    <div v-if="viewMode === 'report' && isCompleted" class="space-y-8">
      <!-- Signal Card - Hero Section -->
      <div class="report-card bg-gradient-to-r from-gray-50 to-white">
        <div class="flex items-center justify-between">
          <div>
            <div class="flex items-center gap-2 mb-2">
              <span class="text-2xl">📊</span>
              <h2 class="text-xl font-bold text-gray-900">{{ stockName || ticker }}</h2>
            </div>
            <p class="text-sm text-gray-500">
              <span class="inline-flex items-center gap-1">
                <span class="font-medium text-gray-700">{{ ticker }}</span>
                <span class="text-gray-400">|</span>
                <span>{{ tradeDate }}</span>
              </span>
            </p>
          </div>
          <div
            class="px-6 py-3 rounded-xl font-bold text-xl shadow-md transform transition-transform hover:scale-105"
            :class="signalClass"
          >
            {{ signal || 'UNKNOWN' }}
          </div>
        </div>
      </div>

      <!-- Section: 决策结论 -->
      <section v-if="result?.final_trade_decision">
        <h2 class="report-section-title">
          <span class="w-8 h-8 rounded-lg bg-primary-100 flex items-center justify-center">
            <span class="text-primary-600">✓</span>
          </span>
          决策结论
        </h2>
        <div class="report-card-colored border-2 border-primary-200 bg-gradient-to-br from-primary-50 to-white">
          <div class="prose-custom prose max-w-none" v-html="renderMd(result.final_trade_decision)"></div>
        </div>
      </section>

      <!-- Section: 因子评分 -->
      <section v-if="result">
        <h2 class="report-section-title">
          <span class="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
            <span class="text-indigo-600">📈</span>
          </span>
          因子评分
        </h2>
        <FactorScore :result="result" />
      </section>

      <hr class="report-divider" />

      <!-- Section: 分析师报告 -->
      <section>
        <h2 class="report-section-title">
          <span class="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
            <span class="text-blue-600">🔍</span>
          </span>
          分析师报告
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div v-if="result?.market_report" class="report-card">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-blue-700 mb-4 pb-2 border-b border-blue-100">
              <span class="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs">📊</span>
              市场分析师
            </h3>
            <div class="prose-custom prose prose-sm max-w-none max-h-72 overflow-y-auto pr-2" v-html="renderMd(result.market_report)"></div>
          </div>
          <div v-if="result?.news_report" class="report-card">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-orange-700 mb-4 pb-2 border-b border-orange-100">
              <span class="w-6 h-6 rounded-full bg-orange-500 flex items-center justify-center text-white text-xs">📰</span>
              新闻分析师
            </h3>
            <div class="prose-custom prose prose-sm max-w-none max-h-72 overflow-y-auto pr-2" v-html="renderMd(result.news_report)"></div>
          </div>
          <div v-if="result?.fundamentals_report" class="report-card">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-green-700 mb-4 pb-2 border-b border-green-100">
              <span class="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center text-white text-xs">💰</span>
              基本面分析师
            </h3>
            <div class="prose-custom prose prose-sm max-w-none max-h-72 overflow-y-auto pr-2" v-html="renderMd(result.fundamentals_report)"></div>
          </div>
          <div v-if="result?.sentiment_report" class="report-card">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-purple-700 mb-4 pb-2 border-b border-purple-100">
              <span class="w-6 h-6 rounded-full bg-purple-500 flex items-center justify-center text-white text-xs">💬</span>
              社交媒体分析师
            </h3>
            <div class="prose-custom prose prose-sm max-w-none max-h-72 overflow-y-auto pr-2" v-html="renderMd(result.sentiment_report)"></div>
          </div>
        </div>
      </section>

      <hr class="report-divider" />

      <!-- Section: 多空辩论 -->
      <section v-if="result?.investment_debate_state">
        <h2 class="report-section-title">
          <span class="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center">
            <span class="text-green-600">⚖️</span>
          </span>
          多空辩论
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div v-if="result.investment_debate_state.bull_history" class="report-card-colored border-2 border-green-200 bg-gradient-to-br from-green-50 to-white">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-green-700 mb-4 pb-2 border-b border-green-100">
              <span class="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center text-white text-xs">🐂</span>
              多方研究员
            </h3>
            <div class="prose-custom prose prose-sm max-w-none max-h-72 overflow-y-auto pr-2" v-html="renderMd(result.investment_debate_state.bull_history)"></div>
          </div>
          <div v-if="result.investment_debate_state.bear_history" class="report-card-colored border-2 border-red-200 bg-gradient-to-br from-red-50 to-white">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-red-700 mb-4 pb-2 border-b border-red-100">
              <span class="w-6 h-6 rounded-full bg-red-500 flex items-center justify-center text-white text-xs">🐻</span>
              空方研究员
            </h3>
            <div class="prose-custom prose prose-sm max-w-none max-h-72 overflow-y-auto pr-2" v-html="renderMd(result.investment_debate_state.bear_history)"></div>
          </div>
        </div>
      </section>

      <!-- Section: 研究经理 -->
      <section v-if="result?.investment_plan">
        <div class="report-card-colored border-2 border-indigo-200 bg-gradient-to-br from-indigo-50 to-white">
          <h3 class="flex items-center gap-2 text-sm font-semibold text-indigo-700 mb-4 pb-2 border-b border-indigo-100">
            <span class="w-6 h-6 rounded-full bg-indigo-500 flex items-center justify-center text-white text-xs">👨‍💼</span>
            研究经理投资计划
          </h3>
          <div class="prose-custom prose prose-sm max-w-none" v-html="renderMd(result.investment_plan)"></div>
        </div>
      </section>

      <!-- Section: 交易员 -->
      <section v-if="result?.trader_investment_plan">
        <div class="report-card-colored border-2 border-cyan-200 bg-gradient-to-br from-cyan-50 to-white">
          <h3 class="flex items-center gap-2 text-sm font-semibold text-cyan-700 mb-4 pb-2 border-b border-cyan-100">
            <span class="w-6 h-6 rounded-full bg-cyan-500 flex items-center justify-center text-white text-xs">💹</span>
            交易员投资计划
          </h3>
          <div class="prose-custom prose prose-sm max-w-none" v-html="renderMd(result.trader_investment_plan)"></div>
        </div>
      </section>

      <hr class="report-divider" />

      <!-- Section: 风控辩论 -->
      <section v-if="result?.risk_debate_state">
        <h2 class="report-section-title">
          <span class="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center">
            <span class="text-amber-600">🛡️</span>
          </span>
          风控辩论
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div v-if="result.risk_debate_state.aggressive_history" class="report-card-colored border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-white">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-orange-700 mb-4 pb-2 border-b border-orange-100">
              <span class="w-6 h-6 rounded-full bg-orange-500 flex items-center justify-center text-white text-xs">🔥</span>
              激进风控
            </h3>
            <div class="prose-custom prose prose-sm max-w-none max-h-72 overflow-y-auto pr-2" v-html="renderMd(result.risk_debate_state.aggressive_history)"></div>
          </div>
          <div v-if="result.risk_debate_state.conservative_history" class="report-card-colored border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-white">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-blue-700 mb-4 pb-2 border-b border-blue-100">
              <span class="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs">🧊</span>
              保守风控
            </h3>
            <div class="prose-custom prose prose-sm max-w-none max-h-72 overflow-y-auto pr-2" v-html="renderMd(result.risk_debate_state.conservative_history)"></div>
          </div>
          <div v-if="result.risk_debate_state.neutral_history" class="report-card-colored border-2 border-gray-200 bg-gradient-to-br from-gray-50 to-white">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-4 pb-2 border-b border-gray-100">
              <span class="w-6 h-6 rounded-full bg-gray-500 flex items-center justify-center text-white text-xs">⚖️</span>
              中性风控
            </h3>
            <div class="prose-custom prose prose-sm max-w-none max-h-72 overflow-y-auto pr-2" v-html="renderMd(result.risk_debate_state.neutral_history)"></div>
          </div>
        </div>
      </section>

      <hr class="report-divider" />

      <!-- Section: K线图表 -->
      <section>
        <h2 class="report-section-title">
          <span class="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
            <span class="text-purple-600">📉</span>
          </span>
          K线图表
        </h2>
        <DataChart :ticker="ticker" :trade-date="tradeDate" />
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import AgentPipeline from '../components/AgentPipeline.vue'
import AgentOutput from '../components/AgentOutput.vue'
import ToolCallPanel from '../components/ToolCallPanel.vue'
import DebateView from '../components/DebateView.vue'
import DecisionCard from '../components/DecisionCard.vue'
import FactorScore from '../components/FactorScore.vue'
import DataChart from '../components/DataChart.vue'
import { api } from '../api.js'
import { taskStore } from '../stores/taskStore.js'

function renderMd(text) {
  if (!text) return ''
  const cleaned = text.replace(/<tool_call>[\s\S]*?<\/think>/gi, '').trim()
  return marked.parse(cleaned)
}

const props = defineProps({
  taskId: String,
})

const router = useRouter()

const events = ref([])
const ticker = ref('')
const stockName = ref('')
const tradeDate = ref('')
const status = ref('pending')
const signal = ref('')
const result = ref(null)
const selectedAgent = ref('')
const viewMode = ref('process')  // 'process' or 'report'
let cleanup = null

const isRunning = computed(() => status.value === 'running' || status.value === 'pending')
const isCompleted = computed(() => status.value === 'completed')

const statusText = computed(() => {
  const map = {
    pending: '等待中',
    running: '分析中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status.value] || status.value
})

const statusClass = computed(() => {
  const map = {
    pending: 'bg-gray-100 text-gray-600',
    running: 'bg-primary-100 text-primary-700 animate-pulse',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    cancelled: 'bg-amber-100 text-amber-700',
  }
  return map[status.value] || 'bg-gray-100 text-gray-600'
})

const signalClass = computed(() => {
  const s = signal.value?.toUpperCase()
  if (s === 'BUY') return 'bg-green-500 text-white'
  if (s === 'SELL') return 'bg-red-500 text-white'
  return 'bg-gray-500 text-white'
})

async function cancelAnalysis() {
  // Close SSE connection
  if (cleanup) cleanup()
  // Call backend to stop the runner
  try {
    await api.cancelAnalysis(props.taskId)
  } catch (e) {
    console.error('Cancel API error', e)
  }
  status.value = 'cancelled'
}

function onSelectAgent(agentName) {
  selectedAgent.value = agentName
}

function onClearSelection() {
  selectedAgent.value = ''
}

function handleEvent(event) {
  events.value.push(event)
  taskStore.addEvent(event)

  if (event.type === 'started') {
    status.value = 'running'
    if (event.data.ticker) ticker.value = event.data.ticker
    if (event.data.trade_date) tradeDate.value = event.data.trade_date
  }
  if (event.type === 'completed') {
    status.value = 'completed'
    taskStore.setStatus('completed')
  }
  if (event.type === 'failed') {
    status.value = 'failed'
    taskStore.setStatus('failed')
  }
}

async function loadTaskInfo() {
  try {
    const info = await api.getStatus(props.taskId)
    ticker.value = info.ticker
    stockName.value = info.stock_name || ''
    tradeDate.value = info.trade_date
    status.value = info.status
    signal.value = info.signal || ''
    return info.status
  } catch (e) {
    console.error('load task info failed', e)
    return null
  }
}

async function loadHistoricalEvents() {
  try {
    // Load events already saved in DB (for page refresh / re-entry)
    const detail = await api.getHistoryDetail(props.taskId)
    if (detail && detail.events && detail.events.length > 0) {
      for (const ev of detail.events) {
        events.value.push({ type: ev.type, data: ev.data })
        taskStore.addEvent({ type: ev.type, data: ev.data })
      }
    }
    // Also load result if available
    if (detail?.result) {
      result.value = detail.result
      if (detail.signal) signal.value = detail.signal
    }
  } catch (e) {
    // No history yet, that's fine
  }
}

onMounted(async () => {
  taskStore.reset()
  taskStore.setTaskId(props.taskId)

  const currentStatus = await loadTaskInfo()

  // If task is still running or pending, load history then connect SSE
  if (currentStatus === 'running' || currentStatus === 'pending') {
    await loadHistoricalEvents()
    cleanup = api.streamEvents(
      props.taskId,
      handleEvent,
      (err) => console.error('SSE error', err),
      () => {},
    )
  } else {
    // Task already finished — just replay all events from DB
    await loadHistoricalEvents()
    // For completed tasks, show report view by default if we have a result
    if (currentStatus === 'completed' && result.value) {
      viewMode.value = 'report'
    }
  }
})

onUnmounted(() => {
  if (cleanup) cleanup()
})
</script>
