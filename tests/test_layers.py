"""Enforces ARCHITECTURE.md §3: imports only point down the layer stack."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "roleedge"

LAYER = {  # higher number = higher layer
    "config": 0, "models": 0,
    "llm": 1,
    "content": 2, "connectors": 2, "guard": 2, "scam": 2, "checkin": 2, "render": 2, "trends": 2, "gates": 2, "compose": 2, "replies": 2, "avatar": 2,
    "demo": 3, "samples": 3, "costs": 3, "mock": 3, "families": 3, "store": 3, "studio": 3, "errands": 3,
    "chat": 4, "cli": 4, "guard_cli": 4, "app": 4,
    "lab": 5, "__main__": 5, "__init__": 5,
}
EXTRA_FORBIDDEN = {("render", "llm")}  # rendering never calls a model (rule A3)


def top_level(module_path: Path) -> str:
    return module_path.relative_to(PACKAGE).parts[0].removesuffix(".py")


def imported_packages(path: Path) -> set[str]:
    """roleedge sub-packages imported by a module (relative imports resolved)."""
    depth_of_file = len(path.relative_to(PACKAGE).parts) - 1  # 0 for roleedge/x.py, 1 for roleedge/pkg/x.py
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level:
            up = node.level - 1  # how many packages above the module's own package
            if up > depth_of_file:
                continue
            if up == depth_of_file:  # resolved to roleedge/ itself
                names = [node.module.split(".")[0]] if node.module else [a.name for a in node.names]
                found.update(names)
            else:  # stays inside the module's own top-level package
                found.add(path.relative_to(PACKAGE).parts[0])
    return found


def test_imports_point_down():
    violations = []
    for path in PACKAGE.rglob("*.py"):
        me = top_level(path)
        for dep in imported_packages(path) - {me}:
            if dep not in LAYER:
                continue
            if LAYER[dep] >= LAYER[me] or (me, dep) in EXTRA_FORBIDDEN:
                violations.append(f"{path.relative_to(PACKAGE)} imports {dep}")
    assert not violations, "layer violations:\n" + "\n".join(violations)


def test_every_top_level_module_has_a_layer():
    names = {p.name.removesuffix(".py") for p in PACKAGE.iterdir() if p.suffix == ".py" or (p / "__init__.py").exists()}
    assert names <= set(LAYER), f"add to LAYER: {names - set(LAYER)}"
