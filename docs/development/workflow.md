# Fejlesztői környezet és workflow

## Támogatott környezet

Elsődleges környezet: macOS Apple Silicon. A parancsok POSIX shellre és GNU/BSD Make szintaxisra épülnek, Linux/WSL alatt is használhatók. A jelenlegi valódi futtatási ellenőrzés macOS-en, GNU Make 3.81-gyel történt. A BSD make verziófelismerését szimulált smoke teszt ellenőrzi, valódi BSD make futtatás még nem történt.

| Eszköz | Követelmény | Verzióforrás |
| --- | --- | --- |
| Git | Elérhető CLI | A `doctor` kiírja a verziót |
| Make | GNU Make vagy BSD make | A `doctor` kiírja a verziót |
| uv | Python-projektkezelő | A `doctor` kiírja a verziót |
| Python | uv-managed `3.14.8`, telepítve és ellenőrizve | FND-008-tól `apps/api/.python-version` |
| Node.js | `24.22.1`, a kijelölt 24 LTS ágból | Root `.node-version` és `package.json` |
| pnpm | `12.15.0` | Root `package.json` `packageManager` |
| Corepack | Bootstraplehetőség, meglévő megfelelő pnpm mellett opcionális | A `doctor` kiírja, ha elérhető |
| Docker + Compose | Elérhető CLI és Compose plugin | A `doctor` kiírja a verziót |

A Node.js- és pnpm-pinek a jelenleg telepített, ellenőrzött verziókat rögzítik. Frissítéskor a kapcsolódó verzióforrásokat együtt kell módosítani és újraellenőrizni.

A Node.js-et felhasználói verziókezelővel válaszd ki a `.node-version` alapján. A pnpm-et a `packageManager` pin szerint biztosítsd. A rendelkezésre álló Corepack használható bootstraphez, de a `doctor` nem aktivál shim-et, nem tölt le csomagkezelőt és nem telepít globális csomagot. Ha nincs helyben a rögzített pnpm, hibát ad.

