<template>
  <div class="max-w-5xl mx-auto px-4 py-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-gray-900">分析历史</h1>
      <button class="btn-primary text-sm" @click="$router.push('/')">
        新建分析
      </button>
    </div>

    <div v-if="loading" class="card text-center py-12">
      <div class="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
      <p class="text-gray-500">加载中...</p>
    </div>

    <div v-else-if="tasks.length === 0" class="card text-center py-12 text-gray-500">
      暂无分析记录
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="task in tasks"
        :key="task.task_id"
        class="card flex items-center gap-4 hover:shadow-md transition-shadow cursor-pointer"
        @click="goToReport(task.task_id)"
      >
        <div class="w-12 h-12 rounded-xl flex items-center justify-center font-bold text-white shrink-0"
          :class="signalClass(task.signal)"
        >
          {{ task.signal ? task.signal[0] : '?' }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="font-semibold text-gray-900">{{ task.ticker }}</span>
            <span class="text-xs text-gray-400">{{ task.trade_date }}</span>
            <span
              class="text-xs px-2 py-0.5 rounded-full font-medium"
              :class="statusClass(task.status)"
            >
              {{ statusText(task.status) }}
            </span>
          </div>
          <div class="text-sm text-gray-500 mt-0.5">
            {{ formatTime(task.created_at) }}
          </div>
        </div>
        <div class="hidden sm:flex gap-2">
          <button
            class="text-sm px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50"
            @click.stop="reanalyze(task.ticker, task.trade_date)"
          >
            重新分析
          </button>
          <button
            class="text-sm px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            @click.stop="goToReport(task.task_id)"
          >
            查看
          </button>
        </div>
      </div>
    </div>

    <div v-if="total > tasks.length" class="mt-4 text-center">
      <button class="btn-secondary text-sm" @click="loadMore">
        加载更多
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'

const router = useRouter()

const tasks = ref([])
const total = ref(0)
const loading = ref(true)
const limit = ref(50)

function statusText(status) {
  const map = {
    pending: '等待中',
    running: '分析中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

function statusClass(status) {
  const map = {
    pending: 'bg-gray-100 text-gray-600',
    running: 'bg-primary-100 text-primary-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    cancelled: 'bg-amber-100 text-amber-700',
  }
  return map[status] || 'bg-gray-100 text-gray-600'
}

function signalClass(signal) {
  if (!signal) return 'bg-gray-400'
  const s = signal.toUpperCase()
  if (s.includes('BUY')) return 'bg-bull-500'
  if (s.includes('SELL')) return 'bg-bear-500'
  return 'bg-amber-500'
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

function goToReport(taskId) {
  router.push(`/report/${taskId}`)
}

async function reanalyze(ticker, tradeDate) {
  try {
    const res = await api.startAnalysis({ ticker, trade_date: tradeDate })
    router.push(`/analyze/${res.task_id}`)
  } catch (e) {
    alert('启动失败: ' + e.message)
  }
}

async function loadMore() {
  limit.value += 50
  await fetchTasks()
}

async function fetchTasks() {
  try {
    const res = await api.getHistory(limit.value, 0)
    tasks.value = res.tasks
    total.value = res.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchTasks)
</script>
