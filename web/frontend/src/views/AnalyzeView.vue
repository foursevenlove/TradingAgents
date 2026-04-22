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
        <button
          v-if="isCompleted"
          class="btn-primary text-sm"
          @click="goToReport"
        >
          查看报告
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Left: Pipeline -->
      <div class="lg:col-span-1">
        <AgentPipeline :events="events" />
      </div>

      <!-- Right: Output + Tools + Debate -->
      <div class="lg:col-span-2 space-y-6">
        <AgentOutput :events="events" />
        <ToolCallPanel :events="events" />
        <DebateView :events="events" />
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

function cancelAnalysis() {
  if (cleanup) cleanup()
  status.value = 'cancelled'
}

function goToReport() {
  router.push(`/report/${props.taskId}`)
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
  }
})

onUnmounted(() => {
  if (cleanup) cleanup()
})
</script>
