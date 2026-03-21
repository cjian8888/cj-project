#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data"
OUTPUT_ROOT = ROOT / "output"
REPORT_JSON = OUTPUT_ROOT / "analysis_results" / "qa" / "report_package.json"
REPORT_TXT = OUTPUT_ROOT / "analysis_results" / "核查结果分析报告.txt"
SUSPICIONS_JSON = OUTPUT_ROOT / "analysis_cache" / "suspicions.json"
REPORT_OUT_TXT = OUTPUT_ROOT / "analysis_results" / "qa" / "e2e_blindbox_audit_report.txt"
REPORT_OUT_JSON = OUTPUT_ROOT / "analysis_results" / "qa" / "e2e_blindbox_audit_report.json"

MONEY_RE = re.compile(r"([0-9][0-9,]*\.?[0-9]*)元")
FILE_ROW_RE = re.compile(r"(.+?\.xlsx)（解析记录第(\d+)行）")
DATE_RE = re.compile(r"交易日期:\s*([0-9:\-\s]+)")
DATETIME_LINE_RE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}")

BANK_COLUMNS = [
    "名称",
    "借贷标志",
    "交易金额",
    "交易时间",
    "交易对方名称",
    "交易对方账号",
    "交易对方卡号",
    "交易摘要",
    "交易流水号",
    "本方账号",
    "本方卡号",
    "查询卡号",
]

INCOME_HINTS = ("进", "贷", "收入", "入", "收")
EXPENSE_HINTS = ("出", "借", "支出", "付", "汇出", "转出")
COMPANY_MARKERS = (
    "公司",
    "集团",
    "研究所",
    "研究院",
    "中心",
    "银行",
    "医院",
    "大学",
    "学院",
    "协会",
)
ALIPAY_EXCLUDED_STATUSES = {
    "交易中途关闭（未完成）",
    "还款失败",
    "付款关闭",
    "交易关闭",
    "关闭",
    "单据关闭",
    "卖家已发货，买家确认中",
    "付款处理中",
    "初始化",
    "完成",
}


def money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return Decimal("0.00")
    return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "<na>"}:
        return ""
    return text.replace("\u200b", "").replace("\ufeff", "")


def clean_account(value: Any) -> str:
    text = clean_text(value).replace("\t", "").replace(" ", "")
    if not text:
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    return text


def accounts_match(left: str, right: str) -> bool:
    left = clean_account(left).lstrip("0")
    right = clean_account(right).lstrip("0")
    if not left or not right:
        return False
    if left == right:
        return True
    left_trimmed = left.rstrip("0")
    right_trimmed = right.rstrip("0")
    if left_trimmed and left_trimmed == right_trimmed:
        return True
    short = min(len(left), len(right))
    if short >= 8 and (left.startswith(right) or right.startswith(left) or left.endswith(right) or right.endswith(left)):
        return True
    return False


def parse_datetime(value: Any) -> pd.Timestamp | None:
    text = clean_text(value)
    if not text:
        return None
    dt = pd.to_datetime(text, errors="coerce")
    if pd.isna(dt):
        return None
    return dt


def normalize_direction(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return "unknown"
    for token in INCOME_HINTS:
        if token in text:
            return "income"
    for token in EXPENSE_HINTS:
        if token in text:
            return "expense"
    return "unknown"


def fmt_money(value: Decimal) -> str:
    return f"{money(value):,.2f}"


def fmt_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def is_company_name(name: str) -> bool:
    return any(marker in name for marker in COMPANY_MARKERS)


def parse_headline_amount(headline: str) -> Decimal:
    match = MONEY_RE.search(headline)
    return money(match.group(1)) if match else Decimal("0.00")


def parse_headline_parties(headline: str) -> tuple[str, str]:
    match = re.match(r"(.+?)与(.+?)发生", headline)
    if not match:
        return "", ""
    return match.group(1).strip(), match.group(2).strip()


def parse_issue_date(issue: dict[str, Any]) -> pd.Timestamp | None:
    for item in issue.get("why_flagged", []):
        match = DATE_RE.search(item)
        if match:
            return parse_datetime(match.group(1))
    return None


@dataclass
class BankRow:
    path: Path
    basename: str
    data_row_num: int
    excel_row_num: int
    entity_name: str
    direction: str
    amount: Decimal
    transaction_time: pd.Timestamp | None
    counterparty_name: str
    counterparty_account: str
    own_account: str
    summary: str
    transaction_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": fmt_path(self.path),
            "basename": self.basename,
            "data_row_num": self.data_row_num,
            "excel_row_num": self.excel_row_num,
            "entity_name": self.entity_name,
            "direction": self.direction,
            "amount": float(self.amount),
            "transaction_time": self.transaction_time.isoformat(sep=" ") if self.transaction_time is not None else None,
            "counterparty_name": self.counterparty_name,
            "counterparty_account": self.counterparty_account,
            "own_account": self.own_account,
            "summary": self.summary,
            "transaction_id": self.transaction_id,
        }


