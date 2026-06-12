<script setup lang="ts">
import { ref } from 'vue'
import { dataProbeApi } from '../utils/dataProbeApi'
import { platformApi } from '../utils/platformApi'

const target = ref('')
const investigating = ref(false)
const sessionId = ref('')
const protection = ref('-')
const channels = ref<string[]>([])
const evidence = ref<any[]>([])
const limits = ref<string[]>([])
const statusText = ref('输入目标，点击"开始调查"')
const errorText = ref('')
const logs = ref<string[]>([])

function addLog(msg: string) {
  logs.value.push(`[${new Date().toLocaleTimeString()}] ${msg}`)
}

async function startInvestigation() {
  if (!target.value.trim()) return
  investigating.value = true
  errorText.value = ''
  statusText.value = '正在分析目标...'
  evidence.value = []
  channels.value = []
  limits.value = []
  addLog(`开始调查: ${target.value}`)

  try {
    const result = await dataProbeApi.startInvestigation(target.value.trim())
    sessionId.value = result.sessionId || ''
    channels.value = result.channels || []
    limits.value = result.limits || []
    addLog(`调查已启动: ${result.status}, 通道: ${(result.channels || []).join(', ')}`)
    statusText.value = '采集中...'

    // 开始轮询证据
    pollEvidence()
  } catch (e: any) {
    errorText.value = e.message || '启动失败'
    investigating.value = false
    addLog(`错误: ${errorText.value}`)
  }
}

async function stopInvestigation() {
  try {
    await dataProbeApi.stopInvestigation()
    investigating.value = false
    statusText.value = '已停止'
    addLog('调查已停止')
  } catch (e: any) {
    errorText.value = e.message || '停止失败'
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null

async function pollEvidence() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const result = await dataProbeApi.getEvidence()
      if (result.items && result.items.length > 0) {
        evidence.value = result.items
        statusText.value = `已提取 ${result.items.length} 条证据`
      }
    } catch {
      // 轮询失败不中断
    }
  }, 2000)
}

function getTypeClass(type: string): string {
  const map: Record<string, string> = {
    token: 'token', url: 'url', key: 'key',
    params: 'params', image: 'key', raw: 'raw',
  }
  return `type-badge ${map[type.toLowerCase()] || 'raw'}`
}

function copyValue(val: string) {
  navigator.clipboard.writeText(val)
}

function formatTime(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}
</script>

<template>
  <div class="easy-mode">
    <!-- Input Section -->
    <div class="input-section">
      <div class="input-row">
        <input
          v-model="target"
          placeholder="输入目标 URL、域名、包名或文件路径..."
          :disabled="investigating"
          @keyup.enter="startInvestigation"
        />
        <button
          v-if="!investigating"
          class="btn-start"
          :disabled="!target.trim()"
          @click="startInvestigation"
        >▶ 开始调查</button>
        <button
          v-else
          class="btn-stop"
          @click="stopInvestigation"
        >■ 停止</button>
      </div>
      <div class="pack-selector">
        <label><input type="checkbox" checked disabled /> Token/凭证</label>
        <label><input type="checkbox" checked disabled /> 支付数据</label>
        <label><input type="checkbox" checked disabled /> API 端点</label>
        <label><input type="checkbox" checked disabled /> 启发式发现</label>
      </div>
    </div>

    <!-- Status -->
    <div class="status-bar">
      <span :class="investigating ? 'status-active' : 'status-idle'">
        {{ investigating ? '● 采集中' : '○ 待命' }}
      </span>
      <span class="status-text">{{ statusText }}</span>
      <span v-if="errorText" class="status-error">{{ errorText }}</span>
    </div>

    <!-- Plan Section -->
    <div v-if="channels.length > 0" class="plan-section">
      <div class="plan-header">
        <h3>🎯 对抗方案</h3>
        <div class="plan-detail">会话: {{ sessionId || '-' }}</div>
      </div>
      <div class="plan-channels">
        <span
          v-for="ch in channels"
          :key="ch"
          class="channel-tag active"
        >{{ ch }}</span>
      </div>
      <div v-if="limits.length > 0" class="plan-limits">
        <li v-for="l in limits" :key="l">{{ l }}</li>
      </div>
    </div>

    <!-- Evidence -->
    <div v-if="evidence.length > 0" class="evidence-section">
      <div class="section-header">
        <h3>📦 提取结果 ({{ evidence.length }})</h3>
        <button class="btn-secondary" @click="copyValue(JSON.stringify(evidence, null, 2))">
          复制全部
        </button>
      </div>
      <div
        v-for="(ev, i) in evidence"
        :key="i"
        class="evidence-card"
      >
        <div class="evidence-row">
          <div>
            <span :class="getTypeClass(ev.type)">{{ ev.type }}</span>
            <span class="confidence-dot" :style="{ background: ev.confidence > 0.8 ? '#3fb950' : '#d29922' }"></span>
            <span class="confidence-text">{{ Math.round(ev.confidence * 100) }}%</span>
          </div>
          <button class="btn-copy" @click="copyValue(ev.value)">复制</button>
        </div>
        <div class="evidence-value">{{ ev.value }}</div>
        <div class="evidence-meta">
          <span>📎 {{ ev.ruleName }}</span>
          <span>📍 {{ ev.locationId }}</span>
          <span>⏱ {{ formatTime(ev.capturedAt) }}</span>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!investigating && evidence.length === 0" class="empty-state">
      <div class="icon">🎯</div>
      <p>输入目标，点击"开始调查"</p>
      <p class="hint">支持 URL、域名、App 包名或文件路径</p>
    </div>

    <!-- Log -->
    <div v-if="logs.length > 0" class="log-section">
      <div v-for="(log, i) in logs" :key="i" class="log-line">{{ log }}</div>
    </div>
  </div>
