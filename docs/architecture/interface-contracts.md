# FND-003 – Interfészek és API-contractok

Állapot: specifikált szerződések. A HTTP-contract géppel olvasható alakja: [foundation.openapi.json](contracts/foundation.openapi.json), OpenAPI 3.1.0.

Ez a contract-first alap a későbbi implementációhoz. A HTTP-sémák itt már konkrétak, a futó FastAPI endpointok az FND-009–011, a Qdrant-adapter az FND-017, a DecisionPort és adapterei az FND-018–020 feladatai. Embedding- és generator-implementáció nem része a Foundationnek.

## HTTP API

Minden üzleti endpoint prefixe `/api/v1`. A folyamatdiagnosztikai health endpointok ezen kívül maradnak. A sikeres válaszok endpointspecifikusak, általános response wrapper nélkül.

| Metódus és útvonal | HTTP | Pontos JSON-válasz |
| --- | --- | --- |
| `GET /health/live` | 200 | `{"status":"alive"}` |
| `GET /health/ready` | 200 | `{"status":"ready","dependencies":{"qdrant":"up"}}` |
| `GET /health/ready` | 503 | `{"status":"not_ready","dependencies":{"qdrant":"down"}}` |
| `GET /api/v1/system/status` | 200 | `{"service":"api","status":"ok"}` |

A liveness és a system status nem hív külső szolgáltatást. A status az API elérhetőségét jelzi, nem helyettesíti a readinesst. A readiness a szükséges Qdrant-kapcsolatot vizsgálja konfigurált, véges timeouttal. A kezdeti, valódi adapter nélküli probe `down`, nem adhat hamis `ready` állapotot. A Jev elérhetősége nem része a readiness feltételének.

A readiness várható függőséghibája a táblázat szerinti diagnosztikai 503, nem általános error envelope. Váratlan alkalmazáshiba bármely endpointon a közös 500-as hibasémát használja. A válaszok nem tartalmaznak credentialt, belső címet, connection stringet vagy stack trace-t.

Az FND-009 később `/openapi.json` és `/docs` fejlesztői felületet is biztosít. Az itt tárolt OpenAPI-fájl a három Foundation endpoint szerződése, nem futó alkalmazásból exportált eredmény.

## Hibák és request ID

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request",
    "details": [{"field": "body.question", "code": "required"}]
  },
  "request_id": "80d3c0b6-9b52-4aa9-85a0-5a657bb402d8"
}
```

| Mező | Típus és feltétel |
| --- | --- |
| `error.code` | Kötelező, nem üres stabil gépi kód |
| `error.message` | Kötelező, biztonságos, nem üres publikus üzenet |
| `error.details` | Kötelező kulcs, `null` vagy szűrt `{field, code}` elemek listája |
| `request_id` | Kötelező, a válasz `X-Request-ID` headerével megegyező azonosító |

A kiinduló terv opcionális részleteit egységesen jelen lévő, nullable `details` mezőként pontosítjuk. A validációs adatok kizárólag biztonságos mezőazonosítót és hibakódot tartalmazhatnak, inputértéket és nyers kivételt nem.

| Eset | HTTP | `error.code` | Publikus üzenet |
| --- | --- | --- | --- |
| Érvénytelen kérés | 422 | `VALIDATION_ERROR` | `Invalid request` |
| Ismeretlen endpoint | 404 | `NOT_FOUND` | `Resource not found` |
| Tiltott HTTP-metódus | 405 | `METHOD_NOT_ALLOWED` | `Method not allowed` |
| Későbbi üzleti függőséghiba | 503 | `SERVICE_UNAVAILABLE` | `Service unavailable` |
| Nem kezelt hiba | 500 | `INTERNAL_ERROR` | `Internal server error` |

A 405-ös válasz megőrzi az `Allow` headert. A Foundation diagnosztikai GET-ek nem vesznek át üzleti bemenetet, ezért a 422-es séma a későbbi endpointok közös komponense, nem egy kitalált kérésparaméter.

Minden válasz, a health és a hibaválasz is, tartalmaz `X-Request-ID` headert. A bejövő azonosító 1–64 ASCII betűből, számból, `.`, `_`, `-` karakterből állhat. Hiányzó vagy érvénytelen érték helyett UUID4 generálódik. Az érvénytelen header nem okoz 422-t. Aszinkron kérések között a request context nem keveredhet.

## Belső portok

A portok saját domainmodelljeikkel dolgoznak. Nem adhatnak vissza SDK-válaszobjektumot vagy SDK-kivételt az application rétegnek. Az alábbi szignatúrák implementációs szerződések, a hivatkozott típusokat az illetékes backendfeladat vezeti be.

```python
class DecisionPort(Protocol):
    async def evaluate(self, request: DecisionRequest) -> DecisionResult: ...


