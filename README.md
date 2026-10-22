# Jev + RAG

## Leírás

A **Jev + RAG** egy tervezett, dokumentumalapú kérdés-válasz rendszer, amely a Retrieval-Augmented Generation (RAG) megközelítést a Jev döntési rétegével egészíti ki.

Az első fejlesztési fázis célja egy működő, mérhető RAG baseline létrehozása.

## A projekt célja

A rendszer célja, hogy a felhasználói kérdésekre a betöltött dokumentumokból visszakeresett információk alapján adjon választ, és a válaszhoz felhasznált forrásokat azonosíthatóvá tegye.

A tervezés magyar és angol nyelvű kérdésekkel, valamint vegyes nyelvű dokumentumállománnyal számol. Fontos szempont a visszakeresés és a válaszadás értékelhetősége, illetve a nem megfelelően alátámasztott válaszok kezelése.

## Tervezett minimális működés

Az **1. fázis – RAG Baseline** tervezett feldolgozási folyamata:

1. **Ingestion:** dokumentumok betöltése, feldolgozása, darabolása és kereshetővé tétele.
2. **Retrieval:** a felhasználói kérdéshez kapcsolódó dokumentumrészletek visszakeresése.
3. **Jev Decision Layer:** a visszakeresett bizonyítékok alapján a további válaszadási folyamat támogatása.
4. **Answer Generation:** a rendelkezésre álló forrásokra támaszkodó válasz előállítása, forráshivatkozásokkal.
5. **Evaluation:** a visszakeresés és a válaszadás minőségének ellenőrizhető értékelése.

A tervezett alkalmazásréteg Python/FastAPI alapú; a helyi Python-fejlesztési környezet kezelése `uv`-vel történik. A tervezett webes felület Next.js alapú. A fejlesztési környezet macOS-en, Apple Silicon gépen fut; a háttérszolgáltatásokhoz Docker használata tervezett.

A felsorolt képességek **tervezett funkciók**, nem igazoltan elkészült részek.

## Indítás

**Jelenleg nincs dokumentált, ellenőrzött indítási parancs.**

A tervezett fejlesztői futtatási modell szerint:

- a Python/FastAPI alkalmazás helyben, `uv` által kezelt környezetben fut;
- a Next.js alkalmazás helyben fut;
- a szükséges háttérszolgáltatások Dockerben futnak.

A tényleges telepítési, konfigurációs és indítási parancsok az implementálásuk és ellenőrzésük után kerülnek a README-be.
