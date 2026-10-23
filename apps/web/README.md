# Frontend workspace

Node.js 24.22.1, pnpm 12.15.0, Next.js 16.4.2, strict TypeScript and App Router. Generated with the official create-next-app CLI.

From the repository root: `pnpm install --frozen-lockfile`, `make dev-web`, `pnpm --filter @jev-rag/web lint`, `pnpm --filter @jev-rag/web typecheck`, `pnpm --filter @jev-rag/web build`. The development server listens on 127.0.0.1:3000.

Server-only native fetch client and GET /api/backend/status aggregate system status and readiness. Requests use UUID correlation, no-store and a configurable timeout. Configure BACKEND_API_URL and BACKEND_TIMEOUT_MS in apps/web/.env.local using the example. Production requires an explicit URL. Run mock contract tests with `pnpm --filter @jev-rag/web test`.
