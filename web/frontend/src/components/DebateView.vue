<template>
  <div class="card flex flex-col" style="max-height: 480px;">
    <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2 shrink-0">
      <span class="w-2 h-2 rounded-full bg-purple-500"></span>
      辩论环节
    </h3>

    <!-- Scrollable speech area -->
    <div ref="scrollEl" class="flex-1 overflow-y-auto space-y-3 pr-1 min-h-0">
      <div v-if="speeches.length === 0" class="text-center text-gray-400 text-sm py-6">
        等待辩论开始...
      </div>
      <div
        v-for="(sp, idx) in speeches"
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
      <div v-if="judgeDecision" class="p-3 bg-purple-50 border border-purple-200 rounded-lg">
        <div class="text-xs font-bold text-purple-700 mb-1">⚖️ 裁判决策</div>
        <div class="text-sm text-purple-900 whitespace-pre-wrap max-h-40 overflow-y-auto">{{ judgeDecision }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
})

const scrollEl = ref(null)

const speeches = computed(() =>
  props.events.filter(e => e.type === 'debate_speech').map(e => e.data)
)

const judgeDecision = computed(() => {
  const ev = props.events.find(e => e.type === 'debate_judge')
  return ev?.data?.decision || ''
})

// Auto-scroll to bottom only when new speech arrives
watch(() => speeches.value.length, async () => {
  await nextTick()
  if (scrollEl.value) {
    scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  }
})

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
