# Frontend foundation

A workspace a hivatalos `create-next-app@16.4.2` generátorral készült, TypeScript, ESLint, App Router és src struktúrával, Tailwind és React Compiler nélkül. Egyetlen gyökérszintű lockfile-t használ.

## Fejlesztés

Node.js 24.22.1 ARM64 szükséges. Telepített fnm esetén a repository gyökerében:

```sh
fnm install
fnm use
corepack enable
pnpm install --frozen-lockfile
make dev-web
```

A Corepack a root packageManager mezőből választja a pnpm 12.15.0 verziót. A szerver címe http://127.0.0.1:3000.

Másold a `.env.local.example` fájlt `.env.local` néven ebbe a könyvtárba. A BACKEND_API_URL csak a szerveren használható, development alapértéke http://127.0.0.1:8000. Production esetén explicit megadása kötelező. A BACKEND_TIMEOUT_MS pozitív egész, alapértéke 2000. A konfiguráció az első API-híváskor validálódik, buildhez nincs szükség backendhez.

## Kommunikáció

A böngésző csak a relatív GET /api/backend/status végpontot hívja. A Node runtime-ban futó BFF párhuzamosan ellenőrzi a FastAPI system/status és health/ready válaszait. Runtime-validáció, hívásonkénti timeout, no-store és UUID request ID védi a kommunikációt. Nincs retry vagy polling. A readiness 503 mellett a backend online marad. A system-status hálózati hibája 503, timeoutja 504, hibás válasza 502. Belső exception nem kerül a válaszba.

A UI loading, online/ready, online/not_ready, online/unknown és offline állapotokat kezel, kézi újraellenőrzéssel, letiltott párhuzamos kérésekkel és unmountkor megszakítással.

## Ellenőrzés

A repository gyökeréből:

```sh
pnpm --filter @jev-rag/web lint
pnpm --filter @jev-rag/web typecheck
pnpm --filter @jev-rag/web test
pnpm --filter @jev-rag/web build
```

A typecheck először generálja a Next route típusokat. A tesztek egyszer futnak, mockolt fetch használatával. A production build nem kapcsolódik FastAPI-hoz. A valódi Qdrant-ready integráció a FND-015–017 feladata.