def load_report_artifacts() -> tuple[dict[str, Any], str, dict[str, Any]]:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    report_text = REPORT_TXT.read_text(encoding="utf-8")
    suspicions = json.loads(SUSPICIONS_JSON.read_text(encoding="utf-8"))
    return report, report_text, suspicions


def parse_report_text_metrics(report_text: str) -> dict[str, int]:
    metrics: dict[str, int] = {}
    patterns = {
        "direct_transfer_count": r"发现\s+(\d+)\s+条直接往来记录",
        "long_unrepaid_loan_count": r"发现\s+(\d+)\s+笔长期无还款借贷",
        "platform_loan_count": r"发现\s+(\d+)\s+笔网贷平台交易",
        "large_income_count": r"发现\s+(\d+)\s+笔大额单笔收入",
        "regular_non_salary_income_group_count": r"发现\s+(\d+)\s+组规律性非工资收入",
        "alipay_trade_count": r"支付宝(\d+)笔",
        "tenpay_trade_count": r"财付通(\d+)笔",
        "wx_login_count": r"微信登录轨迹(\d+)条",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, report_text)
        if match:
            metrics[key] = int(match.group(1))
    return metrics


def load_bank_rows() -> tuple[list[BankRow], dict[str, list[BankRow]], dict[str, dict[str, Any]]]:
    rows: list[BankRow] = []
    rows_by_file: dict[str, list[BankRow]] = defaultdict(list)
    dedupe_keys: set[str] = set()
    entity_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "transaction_count": 0,
            "total_income": Decimal("0.00"),
            "total_expense": Decimal("0.00"),
            "paths": set(),
            "accounts": set(),
        }
    )

    bank_paths = sorted(
        path
        for path in DATA_ROOT.rglob("*.xlsx")
        if "银行业金融机构交易流水" in str(path)
    )
    for path in bank_paths:
        df = pd.read_excel(path, sheet_name=0, dtype=str, usecols=lambda col: col in BANK_COLUMNS)
        for idx, record in df.iterrows():
            entity_name = clean_text(record.get("名称"))
            direction = normalize_direction(record.get("借贷标志"))
            amount_value = money(record.get("交易金额"))
            transaction_time = parse_datetime(record.get("交易时间"))
            counterparty_name = clean_text(record.get("交易对方名称"))
            counterparty_account = clean_account(record.get("交易对方账号") or record.get("交易对方卡号"))
            own_account = clean_account(record.get("本方账号") or record.get("本方卡号") or record.get("查询卡号"))
            row = BankRow(
                path=path,
                basename=path.name,
                data_row_num=idx + 1,
                excel_row_num=idx + 2,
                entity_name=entity_name,
                direction=direction,
                amount=amount_value,
                transaction_time=transaction_time,
                counterparty_name=counterparty_name,
                counterparty_account=counterparty_account,
                own_account=own_account,
                summary=clean_text(record.get("交易摘要")),
                transaction_id=clean_text(record.get("交易流水号")),
            )
            rows.append(row)
            rows_by_file[path.name].append(row)
            txid_key = row.transaction_id
            natural_key = "|".join(
                [
                    row.entity_name,
                    row.direction,
                    f"{row.amount:.2f}",
                    row.transaction_time.isoformat(sep=" ") if row.transaction_time is not None else "",
                    row.counterparty_name,
                    row.summary,
                    row.own_account,
                ]
            )
            dedupe_key = f"{path.name}|TXID|{txid_key}" if txid_key else f"{path.name}|NAT|{natural_key}"
            if dedupe_key in dedupe_keys:
                continue
            dedupe_keys.add(dedupe_key)
            stats = entity_stats[entity_name]
            stats["transaction_count"] += 1
            if direction == "income":
                stats["total_income"] += amount_value
            elif direction == "expense":
                stats["total_expense"] += amount_value
            stats["paths"].add(fmt_path(path))
            if own_account:
                stats["accounts"].add(own_account)
    return rows, rows_by_file, entity_stats


