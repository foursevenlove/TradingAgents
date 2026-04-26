<template>
  <div class="card flex flex-col h-80">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-gray-700 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-primary-500"></span>
        Agent 输出
      </h3>
      <span v-if="selectedAgent" class="text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded-full">
        {{ agentNameDisplay(selectedAgent) }}
        <button @click="clearSelection" class="ml-1 hover:text-primary-900">×</button>
      </span>
      <span v-else-if="currentAgent" class="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-full">
        {{ agentNameDisplay(currentAgent) }}
      </span>
    </div>
    <div ref="scrollRef" class="flex-1 overflow-y-auto space-y-3 pr-1">
      <div
        v-for="(msg, idx) in filteredMessages"
        :key="idx"
        class="p-3 rounded-lg text-sm"
        :class="msg.type === 'tool' ? 'bg-amber-50 border border-amber-100' : 'bg-gray-50 border border-gray-100'"
      >
        <div class="text-xs text-gray-400 mb-1">{{ agentNameDisplay(msg.agent) }}</div>
        <div class="text-gray-700 whitespace-pre-wrap leading-relaxed">{{ msg.content }}</div>
      </div>
      <div v-if="filteredMessages.length === 0" class="text-center text-gray-400 text-sm py-10">
        {{ selectedAgent ? '该 Agent 暂无输出' : '等待 Agent 输出...' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
  selectedAgent: { type: String, default: '' },
})

const emit = defineEmits(['clear-selection'])

const scrollRef = ref(null)

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

const messages = computed(() => {
  const out = []
  for (const ev of props.events) {
    if (ev.type === 'agent_output') {
      out.push({
        type: 'output',
        agent: ev.data.agent_name,
        content: ev.data.content,
      })
    } else if (ev.type === 'tool_result') {
      out.push({
        type: 'tool',
        agent: ev.data.agent_name,
        content: `[${ev.data.tool_name}] ${ev.data.result_preview}`,
      })
    }
  }
  return out.slice(-50)
})

const filteredMessages = computed(() => {
  if (props.selectedAgent) {
    return messages.value.filter(m => m.agent === props.selectedAgent)
  }
  // When no agent selected, show only the current running agent's output
  const runningAgent = currentAgent.value
  if (runningAgent) {
    return messages.value.filter(m => m.agent === runningAgent).slice(-30)
  }
  return messages.value.slice(-30)
})

const currentAgent = computed(() => {
  for (let i = props.events.length - 1; i >= 0; i--) {
    const ev = props.events[i]
    if (ev.type === 'agent_start') return ev.data.agent_name
  }
  return null
})

function clearSelection() {
  emit('clear-selection')
}

watch(() => props.events.length, () => {
  nextTick(() => {
    if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  })
})
</script>
