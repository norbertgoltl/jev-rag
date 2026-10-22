# Frontend workspace

A Next.js-projekt gyökere ez a könyvtár. Az FND-012 hozza létre a saját `package.json` fájlt és a repository gyökerében lévő egyetlen `pnpm-lock.yaml` fájlt. Jelenleg nincs indítható frontend.

A Node.js verzióját a gyökérszintű `.node-version`, a pnpm verzióját a gyökérszintű `package.json` rögzíti. A projekt a root `pnpm-workspace.yaml` része, saját lockfile nélkül.

A későbbi lokális konfiguráció `apps/web/.env.local` útvonalon lesz, verziókezelt `.env.local.example` mintával. TypeSafe API-kulcs nem kerülhet a frontendhez vagy `NEXT_PUBLIC_*` változóba.
