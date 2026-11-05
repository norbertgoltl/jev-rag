# Jev / TypeSafe integráció

A Python backend egyetlen TypeSafe integrációja az `integrations/jev` adapterréteg. SDK: `typesafe-sdk==0.7.5`, baseline modell: `jev-1.13.0`. A TypeSafe JavaScript SDK nem része a frontendnek. A Python 3.14 saját zstd támogatása elegendő, külön SDK extra nincs.

## Konfiguráció

A root `.env.example` alapján állítsd be a root `.env` fájlt, meglévőt ne írj felül.

| Változó | Alapérték / szabály |
| --- | --- |
| JEV_MODE | development/test: mock. Production esetén explicit live vagy disabled, mock tiltott |
| TYPESAFE_API_KEY | SecretStr, csak live módban kötelező, nem lehet üres vagy hibás formátumú |
| TYPESAFE_MODEL | jev-1.13.0, mozgó alias nem használható |
| TYPESAFE_TIMEOUT_SECONDS | 5.0, pozitív és véges |
| TYPESAFE_RETRY_MAX | 1, nem negatív egész |
| TYPESAFE_RETRY_BUDGET_SECONDS | 10.0, pozitív és véges |

Live kulcs nélkül és tiltott production konfigurációval az alkalmazás nem indul. A kulcs nem kerülhet frontendbe, NEXT_PUBLIC változóba vagy logba. Mock/disabled módban nincs SDK-kliens vagy külső hívás. A disabled adapter DecisionUnavailableError hibát ad. Nincs szolgáltatáshibát elfedő mock fallback.

A factory `decision_port` argumentummal explicit mockot fogadhat. A `get_decision_port` dependency FastAPI dependency_overrides segítségével is felülírható. Az alapértelmezett mockban nincsenek általános válaszok: a hívó tesztnek a teljes requesthez tartozó fixture-t kell adnia.

## Timeout, retry és hibák

A Settings timeout, modell és RetryPolicy értékei közvetlenül az SDK-konstruktorba kerülnek. Nincs második alkalmazásszintű retry loop. Az SDK exponenciális backoffot és Retry-After figyelembevételt használ. 400/401/403/422 nem retryolható. 429, 529, átmeneti 500/502/503/504 és connection/timeout korlátozottan retryolható. A budget előtt a következő túl hosszú várakozást az SDK elutasítja.

A 400/422 invalid request, 401/403 authentication, 429 rate limited, timeout timeout, connection/5xx és minden más, ismeretlen SDK-hiba unavailable domain hiba. Az SDK-hibák leképezése az SDK típusos kivételosztályain alapul (nem a státuszkód attribútumán); invalid request hibát csak a 400/422 válasz vagy a request SDK-típusokra képezésének helyi hibája ad. A mock adapter fixture-jei explicit `(request, result)` párok, a teljes request pontos egyezése alapján. Hibás vagy hiányzó válasz invalid response. SDK exception, teljes provider body, state vagy API-kulcs nem része a domain hibaüzenetnek. A kliens inicializálási hibája biztonságos configuration hiba.

A strukturált logok eseményt, request-korrelációt, modellazonosítót, provider request ID-t, kérdésszámot és primitívtípusokat, időtartamot, opcionális tokenszámot és biztonságos hibakódot tartalmaznak. State, instructions és válasz nem naplózható. A typesafe_sdk logger WARNING szinten fut, az SDK warningok tartalmát biztonságos állandó eseménynévre cseréljük, így ismeretlen kérdésazonosító vagy exception sem szivárog ki. A TYPESAFE_LOG_LEVEL=debug ezt a provider inicializálása után nem írja felül.

## Offline ellenőrzés

```sh
make setup-api
make test-api
make test
make smoke
```

A make test backend- és frontendteszteket futtat. Nem igényel Dockert, Qdrantot, API-kulcsot vagy külső hálózatot. A valódi SDK contract tesztjei HTTPX2 MockTransportot használnak, nem külön REST klienst. A retrytesztek nulla várakozással vagy mockolt async sleep-pel futnak, a budgetteszt várakozás nélkül ellenőriz. A HU/EN fixture-ök szerkezeti kompatibilitást igazolnak, nem azonos döntési pontosságot vagy kalibrációt.

## Opcionális élő smoke

A live smoke fizetős külső kérést indíthat. Csak tudatos engedélyezéssel futtasd, a kulcsot biztonságos környezeti beállításból vagy a nem verziókezelt `.env` fájlból add meg.

```sh
JEV_LIVE_SMOKE=1 JEV_MODE=live make jev-smoke
```

A parancs csak érvényes TYPESAFE_API_KEY és hozzáférhető modell mellett működhet. Egy mesterséges, nem érzékeny state-et küld egyetlen system_one kérésben category/Choice, urgency/Score és needs_action/Noul kérdésekkel. Csak szerkezetet, modellazonosítót és értéktartományokat ellenőriz, konkrét döntést nem. Nem jelent mock eredményt élő sikerként. A normál pytest-futásban a live teszt akkor is skipped, ha a környezetben van API-kulcs. A külön CLI `--jev-live` kapcsoló és JEV_LIVE_SMOKE=1 együttesen szükséges.

## Ellenőrzési eredmények

116 backendteszt sikeres, 1 explicit live smoke skipped. A frontend 18 tesztje és a developer CLI smoke sikeres. A tesztek ellenőrzik a primitíveket, request/result validációt, mock determinisztikusságot, SDK wire-formátumot, hibamappinget, retry/budget viselkedést, klienslezárást, provider/DI-t és naplóvédelmet. Az SDK telepítése a backend függőségeit és uv.lock fájlját bővítette, a frontend függőségei változatlanok.

2026-10-23-án az explicit élő smoke teszt is sikeresen lefutott:

```sh
JEV_LIVE_SMOKE=1 JEV_MODE=live make jev-smoke
```

Eredmény: `1 passed in 0.29s`, 0 kilépési kód. A valódi TypeSafe SDK egyetlen system_one kérésében a category/Choice, urgency/Score és needs_action/Noul primitívek strukturális szerződése, az eredményértékek érvényessége és a jev-1.13.0 modellazonosító ellenőrzése sikeres. Ez élő API-ellenőrzés volt, nem mock eredmény. Döntési pontosságot vagy HU/EN minőségi egyenértékűséget nem mér. A kulcsot és a teljes provider választ nem rögzítettük. A normál offline tesztfutásban a live smoke továbbra is skipped.
