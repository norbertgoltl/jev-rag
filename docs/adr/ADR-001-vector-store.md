# ADR-001 – Qdrant vector store

Állapot: elfogadott architektúradöntés. Kapcsolódó feladat: FND-004.

## Kontextus

A projekt lokálisan fejlesztett RAG-rendszer, amelynek elsődleges tárolási feladata dokumentumrészletek szemantikus visszakeresése és metaadatok szerinti szűrése. Jelenleg nincs meglévő PostgreSQL-adatbázis vagy jelentős relációs üzleti adatmodell.

## Döntés

A vector store Qdrant, külön Docker Compose szolgáltatásként. Elérése kizárólag a backend providerfüggetlen VectorStorePortjának adapterén keresztül történik. A frontend és a későbbi agentek nem kapnak közvetlen adatbázis-hozzáférést.

## Mérlegelt alternatívák

| Szempont | Qdrant | PostgreSQL + pgvector |
| --- | --- | --- |
| Alapmodell | Dedikált vector kereső | Relációs adatbázis vector bővítéssel |
| Szűrés | Payload és payloadindexek | SQL és relációs indexek |
| Későbbi hybrid retrieval | Dense/sparse kombináció | Vector és full-text kombináció |
| Üzleti adatok és tranzakciók | Külön autoritatív adatbázis lehet szükséges | Ugyanabban a relációs adatbázisban kezelhetők |
| Projektbeli következmény | Közvetlenül illeszkedik a retrieval feladathoz | Jelenleg kihasználatlan relációs infrastruktúrát vezetne be |

A Qdrantot a retrieval-központú scope és a payload-alapú szűrés indokolja. Ez nem méréssel igazolt teljesítményelőny a pgvectorral szemben. PostgreSQL később bevezethető felhasználók, dokumentum-életciklus, jobállapotok vagy beszélgetések autoritatív tárolására, a vector index cseréje nélkül.

## Kötelező üzemeltetési feltételek

| Terület | Követelmény | Implementáció |
| --- | --- | --- |
| Futtatás | Docker Compose, hoston futó API és web mellett | FND-015 |
| Hálózat | HTTP-kötés `127.0.0.1:6333:6333`, LAN felé nincs publikálás | FND-015 |
| További portok | gRPC és cluster port nem publikált a hoston | FND-015 |
| Image | Ellenőrzött, konkrét verzió, nem `latest` | FND-015 |
| Tárolás | Docker named volume a `/qdrant/storage` útvonalon | FND-016 |
| Adatmegőrzés | Restart és normál leállítás/újraindítás megőrzi az adatot, volume-törlés csak explicit adatvesztési művelet | FND-016 |
| Readiness | Határolt kapcsolatteszt a backend adapterből, elérhetetlenségre 503 | FND-017 |
| Production | Hitelesítés, TLS, hálózati védelem, snapshot- és visszaállítási stratégia | Élesítés előtt külön feladat |

A [Qdrant quickstart](https://qdrant.tech/documentation/quickstart/) figyelmeztet arra, hogy alapkonfigurációban nincs hitelesítés vagy titkosítás. Ezért a loopback bind kötelező, a lokális konfiguráció önmagában nem production telepítés.

## Adatkezelési következmények

A Qdrant újraépíthető keresési index. Az eredeti dokumentumokat és a feldolgozási konfigurációt külön meg kell őrizni. Dokumentumvesztésből nem állítható helyre megbízhatóan az eredeti tartalom pusztán a vector index alapján.

A collection neve, vektordimenzió, távolságmetrika és embeddingmodell a RAG Core döntése. Foundationben nem készül előre üzleti collection. Az infrastruktúra perzisztenciatesztje használhat elkülönített, szintetikus tesztcollectiont.

A RAG Core indexterve a tényleges szűrési minták alapján jelöli ki a payloadindexeket, lehetőleg az adatbetöltés előtt, a [Qdrant indexelési útmutatója](https://qdrant.tech/documentation/manage-data/indexing/) szerint. A későbbi `access_scope` filter nem helyettesíti az alkalmazásoldali autorizációt.

## Újravizsgálat

A döntés akkor vizsgálandó újra, ha a relációs igény dominánssá válik, a két tároló üzemeltetési költsége problémát okoz, mért keresési hiányosság jelentkezik, vagy a tranzakcionális konzisztencia szorosabb összekapcsolást követel. Technológiai preferencia önmagában nem indok migrációra.

## Elfogadás

Az FND-004 teljesült: a választás, alternatíva, következmények és újravizsgálati feltételek rögzítettek. A Compose, a volume és a kapcsolatteszt megvalósítása FND-015–017, nem az ADR elkészültének része.

Kapcsolódó dokumentumok: [scope](../foundation/scope.md), [architektúra](../architecture/system-architecture.md), [interfészek](../architecture/interface-contracts.md).
