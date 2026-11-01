# macOS Apple Silicon setup

This guide uses a separate clone or a new project directory. It does not reset Docker Desktop, overwrite an existing `.env`, or delete a Qdrant volume.

## Prerequisites

Install and start Docker Desktop manually. Install Git, Make, `uv`, `fnm`, and pnpm 12.15.0. The repository pins Python 3.14.8 in `apps/api/.python-version`, Node.js 24.22.1 in `.node-version`, and pnpm 12.15.0 in the root `package.json`. Docker Compose V2 must be available through Docker Desktop.

## Clean setup

```sh
git clone <repository-url> jev-rag-clean
cd jev-rag-clean
fnm use
cp .env.example .env
make doctor
make setup
make security-setup
```

If `.env` already exists, inspect it and preserve it instead of copying over it. The template selects mock Jev mode and has no live credential. `make doctor` checks versions and local prerequisites. `make setup` installs the locked backend and frontend dependencies in project-managed environments.

## Start and validate

```sh
make up
make dev-api
```

In a second terminal, start the frontend:

```sh
cd jev-rag-clean
make dev-web
```

Open `http://127.0.0.1:3000` for frontend diagnostics. The API is bound to `http://127.0.0.1:8000`; Qdrant exposes REST only on `http://127.0.0.1:6333`.

```sh
make health
make check
make security-check
make security-smoke
make infra-test
```

`make check` and security checks do not require a Jev API key. `make infra-test` uses an isolated Compose project, port, and volume, then removes only its own resources after success.

Stop the application terminals with Ctrl-C, then stop Qdrant while preserving its data:

```sh
make down
```

For release evidence, record the actual command outputs and machine versions in [`../foundation/release-report.md`](../foundation/release-report.md). Use a fresh directory for the clean-clone test so current development files and data remain untouched.
