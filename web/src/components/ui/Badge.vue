<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  status?: string
  type?: string
  label?: string
  size?: 'sm' | 'md'
}>(), {
  size: 'md',
})

const colorMap: Record<string, string> = {
  active: 'bg-brand-success/10 text-brand-success border-brand-success/20',
  inactive: 'bg-[var(--color-border)]/30 text-[var(--color-text-muted)] border-[var(--color-border)]',
  pending: 'bg-brand-warning/10 text-brand-warning border-brand-warning/20',
  processing: 'bg-brand-info/10 text-brand-info border-brand-info/20',
  completed: 'bg-brand-success/10 text-brand-success border-brand-success/20',
  delivered: 'bg-brand-success/10 text-brand-success border-brand-success/20',
  cancelled: 'bg-brand-danger/10 text-brand-danger border-brand-danger/20',
  failed: 'bg-brand-danger/10 text-brand-danger border-brand-danger/20',
  error: 'bg-brand-danger/10 text-brand-danger border-brand-danger/20',
  success: 'bg-brand-success/10 text-brand-success border-brand-success/20',
}

const labelMap: Record<string, string> = {
  active: '启用',
  inactive: '停用',
  pending: '待处理',
  processing: '处理中',
  shipped: '已发货',
  delivered: '已送达',
  cancelled: '已取消',
  completed: '已完成',
  failed: '失败',
  error: '异常',
  success: '成功',
}

const effectiveStatus = computed(() => props.status || props.type || '')
const badgeClass = computed(() => colorMap[effectiveStatus.value] || 'bg-[var(--color-border)]/30 text-[var(--color-text-muted)]')
const displayLabel = computed(() => props.label || labelMap[effectiveStatus.value] || effectiveStatus.value)
const sizeClass = computed(() => props.size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2.5 py-1 text-xs')
</script>

<template>
  <span
    :class="[
      'inline-flex items-center font-medium rounded-full border',
      badgeClass,
      sizeClass,
    ]"
  >
    {{ displayLabel }}
  </span>
</template>
