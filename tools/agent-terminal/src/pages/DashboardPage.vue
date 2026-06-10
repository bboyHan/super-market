<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useRouter } from 'vue-router'

const theme = useThemeStore()
const router = useRouter()

// ── 类型 ─────────────────────────────────────

interface Credential {
  id: string
  type: string
  value: string
  platform: string
  product_id: string
  source_pipeline: string
  status: string
  captured_at: string
  raw_data?: Record<string, any>
  metadata?: Record<string, any>
}

// ── 状态 ─────────────────────────────────────

const capturing = ref(false)
const credentials = ref<Credential[]>([])
const selected = ref<Credential | null>(null)
const searchQuery = ref('')
const typeFilter = ref('all')
const platformFilter = ref('all')
const sseConnected = ref(false)

// ── 计算属性 ─────────────────────────────────

const uniquePlatforms = computed(() => {
  const set = new Set(credentials.value.map(c => c.platform))
  return ['all', ...Array.from(set)]
})

const uniqueTypes = computed(() => {
  const set = new Set(credentials.value.map(c => c.type))
  return ['all', ...Array.from(set)]
})

const filteredCredentials = computed(() => {
  return credentials.value.filter(c => {
    if (typeFilter.value !== 'all' && c.type !== typeFilter.value) return false
    if (platformFilter.value !== 'all' && c.platform !== platformFilter.value) return false
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      return c.value.toLowerCase().includes(q) ||
             c.platform.toLowerCase().includes(q) ||
             c.id.includes(q)
    }
    return true
  })
})

const captureCount = computed(() => credentials.value.length)

// ── SSE 实时推送 ─────────────────────────────

let eventSource: EventSource | null = null
let pingTimer: number | null = null

function connectSSE() {
  if (eventSource) return
  try {
    eventSource = new EventSource('/api/capture/sse')
    sseConnected.value = true

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'captured' && data.credential) {
          // 新凭证到达，插入列表最前面
          credentials.value.unshift(data.credential)
          // 保留最近 500 条
          if (credentials.value.length > 500) {
            credentials.value.length = 500
          }
        } else if (data.type === 'heartbeat') {
          // 心跳，不做处理
        }
      } catch {}
    }

    eventSource.onerror = () => {
      sseConnected.value = false
      // 3秒后重连
      setTimeout(connectSSE, 3000)
    }
  } catch {
    sseConnected.value = false
  }
}

function disconnectSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
    sseConnected.value = false
  }
}

// ── 捕获控制 ─────────────────────────────────

async function startCapture() {
  try {
    const resp = await fetch('/api/capture/start', { method: 'POST' })
    const data = await resp.json()
    if (data.status === 'started') {
      capturing.value = true
    }
  } catch (e) {
    console.error('Failed to start capture:', e)
  }
}

async function stopCapture() {
  try {
    const resp = await fetch('/api/capture/stop', { method: 'POST' })
    const data = await resp.json()
    if (data.status === 'stopped') {
      capturing.value = false
    }
  } catch (e) {
    console.error('Failed to stop capture:', e)
  }
}

function clearAll() {
  credentials.value = []
  selected.value = null
}

// ── 工具 ─────────────────────────────────────

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

function typeBadge(type: string): string {
  const map: Record<string, string> = {
    'payment_url': '支付URL',
    'payment_params': '支付参数',
    'access_token': '访问令牌',
    'qr_image': '二维码',
    'card_key': '卡密',
    'raw_data': '原始数据',
  }
  return map[type] || type
}

function typeClass(type: string) {
  const map: Record<string, string> = {
    'payment_url': 'badge-url',
    'payment_params': 'badge-params',
    'access_token': 'badge-token',
    'qr_image': 'badge-qr',
    'card_key': 'badge-card',
  }
  return map[type] || 'badge-raw'
}

function statusIcon(status: string): string {
  return status === 'uploaded' ? '✅' : status === 'duplicated' ? '⏭️' : '📥'
}

function previewValue(value: string, max = 60): string {
  if (value.startsWith('data:image')) return '[图片数据]'
  if (value.length > max) return value.slice(0, max) + '...'
  return value
}

function selectCredential(c: Credential) {
  selected.value = c
}

function getAccountName(c: Credential): string {
  if (c.account_name) return c.account_name
  const meta = c.metadata || {}
  return meta.account_name || meta.openid?.slice(0,12) + '...' || '-'
}

function getOpenId(c: Credential): string {
  const meta = c.metadata || {}
  return meta.openid || '-'
}

// ── 生命周期 ─────────────────────────────────

async function loadExistingCredentials() {
  try {
    const resp = await fetch('/api/inventory/list?page_size=50')
    const data = await resp.json()
    if (data.resources) {
      credentials.value = data.resources.map((r: any) => {
        let meta = r.metadata || {}
        if (typeof meta === 'string') { try { meta = JSON.parse(meta) } catch { meta = {} } }
        return {
          id: r.resource_id || r.id,
          type: r.resource_type || 'unknown',
          value: r.value || '',
          platform: r.platform || '',
          product_id: r.product_id || '',
          status: r.status || '',
          captured_at: r.created_at || '',
          metadata: meta,
          source_pipeline: '',
        }
      })
    }
  } catch {}
}

