# Shared POSIX shell helpers. Callers set REPO_ROOT before sourcing this file.

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

require_file() {
    [ -f "$REPO_ROOT/$1" ] || fail "Missing $1. Complete $2 first."
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Missing $1. $2"
}

load_versions() {
    EXPECTED_NODE=$(cat "$REPO_ROOT/.node-version")
    EXPECTED_PNPM=$(sed -n 's/.*"packageManager": "pnpm@\([^"]*\)".*/\1/p' "$REPO_ROOT/package.json")
    EXPECTED_PYTHON=3.14.8
    if [ -f "$REPO_ROOT/apps/api/.python-version" ]; then
        EXPECTED_PYTHON=$(cat "$REPO_ROOT/apps/api/.python-version")
    fi
    [ -n "$EXPECTED_NODE" ] && [ -n "$EXPECTED_PNPM" ] || fail 'Missing runtime version pins.'
}

check_node_pnpm() {
    require_command node 'Use a user-level Node.js version manager and .node-version.'
    NODE_VERSION=$(node --version) || fail 'Cannot read Node.js version.'
    [ "$NODE_VERSION" = "v$EXPECTED_NODE" ] || fail "Node.js $EXPECTED_NODE required, found $NODE_VERSION. Select .node-version with your version manager."
    require_command pnpm 'Use the pinned pnpm version with Corepack or a user-level pnpm installation.'
    # Bypass automatic manager resolution, including pnpm 12 boot-lock writes.
    PNPM_VERSION=$(
        COREPACK_ENABLE_NETWORK=0 COREPACK_ENABLE_AUTO_PIN=0 COREPACK_ENABLE_PROJECT_SPEC=0 \
        pnpm_config_pm_on_fail=ignore npm_config_manage_package_manager_versions=false pnpm --version
    ) || fail 'Cannot read pnpm version without network access. Provision the pinned version explicitly.'
    [ "$PNPM_VERSION" = "$EXPECTED_PNPM" ] || fail "pnpm $EXPECTED_PNPM required, found $PNPM_VERSION. Provision the pinned version explicitly."
}
