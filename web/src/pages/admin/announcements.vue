<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import { Plus, Trash2 } from 'lucide-vue-next'

const announcements = ref<any[]>([])
const loading = ref(true)
const showForm = ref(false)
const title = ref('')
const content = ref('')
const targetRole = ref('ALL')

async function load() {
  try {
    const r = await api.get('/api/admin/announcements')
    announcements.value = r.data || []
  } catch (e) { console.error(e) }
  loading.value = false
}

async function create() {
  if (!title.value.trim()) return
  try {
    await api.post('/api/admin/announcements', { title: title.value, content: content.value, target_role: targetRole.value })
    title.value = ''; content.value = ''; showForm.value = false
    await load()
  } catch (e: any) { alert(e.message) }
}

async function remove(id: number) {
  if (!confirm('确认删除此公告？')) return
  try { await api.delete(`/api/admin/announcements/${id}`); await load() }
  catch (e: any) { alert(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-bold text-[var(--color-text)]">系统公告</h2>
      <button class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded bg-[var(--color-primary)] text-white" @click="showForm = !showForm">
        <Plus class="w-3.5 h-3.5" /> 发布公告
      </button>
    </div>

    <div v-if="showForm" class="p-4 mb-4 bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg space-y-3">
      <input v-model="title" placeholder="公告标题" class="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-[var(--color-text)]" />
      <textarea v-model="content" placeholder="公告内容" rows="3" class="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-[var(--color-text)]"></textarea>
      <div class="flex items-center gap-2">
        <select v-model="targetRole" class="px-3 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-[var(--color-text)]">
          <option value="ALL">全部用户</option>
          <option value="SUPPLIER">仅供应商</option>
          <option value="AGENT">仅代理商</option>
        </select>
        <button class="px-4 py-1.5 text-sm bg-[var(--color-primary)] text-white rounded" @click="create">发布</button>
        <button class="px-4 py-1.5 text-sm bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] rounded" @click="showForm = false">取消</button>
      </div>
    </div>

    <div v-if="loading" class="text-center py-12 text-[var(--color-text-muted)]">加载中...</div>
    <div v-else-if="announcements.length === 0" class="text-center py-12 text-[var(--color-text-muted)]">暂无公告</div>
    <div v-for="a in announcements" :key="a.id" class="p-4 mb-2 bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg">
      <div class="flex items-start justify-between">
        <div>
          <div class="text-sm font-medium text-[var(--color-text)]">{{ a.title }}</div>
          <div class="text-xs text-[var(--color-text-muted)] mt-1">{{ a.content || '-' }}</div>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs px-2 py-0.5 rounded bg-[var(--color-bg)] text-[var(--color-text-muted)]">{{ a.target_role }}</span>
          <button class="text-[var(--color-danger)] hover:underline text-xs" @click="remove(a.id)"><Trash2 class="w-3.5 h-3.5" /></button>
        </div>
      </div>
      <div class="text-xs text-[var(--color-text-muted)] mt-2">{{ a.created_at?.slice(0, 16) || '' }}</div>
    </div>
  </div>
</template>
