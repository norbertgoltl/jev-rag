# FND-001 – Foundation scope és követelmények

Állapot: rögzített döntés. A dokumentum elkészülte nem jelenti a teljes Foundation implementációjának elkészültét.

## Cél

A projekt célja egy magyar és angol dokumentumokat és kérdéseket kezelő, mérhető RAG baseline. Ennek előfeltétele a reprodukálható, lokális fejlesztési alap, elkülönített RAG-, döntési, embedding- és generálási felelősségekkel.

Az első megvalósítás egy fejlesztőre, lokális futtatásra és moduláris monolitra készül. Az agentek későbbi csatlakoztatását a modulhatárok támogatják. Teljes agent framework nem része a baseline-nak.

## Fázisok és hatókör

| Terület | 01 Foundation | 02 RAG Core | Későbbi fázis |
| --- | --- | --- | --- |
| Repository, tooling | Monorepo, uv, pnpm, lockfile-ok, setup | Meglévő eszközök használata | Igény szerinti bővítés |
| Backend | FastAPI-váz, konfiguráció, health, hibakezelés, request ID, logok | Ingestion és kérdés-válasz use case-ek | Új üzleti folyamatok |
| Frontend | Next.js-váz és backend-diagnosztika | Dokumentum- és kérdés-válasz felület | További felhasználói folyamatok |
| Qdrant | Compose, perzisztencia, kapcsolatteszt, adapterhatár | Collection, upsert, search, delete, payloadindexek | Mért igény szerinti optimalizálás |
| Jev | Típusos port, determinisztikus mock, SDK-adapter, külön smoke teszt | Routing és relevanciaértékelés, mért policy | További döntési use case-ek |
| Dokumentumfeldolgozás | Chunk-adatok követelményei | Betöltés, darabolás, újraindexelés | További formátumok |
| Embedding | Providerhatár és konzisztenciakövetelmények | Modellválasztás és integráció | Mért igény szerinti modellváltás |
| Generatív LLM | Felelősség és providerhatár | Modellválasztás, forrásalapú válasz, hivatkozások | További képességek |
| Evaluation | Offline tesztelhetőség biztosítása | Retrieval és válaszminőség, HU/EN mérések, elégtelen bizonyíték kezelése | Folyamatos regressziómérés |
| Agent orchestration | Kontrollált bővítési pont | Nincs teljes agent framework | Külön tervezett agentic fázis |
| Production | Lokális biztonsági alapok | Nincs production SLA | Skálázás, többfelhasználós autorizáció, TLS, backup, rendelkezésre állás |

Új Epic besorolása: fejlesztési vagy futtatási alap → Foundation, dokumentumból választ előállító folyamat vagy annak minőségmérése → RAG Core, autonóm eszközhasználat → agentic fázis, éles üzemeltetés vagy többfelhasználós működés → production fázis. Vegyes Epicet ezek mentén kell bontani.

## Foundation feladatcsoportok

| Feladatok | Kimenet | Fázis |
| --- | --- | --- |
| FND-001–004 | Scope, architektúra, interfészszerződések, vector store ADR | 01 Foundation, tervezés |
| FND-005–007 | Monorepo, Git-konfiguráció, fejlesztői parancsok | 01 Foundation, implementáció |
| FND-008–011 | Python/uv, FastAPI, settings, HTTP-contractok megvalósítása, logging | 01 Foundation, implementáció |
| FND-012–014 | Next.js, típusos backend-kliens, diagnosztikai felület | 01 Foundation, implementáció |
| FND-015–017 | Qdrant Compose, perzisztencia, valódi readiness probe | 01 Foundation, implementáció |
| FND-018–020 | DecisionPort, mock, TypeSafe SDK-adapter és contract/smoke tesztek | 01 Foundation, implementáció |
| FND-021–023 | Backend/frontend minőségellenőrzés és CI | 01 Foundation, implementáció |
| FND-024–026 | Biztonsági és agentfejlesztési szabályok, integrált release gate | 01 Foundation, ellenőrzés |

Az FND-003 konkrét szerződéseket ad a későbbi implementációhoz. A futó endpointok és adapterek nem az FND-001–004 részeként készülnek el.

## Nem funkcionális követelmények

| Követelmény | Ellenőrizhető elvárás a Foundation végén |
| --- | --- |
| Izoláció | FastAPI uv-környezetben és Next.js pnpm-mel a hoston, infrastruktúra Dockerben, globális projektfüggőség nélkül |
| Reprodukálhatóság | Runtime- és csomagverziók rögzítve, uv/pnpm lockfile, konkrét Qdrant image-tag, dokumentált tiszta setup |
| Tesztelhetőség | Unit és szimulált integration tesztek AI API-kulcs és külső AI API nélkül futnak, Docker- és live smoke külön indítható |
| Biztonság | Secret kizárólag szerveroldalon, verziókezelésen kívül, infrastruktúra loopback binddal, szűrt hibák és logok |
| Megfigyelhetőség | Strukturált logok, kérésenként request ID, külön liveness és Qdrant-readiness |
| Bővíthetőség | SDK-független domain/port réteg, SDK csak adapterben, policy az application rétegben |
| Minőség | Automatizált lint, typecheck, tesztek és CI, hibás ellenőrzés nem jelenthet sikert |

## Elfogadás és kapcsolódó döntések

Az FND-001 teljesült: a fázishatárok és valamennyi ismert Foundation feladatcsoport besorolása rögzített. A többi fázis működő képességeit külön megvalósítás és teszt igazolja.

- [Rendszerarchitektúra](../architecture/system-architecture.md)
- [Interfészszerződések](../architecture/interface-contracts.md)
- [ADR-001: Qdrant](../adr/ADR-001-vector-store.md)
