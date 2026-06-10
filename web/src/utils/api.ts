type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface RequestOptions {
  headers?: Record<string, string>
  params?: Record<string, string | number | boolean>
  signal?: AbortSignal
}

const BASE_URL = ''  // proxied by Vite to backend

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  method: HttpMethod,
  url: string,
  body?: unknown,
  options: RequestOptions = {}
): Promise<T> {
  const token = localStorage.getItem('auth-token')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Build query string
  let fullUrl = `${BASE_URL}${url}`
  if (options.params) {
    const params = new URLSearchParams()
    Object.entries(options.params).forEach(([key, value]) => {
      params.append(key, String(value))
    })
    fullUrl += `?${params.toString()}`
  }

  const config: RequestInit = {
    method,
    headers,
    signal: options.signal,
  }

  if (body && method !== 'GET') {
    config.body = JSON.stringify(body)
  }

  const response = await fetch(fullUrl, config)

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`
    try {
      const errorData = await response.json()
      errorMessage = errorData?.message || errorMessage
      throw new ApiError(response.status, errorMessage, errorData)
    } catch (e) {
      if (e instanceof ApiError) throw e
      throw new ApiError(response.status, errorMessage)
    }
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

export const api = {
  get<T>(url: string, options?: RequestOptions): Promise<T> {
    return request<T>('GET', url, undefined, options)
  },
  post<T>(url: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>('POST', url, body, options)
  },
  put<T>(url: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>('PUT', url, body, options)
  },
  patch<T>(url: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>('PATCH', url, body, options)
  },
  delete<T>(url: string, options?: RequestOptions): Promise<T> {
    return request<T>('DELETE', url, undefined, options)
  },
}

export default api
