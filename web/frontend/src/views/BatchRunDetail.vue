<template>
  <div class="max-w-5xl mx-auto px-4 py-8">
    <div class="flex items-center gap-3 mb-6">
      <button @click="router.push('/batch')" class="text-gray-400 hover:text-gray-600">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
      </button>
      <h1 class="text-2xl font-bold text-gray-900">批量分析详情</h1>
    </div>

    <div v-if="!batch" class="text-center text-gray-400 py-8">加载中...</div>

    <template v-if="batch">
      <!-- Summary card -->
      <div class="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div class="grid grid-cols-2 md:grid-cols-6 gap-4">
          <div>
            <div class="text-xs text-gray-400">触发方式</div>
            <div class="text-sm font-medium">{{ batch.triggered_by === 'schedule' ? '定时' : '手动' }}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400">触发时间</div>
            <div class="text-sm font-medium">{{ formatDate(batch.triggered_at) }}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400">总数</div>
            <div class="text-sm font-medium">{{ batch.total_stocks }}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400">完成</div>
            <div class="text-sm font-medium text-green-600">{{ batch.completed_count }}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400">失败</div>
            <div class="text-sm font-medium text-red-600">{{ batch.failed_count }}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400">跳过</div>
            <div class="text-sm font-medium text-gray-500">{{ batch.skipped?.length || 0 }}</div>
          </div>
        </div>
        <div v-if="batch.error" class="mt-3 text-sm text-red-500 bg-red-50 px-3 py-2 rounded">
          {{ batch.error }}
        </div>
      </div>

      <!-- Per-stock table -->
      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table class="w-full">
          <thead class="bg-gray-50 border-b border-gray-200">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">代码</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">信号</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">完成时间</th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in batch.tasks" :key="task.task_id" class="border-b border-gray-100 hover:bg-gray-50">
              <td class="px-4 py-3">
                <span :class="taskStatusBadge(task.status)" class="px-2 py-0.5 rounded-full text-xs font-medium">
                  {{ taskStatusLabel(task.status) }}
                </span>
              </td>
              <td class="px-4 py-3 font-mono text-sm text-gray-900">{{ task.ticker }}</td>
              <td class="px-4 py-3">
                <span v-if="task.signal" :class="signalBadge(task.signal)" class="px-2 py-0.5 rounded-full text-xs font-bold">
                  {{ task.signal }}
                </span>
                <span v-else class="text-xs text-gray-400">-</span>
              </td>
              <td class="px-4 py-3 text-xs text-gray-400">{{ formatDate(task.completed_at) }}</td>
              <td class="px-4 py-3 text-right">
                <router-link
                  v-if="task.status === 'completed'"
                  :to="{ name: 'Report', params: { taskId: task.task_id } }"
                  class="text-primary-600 hover:text-primary-800 text-sm"
                >
                  查看报告
                </router-link>
                <button
                  v-else-if="task.error"
                  @click="showError(task)"
                  class="text-red-500 hover:text-red-700 text-sm"
                >
                  查看错误
                </button>
              </td>
            </tr>
            <!-- Skipped stocks -->
            <tr v-for="item in batch.skipped" :key="item.ticker" class="border-b border-gray-100 bg-gray-50">
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-500">
                  跳过
                </span>
              </td>
              <td class="px-4 py-3 font-mono text-sm text-gray-700">{{ item.ticker }}</td>
              <td class="px-4 py-3">
                <span v-if="item.signal" :class="signalBadge(item.signal)" class="px-2 py-0.5 rounded-full text-xs font-bold">
                  {{ item.signal }}
                </span>
                <span v-else class="text-xs text-gray-400">-</span>
              </td>
              <td class="px-4 py-3 text-xs text-gray-400">{{ formatDate(item.completed_at) }}</td>
              <td class="px-4 py-3 text-right">
                <router-link
                  :to="{ name: 'Report', params: { taskId: item.existing_task_id } }"
                  class="text-gray-500 hover:text-gray-700 text-sm"
                >
                  查看历史报告
                </router-link>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Error Modal -->
      <div v-if="selectedError" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click="selectedError = null">
        <div class="bg-white rounded-xl max-w-2xl w-full mx-4 p-6 shadow-xl" @click.stop>
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold text-gray-900">错误详情</h3>
            <button @click="selectedError = null" class="text-gray-400 hover:text-gray-600">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="mb-3">
            <span class="text-xs text-gray-400">股票代码:</span>
            <span class="font-mono text-sm ml-2">{{ selectedError.ticker }}</span>
          </div>
          <div class="mb-3">
            <span class="text-xs text-gray-400">分析日期:</span>
            <span class="text-sm ml-2">{{ selectedError.trade_date }}</span>
          </div>
          <div class="bg-red-50 border border-red-200 rounded-lg p-4">
            <pre class="text-sm text-red-700 whitespace-pre-wrap overflow-auto max-h-60">{{ selectedError.error }}</pre>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api.js'

const route = useRoute()
const router = useRouter()
const batch = ref(null)
const selectedError = ref(null)

let pollTimer = null

onMounted(async () => {
  await loadDetail()
  // Poll if still running
  if (batch.value && batch.value.status === 'running') {
    pollTimer = setInterval(async () => {
      await loadDetail()
      if (batch.value && batch.value.status !== 'running') {
        clearInterval(pollTimer)
      }
    }, 5000)
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

async function loadDetail() {
  batch.value = await api.getBatchRun(route.params.batchId)
}

function showError(task) {
  selectedError.value = {
    ticker: task.ticker,
    trade_date: task.trade_date,
    error: task.error,
  }
}

function formatDate(s) {
  if (!s) return '-'
  try { return new Date(s).toLocaleString('zh-CN') } catch { return s }
}

function taskStatusBadge(status) {
  return {
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    running: 'bg-blue-100 text-blue-700',
    pending: 'bg-gray-100 text-gray-500',
    cancelled: 'bg-gray-100 text-gray-500',
  }[status] || 'bg-gray-100 text-gray-500'
}

function taskStatusLabel(status) {
  return {
    completed: '完成',
    failed: '失败',
    running: '运行中',
    pending: '等待中',
    cancelled: '已取消',
  }[status] || status
}

function signalBadge(signal) {
  if (!signal) return ''
  const s = signal.toUpperCase()
  if (s.includes('BUY')) return 'bg-green-100 text-green-700'
  if (s.includes('SELL')) return 'bg-red-100 text-red-700'
  if (s.includes('HOLD')) return 'bg-yellow-100 text-yellow-700'
  return 'bg-gray-100 text-gray-500'
}
</script>
