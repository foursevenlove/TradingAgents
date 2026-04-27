<template>
  <div class="card flex flex-col" :style="heightStyle">
    <div class="flex items-center justify-between mb-3 shrink-0">
      <h3 class="text-sm font-semibold text-gray-700 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-primary-500"></span>
        Agent 输出
      </h3>
      <span v-if="selectedAgent" class="text-xs px-2 py-1 bg-gradient-to-r from-primary-100 to-primary-200 text-primary-700 rounded-full">
        {{ agentNameDisplay(selectedAgent) }}
        <button @click="clearSelection" class="ml-1 hover:text-primary-900">×</button>
      </span>
      <span v-else-if="currentAgent" class="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-full">
        {{ agentNameDisplay(currentAgent) }}
      </span>
    </div>
    <div ref="scrollRef" class="flex-1 overflow-y-auto space-y-3 pr-1 min-h-0">
      <div
        v-for="(msg, idx) in filteredMessages"
        :key="idx"
        class="p-3 rounded-lg text-sm border-2 transition-colors"
        :class="contentClass(msg)"
      >
        <div class="text-xs font-medium mb-2 flex items-center gap-2" :class="headerClass(msg)">
          <span class="w-1.5 h-1.5 rounded-full"></span>
          {{ agentNameDisplay(msg.agent) }}
        </div>
        <!-- Render markdown for output, plain text for tool results -->
        <div v-if="msg.type === 'output'" class="prose-custom prose prose-sm max-w-none leading-relaxed" v-html="renderMd(msg.content)"></div>
        <div v-else class="text-gray-700 font-mono bg-gray-100/50 rounded px-2 py-1 text-xs">{{ msg.content }}</div>
      </div>
      <div v-if="filteredMessages.length === 0" class="text-center text-gray-400 text-sm py-8">
        {{ selectedAgent ? '该 Agent 暂无输出' : '等待 Agent 输出...' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  events: { type: Array, default: () => [] },
  selectedAgent: { type: String, default: '' },
  expanded: { type: Boolean, default: false },
})

const emit = defineEmits(['clear-selection'])

const scrollRef = ref(null)

// Store scroll position for each agent separately
const scrollPositions = ref({})

function renderMd(text) {
  if (!text) return ''
  const cleaned = text.replace(/<think[\s\S]*?<\/think>/gi, '').trim()
  return marked.parse(cleaned)
}

// Fill parent container via flex, internal scroll
const heightStyle = computed(() => {
  return 'height: 100%;'
})

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

// Color mapping for different agent types
const agentColors = {
  'Market Analyst': { bg: 'from-blue-50 to-blue-100', border: 'border-blue-300', header: 'text-blue-600', dot: 'bg-blue-400' },
  'Social Analyst': { bg: 'from-purple-50 to-purple-100', border: 'border-purple-300', header: 'text-purple-600', dot: 'bg-purple-400' },
  'News Analyst': { bg: 'from-orange-50 to-orange-100', border: 'border-orange-300', header: 'text-orange-600', dot: 'bg-orange-400' },
  'Fundamentals Analyst': { bg: 'from-green-50 to-green-100', border: 'border-green-300', header: 'text-green-600', dot: 'bg-green-400' },
  'Bull Researcher': { bg: 'from-emerald-50 to-emerald-100', border: 'border-emerald-300', header: 'text-emerald-600', dot: 'bg-emerald-400' },
  'Bear Researcher': { bg: 'from-red-50 to-red-100', border: 'border-red-300', header: 'text-red-600', dot: 'bg-red-400' },
  'Research Manager': { bg: 'from-indigo-50 to-indigo-100', border: 'border-indigo-300', header: 'text-indigo-600', dot: 'bg-indigo-400' },
  'Trader': { bg: 'from-cyan-50 to-cyan-100', border: 'border-cyan-300', header: 'text-cyan-600', dot: 'bg-cyan-400' },
  'Aggressive Analyst': { bg: 'from-amber-50 to-amber-100', border: 'border-amber-300', header: 'text-amber-600', dot: 'bg-amber-400' },
  'Conservative Analyst': { bg: 'from-sky-50 to-sky-100', border: 'border-sky-300', header: 'text-sky-600', dot: 'bg-sky-400' },
  'Neutral Analyst': { bg: 'from-gray-50 to-gray-100', border: 'border-gray-300', header: 'text-gray-600', dot: 'bg-gray-400' },
  'Risk Judge': { bg: 'from-violet-50 to-violet-100', border: 'border-violet-300', header: 'text-violet-600', dot: 'bg-violet-400' },
}

function contentClass(msg) {
  if (msg.type === 'tool') {
    return 'bg-gradient-to-r from-amber-50 to-amber-100 border-amber-200'
  }
  const colors = agentColors[msg.agent] || agentColors['Market Analyst']
  return `bg-gradient-to-r ${colors.bg} ${colors.border}`
}

function headerClass(msg) {
  if (msg.type === 'tool') return 'text-amber-600'
  const colors = agentColors[msg.agent] || agentColors['Market Analyst']
  return colors.header
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

// Current agent key for scroll tracking
const currentAgentKey = computed(() => {
  if (props.selectedAgent) return props.selectedAgent
  const runningAgent = currentAgent.value
  if (runningAgent) return runningAgent
  return 'default'
})

const filteredMessages = computed(() => {
  const key = currentAgentKey.value
  if (key !== 'default') {
    return messages.value.filter(m => m.agent === key)
  }
  // Default to first analyst when nothing is running
  const defaultAgent = 'Market Analyst'
  const defaultMessages = messages.value.filter(m => m.agent === defaultAgent)
  if (defaultMessages.length > 0) {
    return defaultMessages.slice(-30)
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

// Save scroll position before switching agent
watch(currentAgentKey, (newKey, oldKey) => {
  if (scrollRef.value && oldKey) {
    scrollPositions.value[oldKey] = scrollRef.value.scrollTop
  }
  // Restore scroll position for new agent
  nextTick(() => {
    if (scrollRef.value) {
      const savedPos = scrollPositions.value[newKey]
      if (savedPos !== undefined) {
        // Restore saved position
        scrollRef.value.scrollTop = savedPos
      } else {
        // New agent - show top (scrollTop = 0), not bottom
        scrollRef.value.scrollTop = 0
      }
    }
  })
})

// Auto-scroll to bottom when new content arrives for current agent (only if near bottom)
watch(() => filteredMessages.value.length, (newLen, oldLen) => {
  if (newLen > oldLen && scrollRef.value) {
    const isNearBottom = scrollRef.value.scrollHeight - scrollRef.value.scrollTop - scrollRef.value.clientHeight < 100
    if (isNearBottom) {
      nextTick(() => {
        scrollRef.value.scrollTop = scrollRef.value.scrollHeight
      })
    }
  }
})
</script>