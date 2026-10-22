# Fejlesztői környezet és workspace-határok

Elsődleges környezet: macOS Apple Silicon. A Python/FastAPI és a Node.js/Next.js alkalmazások a hoston futnak majd, az infrastruktúra Docker Compose-ban.

A Node.js pin `24.13.0` a `.node-version` és a root `package.json` fájlban, a pnpm pin `12.6.0` a root `package.json` fájlban található. A Python célverziója uv-managed `3.14.8`. Rendszerszintű Python-/npm-projektfüggőségek nem telepíthetők.

## Projektgyökerek és lockfile-ok

| Útvonal | Felelősség |
| --- | --- |
| `apps/api/` | Egyetlen Python-projekt, saját `pyproject.toml`, `uv.lock` és `.venv`, FND-008-tól |
| `apps/web/` | Next.js és saját `package.json`, FND-012-től |
| `package.json` | Privát workspace-koordinátor, runtime- és package manager pin, alkalmazásfüggőség nélkül |
| `pnpm-workspace.yaml` | Kizárólag `apps/web`, közös root lockfile-lal |
| `infra/compose/` | Docker-infrastruktúra, FND-015–017-től |
| `scripts/` | Fejlesztői tooling helye, FND-007-től |
| `docs/architecture/`, `docs/adr/`, `docs/foundation/` | Architektúra, döntések, fázishatárok |
| `docs/development/` | Setup és fejlesztési workflow |
| `.github/` | PR-sablon helye FND-006-tól, később CI |

Nincs root Python-projekt, uv workspace, frontend saját lockfile vagy előre létrehozott shared/agent/embedding csomag. Az alkalmazásgyökereket jelenleg a saját README-jük tartja fenn, üres `.gitkeep` nélkül.

Az `apps/api/uv.lock` az FND-008, a root `pnpm-lock.yaml` az FND-012 során jön létre. A későbbi lockfile-ok és runtime-pinek verziókezelendők. A setup nem generálhat hiányzó lockfile-t, és nem oldhat fel új verziókat.

## Konfiguráció

A root [.env.example](../../.env.example) a backend/infra secret nélküli mintája. A lokális `.env` nem verziókezelt és nem hajtható végre shell scriptként. A frontend saját mintáját az FND-012–014 hozza létre.

Jelenleg nincs alkalmazásprojekt, Compose vagy fejlesztői CLI. A parancsfelület az FND-007 feladata.

## Git és szerkesztési szabályok

Rövid életű branchek a `main` fölött, review és squash merge. Új feladatnál `feature/fnd-XXX-description`, hibajavításnál `fix/fnd-XXX-description` név használható. A commitüzenet Conventional Commits formátumú, angolul, például:

```text
chore(repo): initialize monorepo development tooling
```

Commitüzenethez co-author nem adható. Branch protection és kötelező GitHub CI-check későbbi feladat. A [PR-sablon](../../.github/pull_request_template.md) a scope-ot, változásokat, ellenőrzéseket és kockázatokat rögzíti.

Az EditorConfig UTF-8-at, LF-et, végső újsort, Pythonhoz és shellhez 4, TypeScript/JSON/YAML-hez 2 szóközt, Makefile-hoz tabot ír elő. A Git attributes normalizálja a szövegeket és binárisként kezeli a kijelölt médiatípusokat.

A `.gitignore` kizárja a secret fájlokat, környezeteket, függőségeket, buildet és cache-t. A `.env.example`, `.env.local.example` és hasonló minták kivételek. Ez nem akadályozza meg a titkok explicit hozzáadását, az automatizált secret scanner az FND-024 része.

Commit előtt `git status --short` és `git diff --check` futtatandó. A fejlesztői CLI és annak ellenőrzése az FND-007 része. Új fájloknál a diff mellett a fájlok tartalmát is át kell nézni, mert a `git diff` önmagában nem mutatja az untracked fájlokat. Ellenőrizendő, hogy nincs secret, `.venv`, `node_modules` vagy generált adat a változások között.
