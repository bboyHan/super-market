<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/utils/api'

const router = useRouter()
const captureCount = ref(0)
const backendOnline = ref(false)
const recentLogs = ref<string[]>([])
const isElectron = ref(false)

let timer: number | null = null

async function refresh() {
  try {
    const data = await api.get('/api/collector/status')
    captureCount.value = data.totalCount || 0
    backendOnline.value = true
  } catch {
    backendOnline.value = false
  }
  try {
    const logs = await api.get('/api/logs?limit=10')
    recentLogs.value = (Array.isArray(logs) ? logs : []).map((l: any) =>
      `[${l.created_at?.slice(11, 19) || ''}] ${l.message}`
    )
  } catch {}
}

function goBack() { router.push('/dashboard') }
function openPayQQ() { window.open('https://pay.qq.com/h5/shop.shtml', '_blank') }
function openPayQQIpay() { window.open('https://pay.qq.com/ipay/index.shtml?c=qqacct_save', '_blank') }

onMounted(() => {
  isElectron.value = !!(window as any).electronAPI
  refresh()
  timer = window.setInterval(refresh, 3000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="console">
    <header class="console-header">
      <button class="back-btn" @click="goBack">◀ 返回</button>
      <span class="console-title">浏览器采集控制台</span>
      <span class="badge" :class="{ online: backendOnline }">
        {{ backendOnline ? '后端在线' : '离线' }}
      </span>
    </header>

    <div class="content">
      <!-- 左侧信息面板 -->
      <div class="info-panel">
        <div class="stat-card">
          <div class="stat-value">{{ captureCount }}</div>
          <div class="stat-label">已采集凭证</div>
        </div>

        <div class="action-group">
          <div class="action-title">快速入口</div>
          <button class="action-btn" @click="openPayQQ">
            🛒 pay.qq.com 商城
          </button>
          <button class="action-btn" @click="openPayQQIpay">
            🔐 PC 充值中心（扫码登录）
          </button>
        </div>

        <div class="tips">
          <div class="tips-title">操作指引</div>
          <ol class="tips-list">
            <li>点击上方入口打开支付页面</li>
            <li>登录并选择商品点击支付</li>
            <li>Chrome 插件自动拦截凭证</li>
            <li>凭证自动回传到本系统</li>
          </ol>
        </div>
      </div>

      <!-- 右侧日志面板 -->
      <div class="log-panel">
        <div class="log-title">采集日志</div>
        <div class="log-list">
          <div v-for="(log, i) in recentLogs" :key="i" class="log-item">
            {{ log }}
          </div>
          <div v-if="recentLogs.length === 0" class="log-empty">
            暂无采集记录，请打开支付页面操作
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.console {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0f0f1a;
  color: #e0e0e0;
}
.console-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: #1a1a2e;
  border-bottom: 1px solid #2a2a4a;
}
.back-btn {
  padding: 6px 14px;
  border: 1px solid #333;
  border-radius: 6px;
  background: transparent;
  color: #ccc;
  font-size: 13px;
  cursor: pointer;
}
.back-btn:hover { background: #333; }
.console-title { font-size: 16px; font-weight: 600; flex: 1; }
.badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 10px;
  background: #f87171;
  color: #fff;
}
.badge.online { background: #4ade80; }

.content {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 0;
  flex: 1;
  overflow: hidden;
}

/* 信息面板 */
.info-panel {
  padding: 20px;
  border-right: 1px solid #2a2a4a;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.stat-card {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
}
.stat-value { font-size: 42px; font-weight: 800; color: #e94560; }
.stat-label { font-size: 13px; color: #888; margin-top: 4px; }

.action-group { display: flex; flex-direction: column; gap: 8px; }
.action-title { font-size: 12px; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 1px; }
.action-btn {
  padding: 10px 16px;
  border: 1px solid #333;
  border-radius: 8px;
  background: #1a1a2e;
  color: #e0e0e0;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}
.action-btn:hover { border-color: #e94560; background: #2a1a2e; }

.tips {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  padding: 16px;
}
.tips-title { font-size: 12px; font-weight: 600; color: #888; margin-bottom: 8px; }
.tips-list {
  font-size: 12px;
  color: #aaa;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 日志面板 */
.log-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.log-title {
  padding: 14px 20px;
  font-size: 13px;
  font-weight: 600;
  color: #888;
  border-bottom: 1px solid #2a2a4a;
}
.log-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.log-item {
  padding: 6px 20px;
  font-size: 12px;
  color: #aaa;
  font-family: monospace;
}
.log-item:nth-child(odd) { background: #0a0a15; }
.log-empty {
  padding: 40px 20px;
  text-align: center;
  color: #555;
  font-size: 13px;
}
</style>
