<script setup lang="ts">
import type { TaskStep } from '@/stores/tasks'

defineProps<{
  steps: TaskStep[]
  currentProgress?: number
}>()

function stepIcon(status: TaskStep['status']) {
  if (status === 'done') {
    return 'done'
  }
  if (status === 'doing') {
    return 'doing'
  }
  if (status === 'error') {
    return 'error'
  }
  return 'pending'
}
</script>

<template>
  <div class="task-progress">
    <div v-if="currentProgress !== undefined" class="progress-section">
      <div class="progress-header">
        <span class="progress-label">Overall Progress</span>
        <span class="progress-value">{{ currentProgress }}%</span>
      </div>
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: currentProgress + '%', background: 'var(--accent-primary)' }"
        />
      </div>
    </div>

    <div class="steps-list">
      <div
        v-for="(step, index) in steps"
        :key="index"
        class="step-item"
        :class="step.status"
      >
        <div class="step-indicator">
          <!-- Done: green check -->
          <svg v-if="stepIcon(step.status) === 'done'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-green)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" fill="rgba(34,197,94,0.15)" />
            <polyline points="9 12 11 14 15 10" />
          </svg>
          <!-- Doing: spinning loader -->
          <svg v-else-if="stepIcon(step.status) === 'doing'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="spinner">
            <circle cx="12" cy="12" r="10" fill="rgba(99,102,241,0.1)" />
            <line x1="12" y1="2" x2="12" y2="6" />
            <line x1="12" y1="18" x2="12" y2="22" />
          </svg>
          <!-- Error: red X -->
          <svg v-else-if="stepIcon(step.status) === 'error'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-red)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" fill="rgba(239,68,68,0.15)" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          <!-- Pending: empty circle -->
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" />
          </svg>
        </div>
        <div class="step-content">
          <span class="step-name">{{ step.name }}</span>
          <span v-if="step.time" class="step-time">{{ step.time }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-progress {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.progress-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent-primary);
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  transition: background 0.2s ease;
}

.step-item:hover {
  background: var(--bg-hover);
}

.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
}

.step-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 1;
}

.step-name {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.step-item.pending .step-name {
  color: var(--text-muted);
}

.step-item.done .step-name {
  color: var(--accent-green);
}

.step-time {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
