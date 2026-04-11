import { NextResponse, type NextRequest } from 'next/server'

/**
 * Content-Security-Policy + complementary security headers.
 *
 * Why this exists: auth tokens moved to per-tab `sessionStorage` so an XSS
 * vulnerability anywhere in the frontend (or in a poisoned dependency)
 * could exfiltrate them. CSP is the load-bearing mitigation — it keeps an
 * attacker from landing the script in the first place. See
 * `docs/SECURITY.md` §1 and `PLANS.md §5` for the full rationale.
 *
 * Scope of the policy (production):
 *   - `script-src 'self'` — no inline scripts, no eval, no remote scripts.
 *     Next.js in production serves every chunk from `/_next/static/...`
 *     which is same-origin, so `'self'` is sufficient. The app has no
 *     `<Script>` tags, no `dangerouslySetInnerHTML`, and no third-party
 *     scripts (verified by grep).
 *   - `style-src 'self' 'unsafe-inline'` — Tailwind and the
 *     `--shadow-lifted` inline `[box-shadow:...]` utility in Card both
 *     rely on inline styles. This is the only `'unsafe-inline'` we keep;
 *     it's the standard concession for a Tailwind/CSS-in-JS pipeline and
 *     script-src is the one that actually matters for XSS.
 *   - `img-src 'self' data: blob:` — `data:` for base64 icons, `blob:`
 *     so the user can preview a PDF they're about to upload.
 *   - `connect-src` includes the API origin and the WS origin — both are
 *     baked into `NEXT_PUBLIC_*` at build time and read here on the
 *     server side.
 *   - `frame-ancestors 'none'` — the app can't be iframed, which
 *     neutralises clickjacking.
 *
 * Dev vs prod:
 *   - Prod: `Content-Security-Policy` (enforced, request-blocking).
 *   - Dev: `Content-Security-Policy-Report-Only` with the dev-relaxed
 *     policy (`'unsafe-eval'` and `'unsafe-inline'` on script-src
 *     because Next.js's HMR client evals inline chunks during reloads).
 *     Report-only means violations log to the browser console but don't
 *     break the dev server. Flip this to enforced if you want to prove
 *     the prod policy works — but expect HMR to fail.
 */

const isProd = process.env.NODE_ENV === 'production'

// Read from the same env vars the API client + WS client use, so everything
// stays in sync. Fallbacks are dev-only and match `lib/constants.ts`.
const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const WS_ORIGIN = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'

function buildCsp(): string {
  const scriptSrc = isProd
    ? ["'self'"]
    : // Dev: Next.js's HMR client uses eval + inline. Loose here, strict in prod.
      ["'self'", "'unsafe-eval'", "'unsafe-inline'"]

  return [
    "default-src 'self'",
    `script-src ${scriptSrc.join(' ')}`,
    // Tailwind + `[box-shadow:var(--shadow-lifted)]` arbitrary-value utilities
    // require inline styles. Acceptable trade-off; script-src is the XSS lever.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self' ${API_ORIGIN} ${WS_ORIGIN}`,
    // Next.js image optimization uses blob: URLs for some preview flows.
    "media-src 'self' blob:",
    // Nothing should ever load a Flash/Java/Silverlight plugin.
    "object-src 'none'",
    // Prevent this page from being embedded as an iframe (clickjacking).
    "frame-ancestors 'none'",
    // `<base href>` can't be hijacked to rewrite relative URLs.
    "base-uri 'self'",
    // Forms can only submit back to the same origin.
    "form-action 'self'",
    // Upgrade any accidental http:// subresource to https:// in prod.
    ...(isProd ? ['upgrade-insecure-requests'] : []),
  ].join('; ')
}

export function middleware(_req: NextRequest) {
  const res = NextResponse.next()
  const csp = buildCsp()

  // Enforced in prod, report-only in dev so HMR keeps working while we
  // still see violations in the browser console.
  res.headers.set(
    isProd ? 'Content-Security-Policy' : 'Content-Security-Policy-Report-Only',
    csp
  )

  // Defense-in-depth — cheap headers the browser enforces regardless.
  res.headers.set('X-Content-Type-Options', 'nosniff')
  res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin')
  res.headers.set('X-Frame-Options', 'DENY')
  // Opt out of APIs we don't use. A dependency that tries to access the
  // camera/mic/geolocation will be blocked at the browser level.
  res.headers.set(
    'Permissions-Policy',
    'camera=(), microphone=(), geolocation=(), interest-cohort=()'
  )
  // HSTS is set server-side by Django in production (SECURE_HSTS_SECONDS),
  // but we also set it here so the frontend origin is covered when served
  // as a standalone Next.js deploy (e.g. CloudFront → S3 or Vercel) where
  // Django isn't in the path.
  if (isProd) {
    res.headers.set(
      'Strict-Transport-Security',
      'max-age=31536000; includeSubDomains; preload'
    )
  }

  return res
}

// Run on every route except Next's own static assets and the favicon.
// Including API routes isn't useful — Django serves `/api/*`, not Next —
// but if a future proxy rewrite lands, the headers still apply.
export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
}
