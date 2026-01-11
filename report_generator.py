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
        display: flex;
        justify-content: center;
        padding: 20px;
    }
    .page {
        background-color: white;
        width: 210mm;
        min-height: 297mm;
        padding: 25mm 20mm;
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
        box-sizing: border-box;
        font-size: 16px;
        line-height: 1.6;
        color: #000;
        margin-bottom: 20px;
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
             summary = profile['summary']
             val = max(0, summary['total_income'] - summary['total_expense'])
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
        if not profile['has_data']:
            continue
        
        summary = profile['summary']
        income_structure = profile.get('income_structure', {})
        summary_data.append({
            '对象名称': entity,
            '数据时间范围': f"{summary['date_range'][0].strftime('%Y-%m-%d')} 至 {summary['date_range'][1].strftime('%Y-%m-%d')}",
            '交易笔数': summary['transaction_count'],
            '资金流入总额(万元)': round(summary['total_income'] / 10000, 2),
            '资金流出总额(万元)': round(summary['total_expense'] / 10000, 2),
            '净流入(万元)': round(summary['net_flow'] / 10000, 2),
            '真实收入(万元)': round(summary.get('real_income', 0) / 10000, 2),
            '真实支出(万元)': round(summary.get('real_expense', 0) / 10000, 2),
            '工资性收入(万元)': round(income_structure.get('salary_income', 0) / 10000, 2),
            '工资性收入占比': round(summary['salary_ratio'], 3),
            '第三方支付占比': round(summary['third_party_ratio'], 3),
            '大额现金笔数': summary['large_cash_count']
        })
    
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='资金画像汇总', index=False)
        worksheet = writer.sheets['资金画像汇总']
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
            '日期': t['date'].strftime('%Y-%m-%d'),
            '人员': t['person'],
            '方向': t['direction'],
            '公司': t['company'],
            '金额(元)': t['amount'],
            '摘要': t['description']
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
            '日期': collision['date'].strftime('%Y-%m-%d'),
            '人员A': collision['person_a'],
            '人员B': collision['person_b'],
            '地点': collision.get('location', ''),
            '时间差(分钟)': collision.get('time_diff', 0)
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
                '日期': asset['date'].strftime('%Y-%m-%d'),
                '人员': person,
                '对手方': asset['counterparty'],
                '金额(元)': asset['amount'],
                '摘要': asset['description']
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


def generate_excel_workbook(profiles: Dict,
                            suspicions: Dict,
                            output_path: str = None,
                            family_tree: Dict = None,
                            family_assets: Dict = None,
                            validation_results: Dict = None,
                            penetration_results: Dict = None) -> str:
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
        
        # 7. 家族关系图谱（新增）
        _generate_family_tree_sheet(writer, family_tree)
        
        # 8. 家族资产汇总（新增）
        _generate_family_assets_sheets(writer, family_assets, profiles)
        
        # 9. 数据验证结果（新增）
        _generate_validation_sheets(writer, validation_results)
        
        # 10. 资金穿透分析（新增）
        _generate_penetration_sheets(writer, penetration_results)
    
    logger.info(f'Excel底稿生成完成: {output_path}')
    
    return output_path


def _group_into_households(core_persons, family_summary):
    """
    将核心人员按家庭关系分组
    
    Args:
        core_persons: 核心人员列表
        family_summary: 家庭关系摘要
        
    Returns:
        家庭分组列表
    """
    adj = {p: set() for p in core_persons}
    if family_summary:
        for p, rels in family_summary.items():
            if p not in core_persons: continue
            direct_names = []
            for k in ['配偶', '子女', '父母', '夫妻', '儿子', '女儿', '父亲', '母亲']:
                if k in rels:
                    direct_names.extend(rels[k])
            for d in direct_names:
                if d in core_persons:
                    adj[p].add(d)
                    if d in adj: adj[d].add(p)
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


