#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
家庭财务汇总模块 - 计算家庭总资产和成员间资金往来
"""

import pandas as pd
from typing import Dict, List
import config
import utils

logger = utils.setup_logger(__name__)


def calculate_bank_balance_summary(df: pd.DataFrame, entity_name: str) -> Dict:
    """
    计算银行账户余额汇总（截至最后交易日期）

    Args:
        df: 交易DataFrame（需包含 account_number/本方账号, balance/余额(元), date/交易时间 列）
        entity_name: 实体名称

    Returns:
        Dict: {
            'total_balance': 总余额,
            'account_count': 账户数量,
            'last_date': 最后交易日期,
            'accounts': [{'account': 账号, 'balance': 余额, 'last_date': 最后日期}...]
        }
    """
    df = df.copy()

    # 列名映射
    col_map = {"本方账号": "account_number", "余额(元)": "balance", "交易时间": "date"}
    for cn, en in col_map.items():
        if cn in df.columns and en not in df.columns:
            df[en] = df[cn]

    # 确保必要列存在
    if "account_number" not in df.columns or "balance" not in df.columns:
        logger.warning(f"{entity_name}: 缺少账号或余额列")
        return {
            "total_balance": 0,
            "account_count": 0,
            "accounts": [],
            "last_date": None,
        }

    # 按账户分组，取最后一笔交易的余额
    df_sorted = df.sort_values("date")
    last_records = df_sorted.groupby("account_number").last().reset_index()

    accounts = []
    for _, row in last_records.iterrows():
        acct = str(row["account_number"])
        balance = row.get("balance", 0) or 0
        if pd.notna(balance) and balance != 0:
            accounts.append(
                {
                    "account": acct,
                    "balance": float(balance),
                    "last_date": row.get("date"),
                }
            )

    # 按余额降序排序
    accounts.sort(key=lambda x: x["balance"], reverse=True)

    total_balance = sum(a["balance"] for a in accounts)
    last_date = df["date"].max() if "date" in df.columns else None

    return {
        "total_balance": total_balance,
        "account_count": len(accounts),
        "accounts": accounts,
        "last_date": last_date,
    }


def calculate_family_transfers(
    df: pd.DataFrame, entity_name: str, family_members: List[str]
) -> Dict:
    """
    计算与家庭成员间的资金往来

    Args:
        df: 交易DataFrame
        entity_name: 当前实体名称
        family_members: 家庭成员姓名列表

    Returns:
        Dict: {
            'member_name': {
                'received': 收到金额,
                'sent': 转出金额,
                'net': 净收入(正值=收入，负值=转出),
                'received_count': 收到笔数,
                'sent_count': 转出笔数
            },
            ...
            'total': {'received': x, 'sent': y, 'net': z}
        }
    """
    df = df.copy()

    # 列名映射
    col_map = {"交易对手": "counterparty", "收入(元)": "income", "支出(元)": "expense"}
    for cn, en in col_map.items():
        if cn in df.columns and en not in df.columns:
            df[en] = df[cn]

    if "counterparty" not in df.columns:
        return {"total": {"received": 0, "sent": 0, "net": 0}}

    result = {}
    total_received = 0
    total_sent = 0

    for member in family_members:
        if member == entity_name:
            continue  # 跳过自己

        # 查找对手方包含该成员姓名的交易
        mask = df["counterparty"].astype(str).str.contains(member, na=False)
        transfers = df[mask]

        if len(transfers) > 0:
            received = transfers[transfers["income"] > 0]["income"].sum()
            sent = transfers[transfers["expense"] > 0]["expense"].sum()
            received_count = len(transfers[transfers["income"] > 0])
            sent_count = len(transfers[transfers["expense"] > 0])

            result[member] = {
                "received": received,
                "sent": sent,
                "net": received - sent,
                "received_count": received_count,
                "sent_count": sent_count,
            }

            total_received += received
            total_sent += sent

    result["total"] = {
        "received": total_received,
        "sent": total_sent,
        "net": total_received - total_sent,
    }

    return result


def estimate_wealth_balance(wealth_management: Dict) -> Dict:
    """
    估算理财产品期末余额

    基于理财购买/赎回数据估算期末余额

    Args:
        wealth_management: 来自financial_profiler的理财分析结果

    Returns:
        Dict: {
            'purchase': 购买总额,
            'redemption': 赎回总额,
            'interest': 收益总额,
            'net_flow': 净流入(购买-赎回),
            'estimated_initial': 估算期初余额(如果赎回>购买),
            'estimated_final': 估算期末余额
        }
    """
    purchase = wealth_management.get("wealth_purchase", 0)
    redemption = wealth_management.get("wealth_redemption", 0)
    interest = wealth_management.get("wealth_income", 0)

    net_flow = purchase - redemption

    # 如果赎回 > 购买，说明期初有存量
    estimated_initial = max(0, redemption - purchase)

    # 期末余额估算：
    # 如果净流入为正（购买>赎回），期末余额 = 净流入
    # 如果净流入为负（赎回>购买），说明是消耗存量，期末余额可能接近0
    # 实际期末余额需要从账户余额中获取
    estimated_final = max(0, net_flow)

    return {
        "purchase": purchase,
        "redemption": redemption,
        "interest": interest,
        "net_flow": net_flow,
        "estimated_initial": estimated_initial,
        "estimated_final": estimated_final,
    }


def calculate_family_total_assets(
    balance_summary: Dict,
    properties: List[Dict],
    vehicles: List[Dict],
    wealth_estimate: Dict,
) -> Dict:
    """
    计算家庭总资产

    Args:
        balance_summary: 银行余额汇总
        properties: 房产列表
        vehicles: 车辆列表
        wealth_estimate: 理财余额估算

    Returns:
        Dict: {
            'bank_balance': 银行存款,
            'property_value': 房产价值,
            'vehicle_value': 车辆价值（估算）,
            'wealth_balance': 理财余额,
            'total': 总计
        }
    """
    bank_balance = balance_summary.get("total_balance", 0)

    # 房产价值
    property_value = 0
    for prop in properties:
        price = prop.get("金额", prop.get("价格", 0))
        if isinstance(price, str):
            try:
                price = (
                    float(price.replace("万元", "").replace("万", "").replace(",", ""))
                    * config.UNIT_WAN
                )
            except (ValueError, TypeError):
                price = 0
        property_value += float(price) if price else 0

    # 车辆价值（简单估算：根据购买记录或默认值）
    vehicle_value = len(vehicles) * config.DEFAULT_VEHICLE_VALUE  # 默认每辆车估值

    # 理财余额（从银行余额中已包含，避免重复计算）
    # 这里只用于展示明细
    wealth_balance = wealth_estimate.get("estimated_final", 0)

    # 总资产 = 银行存款 + 房产 + 车辆
    # 注：银行存款已包含理财账户余额
    total = bank_balance + property_value + vehicle_value

    return {
        "bank_balance": bank_balance,
        "property_value": property_value,
        "vehicle_value": vehicle_value,
        "wealth_balance": wealth_balance,
        "total": total,
        "property_count": len(properties),
        "vehicle_count": len(vehicles),
    }


def generate_family_finance_report(
    entity_name: str,
    df: pd.DataFrame,
    profile: Dict,
    family_members: List[str],
    properties: List[Dict] = None,
    vehicles: List[Dict] = None,
) -> str:
    """
    生成家庭财务汇总报告文本
    """
    properties = properties or []
    vehicles = vehicles or []

    # 1. 银行余额汇总
    balance_summary = calculate_bank_balance_summary(df, entity_name)

    # 2. 家庭成员资金往来
    family_transfers = calculate_family_transfers(df, entity_name, family_members)

    # 3. 理财余额估算
    wealth_mgmt = profile.get("wealth_management", {})
    wealth_estimate = estimate_wealth_balance(wealth_mgmt)

    # 4. 家庭总资产
    total_assets = calculate_family_total_assets(
        balance_summary, properties, vehicles, wealth_estimate
    )

    # 生成报告文本
    lines = []
    lines.append(f"\n  4. 家庭财务汇总")

    # 银行存款
    lines.append(
        f"     【银行存款】(截至 {balance_summary['last_date'].strftime('%Y-%m-%d') if balance_summary.get('last_date') else '最后交易日'})"
    )
    lines.append(f"     账户总数: {balance_summary['account_count']} 个")
    lines.append(
        f"     存款余额合计: {utils.format_currency(balance_summary['total_balance'])}"
    )

    # 显示Top 5账户
    if balance_summary["accounts"]:
        lines.append(f"     主要账户余额:")
        for i, acct in enumerate(balance_summary["accounts"][:5], 1):
            acct_display = utils.safe_account_display(acct["account"])
            lines.append(
                f"       {i}. {acct_display}: {utils.format_currency(acct['balance'])}"
            )
        if len(balance_summary["accounts"]) > 5:
            lines.append(
                f"       (还有 {len(balance_summary['accounts']) - 5} 个账户未显示)"
            )

    # 理财产品分析
    lines.append(f"     【理财产品分析】")
    lines.append(
        f"     期间购买: {utils.format_currency(wealth_estimate['purchase'])} | 期间赎回: {utils.format_currency(wealth_estimate['redemption'])}"
    )
    if wealth_estimate["estimated_initial"] > 0:
        lines.append(
            f"     推算期初存量: {utils.format_currency(wealth_estimate['estimated_initial'])} (赎回金额大于购买，说明期初有理财存量)"
        )
    lines.append(f"     理财收益: {utils.format_currency(wealth_estimate['interest'])}")

    # 家庭成员资金往来
    if any(m for m in family_transfers if m != "total"):
        lines.append(f"     【与家庭成员资金往来】")
        for member, data in family_transfers.items():
            if member == "total":
                continue
            net_desc = "净收入" if data["net"] >= 0 else "净转出"
            lines.append(
                f"       {member}: 收到 {utils.format_currency(data['received'])}({data['received_count']}笔) / 转出 {utils.format_currency(data['sent'])}({data['sent_count']}笔) → {net_desc} {utils.format_currency(abs(data['net']))}"
            )

        total = family_transfers["total"]
        total_net_desc = "净收入" if total["net"] >= 0 else "净转出"
        lines.append(
            f"       合计: {total_net_desc} {utils.format_currency(abs(total['net']))}"
        )

    # 家庭总资产
    lines.append(f"     【资产估值】")
    lines.append(
        f"     银行存款(含理财): {utils.format_currency(total_assets['bank_balance'])}"
    )
    if total_assets["property_count"] > 0:
        lines.append(
            f"     房产({total_assets['property_count']}套): {utils.format_currency(total_assets['property_value'])}"
        )
    if total_assets["vehicle_count"] > 0:
        lines.append(
            f"     车辆({total_assets['vehicle_count']}辆): {utils.format_currency(total_assets['vehicle_value'])} (估值)"
        )
    lines.append(f"     ────────────────────")
    lines.append(f"     资产估值合计: {utils.format_currency(total_assets['total'])}")

    return "\n".join(lines)


# ========== Phase 3: 家庭汇总计算 (2026-01-20 新增) ==========


def calculate_family_summary(
    all_profiles: Dict[str, Dict],
    family_members: List[str],
    properties: List[Dict] = None,
    vehicles: List[Dict] = None,
) -> Dict:
    """
    计算家庭汇总数据

    【Phase 3 - 2026-01-20】
    功能:
    1. 汇总所有家庭成员的资产
    2. 汇总所有家庭成员的收支
    3. 识别并剔除家庭成员间的互转
    4. 计算家庭真实净流入/净流出

    Args:
        all_profiles: 所有成员的画像数据 {name: profile}
        family_members: 家庭成员姓名列表
        properties: 房产列表(可选)
        vehicles: 车辆列表(可选)

    Returns:
        家庭汇总字典,包含:
        - family_members: 家庭成员列表
        - total_assets: 家庭总资产
        - total_income_expense: 家庭总收支(剔除互转)
        - member_transfers: 成员间互转明细
    """
    logger.info(f"正在计算家庭汇总(成员数: {len(family_members)})...")

    if not family_members:
        logger.warning("家庭成员列表为空")
        return {
            "family_members": [],
            "total_assets": {},
            "total_income_expense": {},
            "member_transfers": {},
        }

    # 1. 汇总家庭资产
    total_bank_balance = 0.0
    total_wealth_balance = 0.0

    for member in family_members:
        if member not in all_profiles:
            continue

        profile = all_profiles[member]
        if not profile.get("has_data"):
            continue

        # 银行余额(从summary中获取)
        summary = profile.get("summary", {})
        # 注: 这里简化处理,实际应该从最后交易的余额计算
        # 但由于没有直接的余额字段,我们使用净流入作为参考
        net_flow = summary.get("net_flow", 0)
        total_bank_balance += net_flow

        # 理财余额
        wealth_mgmt = profile.get("wealth_management", {})
        estimated_holding = wealth_mgmt.get("estimated_holding", 0)
        total_wealth_balance += estimated_holding

    # 房产和车辆价值
    property_value = 0.0
    if properties:
        for prop in properties:
            price = prop.get("金额", prop.get("价格", 0))
            if isinstance(price, str):
                try:
                    price = (
                        float(
                            price.replace("万元", "").replace("万", "").replace(",", "")
                        )
                        * config.UNIT_WAN
                    )
                except (ValueError, TypeError):
                    price = 0
            property_value += float(price) if price else 0

    vehicle_value = len(vehicles) * config.DEFAULT_VEHICLE_VALUE if vehicles else 0

    total_assets = {
        "bank_balance": total_bank_balance,
        "property_value": property_value,
        "vehicle_value": vehicle_value,
        "wealth_balance": total_wealth_balance,
        "total": total_bank_balance
        + property_value
        + vehicle_value
        + total_wealth_balance,
        "property_count": len(properties) if properties else 0,
        "vehicle_count": len(vehicles) if vehicles else 0,
    }

    # 2. 计算成员间互转（遍历原始交易数据）
    member_transfers = {}
    total_family_transfers = 0.0

    for member in family_members:
        if member not in all_profiles:
            continue

        profile = all_profiles[member]
        if not profile.get("has_data"):
            continue

        # 从理财管理数据中获取自我转账记录（包含家庭成员间互转）
        wealth_mgmt = profile.get("wealth_management", {})
        transfer_records = wealth_mgmt.get("self_transfer_transactions", [])

        # 统计与其他家庭成员的互转
        to_family = 0.0
        from_family = 0.0
        transfer_details = []

        # 遍历转账记录，筛选出家庭成员间的互转
        for record in transfer_records:
            counterparty = record.get("交易对手", "")
            income = record.get("收入", 0) or 0
            expense = record.get("支出", 0) or 0

            # 检查交易对手是否是家庭成员
            if counterparty in family_members and counterparty != member:
                # 这是家庭成员间的互转
                if income > 0:
                    from_family += income
                    transfer_details.append(
                        {
                            "counterparty": counterparty,
                            "amount": income,
                            "direction": "in",
                            "date": record.get("日期", ""),
                        }
                    )
                if expense > 0:
                    to_family += expense
                    transfer_details.append(
                        {
                            "counterparty": counterparty,
                            "amount": expense,
                            "direction": "out",
                            "date": record.get("日期", ""),
                        }
                    )

        member_transfers[member] = {
            "to_family": to_family,
            "from_family": from_family,
            "net": from_family - to_family,
            "transfer_details": transfer_details,
        }

        # 累计家庭内部互转总额（只计算单方向）
        total_family_transfers += to_family

    # 3. 汇总家庭收支(剔除互转)
    total_income = 0.0
    total_expense = 0.0

    for member in family_members:
        if member not in all_profiles:
            continue

        profile = all_profiles[member]
        if not profile.get("has_data"):
            continue

        summary = profile.get("summary", {})
        total_income += summary.get("total_income", 0)
        total_expense += summary.get("total_expense", 0)

    # 剔除互转（互转会被双方都记录，所以家庭内部互转不应该计入家庭收支）
    # 家庭对外收入 = 总收入 - 家庭成员转入
    # 家庭对外支出 = 总支出 - 家庭成员转出
    total_transfers_in = sum(m["from_family"] for m in member_transfers.values())
    total_transfers_out = sum(m["to_family"] for m in member_transfers.values())

    external_income = total_income - total_transfers_in
    external_expense = total_expense - total_transfers_out
    net_flow = external_income - external_expense

    logger.info(
        f"家庭汇总完成: 总资产{utils.format_currency(total_assets['total'])}, "
        f"对外净流入{utils.format_currency(net_flow)} (剔除内部互转{utils.format_currency(total_transfers_in)}转入/{utils.format_currency(total_transfers_out)}转出)"
    )

    # 【修复】返回扁平化结构，兼容前端
    return {
        "family_members": family_members,
        "total_assets": total_assets,
        "total_income": total_income,
        "total_expense": total_expense,
        "internal_transfers_in": total_transfers_in,  # 家庭成员转入总额
        "internal_transfers_out": total_transfers_out,  # 家庭成员转出总额
        "external_income": external_income,
        "external_expense": external_expense,
        "net_flow": net_flow,
        "member_transfers": member_transfers,
    }
