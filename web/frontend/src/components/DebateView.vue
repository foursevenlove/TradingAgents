<template>
  <div class="card flex flex-col" :style="fullHeightStyle">
    <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2 shrink-0">
      <span class="w-2 h-2 rounded-full bg-purple-500"></span>
      辩论环节
      <span v-if="selectedAgent" class="text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded-full ml-2">
        {{ agentNameDisplay(selectedAgent) }}
        <button @click="clearSelection" class="ml-1 hover:text-primary-900">×</button>
      </span>
      <span class="text-xs text-gray-400 ml-2">({{ filteredSpeeches.length }}条发言)</span>
    </h3>

    <!-- Scrollable speech area -->
    <div ref="scrollEl" class="flex-1 flex flex-col overflow-y-auto pr-1 min-h-0 gap-3">
      <div v-if="filteredSpeeches.length === 0 && !filteredJudgeDecision" class="flex-1 flex items-center justify-center text-gray-400 text-sm">
        {{ selectedAgent ? '该 Agent 暂无辩论发言' : '等待辩论开始...' }}
      </div>
      <div
        v-for="(sp, idx) in filteredSpeeches"
        :key="idx"
        class="flex flex-1"
        :class="alignClass(sp)"
      >
        <div
          class="p-4 rounded-xl text-sm shadow-sm w-full flex flex-col"
          :class="bubbleClass(sp)"
        >
          <div class="flex items-center gap-2 mb-2 shrink-0">
            <span class="text-xs font-bold">{{ speakerLabel(sp) }}</span>
            <span class="text-xs px-1.5 py-0.5 rounded-full bg-white/50">第{{ sp.round }}轮</span>
          </div>
          <!-- Content fills remaining height -->
          <div class="flex-1 overflow-y-auto prose-custom prose prose-sm max-w-none" v-html="renderMd(sp.content)"></div>
        </div>
      </div>

      <!-- Judge decision fills remaining space -->
      <div v-if="filteredJudgeDecision" class="flex-1 flex flex-col p-4 bg-gradient-to-r from-purple-50 to-indigo-50 border-2 border-purple-300 rounded-xl shadow-md min-h-0">
        <div class="flex items-center gap-2 mb-2 shrink-0">
          <span class="text-base">⚖️</span>
          <span class="text-xs font-bold text-purple-700">裁判决策</span>
        </div>
        <div class="flex-1 overflow-y-auto text-sm text-purple-900 leading-relaxed prose-custom prose prose-sm max-w-none" v-html="renderMd(filteredJudgeDecision)"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  events: { type: Array, default: () => [] },
  selectedAgent: { type: String, default: '' },
  fullHeight: { type: Boolean, default: false },
})

const emit = defineEmits(['clear-selection'])

const scrollEl = ref(null)

function renderMd(text) {
  if (!text) return ''
  const cleaned = text.replace(/<think[\s\S]*?<\/think>/gi, '').trim()
  return marked.parse(cleaned)
}

// Fill parent container via flex, internal scroll
const fullHeightStyle = computed(() => {
  return 'height: 100%;'
})

const nameMap = {
  'Bull Researcher': '多方研究员',
  'Bear Researcher': '空方研究员',
  'Research Manager': '研究经理',
  'Aggressive Analyst': '激进风控',
  'Conservative Analyst': '保守风控',
  'Neutral Analyst': '中性风控',
  'Risk Judge': '风控经理',
}

function agentNameDisplay(name) {
  return nameMap[name] || name
}

// Map agent name to debate side
const agentToSide = {
  'Bull Researcher': 'bull',
  'Bear Researcher': 'bear',
  'Research Manager': 'judge_invest',
  'Aggressive Analyst': 'aggressive',
  'Conservative Analyst': 'conservative',
  'Neutral Analyst': 'neutral',
  'Risk Judge': 'judge_risk',
}

const speeches = computed(() =>
  props.events.filter(e => e.type === 'debate_speech').map(e => e.data)
)

const filteredSpeeches = computed(() => {
  if (!props.selectedAgent) return speeches.value
  const side = agentToSide[props.selectedAgent]
  if (!side) return speeches.value
  if (side === 'judge_invest' || side === 'judge_risk') return [] // judges don't have speeches
  return speeches.value.filter(sp => sp.side === side)
})

const judgeDecisions = computed(() =>
  props.events.filter(e => e.type === 'debate_judge').map(e => e.data)
)

const filteredJudgeDecision = computed(() => {
  if (!props.selectedAgent) {
    // Show all judge decisions when no agent selected
    return judgeDecisions.value.map(d => d.decision).join('\n\n')
  }
  // Only show judge decision if selected agent is a judge
  if (props.selectedAgent === 'Research Manager') {
    const investJudge = judgeDecisions.value.find(d => d.judge === 'Research Manager')
    return investJudge?.decision || ''
  }
  if (props.selectedAgent === 'Risk Judge') {
    const riskJudge = judgeDecisions.value.find(d => d.judge === 'Risk Manager')
    return riskJudge?.decision || ''
  }
  return ''
})

// Auto-scroll to bottom only when new speech arrives
watch(() => speeches.value.length, async () => {
  await nextTick()
  if (scrollEl.value) {
    scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  }
})

function clearSelection() {
  emit('clear-selection')
}

function alignClass(side) {
  return 'justify-start'
}

function bubbleClass(sp) {
  const map = {
    bull: 'bg-gradient-to-r from-green-50 to-green-100 border-2 border-green-300 text-green-800',
    bear: 'bg-gradient-to-r from-red-50 to-red-100 border-2 border-red-300 text-red-800',
    aggressive: 'bg-gradient-to-r from-orange-50 to-orange-100 border-2 border-orange-300 text-orange-800',
    conservative: 'bg-gradient-to-r from-blue-50 to-blue-100 border-2 border-blue-300 text-blue-800',
    neutral: 'bg-gradient-to-r from-gray-50 to-gray-100 border-2 border-gray-300 text-gray-800',
  }
  return map[sp.side] || map.neutral
}

function speakerLabel(sp) {
  const map = { bull: '多方', bear: '空方', aggressive: '激进', conservative: '保守', neutral: '中性' }
  return map[sp.side] || sp.speaker
}
</script>