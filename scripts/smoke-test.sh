#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH='' cd "$(dirname "$0")/.." && pwd -P)
MAKE_BIN=$(command -v make)
smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/jev-rag-smoke.XXXXXX")
trap 'rm -rf "$smoke_dir"' 0
trap 'exit 1' HUP INT TERM
fixture_root="$smoke_dir/repo with spaces"
mkdir -p "$fixture_root" "$smoke_dir/bin"
fixture_root=$(CDPATH='' cd "$fixture_root" && pwd -P)
cp "$REPO_ROOT/Makefile" "$REPO_ROOT/package.json" "$REPO_ROOT/.node-version" "$fixture_root/"
cp -R "$REPO_ROOT/scripts" "$fixture_root/"

cat > "$smoke_dir/bin/fake-tool" <<'MOCK'
#!/bin/sh
set -eu
case "${0##*/}" in
    git) printf 'git version 2.50.0\n' ;;
    make)
        if [ "${SMOKE_BSD_MAKE:-0}" = 1 ]; then
            [ "$1" = -V ] || exit 1
            printf '20251001\n'
        else
            printf 'GNU Make 4.4\n'
        fi
        ;;
    node) printf 'v%s\n' "${SMOKE_NODE_VERSION:-24.13.0}" ;;
    corepack) printf '0.34.5\n' ;;
    docker)
        [ "${SMOKE_COMPOSE_MISSING:-0}" = 0 ] || [ "$1" != compose ] || exit 1
        printf 'Docker version 28.0.0\n'
        ;;
    uv)
        case "$1" in
            --version) printf 'uv 0.11.14\n' ;;
            python)
                [ "${SMOKE_PYTHON_MISSING:-0}" = 0 ] || exit 1
                printf '3.14.8\n'
                ;;
            *)
                printf 'uv %s\n' "$*" >> "$CLI_SMOKE_LOG"
                exit "${SMOKE_UV_EXIT:-0}"
                ;;
        esac
        ;;
    pnpm)
        if [ "$1" = --version ]; then
            [ "${pnpm_config_pm_on_fail:-}" = ignore ] || exit 1
            [ "${COREPACK_ENABLE_NETWORK:-}" = 0 ] || exit 1
            printf '%s\n' "${SMOKE_PNPM_VERSION:-12.6.0}"
        else
            printf 'pnpm %s\n' "$*" >> "$CLI_SMOKE_LOG"
        fi
        ;;
esac
MOCK
chmod +x "$smoke_dir/bin/fake-tool"
for tool in git make node corepack docker uv pnpm; do
    ln -s fake-tool "$smoke_dir/bin/$tool"
done
PATH="$smoke_dir/bin:$PATH"
CLI_SMOKE_LOG="$smoke_dir/commands.log"
export PATH CLI_SMOKE_LOG
: > "$CLI_SMOKE_LOG"
smoke_output="$smoke_dir/output"

expect_failure() {
    expected_text=$1
    shift
    if "$@" > "$smoke_output" 2>&1; then
        printf 'FAIL: expected nonzero exit: %s\n' "$*" >&2
        exit 1
    fi
    case "$(cat "$smoke_output")" in
        *"$expected_text"*) ;;
        *) cat "$smoke_output" >&2; exit 1 ;;
    esac
}

cd "$smoke_dir"
"$MAKE_BIN" -C "$fixture_root" help > "$smoke_output"
sh "$fixture_root/scripts/doctor.sh" > "$smoke_output"
SMOKE_BSD_MAKE=1 sh "$fixture_root/scripts/doctor.sh" > "$smoke_output"
expect_failure 'Node.js 24.13.0 required' env SMOKE_NODE_VERSION=22.0.0 sh "$fixture_root/scripts/doctor.sh"
expect_failure 'pnpm 12.6.0 required' env SMOKE_PNPM_VERSION=10.0.0 sh "$fixture_root/scripts/doctor.sh"
expect_failure 'Python 3.14.8 is not installed' env SMOKE_PYTHON_MISSING=1 sh "$fixture_root/scripts/doctor.sh"
expect_failure 'Docker Compose is unavailable' env SMOKE_COMPOSE_MISSING=1 sh "$fixture_root/scripts/doctor.sh"
expect_failure 'Unknown command' sh "$fixture_root/scripts/dev.sh" unknown
mkdir "$smoke_dir/missing-tools"
for tool in dirname cat sed; do
    ln -s "$(command -v "$tool")" "$smoke_dir/missing-tools/$tool"
done
expect_failure 'Missing uv' env PATH="$smoke_dir/missing-tools" /bin/sh "$fixture_root/scripts/doctor.sh"
for target in up down status logs dev-api dev-web lint format typecheck test check; do
    expect_failure 'not implemented' "$MAKE_BIN" -C "$fixture_root" "$target"
done
expect_failure 'Missing apps/api/pyproject.toml' "$MAKE_BIN" -C "$fixture_root" setup
[ ! -s "$CLI_SMOKE_LOG" ]

# Synthetic workspaces exercise delegation without installing dependencies.
mkdir -p "$fixture_root/apps/api" "$fixture_root/apps/web"
printf '3.14.8\n' > "$fixture_root/apps/api/.python-version"
: > "$fixture_root/apps/api/pyproject.toml"
: > "$fixture_root/apps/api/uv.lock"
printf '{}\n' > "$fixture_root/apps/web/package.json"
expect_failure 'Missing pnpm-lock.yaml' "$MAKE_BIN" -C "$fixture_root" setup
[ ! -s "$CLI_SMOKE_LOG" ]
: > "$fixture_root/pnpm-lock.yaml"
printf 'touch "%s"\n' "$smoke_dir/env-was-executed" > "$fixture_root/.env"
expect_failure 'Error' env SMOKE_UV_EXIT=7 "$MAKE_BIN" -C "$fixture_root" setup
case "$(cat "$CLI_SMOKE_LOG")" in
    *pnpm*) printf 'FAIL: pnpm ran after uv failed\n' >&2; exit 1 ;;
esac
: > "$CLI_SMOKE_LOG"
"$MAKE_BIN" -C "$fixture_root" setup > "$smoke_output"
expected_commands=$(printf 'uv sync --project %s/apps/api --managed-python --locked\npnpm install --frozen-lockfile' "$fixture_root")
[ "$(cat "$CLI_SMOKE_LOG")" = "$expected_commands" ] || {
    printf 'FAIL: unexpected setup delegation\n' >&2
    cat "$CLI_SMOKE_LOG" >&2
    exit 1
}
[ ! -e "$smoke_dir/env-was-executed" ]
printf 'PASS: CLI diagnostics, GNU/BSD version detection, unavailable targets, locked setup, failure propagation, space-containing paths and .env isolation\n'
