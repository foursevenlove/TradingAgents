<template>
  <div class="card">
    <h3 class="text-sm font-semibold text-gray-700 mb-4">因子评分</h3>
    <div class="space-y-4">
      <div v-for="factor in factors" :key="factor.name">
        <div class="flex justify-between text-sm mb-1">
          <span class="text-gray-600">{{ factor.name }}</span>
          <span :class="factor.score > 0 ? 'text-bull-600' : factor.score < 0 ? 'text-bear-600' : 'text-gray-500'">
            {{ factor.score > 0 ? '+' : '' }}{{ factor.score }}
          </span>
        </div>
        <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="factor.score > 0 ? 'bg-bull-500' : 'bg-bear-500'"
            :style="{ width: Math.min(Math.abs(factor.score) * 10, 100) + '%', marginLeft: factor.score < 0 ? 'auto' : '0', marginRight: factor.score > 0 ? 'auto' : '0' }"
          ></div>
        </div>
      </div>
      <div v-if="factors.length === 0" class="text-center text-gray-400 text-sm py-4">
        暂无评分数据
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: { type: Object, default: null },
})

const factors = computed(() => {
  // Derive simple factor scores from reports if available
  const r = props.result
  if (!r) return []
  const out = []
  if (r.market_report) {
    const score = r.market_report.includes('涨') || r.market_report.includes('bull') ? 1 : r.market_report.includes('跌') || r.market_report.includes('bear') ? -1 : 0
    out.push({ name: '技术面', score })
  }
  if (r.sentiment_report) {
    const score = r.sentiment_report.includes('积极') || r.sentiment_report.includes('乐观') ? 1 : r.sentiment_report.includes('消极') || r.sentiment_report.includes('悲观') ? -1 : 0
    out.push({ name: '情绪面', score })
  }
  if (r.fundamentals_report) {
    const score = r.fundamentals_report.includes('增长') || r.fundamentals_report.includes('向好') ? 1 : r.fundamentals_report.includes('下滑') || r.fundamentals_report.includes('恶化') ? -1 : 0
    out.push({ name: '基本面', score })
  }
  if (r.news_report) {
    const score = r.news_report.includes('利好') || r.news_report.includes('positive') ? 1 : r.news_report.includes('利空') || r.news_report.includes('negative') ? -1 : 0
    out.push({ name: '消息面', score })
  }
  return out
})
</script>
