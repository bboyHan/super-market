const BASE_URL = ''

async function request<T = any>(
  method: string,
  url: string,
  body?: any,
  headers?: Record<string, string>
): Promise<T> {
  const options: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  }

  if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    options.body = JSON.stringify(body)
  }

  try {
    const response = await fetch(`${BASE_URL}${url}`, options)

    if (!response.ok) {
      const errorText = await response.text()
      let errorData: any
      try {
        errorData = JSON.parse(errorText)
      } catch {
        errorData = { message: errorText }
      }
      throw new Error(errorData.message || `Request failed with status ${response.status}`)
    }

    const text = await response.text()
    if (!text) return null as T
    return JSON.parse(text) as T
  } catch (error: any) {
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      console.warn(`[API] Network error: ${url} — server may be offline`)
      throw new Error('Network error: server is offline')
    }
    throw error
  }
}

export const api = {
  get: <T = any>(url: string, headers?: Record<string, string>) =>
    request<T>('GET', url, undefined, headers),

  post: <T = any>(url: string, body?: any, headers?: Record<string, string>) =>
    request<T>('POST', url, body, headers),

  put: <T = any>(url: string, body?: any, headers?: Record<string, string>) =>
    request<T>('PUT', url, body, headers),

  delete: <T = any>(url: string, headers?: Record<string, string>) =>
    request<T>('DELETE', url, undefined, headers),
}