</template>

<style scoped>
.easy-mode { padding: 20px; }
.input-section { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 12px; }
.input-row { display: flex; gap: 10px; margin-bottom: 12px; }
.input-row input {
  flex: 1; padding: 10px 14px; background: #0d1117; border: 1px solid #30363d;
  border-radius: 6px; color: #c9d1d9; font-size: 14px; outline: none;
}
.input-row input:focus { border-color: #58a6ff; }
.btn-start { padding: 10px 24px; background: #238636; color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-start:hover { background: #2ea043; }
.btn-start:disabled { background: #1a5f2a; color: #8b949e; cursor: not-allowed; }
.btn-stop { padding: 10px 24px; background: #da3633; color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-stop:hover { background: #f85149; }
.pack-selector { display: flex; gap: 8px; flex-wrap: wrap; }
.pack-selector label { display: flex; align-items: center; gap: 6px; padding: 4px 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; font-size: 12px; cursor: pointer; }
.status-bar { display: flex; align-items: center; gap: 12px; padding: 8px 0; margin-bottom: 12px; font-size: 13px; }
.status-active { color: #3fb950; font-weight: 600; }
.status-idle { color: #8b949e; }
.status-text { color: #8b949e; }
.status-error { color: #f85149; }
.plan-section { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.plan-header h3 { font-size: 14px; color: #58a6ff; margin-bottom: 4px; }
.plan-detail { font-size: 12px; color: #8b949e; }
.plan-channels { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
.channel-tag { padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
.channel-tag.active { background: #0e4429; color: #3fb950; border: 1px solid #238636; }
.plan-limits li { color: #d29922; font-size: 12px; margin: 2px 0; list-style: none; }
.evidence-section { margin-top: 8px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.section-header h3 { font-size: 15px; font-weight: 600; }
.btn-secondary { padding: 4px 12px; border: 1px solid #30363d; border-radius: 4px; font-size: 11px; cursor: pointer; background: #21262d; color: #8b949e; }
.btn-secondary:hover { background: #30363d; color: #c9d1d9; }
.evidence-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
.evidence-card:hover { border-color: #58a6ff; }
.evidence-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.evidence-value { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 13px; color: #3fb950; word-break: break-all; }
.evidence-meta { font-size: 11px; color: #8b949e; margin-top: 6px; display: flex; gap: 16px; flex-wrap: wrap; }
.type-badge { display: inline-flex; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600; margin-right: 6px; }
.type-badge.token { background: #2d1b4e; color: #bc8cff; }
.type-badge.url { background: #0e4429; color: #3fb950; }
.type-badge.key { background: #1c2d4e; color: #58a6ff; }
.type-badge.params { background: #2d2d1b; color: #d29922; }
.type-badge.raw { background: #1c1c1c; color: #8b949e; }
.confidence-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; vertical-align: middle; }
.confidence-text { font-size: 11px; color: #8b949e; }
.btn-copy { padding: 4px 10px; border: 1px solid #30363d; border-radius: 4px; font-size: 11px; cursor: pointer; background: #21262d; color: #8b949e; }
.btn-copy:hover { background: #30363d; color: #c9d1d9; }
.empty-state { text-align: center; padding: 80px 20px; color: #484f58; }
.empty-state .icon { font-size: 48px; margin-bottom: 12px; }
.empty-state p { font-size: 14px; }
.empty-state .hint { font-size: 12px; color: #30363d; margin-top: 8px; }
.log-section { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 12px; margin-top: 16px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; }
.log-line { color: #8b949e; padding: 2px 0; border-bottom: 1px solid #21262d; }
</style>