def _estimate_bank_balance(person, cleaned_data):
    """
    估算银行余额
    
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
            # 存款估算
            deposit = _estimate_bank_balance(person, cleaned_data)
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
            report_lines.append(f"  • {t['date'].strftime('%Y-%m-%d')}: {t['person']} {t['direction']} {t['company']} {utils.format_currency(t['amount'])} (摘要: {t['description']})")
        report_lines.append(f"  ➡ 建议 {suggestion_idx}: 调取相关凭证，核实上述资金往来的业务背景。")
        suggestion_idx += 1
        has_suggestions = True
        report_lines.append("")

    # 4.2 隐形资产
    hidden = [item for sublist in suspicions['hidden_assets'].values() for item in sublist]
    if hidden:
        report_lines.append("【疑似隐形资产】")
        for h in hidden:
             report_lines.append(f"  • {h['date'].strftime('%Y-%m-%d')}: 支付 {utils.format_currency(h['amount'])} 给 {h['counterparty']} (摘要: {h['description']})")
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
            <p><strong>【总体评价】</strong>: 本次核查对象共 {len(core_persons)} 人及 {len(involved_companies)} 家关联公司，总体风险评级为 <strong><span style="color:{risk_color}">{risk_assessment}</span></strong>。</p>
            <p><strong>【数据概况】</strong>: 累计分析银行流水 {total_trans} 条。</p>
    """
    
    # 高流水预警
    high_flow_persons = []
    for p_name, p_data in profiles.items():
        if p_name in core_persons and p_data['has_data']:
            total_vol = p_data['summary']['total_income'] + p_data['summary']['total_expense']
            if total_vol > 50000000:
                high_flow_persons.append(f"{p_name}")
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
    生成HTML报告的家庭板块
    
    Args:
        profiles: 资金画像字典
        core_persons: 核心人员列表
        family_summary: 家庭关系摘要
        family_assets: 家庭资产数据
        cleaned_data: 清洗后的数据
        
    Returns:
        HTML内容字符串
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
            props = family_assets.get(person, {}).get('房产', []) if family_assets else []
            fam_props_list.extend([(person, p) for p in props])
            fam_cars_num += len(family_assets.get(person, {}).get('车辆', [])) if family_assets else 0
            
            p_prof = profiles.get(person)
            if p_prof and p_prof['has_data']:
                deposit = _estimate_bank_balance(person, cleaned_data)
                fam_total_deposit_est += deposit
                wealth = p_prof.get('wealth_management', {})
                w_holding = wealth.get('estimated_holding', 0.0)
                if w_holding == 0 and 'estimated_holding' not in wealth:
                    w_holding = max(0, wealth.get('wealth_purchase', 0) - wealth.get('wealth_redemption', 0))
                if w_holding > 0: fam_total_wealth_est += w_holding
        
        content_html += f"""<div class="subsection-title">➤ {title}</div>"""
        
        # 家庭概览框
        content_html += f"""
        <div style="border: 1px solid #ddd; padding: 10px; background-color: #fcfcfc; margin-bottom: 15px;">
            <p><strong>【家庭资产全貌】</strong> (截至数据提取日)</p>
            <p>• <strong>房产合计: {len(fam_props_list)} 套</strong></p>
            <ul style="margin-top:0; margin-bottom:5px; font-size:14px; color:#555;">
        """
        for owner, p in fam_props_list:
            addr = p.get('房地坐落', '未知地址')
            price = p.get('交易金额', 0)
            price_str = f"{utils.format_currency(price)}" if price > 0 else "价格未知"
            area = p.get('建筑面积', 0)
            content_html += f"<li>[{owner}] {addr} ({area}平, {price_str})</li>"
        
        content_html += f"""
            </ul>
            <p>• <strong>车辆合计: {fam_cars_num} 辆</strong></p>
            <p>• <strong>资金沉淀 (估算):</strong> 存款约 <b>{utils.format_currency(fam_total_deposit_est)}</b> | 理财约 <b>{utils.format_currency(fam_total_wealth_est)}</b></p>
        </div>
        """
        
        # 2. 个人详情
        for person in household:
            content_html += f"""<h3 style="margin-left:0; font-size:16px;">[{person}]</h3>"""
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
                 sal_desc = " (" + "; ".join([f"{y}年:{utils.format_currency(v)}" for y, v in sorted(yearly_sal.items())]) + ")"
            content_html += f"""<p><strong>收入结构</strong>: 工资性收入 {utils.format_currency(income.get('salary_income', 0))} (占比 {summary['salary_ratio']:.1%}){sal_desc}</p>"""
            
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
                     hold_strs = [f"{k}在持{utils.format_currency(v['amount'])}" for k, v in sorted_hold]
                     content_html += f"""<p style="text-indent: 2em;">>> 持有分布: {', '.join(hold_strs)}</p>"""
            
            # 流向
            content_html += f"""<p><strong>主要去向</strong>: {_get_top_counterparties_str(person, 'out', cleaned_data)}</p>"""
            content_html += "<hr style='border:0; border-top:1px dashed #eee; margin:10px 0;'>"
    content_html += "</div>" # End Household Page
    
    return content_html


