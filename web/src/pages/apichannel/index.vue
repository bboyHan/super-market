<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { Plus, Copy, Eye, EyeOff } from 'lucide-vue-next'

const payers = ref<any[]>([])
const loading = ref(true)
const showCreate = ref(false)
const nickname = ref('')
const showKey = ref<Record<number, boolean>>({})
const showSecret = ref<Record<number, boolean>>({})
const generated = ref<any>(null)

async function load() {
  loading.value = true
  try {
    const r = await api.get<{code: number; data: any[]}>('/api/merchant/api-payers')
    payers.value = r.data
  } finally { loading.value = false }
}

async function createPayer() {
  const r = await api.post('/api/merchant/api-payers', { nickname: nickname.value })
  generated.value = r.data
  showCreate.value = false
  nickname.value = ''
  await load()
}

async function toggleStatus(p: any) {
  const ns = p.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
  await api.put(`/api/merchant/api-payers/${p.id}?status=${ns}`, {})
  await load()
}

function copy(text: string) {
  navigator.clipboard.writeText(text)
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-2xl font-bold text-[var(--color-text)]">API 渠道</h2>
        <p class="text-sm text-[var(--color-text-muted)]">创建和管理你的API支付商</p>
      </div>
      <button class="btn btn-primary btn-sm" @click="showCreate = true"><Plus class="w-4 h-4" /> 创建API支付商</button>
    </div>

    <div class="card p-0 overflow-hidden">
      <div v-if="loading" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
      <table v-else class="w-full text-sm">
        <thead><tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">商户</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">API Key</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">API Secret</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">状态</th>
          <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">操作</th>
        </tr></thead>
        <tbody>
        <tr v-for="p in payers" :key="p.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
          <td class="p-3 font-medium">{{ p.nickname }}</td>
          <td class="p-3">
            <div class="flex items-center gap-1">
              <code class="text-xs bg-[var(--color-bg)] px-1.5 py-0.5 rounded font-mono">
                {{ showKey[p.id] ? p.api_key : p.api_key?.slice(0,8)+'...' }}
              </code>
              <button @click="showKey[p.id]=!showKey[p.id]" class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <Eye v-if="!showKey[p.id]" class="w-3 h-3" /><EyeOff v-else class="w-3 h-3" />
              </button>
              <button @click="copy(p.api_key)" class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <Copy class="w-3 h-3" />
              </button>
            </div>
          </td>
          <td class="p-3">
            <div class="flex items-center gap-1">
              <code class="text-xs bg-[var(--color-bg)] px-1.5 py-0.5 rounded font-mono">
                {{ showSecret[p.id] ? p.api_secret : '••••••••'+p.api_secret?.slice(-4) }}
              </code>
              <button @click="showSecret[p.id]=!showSecret[p.id]" class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <Eye v-if="!showSecret[p.id]" class="w-3 h-3" /><EyeOff v-else class="w-3 h-3" />
              </button>
              <button @click="copy(p.api_secret)" class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <Copy class="w-3 h-3" />
              </button>
            </div>
          </td>
          <td class="p-3"><Badge :type="p.status === 'ACTIVE' ? 'success' : 'danger'">{{ p.status }}</Badge></td>
          <td class="p-3 text-right">
            <button class="btn btn-outline btn-sm" @click="toggleStatus(p)">{{ p.status === 'ACTIVE' ? '停用' : '启用' }}</button>
          </td>
        </tr>
        </tbody>
      </table>
      <div v-if="!loading && !payers.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">暂无API支付商，点击上方创建</div>
    </div>

    <!-- Generated credentials -->
    <div v-if="generated" class="fixed bottom-6 right-6 card p-4 max-w-sm z-50 shadow-xl border-[var(--color-accent)]">
      <h4 class="text-sm font-semibold mb-2">🎉 {{ generated.nickname }} 创建成功</h4>
      <div class="text-xs space-y-1.5">
        <div>API Key: <code class="text-[var(--color-accent)] break-all">{{ generated.api_key }}</code></div>
        <div>API Secret: <code class="text-[var(--color-warning)] break-all">{{ generated.api_secret }}</code></div>
        <p class="text-[var(--color-warning)] mt-2">⚠️ Secret 仅展示一次</p>
      </div>
      <button class="btn btn-outline btn-sm mt-3 w-full justify-center" @click="generated=null">关闭</button>
    </div>

    <!-- Create Modal -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showCreate = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-4">创建 API 支付商</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">所属供应商</label>
            <input disabled class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]/50 text-sm text-[var(--color-text-muted)] cursor-not-allowed" value="你的供应商（自动关联）" />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">商户昵称</label>
            <input v-model="nickname" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm" />
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showCreate = false">取消</button>
          <button class="btn btn-primary" @click="createPayer">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>
