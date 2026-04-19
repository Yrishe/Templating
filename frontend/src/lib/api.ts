const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ─── Per-tab token storage ──────────────────────────────────────────────────
//
// Tokens live in `sessionStorage` instead of httpOnly cookies so each browser
// tab holds its own session. httpOnly cookies are per-origin, not per-tab, so
// they can't hold two simultaneous sessions (Alice in one tab, Bob in another)
// — whichever tab logs in last overwrites the cookie for everyone. sessionStorage
// is per-tab and survives reloads, which is exactly the isolation we want.
//
// Trade-off: `sessionStorage` is JS-readable, so an XSS vulnerability could
// exfiltrate the tokens. Mitigated by:
//   1. 15-minute access token lifetime (SIMPLE_JWT setting)
//   2. Refresh rotation + blacklist (ROTATE_REFRESH_TOKENS = True)
//   3. CSP hardening (see PLANS.md #5)

const ACCESS_KEY = 'auth.access'
const REFRESH_KEY = 'auth.refresh'

// Guard for SSR — sessionStorage is undefined during Next.js server render.
const hasStorage = () => typeof window !== 'undefined' && !!window.sessionStorage

export const tokenStorage = {
  getAccess(): string | null {
    if (!hasStorage()) return null
    return window.sessionStorage.getItem(ACCESS_KEY)
  },
  getRefresh(): string | null {
    if (!hasStorage()) return null
    return window.sessionStorage.getItem(REFRESH_KEY)
  },
  set(access: string, refresh: string) {
    if (!hasStorage()) return
    window.sessionStorage.setItem(ACCESS_KEY, access)
    window.sessionStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    if (!hasStorage()) return
    window.sessionStorage.removeItem(ACCESS_KEY)
    window.sessionStorage.removeItem(REFRESH_KEY)
  },
}

// ─── Refresh coordination ───────────────────────────────────────────────────
//
// If multiple requests hit a 401 at the same time, we only want one refresh
// call — the rest wait on the shared promise and then retry.

let refreshPromise: Promise<boolean> | null = null

async function tryRefreshToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise
  const refresh = tokenStorage.getRefresh()
  if (!refresh) return false

  refreshPromise = fetch(`${API_BASE}/api/auth/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })
    .then(async (res) => {
      if (!res.ok) {
        tokenStorage.clear()
        return false
      }
      const body = (await res.json()) as { access?: string; refresh?: string }
      if (!body.access || !body.refresh) return false
      tokenStorage.set(body.access, body.refresh)
      return true
    })
    .catch(() => {
      tokenStorage.clear()
      return false
    })
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

// ─── Fetch wrapper ──────────────────────────────────────────────────────────

function buildFetchOptions(options: RequestInit): RequestInit {
  const access = tokenStorage.getAccess()
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...((options.headers as Record<string, string> | undefined) ?? {}),
  }
  if (access) {
    headers.Authorization = `Bearer ${access}`
  }
  return {
    ...options,
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
