/**
 * Format a number as currency (CNY)
 */
export function formatCurrency(amount: number, currency: string = 'CNY'): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

/**
 * Format a date string
 */
export function formatDate(dateStr: string | Date, format: 'date' | 'datetime' | 'time' = 'datetime'): string {
  const date = typeof dateStr === 'string' ? new Date(dateStr) : dateStr

  const options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }

  if (format === 'datetime') {
    options.hour = '2-digit'
    options.minute = '2-digit'
  } else if (format === 'time') {
    options.hour = '2-digit'
    options.minute = '2-digit'
    options.second = '2-digit'
  }

  return new Intl.DateTimeFormat('zh-CN', options).format(date)
}

/**
 * Format a number with thousands separators
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('zh-CN').format(num)
}

/**
 * Format a percentage
 */
export function formatPercent(value: number, decimals: number = 1): string {
  return `${(value * 100).toFixed(decimals)}%`
}

/**
 * Truncate text with ellipsis
 */
export function truncateText(text: string, maxLength: number = 50): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

/**
 * Get status display color class
 */
export function getStatusColor(status: string): string {
  const colorMap: Record<string, string> = {
    active: 'text-brand-success bg-brand-success/10',
    inactive: 'text-[var(--color-text-muted)] bg-[var(--color-border)]/30',
    pending: 'text-brand-warning bg-brand-warning/10',
    processing: 'text-brand-info bg-brand-info/10',
    completed: 'text-brand-success bg-brand-success/10',
    delivered: 'text-brand-success bg-brand-success/10',
    cancelled: 'text-brand-danger bg-brand-danger/10',
    failed: 'text-brand-danger bg-brand-danger/10',
    error: 'text-brand-danger bg-brand-danger/10',
    success: 'text-brand-success bg-brand-success/10',
  }
  return colorMap[status] || 'text-[var(--color-text-muted)] bg-[var(--color-border)]/30'
}

/**
 * Get status label in Chinese
 */
export function getStatusLabel(status: string): string {
  const labelMap: Record<string, string> = {
    active: '启用',
    inactive: '停用',
    pending: '待处理',
    processing: '处理中',
    shipped: '已发货',
    delivered: '已送达',
    cancelled: '已取消',
    completed: '已完成',
    failed: '失败',
    error: '异常',
    success: '成功',
  }
  return labelMap[status] || status
}
