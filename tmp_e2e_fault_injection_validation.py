#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import tmp_e2e_blindbox_audit as core
import tmp_e2e_boundary_blindbox_audit as boundary
import tmp_e2e_delivery_blindbox_audit as delivery


ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "output"
REPORT_OUT_TXT = (
    OUTPUT_ROOT / "analysis_results" / "qa" / "e2e_fault_injection_validation_report.txt"
)
REPORT_OUT_JSON = (
    OUTPUT_ROOT / "analysis_results" / "qa" / "e2e_fault_injection_validation_report.json"
)


def _replace_first(pattern: str, repl: str, text: str) -> str:
    return re.sub(pattern, repl, text, count=1)


def run_fault_injections() -> dict[str, Any]:
    report, report_text, suspicions = core.load_report_artifacts()
    report_text_metrics = core.parse_report_text_metrics(report_text)
    all_rows, rows_by_file, entity_stats = core.load_bank_rows()
    wallet_metrics = core.load_wallet_metrics()
    report_entity_stats = core.make_report_entity_stats(report)
    derived_data = boundary._load_json(boundary.DERIVED_JSON)
    profiles = boundary._load_json(boundary.PROFILES_JSON)

    scenarios: list[dict[str, Any]] = []

    mutated_report = copy.deepcopy(report)
    mutated_report["coverage"]["bank_transaction_count"] = int(
        mutated_report["coverage"]["bank_transaction_count"]
    ) + 7
    _, mismatches, _ = core.compare_core_metrics(
        mutated_report,
        report_text_metrics,
        entity_stats,
        wallet_metrics,
        core.make_report_entity_stats(mutated_report),
    )
    scenarios.append(
        {
            "scenario": "core_coverage_count_drift",
            "expected_failure": True,
            "detected": any(item["metric"] == "银行流水总笔数" for item in mismatches),
            "details": mismatches[:5],
        }
    )

    mutated_report = copy.deepcopy(report)
    mutated_report["person_dossiers"][0]["transaction_count"] = int(
        mutated_report["person_dossiers"][0]["transaction_count"]
    ) + 1
    _, _, context = core.compare_core_metrics(
        mutated_report,
        report_text_metrics,
        entity_stats,
        wallet_metrics,
        core.make_report_entity_stats(mutated_report),
    )
    scenarios.append(
        {
            "scenario": "entity_rollup_drift",
            "expected_failure": True,
            "detected": bool(context["entity_mismatches"]),
            "details": context["entity_mismatches"][:3],
        }
    )

    mutated_report = copy.deepcopy(report)
    mutated_report["main_report_view"]["issues"][0]["evidence_refs"] = [
        "不存在的文件.xlsx（解析记录第999行）",
        "交易标识 DOES-NOT-EXIST",
    ]
    issue_audit = core.audit_report_issues(mutated_report, rows_by_file)
    scenarios.append(
        {
            "scenario": "issue_evidence_drift",
            "expected_failure": True,
            "detected": issue_audit["failed_count"] > 0,
            "details": issue_audit["failed_details"][:3],
        }
    )

    mutated_report = copy.deepcopy(report)
    mutated_report["priority_board"][0]["issue_refs"] = list(
        mutated_report["priority_board"][0].get("issue_refs", [])
    ) + ["FAKE-TEST-001"]
    semantic_audit = boundary.audit_semantic_consistency(
        mutated_report,
        derived_data,
        profiles,
    )
    scenarios.append(
        {
            "scenario": "semantic_priority_link_drift",
            "expected_failure": True,
            "detected": semantic_audit["problem_count"] > 0,
            "details": semantic_audit["problems"][:3],
        }
    )

    mutated_text = _replace_first(
        r"发现\s+\d+\s+条直接往来记录",
        "发现 999 条直接往来记录",
        report_text,
    )
    text_audit = boundary.audit_report_text_alignment(
        report,
        mutated_text,
        suspicions,
        derived_data,
    )
    scenarios.append(
        {
            "scenario": "formal_txt_headline_drift",
            "expected_failure": True,
            "detected": text_audit["problem_count"] > 0,
            "details": text_audit["problems"][:3],
        }
    )

    mutated_report = copy.deepcopy(report)
    mutated_report["priority_board"][0]["entity_name"] = "测试假对象"
    excel_audit = delivery.audit_excel_alignment(mutated_report, report_text, suspicions)
    scenarios.append(
        {
            "scenario": "excel_priority_board_drift",
            "expected_failure": True,
            "detected": excel_audit["problem_count"] > 0,
            "details": excel_audit["problems"][:3],
        }
    )

    undetected = [item for item in scenarios if item["expected_failure"] and not item["detected"]]
    return {
        "scenario_count": len(scenarios),
        "undetected_count": len(undetected),
        "scenarios": scenarios,
        "verdict": (
            "故障注入场景全部被盲盒脚本成功打红，测试本身具备基本杀伤力。"
            if not undetected
            else "仍有故障注入场景未被盲盒识别，测试本身还不够硬。"
        ),
    }


def build_text_report(payload: dict[str, Any]) -> str:
    lines = [
        "======================================================================",
        "盲盒故障注入验证报告",
        "======================================================================",
        f"共执行 {payload['scenario_count']} 个故障注入场景，漏检 {payload['undetected_count']} 个。",
        "",
    ]
    for item in payload["scenarios"]:
        lines.append(
            f"- {item['scenario']}: {'已命中' if item['detected'] else '漏检'}"
        )
        if item["details"]:
            lines.append(f"  详情: {json.dumps(item['details'], ensure_ascii=False)}")
    lines.append("")
    lines.append(payload["verdict"])
    return "\n".join(lines)


def main() -> None:
    payload = run_fault_injections()
    REPORT_OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    text = build_text_report(payload)
    REPORT_OUT_TXT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
