"""Local Docker Desktop lifecycle and isolated infrastructure acceptance tests."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from urllib.error import URLError
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ["docker", "--context", "desktop-linux"]


def run(*args, capture=False, env=None):
    return subprocess.run(args, cwd=ROOT, env=env, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def environment():
    if not (ROOT / ".env").is_file():
        raise RuntimeError("Missing .env. Copy .env.example to .env first.")
    return {**dotenv_values(ROOT / ".env"), **os.environ}


def compose(*args, env=None, project=None, capture=False):
    command = [*DOCKER, "compose", "--env-file", ".env", "-f", "infra/compose.yaml"]
    if project:
        command += ["-p", project]
    return run(*command, *args, env=env, capture=capture)


def request(url, timeout=1.0, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    with urlopen(Request(url, data=data, method=method, headers={"Content-Type": "application/json"}), timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("HTTP readiness failed")
        return response.read()


def preflight(env):
    run(*DOCKER, "context", "inspect", "desktop-linux", capture=True)
    info = json.loads(run(*DOCKER, "info", "--format", "{{json .}}", capture=True))
    if info["OSType"] != "linux" or info["Architecture"] not in {"aarch64", "arm64"}:
        raise RuntimeError("Docker Desktop Linux ARM64 Engine required")
    if info["NCPU"] < 2 or info["MemTotal"] < 4 * 1024**3:
        raise RuntimeError("Docker Desktop requires at least 2 CPUs and 4 GiB RAM")
    run(*DOCKER, "compose", "version", capture=True)
    config = json.loads(compose("config", "--format", "json", env=env, capture=True))
    port = int(env.get("QDRANT_HOST_PORT", "6333"))
    own = compose("ps", "-q", "qdrant", env=env, capture=True).strip()
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", port))
    except OSError:
        if not own:
            raise RuntimeError(f"Port {port} is occupied by another process") from None
        inspected = json.loads(run(*DOCKER, "inspect", own, capture=True))[0]
        bindings = inspected["NetworkSettings"]["Ports"].get("6333/tcp") or []
        if not any(b["HostIp"] == "127.0.0.1" and b["HostPort"] == str(port) for b in bindings):
            raise RuntimeError("Occupied port does not belong to this Qdrant service") from None
    finally:
        probe.close()
    if config["services"]["qdrant"]["platform"] != "linux/arm64":
        raise RuntimeError("Unexpected Compose platform")
    print("PASS: Docker Desktop Linux ARM64, Compose, resources and host port")


def acceptance(env):
    project = "jev-rag-test-" + uuid.uuid4().hex
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    test_env = {**env, "QDRANT_HOST_PORT": str(port), "COMPOSE_PROJECT_NAME": project,
                "QDRANT_URL": f"http://127.0.0.1:{port}"}
    preflight(test_env)
    url = test_env["QDRANT_URL"]
    before = run("docker", "context", "show", capture=True)
    volume = project + "_qdrant_data"
    print(f"Isolated project: {project}; port: {port}; volume: {volume}", flush=True)
    success = False
    try:
        for _ in range(2):
            compose("up", "-d", "--wait", "--wait-timeout", "90", env=test_env, project=project)
        container = compose("ps", "-q", "qdrant", env=test_env, project=project, capture=True).strip()
        inspected = json.loads(run(*DOCKER, "inspect", container, capture=True))[0]
        published = {key: value for key, value in inspected["NetworkSettings"]["Ports"].items() if value}
        assert published == {"6333/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}
        assert any(m.get("Name") == volume and m["Destination"] == "/qdrant/storage" for m in inspected["Mounts"])
        assert run(*DOCKER, "image", "inspect", inspected["Image"], "--format", "{{.Os}}/{{.Architecture}}", capture=True).strip() == "linux/arm64"
        request(url + "/readyz")
        request(url + "/collections/persistence_test", method="PUT", body={"vectors": {"size": 2, "distance": "Cosine"}})
        request(url + "/collections/persistence_test/points?wait=true", method="PUT", body={"points": [{"id": 1, "vector": [1.0, 0.0], "payload": {"marker": project}}]})
        from fastapi.testclient import TestClient
        from jev_rag_api.core.config import Settings
        from jev_rag_api.main import create_app
        with TestClient(create_app(Settings(_env_file=None, qdrant_url=url))) as api:
            assert api.get("/health/ready").status_code == 200
            compose("down", env=test_env, project=project)
            compose("down", env=test_env, project=project)
            assert api.get("/health/live").status_code == 200
            assert api.get("/health/ready").status_code == 503
            try:
                request(url + "/readyz")
                raise AssertionError("Stopped Qdrant unexpectedly ready")
            except URLError:
                pass
            compose("up", "-d", "--wait", "--wait-timeout", "90", env=test_env, project=project)
            assert api.get("/health/ready").status_code == 200
            point = json.loads(request(url + "/collections/persistence_test/points/1"))
            assert point["result"]["payload"] == {"marker": project}
        assert run("docker", "context", "show", capture=True) == before
        success = True
        print("PASS: startup, ARM64, loopback ports, persistence, readiness recovery, idempotency and context safety")
    finally:
        if success:
            compose("down", env=test_env, project=project)
            labels = json.loads(run(*DOCKER, "volume", "inspect", volume, capture=True))[0]["Labels"]
            if labels.get("com.docker.compose.project") != project or not project.startswith("jev-rag-test-"):
                raise RuntimeError("Refusing to remove an unverified test volume")
            run(*DOCKER, "volume", "rm", volume)
        else:
            print(f"Test resources preserved for diagnosis: {project}; see infrastructure runbook", file=sys.stderr)


def main():
    action = sys.argv[1]
    env = environment()
    if action == "doctor":
        preflight(env)
    elif action == "infra-test":
        acceptance(env)
    elif action == "health":
        request(env.get("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/") + "/readyz", float(env.get("QDRANT_TIMEOUT_SECONDS", "1.0")))
        print("PASS: Qdrant HTTP readiness")
    else:
        if action == "up":
            preflight(env)
            compose("up", "-d", "--wait", "--wait-timeout", "90", "qdrant", env=env)
        elif action == "down":
            compose("down", env=env)
        elif action == "status":
            compose("ps", "--all", "qdrant", env=env)
        elif action == "logs":
            compose("logs", "--follow", "--tail", "100", "qdrant", env=env)
        else:
            raise RuntimeError("Unknown infrastructure command")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
