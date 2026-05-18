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
          class="btn-secondary text-sm"
          :disabled="refreshing"
          @click="manualRefresh"
        >
          {{ refreshing ? '刷新中...' : '刷新' }}
        </button>
        <span v-if="errorMsg" class="text-xs text-red-600 bg-red-50 px-3 py-1 rounded-full font-medium max-w-md truncate" :title="errorMsg">
          {{ errorMsg }}
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
    <div v-if="viewMode === 'process'" class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Left: Pipeline (narrower) -->
      <div class="lg:col-span-3">
        <AgentPipeline
          :events="events"
          :selected-agent="selectedAgent"
          @select-agent="onSelectAgent"
        />
      </div>

      <!-- Right: Dynamic Content Area (fixed height, children fill) -->
      <div class="lg:col-span-9 h-[calc(100vh-80px)] flex flex-col">
        <!-- Analyst Phase: Agent Output + Tool Calls -->
        <template v-if="isAnalystPhase">
          <AgentOutput
            :events="events"
            :selected-agent="selectedAgent"
            :expanded="true"
            class="flex-1 min-h-0"
            @clear-selection="onClearSelection"
          />
          <ToolCallPanel
            :events="events"
            :selected-agent="selectedAgent"
            :compact="true"
            class="shrink-0 mt-3"
            @clear-selection="onClearSelection"
          />
        </template>

        <!-- Debate Phase -->
        <DebateView
          v-if="isDebatePhase"
          :events="events"
          :selected-agent="selectedAgent"
          class="flex-1 min-h-0"
          @clear-selection="onClearSelection"
        />

        <!-- Trader Phase -->
        <AgentOutput
          v-if="isTraderPhase"
          :events="events"
          :selected-agent="selectedAgent"
          :expanded="true"
          class="flex-1 min-h-0"
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
const selectedAgent = ref('Market Analyst')  // Default to first analyst
const userExplicitlySelected = ref(false)  // Track if user clicked to select
const viewMode = ref('process')  // 'process' or 'report'
const errorMsg = ref('')
const refreshing = ref(false)
let cleanup = null

const isRunning = computed(() => status.value === 'running' || status.value === 'pending')
const isCompleted = computed(() => status.value === 'completed')

// Agent type classifications
const analystAgents = ['Market Analyst', 'Social Analyst', 'News Analyst', 'Fundamentals Analyst']
const debateAgents = ['Bull Researcher', 'Bear Researcher', 'Aggressive Analyst', 'Conservative Analyst', 'Neutral Analyst']
const judgeAgents = ['Research Manager', 'Risk Judge']
const traderAgents = ['Trader']

// Determine current phase based on selection or running agent
const effectiveAgent = computed(() => {
  // If user explicitly clicked to select an agent, respect their choice
  if (userExplicitlySelected.value) {
    return selectedAgent.value
  }
  // When running and user hasn't explicitly selected, follow the running agent
  const running = currentRunningAgent.value
  const isDone = events.value.some(e => e.type === 'completed')
  if (running && !isDone) {
    return running
  }
  // After completion, use selected agent (defaults to Market Analyst)
  return selectedAgent.value
})

const currentRunningAgent = computed(() => {
  // Find the most recent running agent from events
  for (let i = events.value.length - 1; i >= 0; i--) {
    const ev = events.value[i]
    if (ev.type === 'agent_start') return ev.data.agent_name
    if (ev.type === 'debate_speech') {
      // Map debate speech side back to agent
      const sideToAgent = {
        bull: 'Bull Researcher',
        bear: 'Bear Researcher',
        aggressive: 'Aggressive Analyst',
        conservative: 'Conservative Analyst',
        neutral: 'Neutral Analyst'
      }
      return sideToAgent[ev.data.side] || ev.data.speaker
    }
    if (ev.type === 'debate_judge') return ev.data.judge
    if (ev.type === 'trader_plan') return 'Trader'
    if (ev.type === 'final_decision') return 'Trader'
  }
  return null
})

const isAnalystPhase = computed(() => analystAgents.includes(effectiveAgent.value))
const isDebatePhase = computed(() => debateAgents.includes(effectiveAgent.value) || judgeAgents.includes(effectiveAgent.value))
const isTraderPhase = computed(() => traderAgents.includes(effectiveAgent.value))

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
  userExplicitlySelected.value = true
}

function onClearSelection() {
  selectedAgent.value = ''
  userExplicitlySelected.value = false
}

function handleEvent(event) {
  events.value.push(event)
  taskStore.addEvent(event)

  if (event.type === 'started') {
    status.value = 'running'
    if (event.data.ticker) ticker.value = event.data.ticker
    if (event.data.trade_date) tradeDate.value = event.data.trade_date
    // Reset user selection when analysis starts
    userExplicitlySelected.value = false
  }
  if (event.type === 'completed') {
    status.value = 'completed'
    taskStore.setStatus('completed')
    // Reset user selection when analysis completes
    userExplicitlySelected.value = false
    refreshTaskData({ retries: 5, retryDelay: 800, showReport: true })
  }
  if (event.type === 'failed') {
    status.value = 'failed'
    errorMsg.value = event.data.error || '分析失败'
    taskStore.setStatus('failed')
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function loadTaskInfo() {
  try {
    const info = await api.getStatus(props.taskId)
    ticker.value = info.ticker
    stockName.value = info.stock_name || ''
    tradeDate.value = info.trade_date
    status.value = info.status
    signal.value = info.signal || ''
    if (info.error) errorMsg.value = info.error
    return info.status
  } catch (e) {
    console.error('load task info failed', e)
    return null
  }
}

async function loadTaskResult() {
  const res = await api.getResult(props.taskId)
  if (res?.result) {
    result.value = res.result
    signal.value = res.signal || signal.value || ''
    return true
  }

  const detail = await api.getHistoryDetail(props.taskId)
  if (detail?.result) {
    result.value = detail.result
    signal.value = detail.signal || signal.value || ''
    return true
  }

  return false
}

async function refreshTaskData({ retries = 1, retryDelay = 600, showReport = false } = {}) {
  refreshing.value = true
  try {
    for (let attempt = 0; attempt < retries; attempt += 1) {
      const currentStatus = await loadTaskInfo()
      if (currentStatus === 'completed') {
        const loaded = await loadTaskResult()
        if (loaded) {
          if (showReport) viewMode.value = 'report'
          return true
        }
      }
      if (attempt < retries - 1) await sleep(retryDelay)
    }
    return false
  } catch (e) {
    console.error('refresh task data failed', e)
    return false
  } finally {
    refreshing.value = false
  }
}

async function manualRefresh() {
  await refreshTaskData({ retries: 2, retryDelay: 500, showReport: status.value === 'completed' })
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
    if (currentStatus === 'completed' && !result.value) {
      await refreshTaskData({ retries: 3, retryDelay: 800, showReport: true })
    }
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
