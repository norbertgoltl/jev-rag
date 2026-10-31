# Jev + RAG

## Leírás

A **Jev + RAG** egy tervezett, dokumentumalapú kérdés-válasz rendszer, amely a Retrieval-Augmented Generation (RAG) megközelítést a Jev döntési rétegével egészíti ki.

A **01 Foundation** fázis működő FastAPI backendet, Next.js BFF-et, Qdrant infrastruktúrát és Jev DecisionPort adaptert biztosít. A teljes Foundation elfogadási állapotát a [release checklist](docs/foundation/release-checklist.md) és a [release report](docs/foundation/release-report.md) követi. Erre épül a **02 RAG Core** fázis működő, mérhető RAG baseline-ja.

## A projekt célja

A rendszer célja, hogy a felhasználói kérdésekre a betöltött dokumentumokból visszakeresett információk alapján adjon választ, és a válaszhoz felhasznált forrásokat azonosíthatóvá tegye.

A tervezés magyar és angol nyelvű kérdésekkel, valamint vegyes nyelvű dokumentumállománnyal számol. Fontos szempont a visszakeresés és a válaszadás értékelhetősége, illetve a nem megfelelően alátámasztott válaszok kezelése.

## Tervezett minimális működés

A **02 RAG Core** tervezett feldolgozási folyamata:

1. **Ingestion:** dokumentumok betöltése, feldolgozása, darabolása és kereshetővé tétele.
2. **Retrieval:** a felhasználói kérdéshez kapcsolódó dokumentumrészletek visszakeresése.
3. **Jev Decision Layer:** a visszakeresett bizonyítékok alapján a további válaszadási folyamat támogatása.
4. **Answer Generation:** a rendelkezésre álló forrásokra támaszkodó válasz előállítása, forráshivatkozásokkal.
5. **Evaluation:** a visszakeresés és a válaszadás minőségének ellenőrizhető értékelése.

A backend Python/FastAPI alapú, a helyi Python-fejlesztési környezetet `uv` kezeli. A webes felület Next.js alapú. A támogatott elsődleges fejlesztői környezet macOS Apple Silicon, a Qdrant Docker Compose-ban fut.

A felsorolt RAG-képességek **tervezett funkciók**, nem részei a jelenlegi Foundationnek.

## Foundation architektúradöntések

Az FND-001–004 tervezési eredményei elkészültek:

- [FND-001: Scope és követelmények](docs/foundation/scope.md)
- [FND-002: Rendszerarchitektúra](docs/architecture/system-architecture.md)
- [FND-003: Interfészek és API-contractok](docs/architecture/interface-contracts.md)
- [FND-003: Géppel olvasható OpenAPI-contract](docs/architecture/contracts/foundation.openapi.json)
- [FND-004: Qdrant vector store ADR](docs/adr/ADR-001-vector-store.md)

A döntés moduláris FastAPI backend, Next.js frontend, külön Jev döntési adapter és Docker Compose-ban futó Qdrant. A backend, a frontend, az infrastruktúra és az SDK-integráció megvalósult; az integrált elfogadási állapotot a [release report](docs/foundation/release-report.md) rögzíti.

## Monorepo és fejlesztői környezet

Az FND-005–007 alapstruktúrája és fejlesztői CLI-je elkészült. Elsődleges környezet: macOS Apple Silicon, POSIX shell és GNU/BSD Make. A rögzített Node.js-verzió `24.22.1`, a pnpm-verzió `12.15.0`. A backend uv-managed Python `3.14.8` interpretert használ, az FND-008–011 megvalósult.

| Könyvtár | Felelősség |
| --- | --- |
| `apps/api` | Python/FastAPI projekt, saját uv.lock és .venv |
| `apps/web` | Next.js projekt, a root pnpm workspace része |
| `infra/compose.yaml` | Docker-infrastruktúra |
| `scripts` | Fejlesztői parancsok és smoke tesztek |
| `docs` | Architektúra, ADR-ek és fejlesztői útmutatók |
| `.github` | PR-sablon és GitHub Actions CI |

A repository gyökeréből futtatható:

```sh
make help
make doctor
make smoke
```

A `doctor` csak ellenőriz, hiányzó eszköz vagy verzióeltérés esetén hibával lép ki. A `smoke` offline, szimulált eszközökkel ellenőrzi a CLI-t.

## Local quickstart

Docker Desktop legyen elindítva. A rögzített Python, Node.js és pnpm verziókat a [`docs/development/macos-setup.md`](docs/development/macos-setup.md) írja le.

```sh
fnm use
cp .env.example .env
make doctor
make setup
make up
```

Indítsd el külön terminálokban:

```sh
make dev-api
make dev-web
```

A felület címe `http://127.0.0.1:3000`, a backendé `http://127.0.0.1:8000`. A `.env.example` mock Jev módot használ, ezért a kezdő setuphoz nem kell élő API-kulcs. A readiness ellenőrzése és leállítás:

```sh
make health
make down
```

`make down` megőrzi a Qdrant adatvolume-ot.

Az FND-008–011 backendje elkészült: rögzített függőségek, backend tesztek és élő HTTP-smoke ellenőrzés. Részletek: [API README](apps/api/README.md).

A Python-projekt gyökere `apps/api`, a pnpm workspace gyökere a repository. Az API lockfile-ja `apps/api/uv.lock`, a frontendé az egyetlen root `pnpm-lock.yaml`. A FastAPI és Next.js a hoston, csak az infrastruktúra fut Dockerben.

Részletek: [fejlesztői környezet, parancsok és Git-workflow](docs/development/workflow.md).

A backendhez előkészített parancsok: `make setup-api`, `make dev-api`, `make test-api`. Ezek a rögzített `apps/api/uv.lock` alapján futnak.

Az FND-012–014 frontend alap elkészült. Indítás: `make dev-web`. Telepítés, API-kommunikáció és ellenőrzések: [frontend dokumentáció](apps/web/README.md).

Qdrant infrastruktúra: `make up`, `make health`, `make status`, `make down`. Előfeltételek, named volume és izolált tesztek: [infrastruktúra](docs/development/infrastructure.md).

A Jev DecisionPort és TypeSafe SDK integráció elkészült. Quality gate: `make check`. Tesztelési és CI útmutató: [testing](docs/development/testing.md), [CI](docs/development/ci.md). Konfiguráció és külön engedélyezhető live smoke: [Jev integráció](docs/development/jev-integration.md).

## Security és agent workflow

A `TYPESAFE_API_KEY` csak a backend folyamatban használható, frontend bundle-be és nyilvános hibaválaszba nem kerülhet. A biztonsági szabályok, secret incidenseljárás és Gitleaks ellenőrzés a [security baseline](docs/development/security.md) dokumentumban találhatók. A repository agent- és PR-szabályait az [AGENTS.md](AGENTS.md) és az [agent workflow](docs/development/agent-workflow.md) rögzíti.

A lokális minőségellenőrzés `make check`; az integrált átadás további parancsai `make security-check`, `make security-smoke` és `make infra-test`. Az eredményeket csak tényleges futtatás után kell a [release reportban](docs/foundation/release-report.md) PASS-ra állítani.
