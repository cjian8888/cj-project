#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 7+/Python 3.8 启动链兼容性回归测试。"""

from __future__ import annotations

import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PEP585_RE = re.compile(r"\b(?:list|dict|tuple|set|frozenset)\[")
FUTURE_ANNOTATIONS_IMPORT = "from __future__ import annotations"
WINDOWS_PY38_STARTUP_FILES = [
    Path("api_server.py"),
    Path("report_generator.py"),
    Path("investigation_report_builder.py"),
    Path("suspicion_engine.py"),
    Path("related_party_analyzer.py"),
    Path("wallet_risk_analyzer.py"),
    Path("utils/family_relation_utils.py"),
]
TYPING_ALIAS_CHECK_FILES = WINDOWS_PY38_STARTUP_FILES + [
    Path("report_dossier_builder.py"),
]
TYPING_ALIASES = {"Tuple", "Set", "Sequence", "Mapping", "Iterable", "Generator"}


def _read_text(relative_path: Path) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _typing_imports(tree: ast.AST) -> set[str]:
    imports: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            imports.update(alias.name for alias in node.names)
    return imports


def test_windows_py38_startup_modules_defer_pep585_annotations():
    failures: list[str] = []

    for relative_path in WINDOWS_PY38_STARTUP_FILES:
        text = _read_text(relative_path)
        if PEP585_RE.search(text) and FUTURE_ANNOTATIONS_IMPORT not in text:
            failures.append(str(relative_path))

    assert not failures, (
        "以下启动链文件使用了 Python 3.9+ 内建泛型语法，但未启用延迟注解，"
        f"会导致 Windows 7 目标的 Python 3.8 启动失败: {failures}"
    )


def test_pydantic_schemas_avoid_pep585_generics_on_python38():
    failures: list[str] = []

    for schema_path in (PROJECT_ROOT / "schemas").glob("*.py"):
        text = schema_path.read_text(encoding="utf-8")
        if PEP585_RE.search(text):
            failures.append(str(schema_path.relative_to(PROJECT_ROOT)))

    assert not failures, (
        "Pydantic schema 在 Python 3.8 下不能使用 list[...] / dict[...] 这类新语法，"
        f"请改回 typing.List/Dict: {failures}"
    )


def test_windows_startup_files_import_used_typing_aliases():
    failures: list[str] = []

    for relative_path in TYPING_ALIAS_CHECK_FILES:
        py_file = PROJECT_ROOT / relative_path
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        imported_aliases = _typing_imports(tree)
        defined_names = {
            node.name
            for node in getattr(tree, "body", [])
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        used_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

        missing = sorted(
            alias
            for alias in TYPING_ALIASES
            if alias in used_names
            and alias not in imported_aliases
            and alias not in defined_names
        )
        if missing:
            failures.append(f"{relative_path}: {', '.join(missing)}")

    assert not failures, (
        "以下 Windows 启动链文件使用了 typing 别名但未导入，"
        f"会在启动链中触发 NameError: {failures}"
    )
