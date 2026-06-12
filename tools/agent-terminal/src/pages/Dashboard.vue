<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { dataProbeApi } from '../utils/dataProbeApi'
import { platformApi } from '../utils/platformApi'

const dpConnected = ref(false)
const platformConnected = ref(false)
const captureCount = ref(0)
const uptime = ref('-')
const credentials = ref({ total: 0, sent: 0, failed: 0 })
const tlsSessions = ref(0)
const recentData = ref<any[]>([])
const rules = ref<any[]>([])
const loading = ref(true)

let timer: ReturnType<typeof setInterval> | null = null

function fmtTime(sec: number): string {
  if (!sec) return '-'
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60)
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`
}

async function refresh() {
  try {
    const status = await dataProbeApi.getStatus()
    dpConnected.value = true
    captureCount.value = status.credentials_queued || 0
    uptime.value = fmtTime(status.uptime_seconds)
    credentials.value = { total: status.credentials_queued || 0, sent: status.credentials_sent || 0, failed: status.credentials_failed || 0 }
    tlsSessions.value = status.active_tls_sessions || 0
  } catch {
    dpConnected.value = false
  }

  try {
    const ok = await platformApi.healthCheck()
    platformConnected.value = ok
  } catch {
    platformConnected.value = false
  }

  try {
    const data = await dataProbeApi.getData()
    recentData.value = (data.items || []).slice(-10).reverse()
  } catch {}

  try {
    const r = await dataProbeApi.getRules()
    rules.value = r.rules || []
  } catch {}
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="dashboard">
    <h2 class="page-title">仪表盘</h2>

    <!-- Status Cards -->
    <div class="cards">
      <div class="card">
        <div class="label">DataProbe 引擎</div>
        <div class="value" :class="dpConnected ? 'green' : 'red'">{{ dpConnected ? '● 运行中' : '○ 离线' }}</div>
      </div>
      <div class="card">
        <div class="label">平台连接</div>
        <div class="value" :class="platformConnected ? 'green' : 'orange'">{{ platformConnected ? '● 已连接' : '○ 未连接' }}</div>
      </div>
      <div class="card">
        <div class="label">运行时间</div>
        <div class="value blue">{{ uptime }}</div>
      </div>
      <div class="card">
        <div class="label">已捕获</div>
        <div class="value green">{{ captureCount }}</div>
      </div>
      <div class="card">
        <div class="label">已发送/失败</div>
        <div class="value orange">{{ credentials.sent }}/{{ credentials.failed }}</div>
      </div>
      <div class="card">
        <div class="label">TLS 会话</div>
        <div class="value purple">{{ tlsSessions }}</div>
      </div>
    </div>

    <!-- Two-column layout -->
    <div class="grid-2">
      <!-- Recent Data -->
      <div class="section-card">
        <h3>最近捕获</h3>
        <div v-if="recentData.length === 0" class="empty-hint">暂无数据</div>
        <div v-for="(item, i) in recentData" :key="i" class="data-row">
          <div class="data-type">{{ item.type }}</div>
          <div class="data-val">{{ (item.value || '').substring(0, 60) }}</div>
          <div class="data-src">{{ item.source }}</div>
        </div>
      </div>

      <!-- Rules -->
      <div class="section-card">
        <h3>加载的规则 ({{ rules.length }})</h3>
        <div v-if="rules.length === 0" class="empty-hint">无规则</div>
        <div v-for="r in rules" :key="r.id" class="rule-row">
          <span class="rule-name">{{ r.name }}</span>
          <span class="rule-count">{{ r.total_captured || 0 }}条</span>
          <span :class="r.enabled ? 'rule-on' : 'rule-off'">{{ r.enabled ? 'ON' : 'OFF' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard { padding: 20px; }
.page-title { font-size: 20px; font-weight: 700; margin-bottom: 20px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 16px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px; }
.card .label { font-size: 10px; color: #8b949e; text-transform: uppercase; margin-bottom: 4px; }
.card .value { font-size: 16px; font-weight: 700; }
.green { color: #3fb950; }
.red { color: #f85149; }
.orange { color: #d29922; }
.blue { color: #58a6ff; }
.purple { color: #bc8cff; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.section-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
.section-card h3 { font-size: 13px; font-weight: 600; margin-bottom: 10px; }
.empty-hint { font-size: 12px; color: #484f58; text-align: center; padding: 20px; }
.data-row { display: flex; gap: 8px; padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 12px; }
.data-type { color: #58a6ff; white-space: nowrap; min-width: 50px; }
.data-val { color: #3fb950; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.data-src { color: #8b949e; white-space: nowrap; }
.rule-row { display: flex; gap: 8px; padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 12px; }
.rule-name { flex: 1; }
.rule-count { color: #8b949e; }
.rule-on { color: #3fb950; font-weight: 600; }
.rule-off { color: #8b949e; }
</style>
