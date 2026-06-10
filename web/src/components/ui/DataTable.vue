<script setup lang="ts">
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-vue-next'

interface Column {
  key: string
  label: string
  sortable?: boolean
  width?: string
  align?: 'left' | 'center' | 'right'
}

interface Action {
  label: string
  icon?: string
  variant?: 'primary' | 'danger' | 'default'
  handler: (row: any) => void
}

const props = withDefaults(defineProps<{
  columns: Column[]
  data: any[]
  loading?: boolean
  actions?: Action[]
  emptyText?: string
}>(), {
  loading: false,
  emptyText: '暂无数据',
})

const emit = defineEmits<{
  sort: [key: string, direction: 'asc' | 'desc']
}>()

const sortState: Record<string, 'asc' | 'desc'> = {}

function handleSort(key: string) {
  const direction = sortState[key] === 'asc' ? 'desc' : 'asc'
  sortState[key] = direction
  emit('sort', key, direction)
}

function getSortIcon(key: string) {
  if (!sortState[key]) return ChevronsUpDown
  return sortState[key] === 'asc' ? ChevronUp : ChevronDown
}
</script>

<template>
  <div class="card overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <!-- Header -->
        <thead>
          <tr class="border-b border-[var(--color-border)]">
            <th
              v-for="col in columns"
              :key="col.key"
              :class="[
                'px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]',
                col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
              ]"
              :style="col.width ? { width: col.width } : undefined"
            >
              <div
                :class="[
                  'flex items-center gap-1',
                  col.sortable && 'cursor-pointer select-none hover:text-[var(--color-text)]',
                ]"
                @click="col.sortable && handleSort(col.key)"
              >
                <span>{{ col.label }}</span>
                <component
                  v-if="col.sortable"
                  :is="getSortIcon(col.key)"
                  class="w-3.5 h-3.5"
                />
              </div>
            </th>
            <th v-if="actions && actions.length" class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              操作
            </th>
          </tr>
        </thead>

        <!-- Body -->
        <tbody>
          <!-- Loading -->
          <tr v-if="loading">
            <td :colspan="columns.length + (actions?.length ? 1 : 0)" class="px-4 py-12">
              <div class="flex justify-center">
                <div class="loading-spinner" />
              </div>
            </td>
          </tr>

          <!-- Empty state -->
          <tr v-else-if="!data.length">
            <td :colspan="columns.length + (actions?.length ? 1 : 0)" class="px-4 py-12">
              <div class="flex flex-col items-center gap-2 text-[var(--color-text-muted)]">
                <span class="text-sm">{{ emptyText }}</span>
              </div>
            </td>
          </tr>

          <!-- Data rows -->
          <tr
            v-for="(row, rowIdx) in data"
            :key="row.id || rowIdx"
            class="border-b border-[var(--color-border)] last:border-b-0 hover:bg-[var(--color-bg)]/50 transition-colors duration-150"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              :class="[
                'px-4 py-3 text-sm',
                col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
                'text-[var(--color-text)]',
              ]"
            >
              <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
                {{ row[col.key] }}
              </slot>
            </td>

            <!-- Actions -->
            <td v-if="actions && actions.length" class="px-4 py-3">
              <div class="flex items-center justify-end gap-2">
                <button
                  v-for="action in actions"
                  :key="action.label"
                  :class="[
                    'px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-150',
                    action.variant === 'primary'
                      ? 'text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10'
                      : action.variant === 'danger'
                        ? 'text-brand-danger hover:bg-brand-danger/10'
                        : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)]',
                  ]"
                  @click="action.handler(row)"
                >
                  {{ action.label }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Footer slot for pagination -->
    <div v-if="$slots.footer" class="border-t border-[var(--color-border)] px-4 py-3">
      <slot name="footer" />
    </div>
  </div>
</template>