onMounted(() => {
  theme.init()
  loadExistingCredentials()
  connectSSE()
  // 定期轮询捕获状态 + 刷新列表
  const timer = setInterval(async () => {
    try {
      const resp = await fetch('/api/capture/status')
      const data = await resp.json()
      capturing.value = data.running
    } catch {}
  }, 5000)
})

onUnmounted(() => {
  clearInterval(timer)
  disconnectSSE()
})
</script>

<template>
  <div class="page-wrapper" :class="{ light: !theme.isDark }">
    <!-- ═══ 顶部工具栏 ═══ -->
    <header class="toolbar">
      <div class="toolbar-left">
        <span class="brand-icon">⚡</span>
        <span class="brand-text">支付采集器</span>
        <span class="version">v1.0</span>
      </div>
      <div class="toolbar-center">
        <button v-if="!capturing" class="btn btn-start" @click="startCapture">
          ▶ 开始捕获
        </button>
        <button v-else class="btn btn-stop" @click="stopCapture">
          ⏹ 停止捕获
        </button>
        <button class="btn btn-secondary" @click="clearAll">
          🗑 清空
        </button>
      </div>
      <div class="toolbar-right">
        <span class="status-dot" :class="{ active: sseConnected }"></span>
        <span class="status-text">SSE {{ sseConnected ? '已连接' : '断开' }}</span>
        <span class="divider">|</span>
        <span class="status-text">已捕获: <strong>{{ captureCount }}</strong></span>
        <span class="divider">|</span>
        <span class="status-dot" :class="{ active: capturing }"></span>
        <span class="status-text">{{ capturing ? '捕获中' : '已停止' }}</span>
      </div>
    </header>

    <!-- ═══ 过滤栏 ═══ -->
    <div class="filter-bar">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input
          v-model="searchQuery"
          class="search-input"
          placeholder="搜索凭证内容、平台..."
        />
      </div>
      <select v-model="platformFilter" class="filter-select">
        <option value="all">全部平台</option>
        <option v-for="p in uniquePlatforms.filter(x => x !== 'all')" :key="p" :value="p">{{ p }}</option>
      </select>
      <select v-model="typeFilter" class="filter-select">
        <option value="all">全部类型</option>
        <option v-for="t in uniqueTypes.filter(x => x !== 'all')" :key="t" :value="t">{{ typeBadge(t) }}</option>
      </select>
      <span class="filter-count">{{ filteredCredentials.length }} 条</span>
    </div>

    <!-- ═══ 主内容区 ═══ -->
    <div class="main-area">
      <!-- 凭证列表 -->
      <div class="list-panel">
        <div class="list-header">
          <span class="col-id">#</span>
          <span class="col-time">时间</span>
          <span class="col-platform">平台</span>
          <span class="col-type">类型</span>
          <span class="col-account">账号</span>
          <span class="col-value">值预览</span>
          <span class="col-status">状态</span>
        </div>
        <div class="list-body">
          <div
            v-for="(c, idx) in filteredCredentials"
            :key="c.id"
            class="list-row"
            :class="{ selected: selected?.id === c.id }"
            @click="selectCredential(c)"
          >
            <span class="col-id">{{ idx + 1 }}</span>
            <span class="col-time">{{ formatTime(c.captured_at) }}</span>
            <span class="col-platform">{{ c.platform }}</span>
            <span class="col-type">
              <span class="type-badge" :class="typeClass(c.type)">{{ typeBadge(c.type) }}</span>
            </span>
            <span class="col-account" :title="'openid: ' + getOpenId(c)">{{ getAccountName(c) }}</span>
            <span class="col-value" :title="c.value">{{ previewValue(c.value) }}</span>
            <span class="col-status">{{ statusIcon(c.status) }}</span>
          </div>
          <div v-if="filteredCredentials.length === 0" class="empty-state">
            <div class="empty-icon">📭</div>
            <div class="empty-text">暂无凭证数据</div>
            <div class="empty-hint">点击「开始捕获」启动采集器</div>
          </div>
        </div>
      </div>

      <!-- 详情面板 -->
      <div class="detail-panel" v-if="selected">
        <div class="detail-header">
          <span class="detail-title">凭证详情</span>
          <button class="btn-close" @click="selected = null">✕</button>
        </div>
        <div class="detail-body">
          <div class="detail-field">
            <label>类型</label>
            <span class="type-badge large" :class="typeClass(selected.type)">
              {{ typeBadge(selected.type) }}
            </span>
          </div>
          <div class="detail-field">
            <label>平台</label>
            <span>{{ selected.platform }}</span>
          </div>
          <div class="detail-field">
            <label>货品ID</label>
            <span>{{ selected.product_id || '-' }}</span>
          </div>
          <div class="detail-field">
            <label>关联账号</label>
            <span class="account-name">{{ getAccountName(selected) }}</span>
          </div>
          <div class="detail-field">
            <label>openid</label>
            <span class="mono">{{ getOpenId(selected) }}</span>
          </div>
          <div class="detail-field">
            <label>采集时间</label>
            <span>{{ formatTime(selected.captured_at) }}</span>
          </div>
          <div class="detail-field">
            <label>来源</label>
            <span>{{ selected.source_pipeline || '-' }}</span>
          </div>
          <div class="detail-field">
            <label>状态</label>
            <span>{{ selected.status }}</span>
          </div>
          <div class="detail-field value-field">
            <label>凭证值</label>
            <textarea readonly :value="selected.value" rows="4"></textarea>
          </div>
          <div v-if="selected.raw_data && Object.keys(selected.raw_data).length" class="detail-field">
            <label>原始数据</label>
            <pre class="raw-json">{{ JSON.stringify(selected.raw_data, null, 2) }}</pre>
          </div>
        </div>
      </div>
      <div class="detail-panel empty-detail" v-else>
        <div class="empty-detail-inner">
          <div class="empty-icon">👈</div>
          <div class="empty-text">选择一条凭证查看详情</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-wrapper {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary, #0f0f1a);
  color: var(--text-primary, #e0e0e0);
  font-size: 13px;
}
.light {
  background: #f5f5f5;
  color: #333;
}

/* ═══ 工具栏 ═══ */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--bg-secondary, #1a1a2e);
  border-bottom: 1px solid var(--border-color, #2a2a3e);
  gap: 12px;
  flex-shrink: 0;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.brand-icon { font-size: 18px; }
.brand-text { font-weight: 700; font-size: 15px; }
.version { font-size: 11px; color: var(--text-muted, #888); }
.toolbar-center {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted, #888);
}
.status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #555;
}
.status-dot.active { background: #4ade80; }
.status-text strong { color: var(--text-primary); }
.divider { color: #444; margin: 0 2px; }

/* ═══ 按钮 ═══ */
.btn {
  padding: 6px 14px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-start { background: #22c55e; color: #fff; }
.btn-start:hover { background: #16a34a; }
.btn-stop { background: #ef4444; color: #fff; }
.btn-stop:hover { background: #dc2626; }
.btn-secondary { background: var(--bg-hover, #2a2a3e); color: var(--text-secondary); }
.btn-secondary:hover { background: #3a3a4e; color: var(--text-primary); }

/* ═══ 过滤栏 ═══ */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.search-box {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  max-width: 320px;
  padding: 4px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
}
.search-input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}
.filter-select {
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 12px;
}
.filter-count {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}

/* ═══ 主内容区 ═══ */
.main-area {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ═══ 凭证列表 ═══ */
.list-panel {
  width: 60%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color);
}
.list-header, .list-row {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  gap: 8px;
  font-size: 12px;
}
.list-header {
  background: var(--bg-secondary);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  flex-shrink: 0;
}
.list-body {
  flex: 1;
  overflow-y: auto;
}
.list-row {
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.1s;
}
.list-row:hover { background: var(--bg-hover, rgba(255,255,255,0.03)); }
.list-row.selected {
  background: rgba(59, 130, 246, 0.1);
  border-left: 3px solid #3b82f6;
}
.col-id { width: 30px; color: var(--text-muted); }
.col-time { width: 72px; color: var(--text-muted); font-size: 11px; }
.col-platform { width: 80px; }
.col-type { width: 80px; }
.col-account { width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: var(--accent-primary, #3b82f6); }
.col-value { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-secondary); }
.col-status { width: 30px; text-align: center; }
.type-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.badge-url { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
.badge-params { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
.badge-token { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.badge-qr { background: rgba(168, 85, 247, 0.15); color: #a855f7; }
.badge-card { background: rgba(236, 72, 153, 0.15); color: #ec4899; }
.badge-raw { background: rgba(100, 116, 139, 0.15); color: #64748b; }
.type-badge.large { font-size: 13px; padding: 3px 10px; }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-muted);
}
.empty-icon { font-size: 40px; margin-bottom: 8px; }
.empty-text { font-size: 14px; }
.empty-hint { font-size: 12px; margin-top: 4px; }

/* ═══ 详情面板 ═══ */
.detail-panel {
  width: 40%;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}
.detail-title { font-weight: 600; }
.btn-close {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
}
.btn-close:hover { color: var(--text-primary); }
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}
.detail-field {
  margin-bottom: 12px;
}
.detail-field label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 4px;
}
.detail-field textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-family: monospace;
  font-size: 12px;
  resize: vertical;
}
.account-name { color: var(--accent-primary, #3b82f6); font-weight: 600; }
.mono { font-family: monospace; font-size: 11px; color: var(--text-muted); }
.raw-json {
  padding: 8px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-secondary);
  font-size: 11px;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.empty-detail {
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-detail-inner {
  text-align: center;
  color: var(--text-muted);
}
</style>
