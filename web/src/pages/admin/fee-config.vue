<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import { Save } from 'lucide-vue-next'

const fees = ref<any[]>([])
const loading = ref(true)
const saving = ref(false)
const message = ref('')

async function load() {
  try {
    const r = await api.get('/api/admin/fee-config')
    fees.value = r.data || []
  } catch (e) { console.error(e) }
  loading.value = false
}

async function updateFee(f: any) {
  saving.value = true; message.value = ''
  try {
    await api.put(`/api/admin/fee-config/${f.id}?fee_rate=${f.fee_rate}&enabled=${f.enabled}`)
    message.value = `费率 ${f.fee_name} 已更新`
  } catch (e: any) { message.value = e.message || '保存失败' }
  saving.value = false
}

const feeLabels: Record<string, string> = {
  order_fee: '订单交易手续费',
  withdraw_fee: '提现手续费',
}

onMounted(load)
</script>

<template>
  <div class="p-6 max-w-2xl">
    <h2 class="text-xl font-bold text-[var(--color-text)] mb-4">手续费率配置</h2>
    <div v-if="loading" class="text-center py-12 text-[var(--color-text-muted)]">加载中...</div>
    <div v-else-if="fees.length === 0" class="text-center py-12 text-[var(--color-text-muted)]">暂无配置</div>
    <div v-for="f in fees" :key="f.id" class="p-4 mb-3 bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg">
      <div class="flex items-center gap-4">
        <div class="flex-1">
          <div class="text-sm font-medium text-[var(--color-text)]">{{ feeLabels[f.fee_name] || f.fee_name }}</div>
          <div class="text-xs text-[var(--color-text-muted)]">{{ f.description }}</div>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-[var(--color-text-muted)]">费率 %</span>
          <input type="number" v-model.number="f.fee_rate" step="0.001" min="0" max="1"
            class="w-20 px-2 py-1 text-xs text-center bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-[var(--color-text)]"
          />
          <span class="text-xs text-[var(--color-text-muted)]">({{ (f.fee_rate * 100).toFixed(2) }}%)</span>
        </div>
        <label class="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" v-model="f.enabled" class="sr-only peer" />
          <div class="w-8 h-4 bg-gray-600 rounded-full peer peer-checked:bg-[var(--color-primary)] after:content-[''] after:absolute after:top-0.5 after:start-0.5 after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:after:translate-x-4"></div>
        </label>
        <button class="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-[var(--color-primary)] text-white disabled:opacity-50" :disabled="saving" @click="updateFee(f)">
          <Save class="w-3 h-3" /> 保存
        </button>
      </div>
    </div>
    <div v-if="message" class="text-sm mt-2" :class="message.includes('已更新') ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">{{ message }}</div>
  </div>
</template>
