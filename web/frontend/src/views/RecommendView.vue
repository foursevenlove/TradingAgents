<template>
  <div class="max-w-5xl mx-auto px-4 py-8">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">股票推荐</h1>
      <p class="text-gray-500 mt-1">AI热点主题分析 + 数据驱动选股</p>
    </div>

    <!-- Mode Tabs -->
    <div class="flex gap-2 mb-6">
      <button
        @click="switchMode('daily')"
        :class="mode === 'daily' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'"
        class="px-4 py-2 rounded-lg font-medium transition-colors"
      >
        每日推荐
      </button>
      <button
        @click="switchMode('weekly')"
        :class="mode === 'weekly' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'"
        class="px-4 py-2 rounded-lg font-medium transition-colors"
      >
        每周深度
      </button>
      <button
        @click="switchMode('top')"
        :class="mode === 'top' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'"
        class="px-4 py-2 rounded-lg font-medium transition-colors"
      >
        涨幅榜
      </button>
    </div>

    <!-- Cached Result Notice -->
    <div v-if="hasCachedData && !isLoading" class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between">
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="text-sm text-blue-700">
          显示上次生成结果：{{ cachedTimestamp }}
          <span v-if="cachedTradeDate">（{{ cachedTradeDate }}）</span>
        </span>
      </div>
      <button @click="refreshData" class="text-sm text-blue-600 hover:text-blue-800 font-medium">
        重新生成
      </button>
    </div>

    <!-- Daily/Weekly Config -->
    <div v-if="mode === 'daily' || mode === 'weekly'" class="card mb-6">
      <div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            {{ mode === 'daily' ? '交易日期' : '周起始日期' }}
          </label>
          <input
            v-model="tradeDate"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">最大主题数</label>
          <select v-model="maxThemes" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
            <option :value="3">3</option>
            <option :value="5">5</option>
            <option :value="10">10</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">每主题股票数</label>
          <select v-model="maxStocks" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
            <option :value="3">3</option>
            <option :value="5">5</option>
            <option :value="10">10</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">最小成交额</label>
          <select v-model="minAmount" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
            <option :value="1e8">1亿</option>
            <option :value="5e8">5亿</option>
            <option :value="10e8">10亿</option>
          </select>
        </div>
      </div>

      <div class="mt-4 flex justify-end gap-2">
        <button
          @click="fetchRecommendations(true)"
          :disabled="isLoading"
          class="btn-secondary flex items-center gap-2"
        >
          重新生成
        </button>
        <button
          @click="fetchRecommendations(false)"
          :disabled="isLoading"
          class="btn-primary flex items-center gap-2"
        >
          <span v-if="isLoading" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          {{ isLoading ? '生成中...' : '生成推荐' }}
        </button>
      </div>
    </div>

    <!-- Top Gainers Config -->
    <div v-if="mode === 'top'" class="card mb-6">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">最小成交额</label>
          <select v-model="minAmount" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
            <option :value="1e8">1亿</option>
            <option :value="5e8">5亿</option>
            <option :value="10e8">10亿</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">显示数量</label>
          <select v-model="topN" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </div>
        <div class="flex items-end gap-2">
          <button
            @click="fetchTopGainers(false)"
            :disabled="isLoading"
            class="btn-secondary flex items-center gap-2"
          >
            重新获取
          </button>
          <button
            @click="fetchTopGainers(true)"
            :disabled="isLoading"
            class="btn-primary flex items-center gap-2"
          >
            <span v-if="isLoading" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
            {{ isLoading ? '加载中...' : '查询涨幅榜' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
      {{ error }}
    </div>

    <!-- Themes Section -->
    <div v-if="themes.length > 0" class="mb-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-3">热点主题</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="theme in themes"
          :key="theme.name"
          class="card hover:shadow-md transition-shadow"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="font-semibold text-gray-900">{{ theme.name }}</span>
            <span
              class="px-2 py-1 text-xs font-medium rounded-full"
              :class="getConfidenceClass(theme.confidence)"
            >
              {{ (theme.confidence * 100).toFixed(0) }}%
            </span>
          </div>
          <p class="text-sm text-gray-500 mb-2">{{ theme.reason }}</p>
          <div class="flex flex-wrap gap-1">
            <span
              v-for="kw in theme.keywords?.slice(0, 5)"
              :key="kw"
              class="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded"
            >
              {{ kw }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Stocks Section -->
    <div v-if="Object.keys(stocksByTheme).length > 0" class="mb-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-3">推荐股票</h2>
      <div
        v-for="(stocks, themeName) in stocksByTheme"
        :key="themeName"
        class="mb-4"
      >
        <h3 class="text-md font-medium text-gray-700 mb-2">{{ themeName }}</h3>
        <div class="overflow-x-auto">
          <table class="w-full bg-white rounded-lg shadow-sm">
            <thead class="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th class="px-4 py-3 text-left">代码</th>
                <th class="px-4 py-3 text-left">名称</th>
                <th class="px-4 py-3 text-right">价格</th>
                <th class="px-4 py-3 text-right">涨幅</th>
                <th class="px-4 py-3 text-left">行业</th>
                <th v-if="hasAnalysis" class="px-4 py-3 text-center">决策</th>
                <th v-if="hasAnalysis" class="px-4 py-3 text-center">置信度</th>
                <th class="px-4 py-3 text-left">推荐理由</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="stock in stocks" :key="stock.code" class="hover:bg-gray-50">
                <td class="px-4 py-3 text-sm font-medium text-primary-600">
                  <router-link :to="`/?ticker=${stock.code}`" class="hover:underline">
                    {{ stock.code }}
                  </router-link>
                </td>
                <td class="px-4 py-3 text-sm text-gray-900">{{ stock.name }}</td>
                <td class="px-4 py-3 text-sm text-gray-900 text-right">{{ stock.price?.toFixed(2) }}</td>
                <td class="px-4 py-3 text-sm text-right font-medium" :class="stock.change_pct >= 0 ? 'text-red-500' : 'text-green-500'">
                  {{ stock.change_pct?.toFixed(2) }}%
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">{{ stock.industry?.slice(0, 15) }}</td>
                <td v-if="hasAnalysis" class="px-4 py-3 text-center">
                  <span
                    v-if="stock.decision"
                    class="px-2 py-1 text-xs font-medium rounded"
                    :class="getDecisionClass(stock.decision)"
                  >
                    {{ stock.decision }}
                  </span>
                  <span v-else class="text-gray-400">-</span>
                </td>
                <td v-if="hasAnalysis" class="px-4 py-3 text-center text-sm">
                  {{ stock.confidence ? (stock.confidence * 100).toFixed(0) + '%' : '-' }}
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">{{ stock.reason?.slice(0, 30) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Top Gainers Table -->
    <div v-if="topGainers.length > 0" class="mb-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-3">涨幅榜 TOP {{ topN }}</h2>
      <div class="overflow-x-auto">
        <table class="w-full bg-white rounded-lg shadow-sm">
          <thead class="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th class="px-4 py-3 text-center">排名</th>
              <th class="px-4 py-3 text-left">代码</th>
              <th class="px-4 py-3 text-left">名称</th>
              <th class="px-4 py-3 text-right">价格</th>
              <th class="px-4 py-3 text-right">涨幅</th>
              <th class="px-4 py-3 text-right">成交额</th>
              <th class="px-4 py-3 text-right">评分</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="(stock, idx) in topGainers" :key="stock.code" class="hover:bg-gray-50">
              <td class="px-4 py-3 text-sm text-gray-500 text-center">{{ idx + 1 }}</td>
              <td class="px-4 py-3 text-sm font-medium text-primary-600">
                <router-link :to="`/?ticker=${stock.code}`" class="hover:underline">
                  {{ stock.code }}
                </router-link>
              </td>
              <td class="px-4 py-3 text-sm text-gray-900">{{ stock.name }}</td>
              <td class="px-4 py-3 text-sm text-gray-900 text-right">{{ stock.price?.toFixed(2) }}</td>
              <td class="px-4 py-3 text-sm text-right font-medium text-red-500">
                {{ stock.change_pct?.toFixed(2) }}%
              </td>
              <td class="px-4 py-3 text-sm text-gray-500 text-right">
                {{ formatAmount(stock.amount) }}
              </td>
              <td class="px-4 py-3 text-sm text-right">
                <span class="px-2 py-1 bg-primary-100 text-primary-700 rounded text-xs font-medium">
                  {{ stock.score?.toFixed(1) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!isLoading && themes.length === 0 && topGainers.length === 0 && Object.keys(stocksByTheme).length === 0" class="text-center py-12 text-gray-500">
      <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.755-.988-2.364l-.548-.547z" />
      </svg>
      <p>点击上方按钮生成推荐</p>
    </div>

    <!-- Timestamp -->
    <div v-if="timestamp" class="text-center text-sm text-gray-400 mt-6">
      生成时间: {{ timestamp }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api.js'

// Mode
const mode = ref('daily')

// Config
const tradeDate = ref(new Date().toISOString().split('T')[0])
const maxThemes = ref(5)
const maxStocks = ref(5)
const minAmount = ref(1e8)
const topN = ref(20)

// State
const isLoading = ref(false)
const error = ref('')
const themes = ref([])
const stocksByTheme = ref({})
const analysisResults = ref({})
const topGainers = ref([])
const timestamp = ref('')

// Cached data tracking
const hasCachedData = ref(false)
const cachedTimestamp = ref('')
const cachedTradeDate = ref('')

// Computed
const hasAnalysis = computed(() => Object.keys(analysisResults.value).length > 0)

// ── Initialize on mount ──────────────────────────────────────────────────

onMounted(async () => {
  await loadCachedResults()
})

async function loadCachedResults() {
  isLoading.value = true
  error.value = ''

  try {
    const result = await api.getLatestRecommendations()

    // Load cached daily
    if (result.daily) {
      if (mode.value === 'daily') {
        displayDailyResult(result.daily)
      }
    }

    // Load cached weekly
    if (result.weekly) {
      if (mode.value === 'weekly') {
        displayWeeklyResult(result.weekly)
      }
    }

    // Load cached top
    if (result.top) {
      if (mode.value === 'top') {
        displayTopResult(result.top)
      }
    }

    // Store all cached data for switching modes
    cachedData.daily = result.daily
    cachedData.weekly = result.weekly
    cachedData.top = result.top

  } catch (e) {
    error.value = e.message || '获取缓存数据失败'
  } finally {
    isLoading.value = false
  }
}

// Store cached data for mode switching
const cachedData = {
  daily: null,
  weekly: null,
  top: null,
}

function switchMode(newMode) {
  mode.value = newMode
  hasCachedData.value = false

  // Load cached data for new mode if available
  if (cachedData[newMode]) {
    if (newMode === 'daily') {
      displayDailyResult(cachedData.daily)
    } else if (newMode === 'weekly') {
      displayWeeklyResult(cachedData.weekly)
    } else if (newMode === 'top') {
      displayTopResult(cachedData.top)
    }
  } else {
    // Clear current data
    themes.value = []
    stocksByTheme.value = {}
    topGainers.value = []
    analysisResults.value = {}
    timestamp.value = ''
  }
}

// ── Display helpers ──────────────────────────────────────────────────────

function displayDailyResult(result) {
  themes.value = result.themes || []
  stocksByTheme.value = result.stocks || {}
  analysisResults.value = result.analysis || {}
  topGainers.value = []
  timestamp.value = result.timestamp || result.saved_at || ''
  cachedTradeDate.value = result.trade_date || ''

  if (timestamp.value) {
    hasCachedData.value = true
    cachedTimestamp.value = timestamp.value
  }
}

function displayWeeklyResult(result) {
  themes.value = result.themes || []
  stocksByTheme.value = result.stocks || {}
  analysisResults.value = result.analysis || {}
  topGainers.value = []
  timestamp.value = result.timestamp || result.saved_at || ''
  cachedTradeDate.value = `${result.week_start || ''} ~ ${result.week_end || ''}`

  if (timestamp.value) {
    hasCachedData.value = true
    cachedTimestamp.value = timestamp.value
  }
}

function displayTopResult(result) {
  themes.value = []
  stocksByTheme.value = {}
  analysisResults.value = {}
  topGainers.value = result.stocks || []
  timestamp.value = result.timestamp || result.saved_at || ''
  cachedTradeDate.value = result.trade_date || ''

  if (timestamp.value) {
    hasCachedData.value = true
    cachedTimestamp.value = timestamp.value
  }
}

// ── Data fetching ────────────────────────────────────────────────────────

function getConfidenceClass(confidence) {
  if (confidence >= 0.85) return 'bg-green-100 text-green-700'
  if (confidence >= 0.7) return 'bg-yellow-100 text-yellow-700'
  return 'bg-gray-100 text-gray-700'
}

function getDecisionClass(decision) {
  if (decision === 'buy') return 'bg-red-100 text-red-700'
  if (decision === 'sell') return 'bg-green-100 text-green-700'
  return 'bg-gray-100 text-gray-700'
}

function formatAmount(amount) {
  if (!amount) return '-'
  if (amount >= 1e8) return (amount / 1e8).toFixed(1) + '亿'
  if (amount >= 1e4) return (amount / 1e4).toFixed(0) + '万'
  return amount.toFixed(0)
}

async function fetchRecommendations(useCache = false) {
  isLoading.value = true
  error.value = ''
  themes.value = []
  stocksByTheme.value = {}
  analysisResults.value = {}
  hasCachedData.value = false

  try {
    const params = new URLSearchParams({
      trade_date: tradeDate.value,
      max_themes: maxThemes.value,
      max_stocks: maxStocks.value,
      min_amount: minAmount.value,
    })

    if (mode.value === 'daily') {
      // useCache=true means don't force refresh (use cached if available)
      // useCache=false means force refresh (generate new)
      if (!useCache) {
        params.append('refresh', 'true')
      }
      const result = await api.getDailyRecommend(params.toString())
      displayDailyResult(result)
      cachedData.daily = result
    } else {
      if (!useCache) {
        params.append('refresh', 'true')
      }
      const result = await api.getWeeklyRecommend(params.toString())
      displayWeeklyResult(result)
      cachedData.weekly = result
    }
  } catch (e) {
    error.value = e.message || '获取推荐失败'
  } finally {
    isLoading.value = false
  }
}

async function fetchTopGainers(useCache = true) {
  isLoading.value = true
  error.value = ''
  topGainers.value = []
  hasCachedData.value = false

  try {
    const params = new URLSearchParams({
      min_amount: minAmount.value,
      top_n: topN.value,
    })

    // useCache=true: don't force refresh
    // useCache=false: force refresh
    if (!useCache) {
      params.append('refresh', 'true')
    }

    const result = await api.getTopGainers(params.toString())
    displayTopResult(result)
    cachedData.top = result
  } catch (e) {
    error.value = e.message || '获取涨幅榜失败'
  } finally {
    isLoading.value = false
  }
}

async function refreshData() {
  // Force refresh for current mode
  if (mode.value === 'top') {
    await fetchTopGainers(false)
  } else {
    await fetchRecommendations(false)
  }
}
</script>