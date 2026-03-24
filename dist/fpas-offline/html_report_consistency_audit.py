#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit the final HTML report against the analysis cache and semantic package."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from lxml import html
except ImportError as exc:  # pragma: no cover - runtime dependency check
    raise SystemExit(
        "缺少 lxml，无法执行 HTML 一致性审计。请先安装 lxml。"
    ) from exc


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
RESULTS_DIR = OUTPUT_DIR / "analysis_results"
QA_DIR = RESULTS_DIR / "qa"
HTML_PATH = RESULTS_DIR / "初查报告.html"
PROFILES_PATH = OUTPUT_DIR / "analysis_cache" / "profiles.json"
REPORT_PACKAGE_PATH = QA_DIR / "report_package.json"

OUT_JSON = QA_DIR / "html_report_consistency_audit.json"
OUT_TXT = QA_DIR / "html_report_consistency_audit.txt"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_number(text: Any) -> Optional[float]:
    match = re.search(r"(-?\d+(?:\.\d+)?)", str(text or "").replace(",", ""))
    return float(match.group(1)) if match else None


def _extract_person_name(title: str) -> str:
    match = re.search(r"）([^（]+)（", title)
    return match.group(1).strip() if match else title.strip()


def _extract_family_name(title: str) -> str:
    match = re.search(r"、(.+?)(?:家庭(?:（.*?）)?|资产收入情况及数据分析)", title)
    return match.group(1).strip() if match else title.strip()


def _extract_company_name(title: str) -> str:
    match = re.search(r"(?:[一二三四五六七八九十]+、|\d+、)(.+?)及相关人员查询数据分析", title)
    return match.group(1).strip() if match else title.strip()


def _section_nodes(start_node: Any) -> List[Any]:
    nodes: List[Any] = []
    current = start_node.getnext()
    while current is not None and getattr(current, "tag", None) not in {"h1", "h2"}:
        nodes.append(current)
        current = current.getnext()
    return nodes


def _find_first(nodes: Iterable[Any], tag: str, class_name: Optional[str] = None) -> Optional[Any]:
    for node in nodes:
        if getattr(node, "tag", None) != tag:
            continue
        if class_name and class_name not in str(node.get("class") or ""):
            continue
        return node
    return None


def _find_h3_with_text(nodes: Iterable[Any], text: str) -> Optional[Any]:
    for node in nodes:
        if getattr(node, "tag", None) != "h3":
            continue
        node_text = " ".join("".join(node.itertext()).split())
        if text in node_text:
            return node
    return None


def _find_next_sibling(start_node: Any, tag: str) -> Optional[Any]:
    current = start_node.getnext()
    while current is not None and getattr(current, "tag", None) not in {"h1", "h2", "h3"}:
        if getattr(current, "tag", None) == tag:
            return current
        current = current.getnext()
    return None


def _extract_overview_cards(overview_node: Any) -> Dict[str, str]:
    cards: Dict[str, str] = {}
    for node in overview_node.xpath(".//div[./div]"):
        children = [child for child in node if isinstance(getattr(child, "tag", None), str)]
        if len(children) < 2:
            continue
        label = " ".join("".join(children[0].itertext()).split())
        value = " ".join("".join(children[1].itertext()).split())
        if label:
            cards[label] = value
    return cards


def _extract_salary_table(table_node: Any) -> Dict[str, Any]:
    yearly: Dict[str, Optional[float]] = {}
    total: Optional[float] = None

    for row in table_node.xpath("./tr")[1:]:
        cells = [" ".join("".join(cell.itertext()).split()) for cell in row.xpath("./th|./td")]
        year = next((cell for cell in cells if re.fullmatch(r"\d{4}", cell)), None)
        if year:
            amount = next(
                (_parse_number(cell) for cell in cells if cell.endswith("万元")),
                None,
            )
            yearly[year] = amount
            continue
        if any("合计" in cell for cell in cells):
            amounts = [_parse_number(cell) for cell in cells if _parse_number(cell) is not None]
            total = amounts[-1] if amounts else None

    return {"yearly": yearly, "total": total}


def _problem(kind: str, **kwargs: Any) -> Dict[str, Any]:
    payload = {"kind": kind}
    payload.update(kwargs)
    return payload


