// ===== Theme =====
export type ThemeMode = 'light' | 'dark'

export interface ThemeState {
  mode: ThemeMode
}

// ===== User =====

export interface UserInfo {
  id: string
  username: string
  role: string
  reference_id: number | null
  status?: string
  created_at?: string
}

export interface AuthState {
  token: string | null
  user: UserInfo | null
  isAuthenticated: boolean
}

// ===== Orders =====
export type OrderStatus = 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled'

export interface Order {
  id: string
  orderNo: string
  customerName: string
  productName: string
  quantity: number
  totalAmount: number
  status: OrderStatus
  createdAt: string
  updatedAt: string
}

// ===== Agent =====
export interface Agent {
  id: string
  name: string
  contact: string
  phone: string
  email: string
  status: 'active' | 'inactive'
  commission: number
  orderCount: number
  totalAmount: number
}

// ===== Finance =====
export interface FinanceRecord {
  id: string
  date: string
  type: 'income' | 'expense'
  category: string
  amount: number
  description: string
  status: 'completed' | 'pending' | 'failed'
}

// ===== API Channel =====
export interface ApiChannel {
  id: string
  name: string
  endpoint: string
  apiKey: string
  status: 'active' | 'inactive' | 'error'
  lastCall: string | null
  callCount: number
}

// ===== Dashboard Stats =====
export interface DashboardStats {
  totalOrders: number
  totalRevenue: number
  totalAgents: number
  pendingOrders: number
  monthlyGrowth: number
  conversionRate: number
}

// ===== Pagination =====
export interface PaginationParams {
  page: number
  pageSize: number
  total: number
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: PaginationParams
}

// ===== Navigation =====
export interface NavItem {
  label: string
  icon: string
  to: string
  children?: NavItem[]
}
