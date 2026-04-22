<template>
  <div class="card">
    <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-amber-500"></span>
      工具调用 ({{ toolCalls.length }})
    </h3>
    <div class="space-y-2 max-h-60 overflow-y-auto">
      <div
        v-for="(tc, idx) in toolCalls"
        :key="idx"
        class="p-2 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
      >
        <div class="flex items-center gap-2 mb-1">
          <span class="text-xs font-medium px-2 py-0.5 bg-amber-100 text-amber-700 rounded">{{ tc.tool_name }}</span>
          <span class="text-xs text-gray-400">{{ tc.agent_name }}</span>
        </div>
        <div class="text-xs text-gray-500 font-mono bg-gray-100 rounded px-2 py-1 overflow-x-auto">
          {{ JSON.stringify(tc.args) }}
        </div>
      </div>
      <div v-if="toolCalls.length === 0" class="text-center text-gray-400 text-sm py-6">
        暂无工具调用
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
})

const toolCalls = computed(() => {
  return props.events
    .filter(e => e.type === 'tool_call')
    .map(e => e.data)
    .slice(-20)
})
</script>
