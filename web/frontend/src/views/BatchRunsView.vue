<template>
  <div class="max-w-5xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">批量分析历史</h1>

    <div v-if="runs.length === 0" class="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
      <p class="text-lg mb-2">暂无批量分析记录</p>
      <p class="text-sm">在自选股页面点击"批量分析"开始</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="run in runs"
        :key="run.batch_id"
        class="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow cursor-pointer"
        @click="router.push({ name: 'BatchRunDetail', params: { batchId: run.batch_id } })"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span :class="statusDot(run.status)" class="w-3 h-3 rounded-full"></span>
            <div>
              <div class="text-sm font-medium text-gray-900">
                {{ run.triggered_by === 'schedule' ? '定时触发' : '手动触发' }}
              </div>
              <div class="text-xs text-gray-400">{{ formatDate(run.triggered_at) }}</div>
            </div>
          </div>
          <div class="flex items-center gap-4">
            <div class="text-right">
              <div class="text-sm font-medium text-gray-900">
                {{ run.completed_count }}/{{ run.total_stocks }} 完成
              </div>
              <div v-if="run.failed_count > 0" class="text-xs text-red-500">
                {{ run.failed_count }} 失败
              </div>
            </div>
            <span :class="statusBadge(run.status)" class="px-2 py-1 rounded-full text-xs font-medium">
              {{ statusLabel(run.status) }}
            </span>
          </div>
        </div>
        <!-- Progress bar -->
        <div class="mt-2 w-full bg-gray-100 rounded-full h-1.5">
          <div
            class="h-1.5 rounded-full transition-all"
            :class="run.status === 'completed' ? 'bg-green-500' : run.status === 'partial_failure' ? 'bg-yellow-500' : 'bg-red-500'"
            :style="{ width: `${(run.completed_count / run.total_stocks) * 100}%` }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'

const router = useRouter()
const runs = ref([])

onMounted(async () => {
  runs.value = await api.getBatchRuns()
})

function formatDate(s) {
  if (!s) return '-'
  try { return new Date(s).toLocaleString('zh-CN') } catch { return s }
}

function statusDot(status) {
  return {
    completed: 'bg-green-500',
    partial_failure: 'bg-yellow-500',
    failed: 'bg-red-500',
    running: 'bg-blue-500 animate-pulse',
  }[status] || 'bg-gray-300'
}

function statusBadge(status) {
  return {
    completed: 'bg-green-100 text-green-700',
    partial_failure: 'bg-yellow-100 text-yellow-700',
    failed: 'bg-red-100 text-red-700',
    running: 'bg-blue-100 text-blue-700',
  }[status] || 'bg-gray-100 text-gray-500'
}

function statusLabel(status) {
  return {
    completed: '完成',
    partial_failure: '部分失败',
    failed: '失败',
    running: '运行中',
  }[status] || status
}
</script>
