const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

let isRefreshing = false
let refreshPromise: Promise<boolean> | null = null

async function tryRefreshToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise
  isRefreshing = true
  refreshPromise = fetch(`${API_BASE}/api/auth/token/refresh/`, {
    method: 'POST',
    credentials: 'include',
  })
    .then((res) => res.ok)
    .catch(() => false)
    .finally(() => {
      isRefreshing = false
      refreshPromise = null
    })
  return refreshPromise
}

function buildFetchOptions(options: RequestInit): RequestInit {
  return {
    ...options,
    credentials: 'include',
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  }
}

function throwApiError(error: Record<string, unknown>, status: number): never {
  if (typeof error.detail === 'string') {
    throw new Error(error.detail)
  }
  const fieldMessages = Object.entries(error)
    .flatMap(([field, msgs]) => {
      const list = Array.isArray(msgs) ? msgs : [String(msgs)]
      return field === 'non_field_errors' ? list : list.map((m) => `${field}: ${m}`)
    })
  throw new Error(fieldMessages.length ? fieldMessages.join('; ') : `HTTP ${status}`)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const fetchOpts = buildFetchOptions(options)
  let res = await fetch(`${API_BASE}${path}`, fetchOpts)

  // On 401, try refreshing the access token once and retry
  if (res.status === 401 && !path.includes('/auth/token/refresh/')) {
    const refreshed = await tryRefreshToken()
    if (refreshed) {
      res = await fetch(`${API_BASE}${path}`, buildFetchOptions(options))
    }
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({})) as Record<string, unknown>
    throwApiError(error, res.status)
  }
  if (res.status === 204) {
    return undefined as unknown as T
  }
  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  postForm: <T>(path: string, body: FormData) =>
    request<T>(path, { method: 'POST', body }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  patchForm: <T>(path: string, body: FormData) =>
    request<T>(path, { method: 'PATCH', body }),
  delete: (path: string) => request(path, { method: 'DELETE' }),
}
