<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-bold text-gray-900">分析进程</h1>
        <p class="text-sm text-gray-500">{{ ticker }} · {{ tradeDate }}</p>
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
    <div v-if="viewMode === 'report' && isCompleted" class="space-y-6">
      <!-- Signal Card -->
      <div class="bg-white rounded-xl border border-gray-200 p-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-gray-900">最终决策</h2>
            <p class="text-sm text-gray-500">{{ ticker }} · {{ tradeDate }}</p>
          </div>
          <div
            class="px-4 py-2 rounded-lg font-bold text-lg"
            :class="signalClass"
          >
            {{ signal || 'UNKNOWN' }}
          </div>
        </div>
      </div>

      <!-- Reports Summary -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div v-if="result?.market_report" class="card">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">市场分析报告</h3>
          <div class="text-sm text-gray-600 whitespace-pre-wrap max-h-40 overflow-y-auto">{{ result.market_report }}</div>
        </div>
        <div v-if="result?.news_report" class="card">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">新闻分析报告</h3>
          <div class="text-sm text-gray-600 whitespace-pre-wrap max-h-40 overflow-y-auto">{{ result.news_report }}</div>
        </div>
        <div v-if="result?.fundamentals_report" class="card">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">基本面分析报告</h3>
          <div class="text-sm text-gray-600 whitespace-pre-wrap max-h-40 overflow-y-auto">{{ result.fundamentals_report }}</div>
        </div>
        <div v-if="result?.sentiment_report" class="card">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">情绪分析报告</h3>
          <div class="text-sm text-gray-600 whitespace-pre-wrap max-h-40 overflow-y-auto">{{ result.sentiment_report }}</div>
        </div>
      </div>

      <!-- Trader Plan -->
      <div v-if="result?.trader_investment_plan" class="card">
        <h3 class="text-sm font-semibold text-gray-700 mb-2">交易员投资计划</h3>
        <div class="text-sm text-gray-600 whitespace-pre-wrap">{{ result.trader_investment_plan }}</div>
      </div>

      <!-- Final Decision -->
      <div v-if="result?.final_trade_decision" class="card">
        <h3 class="text-sm font-semibold text-gray-700 mb-2">最终交易决策</h3>
        <div class="text-sm text-gray-600 whitespace-pre-wrap">{{ result.final_trade_decision }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import AgentPipeline from '../components/AgentPipeline.vue'
import AgentOutput from '../components/AgentOutput.vue'
import ToolCallPanel from '../components/ToolCallPanel.vue'
import DebateView from '../components/DebateView.vue'
import { api } from '../api.js'
import { taskStore } from '../stores/taskStore.js'

const props = defineProps({
  taskId: String,
})

const router = useRouter()

const events = ref([])
const ticker = ref('')
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
