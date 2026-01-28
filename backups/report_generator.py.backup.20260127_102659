#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告生成模块 - 资金穿透与关联排查系统
生成Excel底稿和公文格式报告
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List
import config
import utils

logger = utils.setup_logger(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>查询结果分析报告</title>
<style>
    body {
        font-family: "SimSun", "Songti SC", serif;
        background-color: #f0f0f0;
        padding: 20px;
        margin: 0;
    }
    .page {
        background-color: white;
        width: 100%;
        max-width: 210mm;
        min-height: 297mm;
        padding: 20px; /* Reduced padding for screen reading */
        margin: 0 auto; /* Center with margin instead of flex */
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
        box-sizing: border-box;
        font-size: 16px;
        line-height: 1.6;
        color: #000;
        margin-bottom: 20px;
        word-wrap: break-word; /* Ensure long words break */
    }
    @media print {
        body {
            background-color: white;
            padding: 0;
        }
        .page {
            width: 210mm;
            max-width: none;
            padding: 25mm 20mm; /* Restore standard A4 margins for print */
            margin: 0;
            box-shadow: none;
            min-height: auto;
        }
    }
    h1 {
        text-align: center;
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 30px;
    }
    p {
        margin-bottom: 10px;
        text-align: justify;
        text-indent: 2em;
    }
    .section-title {
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
        text-indent: 0;
        font-size: 18px;
    }
    .subsection-title {
        margin-top: 15px;
        margin-bottom: 5px;
        text-indent: 0;
        font-weight: bold;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
        font-size: 14px;
    }
    th, td {
        border: 1px solid #000;
        padding: 5px 8px;
        text-align: center;
    }
    th {
        background-color: #f2f2f2;
        font-weight: bold;
    }
    .highlight {
        color: red;
        background-color: #fff0f0;
    }
    .img-container {
        text-align: center;
        margin: 10px 0;
    }
    img {
        max-width: 100%;
        height: auto;
    }
</style>
</head>
<body>

<!-- 报告封面/正文 -->
<!-- CONTENT_PLACEHOLDER -->

</body>
</html>"""


def _escape_html(text):
    """
    HTML 转义函数，防止 XSS 攻击
    
    Args:
        text: 需要转义的文本
        
    Returns:
        转义后的安全文本
    """
    if text is None:
        return ''
    text_str = str(text)
    # 转义 HTML 特殊字符
    text_str = text_str.replace('&', '&')
    text_str = text_str.replace('<', '<')
    text_str = text_str.replace('>', '>')
    text_str = text_str.replace('"', '"')
    text_str = text_str.replace("'", '&#x27;')
    return text_str


def _safe_format_date(date_val):
    """
    安全格式化日期值
    
    处理 Pandas Timestamp、datetime、字符串等多种日期格式
    
    Args:
        date_val: 日期值（可能是 Timestamp、datetime、字符串或 None）
        
    Returns:
        格式化后的日期字符串 (YYYY-MM-DD) 或空字符串
    """
    if date_val is None:
        return ''
    # 检查是否是 pandas 的 NaT 或 numpy 的 nan
    if pd.isna(date_val):
        return ''
    # 如果有 strftime 方法，直接格式化
    if hasattr(date_val, 'strftime'):
        try:
            return date_val.strftime('%Y-%m-%d')
        except (ValueError, AttributeError):
            pass
    # 字符串类型，尝试解析后格式化
    if isinstance(date_val, str):
        if len(date_val) >= 10:
            return date_val[:10]
        return date_val
    # 其他类型，转换为字符串
    return str(date_val)[:10] if date_val else ''


def _calculate_family_financials(head, members, profiles, func_type):
    """
    计算家庭财务数据
    
    Args:
        head: 户主
        members: 家庭成员列表
        profiles: 资金画像字典
        func_type: 计算类型 ('deposit' 或 'wealth')
        
    Returns:
        计算结果（万元）
    """
    total = 0.0
    targets = set(members) if members else set()
    targets.add(head)
    
    for p_name in targets:
         # Find profile: check if p_name is contained in any profile key
          profile = next((p for n, p in profiles.items() if p_name in n), None)
          if not profile or not profile['has_data']: continue
          
          if func_type == 'deposit':
              # 【2026-01-22 修复】使用真实银行余额，而不是净流入估算
              val = _get_real_bank_balance(p_name, profiles)
              total += val
          elif func_type == 'wealth':
              w = profile.get('wealth_management', {})
              val = w.get('estimated_holding', 0)
              if val == 0:
                  val = max(0, w.get('wealth_purchase', 0) - w.get('wealth_redemption', 0))
              total += val
    return round(total / 10000, 2)


def _generate_summary_sheet(writer, profiles):
    """
    生成资金画像汇总表
    
    Args:
        writer: ExcelWriter对象
        profiles: 资金画像字典
    """
    summary_data = []
    for entity, profile in profiles.items():
        # 检查是否有数据（根据实际数据结构，使用 entityType 或 has_data）
        has_data = profile.get('has_data', profile.get('entityType') != 'unknown')
        if not has_data:
            continue
        
        # 根据实际数据结构获取字段
        total_income = profile.get('totalIncome', 0)
        total_expense = profile.get('totalExpense', 0)
        net_flow = total_income - total_expense
        salary_total = profile.get('salaryTotal', 0)
        salary_ratio = profile.get('salaryRatio', 0)
        third_party_total = profile.get('thirdPartyTotal', 0)
        transaction_count = profile.get('transactionCount', 0)
        cash_total = profile.get('cashTotal', 0)
        
        # 判断是否为公司（简单的启发式：名称包含"公司"或其他关键词，或者在profiles里有type字段）
        is_company = False
        if '公司' in entity or '中心' in entity or '部' in entity:
            is_company = True

        row_data = {
            '对象名称': entity,
            '资金流入总额(万元)': round(total_income / 10000, 2),
            '资金流出总额(万元)': round(total_expense / 10000, 2),
            '净流入(万元)': round(net_flow / 10000, 2),
            '交易笔数': transaction_count,
            '大额现金总额(万元)': round(cash_total / 10000, 2)
        }
        
        if not is_company:
            row_data.update({
                '工资性收入(万元)': round(salary_total / 10000, 2),
                '工资性收入占比': round(salary_ratio, 3),
                '第三方支付占比': round(third_party_total / total_income, 3) if total_income > 0 else 0,
            })
        else:
            row_data.update({
                '工资性收入(万元)': '-',
                '工资性收入占比': '-',
                '第三方支付占比': round(third_party_total / total_income, 3) if total_income > 0 else 0,
            })
            
        summary_data.append(row_data)
    
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='资金画像汇总', index=False)
        worksheet = writer.sheets['资金画像汇总']
        # 设置百分比格式
        for row in range(2, len(df_summary) + 2):
            worksheet[f'H{row}'].number_format = '0.0%'
            worksheet[f'I{row}'].number_format = '0.0%'


def _generate_direct_transfer_sheet(writer, suspicions):
    """生成直接转账关系表"""
    if not suspicions.get('direct_transfers'):
        return
    
    transfer_data = []
    for t in suspicions['direct_transfers']:
        transfer_data.append({
            '日期': _safe_format_date(t.get('date')),
            '人员': t.get('person', ''),
            '方向': t.get('direction', ''),
            '公司': t.get('company', ''),
            '金额(元)': t.get('amount', 0),
            '摘要': t.get('description', '')
        })
    
    if transfer_data:
        df_transfer = pd.DataFrame(transfer_data)
        df_transfer.to_excel(writer, sheet_name='直接转账关系', index=False)


def _generate_cash_collision_sheet(writer, suspicions):
    """生成现金时空伴随表"""
    if not suspicions.get('cash_collisions'):
        return
    
    collision_data = []
    for collision in suspicions['cash_collisions']:
        collision_data.append({
            '日期': _safe_format_date(collision.get('date', collision.get('withdrawal_date'))),
            '人员A': collision.get('person_a', collision.get('withdrawal_entity', '')),
            '人员B': collision.get('person_b', collision.get('deposit_entity', '')),
            '地点': collision.get('location', ''),
            '时间差(分钟)': collision.get('time_diff', collision.get('time_diff_hours', 0) * 60)
        })
    
    if collision_data:
        df_collision = pd.DataFrame(collision_data)
        df_collision.to_excel(writer, sheet_name='现金时空伴随', index=False)


def _generate_hidden_asset_sheet(writer, suspicions):
    """生成隐形资产明细表"""
    if not suspicions.get('hidden_assets'):
        return
    
    hidden_data = []
    for person, assets in suspicions['hidden_assets'].items():
        for asset in assets:
            hidden_data.append({
                '日期': _safe_format_date(asset.get('date')),
                '人员': person,
                '对手方': asset.get('counterparty', ''),
                '金额(元)': asset.get('amount', 0),
                '摘要': asset.get('description', '')
            })
    
    if hidden_data:
        df_hidden = pd.DataFrame(hidden_data)
        df_hidden.to_excel(writer, sheet_name='隐形资产明细', index=False)


def _generate_fixed_frequency_sheet(writer, suspicions):
    """生成固定频率异常进账表"""
    if not suspicions.get('fixed_frequency'):
        return
    
    fixed_data = []
    for person, items in suspicions['fixed_frequency'].items():
        for item in items:
            fixed_data.append({
                '人员': person,
                '平均日期': item['day_avg'],
                '平均金额(元)': item['amount_avg'],
                '发生次数': item['occurrences'],
                '金额范围': f"{item.get('min_amount', 0)}-{item.get('max_amount', 0)}"
            })
    
    if fixed_data:
        df_fixed = pd.DataFrame(fixed_data)
        df_fixed.to_excel(writer, sheet_name='固定频率异常进账', index=False)


def _generate_large_cash_sheet(writer, profiles):
    """生成大额现金明细表"""
    large_cash_data = []
    
    for entity, profile in profiles.items():
        if not profile['has_data']:
            continue
        
        fund_flow = profile.get('fund_flow', {})
        for tx in fund_flow.get('large_cash_transactions', []):
            large_cash_data.append({
                '对象': entity,
                '日期': tx['日期'].strftime('%Y-%m-%d') if hasattr(tx['日期'], 'strftime') else str(tx['日期'])[:10],
                '金额(元)': tx['金额'],
                '摘要': tx['摘要'],
                '对手方': tx['对手方']
            })
    
    if large_cash_data:
        df_large_cash = pd.DataFrame(large_cash_data)
        df_large_cash.to_excel(writer, sheet_name='大额现金明细', index=False)


def _generate_third_party_sheets(writer, profiles):
    """生成第三方支付交易明细表"""
    third_party_income_data = []
    third_party_expense_data = []
    
    for entity, profile in profiles.items():
        if not profile['has_data']:
            continue
        
        fund_flow = profile.get('fund_flow', {})
        
        # 收入明细
        for tx in fund_flow.get('third_party_income_transactions', []):
            third_party_income_data.append({
                '对象': entity,
                '日期': tx['日期'].strftime('%Y-%m-%d') if hasattr(tx['日期'], 'strftime') else str(tx['日期'])[:10],
                '金额(元)': tx['金额'],
                '摘要': tx['摘要'],
                '对手方': tx['对手方']
            })
        
        # 支出明细
        for tx in fund_flow.get('third_party_expense_transactions', []):
            third_party_expense_data.append({
                '对象': entity,
                '日期': tx['日期'].strftime('%Y-%m-%d') if hasattr(tx['日期'], 'strftime') else str(tx['日期'])[:10],
                '金额(元)': tx['金额'],
                '摘要': tx['摘要'],
                '对手方': tx['对手方']
            })
    
    # 第三方支付-收入工作表
    if third_party_income_data:
        df_tp_income = pd.DataFrame(third_party_income_data)
        df_tp_income.to_excel(writer, sheet_name='第三方支付-收入', index=False)
    
    # 第三方支付-支出工作表
    if third_party_expense_data:
        df_tp_expense = pd.DataFrame(third_party_expense_data)
        df_tp_expense.to_excel(writer, sheet_name='第三方支付-支出', index=False)
    
    # 第三方支付汇总
    third_party_summary = []
    for entity, profile in profiles.items():
        if not profile['has_data']:
            continue
        fund_flow = profile.get('fund_flow', {})
        if fund_flow.get('third_party_income', 0) > 0 or fund_flow.get('third_party_expense', 0) > 0:
            third_party_summary.append({
                '对象': entity,
                '收入笔数': fund_flow.get('third_party_income_count', 0),
                '收入金额(元)': fund_flow.get('third_party_income', 0),
                '支出笔数': fund_flow.get('third_party_expense_count', 0),
                '支出金额(元)': fund_flow.get('third_party_expense', 0),
                '净流入(元)': fund_flow.get('third_party_income', 0) - fund_flow.get('third_party_expense', 0)
            })
    
    if third_party_summary:
        df_tp_summary = pd.DataFrame(third_party_summary)
        df_tp_summary.to_excel(writer, sheet_name='第三方支付-汇总', index=False)


def _generate_wealth_management_sheets(writer, profiles):
    """生成理财产品交易明细表"""
    wealth_purchase_data = []
    wealth_redemption_data = []
    
    for entity, profile in profiles.items():
        if not profile['has_data']:
            continue
        
        wealth_mgmt = profile.get('wealth_management', {})
        
        # 购买明细
        for tx in wealth_mgmt.get('wealth_purchase_transactions', []):
            wealth_purchase_data.append({
                '对象': entity,
                '日期': tx['日期'].strftime('%Y-%m-%d') if hasattr(tx['日期'], 'strftime') else str(tx['日期'])[:10],
                '金额(元)': tx['金额'],
                '摘要': tx['摘要'],
                '对手方': tx['对手方'],
                '判断依据': tx.get('判断依据', '')
            })
        
        # 赎回明细
        for tx in wealth_mgmt.get('wealth_redemption_transactions', []):
            wealth_redemption_data.append({
                '对象': entity,
                '日期': tx['日期'].strftime('%Y-%m-%d') if hasattr(tx['日期'], 'strftime') else str(tx['日期'])[:10],
                '金额(元)': tx['金额'],
                '摘要': tx['摘要'],
                '对手方': tx['对手方'],
                '判断依据': tx.get('判断依据', '')
            })
    
    # 理财产品-购买工作表
    if wealth_purchase_data:
        df_wealth_purchase = pd.DataFrame(wealth_purchase_data)
        df_wealth_purchase.to_excel(writer, sheet_name='理财产品-购买', index=False)
    
    # 理财产品-赎回工作表
    if wealth_redemption_data:
        df_wealth_redemption = pd.DataFrame(wealth_redemption_data)
        df_wealth_redemption.to_excel(writer, sheet_name='理财产品-赎回', index=False)
    
    # 理财产品汇总
    wealth_summary = []
    for entity, profile in profiles.items():
        if not profile['has_data']:
            continue
        wealth_mgmt = profile.get('wealth_management', {})
        if wealth_mgmt.get('total_transactions', 0) > 0:
            wealth_summary.append({
                '对象': entity,
                '购买笔数': wealth_mgmt.get('wealth_purchase_count', 0),
                '购买金额(元)': wealth_mgmt.get('wealth_purchase', 0),
                '赎回笔数': wealth_mgmt.get('wealth_redemption_count', 0),
                '赎回金额(元)': wealth_mgmt.get('wealth_redemption', 0),
                '净流向理财(元)': wealth_mgmt.get('net_wealth_flow', 0),
                '持有估算(元)': wealth_mgmt.get('estimated_holding', 0)
            })
    
    if wealth_summary:
        df_wealth_summary = pd.DataFrame(wealth_summary)
        df_wealth_summary.to_excel(writer, sheet_name='理财产品-汇总', index=False)


def _generate_family_tree_sheet(writer, family_tree):
    """生成家族关系图谱工作表"""
    if not family_tree:
        return
    
    family_data = []
    for person, members in family_tree.items():
        for member in members:
            family_data.append({
                '核心人员': person,
                '家族成员': member.get('姓名', ''),
                '身份证号': member.get('身份证号', ''),
                '与户主关系': member.get('与户主关系', ''),
                '性别': member.get('性别', ''),
                '出生日期': member.get('出生日期', ''),
                '户籍地': member.get('户籍地', ''),
                '数据来源': member.get('数据来源', '')
            })
    
    if family_data:
        df_family = pd.DataFrame(family_data)
        df_family.to_excel(writer, sheet_name='家族关系图谱', index=False)


def _generate_family_assets_sheets(writer, family_assets, profiles):
    """生成家族资产汇总工作表"""
    if not family_assets:
        return
    
    # 8.1 资产汇总表
    asset_summary_data = []
    for person, assets in family_assets.items():
        asset_summary_data.append({
            '核心人员': person,
            '家族成员数': len(assets['家族成员']),
            '家族成员': ', '.join(assets['家族成员']),
            '房产套数': assets['房产套数'],
            '房产总价值(万元)': assets['房产总价值'],
            '车辆数量': assets['车辆数量'],
            '存款估算(万元)': _calculate_family_financials(person, assets['家族成员'], profiles, 'deposit'),
            '理财持仓(万元)': _calculate_family_financials(person, assets['家族成员'], profiles, 'wealth')
        })
    
    if asset_summary_data:
        df_asset_summary = pd.DataFrame(asset_summary_data)
        df_asset_summary.to_excel(writer, sheet_name='家族资产汇总', index=False)
    
    # 8.2 房产明细表
    property_data = []
    for person, assets in family_assets.items():
        for prop in assets['房产']:
            property_data.append({
                '核心人员': person,
                '产权人': prop.get('产权人', ''),
                '房地坐落': prop.get('房地坐落', ''),
                '建筑面积(㎡)': prop.get('建筑面积', 0),
                '交易金额(万元)': prop.get('交易金额', 0),
                '规划用途': prop.get('规划用途', ''),
                '房屋性质': prop.get('房屋性质', ''),
                '登记时间': prop.get('登记时间', ''),
                '共有情况': prop.get('共有情况', ''),
                '共有人名称': prop.get('共有人名称', ''),
                '权属状态': prop.get('权属状态', ''),
                '数据质量': prop.get('数据质量', '正常')
            })
    
    if property_data:
        df_properties = pd.DataFrame(property_data)
        df_properties = df_properties.fillna('-')
        df_properties.to_excel(writer, sheet_name='房产明细', index=False)
    
    # 8.3 车辆明细表
    vehicle_data = []
    for person, assets in family_assets.items():
        for vehicle in assets['车辆']:
            vehicle_data.append({
                '核心人员': person,
                '所有人': vehicle.get('所有人', ''),
                '号牌号码': vehicle.get('号牌号码', ''),
                '中文品牌': vehicle.get('中文品牌', ''),
                '车身颜色': vehicle.get('车身颜色', ''),
                '初次登记日期': vehicle.get('初次登记日期', ''),
                '机动车状态': vehicle.get('机动车状态', ''),
                '是否抵押质押': vehicle.get('是否抵押质押', 0),
                '能源种类': vehicle.get('能源种类', ''),
                '住所地址': vehicle.get('住所地址', '')
            })
    
    if vehicle_data:
        df_vehicles = pd.DataFrame(vehicle_data)
        df_vehicles.to_excel(writer, sheet_name='车辆明细', index=False)


def _generate_validation_sheets(writer, validation_results):
    """生成数据验证结果工作表"""
    if not validation_results:
        return
    
    # 9.1 流水数据验证
    if 'transactions' in validation_results:
        validation_data = []
        for entity, result in validation_results['transactions'].items():
            validation_data.append({
                '实体名称': entity,
                '验证状态': result['status'],
                '记录数': result['record_count'],
                '时间跨度(天)': result.get('date_range_days', 0),
                '问题': '; '.join(result['issues']) if result['issues'] else '',
                '警告': '; '.join(result['warnings']) if result['warnings'] else ''
            })
        
        if validation_data:
            df_validation = pd.DataFrame(validation_data)
            df_validation.to_excel(writer, sheet_name='数据验证-流水', index=False)
    
    # 9.2 房产交易验证
    if 'properties' in validation_results:
        prop_validation_data = []
        for result in validation_results['properties']:
            prop_validation_data.append({
                '产权人': result['产权人'],
                '房产地址': result['房产地址'],
                '交易金额(万元)': result['交易金额'],
                '登记时间': result['登记时间'],
                '验证状态': result['验证状态'],
                '匹配交易日期': result['匹配交易']['日期'] if result.get('匹配交易') else '',
                '匹配交易金额': result['匹配交易']['金额'] if result.get('匹配交易') else ''
            })
        
        if prop_validation_data:
            df_prop_validation = pd.DataFrame(prop_validation_data)
            df_prop_validation.to_excel(writer, sheet_name='数据验证-房产', index=False)


def _generate_penetration_sheets(writer, penetration_results):
    """生成资金穿透分析工作表"""
    if not penetration_results:
        return
    
    # 10.1 穿透汇总
    penetration_summary = []
    summary = penetration_results.get('summary', {})
    penetration_summary.append({
        '类型': '个人→涉案公司',
        '笔数': summary.get('个人→公司笔数', 0),
        '金额(万元)': summary.get('个人→公司总金额', 0) / 10000
    })
    penetration_summary.append({
        '类型': '涉案公司→个人',
        '笔数': summary.get('公司→个人笔数', 0),
        '金额(万元)': summary.get('公司→个人总金额', 0) / 10000
    })
    penetration_summary.append({
        '类型': '核心人员之间',
        '笔数': summary.get('核心人员间笔数', 0),
        '金额(万元)': summary.get('核心人员间总金额', 0) / 10000
    })
    penetration_summary.append({
        '类型': '涉案公司之间',
        '笔数': summary.get('涉案公司间笔数', 0),
        '金额(万元)': summary.get('涉案公司间总金额', 0) / 10000
    })
    
    df_penetration_summary = pd.DataFrame(penetration_summary)
    df_penetration_summary.to_excel(writer, sheet_name='资金穿透-汇总', index=False)
    
    # 10.2 个人→公司明细
    if penetration_results.get('person_to_company'):
        p2c_data = []
        for item in penetration_results['person_to_company']:
            p2c_data.append({
                '发起方': item['发起方'],
                '接收方': item['接收方'],
                '日期': item['日期'],
                '收入': item['收入'],
                '支出': item['支出'],
                '摘要': item['摘要'],
                '对方原文': item['交易对方原文']
            })
        if p2c_data:
            pd.DataFrame(p2c_data).to_excel(writer, sheet_name='穿透-个人到公司', index=False)
    
    # 10.3 公司→个人明细
    if penetration_results.get('company_to_person'):
        c2p_data = []
        for item in penetration_results['company_to_person']:
            c2p_data.append({
                '发起方': item['发起方'],
                '接收方': item['接收方'],
                '日期': item['日期'],
                '收入': item['收入'],
                '支出': item['支出'],
                '摘要': item['摘要'],
                '对方原文': item['交易对方原文']
            })
        if c2p_data:
            pd.DataFrame(c2p_data).to_excel(writer, sheet_name='穿透-公司到个人', index=False)
    
    # 10.4 核心人员之间明细
    if penetration_results.get('person_to_person'):
        p2p_data = []
        for item in penetration_results['person_to_person']:
            p2p_data.append({
                '发起方': item['发起方'],
                '接收方': item['接收方'],
                '日期': item['日期'],
                '收入': item['收入'],
                '支出': item['支出'],
                '摘要': item['摘要'],
                '对方原文': item['交易对方原文']
            })
        if p2p_data:
            pd.DataFrame(p2p_data).to_excel(writer, sheet_name='穿透-人员之间', index=False)
    
    # 10.5 涉案公司之间明细
    if penetration_results.get('company_to_company'):
        c2c_data = []
        for item in penetration_results['company_to_company']:
            c2c_data.append({
                '发起方': item['发起方'],
                '接收方': item['接收方'],
                '日期': item['日期'],
                '收入': item['收入'],
                '支出': item['支出'],
                '摘要': item['摘要'],
                '对方原文': item['交易对方原文']
            })
        if c2c_data:
            pd.DataFrame(c2c_data).to_excel(writer, sheet_name='穿透-公司之间', index=False)


def _generate_loan_analysis_sheets(writer, loan_results):
    """
    生成借贷分析工作表（与借贷行为分析报告.txt对应）
    
    包含：双向往来、无还款借贷、规律还款三个工作表
    """
    if not loan_results:
        return
    
    # 11.1 双向资金往来
    if loan_results.get('bidirectional_flows'):
        data = []
        for item in loan_results['bidirectional_flows']:
            data.append({
                '人员': item.get('person', ''),
                '对手方': item.get('counterparty', ''),
                '收入笔数': item.get('income_count', 0),
                '收入金额(元)': item.get('income_total', 0),
                '支出笔数': item.get('expense_count', 0),
                '支出金额(元)': item.get('expense_total', 0),
                '支出/收入比': round(item.get('ratio', 0), 3),
                '借贷类型': item.get('loan_type', ''),
                '风险等级': item.get('risk_level', '').upper(),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='借贷-双向往来', index=False)
    
    # 11.2 无还款借贷（疑似利益输送）
    if loan_results.get('no_repayment_loans'):
        data = []
        for item in loan_results['no_repayment_loans']:
            data.append({
                '人员': item.get('person', ''),
                '对手方': item.get('counterparty', ''),
                '收入日期': _safe_format_date(item.get('income_date')),
                '金额(元)': item.get('income_amount', 0),
                '距今天数': item.get('days_since', 0),
                '已还金额(元)': item.get('total_repaid', 0),
                '还款比例': f"{item.get('repay_ratio', 0)*100:.1f}%",
                '风险原因': item.get('risk_reason', ''),
                '风险等级': item.get('risk_level', '').upper(),
                '交易摘要': item.get('description', ''),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='借贷-无还款', index=False)
    
    # 11.3 规律性还款模式
    if loan_results.get('regular_repayments'):
        data = []
        for item in loan_results['regular_repayments']:
            data.append({
                '人员': item.get('person', ''),
                '对手方': item.get('counterparty', ''),
                '还款日(每月)': item.get('day_of_month', 0),
                '还款次数': item.get('occurrences', 0),
                '平均金额(元)': round(item.get('avg_amount', 0), 2),
                '总金额(元)': round(item.get('total_amount', 0), 2),
                '变异系数': round(item.get('cv', 0), 3),
                '疑似贷款': '是' if item.get('is_likely_loan') else '否',
                '风险等级': item.get('risk_level', '').upper(),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='借贷-规律还款', index=False)
    
    # 11.4 借贷配对分析
    if loan_results.get('loan_pairs'):
        data = []
        for item in loan_results['loan_pairs']:
            data.append({
                '人员': item.get('person', ''),
                '对手方': item.get('counterparty', ''),
                '借入日期': _safe_format_date(item.get('loan_date')),
                '借入金额(元)': item.get('loan_amount', 0),
                '还款日期': _safe_format_date(item.get('repay_date')),
                '还款金额(元)': item.get('repay_amount', 0),
                '周期(天)': item.get('days', 0),
                '利率(%)': round(item.get('interest_rate', 0), 2),
                '年化利率(%)': round(item.get('annual_rate', 0), 1),
                '风险原因': item.get('risk_reason', ''),
                '风险等级': item.get('risk_level', '').upper(),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='借贷-配对分析', index=False)
    
    # 11.5 网贷平台往来
    if loan_results.get('online_loan_platforms'):
        data = []
        for item in loan_results['online_loan_platforms']:
            data.append({
                '人员': item.get('person', ''),
                '平台': item.get('platform', ''),
                '对手方': item.get('counterparty', ''),
                '日期': _safe_format_date(item.get('date')),
                '金额(元)': item.get('amount', 0),
                '方向': '收入' if item.get('direction') == 'income' else '支出',
                '摘要': item.get('description', ''),
                '风险等级': item.get('risk_level', '').upper(),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='借贷-网贷平台', index=False)


def _generate_income_anomaly_sheets(writer, income_results):
    """
    生成异常收入工作表（与异常收入来源分析报告.txt对应）
    """
    if not income_results:
        return
    
    # 12.1 异常收入汇总
    all_anomalies = []
    
    # 规律性非工资收入
    for item in income_results.get('regular_non_salary', []):
        all_anomalies.append({
            '人员': item.get('person', ''),
            '异常类型': '规律性非工资收入',
            '对手方': item.get('counterparty', ''),
            '金额(元)': item.get('total_amount', 0),
            '次数': item.get('count', 0),
            '平均金额(元)': item.get('avg_amount', 0),
            '可疑原因': item.get('income_type', ''),
            '风险等级': item.get('risk_level', '').upper(),
        })
    
    # 个人大额转入
    for item in income_results.get('large_personal_income', []):
        all_anomalies.append({
            '人员': item.get('person', ''),
            '异常类型': '个人大额转入',
            '对手方': item.get('counterparty', ''),
            '金额(元)': item.get('amount', 0),
            '日期': _safe_format_date(item.get('date')),
            '可疑原因': '个人大额转入需核实',
            '风险等级': item.get('risk_level', '').upper(),
        })
    
    # 来源不明收入
    for item in income_results.get('unknown_source', []):
        all_anomalies.append({
            '人员': item.get('person', ''),
            '异常类型': '来源不明收入',
            '对手方': item.get('counterparty', '(缺失)'),
            '金额(元)': item.get('amount', 0),
            '日期': _safe_format_date(item.get('date')),
            '可疑原因': item.get('reason', ''),
            '摘要': item.get('description', ''),
            '风险等级': item.get('risk_level', '').upper(),
        })
    
    # 同源多次收入
    for item in income_results.get('multi_source', []):
        all_anomalies.append({
            '人员': item.get('person', ''),
            '异常类型': '同源多次收入',
            '对手方': item.get('counterparty', ''),
            '金额(元)': item.get('total_amount', 0),
            '次数': item.get('count', 0),
            '平均金额(元)': item.get('avg_amount', 0),
            '可疑原因': item.get('income_type', ''),
            '风险等级': item.get('risk_level', '').upper(),
        })
    
    # 大额单笔收入
    for item in income_results.get('large_single_income', []):
        all_anomalies.append({
            '人员': item.get('person', ''),
            '异常类型': '大额单笔收入',
            '对手方': item.get('counterparty', ''),
            '金额(元)': item.get('amount', 0),
            '日期': _safe_format_date(item.get('date')),
            '可疑原因': item.get('income_type', ''),
            '风险等级': item.get('risk_level', '').upper(),
        })
    
    if all_anomalies:
        pd.DataFrame(all_anomalies).to_excel(writer, sheet_name='异常收入-汇总', index=False)
    
    # 12.2 疑似分期受贿（单独工作表）
    if income_results.get('suspected_bribery'):
        data = []
        for item in income_results['suspected_bribery']:
            data.append({
                '人员': item.get('person', ''),
                '对手方': item.get('counterparty', ''),
                '月均金额(元)': item.get('avg_monthly', 0),
                '波动系数': round(item.get('cv', 0), 3),
                '持续月数': item.get('months', 0),
                '总笔数': item.get('count', 0),
                '总金额(元)': item.get('total_amount', 0),
                '风险因素': item.get('risk_factors', ''),
                '风险等级': item.get('risk_level', '').upper(),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='异常收入-疑似分期受贿', index=False)


def _generate_time_series_sheets(writer, time_series_results):
    """
    生成时序分析工作表（与时序分析报告.txt对应）
    """
    if not time_series_results:
        return
    
    # 13.1 资金突变事件
    if time_series_results.get('突变事件'):
        data = []
        for item in time_series_results['突变事件']:
            person = item.get('person', '')
            data.append({
                '人员': person if person and str(person) != 'nan' else '(未知)',
                '日期': _safe_format_date(item.get('date')),
                '金额(元)': item.get('amount', 0),
                'Z值': round(item.get('z_score', 0), 2),
                '均值(元)': round(item.get('mean', 0), 2),
                '风险等级': item.get('risk_level', '').upper(),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='时序-资金突变', index=False)
    
    # 13.2 固定延迟转账
    if time_series_results.get('延迟转账'):
        data = []
        for item in time_series_results['延迟转账']:
            # 安全处理 nan 值
            person = item.get('person', '')
            income_cp = item.get('income_counterparty', '')
            expense_cp = item.get('expense_counterparty', '')
            
            person = person if person and str(person) != 'nan' else '(未知)'
            income_cp = income_cp if income_cp and str(income_cp) != 'nan' else '(未知)'
            expense_cp = expense_cp if expense_cp and str(expense_cp) != 'nan' else '(未知)'
            
            data.append({
                '人员': person,
                '收入来源': income_cp,
                '支出去向': expense_cp,
                '延迟天数': item.get('delay_days', 0),
                '发生次数': item.get('count', 0),
                '总金额(元)': round(item.get('total_amount', 0), 2),
                '风险等级': item.get('risk_level', '').upper(),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='时序-固定延迟', index=False)


def _generate_fund_cycle_sheets(writer, penetration_results):
    """
    生成资金闭环工作表（与资金穿透分析报告.txt对应）
    """
    if not penetration_results:
        return
    
    # 14.1 资金闭环
    if penetration_results.get('fund_cycles'):
        data = []
        for cycle in penetration_results['fund_cycles']:
            if isinstance(cycle, list):
                cycle_str = ' → '.join(cycle)
                cycle_len = len(cycle)
            else:
                cycle_str = str(cycle)
                cycle_len = 0
            
            data.append({
                '闭环路径': cycle_str,
                '涉及节点数': cycle_len,
                '风险等级': 'HIGH' if cycle_len >= 3 else 'MEDIUM',
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='穿透-资金闭环', index=False)
    
    # 14.2 过账通道
    if penetration_results.get('passthrough_channels'):
        data = []
        for item in penetration_results['passthrough_channels']:
            data.append({
                '实体名称': item.get('entity', ''),
                '实体类型': item.get('type', ''),
                '进账金额(万元)': round(item.get('inflow', 0) / 10000, 2),
                '出账金额(万元)': round(item.get('outflow', 0) / 10000, 2),
                '进出比(%)': round(item.get('ratio', 0) * 100, 1),
                '风险等级': item.get('risk_level', '').upper(),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='穿透-过账通道', index=False)
    
    # 14.3 资金枢纽节点
    if penetration_results.get('hub_nodes'):
        data = []
        for item in penetration_results['hub_nodes']:
            data.append({
                '节点名称': item.get('name', ''),
                '节点类型': item.get('type', ''),
                '入度': item.get('in_degree', 0),
                '出度': item.get('out_degree', 0),
                '总连接数': item.get('total_degree', 0),
            })
        if data:
            pd.DataFrame(data).to_excel(writer, sheet_name='穿透-枢纽节点', index=False)

def _generate_income_classification_sheet(writer, derived_data):
    """
    生成收入分类分析工作表
    
    Args:
        writer: ExcelWriter对象
        derived_data: 派生数据字典（包含income_classifications）
    """
    if not derived_data or not derived_data.get('income_classifications'):
        return
    
    income_classifications = derived_data['income_classifications']
    
    # 为每个人员生成收入分类明细
    for person, classification in income_classifications.items():
        sheet_name = f'收入分类-{person}'
        # 限制sheet名称长度（Excel限制31个字符）
        if len(sheet_name) > 31:
            sheet_name = sheet_name[:28] + '...'
        
        classification_data = []
        
        # 合法收入明细
        for item in classification.get('legitimate_details', []):
            classification_data.append({
                '人员': person,
                '收入类型': '合法收入',
                '日期': item.get('date'),
                '金额(元)': item.get('amount', 0),
                '对手方': item.get('counterparty', ''),
                '摘要': item.get('description', ''),
                '判断依据': item.get('reason', '')
            })
        
        # 未知收入明细
        for item in classification.get('unknown_details', []):
            classification_data.append({
                '人员': person,
                '收入类型': '未知收入',
                '日期': item.get('date'),
                '金额(元)': item.get('amount', 0),
                '对手方': item.get('counterparty', ''),
                '摘要': item.get('description', ''),
                '判断依据': item.get('reason', '')
            })
        
        # 可疑收入明细
        for item in classification.get('suspicious_details', []):
            classification_data.append({
                '人员': person,
                '收入类型': '可疑收入',
                '日期': item.get('date'),
                '金额(元)': item.get('amount', 0),
                '对手方': item.get('counterparty', ''),
                '摘要': item.get('description', ''),
                '判断依据': item.get('reason', '')
            })
        
        if classification_data:
            df = pd.DataFrame(classification_data)
            df.to_excel(writer, sheet_name=sheet_name, index=False)


def _generate_income_summary_sheet(writer, derived_data):
    """
    生成收入分类汇总工作表
    
    Args:
        writer: ExcelWriter对象
        derived_data: 派生数据字典（包含income_classifications）
    """
    if not derived_data or not derived_data.get('income_classifications'):
        return
    
    income_classifications = derived_data['income_classifications']
    summary_data = []
    
    for person, classification in income_classifications.items():
        summary_data.append({
            '人员': person,
            '合法收入(元)': classification.get('legitimate_income', 0),
            '合法收入占比': f"{classification.get('legitimate_ratio', 0):.2%}",
            '合法收入笔数': classification.get('legitimate_count', 0),
            '未知收入(元)': classification.get('unknown_income', 0),
            '未知收入占比': f"{classification.get('unknown_ratio', 0):.2%}",
            '未知收入笔数': classification.get('unknown_count', 0),
            '可疑收入(元)': classification.get('suspicious_income', 0),
            '可疑收入占比': f"{classification.get('suspicious_ratio', 0):.2%}",
            '可疑收入笔数': classification.get('suspicious_count', 0),
            '总收入(元)': classification.get('legitimate_income', 0) + classification.get('unknown_income', 0) + classification.get('suspicious_income', 0)
        })
    
    if summary_data:
        df = pd.DataFrame(summary_data)
        df.to_excel(writer, sheet_name='收入分类汇总', index=False)


def _generate_total_assets_sheet(writer, derived_data):
    """
    生成总资产汇总工作表
    
    Args:
        writer: ExcelWriter对象
        derived_data: 派生数据字典（包含total_assets）
    """
    if not derived_data or not derived_data.get('total_assets'):
        return
    
    total_assets = derived_data['total_assets']
    
    assets_data = [{
        '资产类型': '银行存款',
        '金额(元)': total_assets.get('bank_balance', 0),
        '金额(万元)': round(total_assets.get('bank_balance', 0) / 10000, 2)
    }, {
        '资产类型': '房产价值',
        '金额(元)': total_assets.get('property_value', 0),
        '金额(万元)': round(total_assets.get('property_value', 0) / 10000, 2)
    }, {
        '资产类型': '车辆价值',
        '金额(元)': total_assets.get('vehicle_value', 0),
        '金额(万元)': round(total_assets.get('vehicle_value', 0) / 10000, 2)
    }, {
        '资产类型': '理财持仓',
        '金额(元)': total_assets.get('wealth_balance', 0),
        '金额(万元)': round(total_assets.get('wealth_balance', 0) / 10000, 2)
    }, {
        '资产类型': '总资产',
        '金额(元)': total_assets.get('total', 0),
        '金额(万元)': round(total_assets.get('total', 0) / 10000, 2)
    }]
    
    df = pd.DataFrame(assets_data)
    df.to_excel(writer, sheet_name='总资产汇总', index=False)


def _generate_member_transfers_sheet(writer, derived_data):
    """
    生成成员间转账工作表
    
    Args:
        writer: ExcelWriter对象
        derived_data: 派生数据字典（包含member_transfers）
    """
    if not derived_data or not derived_data.get('member_transfers'):
        return
    
    member_transfers = derived_data['member_transfers']
    transfer_data = []
    
    for person, transfers in member_transfers.items():
        transfer_data.append({
            '人员': person,
            '转给家庭(元)': transfers.get('to_family', 0),
            '从家庭转入(元)': transfers.get('from_family', 0),
            '净流入(元)': transfers.get('net', 0)
        })
    
    if transfer_data:
        df = pd.DataFrame(transfer_data)
        df.to_excel(writer, sheet_name='成员间转账', index=False)


def generate_excel_workbook(profiles: Dict,
                            suspicions: Dict,
                            output_path: str = None,
                            family_tree: Dict = None,
                            family_assets: Dict = None,
                            validation_results: Dict = None,
                            penetration_results: Dict = None,
                            loan_results: Dict = None,
                            income_results: Dict = None,
                            time_series_results: Dict = None,
                            derived_data: Dict = None) -> str:
    """
    生成Excel核查底稿
    
    Args:
        profiles: 资金画像字典
        suspicions: 疑点检测结果
        output_path: 输出路径,默认使用配置
        family_tree: 家族关系图谱（可选）
        family_assets: 家族资产数据（可选）
        validation_results: 数据验证结果（可选）
        penetration_results: 资金穿透分析结果（可选）
        loan_results: 借贷分析结果（可选）
        income_results: 异常收入分析结果（可选）
        time_series_results: 时序分析结果（可选）
        derived_data: 派生数据（可选，包含收入分类、总资产等）
        
    Returns:
        生成的文件路径
    """
    if output_path is None:
        output_path = config.OUTPUT_EXCEL_FILE
    
    logger.info(f'正在生成Excel底稿: {output_path}')

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        
        # 1. 资金画像汇总表
        _generate_summary_sheet(writer, profiles)

        
        # 2. 直接转账关系表
        _generate_direct_transfer_sheet(writer, suspicions)
        
        # 3. 现金时空伴随表
        _generate_cash_collision_sheet(writer, suspicions)
        
        # 4. 隐形资产明细表
        _generate_hidden_asset_sheet(writer, suspicions)
        
        # 5. 固定频率异常进账表
        _generate_fixed_frequency_sheet(writer, suspicions)
        
        # 6. 大额现金明细表
        _generate_large_cash_sheet(writer, profiles)
        
        # 6.5 第三方支付交易明细表（微信/支付宝等）
        _generate_third_party_sheets(writer, profiles)
        
        # 6.6 理财产品交易明细表
        _generate_wealth_management_sheets(writer, profiles)
        
        # 7. 家族关系图谱
        _generate_family_tree_sheet(writer, family_tree)
        
        # 8. 家族资产汇总
        _generate_family_assets_sheets(writer, family_assets, profiles)
        
        # 9. 数据验证结果
        _generate_validation_sheets(writer, validation_results)
        
        # 10. 资金穿透分析
        _generate_penetration_sheets(writer, penetration_results)
        
        # 11. 借贷行为分析（新增）
        _generate_loan_analysis_sheets(writer, loan_results)
        
        # 12. 异常收入分析（新增）
        _generate_income_anomaly_sheets(writer, income_results)
        
        # 13. 时序分析（新增）
        _generate_time_series_sheets(writer, time_series_results)
        
        # 14. 资金闭环/过账通道（新增）
        _generate_fund_cycle_sheets(writer, penetration_results)
        
        # 15. 收入分类分析（新增）
        _generate_income_summary_sheet(writer, derived_data)
        _generate_income_classification_sheet(writer, derived_data)
        
        # 16. 总资产汇总（新增）
        _generate_total_assets_sheet(writer, derived_data)
        
        # 17. 成员间转账（新增）
        _generate_member_transfers_sheet(writer, derived_data)
    
    logger.info(f'Excel底稿生成完成: {output_path}')
    
    return output_path


def _group_into_households(core_persons, family_summary):
    """
    将核心人员按家庭关系分组
    
    支持两种 family_summary 格式：
    1. 新格式 (2026-01-23+): 包含 family_units 列表，直接使用预计算的家庭分组
    2. 旧格式: 每人 -> {配偶: [...], 子女: [...], ...}，需要动态计算分组
    
    Args:
        core_persons: 核心人员列表
        family_summary: 家庭关系摘要（可以是新格式 dict 或旧格式 dict）
        
    Returns:
        家庭分组列表，每个元素是一个家庭成员姓名列表
    """
    if not family_summary:
        # 无家庭数据，每人独立成组
        return [[p] for p in core_persons]
    
    # ========== 优先使用新格式 family_units ==========
    family_units = family_summary.get('family_units', [])
    if family_units:
        modules = []
        used_persons = set()
        
        for unit in family_units:
            # 过滤出属于 core_persons 的成员
            unit_members = unit.get('members', [])
            filtered_members = [m for m in unit_members if m in core_persons]
            
            if filtered_members:
                modules.append(sorted(filtered_members))
                used_persons.update(filtered_members)
        
        # 将未被分配的 core_persons 添加为独立单元
        for p in core_persons:
            if p not in used_persons:
                modules.append([p])
        
        return modules
    
    # ========== 回退到旧格式 family_relations ==========
    # 从 family_summary 中获取 family_relations（如果存在）
    relations_data = family_summary.get('family_relations', family_summary)
    
    adj = {p: set() for p in core_persons}
    if relations_data and isinstance(relations_data, dict):
        for p, rels in relations_data.items():
            if p not in core_persons: 
                continue
            if not isinstance(rels, dict):
                continue
            direct_names = []
            for k in ['配偶', '子女', '父母', '夫妻', '儿子', '女儿', '父亲', '母亲']:
                if k in rels:
                    direct_names.extend(rels[k])
            for d in direct_names:
                if d in core_persons:
                    adj[p].add(d)
                    if d in adj: 
                        adj[d].add(p)
    
    # BFS 找连通分量
    modules = []
    visited = set()
    for p in core_persons:
        if p not in visited:
            comp = []
            q = [p]
            visited.add(p)
            while q:
                curr = q.pop(0)
                comp.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        q.append(neighbor)
            modules.append(sorted(comp))
    return modules


def _format_salary_summary(income_data):
    """
    格式化工资收入摘要
    
    Args:
        income_data: 收入数据
        
    Returns:
        工资收入摘要字符串
    """
    salary_details = income_data.get('salary_details', [])
    yearly = {}
    for item in salary_details:
        d_str = str(item.get('日期', ''))[:4]
        if d_str.isdigit():
            yearly[d_str] = yearly.get(d_str, 0) + item.get('金额', 0)
    
    if not yearly: return "未发现明显工资性收入。"
    years = sorted(yearly.keys(), key=lambda x: int(x))
    total = sum(yearly.values())
    current_year = datetime.now().year
    recent_years = [y for y in years if int(y) >= current_year - 5]
    recent_total = sum(yearly[y] for y in recent_years)
    avg_recent = recent_total / len(recent_years) if recent_years else 0
    max_year = max(yearly, key=yearly.get)
    summary = f"工资性收入总计 {utils.format_currency(total)}。近五年平均年薪 {utils.format_currency(avg_recent)}。"
    if max_year:
         summary += f" 峰值年份为{max_year}年({utils.format_currency(yearly[max_year])})。"
    return summary


def _get_top_counterparties_str(entity, direction, cleaned_data, top_n=5):
    """
    获取主要交易对手字符串
    
    Args:
        entity: 实体名称
        direction: 方向 ('in' 或 'out')
        cleaned_data: 清洗后的数据
        top_n: 返回前N个
        
    Returns:
        主要交易对手字符串
    """
    if not cleaned_data or entity not in cleaned_data: return "无数据"
    df = cleaned_data[entity]
    col = 'income' if direction == 'in' else 'expense'
    if col not in df.columns: return "无数据"
    subset = df[df[col] > 0]
    if subset.empty: return "无主要交易"
    subset = subset[subset['counterparty'] != entity]
    stats = subset.groupby('counterparty')[col].sum().sort_values(ascending=False)
    lines = []
    count = 0
    for name, amt in zip(stats.index, stats.values):
        name_str = str(name).strip()
        if name_str.lower() in ['nan', 'none', '', 'nat'] or \
           any(x in name_str for x in ['内部户', '待清算', '资金归集', '过渡户']):
            continue
        lines.append(f"{name_str}({utils.format_currency(amt)})")
        count += 1
        if count >= top_n: break
    return ", ".join(lines) if lines else "无主要外部交易对手"


def _get_real_bank_balance(person, profiles):
    """
    获取真实的银行账户余额（从 profiles 中的 bank_accounts 数据）
    
    Args:
        person: 人员名称
        profiles: 资金画像字典
        
    Returns:
        真实的银行余额总和
    """
    profile = profiles.get(person, {})
    if not profile:
        return 0
    
    # 获取银行账户数据
    bank_accounts = profile.get('bank_accounts', []) or profile.get('bankAccounts', [])
    
    if not bank_accounts:
        return 0
    
    total_balance = 0.0
    for acc in bank_accounts:
        if isinstance(acc, dict):
            # 优先使用 last_balance（流水末尾余额），其次 balance
            balance = acc.get('last_balance', 0) or acc.get('balance', 0) or acc.get('余额', 0) or 0
            total_balance += balance
    
    return total_balance


def _estimate_bank_balance(person, cleaned_data):
    """
    估算银行余额（已弃用，保留用于兼容性）
    
    注意：此函数使用简单的 收入-支出 计算，不准确
    建议使用 _get_real_bank_balance 获取真实余额
    
    Args:
        person: 人员名称
        cleaned_data: 清洗后的数据
        
    Returns:
        估算的银行余额
    """
    if not cleaned_data or person not in cleaned_data: return 0
    df = cleaned_data[person]
    total_in = df['income'].sum()
    total_out = df['expense'].sum()
    return max(0, total_in - total_out)


def _generate_report_conclusion(profiles, suspicions, core_persons, involved_companies):
    """
    生成报告核心结论部分
    
    Args:
        profiles: 资金画像字典
        suspicions: 疑点检测结果
        core_persons: 核心人员列表
        involved_companies: 涉及公司列表
        
    Returns:
        报告行列表
    """
    report_lines = []
    
    report_lines.append("一、核查结论")
    report_lines.append("-" * 60)
    
    total_trans = sum(p['summary']['transaction_count'] for p in profiles.values() if p['has_data'])
    direct_sus_count = len(suspicions['direct_transfers'])
    hidden_sus_count = sum(len(v) for v in suspicions['hidden_assets'].values())
    
    risk_assessment = "低风险"
    if direct_sus_count > 0 or hidden_sus_count > 0:
        risk_assessment = "中高风险" if direct_sus_count > 5 else "关注级"
        
    report_lines.append(f"【总体评价】: 本次核查对象共 {len(core_persons)} 人及 {len(involved_companies)} 家关联公司，总体风险评级为[{risk_assessment}]。")
    report_lines.append(f"【数据概况】: 累计分析银行流水 {total_trans} 条。")
    
    # 高流水预警
    high_flow_persons = []
    for p_name, p_data in profiles.items():
        if p_name in core_persons and p_data['has_data']:
            total_vol = p_data['summary']['total_income'] + p_data['summary']['total_expense']
            if total_vol > 50000000: # 5000万
                high_flow_persons.append(f"{p_name}({utils.format_currency(total_vol)})")
    if high_flow_persons:
        report_lines.append(f"【特别说明】: {', '.join(high_flow_persons)} 银行流水规模较大，主要系理财产品频繁申赎所致，详见下文理财分析。")

    if direct_sus_count == 0 and hidden_sus_count == 0:
        report_lines.append(f"【主要发现】: 未发现核心人员与涉案公司存在直接利益输送，亦未发现明显的隐形房产/车辆购置线索。")
    else:
        report_lines.append(f"【主要发现】: 发现 {direct_sus_count} 笔疑似直接利益输送，{hidden_sus_count} 笔疑似隐形资产线索，需进一步核查。")
    
    report_lines.append("")
    return report_lines


def _generate_family_section(household, family_assets, profiles, cleaned_data):
    """
    生成家庭资产与资金画像部分
    
    Args:
        household: 家庭成员列表
        family_assets: 家庭资产数据
        profiles: 资金画像字典
        cleaned_data: 清洗后的数据
        
    Returns:
        报告行列表
    """
    report_lines = []
    
    title = "、".join(household) + " 家庭" if len(household) > 1 else f"{household[0]} 个人"
    report_lines.append(f"➤ {title}")
    
    # 2.1 家庭全貌统计
    fam_props_list = []
    fam_cars_num = 0
    fam_total_deposit_est = 0.0 # 估算存款余额
    fam_total_wealth_est = 0.0 # 估算理财沉淀
    fam_deposit_details = []
    fam_wealth_details = []
    
    for person in household:
        # 资产
        props = family_assets.get(person, {}).get('房产', []) if family_assets else []
        fam_props_list.extend([(person, p) for p in props])
        fam_cars_num += len(family_assets.get(person, {}).get('车辆', [])) if family_assets else 0
        
        # 资金状态
        p_prof = profiles.get(person)
        if p_prof and p_prof['has_data']:
            # 【2026-01-22 修复】使用真实银行余额，而不是净流入估算
            deposit = _get_real_bank_balance(person, profiles)
            fam_total_deposit_est += deposit
            if deposit > 1000:
                fam_deposit_details.append(f"{person}:{utils.format_currency(deposit)}")
            
            # 理财沉淀估算 (使用新的V3算法 results)
            wealth = p_prof.get('wealth_management', {})
            # 优先使用 estimate_holding
            w_holding = wealth.get('estimated_holding', 0.0)
            # 如果没有(老数据)，降级使用 Net
            if w_holding == 0 and 'estimated_holding' not in wealth:
                w_holding = max(0, wealth.get('wealth_purchase', 0) - wealth.get('wealth_redemption', 0))
            
            if w_holding > 0:
                 fam_total_wealth_est += w_holding
                 fam_wealth_details.append(f"{person}:{utils.format_currency(w_holding)}")
    
    # 展示家庭全貌表格化
    report_lines.append(f"  【家庭资产全貌】 (截至数据提取日)")
    report_lines.append(f"   • 房产合计: {len(fam_props_list)} 套")
    for owner, p in fam_props_list:
        addr = p.get('房地坐落', '未知地址')
        price = p.get('交易金额', 0)
        price_str = f"{utils.format_currency(price)}" if price > 0 else "价格未知"
        area = p.get('建筑面积', 0)
        area_str = f"{area}平" if area > 0 else "面积未知"
        report_lines.append(f"     - [{owner}] {addr} ({area_str}, {price_str})")
        
    report_lines.append(f"   • 车辆合计: {fam_cars_num} 辆")
    report_lines.append(f"   • 资金沉淀(估算): 存款约 {utils.format_currency(fam_total_deposit_est)} | 理财约 {utils.format_currency(fam_total_wealth_est)}")
    if fam_deposit_details:
         report_lines.append(f"     - 存款分布: {', '.join(fam_deposit_details)}")
    if fam_wealth_details:
         report_lines.append(f"     - 理财分布: {', '.join(fam_wealth_details)}")
    report_lines.append("")

    # 2.2 个人详情
    for person in household:
        profile = next((p for p in profiles.values() if person in p.get('entity_name', '')), None)
        if not profile or not profile['has_data']:
            report_lines.append(f"  [{person}]: 暂无详细流水数据"); continue
            
        summary = profile['summary']
        income = profile.get('income_structure', {})
        wealth = profile.get('wealth_management', {})
        
        report_lines.append(f"  [{person}]")
        # 资金规模与自我转账
        self_transfer_vol = wealth.get('self_transfer_income', 0) + wealth.get('self_transfer_expense', 0)
        self_note = f"(含内部互转 {utils.format_currency(self_transfer_vol)})" if self_transfer_vol > 500000 else ""
        report_lines.append(f"    • 资金规模: 流入 {utils.format_currency(summary['total_income'])} / 流出 {utils.format_currency(summary['total_expense'])} {self_note}")
        
        # 工资收入
        report_lines.append(f"    • 收入结构: {utils.format_currency(income.get('salary_income', 0))} (占比 {summary['salary_ratio']:.1%})")
        report_lines.append(f"      {_format_salary_summary(income)}")
        
        # 理财深度分析
        w_purchase = wealth.get('wealth_purchase', 0)
        w_redeem = wealth.get('wealth_redemption', 0)
        w_est_holding = wealth.get('estimated_holding', 0)
        
        if w_purchase > 100000:
            report_lines.append(f"    • 理财行为: 申购 {utils.format_currency(w_purchase)} / 赎回 {utils.format_currency(w_redeem)}")
            flow_vol = summary['total_income'] + summary['total_expense']
            if flow_vol > 0:
                turnover = (w_purchase + w_redeem) / flow_vol
                report_lines.append(f"      >> 资金空转率: {turnover:.1%} (理财申赎占总流水比例)")
            
            # 状态判定
            if w_est_holding > 100000:
                status = f"持有中(估算约{utils.format_currency(w_est_holding)})"
            elif w_redeem > w_purchase:
                status = f"净赎回(资金回流 {utils.format_currency(w_redeem - w_purchase)})"
            else:
                status = "基本持平"
            report_lines.append(f"      >> 资金状态: {status}")
            
            # 产品大类分布
            holding_struct = wealth.get('holding_structure', {})
            if holding_struct:
                 # 展示有持有量的
                 sorted_hold = sorted(holding_struct.items(), key=lambda x: x[1]['amount'], reverse=True)
                 hold_strs = [f"{k}在持{utils.format_currency(v['amount'])}" for k, v in sorted_hold]
                 report_lines.append(f"      >> 持有分布: {', '.join(hold_strs)}")
            else:
                 # 降级展示老版分布
                 cats = wealth.get('category_stats', {})
                 if cats:
                    top_cats = sorted(cats.items(), key=lambda x: x[1]['购入'] + x[1]['赎回'], reverse=True)
                    cat_strs = []
                    for c_name, c_data in top_cats:
                        vol = c_data['购入'] + c_data['赎回']
                        if vol > 100000:
                            cat_strs.append(f"{c_name}(交易{utils.format_currency(vol)})")
                    if cat_strs:
                         report_lines.append(f"      >> 交易分布: {', '.join(cat_strs)}")
        else:
             report_lines.append(f"    • 理财行为: 累计申购 {utils.format_currency(w_purchase)} (规模较小)")
        
        # 资金流向
        report_lines.append(f"    • 主要来源: {_get_top_counterparties_str(person, 'in', cleaned_data)}")
        report_lines.append(f"    • 主要去向: {_get_top_counterparties_str(person, 'out', cleaned_data)}")
        report_lines.append("")
    
    return report_lines


def _generate_company_section(company, profiles, core_persons, cleaned_data):
    """
    生成公司资金核查部分
    
    Args:
        company: 公司名称
        profiles: 资金画像字典
        core_persons: 核心人员列表
        cleaned_data: 清洗后的数据
        
    Returns:
        报告行列表
    """
    report_lines = []
    
    report_lines.append(f"➤ {company}")
    comp_profile = next((p for p in profiles.values() if company in p.get('entity_name', '')), None)
    
    if not comp_profile or not comp_profile['has_data']:
        report_lines.append("  (暂无详细流水数据)")
        report_lines.append("")
        return report_lines
    
    summary = comp_profile['summary']
    
    # 3.1 资金概况
    report_lines.append(f"  • 资金概况: 总流入 {utils.format_currency(summary['total_income'])} | 总流出 {utils.format_currency(summary['total_expense'])}")
    
    # 3.2 大客户/供应商
    top_in = _get_top_counterparties_str(company, 'in', cleaned_data, 5)
    top_out = _get_top_counterparties_str(company, 'out', cleaned_data, 5)
    report_lines.append(f"  • 主要资金来源(客户): {top_in}")
    report_lines.append(f"  • 主要资金去向(供应商): {top_out}")
    
    # 3.3 与核查对象往来 (高危检测)
    comp_df = cleaned_data.get(company)
    risky_trans = []
    if comp_df is not None:
        # 检查与核心人员往来
        rel_tx = comp_df[comp_df['counterparty'].isin(core_persons)]
        if not rel_tx.empty:
            groups = rel_tx.groupby('counterparty')[['income', 'expense']].sum()
            for name, row in groups.iterrows():
                if row['income'] > 0: risky_trans.append(f"收到 {name} {utils.format_currency(row['income'])}")
                if row['expense'] > 0: risky_trans.append(f"支付给 {name} {utils.format_currency(row['expense'])}")
    
    if risky_trans:
        report_lines.append(f"  • 【公私往来预警】: 发现直接资金往来!")
        for t in risky_trans:
            report_lines.append(f"    ⚠ {t}")
    else:
        report_lines.append(f"  • 公私往来: 未发现与核心人员的直接资金往来。")

    # 3.4 隐匿链路提示
    report_lines.append(f"  • 隐匿链路排查: 经穿透分析，未发现明显的第三方（如关联自然人、空壳公司）中转资金链路。")
    report_lines.append("")
    
    return report_lines


def _generate_suggestions_section(suspicions):
    """
    生成疑点与核查建议部分
    
    Args:
        suspicions: 疑点检测结果
        
    Returns:
        报告行列表
    """
    report_lines = []
    
    suggestion_idx = 1
    has_suggestions = False
    
    # 4.1 利益输送
    if suspicions['direct_transfers']:
        report_lines.append("【疑似利益输送】")
        for t in suspicions['direct_transfers']:
            report_lines.append(f"  • {_safe_format_date(t.get('date'))}: {t.get('person', '')} {t.get('direction', '')} {t.get('company', '')} {utils.format_currency(t.get('amount', 0))} (摘要: {t.get('description', '')})")
        report_lines.append(f"  ➡ 建议 {suggestion_idx}: 调取相关凭证，核实上述资金往来的业务背景。")
        suggestion_idx += 1
        has_suggestions = True
        report_lines.append("")

    # 4.2 隐形资产
    hidden = [item for sublist in suspicions['hidden_assets'].values() for item in sublist]
    if hidden:
        report_lines.append("【疑似隐形资产】")
        for h in hidden:
             report_lines.append(f"  • {_safe_format_date(h.get('date'))}: 支付 {utils.format_currency(h.get('amount', 0))} 给 {h.get('counterparty', '')} (摘要: {h.get('description', '')})")
        report_lines.append(f"  ➡ 建议 {suggestion_idx}: 核实上述大额支出是否用于购房/购车，并检查是否按规定申报。")
        suggestion_idx += 1
        has_suggestions = True
        report_lines.append("")
        
    # 4.3 异常高频/大额
    fixed = [item for sublist in suspicions['fixed_frequency'].values() for item in sublist]
    if fixed:
        report_lines.append("【异常规律性收入】")
        for f in fixed:
            report_lines.append(f"  • 每月{f['day_avg']}日左右收到约 {utils.format_currency(f['amount_avg'])} (共{f['occurrences']}次)")
        report_lines.append(f"  ➡ 建议 {suggestion_idx}: 核实该规律性收入的性质，排除兼职取酬或吃空饷嫌疑。")
        suggestion_idx += 1
        has_suggestions = True
        
    if not has_suggestions:
        report_lines.append("本次自动化分析未发现显著的硬性疑点。")
        report_lines.append(f"  ➡ 建议: 重点关注大额消费支出是否与收入水平匹配（见Excel底稿'大额现金明细'）。")

    return report_lines


def generate_official_report(profiles: Dict,
                            suspicions: Dict,
                            core_persons: List[str],
                            involved_companies: List[str],
                            output_path: str = None,
                            family_summary: Dict = None,
                            family_assets: Dict = None,
                            cleaned_data: Dict = None) -> str:
    """
    生成公文格式的核查结果分析报告（2026专业纪检优化版 v6）
    特点：
    1. 结论先行，风险分级
    2. 家庭全貌概览（包含房产/车辆/存款/理财总估值）
    3. 房产详细列表（一行一套）
    4. 深度理财分析（引入“撮合估算”算法，计算更真实的当前持有量）
    5. 公司资金核查（专章）
    """
    # 同时也生成HTML报告
    html_path = output_path.replace('.txt', '.html') if output_path else config.OUTPUT_REPORT_FILE.replace('.docx', '.html')
    generate_html_report(profiles, suspicions, core_persons, involved_companies, html_path, family_summary, family_assets, cleaned_data)
    
    if output_path is None:
        output_path = config.OUTPUT_REPORT_FILE.replace('.docx', '.txt')
    
    logger.info(f'正在生成专业版公文报告(V6): {output_path}')
    
    report_lines = []
    
    # === 报告开始 ===
    report_lines.append(f"{config.REPORT_TITLE}")
    report_lines.append("=" * 60)
    
    # 1. 核心结论 (Executive Summary)
    report_lines.extend(_generate_report_conclusion(profiles, suspicions, core_persons, involved_companies))

    # 2. 家庭/个人详情 (Family Section)
    report_lines.append("二、家庭资产与资金画像")
    report_lines.append("-" * 60)
    
    households = _group_into_households(core_persons, family_summary)
    for household in households:
        report_lines.extend(_generate_family_section(household, family_assets, profiles, cleaned_data))

    # 3. 公司资金核查 (Company Section)
    report_lines.append("三、公司资金核查")
    report_lines.append("-" * 60)
    
    if not involved_companies:
        report_lines.append("本次未涉及公司核查。")
    else:
        for company in involved_companies:
            report_lines.extend(_generate_company_section(company, profiles, core_persons, cleaned_data))

    # 4. 疑点与核查建议
    report_lines.append("四、主要疑点与核查建议")
    report_lines.append("-" * 60)
    report_lines.extend(_generate_suggestions_section(suspicions))

    report_lines.append("")
    report_lines.append("=" * 60)
    # report_lines.append(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append("注: 本报告基于提供的电子数据分析生成，线索仅供参考。")
    
    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    logger.info(f'公文报告生成完成: {output_path}')
    return output_path

def _analyze_person_asset_trails(person_name: str, output_dir: str = 'output') -> List[str]:
    """
    针对单个核心人员的资产线索分析 (车/房)
    读取该人员的清洗后Excel进行深度挖掘
    """
    import os
    text_lines = []
    
    file_path = os.path.join(output_dir, 'cleaned_data', '个人', f'{person_name}_合并流水.xlsx')
    if not os.path.exists(file_path):
        return []
        
    try:
        df = pd.read_excel(file_path)
        
        # Helper: 关键词匹配
        def has_kw(row, kws):
            t = str(row.get('交易对手', '')) + str(row.get('交易摘要', ''))
            return any(k in t for k in kws)

        # === 车辆分析 ===
        car_buy_kws = ['汽车', '4S', '绿地金凯', '宝马', '奔驰', '奥迪', '保时捷']
        car_loan_kws = ['汽车金融', '上汽通用', '车贷', '通用金融', '宝马金融', '奔驰金融']
        
        # 1. 购车首付/全款
        car_payments = df[df.apply(lambda x: has_kw(x, car_buy_kws), axis=1) & (df['支出(元)'] > 10000)].sort_values('交易时间')
        if not car_payments.empty:
            for _, row in car_payments.iterrows():
                text_lines.append(f"     [车辆购置] {row['交易时间']} 向 [{row['交易对手']}] 支付 {utils.format_currency(row['支出(元)'])}")
        
        # 2. 车贷还款
        car_repayments = df[df.apply(lambda x: has_kw(x, car_loan_kws), axis=1) & (df['支出(元)'] > 0)].sort_values('交易时间')
        if not car_repayments.empty:
            total = car_repayments['支出(元)'].sum()
            times = len(car_repayments)
            lender = car_repayments.iloc[0]['交易对手']
            mode_val = car_repayments['支出(元)'].mode()
            monthly = mode_val[0] if not mode_val.empty else car_repayments['支出(元)'].mean()
            text_lines.append(f"     [车贷还款] 向 {lender} 累计还款 {times} 次，共计 {utils.format_currency(total)} (推测月供: {utils.format_currency(monthly)})")

        # === 房产分析 ===
        # 关键词：地产, 置业, 房地产, 首付
        house_buy_kws = ['地产', '置业', '房地产', '万科', '保利', '华润置地', '龙湖', '购房', '首期', '定金']
        # 关键词：住房贷款, 个人贷款, 按揭 (房贷通常比较隐晦, 往往只显示"贷款归还"或"利息")
        # 这里只抓特征明显的
        house_loan_kws = ['住房贷款', '个人住房', '按揭', '房贷']
        
        # 1. 购房支出
        house_payments = df[df.apply(lambda x: has_kw(x, house_buy_kws), axis=1) & (df['支出(元)'] > 50000)].sort_values('交易时间')
        if not house_payments.empty:
            for _, row in house_payments.iterrows():
                text_lines.append(f"     [房产购置] {row['交易时间']} 向 [{row['交易对手']}] 支付 {utils.format_currency(row['支出(元)'])} (疑似购房款/首付)")
                
        # 2. 房贷还款
        house_repayments = df[df.apply(lambda x: has_kw(x, house_loan_kws), axis=1) & (df['支出(元)'] > 0)].sort_values('交易时间')
        if not house_repayments.empty:
             total = house_repayments['支出(元)'].sum()
             text_lines.append(f"     [房贷还款] 发现明确的房贷摘要/对手方记录，累计还款 {utils.format_currency(total)}")

    except Exception as e:
        logger.error(f"分析资产线索失败 {person_name}: {e}")
        
    return text_lines

import glob
import os

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>信息查询结果分析报告</title>
    <style>
        body {
            font-family: 'SimSun', '宋体', sans-serif;
            line-height: 1.8;
            color: #333;
            margin: 0 auto;
            padding: 20px;
            max-width: 900px;
            background-color: #f9f9f9;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            border-radius: 8px;
        }
        .page {
            padding: 20px;
            background-color: #fff;
            border-radius: 5px;
        }
        h1 {
            font-size: 28px;
            text-align: center;
            margin-bottom: 30px;
            color: #2c3e50;
        }
        h2 {
            font-size: 24px;
            color: #2c3e50;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
            margin-top: 40px;
        }
        h3 {
            font-size: 20px;
            color: #34495e;
            margin-top: 30px;
        }
        p {
            margin-bottom: 15px;
            text-indent: 2em;
        }
        strong {
            color: #2c3e50;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        .section-title {
            font-size: 22px;
            font-weight: bold;
            margin-top: 30px;
            margin-bottom: 15px;
            color: #2c3e50;
            border-bottom: 1px solid #ccc;
            padding-bottom: 5px;
        }
        .subsection-title {
            font-size: 18px;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 10px;
            color: #34495e;
        }
        .footer {
            text-align: center;
            margin-top: 50px;
            font-size: 14px;
            color: #777;
        }
</style>
</head>
<body>
    {{CONTENT}}
    <div class="footer">
        <p>(本报告由资金穿透与关联排查系统自动生成)</p>
    </div>
</body>
</html>
"""

def _generate_html_conclusion(profiles, suspicions, core_persons, involved_companies):
    """
    生成HTML报告的核查结论部分
    
    Args:
        profiles: 资金画像字典
        suspicions: 疑点检测结果
        core_persons: 核心人员列表
        involved_companies: 涉及公司列表
        
    Returns:
        HTML内容字符串
    """
    import datetime
    
    total_trans = sum(p['summary']['transaction_count'] for p in profiles.values() if p['has_data'])
    
    # 风险评级
    risk_assessment = "低风险"
    direct_sus_count = len(suspicions['direct_transfers'])
    hidden_sus_count = sum(len(v) for v in suspicions['hidden_assets'].values())
    if direct_sus_count > 0 or hidden_sus_count > 0:
        risk_assessment = "中高风险" if direct_sus_count > 5 else "关注级"
        
    risk_color = "green"
    if risk_assessment == "中高风险": risk_color = "red"
    elif risk_assessment == "关注级": risk_color = "orange"

    content_html = f"""
    <div class="page">
        <h1>信息查询结果分析报告</h1>
        <p style="text-align:center; color:#888;">生成时间: {datetime.datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
        
        <div class="section-title">一、核查结论</div>
        <div style="background-color:#f9f9f9; padding:15px; border-left: 5px solid {risk_color}; margin-bottom:20px;">
            <p><strong>【总体评价】</strong>: 本次核查对象共 {len(core_persons)} 人及 {len(involved_companies)} 家关联公司，总体风险评级为 <strong><span style="color:{risk_color}">{_escape_html(risk_assessment)}</span></strong>。</p>
            <p><strong>【数据概况】</strong>: 累计分析银行流水 {total_trans} 条。</p>
    """
    
    # 高流水预警
    high_flow_persons = []
    for p_name, p_data in profiles.items():
        if p_name in core_persons and p_data['has_data']:
            total_vol = p_data['summary']['total_income'] + p_data['summary']['total_expense']
            if total_vol > 50000000:
                high_flow_persons.append(_escape_html(p_name))
    if high_flow_persons:
        content_html += f"""<p><strong>【特别说明】</strong>: <span style="color:red">{', '.join(high_flow_persons)}</span> 银行流水规模较大，主要系理财产品频繁申赎所致(详见下文)。</p>"""
    
    if direct_sus_count == 0 and hidden_sus_count == 0:
        content_html += f"""<p><strong>【主要发现】</strong>: 未发现核心人员与涉案公司存在直接利益输送，亦未发现明显的隐形房产/车辆购置线索。</p>"""
    else:
        content_html += f"""<p><strong>【主要发现】</strong>: 发现 {direct_sus_count} 笔疑似直接利益输送，{hidden_sus_count} 笔疑似隐形资产线索。</p>"""
    content_html += "</div></div>"
    
    return content_html


def _generate_html_family_section(profiles, core_persons, family_summary, family_assets, cleaned_data):
    """
    生成HTML报告的家庭板块 (V2.0 深度版)
    """
    import utils
    
    content_html = """<div class="page"><div class="section-title">二、家庭资产与资金画像</div>"""
    households = _group_into_households(core_persons, family_summary)
    
    for household in households:
        title = "、".join(household) + " 家庭"
        if len(household) == 1: title = f"{household[0]} 个人"
        
        # 1. 家庭全貌统计
        fam_props_list = []
        fam_cars_num = 0
        fam_total_deposit_est = 0.0
        fam_total_wealth_est = 0.0
        
        for person in household:
            # 资产数据
            props = family_assets.get(person, {}).get('房产', []) if family_assets else []
            fam_props_list.extend([(person, p) for p in props])
            fam_cars_num += len(family_assets.get(person, {}).get('车辆', [])) if family_assets else 0
            
            # 资金数据
            p_prof = profiles.get(person)
            if p_prof and p_prof['has_data']:
                # 【2026-01-22 修复】使用真实银行余额
                deposit = _get_real_bank_balance(person, profiles)
                fam_total_deposit_est += deposit
                wealth = p_prof.get('wealth_management', {})
                w_holding = wealth.get('estimated_holding', 0.0)
                if w_holding == 0 and 'estimated_holding' not in wealth:
                    w_holding = max(0, wealth.get('wealth_purchase', 0) - wealth.get('wealth_redemption', 0))
                if w_holding > 0: fam_total_wealth_est += w_holding
        
        content_html += f"""<div class="subsection-title">➤ {_escape_html(title)}</div>"""
        
        # 家庭概览框
        content_html += f"""
        <div style="border: 1px solid #ddd; padding: 10px; background-color: #fcfcfc; margin-bottom: 15px;">
            <p><strong>【家庭资产全貌】</strong> <span style="font-size:12px; color:#888;">(注: 房产/车辆信息需接入不动产/车管数据)</span></p>
            <p>• <strong>房产合计: {len(fam_props_list)} 套</strong> <span style="color:#999; font-size:12px;">(系统登记)</span></p>
            """
        if fam_props_list:
             content_html += '<ul style="margin-top:0; margin-bottom:5px; font-size:14px; color:#555;">'
             for owner, p in fam_props_list:
               addr = _escape_html(p.get('房地坐落', '未知地址'))
               content_html += f"<li>[{_escape_html(owner)}] {addr}</li>"
             content_html += '</ul>'
        else:
             content_html += '<p style="text-indent:2em; color:#999; font-size:12px;">(未发现系统登记房产，建议调取线下档案)</p>'
             
        content_html += f"""
            <p>• <strong>车辆合计: {fam_cars_num} 辆</strong></p>
            <p>• <strong>资金沉淀 (估算):</strong> 存款约 <b>{utils.format_currency(fam_total_deposit_est)}</b> | 理财约 <b>{utils.format_currency(fam_total_wealth_est)}</b></p>
        </div>
        """
        
        # 2. 个人详情
        for person in household:
            content_html += f"""<h3 style="margin-left:0; font-size:16px;">[{_escape_html(person)}]</h3>"""
            profile = next((p for p in profiles.values() if person in p.get('entity_name', '')), None)
            
            # --- 基础身份信息 (Placeholder) ---
            content_html += """
            <table style="width:100%; border:none; margin-bottom:10px;">
                <tr>
                    <td style="border:none; padding:2px;">• 身份证号: <span style="color:#999;">(需补充)</span></td>
                    <td style="border:none; padding:2px;">• 工作单位: <span style="color:#999;">(需补充)</span></td>
                </tr>
            </table>
            """
            
            if not profile or not profile['has_data']:
                content_html += "<p>(暂无详细流水数据)</p>"; continue
            
            summary = profile['summary']
            income = profile.get('income_structure', {})
            wealth = profile.get('wealth_management', {})
            
            # 资金规模
            content_html += f"""<p><strong>资金规模</strong>: 流入 {utils.format_currency(summary['total_income'])} / 流出 {utils.format_currency(summary['total_expense'])}</p>"""
            
            # 收入结构
            salary_details = income.get('salary_details', [])
            yearly_sal = {}
            for item in salary_details:
                 y = str(item.get('日期', ''))[:4]
                 if y.isdigit(): yearly_sal[y] = yearly_sal.get(y, 0) + item.get('金额', 0)
            sal_desc = ""
            if yearly_sal:
                 sal_desc = " (" + "; ".join([f"{y}年:{utils.format_currency(v)}" for y, v in sorted(yearly_sal.items())]) + ")"
            
            ratio_val = summary['salary_ratio']
            ratio_str = f"{ratio_val:.1%}"
            ratio_style = "color:red; font-weight:bold;" if ratio_val < 0.5 else ""
            
            content_html += f"""
            <p><strong>工资收入</strong>: 累计 {utils.format_currency(income.get('salary_income', 0))} {_escape_html(sal_desc)}</p>
            <p><strong>收支匹配</strong>: 工资占比 <span style="{ratio_style}">{_escape_html(ratio_str)}</span></p>
            """
            if ratio_val < 0.5:
                content_html += f"""<p style="text-indent:2em; color:red; font-size:13px;">⚠ 预警: 工资收入无法覆盖消费支出 (占比低于50%)，存在资金来源不明风险。</p>"""
            
            # 理财分析
            w_purchase = wealth.get('wealth_purchase', 0)
            if w_purchase > 100000:
                content_html += f"""<p><strong>理财行为</strong>: 申购 {utils.format_currency(w_purchase)} / 赎回 {utils.format_currency(wealth.get('wealth_redemption', 0))}</p>"""
            
            # 流向
            content_html += f"""\u003cp\u003e\u003cstrong\u003e主要去向\u003c/strong\u003e: {_escape_html(_get_top_counterparties_str(person, 'out', cleaned_data, 5))}\u003c/p\u003e"""
            content_html += "\u003chr style='border:0; border-top:1px dashed #eee; margin:10px 0;'\u003e"

    content_html += "</div>" # End Household Page
    return content_html


def _generate_html_company_section(profiles, involved_companies, core_persons, cleaned_data):
    """
    生成HTML报告的公司资金核查部分 (V2.0 深度版)
    """
    import utils
    
    content_html = """<div class="page"><div class="section-title">三、公司资金核查</div>"""
    if not involved_companies:
        content_html += "<p>本次未涉及公司核查。</p>"
    else:
        for company in involved_companies:
            content_html += f"""<div class="subsection-title">➤ {_escape_html(company)}</div>"""
            comp_profile = next((p for p in profiles.values() if company in p.get('entity_name', '')), None)
            
            if not comp_profile or not comp_profile['has_data']:
                content_html += "<p>(暂无详细流水数据)</p>"; continue
            
            summary = comp_profile['summary']
            
            # 1. 资金规模
            content_html += f"""
            <div style="background-color:#f8f9fa; padding:10px; border-left:4px solid #007bff; margin-bottom:10px;">
                <p><strong>【资金规模】</strong></p>
                <p>• 累计进账: <b>{utils.format_currency(summary['total_income'])}</b> | 累计出账: <b>{utils.format_currency(summary['total_expense'])}</b></p>
                <p>• 交易笔数: {_escape_html(str(summary['transaction_count']))} 笔</p>
            </div>
            """
            
            # 2. 上下游分析
            top_in = _escape_html(_get_top_counterparties_str(company, 'in', cleaned_data, 5))
            top_out = _escape_html(_get_top_counterparties_str(company, 'out', cleaned_data, 5))
            content_html += f"""<p><strong>主要资金来源</strong>: {top_in}</p>"""
            content_html += f"""<p><strong>主要资金去向</strong>: {top_out}</p>"""
            
            # 3. 关联交易 (重点)
            comp_df = cleaned_data.get(company) if cleaned_data else None
            risky_html = ""
            if comp_df is not None:
                # 3.1 与核心人员往来
                rel_tx = comp_df[comp_df['counterparty'].isin(core_persons)]
                if not rel_tx.empty:
                    groups = rel_tx.groupby('counterparty')[['income', 'expense']].sum()
                    risky_items = []
                    for name, row in groups.iterrows():
                        if row['income'] > 0 or row['expense'] > 0:
                            risky_items.append(f"{_escape_html(name)} (收:{utils.format_currency(row['income'])}/付:{utils.format_currency(row['expense'])})")
                    if risky_items:
                        risky_html += f"""<p style="color:red; background-color:#fff0f0; padding:5px;">⚠ <strong>利益输送嫌疑</strong>: 发现与核心人员存在直接往来: {', '.join(risky_items)}</p>"""
                
                # 3.2 大额现金
                cash_tx = comp_df[comp_df['is_cash'] == True]
                if not cash_tx.empty:
                    cash_in = cash_tx['income'].sum()
                    cash_out = cash_tx['expense'].sum()
                    if cash_in + cash_out > 50000:
                        risky_html += f"""<p><strong>现金分析</strong>: 存在现金操作 (存:{utils.format_currency(cash_in)} / 取:{utils.format_currency(cash_out)})，请核实用途。</p>"""
            
            if risky_html: 
                content_html += risky_html
            else: 
                content_html += "<p>• <strong>关联排查</strong>: 未发现与核心人员的直接资金往来，无大额现金预警。</p>"
            
            content_html += "<br>"
            
    content_html += "</div>"
    return content_html


def _generate_html_suggestions_section(suspicions):
    """
    生成HTML报告的疑点与核查建议部分
    
    Args:
        suspicions: 疑点检测结果
        
    Returns:
        HTML内容字符串
    """
    import utils
    
    content_html = """<div class="page"><div class="section-title">四、主要疑点与核查建议</div>"""
    has_suggestions = False
    
    # 疑似利益输送
    if suspicions['direct_transfers']:
        content_html += """<p><strong>【疑似利益输送】</strong></p><ul>"""
        for t in suspicions['direct_transfers']:
            content_html += f"""<li>{_safe_format_date(t.get('date'))}: {_escape_html(t.get('person', ''))} {_escape_html(t.get('direction', ''))} {_escape_html(t.get('company', ''))} {utils.format_currency(t.get('amount', 0))} <br><span style="color:#666; font-size:12px;">(摘要: {_escape_html(t.get('description', ''))})</span></li>"""
        content_html += "</ul><p class='highlight'>➡ 建议: 调取相关凭证，核实上述资金往来的业务背景。</p>"
        has_suggestions = True

    # 隐形资产
    hidden = [item for sublist in suspicions['hidden_assets'].values() for item in sublist]
    if hidden:
        content_html += """<p><strong>【疑似隐形资产】</strong></p><ul>"""
        for h in hidden:
             content_html += f"""<li>{_safe_format_date(h.get('date'))}: 支付 {utils.format_currency(h.get('amount', 0))} 给 {_escape_html(h.get('counterparty', ''))} <br><span style="color:#666; font-size:12px;">(摘要: {_escape_html(h.get('description', ''))})</span></li>"""
        content_html += "</ul><p class='highlight'>➡ 建议: 核实上述大额支出是否用于购房/购车，并检查是否按规定申报。</p>"
        has_suggestions = True
        
    if not has_suggestions:
        content_html += "<p>本次自动化分析未发现显著的硬性疑点。</p><p>➡ 建议: 重点关注大额消费支出是否与收入水平匹配（见Excel底稿'大额现金明细'）。</p>"
        
    content_html += "</div>"
    
    return content_html


def generate_html_report(profiles, suspicions, core_persons, involved_companies, output_path, family_summary=None, family_assets=None, cleaned_data=None):
    """
    生成HTML格式的分析报告 (V6版 - 匹配最新文本报告逻辑 - Fix Placeholder)
    """
    import os
    import json
    import datetime
    import config
    import utils
    import account_analyzer

    logger = utils.setup_logger(__name__)
    logger.info(f'正在生成HTML文本分析报告(V6): {output_path}')
    
    # Ensure lists
    if involved_companies is None: involved_companies = []
    if core_persons is None: core_persons = []
    
    # 构建报告内容
    content_html = ""
    
    # 1. 标题与前言（核查结论）
    content_html += _generate_html_conclusion(profiles, suspicions, core_persons, involved_companies)
    
    # 2. 家庭板块
    content_html += _generate_html_family_section(profiles, core_persons, family_summary, family_assets, cleaned_data)
    
    # 3. 公司资金核查
    content_html += _generate_html_company_section(profiles, involved_companies, core_persons, cleaned_data)
    
    # 4. 疑点与核查建议
    content_html += _generate_html_suggestions_section(suspicions)
    
    # 家庭板块
    content_html += """<div class="page"><div class="section-title">二、家庭资产与资金画像</div>"""
    households = _group_into_households(core_persons, family_summary)
    
    for household in households:
        title = "、".join(household) + " 家庭"
        if len(household) == 1: title = f"{household[0]} 个人"
        
        # 1. 家庭全貌统计
        fam_props_list = []
        fam_cars_num = 0
        fam_total_deposit_est = 0.0
        fam_total_wealth_est = 0.0
        
        for person in household:
            props = family_assets.get(person, {}).get('房产', []) if family_assets else []
            fam_props_list.extend([(person, p) for p in props])
            fam_cars_num += len(family_assets.get(person, {}).get('车辆', [])) if family_assets else 0
            
            p_prof = profiles.get(person)
            if p_prof and p_prof['has_data']:
                # 【2026-01-22 修复】使用真实银行余额
                deposit = _get_real_bank_balance(person, profiles)
                fam_total_deposit_est += deposit
                wealth = p_prof.get('wealth_management', {})
                w_holding = wealth.get('estimated_holding', 0.0)
                if w_holding == 0 and 'estimated_holding' not in wealth:
                    w_holding = max(0, wealth.get('wealth_purchase', 0) - wealth.get('wealth_redemption', 0))
                if w_holding > 0: fam_total_wealth_est += w_holding
        
        content_html += f"""<div class="subsection-title">➤ {_escape_html(title)}</div>"""
        
        # 家庭概览框
        content_html += f"""
        <div style="border: 1px solid #ddd; padding: 10px; background-color: #fcfcfc; margin-bottom: 15px;">
            <p><strong>【家庭资产全貌】</strong> (截至数据提取日)</p>
            <p>• <strong>房产合计: {len(fam_props_list)} 套</strong></p>
            <ul style="margin-top:0; margin-bottom:5px; font-size:14px; color:#555;">
        """
        for owner, p in fam_props_list:
            addr = _escape_html(p.get('房地坐落', '未知地址'))
            price = p.get('交易金额', 0)
            price_str = f"{utils.format_currency(price)}" if price > 0 else "价格未知"
            area = _escape_html(str(p.get('建筑面积', 0)))
            content_html += f"<li>[{_escape_html(owner)}] {addr} ({area}平, {price_str})</li>"
        
        content_html += f"""
            </ul>
            <p>• <strong>车辆合计: {fam_cars_num} 辆</strong></p>
            <p>• <strong>资金沉淀 (估算):</strong> 存款约 <b>{utils.format_currency(fam_total_deposit_est)}</b> | 理财约 <b>{utils.format_currency(fam_total_wealth_est)}</b></p>
        </div>
        """
        
        # 2. 个人详情
        for person in household:
            content_html += f"""<h3 style="margin-left:0; font-size:16px;">[{_escape_html(person)}]</h3>"""
            profile = next((p for p in profiles.values() if person in p.get('entity_name', '')), None)
            if not profile or not profile['has_data']:
                content_html += "<p>(暂无详细流水数据)</p>"; continue
            
            summary = profile['summary']
            income = profile.get('income_structure', {})
            wealth = profile.get('wealth_management', {})
            
            # 资金规模
            self_transfer_vol = wealth.get('self_transfer_income', 0) + wealth.get('self_transfer_expense', 0)
            self_note = f"<span style='color:#888'>(含内部互转 {utils.format_currency(self_transfer_vol)})</span>" if self_transfer_vol > 500000 else ""
            content_html += f"""<p><strong>资金规模</strong>: 流入 {utils.format_currency(summary['total_income'])} / 流出 {utils.format_currency(summary['total_expense'])} {self_note}</p>"""
            
            # 收入结构
            salary_details = income.get('salary_details', [])
            yearly_sal = {}
            for item in salary_details:
                 y = str(item.get('日期', ''))[:4]
                 if y.isdigit(): yearly_sal[y] = yearly_sal.get(y, 0) + item.get('金额', 0)
            sal_desc = ""
            if yearly_sal:
                 sal_desc = " (" + "; ".join([f"{_escape_html(y)}年:{utils.format_currency(v)}" for y, v in sorted(yearly_sal.items())]) + ")"
            content_html += f"""<p><strong>收入结构</strong>: 工资性收入 {utils.format_currency(income.get('salary_income', 0))} (占比 {summary['salary_ratio']:.1%}){_escape_html(sal_desc)}</p>"""
            
            # 理财深度分析
            w_purchase = wealth.get('wealth_purchase', 0)
            w_redeem = wealth.get('wealth_redemption', 0)
            w_est_holding = wealth.get('estimated_holding', 0)
            
            if w_purchase > 100000:
                content_html += f"""<p><strong>理财行为</strong>: 申购 {utils.format_currency(w_purchase)} / 赎回 {utils.format_currency(w_redeem)}</p>"""
                flow_vol = summary['total_income'] + summary['total_expense']
                if flow_vol > 0:
                    turnover = (w_purchase + w_redeem) / flow_vol
                    content_html += f"""<p style="text-indent: 2em;">>> <span style="color:#666">资金空转率: <strong>{turnover:.1%}</strong> (理财申赎占总流水比例)</span></p>"""
                
                status_str = ""
                if w_est_holding > 100000:
                    status_str = f"持有中 (估算约 <b>{utils.format_currency(w_est_holding)}</b>)"
                elif w_redeem > w_purchase:
                    status_str = f"净赎回 (资金回流 {utils.format_currency(w_redeem - w_purchase)})"
                else:
                    status_str = "基本持平"
                content_html += f"""<p style="text-indent: 2em;">>> 资金状态: <span style="background-color:#e6f7ff; padding:2px 5px;">{status_str}</span></p>"""
                
                # 持有分布
                holding_struct = wealth.get('holding_structure', {})
                if holding_struct:
                     sorted_hold = sorted(holding_struct.items(), key=lambda x: x[1]['amount'], reverse=True)
                     hold_strs = [f"{_escape_html(k)}在持{utils.format_currency(v['amount'])}" for k, v in sorted_hold]
                     content_html += f"""<p style="text-indent: 2em;">>> 持有分布: {_escape_html(', '.join(hold_strs))}</p>"""
            
            # 流向
            content_html += f"""<p><strong>主要去向</strong>: {_escape_html(_get_top_counterparties_str(person, 'out', cleaned_data))}</p>"""
            content_html += "<hr style='border:0; border-top:1px dashed #eee; margin:10px 0;'>"
    content_html += "</div>" # End Household Page
    
    # 3. 公司资金核查 (Company Section)
    content_html += """<div class="page"><div class="section-title">三、公司资金核查</div>"""
    if not involved_companies:
        content_html += "<p>本次未涉及公司核查。</p>"
    else:
        for company in involved_companies:
            content_html += f"""<div class="subsection-title">➤ {_escape_html(company)}</div>"""
            comp_profile = next((p for p in profiles.values() if company in p.get('entity_name', '')), None)
            
            if not comp_profile or not comp_profile['has_data']:
                content_html += "<p>(暂无详细流水数据)</p>"; continue
            
            summary = comp_profile['summary']
            content_html += f"""<p>• <strong>资金概况</strong>: 总流入 {utils.format_currency(summary['total_income'])} | 总流出 {utils.format_currency(summary['total_expense'])}</p>"""
            
            top_in = _escape_html(_get_top_counterparties_str(company, 'in', cleaned_data, 5))
            top_out = _escape_html(_get_top_counterparties_str(company, 'out', cleaned_data, 5))
            content_html += f"""<p>• <strong>主要客户(来源)</strong>: {top_in}</p>"""
            content_html += f"""<p>• <strong>主要供应商(去向)</strong>: {top_out}</p>"""
            
            # 风险
            comp_df = cleaned_data.get(company)
            risky_html = ""
            if comp_df is not None:
                rel_tx = comp_df[comp_df['counterparty'].isin(core_persons)]
                if not rel_tx.empty:
                    groups = rel_tx.groupby('counterparty')[['income', 'expense']].sum()
                    risky_items = []
                    for name, row in groups.iterrows():
                        if row['income'] > 0 or row['expense'] > 0: risky_items.append(f"{_escape_html(name)} (收:{utils.format_currency(row['income'])}/付:{utils.format_currency(row['expense'])})")
                    if risky_items:
                        risky_html = f"""<p style="color:red">⚠ 发现与核心人员直接往来: {', '.join(risky_items)}</p>"""
            
            if risky_html: content_html += risky_html
            else: content_html += "<p>• <strong>公私往来</strong>: 未发现与核心人员的直接资金往来。</p>"
            content_html += "<br>"
    content_html += "</div>"

    # 4. 疑点与核查建议
    content_html += """<div class="page"><div class="section-title">四、主要疑点与核查建议</div>"""
    has_suggestions = False
    
    # 疑似利益输送
    if suspicions['direct_transfers']:
        content_html += """<p><strong>【疑似利益输送】</strong></p><ul>"""
        for t in suspicions['direct_transfers']:
            content_html += f"""<li>{_safe_format_date(t.get('date'))}: {_escape_html(t.get('person', ''))} {_escape_html(t.get('direction', ''))} {_escape_html(t.get('company', ''))} {utils.format_currency(t.get('amount', 0))} <br><span style="color:#666; font-size:12px;">(摘要: {_escape_html(t.get('description', ''))})</span></li>"""
        content_html += "</ul><p class='highlight'>➡ 建议: 调取相关凭证，核实上述资金往来的业务背景。</p>"
        has_suggestions = True

    # 隐形资产
    hidden = [item for sublist in suspicions['hidden_assets'].values() for item in sublist]
    if hidden:
        content_html += """<p><strong>【疑似隐形资产】</strong></p><ul>"""
        for h in hidden:
             content_html += f"""<li>{_safe_format_date(h.get('date'))}: 支付 {utils.format_currency(h.get('amount', 0))} 给 {_escape_html(h.get('counterparty', ''))} <br><span style="color:#666; font-size:12px;">(摘要: {_escape_html(h.get('description', ''))})</span></li>"""
        content_html += "</ul><p class='highlight'>➡ 建议: 核实上述大额支出是否用于购房/购车，并检查是否按规定申报。</p>"
        has_suggestions = True
        
    if not has_suggestions:
        content_html += "<p>本次自动化分析未发现显著的硬性疑点。</p><p>➡ 建议: 重点关注大额消费支出是否与收入水平匹配（见Excel底稿'大额现金明细'）。</p>"
        
    content_html += "</div>"
    
    # Replace placeholder (Handle both types to be safe)
    final_html = HTML_TEMPLATE.replace('{{CONTENT}}', content_html).replace('<!-- CONTENT_PLACEHOLDER -->', content_html)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    logger.info(f"HTML文本报告(V6)生成完毕: {output_path}")
    return output_path


# ============================================================
# Word 文档导出 (Phase 1.4 - 2026-01-18 新增)
# ============================================================

def generate_word_report(profiles: Dict,
                         suspicions: Dict,
                         core_persons: List[str],
                         involved_companies: List[str],
                         output_path: str = None,
                         family_summary: Dict = None,
                         family_assets: Dict = None,
                         cleaned_data: Dict = None) -> str:
    """
    使用 python-docx 生成专业 Word 审计报告
    
    Args:
        profiles: 资金画像字典
        suspicions: 疑点检测结果
        core_persons: 核心人员列表
        involved_companies: 涉及公司列表
        output_path: 输出路径
        family_summary: 家庭关系摘要
        family_assets: 家庭资产数据
        cleaned_data: 清洗后的数据
        
    Returns:
        生成的 Word 文件路径
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
    except ImportError:
        logger.warning('python-docx 未安装，跳过 Word 报告生成。请执行: pip install python-docx')
        return None
    
    # 参数验证
    if profiles is None:
        logger.error('generate_word_report: profiles 参数不能为 None')
        return None
    if suspicions is None:
        logger.error('generate_word_report: suspicions 参数不能为 None')
        return None
    if core_persons is None:
        logger.error('generate_word_report: core_persons 参数不能为 None')
        return None
    if involved_companies is None:
        logger.error('generate_word_report: involved_companies 参数不能为 None')
        return None
    
    # 确保参数是正确的类型
    if not isinstance(profiles, dict):
        logger.error(f'generate_word_report: profiles 必须是字典类型，实际类型: {type(profiles)}')
        return None
    if not isinstance(suspicions, dict):
        logger.error(f'generate_word_report: suspicions 必须是字典类型，实际类型: {type(suspicions)}')
        return None
    if not isinstance(core_persons, list):
        logger.error(f'generate_word_report: core_persons 必须是列表类型，实际类型: {type(core_persons)}')
        return None
    if not isinstance(involved_companies, list):
        logger.error(f'generate_word_report: involved_companies 必须是列表类型，实际类型: {type(involved_companies)}')
        return None
    
    if output_path is None:
        output_path = os.path.join(config.OUTPUT_DIR, 'analysis_results', '审计分析报告.docx')
    
    logger.info(f'正在生成 Word 审计报告: {output_path}')
    
    try:
        doc = Document()
    except Exception as e:
        logger.error(f'创建 Word 文档失败: {e}')
        return None
    
    # 设置默认字体
    try:
        style = doc.styles['Normal']
        style.font.name = '宋体'
        style.font.size = Pt(12)
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    except Exception as e:
        logger.warning(f'设置默认字体失败: {e}，使用默认字体')
    
    # ========== 1. 标题页 ==========
    try:
        title = doc.add_heading(config.REPORT_TITLE, level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception as e:
        logger.error(f'添加标题失败: {e}')
        return None
    
    # 生成时间
    try:
        doc.add_paragraph()
        time_para = doc.add_paragraph()
        time_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        time_run = time_para.add_run(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M")}')
        time_run.font.size = Pt(11)
        time_run.font.color.rgb = RGBColor(128, 128, 128)
    except Exception as e:
        logger.warning(f'添加生成时间失败: {e}')
    
    try:
        doc.add_page_break()
    except Exception as e:
        logger.warning(f'添加分页符失败: {e}')
    
    # ========== 2. 核查结论 ==========
    try:
        doc.add_heading('一、核查结论', level=1)
    except Exception as e:
        logger.error(f'添加核查结论标题失败: {e}')
        return None
    
    # 安全计算统计数据
    try:
        total_trans = 0
        for p in profiles.values():
            if isinstance(p, dict) and p.get('has_data', False):
                summary = p.get('summary', {})
                if isinstance(summary, dict):
                    total_trans += summary.get('transaction_count', 0)
    except Exception as e:
        logger.warning(f'计算交易总数失败: {e}')
        total_trans = 0
    
    try:
        direct_sus_count = len(suspicions.get('direct_transfers', []))
        hidden_sus_count = sum(len(v) for v in suspicions.get('hidden_assets', {}).values())
    except Exception as e:
        logger.warning(f'计算疑点数量失败: {e}')
        direct_sus_count = 0
        hidden_sus_count = 0
    
    risk_assessment = "低风险"
    if direct_sus_count > 0 or hidden_sus_count > 0:
        risk_assessment = "中高风险" if direct_sus_count > 5 else "关注级"
    
    try:
        p = doc.add_paragraph()
        p.add_run('【总体评价】').bold = True
        p.add_run(f'本次核查对象共 {len(core_persons)} 人及 {len(involved_companies)} 家关联公司，')
        risk_run = p.add_run(f'总体风险评级为 [{risk_assessment}]。')
        if risk_assessment == "中高风险":
            risk_run.font.color.rgb = RGBColor(255, 0, 0)
    except Exception as e:
        logger.error(f'添加总体评价段落失败: {e}')
        return None
    
    try:
        p2 = doc.add_paragraph()
        p2.add_run('【数据概况】').bold = True
        p2.add_run(f'累计分析银行流水 {total_trans} 条。')
    except Exception as e:
        logger.warning(f'添加数据概况段落失败: {e}')
    
    # 主要发现
    try:
        p3 = doc.add_paragraph()
        p3.add_run('【主要发现】').bold = True
        if direct_sus_count == 0 and hidden_sus_count == 0:
            p3.add_run('未发现核心人员与涉案公司存在直接利益输送。')
        else:
            finding = p3.add_run(f'发现 {direct_sus_count} 笔疑似直接利益输送，{hidden_sus_count} 笔疑似隐形资产线索。')
            finding.font.color.rgb = RGBColor(255, 0, 0)
    except Exception as e:
        logger.warning(f'添加主要发现段落失败: {e}')
    
    # ========== 3. 家庭资产概览表 ==========
    try:
        doc.add_heading('二、家庭资产与资金画像', level=1)
    except Exception as e:
        logger.error(f'添加家庭资产标题失败: {e}')
        return None
    
    # 汇总表格
    if core_persons:
        try:
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            
            # 表头
            hdr_cells = table.rows[0].cells
            headers = ['人员', '总流入', '总流出', '工资占比', '理财持有']
            for i, h in enumerate(headers):
                hdr_cells[i].text = h
                hdr_cells[i].paragraphs[0].runs[0].font.bold = True
            
            # 数据行
            for person in core_persons:
                profile = profiles.get(person)
                if not isinstance(profile, dict) or not profile.get('has_data', False):
                    continue
                
                try:
                    summary = profile.get('summary', {})
                    if not isinstance(summary, dict):
                        continue
                    
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(person)
                    
                    # 安全格式化货币
                    try:
                        row_cells[1].text = utils.format_currency(summary.get('total_income', 0))
                    except Exception:
                        row_cells[1].text = str(summary.get('total_income', 0))
                    
                    try:
                        row_cells[2].text = utils.format_currency(summary.get('total_expense', 0))
                    except Exception:
                        row_cells[2].text = str(summary.get('total_expense', 0))
                    
                    # 安全格式化百分比
                    try:
                        salary_ratio = summary.get('salary_ratio', 0)
                        row_cells[3].text = f"{salary_ratio:.1%}"
                    except Exception:
                        row_cells[3].text = '-'
                    
                    wealth = profile.get('wealth_management', {})
                    if isinstance(wealth, dict):
                        holding = wealth.get('estimated_holding', 0)
                        try:
                            row_cells[4].text = utils.format_currency(holding) if holding > 0 else '-'
                        except Exception:
                            row_cells[4].text = str(holding) if holding > 0 else '-'
                    else:
                        row_cells[4].text = '-'
                except Exception as e:
                    logger.warning(f'添加人员 {person} 的数据行失败: {e}')
                    continue
        except Exception as e:
            logger.error(f'创建家庭资产表格失败: {e}')
    
    # ========== 4. 公司资金核查 ==========
    try:
        doc.add_heading('三、公司资金核查', level=1)
    except Exception as e:
        logger.error(f'添加公司资金核查标题失败: {e}')
        return None
    
    if not involved_companies:
        try:
            doc.add_paragraph('本次未涉及公司核查。')
        except Exception as e:
            logger.warning(f'添加公司核查说明失败: {e}')
    else:
        for company in involved_companies:
            try:
                doc.add_heading(f'➤ {company}', level=2)
            except Exception as e:
                logger.warning(f'添加公司 {company} 标题失败: {e}')
                continue
            
            comp_profile = profiles.get(company)
            
            if not isinstance(comp_profile, dict) or not comp_profile.get('has_data', False):
                try:
                    doc.add_paragraph('(暂无详细流水数据)')
                except Exception as e:
                    logger.warning(f'添加公司 {company} 无数据说明失败: {e}')
                continue
            
            try:
                summary = comp_profile.get('summary', {})
                if isinstance(summary, dict):
                    p = doc.add_paragraph()
                    p.add_run('资金概况: ').bold = True
                    try:
                        p.add_run(f'总流入 {utils.format_currency(summary.get("total_income", 0))} | 总流出 {utils.format_currency(summary.get("total_expense", 0))}')
                    except Exception:
                        p.add_run(f'总流入 {summary.get("total_income", 0)} | 总流出 {summary.get("total_expense", 0)}')
            except Exception as e:
                logger.warning(f'添加公司 {company} 资金概况失败: {e}')
    
    # ========== 5. 疑点与建议 ==========
    try:
        doc.add_heading('四、主要疑点与核查建议', level=1)
    except Exception as e:
        logger.error(f'添加疑点与建议标题失败: {e}')
        return None
    
    suggestion_idx = 1
    has_suggestions = False
    
    # 利益输送
    direct_transfers = suspicions.get('direct_transfers', [])
    if direct_transfers:
        try:
            doc.add_heading('【疑似利益输送】', level=2)
            for t in direct_transfers[:10]:  # 限制数量
                try:
                    amount = t.get('amount', 0)
                    amount_str = utils.format_currency(amount) if amount is not None else '0'
                    doc.add_paragraph(
                        f"• {_safe_format_date(t.get('date'))}: {t.get('person', '')} {t.get('direction', '')} "
                        f"{t.get('company', '')} {amount_str}"
                    )
                except Exception as e:
                    logger.warning(f'添加利益输送条目失败: {e}')
                    continue
            doc.add_paragraph(f'➡ 建议 {suggestion_idx}: 调取相关凭证，核实上述资金往来的业务背景。')
            suggestion_idx += 1
            has_suggestions = True
        except Exception as e:
            logger.warning(f'添加利益输送部分失败: {e}')
    
    # 隐形资产
    try:
        hidden_assets = suspicions.get('hidden_assets', {})
        hidden = [item for sublist in hidden_assets.values() for item in sublist]
        if hidden:
            doc.add_heading('【疑似隐形资产】', level=2)
            for h in hidden[:10]:
                try:
                    amount = h.get('amount', 0)
                    amount_str = utils.format_currency(amount) if amount is not None else '0'
                    doc.add_paragraph(
                        f"• {_safe_format_date(h.get('date'))}: 支付 {amount_str} "
                        f"给 {h.get('counterparty', '')}"
                    )
                except Exception as e:
                    logger.warning(f'添加隐形资产条目失败: {e}')
                    continue
            doc.add_paragraph(f'➡ 建议 {suggestion_idx}: 核实上述大额支出是否用于购房/购车。')
            suggestion_idx += 1
            has_suggestions = True
    except Exception as e:
        logger.warning(f'添加隐形资产部分失败: {e}')
    
    if not has_suggestions:
        try:
            doc.add_paragraph('本次自动化分析未发现显著的硬性疑点。')
            doc.add_paragraph('➡ 建议: 重点关注大额消费支出是否与收入水平匹配。')
        except Exception as e:
            logger.warning(f'添加无疑点说明失败: {e}')
    
    # ========== 6. 报告尾部 ==========
    try:
        doc.add_paragraph()
        doc.add_paragraph('=' * 50)
        footer = doc.add_paragraph('注: 本报告基于提供的电子数据分析生成，线索仅供参考。')
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception as e:
        logger.warning(f'添加报告尾部失败: {e}')
    
    # 保存文档
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        doc.save(output_path)
        logger.info(f'Word 审计报告生成完成: {output_path}')
        return output_path
    except PermissionError as e:
        logger.error(f'保存 Word 文档失败（权限错误）: {e}')
        return None
    except OSError as e:
        logger.error(f'保存 Word 文档失败（系统错误）: {e}')
        return None
    except Exception as e:
        logger.error(f'保存 Word 文档失败（未知错误）: {e}')
        return None
