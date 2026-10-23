# Qdrant infrastruktúra

A Docker Desktop telepítése és elindítása kézi fejlesztői előfeltétel. Külön runtime és VM-kezelő nem szükséges. A projekt nem állítja át a Docker Desktopot és nem módosítja a globális Docker contextet.

## Előfeltételek

```sh
docker context inspect desktop-linux
docker --context desktop-linux info
docker --context desktop-linux compose version
cp .env.example .env
make setup-api
make doctor
```

Meglévő `.env` fájlt ne írj felül. A helper dotenv-parserrel olvassa, shellként nem futtatja. A doctor a Docker Desktop context, Linux ARM64 Engine, Compose, legalább 2 CPU és 4 GiB memória, valamint a host port foglaltságát vizsgálja. Saját futó Qdrant portja elfogadott, idegen folyamaté nem. Az ajánlott 40 GiB virtuális lemezkapacitást és a kikapcsolt Kubernetes állapotát kézzel ellenőrizd a Desktopban, ezeket a script nem módosítja. A doctor telepített backend környezetet igényel, függőséget nem telepít.

## Konfiguráció

Az `infra/compose.yaml` Qdrant `qdrant/qdrant:v1.19.2` Linux ARM64 image-et használ. A projekt neve alapból `jev-rag`, szolgáltatása `qdrant`, adatai a `jev-rag_qdrant_data` named volume-ban, `/qdrant/storage` alatt vannak. Csak a `127.0.0.1:6333` HTTP-port publikált, gRPC és cluster port nem. Nincs alkalmazáskonténer, privilegizált mód vagy Docker socket mount.

A root `.env` változói: `COMPOSE_PROJECT_NAME`, `QDRANT_HOST_PORT`, `QDRANT_URL`, `QDRANT_TIMEOUT_SECONDS`. Portváltoztatáskor a host portot és az API URL-t együtt módosítsd. A Compose explicit `--env-file .env -f infra/compose.yaml` útvonalakat és `--context desktop-linux` contextet kap. Nincs automatikus fallback más Engine-re.

## Parancsok

```sh
make up
make status
make health
make logs
make down
make infra-test
```

Az up validálja a konfigurációt és legfeljebb 90 másodpercig vár a healthy állapotra. A logs kizárólag a projekt Qdrant logjait követi, Ctrl-C megszakítja. A health a hostról kérdezi a konfigurált URL `/readyz` útvonalát a beállított timeouttal. Csak HTTP 200 sikeres. A down nem töröl volume-ot, image-et, és nem állítja le a host alkalmazásokat vagy a Desktopot. Ismételt up/down biztonságos.

A konténer healthcheck Bash beépített TCP-funkcióval valódi HTTP-kérést küld, és csak 200-at fogad el. Interval 10s, timeout 3s, retries 5, start period 15s. A helper read-only mount, nem adattárolási bind mount. A rögzített image-ben a Bash és a TCP működése élő healthcheckkel ellenőrzött.

## FastAPI readiness

Az app lifespan egy HTTPX AsyncClientet kezel. A QdrantReadinessProbe `check()` metódusa kizárólag HTTP 200-nál igaz, timeout/kapcsolathibánál strukturált warning és hamis. A meglévő `check_health()` port kompatibilis marad. Klienslezárás shutdownkor történik. Nincs SDK, collection-kezelés vagy retrieval.

Qdrant elérhető: `/health/ready` 200. Kiesés: 503, `/health/live` továbbra is 200. Helyreállás után readiness ismét 200. Belső URL és exception nem kerül a válaszba vagy warning logba.

## Izolált teszt és adatmegőrzés

Az infra-test egyedi `jev-rag-test-<uuid>` projektet, szabad külön portot és külön named volume-ot használ. Tesztcollectiont és azonosítható pontot ír, kétszer indít és állít le, konténert újralétrehoz, ellenőrzi a pont megmaradását és a FastAPI 200 → 503 → 200 viselkedését. Vizsgálja az ARM64 image-et, a mountot, portokat és a globális context változatlanságát. Sikerkor csak a saját, Compose-label alapján is igazolt tesztvolume-ot törli. A normál fejlesztői volume-ot nem érinti.

Hibánál a teszt kiírja a projektnevet és megőrzi az erőforrásokat. Diagnosztika: `docker --context desktop-linux compose --env-file .env -f infra/compose.yaml -p <test-project> ps -a`, majd `logs qdrant`. Kézi takarításkor előbb igazold a tesztprojektet és a volume Compose-labeljét. Normál projektben ne használj `down -v` parancsot.

A volume a Docker Desktop Engine adattárolójában él. Factory reset, Desktop-adattörlés vagy célzott volume-törlés adatvesztést okozhat. A named volume nem backup. Automatikus snapshot/restore nincs. Qdrant-verziófrissítés külön PR-t és storage/migráció kompatibilitási vizsgálatot igényel.

## Validáció

43 backendteszt és CLI smoke sikeres. Az izolált Docker acceptance teszt igazolta a startupot, ARM64-et, localhost-only portokat, named volume-ot, adatmegőrzést rekreáció után, readiness kiesést/helyreállást és context-védelmet. A korábbi CLI smoke a még el nem készült up parancs hibáját várta, ezért először hibázott. A tesztet az új lifecycle szerződéshez igazítottuk. Az offline uv lock feloldás cache-hiány miatt hibázott, hálózattal a lock sikeresen frissült, a 26 csomag verziója nem változott. A Starlette HTTPX TestClient deprecation warningja ismert, a tesztek sikeresek.
