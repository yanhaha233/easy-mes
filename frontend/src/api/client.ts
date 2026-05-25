const API_BASE = '/api/v1'
export const AUTH_EXPIRED_EVENT = 'easy-mes:auth-expired'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type QueryValue = string | number | boolean | null | undefined

function buildQuery(params?: Record<string, QueryValue>) {
  if (!params) {
    return ''
  }
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value))
    }
  }
  const text = query.toString()
  return text ? `?${text}` : ''
}

async function readError(response: Response) {
  try {
    const data = await response.json()
    if (typeof data.detail === 'string') {
      return data.detail
    }
    if (data.detail?.message) {
      return data.detail.message
    }
    return JSON.stringify(data.detail ?? data)
  } catch {
    return response.statusText || '请求失败'
  }
}

function buildHeaders(body: BodyInit | null | undefined, headers?: HeadersInit) {
  const merged = new Headers(headers)
  if (body && !merged.has('Content-Type')) {
    merged.set('Content-Type', 'application/json')
  }
  return merged
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & { query?: Record<string, QueryValue> } = {},
): Promise<T> {
  const { query, headers, body, credentials, ...rest } = options
  const response = await fetch(`${API_BASE}${path}${buildQuery(query)}`, {
    ...rest,
    credentials: credentials ?? 'include',
    headers: buildHeaders(body, headers),
    body,
  })

  if (!response.ok) {
    const message = await readError(response)
    if (response.status === 401 && path !== '/auth/login' && path !== '/auth/me') {
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT))
    }
    throw new ApiError(response.status, message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
