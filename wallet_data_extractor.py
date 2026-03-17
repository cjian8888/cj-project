#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电子钱包补充数据提取器

目标：
1. 解析支付宝注册信息/账户明细
2. 解析微信注册信息/登录轨迹/财付通注册信息/财付通交易
3. 以“主体补充摘要”而非“银行流水替代品”的方式输出缓存
"""

from __future__ import annotations

import csv
import io
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

import pandas as pd

import utils
from utils.safe_types import (
    normalize_column_name,
    safe_datetime,
    safe_float,
    safe_int,
    safe_str,
)

logger = utils.setup_logger(__name__)

OUTPUT_DIR_MARKERS = {"output", "cleaned_data", "analysis_results", "analysis_cache"}
WALLET_PATH_MARKERS = ("电子钱包", "wallet", "ewallet", "zfb+wx", "wx+zfb")


def empty_wallet_data() -> Dict[str, Any]:
    """返回空的电子钱包补充数据结构。"""
    return {
        "available": False,
        "directoryPolicy": {
            "recommendedPath": "补充数据/电子钱包/批次_YYYYMMDD/",
            "lateArrivalSupported": True,
            "mainChainUnaffected": True,
            "scanExclusionEnabled": True,
        },
        "sourceStats": {
            "alipayRegistrationFiles": 0,
            "alipayTransactionFiles": 0,
            "wechatRegistrationFiles": 0,
            "wechatLoginFiles": 0,
            "tenpayRegistrationFiles": 0,
            "tenpayTransactionFiles": 0,
        },
        "summary": {
            "subjectCount": 0,
            "coreMatchedSubjectCount": 0,
            "alipayAccountCount": 0,
            "alipayTransactionCount": 0,
            "wechatAccountCount": 0,
            "tenpayAccountCount": 0,
            "tenpayTransactionCount": 0,
            "loginEventCount": 0,
            "unmatchedWechatCount": 0,
        },
        "subjects": [],
        "subjectsByName": {},
        "subjectsById": {},
        "unmatchedWechatAccounts": [],
        "alerts": [],
        "notes": [
            "未检测到电子钱包补充数据目录或有效样本文件。",
            "推荐目录: <inputDirectory>/补充数据/电子钱包/批次_YYYYMMDD/",
        ],
    }


def empty_wallet_artifact_details() -> Dict[str, List[Dict[str, Any]]]:
    """返回电子钱包专项产物所需的规范化明细结构。"""
    return {
        "sourceFiles": [],
        "alipayRegistrationRows": [],
        "alipayTransactionRows": [],
        "wechatRegistrationRows": [],
        "wechatLoginRows": [],
        "tenpayRegistrationRows": [],
        "tenpayTransactionRows": [],
    }


def empty_wallet_artifact_bundle() -> Dict[str, Any]:
    """返回空的电子钱包专项产物 bundle。"""
    return {
        "walletData": empty_wallet_data(),
        "artifacts": empty_wallet_artifact_details(),
    }


def extract_wallet_artifact_bundle(
    data_dir: str,
    known_person_names: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """提取电子钱包主体摘要及专项产物所需的规范化明细。"""
    if not data_dir or not os.path.exists(data_dir):
        return empty_wallet_artifact_bundle()

    known_name_set = {
        str(name).strip() for name in (known_person_names or []) if safe_str(name)
    }
    file_groups = _scan_wallet_source_files(data_dir)
    total_files = sum(len(paths) for paths in file_groups.values())
    if total_files == 0:
        return empty_wallet_artifact_bundle()

    artifact_details = empty_wallet_artifact_details()
    artifact_details["sourceFiles"] = _build_wallet_source_file_rows(data_dir, file_groups)

    raw_subjects: Dict[str, Dict[str, Any]] = {}
    phone_to_subject_ids: Dict[str, Set[str]] = defaultdict(set)
    alias_to_subject_ids: Dict[str, Set[str]] = defaultdict(set)
    unmatched_wechat_accounts: Dict[str, Dict[str, Any]] = {}

    for path in file_groups["alipay_registration"]:
        _parse_alipay_registration_file(
            path,
            raw_subjects,
            phone_to_subject_ids,
            known_name_set,
            artifact_details,
        )

    for path in file_groups["tenpay_registration"]:
        _parse_tenpay_registration_file(
            path,
            raw_subjects,
            phone_to_subject_ids,
            alias_to_subject_ids,
            known_name_set,
            artifact_details,
        )

    for path in file_groups["alipay_transaction"]:
        _parse_alipay_transaction_file(
            path,
            raw_subjects,
            known_name_set,
            artifact_details,
        )

    for path in file_groups["tenpay_transaction"]:
        _parse_tenpay_transaction_file(
            path,
            raw_subjects,
            known_name_set,
            artifact_details,
        )

    for path in file_groups["wechat_registration"]:
        _parse_wechat_registration_file(
            path,
            raw_subjects,
            phone_to_subject_ids,
            alias_to_subject_ids,
            unmatched_wechat_accounts,
            known_name_set,
            artifact_details,
        )

    for path in file_groups["wechat_login"]:
        _parse_wechat_login_file(
            path,
            raw_subjects,
            phone_to_subject_ids,
            alias_to_subject_ids,
            unmatched_wechat_accounts,
            artifact_details,
        )

    wallet_data = _build_wallet_data_payload(
        raw_subjects,
        unmatched_wechat_accounts,
        file_groups,
        known_name_set,
    )
    _normalize_artifact_source_paths(data_dir, artifact_details)
    return {
        "walletData": wallet_data,
        "artifacts": artifact_details,
    }


def extract_wallet_data(
    data_dir: str,
    known_person_names: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """提取电子钱包补充数据主体摘要。"""
    return extract_wallet_artifact_bundle(
        data_dir,
        known_person_names=known_person_names,
    )["walletData"]


def reconcile_wallet_data(
    wallet_data: Dict[str, Any],
    id_to_name_map: Optional[Dict[str, str]] = None,
    known_person_names: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """用主链已有的人名映射补齐 walletData 的主体标识。"""
    if not wallet_data or not wallet_data.get("subjects"):
        return wallet_data or empty_wallet_data()

    known_name_set = {
        str(name).strip() for name in (known_person_names or []) if safe_str(name)
    }
    id_to_name_map = id_to_name_map or {}

    updated_subjects: List[Dict[str, Any]] = []
    subjects_by_name: Dict[str, Dict[str, Any]] = {}
    subjects_by_id: Dict[str, Dict[str, Any]] = {}

    for subject in wallet_data.get("subjects", []):
        if not isinstance(subject, dict):
            continue
        subject_copy = dict(subject)
        subject_id = safe_str(subject_copy.get("subjectId")) or ""
        subject_name = safe_str(subject_copy.get("subjectName"))
        if subject_id and subject_id in id_to_name_map:
            mapped_name = safe_str(id_to_name_map.get(subject_id))
            if mapped_name:
                subject_name = _prefer_subject_name(subject_name, mapped_name)

        if subject_name:
            subject_copy["subjectName"] = subject_name
        matched_to_core = bool(subject_id and subject_id in id_to_name_map)
        if not matched_to_core and subject_name:
            matched_to_core = subject_name in known_name_set
        subject_copy["matchedToCore"] = matched_to_core

        updated_subjects.append(subject_copy)
        if subject_id:
            subjects_by_id[subject_id] = subject_copy
        if subject_name:
            subjects_by_name[subject_name] = subject_copy

    wallet_data["subjects"] = sorted(
        updated_subjects,
        key=lambda item: (
            _subject_total_transactions(item),
            safe_str(item.get("subjectName")) or "",
        ),
        reverse=True,
    )
    wallet_data["subjectsById"] = subjects_by_id
    wallet_data["subjectsByName"] = subjects_by_name
    wallet_data.setdefault("summary", {})["coreMatchedSubjectCount"] = sum(
        1 for subject in wallet_data["subjects"] if subject.get("matchedToCore")
    )
    wallet_data["alerts"] = build_wallet_alerts(wallet_data)
    return wallet_data


def _scan_wallet_source_files(data_dir: str) -> Dict[str, List[str]]:
    file_groups = {
        "alipay_registration": [],
        "alipay_transaction": [],
        "wechat_registration": [],
        "wechat_login": [],
        "tenpay_registration": [],
        "tenpay_transaction": [],
    }

    for root, dirs, files in os.walk(data_dir):
        parts = {part.lower() for part in Path(root).parts}
        if parts & OUTPUT_DIR_MARKERS:
            continue

        for filename in files:
            file_path = os.path.join(root, filename)
            lower_name = filename.lower()
            if filename.endswith((".xlsx", ".xls")):
                if "注册信息" in filename:
                    file_groups["alipay_registration"].append(file_path)
                elif "账户明细" in filename:
                    file_groups["alipay_transaction"].append(file_path)
            elif lower_name.endswith(".txt"):
                if filename.startswith("regInfobasicInfo"):
                    file_groups["wechat_registration"].append(file_path)
                elif "登录轨迹" in filename:
                    file_groups["wechat_login"].append(file_path)
                elif filename.startswith("TenpayRegInfo"):
                    file_groups["tenpay_registration"].append(file_path)
                elif filename.startswith("TenpayTrades"):
                    file_groups["tenpay_transaction"].append(file_path)

    return file_groups


def _build_wallet_source_file_rows(
    data_dir: str,
    file_groups: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    data_type_map = {
        "alipay_registration": "支付宝注册信息",
        "alipay_transaction": "支付宝账户明细",
        "wechat_registration": "微信注册信息",
        "wechat_login": "微信登录轨迹",
        "tenpay_registration": "财付通注册信息",
        "tenpay_transaction": "财付通交易明细",
    }
    rows: List[Dict[str, Any]] = []
    root = Path(data_dir)
    for group_name, paths in file_groups.items():
        for path in sorted(paths):
            file_path = Path(path)
            relative_path = _to_wallet_relative_path(root, file_path)
            rows.append(
                {
                    "dataType": data_type_map.get(group_name, group_name),
                    "groupKey": group_name,
                    "fileName": file_path.name,
                    "relativePath": relative_path,
                    "filePath": relative_path,
                }
            )
    return rows


def _normalize_artifact_source_paths(
    data_dir: str,
    artifact_details: Dict[str, List[Dict[str, Any]]],
) -> None:
    """将专项产物中的来源路径统一归一为相对输入目录的相对路径。"""
    root = Path(data_dir)

    for item in artifact_details.get("sourceFiles", []) or []:
        if not isinstance(item, dict):
            continue
        relative_path = _to_wallet_relative_path(
            root,
            item.get("relativePath") or item.get("filePath") or item.get("fileName"),
        )
        item["relativePath"] = relative_path
        item["filePath"] = relative_path

    for bucket, rows in artifact_details.items():
        if bucket == "sourceFiles" or not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            source_file = row.get("sourceFile")
            if source_file:
                row["sourceFile"] = _to_wallet_relative_path(root, source_file)


def _to_wallet_relative_path(root: Path, value: Any) -> str:
    """将文件路径转换为相对输入目录的路径文本。"""
    text = safe_str(value)
    if not text:
        return ""

    path = Path(text)
    if not path.is_absolute():
        if not root.is_absolute():
            try:
                if path.parts[: len(root.parts)] == root.parts:
                    return str(path)
            except AttributeError:
                pass
            return str(root / path)
        return str(path)

    root_abs = root if root.is_absolute() else (Path.cwd() / root).resolve()
    try:
        relative_path = path.resolve().relative_to(root_abs)
    except ValueError:
        return path.name if path.name else text
    if root.is_absolute():
        return str(relative_path)
    return str(root / relative_path)


def _append_artifact_row(
    artifact_details: Optional[Dict[str, List[Dict[str, Any]]]],
    bucket: str,
    row: Dict[str, Any],
) -> None:
    if not artifact_details or bucket not in artifact_details:
        return
    artifact_details[bucket].append(row)


def _new_subject(subject_id: str, subject_name: Optional[str], known_name_set: Set[str]) -> Dict[str, Any]:
    return {
        "subjectId": subject_id,
        "subjectName": subject_name or subject_id,
        "matchedToCore": bool(subject_name and subject_name in known_name_set),
        "phones": set(),
        "signals": set(),
        "matchBasis": set(),
        "platformPhones": {
            "alipay": set(),
            "wechat": set(),
            "tenpay": set(),
        },
        "platformBankCards": {
            "alipay": set(),
            "tenpay": set(),
        },
        "platformAliases": {
            "wechat": set(),
            "tenpay": set(),
        },
        "alipay": {
            "accountIds": set(),
            "transactionCount": 0,
            "successfulTransactionCount": 0,
            "incomeTotalYuan": 0.0,
            "expenseTotalYuan": 0.0,
            "firstTransactionAt": None,
            "lastTransactionAt": None,
            "topCounterpartyStats": defaultdict(lambda: {"count": 0, "totalAmountYuan": 0.0}),
        },
        "wechat": {
            "wechatAccounts": set(),
            "wechatAliases": set(),
            "tenpayAccounts": set(),
            "tenpayTransactionCount": 0,
            "incomeTotalYuan": 0.0,
            "expenseTotalYuan": 0.0,
            "firstTransactionAt": None,
            "lastTransactionAt": None,
            "loginEventCount": 0,
            "latestLoginAt": None,
            "topCounterpartyStats": defaultdict(lambda: {"count": 0, "totalAmountYuan": 0.0}),
        },
    }


def _ensure_subject(
    raw_subjects: Dict[str, Dict[str, Any]],
    subject_id: str,
    subject_name: Optional[str],
    known_name_set: Set[str],
) -> Dict[str, Any]:
    subject_id = safe_str(subject_id) or ""
    if not subject_id:
        raise ValueError("subject_id 不能为空")

    if subject_id not in raw_subjects:
        raw_subjects[subject_id] = _new_subject(subject_id, subject_name, known_name_set)
        return raw_subjects[subject_id]

    subject = raw_subjects[subject_id]
    preferred_name = _prefer_subject_name(
        safe_str(subject.get("subjectName")),
        subject_name,
    )
    if preferred_name:
        subject["subjectName"] = preferred_name
        if preferred_name in known_name_set:
            subject["matchedToCore"] = True
    return subject


def _parse_alipay_registration_file(
    file_path: str,
    raw_subjects: Dict[str, Dict[str, Any]],
    phone_to_subject_ids: Dict[str, Set[str]],
    known_name_set: Set[str],
    artifact_details: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    try:
        df = pd.read_excel(file_path)
    except Exception as exc:
        logger.warning(f"支付宝注册信息读取失败: {file_path}, {exc}")
        return

    if df is None or df.empty:
        return

    column_map = {normalize_column_name(col): col for col in df.columns}
    for _, row in df.iterrows():
        subject_id = _normalize_person_id(
            row.get(column_map.get("证件号")) or row.get(column_map.get("对应的协查数据"))
        )
        if not subject_id:
            continue

        subject_name = safe_str(row.get(column_map.get("账户名称")))
        subject = _ensure_subject(raw_subjects, subject_id, subject_name, known_name_set)
        subject["matchBasis"].add("实名身份证号")
        subject["signals"].add("存在支付宝实名账户")

        account_id = safe_str(row.get(column_map.get("用户id")))
        login_phone = _normalize_phone(row.get(column_map.get("登录手机")))
        bound_phone = _normalize_phone(row.get(column_map.get("绑定手机")))
        if account_id:
            subject["alipay"]["accountIds"].add(account_id)

        for phone in (bound_phone, login_phone):
            if phone:
                subject["phones"].add(phone)
                subject["platformPhones"]["alipay"].add(phone)
                phone_to_subject_ids[phone].add(subject_id)

        bank_cards = _extract_bank_cards(row.get(column_map.get("绑定银行卡")))
        subject["platformBankCards"]["alipay"].update(bank_cards)
        _append_artifact_row(
            artifact_details,
            "alipayRegistrationRows",
            {
                "sourceFile": file_path,
                "sourceFileName": Path(file_path).name,
                "subjectId": subject_id,
                "subjectName": safe_str(subject.get("subjectName")) or subject_name or "",
                "alipayUserId": account_id or "",
                "loginEmail": safe_str(row.get(column_map.get("登录邮箱"))) or "",
                "loginPhone": login_phone or "",
                "boundPhone": bound_phone or "",
                "registrationTime": safe_datetime(row.get(column_map.get("注册时间"))),
                "cancellationTime": safe_datetime(row.get(column_map.get("注销时间"))),
                "availableBalanceYuan": safe_float(row.get(column_map.get("可用余额"))),
                "bankCardCount": len(bank_cards),
                "bankCards": "; ".join(sorted(bank_cards)),
                "linkedAccounts": safe_str(row.get(column_map.get("关联账户"))) or "",
                "remarks": safe_str(row.get(column_map.get("备注"))) or "",
            },
        )


def _parse_alipay_transaction_file(
    file_path: str,
    raw_subjects: Dict[str, Dict[str, Any]],
    known_name_set: Set[str],
    artifact_details: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    try:
        workbook = pd.read_excel(file_path, sheet_name=None)
    except Exception as exc:
        logger.warning(f"支付宝账户明细读取失败: {file_path}, {exc}")
        return

    for sheet_name, df in workbook.items():
        if df is None or df.empty:
            continue

        subject_id = _normalize_person_id(sheet_name)
        if not subject_id and "对应的协查数据" in df.columns:
            subject_id = _normalize_person_id(df["对应的协查数据"].dropna().astype(str).iloc[0] if not df["对应的协查数据"].dropna().empty else None)
        if not subject_id:
            continue

        user_info_series = df["用户信息"] if "用户信息" in df.columns else pd.Series([], dtype=object)
        subject_name = None
        if not user_info_series.empty:
            subject_name = _extract_party_name(user_info_series.astype(str).iloc[0])

        subject = _ensure_subject(raw_subjects, subject_id, subject_name, known_name_set)
        alipay = subject["alipay"]

        for _, row in df.iterrows():
            amount_yuan = safe_float(row.get("金额（元）")) or 0.0
            direction = safe_str(row.get("收/支")) or ""
            status = safe_str(row.get("交易状态")) or ""
            created_at = safe_datetime(
                row.get("交易创建时间") or row.get("付款时间") or row.get("最近修改时间")
            )
            counterparty = _extract_party_name(row.get("交易对方信息"))
            user_name = _extract_party_name(row.get("用户信息")) or subject_name or safe_str(subject.get("subjectName")) or ""
            is_effective = _is_effective_alipay_status(status)

            alipay["transactionCount"] += 1
            if is_effective:
                alipay["successfulTransactionCount"] += 1
                if direction == "收入":
                    alipay["incomeTotalYuan"] += amount_yuan
                elif direction == "支出":
                    alipay["expenseTotalYuan"] += amount_yuan

                if counterparty:
                    _update_counterparty_stat(
                        alipay["topCounterpartyStats"],
                        counterparty,
                        amount_yuan,
                    )
                _update_time_range(alipay, created_at)

            _append_artifact_row(
                artifact_details,
                "alipayTransactionRows",
                {
                    "sourceFile": file_path,
                    "sourceFileName": Path(file_path).name,
                    "sourceSheet": sheet_name,
                    "subjectId": subject_id,
                    "subjectName": user_name,
                    "transactionId": safe_str(row.get("交易号")) or "",
                    "merchantOrderNo": safe_str(row.get("商户订单号")) or "",
                    "createdAt": safe_datetime(row.get("交易创建时间")),
                    "paidAt": safe_datetime(row.get("付款时间")),
                    "modifiedAt": safe_datetime(row.get("最近修改时间")),
                    "transactionSource": safe_str(row.get("交易来源地")) or "",
                    "transactionType": safe_str(row.get("类型")) or "",
                    "userInfo": safe_str(row.get("用户信息")) or "",
                    "counterpartyName": counterparty or "",
                    "counterpartyInfo": safe_str(row.get("交易对方信息")) or "",
                    "itemName": safe_str(row.get("消费名称")) or "",
                    "amountYuan": round(amount_yuan, 2),
                    "direction": direction,
                    "status": status,
                    "isEffective": is_effective,
                    "paymentMethod": safe_str(row.get("支付方式")) or "",
                    "clearingSerialNo": safe_str(row.get("清算流水号")) or "",
                    "remarks": safe_str(row.get("备注")) or "",
                },
            )


def _parse_tenpay_registration_file(
    file_path: str,
    raw_subjects: Dict[str, Dict[str, Any]],
    phone_to_subject_ids: Dict[str, Set[str]],
    alias_to_subject_ids: Dict[str, Set[str]],
    known_name_set: Set[str],
    artifact_details: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    path = Path(file_path)
    subject_id = _extract_subject_id_from_path(path)
    account_alias = path.parent.name
    if not subject_id:
        return

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning(f"财付通注册信息读取失败: {file_path}, {exc}")
        return

    bank_cards: Set[str] = set()
    bound_phones: Set[str] = set()
    subject_name = None
    for line in text.splitlines():
        if not line.strip() or line.startswith("账户状态") or line.startswith("注销信息") or line.startswith("账号\t注册姓名"):
            continue
        columns = [part.strip() for part in line.split("\t")]
        if len(columns) < 9:
            continue
        if columns[2]:
            subject_name = columns[2]
        if columns[5]:
            phone = _normalize_phone(columns[5])
            if phone:
                bound_phones.add(phone)
        if columns[8]:
            bank_cards.update(_extract_bank_cards(columns[8]))
        current_row_cards = _extract_bank_cards(columns[8])
        _append_artifact_row(
            artifact_details,
            "tenpayRegistrationRows",
            {
                "sourceFile": file_path,
                "sourceFileName": path.name,
                "subjectId": subject_id,
                "subjectName": columns[2] or "",
                "tenpayAccountAlias": columns[1] or account_alias,
                "accountStatus": columns[0] or "",
                "registeredAt": safe_datetime(columns[3]),
                "boundPhone": _normalize_phone(columns[5]) or "",
                "bindingStatus": columns[6] or "",
                "bankInfo": columns[7] or "",
                "bankCardCount": len(current_row_cards),
                "bankCards": "; ".join(sorted(current_row_cards)),
            },
        )

    subject = _ensure_subject(raw_subjects, subject_id, subject_name, known_name_set)
    wechat = subject["wechat"]
    wechat["tenpayAccounts"].add(account_alias)
    subject["platformAliases"]["tenpay"].add(account_alias)
    alias_to_subject_ids[account_alias].add(subject_id)
    subject["matchBasis"].add("财付通实名身份证号")
    subject["signals"].add("存在财付通实名账户")
    subject["platformBankCards"]["tenpay"].update(bank_cards)

    for bound_phone in bound_phones:
        subject["phones"].add(bound_phone)
        subject["platformPhones"]["tenpay"].add(bound_phone)
        phone_to_subject_ids[bound_phone].add(subject_id)


def _parse_tenpay_transaction_file(
    file_path: str,
    raw_subjects: Dict[str, Dict[str, Any]],
    known_name_set: Set[str],
    artifact_details: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    path = Path(file_path)
    subject_id = _extract_subject_id_from_path(path)
    account_alias = path.parent.name
    if not subject_id:
        return

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning(f"财付通交易读取失败: {file_path}, {exc}")
        return

    rows = _parse_tsv_rows(text)
    subject = _ensure_subject(raw_subjects, subject_id, None, known_name_set)
    wechat = subject["wechat"]
    wechat["tenpayAccounts"].add(account_alias)
    subject["platformAliases"]["tenpay"].add(account_alias)

    for row in rows:
        amount_fen = safe_int(row.get("交易金额(分)")) or 0
        amount_yuan = amount_fen / 100.0
        direction = safe_str(row.get("借贷类型")) or ""
        transaction_time = safe_datetime(row.get("交易时间"))
        counterparty = _extract_party_name(
            row.get("对手侧账户名称")
            or row.get("第三方账户名称")
            or row.get("第三方账户名称__1")
        )

        wechat["tenpayTransactionCount"] += 1
        if direction == "入":
            wechat["incomeTotalYuan"] += amount_yuan
        elif direction == "出":
            wechat["expenseTotalYuan"] += amount_yuan

        if counterparty:
            _update_counterparty_stat(
                wechat["topCounterpartyStats"],
                counterparty,
                amount_yuan,
            )
        _update_time_range(wechat, transaction_time)
        counterparty_receive_amount_fen = safe_int(row.get("对手方接收金额(分)"))
        _append_artifact_row(
            artifact_details,
            "tenpayTransactionRows",
            {
                "sourceFile": file_path,
                "sourceFileName": path.name,
                "subjectId": subject_id,
                "subjectName": safe_str(row.get("用户侧账号名称")) or safe_str(subject.get("subjectName")) or "",
                "tenpayAccountAlias": account_alias,
                "transactionId": safe_str(row.get("交易单号")) or "",
                "masterOrderNo": safe_str(row.get("大单号")) or "",
                "direction": direction,
                "businessType": safe_str(row.get("交易业务类型")) or "",
                "purposeType": safe_str(row.get("交易用途类型")) or "",
                "transactionTime": transaction_time,
                "amountFen": amount_fen,
                "amountYuan": round(amount_yuan, 2),
                "balanceFen": safe_int(row.get("账户余额(分)")),
                "userBankCard": safe_str(row.get("用户银行卡号")) or "",
                "userNetSerialNo": safe_str(row.get("用户侧网银联单号")) or "",
                "networkChannel": safe_str(row.get("网联/银联")) or "",
                "thirdPartyAccountName": safe_str(row.get("第三方账户名称")) or "",
                "counterpartyId": safe_str(row.get("对手方ID")) or "",
                "counterpartyName": counterparty or "",
                "counterpartyBankCard": safe_str(row.get("对手方银行卡号")) or "",
                "counterpartyBankName": safe_str(row.get("对手侧银行名称")) or "",
                "counterpartyNetSerialNo": safe_str(row.get("对手侧网银联单号")) or "",
                "counterpartyNetworkChannel": safe_str(row.get("网联/银联__1")) or "",
                "counterpartyReceivedAt": safe_datetime(row.get("对手方接收时间")),
                "counterpartyReceivedAmountFen": counterparty_receive_amount_fen,
                "counterpartyReceivedAmountYuan": round((counterparty_receive_amount_fen or 0) / 100.0, 2),
                "remark1": safe_str(row.get("备注1")) or "",
                "remark2": safe_str(row.get("备注2")) or "",
            },
        )


def _parse_wechat_registration_file(
    file_path: str,
    raw_subjects: Dict[str, Dict[str, Any]],
    phone_to_subject_ids: Dict[str, Set[str]],
    alias_to_subject_ids: Dict[str, Set[str]],
    unmatched_wechat_accounts: Dict[str, Dict[str, Any]],
    known_name_set: Set[str],
    artifact_details: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    path = Path(file_path)
    phone = _normalize_phone(path.parent.name)
    if not phone:
        return

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning(f"微信注册信息读取失败: {file_path}, {exc}")
        return

    info = _parse_key_value_text(text)
    wxid = safe_str(info.get("微信号"))
    alias = safe_str(info.get("别名"))
    nickname = safe_str(info.get("昵称"))
    registered_at = safe_datetime(info.get("注册时间"))
    current_bound_phone = _normalize_phone(
        info.get("当前绑定手机号") or info.get("绑定手机号")
    )

    candidate_subject_id = _select_unique_match(phone_to_subject_ids.get(phone, set()))
    match_basis = None
    if candidate_subject_id:
        match_basis = "手机号"
    else:
        for alias_value in (alias, wxid):
            if not alias_value:
                continue
            candidate_subject_id = _select_unique_match(
                alias_to_subject_ids.get(alias_value, set())
            )
            if candidate_subject_id:
                match_basis = "别名" if alias_value == alias else "wxid"
                break

    if not candidate_subject_id:
        unmatched_wechat_accounts[phone] = {
            "phone": phone,
            "wxid": wxid or "",
            "alias": alias or "",
            "nickname": nickname or "",
            "registeredAt": registered_at,
            "latestLoginAt": unmatched_wechat_accounts.get(phone, {}).get("latestLoginAt"),
            "loginEventCount": unmatched_wechat_accounts.get(phone, {}).get("loginEventCount", 0),
        }
        _append_artifact_row(
            artifact_details,
            "wechatRegistrationRows",
            {
                "sourceFile": file_path,
                "sourceFileName": path.name,
                "subjectId": "",
                "subjectName": nickname or "",
                "phoneDirectory": phone,
                "currentBoundPhone": current_bound_phone or "",
                "wechatId": wxid or "",
                "wechatAlias": alias or "",
                "nickname": nickname or "",
                "registeredAt": registered_at,
                "matchStatus": "unmatched",
                "matchBasis": "",
            },
        )
        return

    subject = _ensure_subject(raw_subjects, candidate_subject_id, nickname, known_name_set)
    wechat = subject["wechat"]
    if wxid:
        wechat["wechatAccounts"].add(wxid)
    if alias:
        wechat["wechatAliases"].add(alias)
        subject["platformAliases"]["wechat"].add(alias)
    if wxid:
        subject["platformAliases"]["wechat"].add(wxid)
    subject["phones"].add(phone)
    subject["platformPhones"]["wechat"].add(phone)
    subject["signals"].add("存在微信注册信息")
    if match_basis:
        subject["matchBasis"].add(f"微信{match_basis}映射")
    _append_artifact_row(
        artifact_details,
        "wechatRegistrationRows",
        {
            "sourceFile": file_path,
            "sourceFileName": path.name,
            "subjectId": candidate_subject_id,
            "subjectName": safe_str(subject.get("subjectName")) or nickname or "",
            "phoneDirectory": phone,
            "currentBoundPhone": current_bound_phone or "",
            "wechatId": wxid or "",
            "wechatAlias": alias or "",
            "nickname": nickname or "",
            "registeredAt": registered_at,
            "matchStatus": "matched",
            "matchBasis": match_basis or "",
        },
    )


def _parse_wechat_login_file(
    file_path: str,
    raw_subjects: Dict[str, Dict[str, Any]],
    phone_to_subject_ids: Dict[str, Set[str]],
    alias_to_subject_ids: Dict[str, Set[str]],
    unmatched_wechat_accounts: Dict[str, Dict[str, Any]],
    artifact_details: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    path = Path(file_path)
    phone = _normalize_phone(path.parent.name)
    if not phone:
        return

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning(f"微信登录轨迹读取失败: {file_path}, {exc}")
        return

    login_events: List[Dict[str, Any]] = []
    for line in text.splitlines():
        if "CST" not in line:
            continue
        columns = [part.strip() for part in line.split("\t") if part.strip()]
        if not columns:
            continue
        login_time = safe_datetime(columns[0].replace(" +0800 CST", ""))
        if login_time:
            login_events.append(
                {
                    "loginTime": login_time,
                    "ipAddress": columns[1] if len(columns) > 1 else "",
                }
            )

    if not login_events:
        return

    subject_id = _select_unique_match(phone_to_subject_ids.get(phone, set()))
    if subject_id and subject_id in raw_subjects:
        subject = raw_subjects[subject_id]
        wechat = subject["wechat"]
        wechat["loginEventCount"] += len(login_events)
        latest_login = max(event["loginTime"] for event in login_events)
        if not wechat["latestLoginAt"] or latest_login > wechat["latestLoginAt"]:
            wechat["latestLoginAt"] = latest_login
        subject["signals"].add("存在微信登录轨迹")
        for event in login_events:
            _append_artifact_row(
                artifact_details,
                "wechatLoginRows",
                {
                    "sourceFile": file_path,
                    "sourceFileName": path.name,
                    "subjectId": subject_id,
                    "subjectName": safe_str(subject.get("subjectName")) or "",
                    "phoneDirectory": phone,
                    "loginTime": event["loginTime"],
                    "ipAddress": event["ipAddress"],
                    "matchStatus": "matched",
                },
            )
        return

    unmatched = unmatched_wechat_accounts.setdefault(
        phone,
        {
            "phone": phone,
            "wxid": "",
            "alias": "",
            "nickname": "",
            "registeredAt": None,
            "latestLoginAt": None,
            "loginEventCount": 0,
        },
    )
    unmatched["loginEventCount"] += len(login_events)
    latest_login = max(event["loginTime"] for event in login_events)
    if not unmatched["latestLoginAt"] or latest_login > unmatched["latestLoginAt"]:
        unmatched["latestLoginAt"] = latest_login
    for event in login_events:
        _append_artifact_row(
            artifact_details,
            "wechatLoginRows",
            {
                "sourceFile": file_path,
                "sourceFileName": path.name,
                "subjectId": "",
                "subjectName": safe_str(unmatched.get("nickname")) or "",
                "phoneDirectory": phone,
                "loginTime": event["loginTime"],
                "ipAddress": event["ipAddress"],
                "matchStatus": "unmatched",
            },
        )


def _build_wallet_data_payload(
    raw_subjects: Dict[str, Dict[str, Any]],
    unmatched_wechat_accounts: Dict[str, Dict[str, Any]],
    file_groups: Dict[str, List[str]],
    known_name_set: Set[str],
) -> Dict[str, Any]:
    if not raw_subjects and not unmatched_wechat_accounts:
        return empty_wallet_data()

    subjects: List[Dict[str, Any]] = []
    subjects_by_name: Dict[str, Dict[str, Any]] = {}
    subjects_by_id: Dict[str, Dict[str, Any]] = {}

    totals = {
        "alipayAccountCount": 0,
        "alipayTransactionCount": 0,
        "wechatAccountCount": 0,
        "tenpayAccountCount": 0,
        "tenpayTransactionCount": 0,
        "loginEventCount": 0,
    }

    for subject in raw_subjects.values():
        summary = _finalize_subject(subject, known_name_set)
        subjects.append(summary)
        subjects_by_id[summary["subjectId"]] = summary
        if summary.get("subjectName"):
            subjects_by_name[summary["subjectName"]] = summary

        totals["alipayAccountCount"] += summary["platforms"]["alipay"]["accountCount"]
        totals["alipayTransactionCount"] += summary["platforms"]["alipay"]["transactionCount"]
        totals["wechatAccountCount"] += summary["platforms"]["wechat"]["wechatAccountCount"]
        totals["tenpayAccountCount"] += summary["platforms"]["wechat"]["tenpayAccountCount"]
        totals["tenpayTransactionCount"] += summary["platforms"]["wechat"]["tenpayTransactionCount"]
        totals["loginEventCount"] += summary["platforms"]["wechat"]["loginEventCount"]

    subjects.sort(
        key=lambda item: (_subject_total_transactions(item), item.get("subjectName", "")),
        reverse=True,
    )

    notes = [
        "电子钱包数据以主体补充摘要进入 analysis_cache，不写入 cleaned_data。",
        "支付宝侧重点是实名账户与交易明细，微信侧重点是账号映射、登录轨迹与财付通交易。",
    ]
    if unmatched_wechat_accounts:
        notes.append("存在无法自动归并到实名主体的微信账号，请在下一阶段补充手机号/别名映射。")

    alerts = build_wallet_alerts(
        {
            "subjects": subjects,
            "unmatchedWechatAccounts": list(unmatched_wechat_accounts.values()),
        }
    )

    return {
        "available": True,
        "directoryPolicy": {
            "recommendedPath": "补充数据/电子钱包/批次_YYYYMMDD/",
            "lateArrivalSupported": True,
            "mainChainUnaffected": True,
            "scanExclusionEnabled": True,
        },
        "sourceStats": {
            "alipayRegistrationFiles": len(file_groups["alipay_registration"]),
            "alipayTransactionFiles": len(file_groups["alipay_transaction"]),
            "wechatRegistrationFiles": len(file_groups["wechat_registration"]),
            "wechatLoginFiles": len(file_groups["wechat_login"]),
            "tenpayRegistrationFiles": len(file_groups["tenpay_registration"]),
            "tenpayTransactionFiles": len(file_groups["tenpay_transaction"]),
        },
        "summary": {
            "subjectCount": len(subjects),
            "coreMatchedSubjectCount": sum(1 for item in subjects if item["matchedToCore"]),
            "alipayAccountCount": totals["alipayAccountCount"],
            "alipayTransactionCount": totals["alipayTransactionCount"],
            "wechatAccountCount": totals["wechatAccountCount"],
            "tenpayAccountCount": totals["tenpayAccountCount"],
            "tenpayTransactionCount": totals["tenpayTransactionCount"],
            "loginEventCount": totals["loginEventCount"],
            "unmatchedWechatCount": len(unmatched_wechat_accounts),
        },
        "subjects": subjects,
        "subjectsByName": subjects_by_name,
        "subjectsById": subjects_by_id,
        "unmatchedWechatAccounts": sorted(
            unmatched_wechat_accounts.values(),
            key=lambda item: item.get("phone", ""),
        ),
        "alerts": alerts,
        "notes": notes,
    }


def build_wallet_alerts(wallet_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """基于电子钱包主体摘要生成第一批风险预警。"""
    if not isinstance(wallet_data, dict):
        return []

    alerts: List[Dict[str, Any]] = []
    subjects = wallet_data.get("subjects", []) or []
    for subject in subjects:
        if not isinstance(subject, dict):
            continue

        subject_name = safe_str(subject.get("subjectName")) or safe_str(subject.get("subjectId")) or "未知主体"
        subject_id = safe_str(subject.get("subjectId")) or ""
        matched_to_core = bool(subject.get("matchedToCore"))
        platforms = subject.get("platforms", {}) or {}
        alipay = platforms.get("alipay", {}) or {}
        wechat = platforms.get("wechat", {}) or {}
        cross = subject.get("crossSignals", {}) or {}

        alipay_total = float(alipay.get("incomeTotalYuan", 0) or 0) + float(alipay.get("expenseTotalYuan", 0) or 0)
        tenpay_total = float(wechat.get("incomeTotalYuan", 0) or 0) + float(wechat.get("expenseTotalYuan", 0) or 0)
        combined_total = alipay_total + tenpay_total
        combined_tx_count = int(alipay.get("transactionCount", 0) or 0) + int(wechat.get("tenpayTransactionCount", 0) or 0)
        latest_date = _latest_wallet_activity_time(subject)

        if matched_to_core and combined_total >= 300000 and combined_tx_count >= 100:
            alerts.append(
                _build_wallet_alert_record(
                    alert_type="wallet_large_scale",
                    person=subject_name,
                    counterparty="电子钱包总体",
                    date=latest_date,
                    amount=round(combined_total, 2),
                    description=f"{subject_name}电子钱包交易规模较大，支付宝/财付通合计{combined_tx_count}笔、{combined_total / 10000:.1f}万元。",
                    risk_level="high" if combined_total >= 1000000 else "medium",
                    risk_reason="第三方支付明细规模明显，建议结合银行流水核对资金来源及用途。",
                    subject_id=subject_id,
                    matched_to_core=matched_to_core,
                    transaction_count=combined_tx_count,
                    evidence_summary=f"支付宝/财付通合计{combined_tx_count}笔，累计{combined_total / 10000:.1f}万元。",
                )
            )

        if (
            not matched_to_core
            and (combined_total >= 300000 or combined_tx_count >= 100)
        ):
            alerts.append(
                _build_wallet_alert_record(
                    alert_type="wallet_unmapped_large_scale",
                    person=subject_name,
                    counterparty="待确认电子钱包主体",
                    date=latest_date,
                    amount=round(combined_total, 2),
                    description=f"{subject_name}尚未归并到主链主体，但电子钱包累计{combined_tx_count}笔、{combined_total / 10000:.1f}万元，建议优先人工核实。",
                    risk_level="high" if (combined_total >= 1000000 or combined_tx_count >= 300) else "medium",
                    risk_reason="补充数据中存在规模较大的未映射电子钱包主体，可能对应尚未确认的重点核查对象。",
                    subject_id=subject_id,
                    matched_to_core=matched_to_core,
                    transaction_count=combined_tx_count,
                    evidence_summary=f"未命中主链，电子钱包合计{combined_tx_count}笔，累计{combined_total / 10000:.1f}万元。",
                )
            )

        if matched_to_core and int(cross.get("bankCardOverlapCount", 0) or 0) >= 2 and int(cross.get("aliasMatchCount", 0) or 0) >= 1:
            alerts.append(
                _build_wallet_alert_record(
                    alert_type="wallet_cross_platform_binding",
                    person=subject_name,
                    counterparty="跨平台账户映射",
                    date=latest_date,
                    amount=round(combined_total, 2),
                    description=f"{subject_name}存在{cross.get('bankCardOverlapCount', 0)}张跨平台绑定银行卡重叠，且微信别名与财付通账号存在重叠。",
                    risk_level="medium",
                    risk_reason="电子钱包与财付通控制关系明确，可用于补强同一人控制多个支付通道的证据。",
                    subject_id=subject_id,
                    matched_to_core=matched_to_core,
                    transaction_count=combined_tx_count,
                    overlap_count=int(cross.get("bankCardOverlapCount", 0) or 0) + int(cross.get("aliasMatchCount", 0) or 0),
                    evidence_summary=f"跨平台重叠银行卡{int(cross.get('bankCardOverlapCount', 0) or 0)}张，别名重叠{int(cross.get('aliasMatchCount', 0) or 0)}组。",
                )
            )

        if matched_to_core:
            for counterparty in (alipay.get("topCounterparties", []) or [])[:3]:
                if not isinstance(counterparty, dict):
                    continue
                total_amount = float(counterparty.get("totalAmountYuan", 0) or 0)
                count = int(counterparty.get("count", 0) or 0)
                if total_amount >= 50000 and count >= 5:
                    counterparty_name = safe_str(counterparty.get("name")) or "未知对手方"
                    alerts.append(
                        _build_wallet_alert_record(
                            alert_type="wallet_dense_counterparty",
                            person=subject_name,
                            counterparty=counterparty_name,
                            date=latest_date,
                            amount=round(total_amount, 2),
                            description=f"{subject_name}在支付宝与{counterparty_name}往来{count}笔，累计{total_amount / 10000:.1f}万元。",
                            risk_level="medium",
                            risk_reason="高频或大额电子钱包对手方值得结合交易用途进一步核验。",
                            subject_id=subject_id,
                            matched_to_core=matched_to_core,
                            transaction_count=count,
                            evidence_summary=f"支付宝对手方{counterparty_name}往来{count}笔，累计{total_amount / 10000:.1f}万元。",
                        )
                    )

            for counterparty in (wechat.get("topCounterparties", []) or [])[:3]:
                if not isinstance(counterparty, dict):
                    continue
                total_amount = float(counterparty.get("totalAmountYuan", 0) or 0)
                count = int(counterparty.get("count", 0) or 0)
                if total_amount >= 50000 and count >= 5:
                    counterparty_name = safe_str(counterparty.get("name")) or "未知对手方"
                    alerts.append(
                        _build_wallet_alert_record(
                            alert_type="wallet_dense_counterparty",
                            person=subject_name,
                            counterparty=counterparty_name,
                            date=latest_date,
                            amount=round(total_amount, 2),
                            description=f"{subject_name}在财付通与{counterparty_name}往来{count}笔，累计{total_amount / 10000:.1f}万元。",
                            risk_level="high" if total_amount >= 100000 else "medium",
                            risk_reason="微信/财付通高频大额对手方应纳入重点核查名单。",
                            subject_id=subject_id,
                            matched_to_core=matched_to_core,
                            transaction_count=count,
                            evidence_summary=f"财付通对手方{counterparty_name}往来{count}笔，累计{total_amount / 10000:.1f}万元。",
                        )
                    )

    for account in wallet_data.get("unmatchedWechatAccounts", []) or []:
        if not isinstance(account, dict):
            continue
        phone = safe_str(account.get("phone")) or "未知手机号"
        alerts.append(
            _build_wallet_alert_record(
                alert_type="wallet_unmatched_account",
                person=phone,
                counterparty=safe_str(account.get("nickname")) or "待映射微信账号",
                date=safe_str(account.get("latestLoginAt")) or safe_str(account.get("registeredAt")) or "",
                amount=0,
                description=f"存在未自动归并的微信账号，手机号{phone}，昵称{safe_str(account.get('nickname')) or '未知'}。",
                risk_level="medium",
                risk_reason="补充数据中存在待映射账号，需人工确认其与当前核查对象的对应关系。",
                matched_to_core=False,
                evidence_summary=f"待映射微信账号，手机号{phone}，登录{int(account.get('loginEventCount', 0) or 0)}次。",
            )
        )

    alerts.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(str(item.get("risk_level", "medium")), 3),
            -(float(item.get("amount", 0) or 0)),
            safe_str(item.get("person")) or "",
        )
    )
    return alerts


def _build_wallet_alert_record(
    *,
    alert_type: str,
    person: str,
    counterparty: str,
    date: str,
    amount: float,
    description: str,
    risk_level: str,
    risk_reason: str,
    subject_id: str = "",
    matched_to_core: bool = False,
    transaction_count: int = 0,
    overlap_count: int = 0,
    evidence_summary: str = "",
) -> Dict[str, Any]:
    rule_code = _wallet_alert_rule_code(alert_type)
    risk_score = _wallet_alert_risk_score(
        alert_type=alert_type,
        risk_level=risk_level,
        amount=amount,
        transaction_count=transaction_count,
        overlap_count=overlap_count,
        matched_to_core=matched_to_core,
    )
    confidence = _wallet_alert_confidence(
        alert_type=alert_type,
        risk_level=risk_level,
        amount=amount,
        transaction_count=transaction_count,
        overlap_count=overlap_count,
        matched_to_core=matched_to_core,
    )
    return {
        "alert_type": alert_type,
        "rule_code": rule_code,
        "person": person,
        "subject_id": subject_id,
        "matched_to_core": matched_to_core,
        "counterparty": counterparty,
        "date": date,
        "amount": round(float(amount or 0.0), 2),
        "transaction_count": int(transaction_count or 0),
        "description": description,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "risk_score": risk_score,
        "confidence": confidence,
        "evidence_summary": evidence_summary or description,
    }


def _wallet_alert_rule_code(alert_type: str) -> str:
    return {
        "wallet_large_scale": "WALLET-LARGE-SCALE-001",
        "wallet_unmapped_large_scale": "WALLET-UNMAPPED-LARGE-001",
        "wallet_cross_platform_binding": "WALLET-CROSS-BINDING-001",
        "wallet_dense_counterparty": "WALLET-DENSE-COUNTERPARTY-001",
        "wallet_unmatched_account": "WALLET-UNMATCHED-ACCOUNT-001",
        "wallet_bank_counterparty_overlap": "WALLET-BANK-COUNTERPARTY-001",
        "wallet_bank_quick_outflow": "WALLET-BANK-OUTFLOW-001",
        "wallet_split_collection": "WALLET-SPLIT-COLLECTION-001",
        "wallet_quick_pass_through": "WALLET-QUICK-PASS-THROUGH-001",
        "wallet_night_activity": "WALLET-NIGHT-ACTIVITY-001",
    }.get(alert_type, "WALLET-GENERAL-001")


def _wallet_alert_risk_score(
    *,
    alert_type: str,
    risk_level: str,
    amount: float,
    transaction_count: int,
    overlap_count: int,
    matched_to_core: bool,
) -> float:
    base_score = {
        "high": 58.0,
        "medium": 40.0,
        "low": 22.0,
    }.get(str(risk_level or "medium").lower(), 32.0)
    type_bonus = {
        "wallet_large_scale": 8.0,
        "wallet_unmapped_large_scale": 9.0,
        "wallet_cross_platform_binding": 6.0,
        "wallet_dense_counterparty": 7.0,
        "wallet_unmatched_account": 4.0,
        "wallet_bank_counterparty_overlap": 14.0,
        "wallet_bank_quick_outflow": 16.0,
        "wallet_split_collection": 8.0,
        "wallet_quick_pass_through": 14.0,
        "wallet_night_activity": 6.0,
    }.get(alert_type, 0.0)
    score = base_score + type_bonus

    amount = float(amount or 0.0)
    if amount >= 1_000_000:
        score += 8.0
    elif amount >= 300_000:
        score += 5.0
    elif amount >= 100_000:
        score += 3.0
    elif amount >= 50_000:
        score += 1.5

    transaction_count = int(transaction_count or 0)
    if transaction_count >= 300:
        score += 4.0
    elif transaction_count >= 100:
        score += 2.5
    elif transaction_count >= 30:
        score += 1.0
    elif transaction_count >= 5:
        score += 0.5

    if overlap_count > 0:
        score += min(6.0, float(overlap_count) * 1.5)

    if matched_to_core:
        score += 1.0

    return round(min(score, 92.0), 1)


def _wallet_alert_confidence(
    *,
    alert_type: str,
    risk_level: str,
    amount: float,
    transaction_count: int,
    overlap_count: int,
    matched_to_core: bool,
) -> float:
    confidence = {
        "high": 0.84,
        "medium": 0.76,
        "low": 0.64,
    }.get(str(risk_level or "medium").lower(), 0.7)

    if matched_to_core:
        confidence += 0.08
    if amount and float(amount) >= 300_000:
        confidence += 0.03
    if int(transaction_count or 0) >= 100:
        confidence += 0.02
    if int(overlap_count or 0) >= 2:
        confidence += 0.04
    if alert_type == "wallet_unmapped_large_scale":
        confidence -= 0.08
    elif alert_type == "wallet_unmatched_account":
        confidence -= 0.12
    elif alert_type in {"wallet_bank_counterparty_overlap", "wallet_bank_quick_outflow"}:
        confidence += 0.05
    elif alert_type in {"wallet_split_collection", "wallet_quick_pass_through"}:
        confidence += 0.02
    elif alert_type == "wallet_night_activity":
        confidence -= 0.02

    return round(min(max(confidence, 0.55), 0.96), 2)


def _finalize_subject(subject: Dict[str, Any], known_name_set: Set[str]) -> Dict[str, Any]:
    subject_name = safe_str(subject.get("subjectName")) or safe_str(subject.get("subjectId")) or ""
    matched_to_core = bool(subject.get("matchedToCore")) or subject_name in known_name_set

    phone_overlap_count = len(
        (subject["platformPhones"]["alipay"] & subject["platformPhones"]["wechat"])
        | (subject["platformPhones"]["wechat"] & subject["platformPhones"]["tenpay"])
        | (subject["platformPhones"]["alipay"] & subject["platformPhones"]["tenpay"])
    )
    bank_card_overlap_count = len(
        subject["platformBankCards"]["alipay"] & subject["platformBankCards"]["tenpay"]
    )
    alias_match_count = len(
        subject["platformAliases"]["wechat"] & subject["platformAliases"]["tenpay"]
    )

    signals = set(subject.get("signals", set()))
    if phone_overlap_count:
        signals.add(f"存在 {phone_overlap_count} 组跨平台手机号重叠")
    if bank_card_overlap_count:
        signals.add(f"存在 {bank_card_overlap_count} 张跨平台绑定银行卡重叠")
    if alias_match_count:
        signals.add(f"存在 {alias_match_count} 组微信别名与财付通账号重叠")

    alipay = subject["alipay"]
    wechat = subject["wechat"]

    return {
        "subjectId": subject["subjectId"],
        "subjectName": subject_name,
        "matchedToCore": matched_to_core,
        "phones": sorted(subject["phones"]),
        "crossSignals": {
            "phoneOverlapCount": phone_overlap_count,
            "bankCardOverlapCount": bank_card_overlap_count,
            "aliasMatchCount": alias_match_count,
            "matchBasis": sorted(subject["matchBasis"]),
        },
        "signals": sorted(signals),
        "platforms": {
            "alipay": {
                "accountCount": len(alipay["accountIds"]),
                "transactionCount": alipay["successfulTransactionCount"] or alipay["transactionCount"],
                "rawTransactionCount": alipay["transactionCount"],
                "incomeTotalYuan": round(alipay["incomeTotalYuan"], 2),
                "expenseTotalYuan": round(alipay["expenseTotalYuan"], 2),
                "linkedBankCardCount": len(subject["platformBankCards"]["alipay"]),
                "firstTransactionAt": alipay["firstTransactionAt"],
                "lastTransactionAt": alipay["lastTransactionAt"],
                "topCounterparties": _top_counterparties(alipay["topCounterpartyStats"]),
            },
            "wechat": {
                "wechatAccountCount": len(wechat["wechatAccounts"]),
                "tenpayAccountCount": len(wechat["tenpayAccounts"]),
                "tenpayTransactionCount": wechat["tenpayTransactionCount"],
                "incomeTotalYuan": round(wechat["incomeTotalYuan"], 2),
                "expenseTotalYuan": round(wechat["expenseTotalYuan"], 2),
                "linkedBankCardCount": len(subject["platformBankCards"]["tenpay"]),
                "loginEventCount": wechat["loginEventCount"],
                "firstTransactionAt": wechat["firstTransactionAt"],
                "lastTransactionAt": wechat["lastTransactionAt"],
                "latestLoginAt": wechat["latestLoginAt"],
                "topCounterparties": _top_counterparties(wechat["topCounterpartyStats"]),
            },
        },
    }


def _top_counterparties(stats: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = sorted(
        (
            {
                "name": name,
                "count": int(values.get("count", 0)),
                "totalAmountYuan": round(float(values.get("totalAmountYuan", 0.0)), 2),
            }
            for name, values in stats.items()
            if name
        ),
        key=lambda item: (item["totalAmountYuan"], item["count"], item["name"]),
        reverse=True,
    )
    return ranked[:5]


def _subject_total_transactions(subject: Dict[str, Any]) -> int:
    platforms = subject.get("platforms", {})
    alipay = platforms.get("alipay", {})
    wechat = platforms.get("wechat", {})
    return int(alipay.get("transactionCount", 0)) + int(wechat.get("tenpayTransactionCount", 0))


def _latest_wallet_activity_time(subject: Dict[str, Any]) -> str:
    platforms = subject.get("platforms", {}) or {}
    alipay = platforms.get("alipay", {}) or {}
    wechat = platforms.get("wechat", {}) or {}
    candidates = [
        safe_str(alipay.get("lastTransactionAt")),
        safe_str(wechat.get("lastTransactionAt")),
        safe_str(wechat.get("latestLoginAt")),
    ]
    candidates = [item for item in candidates if item]
    return max(candidates) if candidates else ""


def _update_counterparty_stat(
    stats: Dict[str, Dict[str, Any]],
    counterparty: Optional[str],
    amount_yuan: float,
) -> None:
    name = safe_str(counterparty)
    if not name:
        return
    item = stats[name]
    item["count"] += 1
    item["totalAmountYuan"] += abs(amount_yuan)


def _update_time_range(container: Dict[str, Any], timestamp: Optional[str]) -> None:
    if not timestamp:
        return
    first_key = "firstTransactionAt"
    last_key = "lastTransactionAt"
    if not container.get(first_key) or timestamp < container[first_key]:
        container[first_key] = timestamp
    if not container.get(last_key) or timestamp > container[last_key]:
        container[last_key] = timestamp


def _parse_key_value_text(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for line in text.splitlines():
        raw_line = line.strip()
        if not raw_line:
            continue
        match = re.match(r"^([^:：]+)[:：]\s*(.*)$", raw_line)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        result[key] = value
    return result


def _parse_tsv_rows(text: str) -> List[Dict[str, str]]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter="\t")
    try:
        header = next(reader)
    except StopIteration:
        return []

    header_names: List[str] = []
    duplicate_count: Dict[str, int] = defaultdict(int)
    for name in header:
        base_name = name.strip() or "unknown"
        duplicate_count[base_name] += 1
        if duplicate_count[base_name] > 1:
            header_names.append(f"{base_name}__{duplicate_count[base_name] - 1}")
        else:
            header_names.append(base_name)

    rows: List[Dict[str, str]] = []
    for row in reader:
        if not any(str(item).strip() for item in row):
            continue
        normalized_row = {
            header_names[index]: row[index].strip()
            for index in range(min(len(header_names), len(row)))
        }
        rows.append(normalized_row)
    return rows


def _is_effective_alipay_status(status: str) -> bool:
    if not status:
        return False
    if "关闭" in status or "未完成" in status:
        return False
    keywords = ("成功", "结束", "领取红包", "还款成功", "付款成功", "处理成功", "已经成功")
    return any(keyword in status for keyword in keywords)


def _extract_party_name(value: Any) -> Optional[str]:
    text = safe_str(value)
    if not text:
        return None
    text = text.replace("\t", "").strip()
    match = re.search(r"\(([^()]+)\)\s*$", text)
    if match and match.group(1).strip():
        return match.group(1).strip()
    if "(" in text:
        return text.split("(")[0].strip() or text
    return text


def _extract_bank_cards(value: Any) -> Set[str]:
    text = safe_str(value)
    if not text:
        return set()
    return {match for match in re.findall(r"(\d{8,30})", text)}


def _normalize_phone(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    digits = ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            digits = str(int(round(float(value))))
        except (TypeError, ValueError):
            digits = ""

    if not digits:
        text = safe_str(value)
        if not text:
            return None
        if re.fullmatch(r"[0-9.+\-eE]+", text):
            numeric_value = safe_float(text)
            if numeric_value is not None:
                digits = str(int(round(numeric_value)))

    if not digits:
        text = safe_str(value)
        if not text:
            return None
        digits = "".join(ch for ch in text if ch.isdigit())

    if len(digits) >= 11:
        return digits[-11:]
    return digits or None


def _normalize_person_id(value: Any) -> Optional[str]:
    text = safe_str(value)
    if not text:
        return None
    match = re.search(r"(\d{17}[\dXx])", text)
    if match:
        return match.group(1).upper()
    return None


def _extract_subject_id_from_path(path: Path) -> Optional[str]:
    for part in path.parts:
        subject_id = _normalize_person_id(part)
        if subject_id:
            return subject_id
    return None


def _select_unique_match(candidate_ids: Set[str]) -> Optional[str]:
    if len(candidate_ids) == 1:
        return next(iter(candidate_ids))
    return None


def _prefer_subject_name(current_name: Optional[str], candidate_name: Optional[str]) -> Optional[str]:
    current = safe_str(current_name)
    candidate = safe_str(candidate_name)
    if not current:
        return candidate
    if not candidate:
        return current
    if current == candidate:
        return current
    if _normalize_person_id(current) and not _normalize_person_id(candidate):
        return candidate
    if len(re.findall(r"[\u4e00-\u9fff]", candidate)) > len(re.findall(r"[\u4e00-\u9fff]", current)):
        return candidate
    return current
