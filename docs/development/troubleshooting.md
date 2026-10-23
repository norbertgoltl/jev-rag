# Infrastruktúra hibakeresés

- Hiányzó vagy álló Docker Desktop: telepítsd/indítsd kézzel, majd `make doctor`. A projekt nem indítja automatikusan.
- Hiányzó `desktop-linux` context: ellenőrizd a Desktop Linux Engine beállítását. Nincs másik Engine-re fallback vagy globális contextváltás.
- Nem ARM64 Engine: az előírt Apple Silicon Docker Desktop környezetet használd. Ne válts x86 emulációra.
- Foglalt port: `lsof -nP -iTCP:6333 -sTCP:LISTEN`. Idegen folyamatot ne állíts le automatikusan. Állíts külön QDRANT_HOST_PORT és egyező QDRANT_URL értéket.
- Image pull hiba: ellenőrizd a Docker Hub elérhetőségét, majd ismételd az up parancsot. Nincs mozgó tag fallback.
- Unhealthy/startup timeout: `make status`, `make logs`. Ellenőrizd a healthcheck read-only helper mountját és a volume írhatóságát. Ne töröld a volume-ot javításként.
- FastAPI readiness 503: `make health`, majd ellenőrizd a backend QDRANT_URL és timeout értékét. A liveness kiesés nélkül is 200 marad.
- Sikertelen infra-test: a kiírt egyedi projekt és volume megmarad diagnosztikára. A takarítás határai az [infrastruktúra runbookban](infrastructure.md) szerepelnek.
- Docker Desktop reset/adattörlés: adatvesztést okozhat, a named volume nem mentés. A projekt nem végez resetet vagy automatikus visszaállítást.
