# Backend workspace

Az FND-008 önálló Python-projektje elkészült: uv-managed CPython `3.14.8`, `src/jev_rag_api` package, `uv_build`, rögzített `uv.lock` és projektlokális `.venv`.

A repository gyökeréből `make setup-api` telepíti a rögzített függőségeket. A lockfile ellenőrzése: `uv lock --project apps/api --check`. A virtuális környezet nem verziókezelendő, globális projektfüggőség nincs.

A FastAPI alkalmazásváz az FND-009, a konfiguráció az FND-010, a hibakezelés és logging az FND-011 feladata. Ebben az állapotban még nincs futó API.
