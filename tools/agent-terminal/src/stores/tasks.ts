import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/utils/api'

export interface TaskStep {
  name: string
  status: 'pending' | 'doing' | 'done' | 'error'
  time?: string
}

export interface Task {
  id: string
  platform: string
  product: string
  quantity: number
  method: string
  auto_mode: boolean
  status: 'idle' | 'running' | 'paused' | 'completed' | 'error'
  progress: number
  steps: TaskStep[]
  logs: string[]
  created_at: string
}

export const useTasksStore = defineStore('tasks', () => {
  const currentTask = ref<Task | null>(null)
  const taskQueue = ref<Task[]>([])
  const isRunning = computed(() => currentTask.value?.status === 'running')
  const eventSource = ref<EventSource | null>(null)

  const defaultSteps: TaskStep[] = [
    { name: 'Initialize task', status: 'pending' },
    { name: 'Validate parameters', status: 'pending' },
    { name: 'Check account balance', status: 'pending' },
    { name: 'Login to platform', status: 'pending' },
    { name: 'Navigate to product', status: 'pending' },
    { name: 'Configure purchase', status: 'pending' },
    { name: 'Execute purchase', status: 'pending' },
    { name: 'Verify transaction', status: 'pending' },
    { name: 'Clean up session', status: 'pending' },
  ]

  function createTask(params: {
    platform: string
    product: string
    quantity: number
    method: string
    auto_mode: boolean
    account_id?: string
  }) {
    const newTask: Task = {
      id: Date.now().toString(),
      ...params,
      status: 'idle',
      progress: 0,
      steps: defaultSteps.map(s => ({ ...s })),
      logs: [],
      created_at: new Date().toISOString(),
    }
    taskQueue.value.push(newTask)
    return newTask
  }

  function startTask(taskId: string) {
    const task = taskQueue.value.find(t => t.id === taskId)
    if (!task) return

    currentTask.value = task
    task.status = 'running'

    api.post('/api/tasks/start', {
      platform: task.platform,
      product: task.product,
      quantity: task.quantity,
      method: task.method,
      auto_mode: task.auto_mode,
    }).catch(() => {
      task.status = 'error'
    })
  }

  async function fetchTasks() {
    try {
      const data = await api.get('/api/tasks')
      taskQueue.value = data.tasks || []
      if (data.current_task) {
        currentTask.value = data.current_task
      }
    } catch {
      // Server not available
    }
  }

  function connectSSE() {
    if (eventSource.value) return

    const es = new EventSource('/api/sse/logs')
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (currentTask.value) {
          if (data.progress !== undefined) {
            currentTask.value.progress = data.progress
          }
          if (data.steps) {
            currentTask.value.steps = data.steps
          }
          if (data.log) {
            currentTask.value.logs.push(data.log)
          }
          if (data.status) {
            currentTask.value.status = data.status
          }
        }
      } catch {
        // Ignore parse errors
      }
    }
    es.onerror = () => {
      es.close()
      eventSource.value = null
      setTimeout(() => connectSSE(), 3000)
    }
    eventSource.value = es
  }

  function disconnectSSE() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
  }

  function updateStep(stepIndex: number, status: TaskStep['status']) {
    if (currentTask.value && currentTask.value.steps[stepIndex]) {
      currentTask.value.steps[stepIndex].status = status
      currentTask.value.steps[stepIndex].time = new Date().toLocaleTimeString()
    }
  }

  function resetTask() {
    currentTask.value = null
  }

  function removeFromQueue(taskId: string) {
    taskQueue.value = taskQueue.value.filter(t => t.id !== taskId)
  }

  return {
    currentTask,
    taskQueue,
    isRunning,
    defaultSteps,
    createTask,
    startTask,
    fetchTasks,
    connectSSE,
    disconnectSSE,
    updateStep,
    resetTask,
    removeFromQueue,
  }
})
