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

## Indítás

**Jelenleg nincs dokumentált, ellenőrzött indítási parancs.**

A tervezett fejlesztői futtatási modell szerint:

- a Python/FastAPI alkalmazás helyben, `uv` által kezelt környezetben fut;
- a Next.js alkalmazás helyben fut;
- a szükséges háttérszolgáltatások Dockerben futnak.

A tényleges telepítési, konfigurációs és indítási parancsok az implementálásuk és ellenőrzésük után kerülnek a README-be.