class VectorStorePort(Protocol):
    async def check_health(self) -> bool: ...
```

A `VectorStorePort.check_health` nem ír adatot és nem hoz létre collectiont. Siker esetén `True`, timeout vagy ismert elérési hiba esetén `False`. A readiness kizárólag ezt a providerfüggetlen eredményt használja, a technikai hibát az adapter biztonságosan naplózza. A timeout konfigurálható és véges. A valódi probe Qdrantot hív, unit tesztben fake-kel helyettesíthető.

| Későbbi határ | Bemenet | Eredmény és invariáns |
| --- | --- | --- |
| Vector upsert | Verziózott chunkok, modellazonosító, megfelelő dimenziójú vektorok | Stabil chunkazonosítóra idempotens indexelés |
| Vector search | Query-vektor, modellazonosító, limit, alkalmazás által ellenőrzött hatókör és filterek | Rangsorolt chunkok és numerikus retrieval score, SDK-típus nélkül |
| Vector delete | Explicit dokumentum-/chunkazonosító és verzióhatár | Kizárólag a kijelölt adatok törlése |
| EmbeddingPort | Dokumentumszövegek vagy query, a választott modell konfigurációja | Véges értékű vektorok, modellazonosító és dimenzió, hibás modell/dimenzió elutasítva |
| GeneratorPort | Kérdés és azonosítható forrásszövegek | Válasz és a felhasznált források azonosítói, SDK-típus nélkül |

Ezek követelményhatárok, nem előre létrehozandó metódusok vagy üres implementációk. A RAG Core rögzíti a végleges típusokat, collection sémát, embedding dimenziót és retrieval score szemantikáját. A generálás nem végez közvetlen retrievalt, a források kiválasztását az application koordinálja.

## Jev Decision Contract

| Tulajdonság | Szerződés |
| --- | --- |
| SDK és kliens | `typesafe-sdk`, `AsyncTypeSafeClient`, backendről |
| Művelet | `system_one(state=..., questions=...)`, adapterből |
| Konfiguráció | Szerveroldali `TYPESAFE_API_KEY`, explicit, konfigurálható modellazonosító |
| Módok | Alapértelmezett offline mock, külön explicit live mód, disabled esetén nincs hívás |
| Életciklus | Workerenként újrafelhasznált kliens, aszinkron lezárás |
| Hibatűrés | 5 s HTTP timeout, legfeljebb 1 SDK retry, 10 s retry budget, második retry loop nélkül |
| Fallback | A use case explicit döntése, nincs automatikus live → mock váltás |

Az [aszinkron kliens](https://docs.typesafe.ai/sdk/python/api/clients/async) támogat timeoutot és retry policyt. A pontos SDK-verzió, modellpin és végrehajtott kompatibilitási ellenőrzés az FND-019–020 kimenete. A modellváltást contract teszteknek, a későbbi üzleti policy esetén minőségmérésnek is jóvá kell hagynia.

### Bemenet

`DecisionRequest.state`: nem null string, JSON-objektum vagy JSON-tömb. `questions`: legalább egy kérdés, nem üres, egyedi stringazonosítóval kulcsolt map. `QuestionSpec`: a `type` szerint diszkriminált unió.

| Típus | Mezők |
| --- | --- |
| `ChoiceQuestionSpec` | `type="choice"`, nem üres `instructions`, `criteria`: legalább két nem üres opcióazonosítót stringhez vagy nullhoz rendelő map |
| `ScoreQuestionSpec` | `type="score"`, nem üres `instructions`, `criteria`: 2–10 rendezett, nem üres szöveges szint |
| `NoulQuestionSpec` | `type="noul"`, nem üres `instructions`, opcionális `criteria`: `true` és/vagy `false` szöveges leírás |

A Foundation szöveges kritériumokat használ. Az SDK további multimodális és strukturált kérdésképességei nem kerülnek automatikusan a belső portba. A provider típusait az adapter képezi le a [TypeSafe kérdésszerződése](https://docs.typesafe.ai/sdk/python/api/types/questions) alapján.

### Kimenet és validáció

`DecisionResult`: kötelező, nem üres `model` és `answers` map, opcionálisan nullable `provider_request_id`, nem negatív egész `input_tokens` és `output_tokens`. Az `answers` minden kért azonosítóhoz pontosan egy választ tartalmaz, többlet nélkül.

| Választípus | Mezők és jelentés |
| --- | --- |
| `ChoiceAnswer` | `type="choice"`, engedélyezett `choice`, opcióazonosítóhoz rendelt `probabilities`, `confidence` |
| `ScoreAnswer` | `type="score"`, törtértéket is megőrző `score`, szintindexhez rendelt `probabilities`, `confidence` |
| `NoulAnswer` | `type="noul"`, `noul`: 0–1 valószínűség, külön confidence nélkül |

A Score intervalluma `0..len(criteria)-1`. A probabilities és confidence véges, 0–1 közötti számok. A Choice eloszláskulcsai pontosan az opciók, a Score eloszláskulcsai a skála egész indexei. A visszatérő primitív egyezik a kérésével. A válasz nem kerekíthető egész score-rá, hiányzó mező nem pótolható kitalált értékkel. Az adapter az [SDK-válaszokat](https://docs.typesafe.ai/sdk/python/api/types/responses) saját domainmodellre alakítja, tényleges modellazonosítóval.

### Hibák, mock és végrehajtási határ

Az `evaluate` kizárólag `DecisionError` leszármazottat adhat ismert providerhiba esetén. Az elvárt kategóriák: `DecisionInvalidRequestError`, `DecisionAuthenticationError`, `DecisionRateLimitedError`, `DecisionUnavailableError`, `DecisionTimeoutError`, `DecisionInvalidResponseError`, `DecisionConfigurationError`. Hibás vagy hiányos providereredmény invalid response, nem sikeres döntés.

400/401/403/422 hibára nincs retry. A 429, átmeneti provider- és hálózati hibák korlátozottan újrapróbálhatók. A hibák nem tartalmazhatnak API-kulcsot, state-et vagy nyers provider body-t. Az SDK DEBUG body-naplózása nem engedélyezett.

A mock konfigurált fixture-öket ad vissza determinisztikusan, külső hálózat és API-kulcs nélkül. Hiányzó fixture explicit hiba. Ugyanazok a bemeneti és kimeneti invariánsok vonatkoznak rá, mint a live adapterre. A normál tesztek offline futnak, a live smoke külön, szintetikus HU/EN inputtal, konkrét modellítélet helyett struktúrát ellenőriz.

A modellválasz döntési bemenet. Az alkalmazás determinisztikus policy alapján végrehajt, visszautasít vagy explicit fallbacket választ. Numerikus számítás, dátum-összehasonlítás és autorizáció kódban történik, nem a modell ítéletére támaszkodik.

## RAG chunk-adatok követelményei

| Mező | Követelmény |
| --- | --- |
| `chunk_id` | Stabil azonosító az adott chunkverzióhoz |
| `document_id` | A forrásdokumentum azonosítója |
| `document_version` | A feldolgozott forrás verziója |
| `content` | Kereshető szöveg |
| `source_uri` | Hivatkozható forráshely |
| `chunk_index` | Nem negatív dokumentumon belüli sorrend |
| `metadata` | Strukturált, JSON-kompatibilis keresési metaadatok |
| `embedding_model` | A vektort előállító modell azonosítója |
| `access_scope` | Az alkalmazás által ellenőrzött jogosultsági hatókör |

A konkrét mezőtípusok és azonosítóképzés, a modell, a dimenzió és a collection séma a RAG Core döntése. A document version és a feldolgozási konfiguráció együtt teszi reprodukálhatóvá az indexet. A kereséshez szükséges hatókört az application határozza meg ellenőrzötten, azt nem veheti át szabadon a felhasználótól.

## Elfogadási ellenőrzések a megvalósító feladatokhoz

| Ellenőrzés | Elvárt eredmény | Tulajdonos |
| --- | --- | --- |
| HTTP-contract | Pontos endpoint, státuszkód, JSON és request ID | FND-009–011 |
| Health izoláció | Liveness/status külső hívás nélkül, Qdrant down → 503, Jev down nem befolyásol | FND-009, FND-017 |
| Hibatartalom | Egységes envelope, szűrt details, titok és stack trace nélkül | FND-011 |
| Qdrant-határ | Fake probe unit tesztben, valódi probe külön integration tesztben | FND-017 |
| Decision contract | Mindhárom primitív, teljes azonosítóegyezés, invalid input/output elutasítva | FND-018–020 |
| Providerhibák | Timeout/retry határolt, SDK-hiba nem szivárog, nincs csendes fallback | FND-019–020 |
| Offline futás | Mock és SDK contract teszt külső AI-hívás nélkül, live smoke elkülönítve | FND-020–023 |

Az FND-003 specifikációs elfogadása teljesült: az API-verziózás, hibák, health, DecisionPort, Qdrant-határ és későbbi providerhatárok meghatározottak. A fenti futásidejű ellenőrzések a megjelölt implementációs feladatok lezárási feltételei.
