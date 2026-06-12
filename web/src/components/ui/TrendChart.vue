<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: { label: string; value: number }[]
  height?: number
  color?: string
}>()

const h = computed(() => props.height || 180)
const maxVal = computed(() => Math.max(...props.data.map(d => d.value), 1))
const barW = computed(() => Math.max(20, Math.min(50, 560 / props.data.length)))
const gap = computed(() => Math.max(4, Math.min(12, (560 - props.data.length * barW.value) / (props.data.length + 1))))

function barHeight(v: number): number {
  return Math.max(2, (v / maxVal.value) * (h.value - 30))
}
</script>

<template>
  <div class="w-full">
    <svg :viewBox="`0 0 ${data.length * (barW + gap) + gap} ${h}`"
         class="w-full" :height="h" preserveAspectRatio="xMidYMid meet">
      <!-- Grid lines -->
      <line v-for="i in 4" :key="'g'+i"
        :x1="0" :y1="h - (i * (h-30) / 4)" :x2="data.length * (barW + gap) + gap"
        :y2="h - (i * (h-30) / 4)"
        stroke="var(--color-border)" stroke-width="0.5" opacity="0.3" />

      <!-- Bars -->
      <g v-for="(d, i) in data" :key="i">
        <rect
          :x="gap + i * (barW + gap)"
          :y="h - 25 - barHeight(d.value)"
          :width="barW"
          :height="barHeight(d.value)"
          :fill="color || 'var(--color-primary)'"
          rx="3"
          opacity="0.85"
          class="transition-all duration-300 hover:opacity-100"
        >
          <title>{{ d.label }}: {{ d.value.toLocaleString() }} 积分</title>
        </rect>
        <text
          :x="gap + i * (barW + gap) + barW / 2"
          :y="h - 8"
          text-anchor="middle"
          class="text-[9px] fill-[var(--color-text-muted)]"
          font-size="9"
        >{{ d.label }}</text>
        <text
          v-if="d.value > 0"
          :x="gap + i * (barW + gap) + barW / 2"
          :y="h - 30 - barHeight(d.value)"
          text-anchor="middle"
          class="text-[10px] fill-[var(--color-text)]"
          font-size="10"
          font-weight="600"
        >{{ d.value.toLocaleString() }}</text>
      </g>
    </svg>
    <div v-if="data.length === 0" class="text-sm text-[var(--color-text-muted)] text-center py-8">
      暂无趋势数据
    </div>
  </div>
</template>
