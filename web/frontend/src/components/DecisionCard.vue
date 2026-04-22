<template>
  <div class="card">
    <h3 class="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full" :class="signalColorDot"></span>
      最终决策
    </h3>
    <div class="flex items-start gap-4">
      <div
        class="w-20 h-20 shrink-0 rounded-2xl flex items-center justify-center text-2xl font-bold text-white shadow-lg"
        :class="signalColorBg"
      >
        {{ signalText }}
      </div>
      <div class="flex-1 min-w-0">
        <div class="text-lg font-bold mb-2" :class="signalColorText">{{ signalLabel }}</div>
        <div
          class="text-sm text-gray-600 leading-relaxed prose prose-sm max-w-none"
          v-html="renderedContent"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  signal: { type: String, default: '' },
  content: { type: String, default: '' },
})

function stripThink(text) {
  return (text || '').replace(/<think>[\s\S]*?<\/think>/gi, '').replace(/<\/think>/gi, '').trim()
}

const signalUpper = computed(() => stripThink(props.signal || '').toUpperCase())

const signalText = computed(() => {
  const s = signalUpper.value
  // Try to extract explicit signal from the end of text first
  const lines = s.split('\n').map(l => l.trim()).filter(Boolean)
  const lastLine = lines[lines.length - 1] || ''
  if (lastLine === 'BUY' || lastLine === 'SELL' || lastLine === 'HOLD') {
    return lastLine
  }
  // Fallback: search whole text
  if (s.includes('SELL')) return 'SELL'
  if (s.includes('BUY')) return 'BUY'
  return 'HOLD'
})

const signalLabel = computed(() => {
  const map = { BUY: '买入信号', SELL: '卖出信号', HOLD: '持有观望' }
  return map[signalText.value] || '未知'
})

// Strip <think>...</think> blocks and render markdown
const renderedContent = computed(() => {
  const text = (props.content || '').replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  return marked.parse(text)
})

const signalColorBg = computed(() => {
  const map = { BUY: 'bg-bull-500', SELL: 'bg-bear-500', HOLD: 'bg-amber-500' }
  return map[signalText.value] || 'bg-gray-500'
})

const signalColorText = computed(() => {
  const map = { BUY: 'text-bull-600', SELL: 'text-bear-600', HOLD: 'text-amber-600' }
  return map[signalText.value] || 'text-gray-600'
})

const signalColorDot = computed(() => {
  const map = { BUY: 'bg-bull-500', SELL: 'bg-bear-500', HOLD: 'bg-amber-500' }
  return map[signalText.value] || 'bg-gray-500'
})
</script>