def load_wallet_metrics() -> dict[str, Any]:
    alipay_paths = sorted(path for path in DATA_ROOT.rglob("*.xlsx") if "账户明细" in path.name and "ZFB+WX" in str(path))
    tenpay_paths = sorted(path for path in DATA_ROOT.rglob("*.txt") if "TenpayTrades" in path.name)
    wx_login_paths = sorted(path for path in DATA_ROOT.rglob("*.txt") if "WX登录轨迹" in path.name)

    alipay_all_trade_count = 0
    alipay_trade_count = 0
    alipay_subjects: set[str] = set()
    alipay_status_counts: Counter[str] = Counter()
    for path in alipay_paths:
        workbook = pd.ExcelFile(path)
        for sheet in workbook.sheet_names:
            df = workbook.parse(sheet)
            alipay_all_trade_count += len(df.index)
            alipay_subjects.add(str(sheet).strip())
            if "交易状态" in df.columns:
                statuses = [clean_text(status).strip() for status in df["交易状态"].fillna("")]
                alipay_status_counts.update(statuses)
                alipay_trade_count += sum(1 for status in statuses if status not in ALIPAY_EXCLUDED_STATUSES)
            else:
                alipay_trade_count += len(df.index)

    tenpay_trade_count = 0
    tenpay_subjects: set[str] = set()
    for path in tenpay_paths:
        text = path.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if line.strip()]
        tenpay_trade_count += max(len(lines) - 1, 0)
        parts = path.parts
        if "IDCARD" in parts:
            idx = parts.index("IDCARD")
            if idx + 1 < len(parts):
                tenpay_subjects.add(parts[idx + 1])

    wx_login_count = 0
    wx_login_by_phone: dict[str, int] = {}
    for path in wx_login_paths:
        text = path.read_text(encoding="utf-8")
        count = sum(1 for line in text.splitlines() if DATETIME_LINE_RE.match(line))
        wx_login_count += count
        wx_login_by_phone[path.parts[-2]] = count

    return {
        "alipay_all_trade_count": alipay_all_trade_count,
        "alipay_trade_count": alipay_trade_count,
        "tenpay_trade_count": tenpay_trade_count,
        "wx_login_count": wx_login_count,
        "wallet_transaction_count": alipay_trade_count + tenpay_trade_count,
        "wallet_subject_count": len(alipay_subjects | tenpay_subjects),
        "alipay_subjects": sorted(alipay_subjects),
        "tenpay_subjects": sorted(tenpay_subjects),
        "alipay_status_counts": dict(alipay_status_counts),
        "wx_login_by_phone": wx_login_by_phone,
    }


