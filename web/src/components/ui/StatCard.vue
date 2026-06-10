<script setup lang="ts">
import { computed } from 'vue'
import { TrendingUp, TrendingDown, Minus } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  title: string
  value: string | number
  icon?: string
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  loading?: boolean
}>(), {
  loading: false,
})

const trendIcon = computed(() => {
  if (props.trend === 'up') return TrendingUp
  if (props.trend === 'down') return TrendingDown
  return Minus
})

const trendColor = computed(() => {
  if (props.trend === 'up') return 'text-brand-success'
  if (props.trend === 'down') return 'text-brand-danger'
  return 'text-[var(--color-text-muted)]'
})
</script>

<template>
  <div class="card-hover p-5">
    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-3 animate-pulse">
      <div class="h-4 w-24 bg-[var(--color-border)] rounded" />
      <div class="h-8 w-32 bg-[var(--color-border)] rounded" />
      <div class="h-3 w-16 bg-[var(--color-border)] rounded" />
    </div>

    <!-- Content -->
    <template v-else>
      <div class="flex items-start justify-between">
        <div class="space-y-1">
          <p class="text-sm font-medium text-[var(--color-text-muted)]">{{ title }}</p>
          <p class="text-2xl font-bold text-[var(--color-text)]">{{ value }}</p>
        </div>
        <div
          v-if="trend"
          :class="[trendColor, 'flex items-center gap-1 text-xs font-medium']"
        >
          <component :is="trendIcon" class="w-3.5 h-3.5" />
          <span>{{ trendValue }}</span>
        </div>
      </div>
    </template>
  </div>
</template>
