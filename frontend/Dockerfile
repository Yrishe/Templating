# ---------------------------------------------------------------------------
# Stage 1: deps — install node_modules
# ---------------------------------------------------------------------------
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps

# ---------------------------------------------------------------------------
# Stage 2: builder — compile Next.js
# ---------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* values are baked into the JS bundle at build time, so
# they must be available as ARG here. Render (and our GitHub Actions CD
# workflow) passes them in as docker build-args; fallbacks are localhost
# so `docker build` still works on a developer's laptop without env.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000
ARG NEXT_PUBLIC_FEATURE_AI_THUMBS=false
ARG NEXT_PUBLIC_FEATURE_FEATURE_FEEDBACK=false

ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL \
    NEXT_PUBLIC_FEATURE_AI_THUMBS=$NEXT_PUBLIC_FEATURE_AI_THUMBS \
    NEXT_PUBLIC_FEATURE_FEATURE_FEEDBACK=$NEXT_PUBLIC_FEATURE_FEATURE_FEEDBACK

RUN npm run build

# ---------------------------------------------------------------------------
# Stage 3: runner — lean production image
# ---------------------------------------------------------------------------
FROM node:20-alpine AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

WORKDIR /app

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
