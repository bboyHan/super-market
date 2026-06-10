<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const apiKey = ref('')
const loading = ref(false)
const error = ref('')
const showKey = ref(false)

async function handleLogin() {
  if (!apiKey.value.trim()) {
    error.value = '请输入授权码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('http://localhost:8800/api/platform/auth-token-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey.value.trim() }),
    })
    const data = await res.json()
    if (data.code === 0 && data.data?.token) {
      localStorage.setItem('agent-token', data.data.token)
      localStorage.setItem('agent-info', JSON.stringify(data.data))
      router.push('/dashboard')
    } else {
      error.value = data.msg || '授权失败，请检查授权码'
    }
  } catch (e: any) {
    error.value = '连接失败：' + (e.message || '无法连接到服务端')
  }
  loading.value = false
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--accent-primary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="12" r="3" />
          <line x1="12" y1="2" x2="12" y2="6" />
          <line x1="12" y1="18" x2="12" y2="22" />
          <line x1="2" y1="12" x2="6" y2="12" />
          <line x1="18" y1="12" x2="22" y2="12" />
        </svg>
        <h1 class="login-title">凭证采集站</h1>
        <p class="login-desc">请输入授权码以登录</p>
      </div>

      <div class="login-form">
        <div class="field">
          <label>授权码（API Key）</label>
          <div class="input-wrapper">
            <input
              v-model="apiKey"
              :type="showKey ? 'text' : 'password'"
              class="input"
              placeholder="sk_xxxxxxxx..."
              @keyup.enter="handleLogin"
            />
            <button class="toggle-vis" @click="showKey = !showKey">
              <svg v-if="showKey" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          </div>
        </div>

        <p v-if="error" class="error-msg">{{ error }}</p>

        <button class="btn btn-primary btn-login" @click="handleLogin" :disabled="loading">
          <span v-if="loading">验证中...</span>
          <span v-else>登录</span>
        </button>
      </div>

      <div class="login-footer">
        <p class="hint">授权码由平台管理员生成</p>
        <p class="hint">首次使用请联系管理员获取</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--bg-primary);
  padding: 20px;
}
.login-card {
  width: 400px;
  max-width: 100%;
  padding: 40px 32px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  text-align: center;
}
.login-logo {
  margin-bottom: 28px;
}
.login-title {
  font-size: 22px;
  font-weight: 700;
  margin: 16px 0 6px;
  color: var(--text-primary);
}
.login-desc {
  font-size: 13px;
  color: var(--text-muted);
}
.login-form {
  text-align: left;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}
.field label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.input-wrapper {
  display: flex;
  align-items: center;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-primary);
  overflow: hidden;
}
.input-wrapper:focus-within {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 2px var(--accent-primary-bg);
}
.input {
  flex: 1;
  padding: 12px 14px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 14px;
  font-family: var(--font-mono, monospace);
  outline: none;
}
.input::placeholder {
  color: var(--text-muted);
  font-family: var(--font-sans, sans-serif);
}
.toggle-vis {
  background: none;
  border: none;
  padding: 8px 12px;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
}
.toggle-vis:hover {
  color: var(--text-secondary);
}
.error-msg {
  color: var(--accent-red, #ef4444);
  font-size: 12px;
  margin: -8px 0 12px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 6px;
}
.btn-login {
  width: 100%;
  padding: 12px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 8px;
  margin-top: 4px;
}
.login-footer {
  margin-top: 24px;
}
.hint {
  font-size: 11px;
  color: var(--text-muted);
  margin: 2px 0;
}
</style>
