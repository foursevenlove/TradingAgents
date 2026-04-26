<template>
  <div class="max-w-5xl mx-auto px-4 py-8">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">自选股管理</h1>
      <button
        v-if="store.stocks.filter(s => s.enabled).length > 0"
        @click="triggerBatch"
        :disabled="batching"
        class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 text-sm font-medium"
      >
        {{ batching ? '批量分析中...' : '批量分析' }}
      </button>
    </div>

    <!-- Add stock form -->
    <div class="bg-white rounded-xl border border-gray-200 p-4 mb-6">
      <div class="flex gap-3 items-end">
        <div class="flex-1">
          <label class="block text-xs font-medium text-gray-500 mb-1">股票代码</label>
          <input
            v-model="newTicker"
            @keyup.enter="addStock"
            placeholder="如 600000.SH 或 000001.SZ"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div class="flex-1">
          <label class="block text-xs font-medium text-gray-500 mb-1">股票名称（可选）</label>
          <input
            v-model="newName"
            @keyup.enter="addStock"
            placeholder="如 浦发银行"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <button
          @click="addStock"
          :disabled="!newTicker.trim()"
          class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 text-sm font-medium"
        >
          添加
        </button>
      </div>
    </div>

    <!-- Watchlist table -->
    <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div v-if="store.stocks.length === 0" class="p-8 text-center text-gray-400">
        <p class="text-lg mb-2">自选股列表为空</p>
        <p class="text-sm">添加股票代码开始使用</p>
      </div>
      <table v-else class="w-full">
        <thead class="bg-gray-50 border-b border-gray-200">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">启用</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">代码</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">名称</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">添加时间</th>
            <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="stock in store.stocks" :key="stock.id" class="border-b border-gray-100 hover:bg-gray-50">
            <td class="px-4 py-3">
              <input
                type="checkbox"
                :checked="stock.enabled"
                @change="store.toggleStock(stock.id, !stock.enabled)"
                class="w-4 h-4 text-primary-600 rounded"
              />
            </td>
            <td class="px-4 py-3 font-mono text-sm text-gray-900">{{ stock.ticker }}</td>
            <td class="px-4 py-3 text-sm text-gray-600">{{ stock.name || '-' }}</td>
            <td class="px-4 py-3 text-xs text-gray-400">{{ formatDate(stock.created_at) }}</td>
            <td class="px-4 py-3 text-right">
              <button @click="removeStock(stock.id)" class="text-red-500 hover:text-red-700 text-sm">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Schedule config -->
    <div class="bg-white rounded-xl border border-gray-200 p-6 mt-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">定时批量分析</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">启用定时</label>
          <input type="checkbox" v-model="scheduleForm.enabled" class="w-4 h-4 text-primary-600 rounded" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">执行时间</label>
          <select
            v-model="scheduleForm.schedule_option"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="everyday_9am">每天 09:00（开盘前）</option>
            <option value="everyday_3pm">每天 15:00（收盘后）</option>
            <option value="weekday_9am">工作日 09:00（周一至周五）</option>
            <option value="weekday_3pm">工作日 15:00（周一至周五）</option>
            <option value="monday_9am">每周一 09:00</option>
            <option value="friday_3pm">每周五 15:00</option>
            <option value="every_30min">每 30 分钟</option>
            <option value="every_1hour">每 1 小时</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">最大并发数</label>
          <select
            v-model.number="scheduleForm.max_concurrency"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option :value="1">1</option>
            <option :value="2">2</option>
            <option :value="3">3</option>
            <option :value="4">4</option>
            <option :value="5">5</option>
          </select>
        </div>
      </div>
      <div class="mt-4 flex items-center gap-4">
        <button
          @click="saveSchedule"
          class="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 text-sm font-medium"
        >
          保存配置
        </button>
        <span v-if="saveMsg" class="text-sm text-gray-600">{{ saveMsg }}</span>
        <div v-if="store.schedulerStatus.next_run_at" class="text-xs text-gray-400">
          下次运行: {{ formatDate(store.schedulerStatus.next_run_at) }}
        </div>
        <div v-if="store.schedulerStatus.last_run_at" class="text-xs text-gray-400">
          上次运行: {{ formatDate(store.schedulerStatus.last_run_at) }}
        </div>
      </div>
    </div>

    <!-- Batch run toast -->
    <div v-if="batchMsg" class="fixed bottom-6 right-6 bg-gray-900 text-white px-4 py-3 rounded-lg shadow-lg text-sm">
      {{ batchMsg }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { watchlistStore as store } from '../stores/watchlistStore.js'
import { api } from '../api.js'

const router = useRouter()
const newTicker = ref('')
const newName = ref('')
const batching = ref(false)
const batchMsg = ref('')
const saveMsg = ref('')

const scheduleForm = ref({
  enabled: false,
  schedule_option: 'weekday_9am',
  max_concurrency: 2,
})

// 选项到 cron 表达式的映射
const SCHEDULE_TO_CRON = {
  'everyday_9am': '0 9 * * *',        // 每天 9:00
  'everyday_3pm': '0 15 * * *',       // 每天 15:00
  'weekday_9am': '0 9 * * 1-5',       // 工作日 9:00 (周一到周五)
  'weekday_3pm': '0 15 * * 1-5',      // 工作日 15:00
  'monday_9am': '0 9 * * 1',          // 每周一 9:00
  'friday_3pm': '0 15 * * 5',         // 每周五 15:00
  'every_30min': '*/30 * * * *',      // 每 30 分钟
  'every_1hour': '0 * * * *',         // 每小时
}

// cron 表达式到选项的反向映射
const CRON_TO_SCHEDULE = {
  '0 9 * * *': 'everyday_9am',
  '0 15 * * *': 'everyday_3pm',
  '0 9 * * 1-5': 'weekday_9am',
  '0 15 * * 1-5': 'weekday_3pm',
  '0 9 * * 1': 'monday_9am',
  '0 15 * * 5': 'friday_3pm',
  '*/30 * * * *': 'every_30min',
  '0 * * * *': 'every_1hour',
}

onMounted(async () => {
  await store.loadStocks()
  await store.loadSchedule()
  await store.loadSchedulerStatus()
  scheduleForm.value.enabled = store.schedule.enabled
  scheduleForm.value.max_concurrency = store.schedule.max_concurrency

  // 把 cron 表达式映射到选项
  const cron = store.schedule.cron_expression
  scheduleForm.value.schedule_option = CRON_TO_SCHEDULE[cron] || 'weekday_9am'
})

async function addStock() {
  if (!newTicker.value.trim()) return
  await store.addStock(newTicker.value.trim(), newName.value.trim())
  newTicker.value = ''
  newName.value = ''
}

async function removeStock(id) {
  await store.removeStock(id)
}

async function saveSchedule() {
  saveMsg.value = '保存中...'
  try {
    const cron_expression = SCHEDULE_TO_CRON[scheduleForm.value.schedule_option] || '0 9 * * 1-5'
    await store.updateSchedule({
      enabled: scheduleForm.value.enabled,
      cron_expression,
      max_concurrency: scheduleForm.value.max_concurrency,
    })
    saveMsg.value = '✓ 配置已保存'
    setTimeout(() => { saveMsg.value = '' }, 2000)
  } catch (err) {
    saveMsg.value = `保存失败: ${err.message}`
  }
}

async function triggerBatch() {
  batching.value = true
  batchMsg.value = '正在启动批量分析...'
  try {
    const result = await api.startBatch()
    batchMsg.value = `批量分析已启动 (${result.total_stocks}只股票)`
    setTimeout(() => {
      router.push({ name: 'BatchRunDetail', params: { batchId: result.batch_id } })
    }, 1500)
  } catch (err) {
    batchMsg.value = `启动失败: ${err.message}`
    batching.value = false
  }
}

function formatDate(s) {
  if (!s) return '-'
  try { return new Date(s).toLocaleString('zh-CN') } catch { return s }
}
</script>