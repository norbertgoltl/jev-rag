# FastAPI Foundation

Az FND-008–010 Python-projektje és FastAPI-váza elkészült. `make setup-api`, `make test-api` és `make dev-api` használható a repository gyökeréből. Az alkalmazás `127.0.0.1:8000` címen indul, hoston, uv-környezetben.

A liveness és a system status külső szolgáltatás nélkül 200-at ad. Az alapértelmezett readiness 503, a fake probe tesztben 200/503 állapotot adhat. `/docs` és `/openapi.json` elérhető, a CORS kizárólag a frontend explicit originjét engedi.

A konfiguráció Pydantic Settings modellen keresztül érkezik, root `.env` útvonallal, explicit injectionnel, validált porttal, URL-lel, timeouttal és CORS-origin listával. Productionben a debug tiltott. A hibák, request ID és JSON logging az FND-011 feladata. Qdrant/Jev SDK nem része ennek a PR-nek.
