<template>
  <div class="card flex flex-col" style="max-height: 480px;">
    <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2 shrink-0">
      <span class="w-2 h-2 rounded-full bg-purple-500"></span>
      辩论环节
      <span v-if="selectedAgent" class="text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded-full ml-2">
        {{ agentNameDisplay(selectedAgent) }}
        <button @click="clearSelection" class="ml-1 hover:text-primary-900">×</button>
      </span>
    </h3>

    <!-- Scrollable speech area -->
    <div ref="scrollEl" class="flex-1 overflow-y-auto space-y-3 pr-1 min-h-0">
      <div v-if="filteredSpeeches.length === 0 && !filteredJudgeDecision" class="text-center text-gray-400 text-sm py-6">
        {{ selectedAgent ? '该 Agent 暂无辩论发言' : '等待辩论开始...' }}
      </div>
      <div
        v-for="(sp, idx) in filteredSpeeches"
        :key="idx"
        class="flex"
        :class="alignClass(sp.side)"
      >
        <div
          class="max-w-[85%] p-3 rounded-xl text-sm"
          :class="bubbleClass(sp)"
        >
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-bold">{{ speakerLabel(sp) }}</span>
            <span class="text-xs opacity-60">第{{ sp.round }}轮</span>
          </div>
          <!-- Content with its own scroll if very long -->
          <div class="leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">{{ sp.content }}</div>
        </div>
      </div>

      <!-- Judge decision inline at bottom of scroll area -->
      <div v-if="filteredJudgeDecision" class="p-3 bg-purple-50 border border-purple-200 rounded-lg">
        <div class="text-xs font-bold text-purple-700 mb-1">⚖️ 裁判决策</div>
        <div class="text-sm text-purple-900 whitespace-pre-wrap max-h-40 overflow-y-auto">{{ filteredJudgeDecision }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
  selectedAgent: { type: String, default: '' },
})

const emit = defineEmits(['clear-selection'])

const scrollEl = ref(null)

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
  // Bull/Aggressive → left, Bear/Conservative → right, Neutral → center
  if (side === 'bull' || side === 'aggressive') return 'justify-start'
  if (side === 'bear' || side === 'conservative') return 'justify-end'
  return 'justify-center'
}

function bubbleClass(sp) {
  const map = {
    bull: 'bg-green-50 border border-green-200 text-green-800',
    bear: 'bg-red-50 border border-red-200 text-red-800',
    aggressive: 'bg-orange-50 border border-orange-200 text-orange-800',
    conservative: 'bg-blue-50 border border-blue-200 text-blue-800',
    neutral: 'bg-gray-50 border border-gray-200 text-gray-800',
  }
  return map[sp.side] || map.neutral
}

function speakerLabel(sp) {
  const map = { bull: '多方', bear: '空方', aggressive: '激进', conservative: '保守', neutral: '中性' }
  return map[sp.side] || sp.speaker
}
</script>
