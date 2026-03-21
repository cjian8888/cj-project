#!/usr/bin/env python3
from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import tmp_e2e_blindbox_audit as base


ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "output"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "blindbox_gold_standard.json"
REPORT_JSON = OUTPUT_ROOT / "analysis_results" / "qa" / "report_package.json"
REPORT_TXT = OUTPUT_ROOT / "analysis_results" / "核查结果分析报告.txt"
REPORT_OUT_TXT = (
    OUTPUT_ROOT / "analysis_results" / "qa" / "e2e_gold_standard_audit_report.txt"
)
REPORT_OUT_JSON = (
    OUTPUT_ROOT / "analysis_results" / "qa" / "e2e_gold_standard_audit_report.json"
)


def money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    text = str(value).strip().replace(",", "")
    if not text:
        return Decimal("0.00")
    return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fmt_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit() -> dict[str, Any]:
    fixture = _load_json(FIXTURE_PATH)
    report = _load_json(REPORT_JSON)
    report_text = REPORT_TXT.read_text(encoding="utf-8")
    report_text_metrics = base.parse_report_text_metrics(report_text)
    all_rows, rows_by_file, entity_stats = base.load_bank_rows()

    problems: list[dict[str, Any]] = []

    coverage_checks = {
        "bank_transaction_count": int(report["coverage"]["bank_transaction_count"]),
        "persons_count": int(report["coverage"]["persons_count"]),
        "companies_count": int(report["coverage"]["companies_count"]),
        "wallet_subject_count": int(report["coverage"]["wallet_subject_count"]),
        "alipay_trade_count": int(report_text_metrics.get("alipay_trade_count", 0)),
        "tenpay_trade_count": int(report_text_metrics.get("tenpay_trade_count", 0)),
        "wx_login_count": int(report_text_metrics.get("wx_login_count", 0)),
        "direct_transfer_count": int(report_text_metrics.get("direct_transfer_count", 0)),
    }
    for key, expected_value in fixture["coverage"].items():
        actual_value = coverage_checks.get(key)
        if int(actual_value or 0) != int(expected_value):
            problems.append(
                {
                    "kind": "coverage_mismatch",
                    "metric": key,
                    "expected_value": int(expected_value),
                    "actual_value": int(actual_value or 0),
                }
            )

    dossier_lookup = {
        item["entity_name"]: item
        for item in report.get("person_dossiers", []) + report.get("company_dossiers", [])
    }
    for sample in fixture["entity_samples"]:
        entity_name = sample["entity_name"]
        dossier = dossier_lookup.get(entity_name)
        raw_stats = entity_stats.get(entity_name)
        if not dossier or not raw_stats:
            problems.append(
                {
                    "kind": "missing_entity_sample",
                    "entity_name": entity_name,
                    "has_dossier": bool(dossier),
                    "has_raw_stats": bool(raw_stats),
                }
            )
            continue

        expected_tx_count = int(sample["transaction_count"])
        expected_income = money(sample["total_income"])
        expected_expense = money(sample["total_expense"])
        actual_dossier_income = money(dossier.get("total_income"))
        actual_dossier_expense = money(dossier.get("total_expense"))
        actual_raw_income = money(raw_stats.get("total_income"))
        actual_raw_expense = money(raw_stats.get("total_expense"))
        actual_dossier_tx_count = int(dossier.get("transaction_count") or 0)
        actual_raw_tx_count = int(raw_stats.get("transaction_count") or 0)

        if (
            actual_dossier_tx_count != expected_tx_count
            or actual_raw_tx_count != expected_tx_count
            or actual_dossier_income != expected_income
            or actual_raw_income != expected_income
            or actual_dossier_expense != expected_expense
            or actual_raw_expense != expected_expense
        ):
            problems.append(
                {
                    "kind": "entity_sample_mismatch",
                    "entity_name": entity_name,
                    "expected": {
                        "transaction_count": expected_tx_count,
                        "total_income": str(expected_income),
                        "total_expense": str(expected_expense),
                    },
                    "dossier": {
                        "transaction_count": actual_dossier_tx_count,
                        "total_income": str(actual_dossier_income),
                        "total_expense": str(actual_dossier_expense),
                    },
                    "raw": {
                        "transaction_count": actual_raw_tx_count,
                        "total_income": str(actual_raw_income),
                        "total_expense": str(actual_raw_expense),
                    },
                }
            )

    for tx in fixture["key_transactions"]:
        candidates = rows_by_file.get(tx["source_file"], [])
        matched = None
        for row in candidates:
            if (
                row.excel_row_num == int(tx["excel_row_num"])
                and row.entity_name == tx["entity_name"]
                and row.direction == tx["direction"]
                and money(row.amount) == money(tx["amount"])
                and (
                    row.transaction_time.isoformat(sep=" ")
                    if row.transaction_time is not None
                    else ""
                )
                == tx["transaction_time"]
                and row.counterparty_name == tx["counterparty_name"]
                and row.transaction_id == tx["transaction_id"]
            ):
                matched = row
                break
        if matched is None:
            problems.append(
                {
                    "kind": "key_transaction_missing",
                    "expected": tx,
                }
            )

    issue_headlines = {
        str(item.get("headline") or "").strip() for item in report.get("issues", [])
    }
    for headline in fixture.get("key_issue_headlines", []):
        if headline not in issue_headlines:
            problems.append(
                {
                    "kind": "key_issue_missing",
                    "headline": headline,
                }
            )

    return {
        "gold_standard_path": fmt_path(FIXTURE_PATH),
        "checked_entity_samples": len(fixture["entity_samples"]),
        "checked_key_transactions": len(fixture["key_transactions"]),
        "checked_issue_headlines": len(fixture.get("key_issue_headlines", [])),
        "problem_count": len(problems),
        "problems": problems,
        "verdict": (
            "金标准样本中的核心事实与当前正式产物、原始流水保持一致。"
            if not problems
            else "金标准样本与当前产物存在不一致，正式结果还不能视为完全稳定。"
        ),
    }


def build_text_report(payload: dict[str, Any]) -> str:
    lines = [
        "======================================================================",
        "金标准样本审计报告",
        "======================================================================",
        f"金标准文件: {payload['gold_standard_path']}",
        f"已核对对象样本 {payload['checked_entity_samples']} 个，关键交易 {payload['checked_key_transactions']} 条，问题卡标题 {payload['checked_issue_headlines']} 条。",
        f"发现问题 {payload['problem_count']} 项。",
    ]
    if payload["problems"]:
        lines.append("")
        lines.append("问题明细:")
        for item in payload["problems"]:
            lines.append(f"- {item['kind']}: {json.dumps(item, ensure_ascii=False)}")
    lines.append("")
    lines.append(payload["verdict"])
    return "\n".join(lines)


def main() -> None:
    payload = audit()
    REPORT_OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    text = build_text_report(payload)
    REPORT_OUT_TXT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
