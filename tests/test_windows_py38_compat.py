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


def _top_level_imports(tree: ast.AST) -> set[str]:
    imports: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
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


def test_api_server_installs_startup_diagnostics_for_fatal_crashes():
    text = _read_text(Path("api_server.py"))

    assert "faulthandler.enable" in text
    assert "_STARTUP_FATAL_LOG_NAME" in text
    assert "FPAS_STARTUP_DIAGNOSTICS_ROOT" in text
    assert "sys.excepthook = _startup_excepthook" in text


def test_windows_build_requirements_pin_win7_safe_cryptography():
    build_text = _read_text(Path("requirements-windows-build.txt"))
    lock_text = _read_text(Path("requirements-windows-lock.txt"))

    assert "cryptography==39.0.2" in build_text
    assert "cryptography==39.0.2" in lock_text


def test_api_server_defers_openpyxl_export_modules_until_needed():
    api_server_path = PROJECT_ROOT / "api_server.py"
    text = api_server_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(api_server_path))
    imports = _top_level_imports(tree)

    assert "asset_extractor" not in imports
    assert "data_extractor" not in imports
    assert "investigation_report_builder" not in imports
    assert "report_config.primary_targets_service" not in imports
    assert "report_quality_guard" not in imports
    assert "report_generator" not in imports
    assert "specialized_reports" not in imports
    assert "suspicion_engine" not in imports
    assert "wallet_report_builder" not in imports
    assert "def _load_asset_extractor():" in text
    assert 'importlib.import_module("asset_extractor")' in text
    assert "def _load_data_extractor():" in text
    assert 'importlib.import_module("data_extractor")' in text
    assert "def _load_investigation_report_builder_module():" in text
    assert 'importlib.import_module("investigation_report_builder")' in text
    assert "def _load_primary_targets_service_module():" in text
    assert 'importlib.import_module("report_config.primary_targets_service")' in text
    assert "def _load_report_quality_guard_module():" in text
    assert 'importlib.import_module("report_quality_guard")' in text
    assert "def _load_report_generator():" in text
    assert 'importlib.import_module("report_generator")' in text
    assert "def _load_specialized_reports_module():" in text
    assert 'importlib.import_module("specialized_reports")' in text
    assert "def _load_suspicion_engine_module():" in text
    assert 'importlib.import_module("suspicion_engine")' in text
    assert "def _load_wallet_report_builder():" in text
    assert 'importlib.import_module("wallet_report_builder")' in text
    assert "_load_asset_extractor().extract_precise_property_info(" in text
    assert "_load_data_extractor().extract_all_clues(" in text
    assert "_load_investigation_report_builder_module().load_investigation_report_builder(" in text
    assert "_load_report_quality_guard_module().REPORT_QA_GUARD_VERSION" in text
    assert "_load_report_generator().generate_excel_workbook(" in text
    assert "_load_wallet_report_builder().generate_wallet_artifacts(" in text
