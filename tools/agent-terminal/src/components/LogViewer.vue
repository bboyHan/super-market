<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const props = defineProps<{
  logs: string[]
  maxHeight?: string
}>()

const autoScroll = ref(true)
const logContainer = ref<HTMLElement | null>(null)

watch(
  () => props.logs.length,
  async () => {
    if (autoScroll.value) {
      await nextTick()
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight
      }
    }
  }
)

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value
}

function logColorClass(log: string): string {
  if (log.includes('ERROR') || log.includes('error') || log.includes('fail')) return 'log-error'
  if (log.includes('WARN') || log.includes('warn')) return 'log-warn'
  if (log.includes('SUCCESS') || log.includes('success') || log.includes('done') || log.includes('completed')) return 'log-success'
  if (log.includes('INFO') || log.includes('info')) return 'log-info'
  if (log.includes('DEBUG') || log.includes('debug')) return 'log-debug'
  return 'log-info'
}

function formatTimestamp(): string {
  return new Date().toLocaleTimeString()
}
</script>

<template>
  <div class="log-viewer">
    <div class="log-toolbar">
      <span class="log-count">{{ logs.length }} entries</span>
      <button class="log-toggle" @click="toggleAutoScroll">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="23 18 17 24 11 18" />
          <path d="M17 24V2" />
        </svg>
        <span>{{ autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF' }}</span>
      </button>
    </div>
    <div
      ref="logContainer"
      class="log-content"
      :style="{ maxHeight: maxHeight || '300px' }"
    >
      <div v-if="logs.length === 0" class="log-empty">
        No log entries yet. Start a task to see output.
      </div>
      <div
        v-for="(log, index) in logs"
        :key="index"
        class="log-entry"
        :class="logColorClass(log)"
      >
        <span class="log-time">{{ formatTimestamp() }}</span>
        <span class="log-text">{{ log }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.log-viewer {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-input);
}

.log-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.log-count {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.log-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.log-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.log-content {
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.log-empty {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.log-entry {
  display: flex;
  gap: 8px;
  padding: 3px 6px;
  border-radius: 3px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  line-height: 1.5;
}

.log-entry:hover {
  background: rgba(255, 255, 255, 0.03);
}

.log-time {
  color: var(--text-muted);
  flex-shrink: 0;
  min-width: 70px;
}

.log-text {
  flex: 1;
  word-break: break-all;
}

.log-info { color: var(--text-secondary); }
.log-success { color: var(--accent-green); }
.log-warn { color: var(--accent-yellow); }
.log-error { color: var(--accent-red); }
.log-debug { color: var(--text-muted); }
</style>
