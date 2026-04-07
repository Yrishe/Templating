const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include', // send httpOnly cookies
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({})) as Record<string, unknown>
    // DRF returns { detail: "..." } for non-field errors, or { field: ["msg"] } for validation errors
    if (typeof error.detail === 'string') {
      throw new Error(error.detail)
    }
    const fieldMessages = Object.entries(error)
      .flatMap(([field, msgs]) => {
        const list = Array.isArray(msgs) ? msgs : [String(msgs)]
        return field === 'non_field_errors' ? list : list.map((m) => `${field}: ${m}`)
      })
    throw new Error(fieldMessages.length ? fieldMessages.join('; ') : `HTTP ${res.status}`)
  }
  // Handle 204 No Content
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
