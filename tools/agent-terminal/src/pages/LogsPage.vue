<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '@/utils/api'

interface LogEntry {
  id: string
  timestamp: string
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR'
  module: string
  message: string
}

const logs = ref<LogEntry[]>([])
const selectedLevel = ref('all')
const selectedModule = ref('all')

const modules = ['System', 'Tasks', 'Inventory', 'Accounts', 'API', 'Emulator', 'Database']
const levels = ['DEBUG', 'INFO', 'WARN', 'ERROR']
const eventSource = ref<EventSource | null>(null)

const filteredLogs = computed(() => {
  let result = logs.value
  if (selectedLevel.value !== 'all') {
    result = result.filter(l => l.level === selectedLevel.value)
  }
  if (selectedModule.value !== 'all') {
    result = result.filter(l => l.module === selectedModule.value)
  }
  return result
})

function connectSSE() {
  const es = new EventSource('/api/sse/logs')
  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      logs.value.push({
        id: Date.now().toString() + Math.random().toString(36).slice(2, 8),
        timestamp: new Date().toISOString(),
        level: data.level || 'INFO',
        module: data.module || 'System',
        message: data.message || data.log || event.data,
      })
      if (logs.value.length > 500) {
        logs.value = logs.value.slice(-500)
      }
    } catch {
      logs.value.push({
        id: Date.now().toString() + Math.random().toString(36).slice(2, 8),
        timestamp: new Date().toISOString(),
        level: 'INFO',
        module: 'System',
        message: event.data,
      })
    }
  }
  es.onerror = () => {
    es.close()
    eventSource.value = null
  }
  eventSource.value = es
}

async function fetchLogs() {
  try {
    const data = await api.get('/api/logs')
    if (data.logs) {
      logs.value = data.logs
    }
  } catch {
    // API not available — logs will arrive via SSE stream
    // Don't generate fake data
  }
}

function levelClass(level: string): string {
  const map: Record<string, string> = {
    'ERROR': 'level-error',
    'WARN': 'level-warn',
    'INFO': 'level-info',
    'DEBUG': 'level-debug',
  }
  return map[level] || 'level-info'
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString()
}

function clearLogs() {
  logs.value = []
}

const logContainer = ref<HTMLElement | null>(null)
const autoScroll = ref(true)

function scrollToBottom() {
  if (autoScroll.value && logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

onMounted(() => {
  fetchLogs()
  connectSSE()
})

onUnmounted(() => {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
})
</script>

<template>
  <div class="logs-page">
    <!-- Filters -->
    <div class="card filter-card">
      <div class="filter-row">
        <div class="filter-group">
          <label class="filter-label">Level</label>
          <select v-model="selectedLevel" class="select select-sm">
            <option value="all">All Levels</option>
            <option v-for="l in levels" :key="l" :value="l">{{ l }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label class="filter-label">Module</label>
          <select v-model="selectedModule" class="select select-sm">
            <option value="all">All Modules</option>
            <option v-for="m in modules" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
        <div class="filter-actions">
          <button class="btn btn-sm btn-secondary" @click="clearLogs">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            Clear
          </button>
          <span class="log-count">{{ filteredLogs.length }} entries</span>
        </div>
      </div>
    </div>

    <!-- Log List -->
    <div class="card log-card">
      <div
        ref="logContainer"
        class="log-list"
      >
        <div
          v-for="log in filteredLogs"
          :key="log.id"
          class="log-entry"
          :class="levelClass(log.level)"
        >
          <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          <span class="log-level">{{ log.level }}</span>
          <span class="log-module">{{ log.module }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
        <div v-if="filteredLogs.length === 0" class="log-empty">
          No log entries match the current filters.
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.logs-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1200px;
}

.filter-card {
  padding: 12px 16px;
}

.filter-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filter-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  font-weight: 500;
}

.select-sm {
  padding: 6px 28px 6px 10px;
  font-size: 12px;
  min-width: 130px;
}

.filter-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.log-count {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.log-card {
  overflow: hidden;
  padding: 0;
}

.log-list {
  height: 600px;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.log-entry {
  display: flex;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 4px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  line-height: 1.6;
  align-items: center;
}

.log-entry:hover {
  background: var(--bg-hover);
}

.log-time {
  color: var(--text-muted);
  flex-shrink: 0;
  min-width: 80px;
}

.log-level {
  flex-shrink: 0;
  min-width: 50px;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
}

.log-module {
  flex-shrink: 0;
  min-width: 90px;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 11px;
  text-align: center;
}

.log-message {
  flex: 1;
  color: var(--text-primary);
  word-break: break-word;
}

.level-error .log-level { color: var(--accent-red); }
.level-error .log-message { color: var(--accent-red); }

.level-warn .log-level { color: var(--accent-yellow); }
.level-warn .log-message { color: var(--accent-yellow); }

.level-info .log-level { color: var(--accent-blue); }

.level-debug .log-level { color: var(--text-muted); }
.level-debug .log-message { color: var(--text-muted); }

.log-empty {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}
</style>
