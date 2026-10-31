#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH='' cd "$(dirname "$0")/.." && pwd -P)
TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/jev-rag-security-smoke.XXXXXX")
trap 'rm -rf "$TEMP_ROOT"' EXIT HUP INT TERM

fixture="$TEMP_ROOT/fixture"
mkdir -p "$fixture/scripts" "$fixture/apps/web/src/lib/config" "$fixture/infra"
mkdir -p "$fixture/.tools"
cp "$REPO_ROOT/.tools/gitleaks" "$fixture/gitleaks"
mv "$fixture/gitleaks" "$fixture/.tools/gitleaks"
cp "$REPO_ROOT/.gitleaks.toml" "$fixture/.gitleaks.toml"
cp "$REPO_ROOT/scripts/security-check.sh" "$fixture/scripts/security-check.sh"
cp "$REPO_ROOT/infra/compose.yaml" "$fixture/infra/compose.yaml"
cp "$REPO_ROOT/apps/web/src/lib/config/server.ts" "$fixture/apps/web/src/lib/config/server.ts"
cat > "$fixture/.env.example" <<'EOF'
JEV_MODE=mock
TYPESAFE_API_KEY=
QDRANT_HOST_PORT=6333
EOF
cat > "$fixture/Makefile" <<'EOF'
security-check:
	@sh scripts/security-check.sh
EOF

fake_bin="$TEMP_ROOT/bin"
mkdir -p "$fake_bin"
cat > "$fake_bin/docker" <<'EOF'
#!/bin/sh
if [ "$1" = "--context" ] && [ "$3" = "compose" ] && [ "$4" = "--env-file" ]; then
    printf '%s\n' '{"services":{"qdrant":{"image":"qdrant/qdrant:v1.19.2","ports":[{"target":6333,"host_ip":"127.0.0.1"}],"volumes":[]}}}'
    exit 0
fi
exit 1
EOF
chmod 755 "$fake_bin/docker"
export PATH="$fake_bin:$PATH"

git -C "$fixture" init -q
git -C "$fixture" config user.email security-smoke@example.invalid
git -C "$fixture" config user.name "Security Smoke Test"
git -C "$fixture" add .
git -C "$fixture" commit -qm "chore(test): initialize security fixture"

expect_failure() {
    label=$1
    shift
    if "$@" >"$TEMP_ROOT/output" 2>&1; then
        printf 'ERROR: Security smoke test unexpectedly passed: %s\n' "$label" >&2
        exit 1
    fi
    printf 'PASS: Security smoke test rejected %s\n' "$label"
}

if (cd "$fixture" && make security-check) >"$TEMP_ROOT/output" 2>&1; then
    printf 'PASS: clean security fixture\n'
else
    cat "$TEMP_ROOT/output" >&2
    exit 1
fi

printf 'TYPESAFE_API_KEY=placeholder-only\n' > "$fixture/.env"
git -C "$fixture" add .env
expect_failure 'tracked .env file' sh -c "cd '$fixture' && make security-check"
git -C "$fixture" reset -q -- .env
rm "$fixture/.env"

printf 'const key = process.env.TYPESAFE_API_KEY;\n' > "$fixture/apps/web/src/leak.ts"
expect_failure 'frontend secret access' sh -c "cd '$fixture' && make security-check"
rm "$fixture/apps/web/src/leak.ts"

printf 'const apiKey = "%s%s";\n' \
    'dGhpcy1pcy1hLXRlc3Qta2V5LXdoaWNoLWlz' '-bm90LXJlYWw=' \
    > "$fixture/apps/web/src/credential.ts"
git -C "$fixture" add apps/web/src/credential.ts
expect_failure 'synthetic credential in source' sh -c "cd '$fixture' && make security-check"
rm "$fixture/apps/web/src/credential.ts"

printf '%s\n' '{"services":{"qdrant":{"image":"qdrant/qdrant:v1.19.2","ports":[{"target":6333,"host_ip":"0.0.0.0"}],"volumes":[]}}}' > "$TEMP_ROOT/compose-bad.json"
cat > "$fake_bin/docker" <<EOF
#!/bin/sh
cat "$TEMP_ROOT/compose-bad.json"
EOF
chmod 755 "$fake_bin/docker"
expect_failure 'wildcard Qdrant port binding' sh -c "cd '$fixture' && make security-check"

printf 'PASS: all security negative cases were rejected\n'
