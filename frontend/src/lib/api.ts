const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ─── Access-token storage ───────────────────────────────────────────────────
//
// Access tokens live here — in the JS heap, not sessionStorage. XSS can
// still read this in the same tab, but:
//   1. the token has a 15-minute TTL, and
//   2. the refresh token is in an HttpOnly cookie the attacker can't read,
// so an exfiltrated access alone buys at most a 15-minute window, not a
// renewable session (finding #5 — see CHANGELOG). Multi-tab different-users
// is no longer supported; users needing concurrent sessions use Chrome
// profiles or incognito.

let accessToken: string | null = null

export const accessTokenStore = {
  get: (): string | null => accessToken,
  set: (t: string) => { accessToken = t },
  clear: () => { accessToken = null },
}

// ─── Refresh coordination ───────────────────────────────────────────────────
//
// If multiple requests hit a 401 at the same time, we only want one refresh
// call — the rest wait on the shared promise and then retry.

let refreshPromise: Promise<boolean> | null = null

export async function tryRefreshToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise

  refreshPromise = fetch(`${API_BASE}/api/auth/token/refresh/`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  })
    .then(async (res) => {
      if (!res.ok) {
        accessTokenStore.clear()
        return false
      }
      const body = (await res.json()) as { access?: string }
      if (!body.access) return false
      accessTokenStore.set(body.access)
      return true
    })
    .catch(() => {
      accessTokenStore.clear()
      return false
    })
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

// ─── Fetch wrapper ──────────────────────────────────────────────────────────

function buildFetchOptions(options: RequestInit): RequestInit {
  const access = accessTokenStore.get()
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...((options.headers as Record<string, string> | undefined) ?? {}),
  }
  if (access) {
    headers.Authorization = `Bearer ${access}`
  }
  return {
    ...options,
    credentials: 'include',
    headers,
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
  let res = await fetch(`${API_BASE}${path}`, buildFetchOptions(options))

  // On 401, try refreshing the access token once and retry. Skip refresh for
  // the refresh endpoint itself to avoid an infinite loop.
  if (res.status === 401 && !path.includes('/auth/token/refresh/')) {
    const refreshed = await tryRefreshToken()
    if (refreshed) {
      res = await fetch(`${API_BASE}${path}`, buildFetchOptions(options))
    }
  }

  if (!res.ok) {
    const error = (await res.json().catch(() => ({}))) as Record<string, unknown>
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

// Authenticated binary download. `url` may be absolute (returned by
// DRF's `request.build_absolute_uri`) or a relative API path. The browser
// can't attach the Bearer token to an `<a href>` click, so we fetch the
// blob ourselves and trigger the download from an object URL.
export async function downloadAuthed(url: string, filenameFallback = 'download'): Promise<void> {
  const resolved = url.startsWith('http') ? url : `${API_BASE}${url}`
  const doFetch = () => fetch(resolved, buildFetchOptions({ method: 'GET' }))
  let res = await doFetch()
  if (res.status === 401 && (await tryRefreshToken())) {
    res = await doFetch()
  }
  if (!res.ok) {
    throw new Error(`Download failed: HTTP ${res.status}`)
  }
  const blob = await res.blob()
  const filename =
    res.headers
      .get('content-disposition')
      ?.match(/filename="?([^"]+)"?/i)?.[1] ?? filenameFallback
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}
