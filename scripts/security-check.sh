#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH='' cd "$(dirname "$0")/.." && pwd -P)
GITLEAKS="$REPO_ROOT/.tools/gitleaks"

if [ ! -x "$GITLEAKS" ]; then
    printf 'ERROR: Project-local Gitleaks is missing. Run make security-setup first.\n' >&2
    exit 1
fi
installed_version=$("$GITLEAKS" version 2>/dev/null | sed -n '1p')
if [ "$installed_version" != "8.30.1" ]; then
    printf 'ERROR: Gitleaks 8.30.1 is required, found %s.\n' "$installed_version" >&2
    exit 1
fi

python3 - "$REPO_ROOT" <<'PY'
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
tracked = subprocess.run(
    ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
    check=True,
    stdout=subprocess.PIPE,
).stdout.split(b"\0")
allowed_templates = {".env.example", ".env.sample", ".env.template"}
private_key_extensions = {".pem", ".p12", ".pfx", ".key"}
for raw_path in tracked:
    if not raw_path:
        continue
    path = Path(raw_path.decode("utf-8", errors="strict"))
    name = path.name
    is_env_file = name == ".env" or name.startswith(".env.")
    is_allowed_template = (
        name in allowed_templates
        or name.startswith(".env.")
        and name.rsplit(".", 1)[-1] in {"example", "sample", "template"}
    )
    if is_env_file and not is_allowed_template:
        raise SystemExit(f"ERROR: Tracked local environment file: {path}")
    if path.suffix.lower() in private_key_extensions or name in {"id_rsa", "id_ed25519"}:
        raise SystemExit(f"ERROR: Tracked private-key file: {path}")
    if name in {"credentials.json", "service-account.json"}:
        raise SystemExit(f"ERROR: Tracked credential file: {path}")

frontend = root / "apps/web"
for path in frontend.rglob("*"):
    if not path.is_file() or path.suffix not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        continue
    if any(part in {"node_modules", ".next", "coverage"} for part in path.parts):
        continue
    source = path.read_text(encoding="utf-8")
    if "TYPESAFE_API_KEY" in source:
        raise SystemExit(f"ERROR: TypeSafe credential reference in frontend source: {path.relative_to(root)}")

next_configs = [*frontend.glob("next.config.*")]
for path in next_configs:
    source = path.read_text(encoding="utf-8")
    if "TYPESAFE_API_KEY" in source or "BACKEND_API_URL" in source:
        raise SystemExit(f"ERROR: Private configuration is exposed by Next.js config: {path.relative_to(root)}")
    if __import__("re").search(r"\benv\s*:", source):
        raise SystemExit(f"ERROR: Do not expose values using next.config env: {path.relative_to(root)}")

server_config = frontend / "src/lib/config/server.ts"
if not server_config.is_file() or 'import "server-only"' not in server_config.read_text(encoding="utf-8"):
    raise SystemExit("ERROR: Backend URL configuration must use the server-only boundary.")

browser_artifacts = frontend / ".next/static"
if browser_artifacts.is_dir():
    for path in browser_artifacts.rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            if b"TYPESAFE_API_KEY" in content or b"BACKEND_API_URL" in content:
                raise SystemExit(f"ERROR: Server configuration name found in browser artifact: {path.relative_to(root)}")

print("PASS: tracked-file and frontend secret boundaries")
PY

compose_context=${JEV_RAG_DOCKER_CONTEXT:-desktop-linux}
compose_json=$(docker --context "$compose_context" compose \
    --env-file "$REPO_ROOT/.env.example" \
    -f "$REPO_ROOT/infra/compose.yaml" config --format json)
printf '%s' "$compose_json" | python3 -c '
import json
import sys

config = json.load(sys.stdin)
service = config.get("services", {}).get("qdrant")
if service is None:
    raise SystemExit("ERROR: Qdrant Compose service is missing")
image = service.get("image", "")
if not image.startswith("qdrant/qdrant:") or image.endswith(":latest"):
    raise SystemExit("ERROR: Qdrant image must use a pinned version")
if service.get("privileged") is True:
    raise SystemExit("ERROR: Qdrant must not run privileged")
ports = service.get("ports", [])
if len(ports) != 1 or ports[0].get("target") != 6333 or ports[0].get("host_ip") != "127.0.0.1":
    raise SystemExit("ERROR: Qdrant must publish only REST on 127.0.0.1")
if any("docker.sock" in volume.get("source", "") for volume in service.get("volumes", [])):
    raise SystemExit("ERROR: Docker socket must not be mounted into Qdrant")
print("PASS: Qdrant image, localhost-only REST port, and container privileges")
'

"$GITLEAKS" git --no-banner --redact --log-level error --config "$REPO_ROOT/.gitleaks.toml" "$REPO_ROOT"
working_tree_paths=$(mktemp "${TMPDIR:-/tmp}/jev-rag-security-paths.XXXXXX")
trap 'rm -f "$working_tree_paths"' EXIT HUP INT TERM
git -C "$REPO_ROOT" ls-files -z --cached --others --exclude-standard \
    | python3 -c 'import sys; sys.stdout.buffer.write(b"\n".join(p for p in sys.stdin.buffer.read().split(b"\0") if p))' \
    > "$working_tree_paths"
while IFS= read -r relative_path; do
    [ -n "$relative_path" ] || continue
    case "$relative_path" in
        .env|.env.*)
            case "$relative_path" in
                .env.example|.env.sample|.env.template|.env.*.example|.env.*.sample|.env.*.template) ;;
                *) continue ;;
            esac
            ;;
    esac
    case "$relative_path" in
        .tools/*|.cache/*|.venv/*|*/node_modules/*|*/.next/*|*/coverage/*) continue ;;
    esac
    case "$relative_path" in
        .github/*|apps/api/*|apps/web/*|docs/*|infra/*|scripts/*|AGENTS.md|.editorconfig|.env.example|.gitattributes|.gitignore|.gitleaks.toml|Makefile|README.md|package.json|pnpm-lock.yaml|pnpm-workspace.yaml) ;;
        *) continue ;;
    esac
    "$GITLEAKS" dir --no-banner --redact --log-level error --config "$REPO_ROOT/.gitleaks.toml" \
        "$REPO_ROOT/$relative_path"
done < "$working_tree_paths"
rm -f "$working_tree_paths"
printf 'PASS: Gitleaks 8.30.1 history and working-tree scans\n'
