# Backend workspace

A Python-projekt gyökere ez a könyvtár. Az FND-008 hozza létre a `pyproject.toml`, `.python-version` és `uv.lock` fájlokat, valamint a projektlokális `.venv` környezetet. A terv szerinti Python-verzió `3.14.8`, uv által kezelve.

A FastAPI-váz az FND-009–011 feladata. Jelenleg nincs indítható backend. Nincs gyökérszintű Python-projekt vagy uv workspace, a Python-függőségek nem kerülnek a pnpm workspace-be.

A backend konfigurációja később a repository gyökerében lévő `.env` fájlból, explicit útvonallal töltődik be. A fájlt shellből végrehajtani tilos.
