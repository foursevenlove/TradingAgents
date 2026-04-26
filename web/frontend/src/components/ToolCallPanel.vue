<template>
  <div class="card">
    <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-amber-500"></span>
      工具调用
      <span v-if="selectedAgent" class="text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded-full ml-2">
        {{ agentNameDisplay(selectedAgent) }}
        <button @click="clearSelection" class="ml-1 hover:text-primary-900">×</button>
      </span>
      <span class="text-xs text-gray-400 ml-2">({{ filteredToolCalls.length }})</span>
    </h3>
    <div class="space-y-2 max-h-60 overflow-y-auto">
      <div
        v-for="(tc, idx) in filteredToolCalls"
        :key="idx"
        class="p-2 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
      >
        <div class="flex items-center gap-2 mb-1">
          <span class="text-xs font-medium px-2 py-0.5 bg-amber-100 text-amber-700 rounded">{{ tc.tool_name }}</span>
          <span class="text-xs text-gray-400">{{ agentNameDisplay(tc.agent_name) }}</span>
        </div>
        <div class="text-xs text-gray-500 font-mono bg-gray-100 rounded px-2 py-1 overflow-x-auto">
          {{ JSON.stringify(tc.args) }}
        </div>
      </div>
      <div v-if="filteredToolCalls.length === 0" class="text-center text-gray-400 text-sm py-6">
        {{ selectedAgent ? '该 Agent 暂无工具调用' : '暂无工具调用' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
  selectedAgent: { type: String, default: '' },
})

const emit = defineEmits(['clear-selection'])

const nameMap = {
  'Market Analyst': '市场分析师',
  'Social Analyst': '社交媒体分析师',
  'News Analyst': '新闻分析师',
  'Fundamentals Analyst': '基本面分析师',
  'Bull Researcher': '多方研究员',
  'Bear Researcher': '空方研究员',
  'Research Manager': '研究经理',
  'Trader': '交易员',
  'Aggressive Analyst': '激进风控',
  'Conservative Analyst': '保守风控',
  'Neutral Analyst': '中性风控',
  'Risk Judge': '风控经理',
}

function agentNameDisplay(name) {
  return nameMap[name] || name
}

const toolCalls = computed(() => {
  return props.events
    .filter(e => e.type === 'tool_call')
    .map(e => e.data)
})

const filteredToolCalls = computed(() => {
  if (!props.selectedAgent) return toolCalls.value.slice(-20)
  return toolCalls.value.filter(tc => tc.agent_name === props.selectedAgent)
})

function clearSelection() {
  emit('clear-selection')
}
</script>