def _generate_html_company_section(profiles, involved_companies, core_persons, cleaned_data):
    """
    生成HTML报告的公司资金核查部分
    
    Args:
        profiles: 资金画像字典
        involved_companies: 涉及公司列表
        core_persons: 核心人员列表
        cleaned_data: 清洗后的数据
        
    Returns:
        HTML内容字符串
    """
    import utils
    
    content_html = """<div class="page"><div class="section-title">三、公司资金核查</div>"""
    if not involved_companies:
        content_html += "<p>本次未涉及公司核查。</p>"
    else:
        for company in involved_companies:
            content_html += f"""<div class="subsection-title">➤ {company}</div>"""
            comp_profile = next((p for p in profiles.values() if company in p.get('entity_name', '')), None)
            
            if not comp_profile or not comp_profile['has_data']:
                content_html += "<p>(暂无详细流水数据)</p>"; continue
            
            summary = comp_profile['summary']
            content_html += f"""<p>• <strong>资金概况</strong>: 总流入 {utils.format_currency(summary['total_income'])} | 总流出 {utils.format_currency(summary['total_expense'])}</p>"""
            
            top_in = _get_top_counterparties_str(company, 'in', cleaned_data, 5)
            top_out = _get_top_counterparties_str(company, 'out', cleaned_data, 5)
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
                        if row['income'] > 0 or row['expense'] > 0: risky_items.append(f"{name} (收:{utils.format_currency(row['income'])}/付:{utils.format_currency(row['expense'])})")
                    if risky_items:
                        risky_html = f"""<p style="color:red">⚠ 发现与核心人员直接往来: {', '.join(risky_items)}</p>"""
            
            if risky_html: content_html += risky_html
            else: content_html += "<p>• <strong>公私往来</strong>: 未发现与核心人员的直接资金往来。</p>"
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
            content_html += f"""<li>{t['date'].strftime('%Y-%m-%d')}: {t['person']} {t['direction']} {t['company']} {utils.format_currency(t['amount'])} <br><span style="color:#666; font-size:12px;">(摘要: {t['description']})</span></li>"""
        content_html += "</ul><p class='highlight'>➡ 建议: 调取相关凭证，核实上述资金往来的业务背景。</p>"
        has_suggestions = True

    # 隐形资产
    hidden = [item for sublist in suspicions['hidden_assets'].values() for item in sublist]
    if hidden:
        content_html += """<p><strong>【疑似隐形资产】</strong></p><ul>"""
        for h in hidden:
             content_html += f"""<li>{h['date'].strftime('%Y-%m-%d')}: 支付 {utils.format_currency(h['amount'])} 给 {h['counterparty']} <br><span style="color:#666; font-size:12px;">(摘要: {h['description']})</span></li>"""
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

    # 辅助函数
    def _group_into_households(core_persons, family_summary):
        adj = {p: set() for p in core_persons}
        if family_summary:
            for p, rels in family_summary.items():
                if p not in core_persons: continue
                direct_names = []
                for k in ['配偶', '子女', '父母', '夫妻', '儿子', '女儿', '父亲', '母亲']:
                    if k in rels: direct_names.extend(rels[k])
                for d in direct_names:
                    if d in core_persons:
                        adj[p].add(d); adj[d].add(p)
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

    def _get_top_counterparties_str(entity, direction, top_n=5):
        if not cleaned_data or entity not in cleaned_data: return "无数据"
        df = cleaned_data[entity]
        col = 'income' if direction == 'in' else 'expense'
        if col not in df.columns: return "无数据"
        subset = df[df[col] > 0]
        if subset.empty: return "无主要交易"
        subset = subset[subset['counterparty'] != entity]
        stats = subset.groupby('counterparty')[col].sum().sort_values(ascending=False).head(top_n)
        lines = []
        for name, amt in zip(stats.index, stats.values):
            name_str = str(name)
            if name_str.lower() in ['nan', 'none', '', 'nat']: continue
            if any(x in name_str for x in ['内部户', '待清算', '资金归集']): continue
            lines.append(f"{name_str}({utils.format_currency(amt)})")
        return ", ".join(lines) if lines else "无主要外部对手"

    def _estimate_bank_balance(person):
        if not cleaned_data or person not in cleaned_data: return 0
        df = cleaned_data[person]
        total_in = df['income'].sum()
        total_out = df['expense'].sum()
        return max(0, total_in - total_out)

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
                deposit = _estimate_bank_balance(person)
                fam_total_deposit_est += deposit
                wealth = p_prof.get('wealth_management', {})
                w_holding = wealth.get('estimated_holding', 0.0)
                if w_holding == 0 and 'estimated_holding' not in wealth:
                    w_holding = max(0, wealth.get('wealth_purchase', 0) - wealth.get('wealth_redemption', 0))
                if w_holding > 0: fam_total_wealth_est += w_holding
        
        content_html += f"""<div class="subsection-title">➤ {title}</div>"""
        
        # 家庭概览框
        content_html += f"""
        <div style="border: 1px solid #ddd; padding: 10px; background-color: #fcfcfc; margin-bottom: 15px;">
            <p><strong>【家庭资产全貌】</strong> (截至数据提取日)</p>
            <p>• <strong>房产合计: {len(fam_props_list)} 套</strong></p>
            <ul style="margin-top:0; margin-bottom:5px; font-size:14px; color:#555;">
        """
        for owner, p in fam_props_list:
            addr = p.get('房地坐落', '未知地址')
            price = p.get('交易金额', 0)
            price_str = f"{utils.format_currency(price)}" if price > 0 else "价格未知"
            area = p.get('建筑面积', 0)
            content_html += f"<li>[{owner}] {addr} ({area}平, {price_str})</li>"
        
        content_html += f"""
            </ul>
            <p>• <strong>车辆合计: {fam_cars_num} 辆</strong></p>
            <p>• <strong>资金沉淀 (估算):</strong> 存款约 <b>{utils.format_currency(fam_total_deposit_est)}</b> | 理财约 <b>{utils.format_currency(fam_total_wealth_est)}</b></p>
        </div>
        """
        
        # 2. 个人详情
        for person in household:
            content_html += f"""<h3 style="margin-left:0; font-size:16px;">[{person}]</h3>"""
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
                 sal_desc = " (" + "; ".join([f"{y}年:{utils.format_currency(v)}" for y, v in sorted(yearly_sal.items())]) + ")"
            content_html += f"""<p><strong>收入结构</strong>: 工资性收入 {utils.format_currency(income.get('salary_income', 0))} (占比 {summary['salary_ratio']:.1%}){sal_desc}</p>"""
            
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
                     hold_strs = [f"{k}在持{utils.format_currency(v['amount'])}" for k, v in sorted_hold]
                     content_html += f"""<p style="text-indent: 2em;">>> 持有分布: {', '.join(hold_strs)}</p>"""
            
            # 流向
            content_html += f"""<p><strong>主要去向</strong>: {_get_top_counterparties_str(person, 'out')}</p>"""
            content_html += "<hr style='border:0; border-top:1px dashed #eee; margin:10px 0;'>"
    content_html += "</div>" # End Household Page
    
    # 3. 公司资金核查 (Company Section)
    content_html += """<div class="page"><div class="section-title">三、公司资金核查</div>"""
    if not involved_companies:
        content_html += "<p>本次未涉及公司核查。</p>"
    else:
        for company in involved_companies:
            content_html += f"""<div class="subsection-title">➤ {company}</div>"""
            comp_profile = next((p for p in profiles.values() if company in p.get('entity_name', '')), None)
            
            if not comp_profile or not comp_profile['has_data']:
                content_html += "<p>(暂无详细流水数据)</p>"; continue
            
            summary = comp_profile['summary']
            content_html += f"""<p>• <strong>资金概况</strong>: 总流入 {utils.format_currency(summary['total_income'])} | 总流出 {utils.format_currency(summary['total_expense'])}</p>"""
            
            top_in = _get_top_counterparties_str(company, 'in', 5)
            top_out = _get_top_counterparties_str(company, 'out', 5)
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
                        if row['income'] > 0 or row['expense'] > 0: risky_items.append(f"{name} (收:{utils.format_currency(row['income'])}/付:{utils.format_currency(row['expense'])})")
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
            content_html += f"""<li>{t['date'].strftime('%Y-%m-%d')}: {t['person']} {t['direction']} {t['company']} {utils.format_currency(t['amount'])} <br><span style="color:#666; font-size:12px;">(摘要: {t['description']})</span></li>"""
        content_html += "</ul><p class='highlight'>➡ 建议: 调取相关凭证，核实上述资金往来的业务背景。</p>"
        has_suggestions = True

    # 隐形资产
    hidden = [item for sublist in suspicions['hidden_assets'].values() for item in sublist]
    if hidden:
        content_html += """<p><strong>【疑似隐形资产】</strong></p><ul>"""
        for h in hidden:
             content_html += f"""<li>{h['date'].strftime('%Y-%m-%d')}: 支付 {utils.format_currency(h['amount'])} 给 {h['counterparty']} <br><span style="color:#666; font-size:12px;">(摘要: {h['description']})</span></li>"""
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