Hivatalos háttér: [Node.js kiadások](https://nodejs.org/en/about/previous-releases), [pnpm telepítés](https://pnpm.io/installation), [pnpm workspace](https://pnpm.io/workspaces), [uv telepítés](https://docs.astral.sh/uv/getting-started/installation/).

## Projektgyökerek és lockfile-ok

| Útvonal | Felelősség |
| --- | --- |
| `apps/api/` | Egyetlen Python-projekt, saját `pyproject.toml`, `uv.lock` és `.venv`, FND-008-tól |
| `apps/web/` | Next.js és saját `package.json`, FND-012-től |
| `package.json` | Privát workspace-koordinátor, runtime- és package manager pin, alkalmazásfüggőség nélkül |
| `pnpm-workspace.yaml` | Kizárólag `apps/web`, közös root lockfile-lal |
| `infra/compose.yaml` | Docker-infrastruktúra, FND-015–017-től |
| `docs/foundation/` | Foundation acceptance checklist és tényleges release-validáció |
| `scripts/` | Fejlesztői CLI és offline smoke tesztek |
| `docs/architecture/`, `docs/adr/`, `docs/foundation/` | Architektúra, döntések, fázishatárok |
| `docs/development/` | Setup és fejlesztési workflow |
| `.github/` | PR-sablon és GitHub Actions CI |

Nincs root Python-projekt, uv workspace, frontend saját lockfile vagy előre létrehozott shared/agent/embedding csomag. Az alkalmazásgyökereket jelenleg a saját README-jük tartja fenn, üres `.gitkeep` nélkül.

Az `apps/api/uv.lock` az FND-008 során elkészült, a root `pnpm-lock.yaml` az FND-012 feladata. A későbbi lockfile-ok és runtime-pinek verziókezelendők. A setup nem generálhat hiányzó lockfile-t, és nem oldhat fel új verziókat.

## Jelenleg futtatható parancsok

A repository gyökeréből:

```sh
make help
make doctor
make smoke
```

A `help` a teljes stabil parancsfelületet mutatja. A `doctor` összegyűjti a diagnosztikát, hiányzó vagy eltérő eszköz esetén nem nulla kóddal lép ki. Nem vizsgál daemon- vagy szolgáltatáskészenlétet, nem módosít konfigurációt. A Python-keresés offline, kizárólag már telepített uv-managed interpreterek között történik.

A pnpm automatikus package manager feloldását a `pmOnFail: ignore` kikapcsolja, a verzióegyezést a CLI külön ellenőrzi. A diagnosztika a Corepack projektalapú váltását és hálózati hozzáférését is letiltja a verziólekérdezésre. Így az ellenőrzés nem generál pnpm boot-lockfile-t és nem tölti le a hiányzó verziót. A viselkedést a [pnpm CLI-beállításai](https://pnpm.io/settings/cli#pmonfail) írják le.

A `smoke` külső API, Docker daemon és telepített alkalmazásfüggőségek nélkül fut, ideiglenes másolatban és szimulált eszközökkel. Ellenőrzi a diagnosztika sikeres és hibás eseteit, az el nem készült targetek hibáját, a setup delegálását és hibaterjedését, a szóközös útvonalakat és azt, hogy a `.env` tartalma nem fut le. Az ideiglenes fájlokat eltávolítja, a valódi workspace-eket nem inicializálja.

Más könyvtárból `make -C /absolute/path/to/jev-rag help` használható. A shell belépési pontok is saját fájlhelyükhöz képest oldják fel a repository gyökerét.

## Későbbi alrendszereket igénylő parancsok

| Parancs | Delegálás vagy jelenlegi akadály |
| --- | --- |
| `make setup` | Előbb ellenőrzi mindkét workspace manifestjét, az API Python-pinjét és mindkét lockfile-t. Ezután `uv sync --project apps/api --managed-python --locked`, majd root `pnpm install --frozen-lockfile`. A frontend manifestje és a gyökérszintű lockfile elkészült. |
| `make up` | Qdrant indítása, legfeljebb 90 másodperces health várakozással. |
| `make down` | Projekt leállítása a volume és a host appok megőrzésével. |
| `make status`, `make logs` | Projekt Qdrant állapota és követhető logjai. |
| `make dev-api` | Hoston futó FastAPI indítása, uv-környezetben, alapértelmezetten loopback címen. |
| `make dev-web` | A @jev-rag/web dev parancsát hívja, 127.0.0.1:3000 címen. |
| `make lint`, `make format`, `make typecheck` | Backend és frontend quality gate-ek, lásd a [tesztelési útmutatót](testing.md). |
| `make check` | Lint, format-check, typecheck, offline teszt coverage-dzsel és frontend production build. |

Minden hiányzó alrendszerhez érthető, nem nulla kilépési kód tartozik. A setup az első telepítési hiba után leáll, nem futtatja a következő csomagkezelőt. A két csomagkezelő telepítése nem közös tranzakció, a sikeres első lépést a második hibája nem vonja vissza. Ismételt setup ugyanazokat a rögzített függőségeket szinkronizálja. A GitHub Actions négy külön jobban futtatja a backend, frontend, infrastruktúra és security ellenőrzést, lásd a [CI-útmutatót](ci.md).

A későbbi infrastruktúra-implementáció ellenőrzi a Docker daemon elérhetőségét és a portütközést. Normál leállítás soha nem használhat volume-törlést. A FastAPI és Next.js nem kerül Dockerbe.

## Konfiguráció és hostizoláció

A root [.env.example](../../.env.example) secret nélküli backend/infra minta. Szükség esetén másold `.env` névre. Jelenleg a CLI nem tölti be, és nem is hajtja végre. Az app- és infrastruktúra-feladatok később explicit abszolút útvonalon adják át a saját dotenv/Compose betöltőjüknek. Nem függhetnek az indítási munkakönyvtártól.

A frontend `.env.local.example` mintája az FND-012–014 során készül el, a lokális változat `apps/web/.env.local`. API-kulcs nem kerülhet frontendkódba vagy publikus változóba. Mock módban TypeSafe-kulcs nem szükséges, live mód hiányzó kulccsal hibázik.

Python-csomag csak a projekt `.venv` környezetébe, frontendfüggőség csak pnpm által kezelt projektkönyvtárba kerülhet. Rendszer-Python, rendszer-Node vagy globális projektspecifikus npm/pip csomag nem módosítható. A uv interpretertára és a pnpm cache lehet felhasználói szintű.

## Git és szerkesztési szabályok

Rövid életű branchek a `main` fölött, review és squash merge. Új feladatnál `feature/fnd-XXX-description`, hibajavításnál `fix/fnd-XXX-description` név használható. A commitüzenet Conventional Commits formátumú, angolul, például:

```text
chore(repo): initialize monorepo development tooling
```

Commitüzenethez co-author nem adható. A [PR-sablon](../../.github/pull_request_template.md) rögzíti a minőségellenőrzéseket.

Az EditorConfig UTF-8-at, LF-et, végső újsort, Pythonhoz és shellhez 4, TypeScript/JSON/YAML-hez 2 szóközt, Makefile-hoz tabot ír elő. A Git attributes normalizálja a szövegeket és binárisként kezeli a kijelölt médiatípusokat.

A `.gitignore` kizárja a secret fájlokat, környezeteket, függőségeket, buildet és cache-t. A `.env.example`, `.env.local.example` és hasonló minták kivételek. Ez nem akadályozza meg a titkok explicit hozzáadását; a titokellenőrzés részletei a [security baseline](security.md) dokumentumban vannak.

Commit előtt `git status --short`, `git diff --check` és `make smoke` futtatandó, a `doctor` eltéréseit is rögzíteni kell. Új fájloknál a diff mellett a fájlok tartalmát is át kell nézni, mert a `git diff` önmagában nem mutatja az untracked fájlokat. Ellenőrizendő, hogy nincs secret, `.venv`, `node_modules` vagy generált adat a változások között.

## FND-005–007 ellenőrzési állapot

A struktúra, workspace-metaadatok, Git/editor szabályok, PR-sablon, CLI és smoke tesztek elkészültek. A `make help` és a `make smoke` sikeres. A Python-környezet javítása után a valódi `make doctor` is sikeresen lefutott, 0 kilépési kóddal. Az uv-managed Python `3.14.8`, Node.js `24.22.1`, pnpm `12.15.0`, Git, Make, uv, Corepack és Docker Compose ellenőrzése megfelelő. A diagnosztika nem telepített vagy módosított eszközt, alkalmazás- és infrastruktúra-készenlétet nem vizsgál. Az aktuális release-validáció státuszait a [Foundation release report](../foundation/release-report.md) rögzíti.

Az alkalmazás quality gate parancsai: `make lint`, `make format-check`, `make typecheck`, `make test` és `make check`. Részletek: [tesztelés](testing.md), [CI](ci.md).

## FND-008–011 ellenőrzési állapot

Elkészült a backend, a típusos konfiguráció, a hibakezelés és a JSON logging. A valódi uv.lock alapján a projekt települt. A 36 backendteszt, a lockfile-ellenőrzés, a wheel/sdist build, az élő host HTTP smoke és a módosított CLI smoke teszt sikeres. A readiness valódi Qdrant-adapter nélkül továbbra is 503. Részletek és parancsok: [API README](../../apps/api/README.md), [backend konfiguráció](backend.md).


### FND-012–014 ellenőrzés

A frontend hivatalos generátorból készült. A pnpm 12.15.0 szerinti frozen telepítés, ESLint, Next route typegen és TypeScript, 18 mockolt teszt, backend nélküli production build, CLI smoke és production HTTP smoke sikeres. A Node.js 24.22.1 és pnpm 12.15.0 host verzióra rögzítése után a `make doctor` sikeres volt. A lockfile SHA-256 ellenőrzőösszege változatlan, újragenerálás nem történt. A Qdrant-ready integrációt az FND-015–017, a teljes clean-clone diagnosztikai útvonalat az aktuális [release report](../foundation/release-report.md) rögzíti. Részletek: [frontend](../../apps/web/README.md).

Az FND-015–017 infrastruktúra és valódi Qdrant readiness elkészült. Aktuális parancsok és validáció: [infrastruktúra](infrastructure.md).

A `make test` offline backend- és frontendteszteket futtat. A `make jev-smoke` külön engedélyezett live TypeSafe ellenőrzés, nem része a normál tesztfutásnak. Részletek: [Jev integráció](jev-integration.md).
