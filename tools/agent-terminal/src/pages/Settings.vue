<script setup lang="ts">
import { ref } from 'vue'
import { platformApi } from '../utils/platformApi'

const platformUrl = ref('http://localhost:8000')
const apiKey = ref('')
const connected = ref<boolean | null>(null)
const connecting = ref(false)

async function testConnection() {
  connecting.value = true
  connected.value = null
  platformApi.setApiKey(apiKey.value)
  try {
    const profile = await platformApi.login(apiKey.value)
    connected.value = true
  } catch {
    connected.value = false
  } finally {
    connecting.value = false
  }
}

function saveSettings() {
  localStorage.setItem('platform_url', platformUrl.value)
  localStorage.setItem('api_key', apiKey.value)
}
</script>

<template>
  <div class="settings">
    <h2 class="page-title">设置</h2>

    <div class="setting-group">
      <h3>平台连接</h3>

      <div class="field">
        <label>平台地址</label>
        <input v-model="platformUrl" placeholder="http://localhost:8000" />
      </div>

      <div class="field">
        <label>API Key</label>
        <input v-model="apiKey" type="password" placeholder="sk_..." />
      </div>

      <button class="btn" @click="testConnection" :disabled="connecting">
        {{ connecting ? '连接中...' : '测试连接' }}
      </button>

      <div v-if="connected === true" class="status-ok">✅ 连接成功</div>
      <div v-else-if="connected === false" class="status-fail">❌ 连接失败</div>
    </div>

    <div class="setting-group">
      <h3>DataProbe 引擎</h3>
      <div class="field">
        <label>API 端口</label>
        <input value="18801" disabled />
        <span class="hint">默认 18801，在 Electron 主进程中配置</span>
      </div>
    </div>

    <button class="btn btn-save" @click="saveSettings">保存设置</button>
  </div>
</template>

<style scoped>
.settings { padding: 20px; max-width: 600px; }
.page-title { font-size: 20px; font-weight: 700; margin-bottom: 20px; }
.setting-group { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.setting-group h3 { font-size: 14px; font-weight: 600; margin-bottom: 16px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 12px; color: #8b949e; margin-bottom: 4px; }
.field input { width: 100%; padding: 8px 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 13px; }
.field input:focus { border-color: #58a6ff; outline: none; }
.field input:disabled { color: #484f58; }
.hint { display: block; font-size: 11px; color: #484f58; margin-top: 4px; }
.btn { padding: 8px 20px; background: #238636; color: #fff; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn:hover { background: #2ea043; }
.btn:disabled { background: #1a5f2a; color: #8b949e; cursor: not-allowed; }
.btn-save { margin-top: 8px; }
.status-ok { margin-top: 10px; font-size: 13px; color: #3fb950; }
.status-fail { margin-top: 10px; font-size: 13px; color: #f85149; }
</style>
