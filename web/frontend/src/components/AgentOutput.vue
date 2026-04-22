<template>
  <div class="card flex flex-col h-80">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-gray-700 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-primary-500"></span>
        Agent 输出
      </h3>
      <span v-if="currentAgent" class="text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded-full">
        {{ currentAgent }}
      </span>
    </div>
    <div ref="scrollRef" class="flex-1 overflow-y-auto space-y-3 pr-1">
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="p-3 rounded-lg text-sm"
        :class="msg.type === 'tool' ? 'bg-amber-50 border border-amber-100' : 'bg-gray-50 border border-gray-100'"
      >
        <div class="text-xs text-gray-400 mb-1">{{ msg.agent }}</div>
        <div class="text-gray-700 whitespace-pre-wrap leading-relaxed">{{ msg.content }}</div>
      </div>
      <div v-if="messages.length === 0" class="text-center text-gray-400 text-sm py-10">
        等待 Agent 输出...
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
})

const scrollRef = ref(null)

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
  return out.slice(-30)
})

const currentAgent = computed(() => {
  for (let i = props.events.length - 1; i >= 0; i--) {
    const ev = props.events[i]
    if (ev.type === 'agent_start') return ev.data.agent_name
  }
  return null
})

watch(() => props.events.length, () => {
  nextTick(() => {
    if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  })
})
</script>
