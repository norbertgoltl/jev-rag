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

Jelenleg nincs alkalmazásprojekt, Compose vagy fejlesztői CLI. A Git/editor szabályok az FND-006, a parancsfelület az FND-007 feladata.
