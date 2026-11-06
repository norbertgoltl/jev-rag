# Frontend foundation

The workspace was created with the official `create-next-app@16.4.2` generator, using TypeScript, ESLint, App Router, and an src structure, without Tailwind or React Compiler. It uses a single root lockfile.

## Development

Node.js 24.22.1 ARM64 is required. With fnm installed, run from the repository root:

```sh
fnm install
fnm use
corepack enable
pnpm install --frozen-lockfile
make dev-web
```

Corepack selects pnpm 12.15.0 from the root packageManager field. The server is available at http://127.0.0.1:3000.

Copy `.env.local.example` to `.env.local` in this directory. BACKEND_API_URL is server-only and defaults to http://127.0.0.1:8000 in development. It must be explicitly provided in production. BACKEND_TIMEOUT_MS is a positive integer, defaulting to 2000. Configuration is validated on the first API call. The build does not require a backend.

## Communication

The browser only calls the relative GET /api/backend/status endpoint. The BFF running in the Node runtime checks the FastAPI system/status and health/ready responses in parallel. Runtime validation, a per-call timeout, no-store, and a UUID request ID protect communication. There is no retry or polling. The backend remains online when readiness returns 503. A system-status network error returns 503, a timeout returns 504, and an invalid response returns 502. Internal exceptions are not included in the response.

The UI handles loading, online/ready, online/not_ready, online/unknown, and offline states, with manual rechecking, concurrent requests disabled, and cancellation on unmount.

## Validation

Run from the repository root:

```sh
pnpm --filter @jev-rag/web lint
pnpm --filter @jev-rag/web typecheck
pnpm --filter @jev-rag/web test
pnpm --filter @jev-rag/web build
```

The typecheck first generates the Next route types. Tests run once using mocked fetch. The production build does not connect to FastAPI. Real Qdrant-ready integration is the responsibility of FND-015–017.
