#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
QA_DIR = ROOT / "output" / "analysis_results" / "qa"
REPORT_OUT_TXT = QA_DIR / "e2e_final_acceptance_suite_report.txt"
REPORT_OUT_JSON = QA_DIR / "e2e_final_acceptance_suite_report.json"

SUITE = [
    {
        "name": "core_blindbox",
        "script": "tmp_e2e_blindbox_audit.py",
        "json": QA_DIR / "e2e_blindbox_audit_report.json",
        "kind": "fatal_summary",
    },
    {
        "name": "boundary_blindbox",
        "script": "tmp_e2e_boundary_blindbox_audit.py",
        "json": QA_DIR / "e2e_boundary_blindbox_audit_report.json",
        "kind": "fatal_summary",
    },
    {
        "name": "delivery_blindbox",
        "script": "tmp_e2e_delivery_blindbox_audit.py",
        "json": QA_DIR / "e2e_delivery_blindbox_audit_report.json",
        "kind": "fatal_summary",
    },
    {
        "name": "gold_standard",
        "script": "tmp_e2e_gold_standard_audit.py",
        "json": QA_DIR / "e2e_gold_standard_audit_report.json",
        "kind": "problem_count",
    },
    {
        "name": "fault_injection",
        "script": "tmp_e2e_fault_injection_validation.py",
        "json": QA_DIR / "e2e_fault_injection_validation_report.json",
        "kind": "undetected_count",
    },
    {
        "name": "independent_recompute",
        "script": "tmp_e2e_independent_recompute_audit.py",
        "json": QA_DIR / "e2e_independent_recompute_audit_report.json",
        "kind": "problem_count",
    },
]


def run_item(item: dict) -> dict:
    script_path = ROOT / item["script"]
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    payload = {}
    if item["json"].exists():
        payload = json.loads(item["json"].read_text(encoding="utf-8"))

    if item["kind"] == "fatal_summary":
        failed = proc.returncode != 0 or int(payload.get("summary", {}).get("fatal_count", 0)) > 0
        summary_value = int(payload.get("summary", {}).get("fatal_count", 0))
    elif item["kind"] == "problem_count":
        failed = proc.returncode != 0 or int(payload.get("problem_count", 0)) > 0
        summary_value = int(payload.get("problem_count", 0))
    elif item["kind"] == "undetected_count":
        failed = proc.returncode != 0 or int(payload.get("undetected_count", 0)) > 0
        summary_value = int(payload.get("undetected_count", 0))
    else:
        failed = proc.returncode != 0
        summary_value = None

    return {
        "name": item["name"],
        "script": item["script"],
        "returncode": proc.returncode,
        "failed": failed,
        "summary_value": summary_value,
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-20:]),
    }


def build_text_report(payload: dict) -> str:
    lines = [
        "======================================================================",
        "E2E最终验收总报告",
        "======================================================================",
        f"共执行 {payload['summary']['total_checks']} 项检查，失败 {payload['summary']['failed_checks']} 项。",
        "",
    ]
    for item in payload["results"]:
        status = "通过" if not item["failed"] else "失败"
        lines.append(f"- {item['name']}: {status} | script={item['script']} | summary={item['summary_value']}")
    lines.append("")
    lines.append(payload["summary"]["verdict"])
    return "\n".join(lines)


def main() -> None:
    results = [run_item(item) for item in SUITE]
    failed_checks = sum(1 for item in results if item["failed"])
    payload = {
        "results": results,
        "summary": {
            "total_checks": len(results),
            "failed_checks": failed_checks,
            "verdict": (
                "最终验收全绿：核心账、语义层、交付层、金标准、故障注入、异实现复算全部通过。"
                if failed_checks == 0
                else "最终验收未通过：仍有检查项失败，当前不建议直接交付。"
            ),
        },
    }
    REPORT_OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    text = build_text_report(payload)
    REPORT_OUT_TXT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