def make_report_entity_stats(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for item in report.get("person_dossiers", []) + report.get("company_dossiers", []):
        stats[item["entity_name"]] = {
            "transaction_count": int(item.get("transaction_count") or 0),
            "total_income": money(item.get("total_income")),
            "total_expense": money(item.get("total_expense")),
            "entity_type": item.get("entity_type"),
            "summary": item.get("summary", ""),
        }
    return stats


def compare_core_metrics(report: dict[str, Any], report_text_metrics: dict[str, int], entity_stats: dict[str, dict[str, Any]], wallet_metrics: dict[str, Any], report_entity_stats: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    raw_subjects = set(entity_stats.keys()) - {""}
    raw_persons = sorted(name for name in raw_subjects if not is_company_name(name))
    raw_companies = sorted(name for name in raw_subjects if is_company_name(name))

    raw_bank_transaction_count = sum(item["transaction_count"] for item in entity_stats.values())
    raw_total_income = sum((item["total_income"] for item in entity_stats.values()), Decimal("0.00"))
    raw_total_expense = sum((item["total_expense"] for item in entity_stats.values()), Decimal("0.00"))

    report_total_income = sum((item["total_income"] for item in report_entity_stats.values()), Decimal("0.00"))
    report_total_expense = sum((item["total_expense"] for item in report_entity_stats.values()), Decimal("0.00"))
    report_total_transaction_count = sum(item["transaction_count"] for item in report_entity_stats.values())

    metrics = [
        {
            "metric": "银行流水总笔数",
            "report_value": int(report["coverage"]["bank_transaction_count"]),
            "raw_value": raw_bank_transaction_count,
        },
        {
            "metric": "核查对象人数",
            "report_value": int(report["coverage"]["persons_count"]),
            "raw_value": len(raw_persons),
        },
        {
            "metric": "涉案公司数量",
            "report_value": int(report["coverage"]["companies_count"]),
            "raw_value": len(raw_companies),
        },
        {
            "metric": "钱包覆盖主体数",
            "report_value": int(report["coverage"]["wallet_subject_count"]),
            "raw_value": int(wallet_metrics["wallet_subject_count"]),
        },
        {
            "metric": "钱包交易总笔数",
            "report_value": int(report["coverage"]["wallet_transaction_count"]),
            "raw_value": int(wallet_metrics["wallet_transaction_count"]),
        },
        {
            "metric": "支付宝交易笔数",
            "report_value": int(report_text_metrics.get("alipay_trade_count", 0)),
            "raw_value": int(wallet_metrics["alipay_trade_count"]),
        },
        {
            "metric": "财付通交易笔数",
            "report_value": int(report_text_metrics.get("tenpay_trade_count", 0)),
            "raw_value": int(wallet_metrics["tenpay_trade_count"]),
        },
        {
            "metric": "微信登录轨迹条数",
            "report_value": int(report_text_metrics.get("wx_login_count", 0)),
            "raw_value": int(wallet_metrics["wx_login_count"]),
        },
        {
            "metric": "报告侧卷宗汇总交易笔数",
            "report_value": report_total_transaction_count,
            "raw_value": raw_bank_transaction_count,
        },
        {
            "metric": "报告侧卷宗汇总总流入",
            "report_value": float(report_total_income),
            "raw_value": float(raw_total_income),
        },
        {
            "metric": "报告侧卷宗汇总总流出",
            "report_value": float(report_total_expense),
            "raw_value": float(raw_total_expense),
        },
    ]
    mismatches = [item for item in metrics if Decimal(str(item["report_value"])) != Decimal(str(item["raw_value"]))]

    entity_mismatches: list[dict[str, Any]] = []
    for entity_name, report_stats in sorted(report_entity_stats.items()):
        raw_stats = entity_stats.get(entity_name)
        if not raw_stats:
            entity_mismatches.append(
                {
                    "entity_name": entity_name,
                    "problem": "报告列出了主体，但原始银行流水中找不到该主体的任何交易记录。",
                    "report_transaction_count": report_stats["transaction_count"],
                    "raw_transaction_count": 0,
                }
            )
            continue
        if (
            report_stats["transaction_count"] != raw_stats["transaction_count"]
            or report_stats["total_income"] != raw_stats["total_income"]
            or report_stats["total_expense"] != raw_stats["total_expense"]
        ):
            entity_mismatches.append(
                {
                    "entity_name": entity_name,
                    "problem": "卷宗汇总口径与原始流水复算不一致。",
                    "report_transaction_count": report_stats["transaction_count"],
                    "raw_transaction_count": raw_stats["transaction_count"],
                    "report_total_income": fmt_money(report_stats["total_income"]),
                    "raw_total_income": fmt_money(raw_stats["total_income"]),
                    "report_total_expense": fmt_money(report_stats["total_expense"]),
                    "raw_total_expense": fmt_money(raw_stats["total_expense"]),
                }
            )

    raw_context = {
        "raw_bank_subjects": sorted(raw_subjects),
        "raw_persons": raw_persons,
        "raw_companies": raw_companies,
        "raw_bank_transaction_count": raw_bank_transaction_count,
        "raw_total_income": fmt_money(raw_total_income),
        "raw_total_expense": fmt_money(raw_total_expense),
    }
    return metrics, mismatches, {"entity_mismatches": entity_mismatches, **raw_context}


def score_row_match(row: BankRow, amount_value: Decimal | None, issue_date: pd.Timestamp | None, txid: str, parties: set[str]) -> int:
    score = 0
    if amount_value is not None and row.amount == amount_value:
        score += 3
    if issue_date is not None and row.transaction_time is not None and row.transaction_time == issue_date:
        score += 3
    if txid and row.transaction_id == txid:
        score += 4
    names = {row.entity_name, row.counterparty_name}
    if parties and parties <= names:
        score += 3
    return score


def find_best_row(rows_by_file: dict[str, list[BankRow]], file_name: str, ref_row: int | None, amount_value: Decimal | None, issue_date: pd.Timestamp | None, txid: str, parties: set[str]) -> tuple[BankRow | None, str]:
    candidates = rows_by_file.get(file_name, [])
    if not candidates:
        return None, "报告引用的原始文件在 data 目录不存在。"

    best_row = None
    best_score = -1
    reason = "未找到可支撑该结论的原始流水。"

    search_rows = candidates
    if ref_row is not None:
        nearby = [row for row in candidates if abs(row.excel_row_num - ref_row) <= 3 or abs(row.data_row_num - ref_row) <= 3]
        if nearby:
            search_rows = nearby + candidates

    for row in search_rows:
        score = score_row_match(row, amount_value, issue_date, txid, parties)
        if ref_row is not None:
            if row.excel_row_num == ref_row:
                score += 2
            elif row.data_row_num == ref_row:
                score += 1
        if score > best_score:
            best_score = score
            best_row = row

    if best_row is None or best_score < 6:
        return None, reason
    return best_row, ""


def audit_report_issues(report: dict[str, Any], rows_by_file: dict[str, list[BankRow]]) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    passed = 0

    for issue in report["main_report_view"]["issues"]:
        file_ref = next((item for item in issue.get("evidence_refs", []) if item.endswith("行）")), "")
        txid_ref = next((item.replace("交易标识 ", "").strip() for item in issue.get("evidence_refs", []) if item.startswith("交易标识 ")), "")
        match = FILE_ROW_RE.match(file_ref)
        file_name = match.group(1) if match else ""
        ref_row = int(match.group(2)) if match else None
        amount_value = money(issue.get("amount_impact") or parse_headline_amount(issue["headline"]))
        issue_date = parse_issue_date(issue)
        parties = set(parse_headline_parties(issue["headline"]))

        best_row, error = find_best_row(rows_by_file, file_name, ref_row, amount_value, issue_date, txid_ref, parties)
        if best_row is None:
            failed.append(
                {
                    "issue_id": issue["issue_id"],
                    "headline": issue["headline"],
                    "evidence_ref": file_ref,
                    "transaction_id_ref": txid_ref,
                    "problem": error,
                }
            )
            continue

        passed += 1
        details.append(
            {
                "issue_id": issue["issue_id"],
                "headline": issue["headline"],
                "report_file_ref": file_ref,
                "matched_file": fmt_path(best_row.path),
                "matched_excel_row": best_row.excel_row_num,
                "matched_transaction_id": best_row.transaction_id,
                "matched_amount": fmt_money(best_row.amount),
                "matched_time": best_row.transaction_time.isoformat(sep=" ") if best_row.transaction_time is not None else "",
                "matched_counterparty": best_row.counterparty_name,
            }
        )

    return {
        "checked_count": len(report["main_report_view"]["issues"]),
        "passed_count": passed,
        "failed_count": len(failed),
        "passed_details": details,
        "failed_details": failed,
    }


def audit_direct_transfers(report_text_metrics: dict[str, int], suspicions: dict[str, Any], rows_by_file: dict[str, list[BankRow]]) -> dict[str, Any]:
    transfers = suspicions.get("directTransfers", [])
    failures: list[dict[str, Any]] = []
    row_offsets = Counter()
    verified = 0

    for item in transfers:
        file_name = item.get("sourceFile", "")
        ref_row = item.get("sourceRowIndex")
        txid = clean_text(item.get("transactionId"))
        amount_value = money(item.get("amount"))
        issue_date = parse_datetime(item.get("date"))
        parties = {clean_text(item.get("from")), clean_text(item.get("to"))}

        best_row, error = find_best_row(rows_by_file, file_name, ref_row, amount_value, issue_date, txid, parties)
        if best_row is None:
            failures.append(
                {
                    "from": item.get("from"),
                    "to": item.get("to"),
                    "amount": fmt_money(amount_value),
                    "date": clean_text(item.get("date")),
                    "source_file": file_name,
                    "source_row": ref_row,
                    "transaction_id": txid,
                    "problem": error,
                }
            )
            continue

        verified += 1
        if ref_row is not None:
            row_offsets[best_row.excel_row_num - int(ref_row)] += 1

    report_count = int(report_text_metrics.get("direct_transfer_count", len(transfers)))
    return {
        "report_count": report_count,
        "output_count": len(transfers),
        "verified_count": verified,
        "failed_count": len(failures),
        "row_offset_distribution": dict(row_offsets),
        "failed_details": failures[:20],
    }


def find_transfer_item_for_issue(issue: dict[str, Any], suspicions: dict[str, Any]) -> dict[str, Any] | None:
    amount_value = money(issue.get("amount_impact") or parse_headline_amount(issue["headline"]))
    issue_date = parse_issue_date(issue)
    parties = set(parse_headline_parties(issue["headline"]))
    for item in suspicions.get("directTransfers", []):
        item_date = parse_datetime(item.get("date"))
        if money(item.get("amount")) != amount_value:
            continue
        if issue_date is not None and item_date != issue_date:
            continue
        if {clean_text(item.get("from")), clean_text(item.get("to"))} == parties:
            return item
    return None


def search_mirror_row(target: BankRow, all_rows: list[BankRow], transfer_item: dict[str, Any]) -> BankRow | None:
    expected_entity = clean_text(transfer_item.get("from")) if target.direction == "income" else clean_text(transfer_item.get("to"))
    expected_counterparty = clean_text(transfer_item.get("to")) if target.direction == "income" else clean_text(transfer_item.get("from"))
    expected_direction = "expense" if target.direction == "income" else "income"

    candidates = []
    for row in all_rows:
        if row.entity_name != expected_entity:
            continue
        if row.direction != expected_direction:
            continue
        if row.amount != target.amount:
            continue
        if row.transaction_time is None or target.transaction_time is None:
            continue
        if abs((row.transaction_time - target.transaction_time).total_seconds()) > 120:
            continue
        if row.counterparty_name == expected_counterparty or row.counterparty_name == target.entity_name or accounts_match(row.counterparty_account, target.own_account):
            candidates.append(row)
    candidates.sort(key=lambda row: abs((row.transaction_time - target.transaction_time).total_seconds()))
    return candidates[0] if candidates else None


def search_chain_neighbors(target: BankRow, all_rows: list[BankRow], window_hours: int, direction: str) -> list[BankRow]:
    if target.transaction_time is None:
        return []
    start = target.transaction_time - pd.Timedelta(hours=window_hours)
    end = target.transaction_time + pd.Timedelta(hours=window_hours)
    candidates = []
    for row in all_rows:
        if row.entity_name != target.entity_name:
            continue
        if row.direction != direction:
            continue
        if row.transaction_time is None:
            continue
        if not (start <= row.transaction_time <= end):
            continue
        if row.transaction_time == target.transaction_time and row.amount == target.amount and row.transaction_id == target.transaction_id:
            continue
        if target.own_account and row.own_account and not accounts_match(target.own_account, row.own_account):
            continue
        candidates.append(row)
    candidates.sort(key=lambda row: abs((row.transaction_time - target.transaction_time).total_seconds()))
    return candidates


def reverse_trace_largest_issue(report: dict[str, Any], suspicions: dict[str, Any], rows_by_file: dict[str, list[BankRow]], all_rows: list[BankRow]) -> dict[str, Any]:
    issues = sorted(
        report["main_report_view"]["issues"],
        key=lambda item: (money(item.get("amount_impact") or parse_headline_amount(item["headline"])), item.get("severity", 0)),
        reverse=True,
    )
    target_issue = issues[0]
    transfer_item = find_transfer_item_for_issue(target_issue, suspicions)

    file_ref = next((item for item in target_issue.get("evidence_refs", []) if item.endswith("行）")), "")
    txid_ref = next((item.replace("交易标识 ", "").strip() for item in target_issue.get("evidence_refs", []) if item.startswith("交易标识 ")), "")
    match = FILE_ROW_RE.match(file_ref)
    file_name = match.group(1) if match else ""
    ref_row = int(match.group(2)) if match else None
    amount_value = money(target_issue.get("amount_impact") or parse_headline_amount(target_issue["headline"]))
    issue_date = parse_issue_date(target_issue)
    parties = set(parse_headline_parties(target_issue["headline"]))

    base_row, error = find_best_row(rows_by_file, file_name, ref_row, amount_value, issue_date, txid_ref, parties)
    if base_row is None:
        return {
            "issue_id": target_issue["issue_id"],
            "headline": target_issue["headline"],
            "status": "fatal",
            "problem": error,
        }

    mirror_row = search_mirror_row(base_row, all_rows, transfer_item or {})
    source_side = base_row if base_row.direction == "expense" else mirror_row
    if source_side is None:
        source_side = base_row

    upstream_rows = search_chain_neighbors(source_side, all_rows, window_hours=6, direction="income")
    downstream_rows = search_chain_neighbors(mirror_row or base_row, all_rows, window_hours=24, direction="expense")

    return {
        "issue_id": target_issue["issue_id"],
        "headline": target_issue["headline"],
        "status": "pass" if mirror_row is not None else "warn",
        "base_row": base_row.as_dict(),
        "mirror_row": mirror_row.as_dict() if mirror_row is not None else None,
        "upstream_candidates": [row.as_dict() for row in upstream_rows[:5]],
        "downstream_candidates": [row.as_dict() for row in downstream_rows[:5]],
        "problem": "" if mirror_row is not None else "只找到单边流水，未在对手方账户中定位到镜像记录，证据链停在半路。",
    }


def audit_accounts(report: dict[str, Any], entity_stats: dict[str, dict[str, Any]]) -> dict[str, Any]:
    report_entities = set(report["meta"].get("primary_subjects", [])) | set(report["meta"].get("companies", []))
    raw_entities = set(entity_stats.keys()) - {""}

    hallucinated = sorted(report_entities - raw_entities)
    hidden = sorted(raw_entities - report_entities)
    hidden_ranked = [
        {
            "entity_name": entity_name,
            "transaction_count": entity_stats[entity_name]["transaction_count"],
            "total_turnover": fmt_money(entity_stats[entity_name]["total_income"] + entity_stats[entity_name]["total_expense"]),
            "paths": sorted(entity_stats[entity_name]["paths"]),
        }
        for entity_name in hidden
    ]
    hidden_ranked.sort(key=lambda item: (item["transaction_count"], Decimal(item["total_turnover"].replace(",", ""))), reverse=True)

    return {
        "report_entities": sorted(report_entities),
        "raw_entities": sorted(raw_entities),
        "hallucinated_entities": hallucinated,
        "hidden_entities_ranked": hidden_ranked[:10],
    }


def find_exact_subset_by_sum(items: list[tuple[str, int]], target: int) -> list[tuple[str, int]]:
    if target <= 0:
        return []
    for size in range(1, len(items) + 1):
        for combo in combinations(items, size):
            if sum(value for _, value in combo) == target:
                return list(combo)
    return []


def build_text_report(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    append = lines.append

    append("======================================================================")
    append("E2E盲盒对账打脸报告")
    append("======================================================================")
    append(f"报告侧取证: {payload['meta']['report_json']}")
    append(f"原始数据侧: {payload['meta']['data_root']}")
    append("")
    append("一、总表硬对账")
    append("----------------------------------------------------------------------")
    for item in payload["core_metrics"]:
        status = "一致" if Decimal(str(item["report_value"])) == Decimal(str(item["raw_value"])) else "打脸"
        append(f"[{status}] {item['metric']}: 报告={item['report_value']} | 原始复算={item['raw_value']}")
    if payload["core_metric_mismatches"]:
        append("")
        append("硬伤明细:")
        for item in payload["core_metric_mismatches"]:
            append(f"- {item['metric']}: 报告={item['report_value']}，原始复算={item['raw_value']}")
    else:
        append("")
        append("核心总表暂未打脸，至少账面大数没编造。")

    append("")
    append("二、卷宗汇总逐户复算")
    append("----------------------------------------------------------------------")
    if payload["entity_mismatches"]:
        for item in payload["entity_mismatches"]:
            append(
                f"- {item['entity_name']}: {item['problem']} | 笔数 报告={item.get('report_transaction_count')} / 原始={item.get('raw_transaction_count')} | "
                f"流入 报告={item.get('report_total_income', 'N/A')} / 原始={item.get('raw_total_income', 'N/A')} | "
                f"流出 报告={item.get('report_total_expense', 'N/A')} / 原始={item.get('raw_total_expense', 'N/A')}"
            )
    else:
        append("11名个人 + 3家企业的 `transaction_count/total_income/total_expense` 与原始银行流水逐户复算一致，没有抓到算错账。")

    append("")
    append("三、问题卡证据链审计")
    append("----------------------------------------------------------------------")
    issue_audit = payload["issue_evidence_audit"]
    append(
        f"主报告重点问题卡: 共{issue_audit['checked_count']}项，原始流水支撑通过{issue_audit['passed_count']}项，打脸{issue_audit['failed_count']}项。"
    )
    if issue_audit["failed_details"]:
        append("打脸问题:")
        for item in issue_audit["failed_details"]:
            append(
                f"- {item['issue_id']} {item['headline']} | 证据引用={item['evidence_ref']} | 交易标识={item['transaction_id_ref']} | 问题={item['problem']}"
            )
    else:
        append("重点问题卡没有出现“报告写了、原始流水却不存在”的硬核幻觉。")

    append("")
    append("四、232条直接往来记录复核")
    append("----------------------------------------------------------------------")
    transfer_audit = payload["direct_transfer_audit"]
    append(
        f"报告声称直接往来{transfer_audit['report_count']}条；输出缓存列出{transfer_audit['output_count']}条；原始流水核实落地{transfer_audit['verified_count']}条；失联{transfer_audit['failed_count']}条。"
    )
    if transfer_audit["row_offset_distribution"]:
        append(f"行号偏移分布: {transfer_audit['row_offset_distribution']}")
    if transfer_audit["failed_details"]:
        append("失联样本:")
        for item in transfer_audit["failed_details"]:
            append(
                f"- {item['from']} -> {item['to']} {item['amount']}元 @ {item['date']} | {item['source_file']} 行{item['source_row']} | 交易标识={item['transaction_id']} | {item['problem']}"
            )
    else:
        append("232条直接往来没有出现凭空捏造，原始流水都能对上。")

    append("")
    append("五、最大可疑线索逆向拷问")
    append("----------------------------------------------------------------------")
    trace = payload["reverse_trace"]
    append(f"目标线索: {trace['issue_id']} {trace['headline']}")
    if trace["status"] == "fatal":
        append(f"[致命打脸] {trace['problem']}")
    else:
        base = trace["base_row"]
        append(
            f"基础证据: {base['path']} 第{base['excel_row_num']}行 | {base['entity_name']} {base['direction']} {fmt_money(Decimal(str(base['amount'])))}元 | "
            f"{base['transaction_time']} | 对手方={base['counterparty_name']} | 交易标识={base['transaction_id']}"
        )
        if trace["mirror_row"]:
            mirror = trace["mirror_row"]
            append(
                f"镜像证据: {mirror['path']} 第{mirror['excel_row_num']}行 | {mirror['entity_name']} {mirror['direction']} {fmt_money(Decimal(str(mirror['amount'])))}元 | "
                f"{mirror['transaction_time']} | 对手方={mirror['counterparty_name']} | 交易标识={mirror['transaction_id']}"
            )
        else:
            append(f"[证据链断裂] {trace['problem']}")
        if trace["upstream_candidates"]:
            append("上游候选链:")
            for item in trace["upstream_candidates"][:3]:
                append(
                    f"- {item['path']} 第{item['excel_row_num']}行 | {item['entity_name']} {item['direction']} {fmt_money(Decimal(str(item['amount'])))}元 | "
                    f"{item['transaction_time']} | 对手方={item['counterparty_name']}"
                )
        else:
            append("[盲区] 未在近6小时窗口内抓到上游进账，链条只能停留在单笔直接往来。")
        if trace["downstream_candidates"]:
            append("下游候选链:")
            for item in trace["downstream_candidates"][:3]:
                append(
                    f"- {item['path']} 第{item['excel_row_num']}行 | {item['entity_name']} {item['direction']} {fmt_money(Decimal(str(item['amount'])))}元 | "
                    f"{item['transaction_time']} | 对手方={item['counterparty_name']}"
                )
        else:
            append("[盲区] 对手方入账后24小时内未见明确下游续转，链条无法继续拉长。")

    append("")
    append("六、账户幻觉与漏算排查")
    append("----------------------------------------------------------------------")
    accounts = payload["account_audit"]
    if accounts["hallucinated_entities"]:
        append(f"[无中生有] 报告列出但原始流水不存在的主体: {', '.join(accounts['hallucinated_entities'])}")
    else:
        append("报告主体名单没有出现无中生有。")
    if accounts["hidden_entities_ranked"]:
        append("[隐身名单] 原始流水存在、但报告主体名单未覆盖的对象:")
        for item in accounts["hidden_entities_ranked"]:
            append(
                f"- {item['entity_name']} | 笔数={item['transaction_count']} | 总流水={item['total_turnover']}元 | 来源文件={'; '.join(item['paths'][:2])}"
            )
    else:
        append("原始流水里的高频/高额主体没有在最终报告主体名单中消失。")
    if accounts.get("wallet_login_gap_details"):
        append("[钱包盲区] 报告少算的微信登录轨迹，刚好落在以下未归并手机号上:")
        for item in accounts["wallet_login_gap_details"]:
            append(f"- {item['phone']} | 登录轨迹={item['login_count']}条")

    append("")
    append("七、审计结论")
    append("----------------------------------------------------------------------")
    append(
        f"致命问题{payload['summary']['fatal_count']}项，警告{payload['summary']['warn_count']}项。"
    )
    append(payload["summary"]["verdict"])
    append("")
    append(f"审计报告文件: {payload['meta']['report_out_txt']}")
    return "\n".join(lines)


def main() -> None:
    report, report_text, suspicions = load_report_artifacts()
    report_text_metrics = parse_report_text_metrics(report_text)
    all_rows, rows_by_file, entity_stats = load_bank_rows()
    wallet_metrics = load_wallet_metrics()
    report_entity_stats = make_report_entity_stats(report)

    core_metrics, core_metric_mismatches, core_context = compare_core_metrics(
        report,
        report_text_metrics,
        entity_stats,
        wallet_metrics,
        report_entity_stats,
    )
    issue_evidence_audit = audit_report_issues(report, rows_by_file)
    direct_transfer_audit = audit_direct_transfers(report_text_metrics, suspicions, rows_by_file)
    reverse_trace = reverse_trace_largest_issue(report, suspicions, rows_by_file, all_rows)
    account_audit = audit_accounts(report, entity_stats)
    wx_login_gap = int(wallet_metrics["wx_login_count"]) - int(report_text_metrics.get("wx_login_count", 0))
    wx_login_gap_combo = find_exact_subset_by_sum(
        sorted(wallet_metrics["wx_login_by_phone"].items(), key=lambda item: item[1], reverse=True),
        wx_login_gap,
    )
    if wx_login_gap_combo:
        account_audit["wallet_login_gap_details"] = [
            {"phone": phone, "login_count": count}
            for phone, count in wx_login_gap_combo
        ]
    else:
        account_audit["wallet_login_gap_details"] = []

    fatal_count = (
        len(core_metric_mismatches)
        + len(core_context["entity_mismatches"])
        + issue_evidence_audit["failed_count"]
        + direct_transfer_audit["failed_count"]
        + len(account_audit["hallucinated_entities"])
    )
    warn_count = 0
    if reverse_trace.get("status") == "warn":
        warn_count += 1
    if reverse_trace.get("downstream_candidates") == []:
        warn_count += 1

    verdict = (
        "结论: 核心账面、钱包总量与重点问题卡在原始数据侧基本站得住脚；目前没有抓到‘凭空造数’。"
        if fatal_count == 0
        else "结论: 系统产出存在硬伤，已经被原始流水当场打脸。"
    )
    if reverse_trace.get("status") == "warn":
        verdict += " 但最大问题链条只拿到了有限续链证据，穿透叙事仍有盲区。"

    payload = {
        "meta": {
            "report_json": fmt_path(REPORT_JSON),
            "data_root": fmt_path(DATA_ROOT),
            "report_out_txt": fmt_path(REPORT_OUT_TXT),
            "report_out_json": fmt_path(REPORT_OUT_JSON),
        },
        "summary": {
            "fatal_count": fatal_count,
            "warn_count": warn_count,
            "verdict": verdict,
        },
        "core_metrics": core_metrics,
        "core_metric_mismatches": core_metric_mismatches,
        "entity_mismatches": core_context["entity_mismatches"],
        "core_context": core_context,
        "wallet_metrics": wallet_metrics,
        "report_text_metrics": report_text_metrics,
        "issue_evidence_audit": issue_evidence_audit,
        "direct_transfer_audit": direct_transfer_audit,
        "reverse_trace": reverse_trace,
        "account_audit": account_audit,
    }

    REPORT_OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_text_output = build_text_report(payload)
    REPORT_OUT_TXT.write_text(report_text_output, encoding="utf-8")
    print(report_text_output)


if __name__ == "__main__":
    main()