def audit_html_report() -> Dict[str, Any]:
    if not HTML_PATH.exists():
        return {
            "ok": False,
            "problem_count": 1,
            "problems": [_problem("missing_html", path=str(HTML_PATH))],
            "stats": {},
        }

    profiles = _load_json(PROFILES_PATH)
    report_package = _load_json(REPORT_PACKAGE_PATH)
    document = html.fromstring(HTML_PATH.read_text(encoding="utf-8", errors="ignore"))

    problems: List[Dict[str, Any]] = []
    stats = {
        "person_sections_checked": 0,
        "family_blocks_checked": 0,
        "company_sections_checked": 0,
    }

    family_dossiers = {
        item.get("family_name"): item
        for item in report_package.get("family_dossiers", [])
        if isinstance(item, dict) and item.get("family_name")
    }
    company_issue_items = {
        item.get("entity_name"): item
        for item in (
            (report_package.get("main_report_view") or {}).get("company_issue_items", [])
        )
        if isinstance(item, dict) and item.get("entity_name")
    }

    for h2 in document.xpath('//h2[contains(@class, "subsection-title")]'):
        title = " ".join("".join(h2.itertext()).split())
        name = _extract_person_name(title)
        if name not in profiles:
            problems.append(_problem("unknown_person_section", title=title, parsed_name=name))
            continue

        stats["person_sections_checked"] += 1
        section_nodes = _section_nodes(h2)
        overview = _find_first(section_nodes, "div", "overview-card")
        if overview is None:
            problems.append(_problem("missing_overview_card", name=name))
            continue

        profile = profiles[name]
        summary = profile.get("summary", {}) if isinstance(profile.get("summary", {}), dict) else {}
        yearly_salary = (
            profile.get("yearly_salary", {}) if isinstance(profile.get("yearly_salary", {}), dict) else {}
        )
        salary_summary = yearly_salary.get("summary", {}) if isinstance(yearly_salary.get("summary", {}), dict) else {}
        yearly_breakdown = yearly_salary.get("yearly", {}) if isinstance(yearly_salary.get("yearly", {}), dict) else {}

        expected_cards = {
            "总流入": round(float(summary.get("total_income", 0) or 0) / 10000, 2),
            "总流出": round(float(summary.get("total_expense", 0) or 0) / 10000, 2),
            "工资收入": round(float(salary_summary.get("total", 0) or 0) / 10000, 2),
            "真实收入": round(float(summary.get("real_income", 0) or 0) / 10000, 2),
        }
        real_income = float(summary.get("real_income", 0) or 0)
        salary_total = float(salary_summary.get("total", 0) or 0)
        expected_ratio = round((salary_total / real_income * 100) if real_income > 0 else 0.0, 1)

        actual_cards = _extract_overview_cards(overview)
        for label, expected in expected_cards.items():
            actual_value = _parse_number(actual_cards.get(label))
            if actual_value is None or abs(actual_value - expected) > 0.01:
                problems.append(
                    _problem(
                        "overview_card_mismatch",
                        name=name,
                        field=label,
                        expected=expected,
                        actual=actual_value,
                        raw=actual_cards.get(label),
                    )
                )

        actual_ratio = _parse_number(actual_cards.get("工资占比"))
        if actual_ratio is None or abs(actual_ratio - expected_ratio) > 0.1:
            problems.append(
                _problem(
                    "overview_ratio_mismatch",
                    name=name,
                    expected=expected_ratio,
                    actual=actual_ratio,
                    raw=actual_cards.get("工资占比"),
                )
            )

        salary_h3 = _find_h3_with_text(section_nodes, "工资奖金收入")
        if salary_h3 is None:
            problems.append(_problem("missing_salary_block", name=name))
            continue

        salary_p = _find_next_sibling(salary_h3, "p")
        salary_table = _find_next_sibling(salary_p, "table") if salary_p is not None else None
        if salary_p is None or salary_table is None:
            problems.append(_problem("incomplete_salary_block", name=name))
            continue

        narrative = " ".join("".join(salary_p.itertext()).split())
        total_wan = round(float(salary_summary.get("total", 0) or 0) / 10000, 2)
        if f"共取得工资收入{total_wan:.2f}万元" not in narrative:
            problems.append(
                _problem(
                    "salary_narrative_total_mismatch",
                    name=name,
                    expected=f"{total_wan:.2f}",
                    actual=narrative,
                )
            )

        salary_table_data = _extract_salary_table(salary_table)
        table_total = salary_table_data.get("total")
        if table_total is None or abs(table_total - total_wan) > 0.01:
            problems.append(
                _problem(
                    "salary_table_total_mismatch",
                    name=name,
                    expected=total_wan,
                    actual=table_total,
                )
            )
        for year, data in yearly_breakdown.items():
            expected_year = round(float((data or {}).get("total", 0) or 0) / 10000, 2)
            actual_year = salary_table_data["yearly"].get(str(year))
            if actual_year is None or abs(actual_year - expected_year) > 0.01:
                problems.append(
                    _problem(
                        "salary_table_year_mismatch",
                        name=name,
                        year=str(year),
                        expected=expected_year,
                        actual=actual_year,
                    )
                )

    for block in document.xpath('//div[contains(@class, "family-summary-block")]'):
        stats["family_blocks_checked"] += 1
        heading = block.getprevious()
        while heading is not None and getattr(heading, "tag", None) != "h1":
            heading = heading.getprevious()
        heading_text = " ".join("".join(heading.itertext()).split()) if heading is not None else ""
        family_name = _extract_family_name(heading_text)
        dossier = family_dossiers.get(family_name)
        if dossier is None:
            problems.append(_problem("missing_family_dossier", family_name=family_name, heading=heading_text))
            continue

        text = " ".join("".join(block.itertext()).split())
        match = re.search(
            r"家庭概况：(.+?)家庭共(\d+)人。家庭真实收入(-?\d+(?:\.\d+)?)万元，真实支出(-?\d+(?:\.\d+)?)万元（已剔除.*?(-?\d+(?:\.\d+)?)万元）。其中工资收入(-?\d+(?:\.\d+)?)万元，占真实收入(-?\d+(?:\.\d+)?)%。",
            text,
        )
        if not match:
            problems.append(_problem("family_block_parse_failed", family_name=family_name, raw=text[:300]))
            continue

        members = dossier.get("members", []) if isinstance(dossier.get("members", []), list) else []
        covered_profiles = [profiles[name] for name in members if name in profiles]
        expected_income = round(
            sum(float((item.get("summary", {}) or {}).get("real_income", 0) or 0) for item in covered_profiles) / 10000,
            2,
        )
        expected_expense = round(
            sum(float((item.get("summary", {}) or {}).get("real_expense", 0) or 0) for item in covered_profiles) / 10000,
            2,
        )
        expected_offset = round(
            sum(
                max(
                    0.0,
                    float((item.get("summary", {}) or {}).get("total_income", 0) or 0)
                    - float((item.get("summary", {}) or {}).get("real_income", 0) or 0),
                )
                for item in covered_profiles
            )
            / 10000,
            2,
        )
        expected_salary = round(
            sum(
                (((item.get("yearly_salary", {}) or {}).get("summary", {}) or {}).get("total", 0) or 0)
                for item in covered_profiles
            )
            / 10000,
            2,
        )
        expected_ratio = round((expected_salary / expected_income * 100) if expected_income > 0 else 0.0, 1)
        expected_member_count = int(dossier.get("member_count", 0) or 0)

        actual_member_count = int(match.group(2))
        actual_income = round(float(match.group(3)), 2)
        actual_expense = round(float(match.group(4)), 2)
        actual_offset = round(float(match.group(5)), 2)
        actual_salary = round(float(match.group(6)), 2)
        actual_ratio = round(float(match.group(7)), 1)

        family_checks = [
            ("member_count", expected_member_count, actual_member_count),
            ("real_income_wan", expected_income, actual_income),
            ("real_expense_wan", expected_expense, actual_expense),
            ("offset_income_wan", expected_offset, actual_offset),
            ("salary_total_wan", expected_salary, actual_salary),
            ("salary_ratio_pct", expected_ratio, actual_ratio),
        ]
        for field, expected, actual in family_checks:
            tolerance = 0.1 if field == "salary_ratio_pct" else 0.01
            if abs(actual - expected) > tolerance:
                problems.append(
                    _problem(
                        "family_summary_mismatch",
                        family_name=family_name,
                        field=field,
                        expected=expected,
                        actual=actual,
                    )
                )

    for h1 in document.xpath('//h1[contains(@class, "section-title")]'):
        title = " ".join("".join(h1.itertext()).split())
        if "有限公司" not in title or "查询数据分析" not in title:
            continue
        stats["company_sections_checked"] += 1
        company_name = _extract_company_name(title)
        expected = company_issue_items.get(company_name)
        if expected is None:
            problems.append(_problem("missing_company_issue_item", company_name=company_name))
            continue
        paragraph = _find_next_sibling(h1, "p")
        actual_summary = " ".join("".join(paragraph.itertext()).split()) if paragraph is not None else ""
        expected_summary = str(expected.get("summary") or "").strip()
        if actual_summary != expected_summary:
            problems.append(
                _problem(
                    "company_summary_mismatch",
                    company_name=company_name,
                    expected=expected_summary,
                    actual=actual_summary,
                )
            )

    return {
        "ok": not problems,
        "problem_count": len(problems),
        "problems": problems,
        "stats": stats,
        "artifacts": {
            "html": str(HTML_PATH),
            "profiles": str(PROFILES_PATH),
            "report_package": str(REPORT_PACKAGE_PATH),
        },
    }


def write_audit_outputs(result: Dict[str, Any]) -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "HTML 报告一致性审计",
        f"结果: {'通过' if result.get('ok') else '失败'}",
        f"问题数: {result.get('problem_count', 0)}",
        "",
        "统计:",
    ]
    stats = result.get("stats", {})
    lines.extend(
        [
            f"- 个人章节: {stats.get('person_sections_checked', 0)}",
            f"- 家庭汇总块: {stats.get('family_blocks_checked', 0)}",
            f"- 公司章节: {stats.get('company_sections_checked', 0)}",
            "",
            "问题明细:",
        ]
    )
    if result.get("problems"):
        for item in result["problems"]:
            lines.append("- " + json.dumps(item, ensure_ascii=False))
    else:
        lines.append("- 无")
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    result = audit_html_report()
    write_audit_outputs(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
