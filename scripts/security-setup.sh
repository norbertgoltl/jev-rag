#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH='' cd "$(dirname "$0")/.." && pwd -P)
TOOLS_DIR="$REPO_ROOT/.tools"
GITLEAKS="$TOOLS_DIR/gitleaks"
VERSION=8.30.1

if [ -x "$GITLEAKS" ]; then
    installed_version=$("$GITLEAKS" version 2>/dev/null | sed -n '1p')
    if [ "$installed_version" = "$VERSION" ]; then
        printf 'Gitleaks %s is already installed.\n' "$VERSION"
        exit 0
    fi
    printf 'ERROR: Found Gitleaks %s, expected %s. Remove .tools/gitleaks before reinstalling.\n' \
        "$installed_version" "$VERSION" >&2
    exit 1
fi

os=$(uname -s)
architecture=$(uname -m)
case "$os:$architecture" in
    Darwin:arm64|Darwin:aarch64)
        asset="gitleaks_${VERSION}_darwin_arm64.tar.gz"
        checksum=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5
        ;;
    Darwin:x86_64)
        asset="gitleaks_${VERSION}_darwin_x64.tar.gz"
        checksum=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709
        ;;
    Linux:x86_64|Linux:amd64)
        asset="gitleaks_${VERSION}_linux_x64.tar.gz"
        checksum=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
        ;;
    Linux:aarch64|Linux:arm64)
        asset="gitleaks_${VERSION}_linux_arm64.tar.gz"
        checksum=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080
        ;;
    *)
        printf 'ERROR: Gitleaks %s does not support this setup script platform: %s %s\n' \
            "$VERSION" "$os" "$architecture" >&2
        exit 1
        ;;
esac

command -v curl >/dev/null 2>&1 || {
    printf 'ERROR: curl is required to install the project-local Gitleaks scanner.\n' >&2
    exit 1
}
command -v python3 >/dev/null 2>&1 || {
    printf 'ERROR: python3 is required to verify the Gitleaks archive checksum.\n' >&2
    exit 1
}

mkdir -p "$TOOLS_DIR"
temporary_dir=$(mktemp -d "$TOOLS_DIR/gitleaks-install.XXXXXX")
trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM
archive="$temporary_dir/$asset"
url="https://github.com/gitleaks/gitleaks/releases/download/v${VERSION}/${asset}"

curl --fail --location --silent --show-error "$url" --output "$archive"
python3 - "$archive" "$checksum" <<'PY'
import hashlib
from pathlib import Path
import sys

archive = Path(sys.argv[1])
expected = sys.argv[2]
actual = hashlib.sha256(archive.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit(f"ERROR: Gitleaks archive checksum mismatch: {actual}")
PY

tar -xzf "$archive" -C "$temporary_dir" gitleaks
installed_version=$("$temporary_dir/gitleaks" version 2>/dev/null | sed -n '1p')
[ "$installed_version" = "$VERSION" ] || {
    printf 'ERROR: Downloaded Gitleaks version %s, expected %s.\n' "$installed_version" "$VERSION" >&2
    exit 1
}
mv "$temporary_dir/gitleaks" "$GITLEAKS"
chmod 755 "$GITLEAKS"
printf 'Installed project-local Gitleaks %s.\n' "$VERSION"
