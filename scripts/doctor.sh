#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH='' cd "$(dirname "$0")/.." && pwd -P)
. "$REPO_ROOT/scripts/lib/common.sh"
load_versions
doctor_failed=0

report_missing() {
    printf 'ERROR: %s\n' "$*" >&2
    doctor_failed=1
}

check_tool() {
    tool_name=$1
    tool_hint=$2
    shift 2
    if command -v "$tool_name" >/dev/null 2>&1; then
        if tool_output=$("$@" 2>&1); then
            printf 'OK: %s\n' "$(printf '%s\n' "$tool_output" | sed -n '1p')"
        else
            report_missing "$tool_name is not usable. $tool_hint"
        fi
    else
        report_missing "Missing $tool_name. $tool_hint"
    fi
}

check_tool git 'Install Git for your platform.' git --version
if command -v make >/dev/null 2>&1; then
    if make_version=$(make --version 2>/dev/null); then
        printf 'OK: %s\n' "$(printf '%s\n' "$make_version" | sed -n '1p')"
    elif make_version=$(make -V MAKE_VERSION 2>/dev/null) && [ -n "$make_version" ]; then
        printf 'OK: BSD make %s\n' "$make_version"
    else
        report_missing 'Cannot determine Make version. Use GNU Make or BSD make.'
    fi
else
    report_missing 'Missing make. Install GNU Make or BSD make for your platform.'
fi
check_tool uv 'Install uv: https://docs.astral.sh/uv/getting-started/installation/' uv --version

if command -v uv >/dev/null 2>&1; then
    if python_version=$(uv python find --offline --no-cache --no-config --no-project --managed-python --no-python-downloads --show-version "$EXPECTED_PYTHON" 2>/dev/null); then
        if [ "$python_version" = "$EXPECTED_PYTHON" ]; then
            printf 'OK: uv-managed Python %s\n' "$python_version"
        else
            report_missing "Python $EXPECTED_PYTHON required, found $python_version. Select the pinned uv-managed interpreter."
        fi
    else
        report_missing "uv-managed Python $EXPECTED_PYTHON is not installed. Provision it explicitly with uv python install $EXPECTED_PYTHON when available (FND-008)."
    fi
fi

if (check_node_pnpm); then
    printf 'OK: Node.js %s and pnpm %s\n' "$EXPECTED_NODE" "$EXPECTED_PNPM"
else
    doctor_failed=1
fi

if command -v corepack >/dev/null 2>&1; then
    check_tool corepack 'Check your user-level Corepack installation.' corepack --version
else
    printf 'INFO: Corepack is not installed. An existing pinned pnpm installation is sufficient.\n'
fi

check_tool docker 'Install Docker with the Compose plugin. No daemon access is needed by doctor.' docker --version
if command -v docker >/dev/null 2>&1; then
    if compose_version=$(docker compose version 2>/dev/null); then
        printf 'OK: %s\n' "$compose_version"
    else
        report_missing 'Docker Compose is unavailable. Install the Compose plugin.'
    fi
fi

if [ "$doctor_failed" -ne 0 ]; then
    printf 'Environment checks failed. No tools were installed or updated.\n' >&2
    exit 1
fi
printf 'Environment tool checks passed. Application and infrastructure readiness is not checked.\n'
