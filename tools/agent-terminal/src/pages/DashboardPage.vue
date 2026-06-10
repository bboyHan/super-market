<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useRouter } from 'vue-router'
import { api } from '@/utils/api'

const theme = useThemeStore()
const router = useRouter()

// ── 状态 ──
const collectorStatus = ref({
  browser: { active: false, count: 0 },
  pcgame: { active: false, count: 0 },
  mobile: { active: false, count: 0 },
  backend: false,
  platform: false,
  totalCount: 0,
})

// ── 轮询状态 ──
let timer: number | null = null

async function fetchStatus() {
  try {
    collectorStatus.value = await api.get('/api/collector/status')
  } catch {
    collectorStatus.value.backend = false
  }
}

onMounted(() => {
  theme.init()
  fetchStatus()
  timer = window.setInterval(fetchStatus, 3000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

// ── 管道操作 ──
function startPipeline(type: 'browser' | 'pcgame' | 'mobile') {
  if (type === 'browser') {
    // Dev 模式: 新标签页打开（配合 Chrome 插件）
    // 生产模式: Electron BrowserView（由 main.js 处理）
    if ((window as any).electronAPI) {
      (window as any).electronAPI.openBrowser('https://pay.qq.com/h5/shop.shtml')
    } else {
      window.open('https://pay.qq.com/h5/shop.shtml', '_blank')
    }
  } else {
    fetch(`/api/collector/${type}/start`, { method: 'POST' })
  }
}

const statusDot = (active: boolean) => active ? '#4ade80' : '#555'
const statusText = (active: boolean) => active ? '运行中' : '已停止'
</script>

<template>
  <div class="page-wrapper" :class="{ light: !theme.isDark }">
    <!-- 顶部状态栏 -->
    <header class="top-bar">
      <div class="brand">
        <span class="brand-icon">⚡</span>
        <span class="brand-text">Agent Terminal</span>
      </div>
      <div class="status-indicators">
        <span class="indicator" :style="{ color: collectorStatus.backend ? '#4ade80' : '#f87171' }">
          ● {{ collectorStatus.backend ? '后端正常' : '后端离线' }}
        </span>
        <span class="indicator" :style="{ color: collectorStatus.platform ? '#4ade80' : '#fbbf24' }">
          ● {{ collectorStatus.platform ? '平台已连接' : '平台未连接' }}
        </span>
        <span class="nav-link" @click="router.push('/inventory')">库存 ({{ collectorStatus.totalCount }})</span>
        <span class="nav-link" @click="router.push('/tasks')">任务</span>
        <span class="nav-link" @click="router.push('/logs')">日志</span>
      </div>
    </header>

    <!-- 主区域：三管道卡片 -->
    <main class="pipeline-grid">

      <!-- 管道 A：浏览器采集 -->
      <div class="pipeline-card">
        <div class="card-header">
          <span class="pipeline-num">①</span>
          <span class="pipeline-label">浏览器采集</span>
          <span class="status-badge" :style="{ background: statusDot(collectorStatus.browser.active) }">
            {{ statusText(collectorStatus.browser.active) }}
          </span>
        </div>
        <div class="card-body">
          <div class="pipeline-desc">
            适合：网页端 Q币充值、游戏商城、各类 H5 支付
          </div>
          <div class="pipeline-flow">
            <span>打开内置浏览器</span>
            <span class="arrow">→</span>
            <span>扫码/登录</span>
            <span class="arrow">→</span>
            <span>支付操作</span>
            <span class="arrow">→</span>
            <span class="highlight">自动采集 ✓</span>
          </div>
          <div class="stats-row">
            <span>已采集: <strong>{{ collectorStatus.browser.count }}</strong> 条</span>
          </div>
        </div>
        <button class="btn-start" @click="startPipeline('browser')">
          打开浏览器采集
        </button>
        <button class="btn-secondary" @click="router.push('/collector/browser')">
          查看状态
        </button>
      </div>

      <!-- 管道 B：PC端游采集 -->
      <div class="pipeline-card">
        <div class="card-header">
          <span class="pipeline-num">②</span>
          <span class="pipeline-label">PC端游采集</span>
          <span class="status-badge" :style="{ background: statusDot(collectorStatus.pcgame.active) }">
            {{ statusText(collectorStatus.pcgame.active) }}
          </span>
        </div>
        <div class="card-body">
          <div class="pipeline-desc">
            适合：DNF、英雄联盟、梦幻西游等客户端内充值
          </div>
          <div class="pipeline-flow">
            <span>启动代理</span>
            <span class="arrow">→</span>
            <span>打开游戏</span>
            <span class="arrow">→</span>
            <span>点击充值</span>
            <span class="arrow">→</span>
            <span class="highlight">自动采集 ✓</span>
          </div>
          <div class="stats-row">
            <span>已采集: <strong>{{ collectorStatus.pcgame.count }}</strong> 条</span>
          </div>
        </div>
        <button class="btn-start" @click="startPipeline('pcgame')"
          :disabled="collectorStatus.pcgame.active">
          {{ collectorStatus.pcgame.active ? '采集中...' : '启动端游采集' }}
        </button>
      </div>

      <!-- 管道 C：手机端采集 -->
      <div class="pipeline-card">
        <div class="card-header">
          <span class="pipeline-num">③</span>
          <span class="pipeline-label">手机端采集</span>
          <span class="status-badge" :style="{ background: statusDot(collectorStatus.mobile.active) }">
            {{ statusText(collectorStatus.mobile.active) }}
          </span>
        </div>
        <div class="card-body">
          <div class="pipeline-desc">
            适合：手机 QQ 充值、手游 App 内购
          </div>
          <div class="pipeline-flow">
            <span>创建热点</span>
            <span class="arrow">→</span>
            <span>手机连接</span>
            <span class="arrow">→</span>
            <span>打开 App</span>
            <span class="arrow">→</span>
            <span class="highlight">自动采集 ✓</span>
          </div>
          <div class="stats-row">
            <span>已采集: <strong>{{ collectorStatus.mobile.count }}</strong> 条</span>
          </div>
        </div>
        <button class="btn-start" @click="startPipeline('mobile')"
          :disabled="collectorStatus.mobile.active">
          {{ collectorStatus.mobile.active ? '采集中...' : '启动手机采集' }}
        </button>
      </div>

    </main>
  </div>
</template>

<style scoped>
.page-wrapper {
  min-height: 100vh;
  background: #0f0f1a;
  color: #e0e0e0;
  display: flex;
  flex-direction: column;
}
.page-wrapper.light {
  background: #f5f5f5;
  color: #333;
}

/* ── 顶部栏 ── */
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: #1a1a2e;
  border-bottom: 1px solid #2a2a4a;
}
.page-wrapper.light .top-bar {
  background: #fff;
  border-color: #e0e0e0;
}
.brand { display: flex; align-items: center; gap: 8px; }
.brand-icon { font-size: 20px; }
.brand-text { font-size: 16px; font-weight: 700; color: #e94560; }
.status-indicators { display: flex; align-items: center; gap: 16px; font-size: 12px; }
.indicator { display: flex; align-items: center; gap: 4px; }
.nav-link {
  cursor: pointer;
  color: #888;
  transition: color 0.2s;
}
.nav-link:hover { color: #e94560; }

/* ── 三管道卡片 ── */
.pipeline-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  padding: 24px;
  flex: 1;
  align-content: start;
}

.pipeline-card {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: border-color 0.2s, transform 0.2s;
}
.pipeline-card:hover {
  border-color: #e94560;
  transform: translateY(-2px);
}
.page-wrapper.light .pipeline-card {
  background: #fff;
  border-color: #e0e0e0;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.pipeline-num {
  font-size: 24px;
  font-weight: 800;
  color: #e94560;
}
.pipeline-label { font-size: 16px; font-weight: 600; flex: 1; }
.status-badge {
  font-size: 11px;
  color: #fff;
  padding: 2px 10px;
  border-radius: 10px;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}
.pipeline-desc { font-size: 13px; color: #888; }
.pipeline-flow {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  background: #0f0f1a;
  padding: 10px 12px;
  border-radius: 8px;
}
.page-wrapper.light .pipeline-flow {
  background: #f0f0f0;
}
.arrow { color: #555; }
.highlight { color: #4ade80; font-weight: 600; }

.stats-row { font-size: 13px; color: #888; }

.btn-start {
  padding: 12px;
  border: none;
  border-radius: 8px;
  background: #e94560;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-start:hover { background: #d63850; }
.btn-start:disabled {
  background: #555;
  cursor: not-allowed;
}
.btn-secondary {
  padding: 10px;
  border: 1px solid #333;
  border-radius: 8px;
  background: transparent;
  color: #888;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-secondary:hover { border-color: #e94560; color: #e94560; }

@media (max-width: 900px) {
  .pipeline-grid { grid-template-columns: 1fr; }
}
</style>
