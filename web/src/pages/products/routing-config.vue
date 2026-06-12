<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/utils/api'
import { ArrowLeft, Save } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const productId = Number(route.params.id)

interface AgentItem {
  agent_id: number
  agent_name: string
  priority: number
  enabled: boolean
}

interface Product {
  id: number
  name: string
  category: string
}

const product = ref<Product | null>(null)
const strategy = ref('ROUND_ROBIN')
const agents = ref<AgentItem[]>([])
const allAgents = ref<{ id: number; name: string }[]>([])
const loading = ref(true)
const saving = ref(false)
const message = ref('')

const strategies = [
  { value: 'ROUND_ROBIN', label: '轮询分配', desc: '订单平均分配给各代理商' },
  { value: 'PRIORITY', label: '优先分配', desc: '按优先级顺序分配，高优先级先接单' },
  { value: 'WEIGHTED', label: '权重分配', desc: '按 priority 值比例分配' },
]

onMounted(async () => {
  try {
    const [prodRes, routeRes, agentRes] = await Promise.all([
      api.get<{ code: number; data: Product[] }>('/api/merchant/products'),
      api.get<{ code: number; data: { strategy: string; agents: AgentItem[] } }>(`/api/merchant/products/${productId}/routing`),
      api.get<{ code: number; data: { id: number; nickname: string }[] }>('/api/merchant/agents'),
    ])
    product.value = (prodRes.data || []).find((p: any) => p.id === productId) || null
    if (routeRes.data) {
      strategy.value = routeRes.data.strategy
      agents.value = routeRes.data.agents || []
    }
    allAgents.value = (agentRes.data || []).map((a: any) => ({ id: a.id, name: a.nickname }))
  } catch (e) {
    console.error('Failed to load routing config', e)
  }
  loading.value = false
})

function addAgent() {
  const unassigned = allAgents.value.filter(a => !agents.value.some(ag => ag.agent_id === a.id))
  if (unassigned.length === 0) return
  agents.value.push({ agent_id: unassigned[0].id, agent_name: unassigned[0].name, priority: agents.value.length + 1, enabled: true })
}

function removeAgent(agentId: number) {
  agents.value = agents.value.filter(a => a.agent_id !== agentId)
}

async function save() {
  saving.value = true
  message.value = ''
  try {
    const payload = agents.value.map((a, i) => ({
      agent_id: a.agent_id,
      priority: strategy.value === 'WEIGHTED' ? a.priority : i + 1,
      enabled: a.enabled,
    }))
    await api.put(`/api/merchant/products/${productId}/routing?strategy=${strategy.value}`, payload)
    message.value = '保存成功'
  } catch (e: any) {
    message.value = e.message || '保存失败'
  }
  saving.value = false
}
</script>

<template>
  <div class="p-6 max-w-3xl">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button @click="router.push('/products')" class="p-2 rounded-lg hover:bg-[var(--color-bg)] text-[var(--color-text-muted)]">
        <ArrowLeft class="w-5 h-5" />
      </button>
      <div>
        <h2 class="text-xl font-bold text-[var(--color-text)]">路由策略配置</h2>
        <p v-if="product" class="text-sm text-[var(--color-text-muted)]">{{ product.name }} · {{ product.category }}</p>
      </div>
    </div>

    <div v-if="loading" class="text-center py-12 text-[var(--color-text-muted)]">加载中...</div>

    <template v-else-if="product">
      <!-- Strategy Selection -->
      <div class="mb-6 p-4 bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg">
        <h3 class="text-sm font-semibold text-[var(--color-text)] mb-3">分配策略</h3>
        <div class="space-y-2">
          <label v-for="s in strategies" :key="s.value"
            class="flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors"
            :class="strategy === s.value ? 'border-[var(--color-primary)] bg-[var(--color-bg)]' : 'border-[var(--color-border)]'"
          >
            <input type="radio" v-model="strategy" :value="s.value" class="mt-0.5" />
            <div>
              <div class="text-sm font-medium text-[var(--color-text)]">{{ s.label }}</div>
              <div class="text-xs text-[var(--color-text-muted)]">{{ s.desc }}</div>
            </div>
          </label>
        </div>
      </div>

      <!-- Agent Assignment -->
      <div class="mb-6 p-4 bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-[var(--color-text)]">代理商分配</h3>
          <button class="text-xs px-3 py-1.5 rounded bg-[var(--color-primary)] text-white hover:opacity-90" @click="addAgent">+ 添加代理商</button>
        </div>

        <div v-if="agents.length === 0" class="text-sm text-[var(--color-text-muted)] text-center py-8">
          尚未分配代理商，点击"添加代理商"开始配置
        </div>

        <div v-for="(ag, i) in agents" :key="ag.agent_id"
          class="flex items-center gap-3 p-3 mb-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]"
        >
          <span class="text-xs text-[var(--color-text-muted)] w-5">{{ i + 1 }}</span>
          <div class="flex-1">
            <div class="text-sm font-medium text-[var(--color-text)]">{{ ag.agent_name }}</div>
            <div class="text-xs text-[var(--color-text-muted)]">ID: {{ ag.agent_id }}</div>
          </div>
          <div v-if="strategy === 'WEIGHTED'" class="flex items-center gap-2">
            <label class="text-xs text-[var(--color-text-muted)]">权重</label>
            <input type="number" v-model.number="ag.priority" min="1" max="100"
              class="w-16 px-2 py-1 text-xs text-center bg-[var(--color-bg-elevated)] border border-[var(--color-border)] rounded text-[var(--color-text)]"
            />
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" v-model="ag.enabled" class="sr-only peer" />
            <div class="w-8 h-4 bg-gray-600 rounded-full peer peer-checked:bg-[var(--color-primary)] after:content-[''] after:absolute after:top-0.5 after:start-0.5 after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:after:translate-x-4"></div>
          </label>
          <button class="text-xs text-[var(--color-danger)] hover:underline" @click="removeAgent(ag.agent_id)">移除</button>
        </div>
      </div>

      <!-- Save -->
      <div class="flex items-center gap-3">
        <button class="flex items-center gap-2 px-5 py-2.5 bg-[var(--color-primary)] text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50"
          :disabled="saving" @click="save">
          <Save class="w-4 h-4" /> {{ saving ? '保存中...' : '保存配置' }}
        </button>
        <span v-if="message" class="text-sm" :class="message === '保存成功' ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">{{ message }}</span>
      </div>
    </template>

    <div v-else class="text-center py-12 text-[var(--color-danger)]">货品不存在或未授权</div>
  </div>
</template>
