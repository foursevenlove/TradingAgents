<template>
  <div class="card">
    <h3 class="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-primary-500"></span>
      Agent 执行流水线
    </h3>
    <div class="space-y-2">
      <div
        v-for="agent in agents"
        :key="agent.name"
        @click="selectAgent(agent)"
        class="flex items-center gap-3 p-2 rounded-lg transition-colors cursor-pointer"
        :class="agentClass(agent)"
      >
        <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
          :class="iconClass(agent)"
        >
          <template v-if="agent.status === 'completed'">&#10003;</template>
          <template v-else-if="agent.status === 'running'">
            <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          </template>
          <template v-else>{{ agent.name[0] }}</template>
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium truncate">{{ agent.name }}</div>
          <div class="text-xs text-gray-400">{{ agentStatusText(agent) }}</div>
        </div>
        <div v-if="isSelected(agent)" class="w-2 h-2 rounded-full bg-primary-500"></div>
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

const emit = defineEmits(['select-agent'])

const agentOrder = [
  'Market Analyst',
  'Social Analyst',
  'News Analyst',
  'Fundamentals Analyst',
  'Bull Researcher',
  'Bear Researcher',
  'Research Manager',
  'Trader',
  'Aggressive Analyst',
  'Conservative Analyst',
  'Neutral Analyst',
  'Risk Judge',
]

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

const agents = computed(() => {
  const statusMap = {}
  let taskCompleted = false

  for (const ev of props.events) {
    const d = ev.data
    if (ev.type === 'agent_start') {
      if (statusMap[d.agent_name] !== 'completed') {
        statusMap[d.agent_name] = 'running'
      }
    } else if (ev.type === 'agent_end') {
      statusMap[d.agent_name] = 'completed'
    } else if (ev.type === 'debate_speech') {
      // debate speech implies the speaker's agent is running
      const side = d.side
      const nameByRole = { bull: 'Bull Researcher', bear: 'Bear Researcher', aggressive: 'Aggressive Analyst', conservative: 'Conservative Analyst', neutral: 'Neutral Analyst' }
      const agentName = nameByRole[side]
      if (agentName && statusMap[agentName] !== 'completed') statusMap[agentName] = 'running'
    } else if (ev.type === 'debate_judge') {
      // judge decision means all debaters + judge are done
      const isBullBear = d.judge === 'Research Manager'
      if (isBullBear) {
        statusMap['Bull Researcher'] = 'completed'
        statusMap['Bear Researcher'] = 'completed'
        statusMap['Research Manager'] = 'completed'
      } else {
        statusMap['Aggressive Analyst'] = 'completed'
        statusMap['Conservative Analyst'] = 'completed'
        statusMap['Neutral Analyst'] = 'completed'
        statusMap['Risk Judge'] = 'completed'
      }
    } else if (ev.type === 'trader_plan') {
      // trader_plan means Trader is running (not completed yet)
      if (!statusMap['Trader']) statusMap['Trader'] = 'running'
    } else if (ev.type === 'final_decision') {
      statusMap['Trader'] = 'completed'
    } else if (ev.type === 'completed') {
      taskCompleted = true
      // mark all still-running as completed
      for (const k of Object.keys(statusMap)) {
        if (statusMap[k] === 'running') statusMap[k] = 'completed'
      }
    }
  }

  // If task is fully completed, mark ALL agents as completed
  // (handles old tasks that lack agent_start/agent_end for debate agents)
  if (taskCompleted) {
    for (const name of agentOrder) {
      statusMap[name] = 'completed'
    }
  }

  return agentOrder.map(name => ({
    name: nameMap[name] || name,
    rawName: name,
    status: statusMap[name] || 'pending',
  }))
})

function selectAgent(agent) {
  emit('select-agent', agent.rawName)
}

function isSelected(agent) {
  return props.selectedAgent === agent.rawName
}

function agentClass(agent) {
  const baseClass = 'cursor-pointer hover:shadow-sm'
  if (isSelected(agent)) return 'bg-primary-100 border border-primary-300 ' + baseClass
  if (agent.status === 'running') return 'bg-primary-50 border border-primary-200 ' + baseClass
  if (agent.status === 'completed') return 'bg-green-50 border border-green-200 ' + baseClass
  return 'bg-gray-50 border border-gray-100 ' + baseClass
}

function iconClass(agent) {
  if (agent.status === 'running') return 'bg-primary-600 text-white'
  if (agent.status === 'completed') return 'bg-green-500 text-white'
  return 'bg-gray-200 text-gray-500'
}

function agentStatusText(agent) {
  if (agent.status === 'running') return '执行中...'
  if (agent.status === 'completed') return '已完成'
  return '等待中'
}
</script>
