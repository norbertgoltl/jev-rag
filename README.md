# Jev + RAG

## Leírás

A **Jev + RAG** egy tervezett, dokumentumalapú kérdés-válasz rendszer, amely a Retrieval-Augmented Generation (RAG) megközelítést a Jev döntési rétegével egészíti ki.

A **01 Foundation** fázis célja a fejlesztési és futtatási alap létrehozása. Erre épül a **02 RAG Core** fázis működő, mérhető RAG baseline-ja.

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

A tervezett alkalmazásréteg Python/FastAPI alapú; a helyi Python-fejlesztési környezet kezelése `uv`-vel történik. A tervezett webes felület Next.js alapú. A fejlesztési környezet macOS-en, Apple Silicon gépen fut; a háttérszolgáltatásokhoz Docker használata tervezett.

A felsorolt képességek **tervezett funkciók**, nem igazoltan elkészült részek.

## Foundation architektúradöntések

Az FND-001–004 tervezési eredményei elkészültek:

- [FND-001: Scope és követelmények](docs/foundation/scope.md)
- [FND-002: Rendszerarchitektúra](docs/architecture/system-architecture.md)
- [FND-003: Interfészek és API-contractok](docs/architecture/interface-contracts.md)
- [FND-003: Géppel olvasható OpenAPI-contract](docs/architecture/contracts/foundation.openapi.json)
- [FND-004: Qdrant vector store ADR](docs/adr/ADR-001-vector-store.md)

A döntés moduláris FastAPI backend, Next.js frontend, külön Jev döntési adapter és Docker Compose-ban futó Qdrant. A futó alkalmazások, az infrastruktúra és az SDK-integráció megvalósítása a következő Foundation-feladatok része.

## Monorepo és fejlesztői környezet

Az FND-005–007 alapstruktúrája és fejlesztői CLI-je elkészült. Elsődleges környezet: macOS Apple Silicon, POSIX shell és GNU/BSD Make. A rögzített Node.js-verzió `24.22.1`, a pnpm-verzió `12.15.0`. A backend uv-managed Python `3.14.8` interpretert használ, az FND-008–011 megvalósult.

| Könyvtár | Felelősség |
| --- | --- |
| `apps/api` | Python/FastAPI projekt, saját uv.lock és .venv |
| `apps/web` | Next.js projekt, a root pnpm workspace része |
| `infra/compose` | Docker-infrastruktúra |
| `scripts` | Fejlesztői parancsok és smoke tesztek |
| `docs` | Architektúra, ADR-ek és fejlesztői útmutatók |
| `.github` | PR-sablon, később CI |

A repository gyökeréből futtatható:

```sh
make help
make doctor
make smoke
```

A `doctor` csak ellenőriz, hiányzó eszköz vagy verzióeltérés esetén hibával lép ki. A legutóbbi futás sikeres, 0 kilépési kóddal, az uv-managed Python `3.14.8` és minden ellenőrzött eszköz megfelelő. A `smoke` offline, szimulált eszközökkel ellenőrzi a CLI-t.

Az FND-008–011 backendje elkészült: rögzített függőségek, 36 sikeres teszt, sikeres build és élő HTTP-smoke ellenőrzés. Részletek: [API README](apps/api/README.md). A frontend még nem indítható. A `setup` hiányzó manifest vagy lockfile esetén leáll. A frontend-, infrastruktúra- és teljes quality parancsok a későbbi Foundation-feladatok elkészültéig érthető hibát adnak.

A Python-projekt gyökere `apps/api`, a pnpm workspace gyökere a repository. Az API lockfile-ja `apps/api/uv.lock`, a frontendé az egyetlen root `pnpm-lock.yaml` lesz. A FastAPI és Next.js a hoston, csak az infrastruktúra Dockerben fut majd.

Részletek: [fejlesztői környezet, parancsok és Git-workflow](docs/development/workflow.md).

A backendhez előkészített parancsok: `make setup-api`, `make dev-api`, `make test-api`. Ezek a rögzített `apps/api/uv.lock` alapján futnak.

Frontend workspace available: see apps/web/README.md.
