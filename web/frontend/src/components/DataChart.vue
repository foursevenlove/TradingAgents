<template>
  <div class="card">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-gray-700">K 线图表</h3>
      <span v-if="error" class="text-xs text-red-500">{{ error }}</span>
      <span v-else-if="loading" class="text-xs text-gray-400">加载中...</span>
    </div>
    <div ref="chartContainer" class="w-full h-72 rounded-lg bg-gray-50"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { createChart, CandlestickSeries, HistogramSeries } from 'lightweight-charts'

const props = defineProps({
  ticker: String,
  tradeDate: String,
})

const chartContainer = ref(null)
const loading = ref(false)
const error = ref('')
let chart = null
let candleSeries = null

async function loadData() {
  if (!props.ticker) return
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/kline/${encodeURIComponent(props.ticker)}?days=90`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const json = await res.json()
    const data = json.data || []
    if (!data.length) {
      error.value = '暂无行情数据'
      return
    }
    // Feed candle data
    candleSeries.setData(data.map(d => ({
      time: d.time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    })))

    // Mark trade date with a vertical line marker
    if (props.tradeDate) {
      const dateStr = props.tradeDate.slice(0, 10)
      const match = data.find(d => d.time >= dateStr)
      if (match) {
        candleSeries.setMarkers([{
          time: match.time,
          position: 'aboveBar',
          color: '#6366f1',
          shape: 'arrowDown',
          text: '分析日',
        }])
      }
    }

    chart.timeScale().fitContent()
  } catch (e) {
    error.value = '行情数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  chart = createChart(chartContainer.value, {
    layout: {
      background: { color: '#f9fafb' },
      textColor: '#374151',
    },
    grid: {
      vertLines: { color: '#e5e7eb' },
      horzLines: { color: '#e5e7eb' },
    },
    rightPriceScale: { borderColor: '#e5e7eb' },
    timeScale: { borderColor: '#e5e7eb', timeVisible: true },
    width: chartContainer.value.clientWidth,
    height: 288,
  })

  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: '#ef4444',
    downColor: '#22c55e',
    borderUpColor: '#ef4444',
    borderDownColor: '#22c55e',
    wickUpColor: '#ef4444',
    wickDownColor: '#22c55e',
  })

  const ro = new ResizeObserver(() => {
    if (chart && chartContainer.value) {
      chart.applyOptions({ width: chartContainer.value.clientWidth })
    }
  })
  ro.observe(chartContainer.value)

  loadData()
})

onUnmounted(() => {
  if (chart) {
    chart.remove()
    chart = null
  }
})

watch(() => props.ticker, loadData)
</script>
