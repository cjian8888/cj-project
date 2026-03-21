#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from math import isclose
from pathlib import Path
from typing import Any

import pandas as pd
from starlette.requests import Request

import api_server
import tmp_e2e_blindbox_audit as base


ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "output"
RESULTS_DIR = OUTPUT_ROOT / "analysis_results"
QA_DIR = RESULTS_DIR / "qa"

REPORT_JSON = QA_DIR / "report_package.json"
REPORT_TXT = RESULTS_DIR / "核查结果分析报告.txt"
REPORT_HTML = RESULTS_DIR / "初查报告.html"
REPORT_XLSX = RESULTS_DIR / "资金核查底稿.xlsx"

REPORT_OUT_TXT = QA_DIR / "e2e_delivery_blindbox_audit_report.txt"
REPORT_OUT_JSON = QA_DIR / "e2e_delivery_blindbox_audit_report.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _to_html_text(raw_html: str) -> str:
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw_html, flags=re.I | re.S)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _make_request(method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
        }
    )


def _coerce_json_response(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    body = getattr(result, "body", b"") or b""
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    return json.loads(body or "{}")


def _sheet_metric_lookup(df: pd.DataFrame) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for row in df.to_dict("records"):
        key = str(row.get("指标") or "").strip()
        if key:
            lookup[key] = row.get("值")
    return lookup


def _report_file_list_contains(payload: dict[str, Any], target_name: str) -> bool:
    for item in _as_list(payload.get("reports")):
        if not isinstance(item, dict):
            continue
        for key in ("name", "filename", "path", "relativePath"):
            value = str(item.get(key) or "").strip()
            if value == target_name or value.endswith(f"/{target_name}"):
                return True
    return False


def audit_delivery_chain() -> dict[str, Any]:
    logging.getLogger().setLevel(logging.WARNING)
    for logger_name in (
        "api_server",
        "investigation_report_builder",
        "file_categorizer",
        "data_cleaner",
    ):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    problems: list[dict[str, Any]] = []
    current_config = dict(api_server._current_config)

    try:
        api_server._current_config.clear()
        api_server._current_config.update(
            {
                "inputDirectory": str(ROOT / "data"),
                "outputDirectory": str(OUTPUT_ROOT),
            }
        )

        generated = asyncio.run(api_server.generate_investigation_report_html())
        generated_payload = _coerce_json_response(generated)
        if not generated_payload.get("success") or not generated_payload.get("html"):
            return {
                "problem_count": 1,
                "problems": [
                    {
                        "kind": "generate_html_failed",
                        "details": generated_payload,
                    }
                ],
            }

        html_content = str(generated_payload["html"])
        save_result = asyncio.run(
            api_server.save_html_report(
                {"html": html_content, "filename": REPORT_HTML.name}
            )
        )
        save_payload = _coerce_json_response(save_result)
        if not save_payload.get("success"):
            return {
                "problem_count": 1,
                "problems": [
                    {
                        "kind": "save_html_failed",
                        "details": save_payload,
                    }
                ],
            }

        saved_html = REPORT_HTML.read_text(encoding="utf-8")
        if saved_html != html_content:
            problems.append(
                {
                    "kind": "saved_html_mismatch",
                    "generated_length": len(html_content),
                    "saved_length": len(saved_html),
                }
            )

        live_report_package = _load_json(REPORT_JSON)
        html_text = _to_html_text(saved_html)

        summary_narrative = str(
            _as_dict(live_report_package.get("main_report_view")).get(
                "summary_narrative", ""
            )
        ).strip()
        if summary_narrative and summary_narrative not in html_text:
            problems.append(
                {
                    "kind": "html_missing_summary_narrative",
                    "summary_narrative": summary_narrative,
                }
            )

        missing_issue_headlines = []
        for issue in _as_list(_as_dict(live_report_package.get("main_report_view")).get("issues")):
            headline = str(_as_dict(issue).get("headline") or "").strip()
            if headline and headline not in html_text:
                missing_issue_headlines.append(headline)
        if missing_issue_headlines:
            problems.append(
                {
                    "kind": "html_missing_main_issue_headlines",
                    "count": len(missing_issue_headlines),
                    "details": missing_issue_headlines[:10],
                }
            )

        missing_priority_names = []
        for item in _as_list(live_report_package.get("priority_board"))[:5]:
            entity_name = str(_as_dict(item).get("entity_name") or "").strip()
            if entity_name and entity_name not in html_text:
                missing_priority_names.append(entity_name)
        if missing_priority_names:
            problems.append(
                {
                    "kind": "html_missing_priority_entities",
                    "details": missing_priority_names,
                }
            )

        required_sections = [
            "正式报告综合研判",
            "统一语义层重点对象",
            "重点问题卡",
            "附录C 关系网络与资金穿透",
            "附录E 电子钱包补证",
        ]
        missing_sections = [token for token in required_sections if token not in html_text]
        if missing_sections:
            problems.append(
                {
                    "kind": "html_missing_required_sections",
                    "details": missing_sections,
                }
            )

        preview_html = asyncio.run(
            api_server.preview_report_file(
                REPORT_HTML.name,
                _make_request("GET", f"/api/reports/preview/{REPORT_HTML.name}"),
            )
        )
        preview_html_body = getattr(preview_html, "body", b"") or b""
        if isinstance(preview_html_body, bytes):
            preview_html_body = preview_html_body.decode("utf-8")
        if preview_html_body != saved_html:
            problems.append(
                {
                    "kind": "preview_html_mismatch",
                    "preview_length": len(preview_html_body),
                    "saved_length": len(saved_html),
                }
            )

        live_report_txt = REPORT_TXT.read_text(encoding="utf-8")
        preview_txt = asyncio.run(
            api_server.preview_report_file(
                REPORT_TXT.name,
                _make_request("GET", f"/api/reports/preview/{REPORT_TXT.name}"),
            )
        )
        if (
            not isinstance(preview_txt, dict)
            or preview_txt.get("content") != live_report_txt
            or preview_txt.get("type") != "text"
        ):
            problems.append(
                {
                    "kind": "preview_txt_mismatch",
                    "details": preview_txt if isinstance(preview_txt, dict) else str(type(preview_txt)),
                }
            )

        preview_json = asyncio.run(
            api_server.preview_report_file(
                "qa/report_package.json",
                _make_request("GET", "/api/reports/preview/qa/report_package.json"),
            )
        )
        preview_json_payload = {}
        if isinstance(preview_json, dict):
            preview_json_payload = json.loads(str(preview_json.get("content") or "{}"))
        if preview_json_payload != live_report_package:
            problems.append(
                {
                    "kind": "preview_report_package_mismatch",
                }
            )

        preview_xlsx = asyncio.run(
            api_server.preview_report_file(
                REPORT_XLSX.name,
                _make_request("GET", f"/api/reports/preview/{REPORT_XLSX.name}"),
            )
        )
        expected_download_url = f"/api/reports/download/{REPORT_XLSX.name}"
        if (
            not isinstance(preview_xlsx, dict)
            or preview_xlsx.get("type") != "excel"
            or preview_xlsx.get("download_url") != expected_download_url
        ):
            problems.append(
                {
                    "kind": "preview_xlsx_download_link_mismatch",
                    "details": preview_xlsx if isinstance(preview_xlsx, dict) else str(type(preview_xlsx)),
                }
            )

        for filename in (REPORT_HTML.name, REPORT_XLSX.name, "qa/report_package.json"):
            download_response = asyncio.run(api_server.download_report_file(filename))
            expected_path = str((RESULTS_DIR / filename).resolve()) if not filename.startswith("qa/") else str((QA_DIR / "report_package.json").resolve())
            expected_name = Path(filename).name
            response_path = str(getattr(download_response, "path", ""))
            response_name = str(getattr(download_response, "filename", ""))
            if response_path != expected_path or response_name != expected_name:
                problems.append(
                    {
                        "kind": "download_target_mismatch",
                        "filename": filename,
                        "response_path": response_path,
                        "expected_path": expected_path,
                        "response_name": response_name,
                        "expected_name": expected_name,
                    }
                )

        manifest = asyncio.run(api_server.get_report_manifest())
        if not _report_file_list_contains(_coerce_json_response(manifest), REPORT_HTML.name):
            problems.append(
                {
                    "kind": "manifest_missing_saved_html",
                    "filename": REPORT_HTML.name,
                }
            )

        return {
            "generated_html_length": len(html_content),
            "saved_html_length": len(saved_html),
            "checked_main_issue_count": len(
                _as_list(_as_dict(live_report_package.get("main_report_view")).get("issues"))
            ),
            "checked_priority_count": min(
                5, len(_as_list(live_report_package.get("priority_board")))
            ),
            "problem_count": len(problems),
            "problems": problems,
        }
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(current_config)


def audit_excel_alignment(
    report_package: dict[str, Any],
    report_text: str,
    suspicions: dict[str, Any],
) -> dict[str, Any]:
    problems: list[dict[str, Any]] = []

    workbook = pd.ExcelFile(REPORT_XLSX)
    required_sheets = {
        "资金画像汇总",
        "聚合风险排序",
        "聚合风险重点对象",
        "直接转账关系",
    }
    missing_sheets = sorted(required_sheets - set(workbook.sheet_names))
    if missing_sheets:
        problems.append({"kind": "missing_required_sheets", "details": missing_sheets})
        return {"problem_count": len(problems), "problems": problems}

    profile_df = pd.read_excel(REPORT_XLSX, sheet_name="资金画像汇总")
    priority_summary_df = pd.read_excel(REPORT_XLSX, sheet_name="聚合风险排序")
    priority_detail_df = pd.read_excel(REPORT_XLSX, sheet_name="聚合风险重点对象")
    direct_df = pd.read_excel(REPORT_XLSX, sheet_name="直接转账关系")

    expected_dossiers = {
        str(item.get("entity_name") or "").strip(): item
        for item in (
            _as_list(report_package.get("person_dossiers"))
            + _as_list(report_package.get("company_dossiers"))
        )
        if str(_as_dict(item).get("entity_name") or "").strip()
    }
    profile_names = [str(value).strip() for value in profile_df["对象名称"].tolist()]
    missing_profile_names = sorted(set(expected_dossiers) - set(profile_names))
    extra_profile_names = sorted(set(profile_names) - set(expected_dossiers))
    if len(profile_df) != len(expected_dossiers) or missing_profile_names or extra_profile_names:
        problems.append(
            {
                "kind": "profile_sheet_entity_set_mismatch",
                "sheet_count": len(profile_df),
                "expected_count": len(expected_dossiers),
                "missing_entities": missing_profile_names[:10],
                "extra_entities": extra_profile_names[:10],
            }
        )

    metric_mismatches: list[dict[str, Any]] = []
    for row in profile_df.to_dict("records"):
        entity_name = str(row.get("对象名称") or "").strip()
        dossier = _as_dict(expected_dossiers.get(entity_name))
        if not dossier:
            continue
        expected_income_wan = round(float(dossier.get("total_income", 0) or 0) / 10000, 2)
        expected_expense_wan = round(
            float(dossier.get("total_expense", 0) or 0) / 10000, 2
        )
        if int(row.get("交易笔数") or 0) != int(dossier.get("transaction_count") or 0):
            metric_mismatches.append(
                {
                    "entity_name": entity_name,
                    "field": "transaction_count",
                    "sheet_value": int(row.get("交易笔数") or 0),
                    "expected_value": int(dossier.get("transaction_count") or 0),
                }
            )
        if not isclose(
            float(row.get("资金流入总额(万元)") or 0.0),
            expected_income_wan,
            abs_tol=0.01,
        ):
            metric_mismatches.append(
                {
                    "entity_name": entity_name,
                    "field": "total_income_wan",
                    "sheet_value": float(row.get("资金流入总额(万元)") or 0.0),
                    "expected_value": expected_income_wan,
                }
            )
        if not isclose(
            float(row.get("资金流出总额(万元)") or 0.0),
            expected_expense_wan,
            abs_tol=0.01,
        ):
            metric_mismatches.append(
                {
                    "entity_name": entity_name,
                    "field": "total_expense_wan",
                    "sheet_value": float(row.get("资金流出总额(万元)") or 0.0),
                    "expected_value": expected_expense_wan,
                }
            )
    if metric_mismatches:
        problems.append(
            {
                "kind": "profile_sheet_metric_mismatch",
                "count": len(metric_mismatches),
                "details": metric_mismatches[:20],
            }
        )

    priority_board = _as_list(report_package.get("priority_board"))
    expected_summary = {
        "极高风险实体数": sum(
            1
            for item in priority_board
            if str(_as_dict(item).get("risk_label") or "").strip() == "极高风险"
        ),
        "高风险实体数": sum(
            1
            for item in priority_board
            if str(_as_dict(item).get("risk_label") or "").strip() == "高风险"
        ),
        "高优先线索实体数": len(priority_board),
        "平均风险分": round(
            sum(float(_as_dict(item).get("priority_score", 0) or 0) for item in priority_board)
            / len(priority_board),
            2,
        )
        if priority_board
        else 0.0,
    }
    sheet_summary = _sheet_metric_lookup(priority_summary_df)
    for key, expected_value in expected_summary.items():
        actual_value = sheet_summary.get(key)
        if isinstance(expected_value, float):
            if not isclose(float(actual_value or 0.0), expected_value, abs_tol=0.01):
                problems.append(
                    {
                        "kind": "priority_summary_metric_mismatch",
                        "metric": key,
                        "sheet_value": float(actual_value or 0.0),
                        "expected_value": expected_value,
                    }
                )
        elif int(actual_value or 0) != int(expected_value):
            problems.append(
                {
                    "kind": "priority_summary_metric_mismatch",
                    "metric": key,
                    "sheet_value": int(actual_value or 0),
                    "expected_value": int(expected_value),
                }
            )

    expected_priority_rows = priority_board[: min(5, len(priority_detail_df))]
    if len(priority_detail_df) != min(5, len(priority_board)):
        problems.append(
            {
                "kind": "priority_detail_count_mismatch",
                "sheet_count": len(priority_detail_df),
                "expected_count": min(5, len(priority_board)),
            }
        )
    row_mismatches: list[dict[str, Any]] = []
    for row, expected in zip(priority_detail_df.to_dict("records"), expected_priority_rows):
        expected_name = str(expected.get("entity_name") or "").strip()
        expected_score = round(float(expected.get("priority_score", 0) or 0), 2)
        expected_confidence = round(float(expected.get("confidence", 0) or 0), 2)
        expected_issue_count = len(_as_list(expected.get("issue_refs")))
        if (
            str(row.get("对象名称") or "").strip() != expected_name
            or not isclose(float(row.get("风险评分") or 0.0), expected_score, abs_tol=0.01)
            or not isclose(
                float(row.get("风险置信度") or 0.0), expected_confidence, abs_tol=0.01
            )
            or int(row.get("高优先线索数") or 0) != expected_issue_count
        ):
            row_mismatches.append(
                {
                    "sheet_row": row,
                    "expected_row": {
                        "对象名称": expected_name,
                        "风险评分": expected_score,
                        "风险置信度": expected_confidence,
                        "高优先线索数": expected_issue_count,
                    },
                }
            )
    if row_mismatches:
        problems.append(
            {
                "kind": "priority_detail_row_mismatch",
                "count": len(row_mismatches),
                "details": row_mismatches[:10],
            }
        )

    expected_direct_count = len(_as_list(suspicions.get("directTransfers")))
    text_metrics = base.parse_report_text_metrics(report_text)
    expected_direct_count = text_metrics.get("direct_transfer_count", expected_direct_count)
    if len(direct_df) != expected_direct_count:
        problems.append(
            {
                "kind": "direct_transfer_sheet_count_mismatch",
                "sheet_count": len(direct_df),
                "expected_count": expected_direct_count,
            }
        )

    return {
        "checked_profile_count": len(profile_df),
        "checked_priority_count": len(priority_detail_df),
        "checked_direct_transfer_count": len(direct_df),
        "problem_count": len(problems),
        "problems": problems,
    }


def build_text_report(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    append = lines.append

    append("======================================================================")
    append("E2E交付层盲盒复核报告")
    append("======================================================================")
    append(f"报告语义包: {payload['meta']['report_json']}")
    append(f"正式文本: {payload['meta']['report_txt']}")
    append(f"HTML产物: {payload['meta']['report_html']}")
    append(f"Excel底稿: {payload['meta']['report_xlsx']}")
    append(f"输出报告: {payload['meta']['report_out_txt']}")
    append("")

    append("一、HTML生成与接口链路")
    append("----------------------------------------------------------------------")
    delivery = payload["delivery_chain_audit"]
    append(
        f"已核对 generate-html、save-html、manifest、preview/download，HTML长度={delivery.get('generated_html_length', 0)}，发现问题{delivery['problem_count']}项。"
    )
    if delivery["problems"]:
        for item in delivery["problems"]:
            append(f"- {item['kind']}: {json.dumps(item, ensure_ascii=False)}")
    else:
        append("HTML生成、落盘、清单收录，以及 HTML/TXT/JSON/XLSX 预览下载链路均与当前正式产物一致。")

    append("")
    append("二、Excel底稿与正式语义层对齐")
    append("----------------------------------------------------------------------")
    excel = payload["excel_alignment_audit"]
    append(
        f"已核对 资金画像汇总={excel.get('checked_profile_count', 0)} 行、聚合风险重点对象={excel.get('checked_priority_count', 0)} 行、直接转账关系={excel.get('checked_direct_transfer_count', 0)} 行，发现问题{excel['problem_count']}项。"
    )
    if excel["problems"]:
        for item in excel["problems"]:
            append(f"- {item['kind']}: {json.dumps(item, ensure_ascii=False)}")
    else:
        append("Excel底稿中的对象画像、优先核查榜和直接往来明细已与正式语义包/TXT 统一。")

    append("")
    append("三、复核结论")
    append("----------------------------------------------------------------------")
    append(
        f"致命问题{payload['summary']['fatal_count']}项，警告{payload['summary']['warn_count']}项。"
    )
    append(payload["summary"]["verdict"])
    return "\n".join(lines)


def main() -> None:
    delivery_chain_audit = audit_delivery_chain()
    report_package = _load_json(REPORT_JSON)
    report_text = REPORT_TXT.read_text(encoding="utf-8")
    suspicions = _load_json(OUTPUT_ROOT / "analysis_cache" / "suspicions.json")
    excel_alignment_audit = audit_excel_alignment(report_package, report_text, suspicions)

    fatal_count = (
        delivery_chain_audit["problem_count"] + excel_alignment_audit["problem_count"]
    )
    warn_count = 0
    verdict = (
        "结论: 交付层的 HTML、Excel、报告清单与预览下载接口已和正式语义层对齐；当前可继续向外背书。"
        if fatal_count == 0
        else "结论: 交付层仍存在未收口差异，当前还不能把背书范围扩到最终交付载体。"
    )

    payload = {
        "meta": {
            "report_json": base.fmt_path(REPORT_JSON),
            "report_txt": base.fmt_path(REPORT_TXT),
            "report_html": base.fmt_path(REPORT_HTML),
            "report_xlsx": base.fmt_path(REPORT_XLSX),
            "report_out_txt": base.fmt_path(REPORT_OUT_TXT),
            "report_out_json": base.fmt_path(REPORT_OUT_JSON),
        },
        "summary": {
            "fatal_count": fatal_count,
            "warn_count": warn_count,
            "verdict": verdict,
        },
        "delivery_chain_audit": delivery_chain_audit,
        "excel_alignment_audit": excel_alignment_audit,
    }

    REPORT_OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    text = build_text_report(payload)
    REPORT_OUT_TXT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
