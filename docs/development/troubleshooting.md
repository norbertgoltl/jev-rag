# Infrastruktúra hibakeresés

- Hiányzó vagy álló Docker Desktop: telepítsd/indítsd kézzel, majd `make doctor`. A projekt nem indítja automatikusan.
- Hiányzó `desktop-linux` context: ellenőrizd a Desktop Linux Engine beállítását. Nincs másik Engine-re fallback vagy globális contextváltás.
- Engine/image architektúrahiba: macOS Apple Siliconon ARM64, x64 Linux CI-n x64 natív image szükséges. Ne kényszeríts emulációt.
- Foglalt port: `lsof -nP -iTCP:6333 -sTCP:LISTEN`. Idegen folyamatot ne állíts le automatikusan. Állíts külön QDRANT_HOST_PORT és egyező QDRANT_URL értéket.
- Image pull hiba: ellenőrizd a Docker Hub elérhetőségét, majd ismételd az up parancsot. Nincs mozgó tag fallback.
- Unhealthy/startup timeout: `make status`, `make logs`. Ellenőrizd a healthcheck read-only helper mountját és a volume írhatóságát. Ne töröld a volume-ot javításként.
- FastAPI readiness 503: `make health`, majd ellenőrizd a backend QDRANT_URL és timeout értékét. A liveness kiesés nélkül is 200 marad.
- Sikertelen infra-test: a kiírt egyedi projekt és volume megmarad diagnosztikára. A takarítás határai az [infrastruktúra runbookban](infrastructure.md) szerepelnek.
- Docker Desktop reset/adattörlés: adatvesztést okozhat, a named volume nem mentés. A projekt nem végez resetet vagy automatikus visszaállítást.
- Security check Gitleaks hibával áll le: futtasd a `make security-setup` parancsot, ellenőrizd a hálózatot és a támogatott platformot, majd ismételd a `make security-check` futtatását. A kiírt jelentésben ne jeleníts meg secret értéket.
- Security scanner finding: a credentialt kezeld kompromittáltnak, vond vissza vagy rotáld, majd kövesd a [security incident eljárást](security.md#incident-procedure). Az eltávolítás önmagában nem von vissza egy korábban kiszivárgott kulcsot.
