# Jev RAG API

Önálló `src/jev_rag_api` projekt, `uv_build` build backenddel, uv-managed CPython `3.14.8` interpreterrel. A virtuális környezet helye `apps/api/.venv`. Nincs root uv workspace vagy globális projektfüggőség.

## Ellenőrzési állapot

Az FND-008–011 megvalósítása ellenőrzött: a valódi `uv.lock` elkészült, a projekt editable módban települt az `apps/api/.venv` környezetbe. A 36 backendteszt, a lockfile-ellenőrzés, a wheel/sdist build és az élő HTTP smoke teszt sikeres CPython `3.14.8` alatt.

Az élő szerver mind az öt dokumentált végpontja és a request ID headerek ellenőrzöttek, a readiness Qdrant nélkül 503. A szerverlogok JSON formátumúak. A developer CLI smoke tesztjei is sikeresek. A Starlette TestClient az előírt HTTPX használatára deprecation warningot ad, a tesztek ettől sikeresek. A HTTPX2 migráció külön függőségváltoztatás lehet.

## Setup és futtatás

A függőségek feloldása csak explicit függőségváltoztatáskor:

```sh
uv lock --project apps/api
```

Az `apps/api/uv.lock` a rögzített függőségeket tartalmazza és verziókezelendő. Normál fejlesztéskor a repository gyökeréből:

```sh
make setup-api
make test-api
make dev-api
```

A parancsok kizárólag létező lockfile alapján, `--locked` módban futnak. A `make setup` továbbra is igényli a frontend manifestjét és lockfile-ját. A teljes quality gate az FND-021–022 része.

Közvetlen ellenőrzések:

```sh
uv sync --project apps/api --managed-python --locked
uv lock --project apps/api --check
uv run --project apps/api --managed-python --locked pytest
uv run --project apps/api --managed-python --locked python -c 'import jev_rag_api'
uv run --project apps/api --managed-python --locked jev-rag-api
```

Az entrypoint a Settings `API_HOST` és `API_PORT` értékével indít Uvicornt, alapból `127.0.0.1:8000` címen, development módban reloaddal. Az importálható ASGI alkalmazás `jev_rag_api.main:app`, a factory `create_app(settings=..., readiness_probe=...)`.

| Végpont | Elvárt működés |
| --- | --- |
| `GET /health/live` | 200, `{"status":"alive"}`, külső hívás nélkül |
| `GET /health/ready` | Valódi Qdrant HTTP probe, 200 ha ready, egyébként 503 |
| `GET /api/v1/system/status` | 200, `{"service":"api","status":"ok"}` |
| `GET /docs` | Swagger UI |
| `GET /openapi.json` | Generált OpenAPI |

A Qdrant readiness HTTPX runtime klienssel működik. Jev DecisionPort integration is available; RAG is not implemented. Részletek: [backend fejlesztői útmutató](../../docs/development/backend.md), [HTTP-contract](../../docs/architecture/interface-contracts.md).

See docs/development/jev-integration.md for the TypeSafe integration.
