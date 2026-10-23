# Backend konfiguráció és hibakezelés

## Konfiguráció

A `Settings` Pydantic Settings modell prioritása: explicit értékek, process environment, root `.env`, alapértelmezések. A `.env` abszolút útvonala a forrásfájl helyéből származik, nem az indítási könyvtárból. A hiányzó `.env` megengedett, az ismeretlen Compose/Jev mezők figyelmen kívül maradnak. A fájl nem fut le shell kódként.

| Változó | Default | Validáció |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`, `test`, `production` |
| `APP_DEBUG` | `false` | Productionben nem lehet true |
| `API_HOST` | `127.0.0.1` | Nem üres string |
| `API_PORT` | `8000` | Egész, 1–65535 |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `CORS_ALLOWED_ORIGINS` | `["http://127.0.0.1:3000"]` | JSON-tömb, explicit HTTP(S) origin, wildcard és útvonal nélkül |
| `QDRANT_URL` | `http://127.0.0.1:6333` | HTTP(S) URL |
| `QDRANT_TIMEOUT_SECONDS` | `1.0` | Pozitív, véges szám |

A mintafájl a root [.env.example](../../.env.example). TypeSafe-kulcsot a backend még nem igényel. A későbbi secret mezők `SecretStr` típusúak legyenek. Settings objektum vagy nyers konfiguráció nem kerül HTTP-válaszba és logba. Az Uvicorn indító hibás konfigurációnál biztonságos üzenettel leáll.

Az `APP_DEBUG` true értéke sem kapcsolhatja be a publikus Starlette traceback-válaszokat. A HTTP debug mód ezért mindig kikapcsolt. Tesztben `Settings(_env_file=None, ...)` és explicit factory injection használható. A tesztgyűjtés az importálható default appot is izolált konfigurációval tölti be.

## Hibák, CORS és request ID

A publikus hibaformátum `{error: {code, message, details}, request_id}`. A `details` nullable, validációs hibánál kizárólag bemeneti helyet és hibakódot tartalmaz. Nem szerepelhet benne inputérték, dinamikus dictionary-kulcs, SDK-válasz vagy stack trace.

A 404, 405, 422, 500 és alkalmazásszintű 503 az [interfészszerződést](../architecture/interface-contracts.md) követi. A 405 megőrzi az `Allow` headert. A readiness függőséghibája külön diagnosztikai JSON és 503. Ismeretlen alkalmazáshiba biztonságos `INTERNAL_ERROR` választ ad.

Minden HTTP-válasz `X-Request-ID` headert kap. A bejövő ID 1–64 ASCII betű, szám, pont, aláhúzás vagy kötőjel lehet. Hiányzó, hibás vagy több példányban küldött ID helyett UUID4 keletkezik. A hibatörzs azonosítója a válaszheaderével egyezik. A `ContextVar` a teljes ASGI kérés idejére érvényes, végül visszaáll.

A request context és a CORS a Starlette server-error rétegén kívül található, ezért a preflight és az 500-as válasz is korrelálható. CORS: csak a konfigurált originlista, GET/OPTIONS, Content-Type/X-Request-ID request header, X-Request-ID exposed header, credentials nélkül.

## Strukturált logging

A standard `logging` JSON formatter UTC ISO-időbélyeget, szintet, service-t, eseményt és request ID-t ír. A HTTP completion esemény ezen felül metódust, query nélküli pathot, státuszt és időtartamot tartalmaz. Váratlan hibánál csak az exception típusa kerül a logba, a szövege és stack trace nélkül.

A request/response body, authorization header, API-kulcs, query string, dokumentumtartalom és Settings objektum nem naplózható. A formatter csak a kijelölt extra mezőket szerializálja. A lezárt biztonságos 500-as válasz után visszadobott Starlette-hibát a külső middleware lezárja, hogy Uvicorn ne írja ki a nyers kivételt.

A hivatalos `jev-rag-api` indító kikapcsolja az Uvicorn access logját és JSON formátumra állítja a szerverlogokat. Egy HTTP-kéréshez egy completion esemény tartozik. A megszakadt streaming válasz nem folytatható új hibatörzzsel.

## Ellenőrzések

A tesztek fake readiness probe-ot és HTTPX/TestClient transportot használnak, Docker és AI-kulcs nélkül. Vizsgálandó a két readiness állapot és timeout, a külső hívást nem végző liveness/status, CORS, konfigurációprioritás, 404/405/422/500/503, request ID és párhuzamosság, valamint a logok adatvédelme.

Az aktuális végrehajtási állapot az [API README-ben](../../apps/api/README.md) található. A 36 pytest teszt és a hoston futó Uvicorn HTTP-smoke ellenőrzése sikeres, az utóbbi után a tesztszerver leállt. A Qdrant/Jev továbbra sem része ennek az ellenőrzésnek.
