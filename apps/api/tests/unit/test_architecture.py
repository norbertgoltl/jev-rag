import ast
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "jev_rag_api"
PACKAGE = "jev_rag_api"

# Layer -> top-level modules it must not import. The composition root (main.py) is exempt.
FORBIDDEN_IMPORTS = {
    "domain": {"fastapi", "starlette", "httpx", f"{PACKAGE}.api", f"{PACKAGE}.integrations"},
    "application": {"fastapi", "starlette", "httpx", f"{PACKAGE}.api", f"{PACKAGE}.integrations"},
    "core": {"fastapi", f"{PACKAGE}.api", f"{PACKAGE}.integrations"},
    "integrations": {"fastapi", "starlette", f"{PACKAGE}.api"},
}


def imported_modules(source: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text())):
        if isinstance(node, ast.Import):
            modules.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def is_forbidden(module: str, forbidden: set[str]) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in forbidden)


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_IMPORTS))
def test_layer_does_not_import_outer_layers(layer: str) -> None:
    violations = [
        f"{source.relative_to(SOURCE_ROOT)} imports {module}"
        for source in (SOURCE_ROOT / layer).rglob("*.py")
        for module in imported_modules(source)
        if is_forbidden(module, FORBIDDEN_IMPORTS[layer])
    ]
    assert violations == []
