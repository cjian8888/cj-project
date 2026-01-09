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
                '工资性收入(万元)': round(income_structure.get('salary_income', 0) / 10000, 2),  # 新增
                '工资性收入占比': round(summary['salary_ratio'], 3),  # 数值型，如 0.643
                '第三方支付占比': round(summary['third_party_ratio'], 3),  # 数值型，如 0.107
                '大额现金笔数': summary['large_cash_count']
            })
        
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            # 设置百分比列的格式
            df_summary.to_excel(writer, sheet_name='资金画像汇总', index=False)
            # 获取工作表对象以设置格式
            worksheet = writer.sheets['资金画像汇总']
            # 设置百分比格式（H列和I列，从第2行开始）
            for row in range(2, len(df_summary) + 2):
                worksheet[f'H{row}'].number_format = '0.0%'
                worksheet[f'I{row}'].number_format = '0.0%'


        
        # 2. 直接转账关系表
        if suspicions['direct_transfers']:
            transfer_data = []
            for transfer in suspicions['direct_transfers']:
                transfer_data.append({
                    '人员': transfer['person'],
                    '公司': transfer['company'],
                    '日期': transfer['date'].strftime('%Y-%m-%d'),
                    '金额(元)': transfer['amount'],
                    '方向': '收款' if transfer['direction'] == 'receive' else '付款',
                    '摘要': transfer['description'],
                    '风险等级': config.RISK_LEVELS.get(transfer['risk_level'], transfer['risk_level'])
                })
            
            df_transfers = pd.DataFrame(transfer_data)
            df_transfers.to_excel(writer, sheet_name='直接资金往来', index=False)
        
        # 3. 现金时空伴随表
        if suspicions['cash_collisions']:
            collision_data = []
            for collision in suspicions['cash_collisions']:
                collision_data.append({
                    '取现方': collision['withdrawal_entity'],
                    '存现方': collision['deposit_entity'],
                    '取现日期': collision['withdrawal_date'].strftime('%Y-%m-%d %H:%M'),
                    '存现日期': collision['deposit_date'].strftime('%Y-%m-%d %H:%M'),
                    '时间差(小时)': f"{collision['time_diff_hours']:.1f}",
                    '取现金额(元)': collision['withdrawal_amount'],
                    '存现金额(元)': collision['deposit_amount'],
                    '金额差(元)': collision['amount_diff'],
                    '金额差异率': f"{collision['amount_diff_ratio']:.2%}",
                    '风险等级': config.RISK_LEVELS.get(collision['risk_level'], collision['risk_level'])
                })
            
            df_collisions = pd.DataFrame(collision_data)
            df_collisions.to_excel(writer, sheet_name='现金时空伴随', index=False)
        
        # 4. 隐形资产明细表
        hidden_asset_data = []
        for entity, assets in suspicions['hidden_assets'].items():
            for asset in assets:
                hidden_asset_data.append({
                    '对象': entity,
                    '类型': '疑似购房' if asset['type'] == 'property' else '疑似购车',
                    '日期': asset['date'].strftime('%Y-%m-%d'),
                    '金额(元)': asset['amount'],
                    '对手方': asset['counterparty'],
                    '摘要': asset['description'],
                    '风险等级': config.RISK_LEVELS.get(asset['risk_level'], asset['risk_level'])
                })
        
        if hidden_asset_data:
            df_assets = pd.DataFrame(hidden_asset_data)
            df_assets.to_excel(writer, sheet_name='隐形资产', index=False)
        
        # 5. 固定频率异常进账表
        frequency_data = []
        for entity, patterns in suspicions['fixed_frequency'].items():
            for pattern in patterns:
                frequency_data.append({
                    '对象': entity,
                    '平均金额(元)': pattern['amount_avg'],
                    '平均日期': f"每月{pattern['day_avg']}日",
                    '出现次数': pattern['occurrences'],
                    '时间跨度': f"{pattern['date_range'][0].strftime('%Y-%m')} 至 {pattern['date_range'][1].strftime('%Y-%m')}",
                    '风险等级': config.RISK_LEVELS.get(pattern['risk_level'], pattern['risk_level'])
                })
        
        if frequency_data:
            df_frequency = pd.DataFrame(frequency_data)
            df_frequency.to_excel(writer, sheet_name='固定频率异常', index=False)
        
        # 6. 大额现金明细表
        cash_data = []
        for entity, profile in profiles.items():
            if not profile['has_data']:
                continue
            
            for cash in profile['large_cash']:
                cash_data.append({
                    '对象': entity,
                    '日期': cash['date'].strftime('%Y-%m-%d'),
                    '类型': '存现' if cash['cash_type'] == 'deposit' else '取现',
                    '金额(元)': cash['amount'],
                    '摘要': cash['description'],
                    '风险等级': config.RISK_LEVELS.get(cash['risk_level'], cash['risk_level'])
                })
        
        if cash_data:
            df_cash = pd.DataFrame(cash_data)
            df_cash.to_excel(writer, sheet_name='大额现金明细', index=False)
        
        # 6.5 第三方支付交易明细表（微信/支付宝等）
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
        
        # 6.6 理财产品交易明细表
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
                    '净流向理财(元)': wealth_mgmt.get('net_wealth_flow', 0)
                })
        
        if wealth_summary:
            df_wealth_summary = pd.DataFrame(wealth_summary)
            df_wealth_summary.to_excel(writer, sheet_name='理财产品-汇总', index=False)
        
        # 7. 家族关系图谱（新增）
        if family_tree:
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
        
        # 8. 家族资产汇总（新增）
        if family_assets:
            # 8.1 资产汇总表
            asset_summary_data = []
            for person, assets in family_assets.items():
                asset_summary_data.append({
                    '核心人员': person,
                    '家族成员数': len(assets['家族成员']),
                    '家族成员': ', '.join(assets['家族成员']),
                    '房产套数': assets['房产套数'],
                    '房产总价值(万元)': assets['房产总价值'],
                    '车辆数量': assets['车辆数量']
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
                # 将 NaN 值替换为 "-"
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
        
        # 9. 数据验证结果（新增）
        if validation_results:
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
        
        # 10. 资金穿透分析（新增）
        if penetration_results:
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
    
    logger.info(f'Excel底稿生成完成: {output_path}')
    
    return output_path

def generate_official_report(profiles: Dict,
                            suspicions: Dict,
                            core_persons: List[str],
                            involved_companies: List[str],
                            output_path: str = None,
                            family_summary: Dict = None,
                            family_assets: Dict = None,
                            cleaned_data: Dict = None) -> str:
    """
    生成公文格式的核查结果分析报告（重构版：按分析维度组织）
    结构：前言 -> 家庭资产收入及分析 -> 公司资金分析 -> 结论
    """
    # 同时也生成HTML报告
    html_path = output_path.replace('.txt', '.html') if output_path else config.OUTPUT_REPORT_FILE.replace('.docx', '.html')
    generate_html_report(profiles, suspicions, core_persons, involved_companies, html_path, family_summary, family_assets, cleaned_data)
    
    if output_path is None:
        output_path = config.OUTPUT_REPORT_FILE.replace('.docx', '.txt')
    
    logger.info(f'正在生成重构版公文报告: {output_path}')
    
    import family_finance
    import os
    
    report_lines = []
    
    # 辅助函数：分组家庭 (户)
    def _group_into_households(core_persons, family_summary):
        adj = {p: set() for p in core_persons}
        if family_summary:
            for p, rels in family_summary.items():
                if p not in core_persons: continue
                # 直系亲属判定为同一户 (配偶、子女、父母)
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

    # 辅助函数：获取主要交易对手
    def _get_top_counterparties_str(person, direction, top_n=5):
        if not cleaned_data or person not in cleaned_data: return "无数据"
        df = cleaned_data[person]
        col = 'income' if direction == 'in' else 'expense'
        if col not in df.columns: return "无数据"
        
        subset = df[df[col] > 0]
        if subset.empty: return "无主要交易"
        
        # 排除同名转账
        subset = subset[subset['counterparty'] != person]
        
        stats = subset.groupby('counterparty')[col].sum().sort_values(ascending=False).head(top_n)
        lines = []
        for name, amt in zip(stats.index, stats.values):
            name_str = str(name)
            if name_str.lower() in ['nan', 'none', '', 'nat']:
                name_str = '未知/内部户'
            lines.append(f"{name_str}({utils.format_currency(amt)})")
        return ", ".join(lines)

    # === 一、前言 ===
    report_lines.append(f"{config.REPORT_TITLE}")
    report_lines.append("=" * 60)
    report_lines.append("一、前言")
    report_lines.append("-" * 60)
    
    total_trans = sum(p['summary']['transaction_count'] for p in profiles.values() if p['has_data'])
    total_sus = (len(suspicions['direct_transfers']) + len(suspicions['cash_collisions']) + 
                 sum(len(v) for v in suspicions['hidden_assets'].values()) + 
                 sum(len(v) for v in suspicions['fixed_frequency'].values()))

    report_lines.append(f"本次核查工作针对 {', '.join(core_persons)} 等 {len(core_persons)} 名核心人员及 {', '.join(involved_companies)} 等 {len(involved_companies)} 家涉案公司的资金流向进行了全面分析。")
    report_lines.append(f"核查内容涵盖银行账户流水、关联资产信息及外部查询结果。共清洗分析交易记录 {total_trans} 条，发现重要疑点 {total_sus} 个。")
    report_lines.append("")

    # === 二、家庭资产收入情况及数据分析 ===
    report_lines.append("二、家庭资产收入情况及数据分析")
    report_lines.append("-" * 60)
    
    # 2.1 每个家庭成员的个人情况
    households = _group_into_households(core_persons, family_summary)
    
    for household in households:
        title = "、".join(household) + " 家庭"
        if len(household) == 1:
             title = f"{household[0]} 个人"
        report_lines.append(f"【{title}情况】")

        for person in household:
            if len(household) > 1:
                report_lines.append(f"  [成员: {person}]")
            
            profile = None
            for p in profiles.values():
                 if person in p.get('entity_name', ''): profile = p; break
            
            if not profile or not profile['has_data']:
                report_lines.append("  (暂无详细资金数据)")
                report_lines.append("")
                continue

            summary = profile['summary']
            income = profile.get('income_structure', {})
            wealth = profile.get('wealth_management', {})
            
            # 基础收支
            report_lines.append(f"  1. 基础收支: 总流入 {utils.format_currency(summary['total_income'])} (工资性收入: {utils.format_currency(income.get('salary_income', 0))})")
            report_lines.append(f"                 总流出 {utils.format_currency(summary['total_expense'])}")
            
            # 分年度工资
            salary_details = income.get('salary_details', [])
            yearly_sal = {}
            for item in salary_details:
                d_str = str(item.get('日期', ''))[:4]
                if d_str.isdigit():
                    yearly_sal[d_str] = yearly_sal.get(d_str, 0) + item.get('金额', 0)
            
            if yearly_sal:
                 report_lines.append(f"     分年度工资收入:")
                 for y in sorted(yearly_sal.keys()):
                      report_lines.append(f"       - {y}年: {utils.format_currency(yearly_sal[y])}")

            # 资产情况 (从Family Assets获取)
            props = family_assets.get(person, {}).get('房产', []) if family_assets else []
            vehs = family_assets.get(person, {}).get('车辆', []) if family_assets else []
            
            report_lines.append(f"  2. 名下资产: 房产 {len(props)} 套, 车辆 {len(vehs)} 辆")
            for p in props: report_lines.append(f"     - 房产: {p.get('房地坐落', '未知地址')} (购买价: {p.get('交易金额', 0):.1f}万元)")
            for v in vehs: report_lines.append(f"     - 车辆: {v.get('中文品牌', '未知品牌')} {v.get('号牌号码', '未知车牌')}")
                
            # 银行存款与理财
            report_lines.append(f"  3. 金融资产: 理财购买总额 {utils.format_currency(wealth.get('wealth_purchase', 0))}")
            report_lines.append(f"                 理财峰值存量(估算): {utils.format_currency(wealth.get('max_balance', 0))}")
            report_lines.append("")
    
    # 2.2 家庭数据分析
    report_lines.append("【家庭数据分析】")
    
    # 购房数据分析
    report_lines.append("1. 购房数据分析")
    has_prop_analysis = False
    if sum(len(v) for v in suspicions['hidden_assets'].values()) > 0:
        for ent, assets in suspicions['hidden_assets'].items():
            for asset in assets:
                # Assuming 'type' is added to hidden_assets suspicion for property/vehicle
                # If not, this part might need adjustment based on actual suspicion structure
                # For now, let's assume 'type' is not explicitly there and check for keywords in description
                if '房' in asset.get('description', '') or '地产' in asset.get('description', ''):
                    report_lines.append(f"   - {ent} 于 {asset['date'].strftime('%Y-%m-%d')} 支出 {utils.format_currency(asset['amount'])} 用于房产购置 (对手方: {asset['counterparty']})")
                    has_prop_analysis = True
    if not has_prop_analysis:
        report_lines.append("   - 流水中未发现明显的大额购房资金流出。")

    # 家庭存款与收入分析
    report_lines.append("2. 家庭存款与收入分析")
    total_family_income = sum(p['summary'].get('real_income', 0) for p in profiles.values() if p['has_data'] and p.get('entity_name', '') in core_persons)
    report_lines.append(f"   - 家庭总真实收入(估算): {utils.format_currency(total_family_income)}")
    report_lines.append(f"   - (注: 存款余额需结合调取时点余额确认，此处仅反映流水期间流量)")
    
    # 银行流水交易对象分析
    report_lines.append("3. 银行流水交易对象分析")
    for person in core_persons:
        in_top = _get_top_counterparties_str(person, 'in')
        out_top = _get_top_counterparties_str(person, 'out')
        report_lines.append(f"   - {person} 主要资金来源: {in_top}")
        report_lines.append(f"   - {person} 主要资金去向: {out_top}")

    # 大额存取与转账
    report_lines.append("4. 大额存取与转账情况")
    for person in core_persons:
        if cleaned_data and person in cleaned_data:
            df = cleaned_data[person]
            # Assuming 'amount' column exists and represents the absolute transaction amount
            # Need to ensure 'amount' is correctly calculated in cleaning process
            # Calculate amount from income/expense
            amount_series = df[['income', 'expense']].max(axis=1)
            large_trans = df[amount_series > 50000]
            if not large_trans.empty:
                total_val = amount_series[amount_series > 50000].sum()
                report_lines.append(f"   - {person}: 5万元以上大额交易共 {len(large_trans)} 笔, 合计 {utils.format_currency(total_val)}")

    # 反洗钱数据分析
    report_lines.append("5. 反洗钱风险特征分析")
    aml_risks = []
    # Assuming 'structuring' and 'money_laundering' are keys in suspicions dict
    if suspicions.get('structuring'): aml_risks.append("存在化整为零(拆分交易)嫌疑") 
    if suspicions.get('money_laundering'): aml_risks.append("存在疑似洗钱模式(快进快出)")
    if suspicions.get('cash_collisions'): aml_risks.append(f"发现 {len(suspicions['cash_collisions'])} 组现金时空伴随")
    
    if aml_risks:
        for r in aml_risks: report_lines.append(f"   - {r}")
    else:
        report_lines.append("   - 未发现典型的清洗钱特征。")

    report_lines.append("")

    # === 三、公司资金分析 ===
    report_lines.append("三、公司资金分析")
    report_lines.append("-" * 60)
    
    for company in involved_companies:
        report_lines.append(f"【{company}】")
        
        comp_profile = None
        for p in profiles.values():
             if company in p.get('entity_name', ''): comp_profile = p; break
        
        if not comp_profile:
             report_lines.append("  (暂无数据)")
             continue
             
        summary = comp_profile['summary']
        
        # 累计进出
        report_lines.append(f"  1. 资金概况: 累计进账 {utils.format_currency(summary['total_income'])}, 累计支出 {utils.format_currency(summary['total_expense'])}")
        
        # 关联交易 (与核查人员)
        report_lines.append("  2. 与核查人员往来:")
        if cleaned_data and company in cleaned_data:
            df = cleaned_data[company]
            related_tx = df[df['counterparty'].isin(core_persons)]
            if not related_tx.empty:
                total_rel = related_tx['amount'].sum()
                report_lines.append(f"     发现与核心人员往来 {len(related_tx)} 笔, 合计 {utils.format_currency(total_rel)}")
            else:
                report_lines.append("     未发现直接资金往来。")
        
        # 现金收支
        report_lines.append(f"  3. 现金收支: 现今提取/存入共计 {utils.format_currency(comp_profile.get('cash_analysis', {}).get('total_cash', 0))}")
        
        # 主要交易对象
        top_partners = _get_top_counterparties_str(company, 'out', top_n=3)
        report_lines.append(f"  4. 主要资金去向: {top_partners}")
        report_lines.append("")

    # === 四、结论与疑点 ===
    report_lines.append("四、结论与主要疑点")
    report_lines.append("-" * 60)
    
    # 复用原有的疑点输出逻辑
    sub_idx = 1
    
    if sum(len(v) for v in suspicions['hidden_assets'].values()) > 0:
        report_lines.append(f"1. 隐形资产嫌疑 (疑似购房/购车)")
        for ent, assets in suspicions['hidden_assets'].items():
            for asset in assets:
                 report_lines.append(f"   - {ent}: {asset['date'].strftime('%Y-%m-%d')} 支出 {utils.format_currency(asset['amount'])} (对手方: {asset['counterparty']})")
    
    if suspicions['direct_transfers']:
        report_lines.append(f"2. 利益输送嫌疑 (直接资金往来)")
        for t in suspicions['direct_transfers']:
            d = '收到' if t['direction'] == 'receive' else '支付'
            report_lines.append(f"   - {t['person']} {d} {t['company']} {utils.format_currency(t['amount'])}")

    report_lines.append("")
    report_lines.append("=" * 60)
    report_lines.append(f"(本报告由资金穿透与关联排查系统自动生成)")
    
    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    logger.info(f'重构版公文报告生成完成: {output_path}')
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
    <div class="page">
        <!-- CONTENT_PLACEHOLDER -->
    </div>
    <div class="footer">
        <p>(本报告由资金穿透与关联排查系统自动生成)</p>
    </div>
</body>
</html>
"""

def generate_html_report(profiles, suspicions, core_persons, involved_companies, output_path, family_summary=None, family_assets=None, cleaned_data=None):
    """
    生成HTML格式的分析报告 (Unified: Visual Graph + Detailed Text)
    """
    import os
    import json
    import datetime
    import config
    import utils
    import account_analyzer
    import flow_visualizer

    logger = utils.setup_logger(__name__)
    dir_name = os.path.dirname(output_path)
    # Output to the Visual Report path to unify them
    unified_output_path = os.path.join(dir_name, '资金流向可视化.html')
    logger.info(f'正在生成统一HTML报告: {unified_output_path}')
    
    # Ensure lists
    if involved_companies is None: involved_companies = []
    
    # 辅助函数：家庭分组
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

    # 辅助函数：主要交易对手
    def _get_top_counterparties_str(person, direction, top_n=5):
        if not cleaned_data or person not in cleaned_data: return "无数据"
        df = cleaned_data[person]
        col = 'income' if direction == 'in' else 'expense'
        if col not in df.columns: return "无数据"
        subset = df[df[col] > 0]
        if subset.empty: return "无主要交易"
        subset = subset[subset['counterparty'] != person]
        stats = subset.groupby('counterparty')[col].sum().sort_values(ascending=False).head(top_n)
        lines = []
        for name, amt in zip(stats.index, stats.values):
            name_str = str(name)
            if name_str.lower() in ['nan', 'none', '', 'nat']: name_str = '未知/内部户'
            lines.append(f"{name_str}({utils.format_currency(amt)})")
        return ", ".join(lines)

    # 1. Generate Content HTML (Preamble, Family, Company, Conclusion)
    content_html = ""
    # Preamble
    person_list_str = "、".join(core_persons[:3]) + (f"等{len(core_persons)}人" if len(core_persons) > 3 else "")
    total_trans = sum(p['summary']['transaction_count'] for p in profiles.values() if p['has_data'])
    total_sus = (len(suspicions['direct_transfers']) + len(suspicions['cash_collisions']) + sum(len(v) for v in suspicions['hidden_assets'].values()))
    
    content_html += f"""
    <div class="page">
        <h1>关于{person_list_str}等信息查询结果分析报告</h1>
        <div class="section-title">一、前言</div>
        <p>本次核查工作针对 {', '.join(core_persons)} 等 {len(core_persons)} 名核心人员及 {', '.join(involved_companies)} 等 {len(involved_companies)} 家涉案公司的资金流向进行了全面分析。</p>
        <p>核查内容涵盖银行账户流水、关联资产信息及外部查询结果。共清洗分析交易记录 {total_trans} 条，发现重要疑点 {total_sus} 个。</p>
    </div>"""

    # Family Section
    households = _group_into_households(core_persons, family_summary)
    content_html += """<div class="page"><div class="section-title">二、家庭资产收入情况及数据分析</div>"""
    for household in households:
        title = "、".join(household) + " 家庭"
        if len(household) == 1: title = f"{household[0]} 个人"
        content_html += f"""<div class="subsection-title">【{title}情况】</div>"""
        for person in household:
            if len(household) > 1: content_html += f"""<p style="font-weight:bold; margin-top:10px;">[成员: {person}]</p>"""
            profile = next((p for p in profiles.values() if person in p.get('entity_name', '')), None)
            if not profile or not profile['has_data']:
                content_html += "<p>(暂无详细资金数据)</p>"; continue
            
            summary = profile['summary']
            income = profile.get('income_structure', {})
            wealth = profile.get('wealth_management', {})
            
            # Bank Logic from Step 706
            active_cards_count = 0
            account_rows = ""
            if cleaned_data and person in cleaned_data:
                try:
                    df = cleaned_data[person]
                    acct_info = account_analyzer.classify_accounts(df)
                    real_card_ids = acct_info.get('physical_cards', [])
                    active_cards_count = len(real_card_ids)
                    real_cards_details = []
                    # Robust matching
                    temp_df = df.copy()
                    id_col = '本方账号'; bank_col = '所属银行'; bal_col = '余额(元)'
                    for c in ['account_id', '账号', '卡号', '本方账号']:
                        if c in temp_df.columns: id_col = c; break
                    for c in ['所属银行', '银行', 'bank']:
                         if c in temp_df.columns: bank_col = c; break
                    for c in ['余额(元)', '余额', 'balance']:
                         if c in temp_df.columns: bal_col = c; break
                    
                    if id_col in temp_df.columns:
                        temp_df['mapped_id'] = temp_df[id_col].astype(str).str.strip()
                        for card_id in real_card_ids:
                             match = temp_df[temp_df['mapped_id'] == str(card_id).strip()]
                             if not match.empty:
                                 row = match.iloc[-1]
                                 real_cards_details.append({'bank': row.get(bank_col, '未知银行'), 'card_no': card_id, 'balance': row.get(bal_col, 0)})
                             else:
                                 real_cards_details.append({'bank': '未匹配数据', 'card_no': card_id, 'balance': 0})
                    else:
                        for card_id in real_card_ids:
                             real_cards_details.append({'bank': '列名缺失', 'card_no': card_id, 'balance': 0})
                    
                    real_cards_details.sort(key=lambda x: float(str(x['balance']).replace(',','')) if str(x['balance']).replace('.','',1).replace(',','').isdigit() else 0, reverse=True)
                    for i, acc in enumerate(real_cards_details[:10]):
                        account_rows += f"<tr><td>{i+1}</td><td>{acc.get('bank','')}</td><td>{acc.get('card_no','')}</td><td>正常</td><td>{utils.format_currency(acc.get('balance',0))}</td></tr>"
                except Exception as e: logger.warning(f"Bank analysis error: {e}")

            content_html += f"""<p><strong>1. 基础收支</strong>: 总流入 {utils.format_currency(summary['total_income'])} (工资性收入: {utils.format_currency(income.get('salary_income', 0))})，总流出 {utils.format_currency(summary['total_expense'])}。</p>"""
            
            # Yearly Salary
            salary_details = income.get('salary_details', [])
            yearly_sal = {}
            for item in salary_details:
                 y = str(item.get('日期', ''))[:4]
                 if y.isdigit(): yearly_sal[y] = yearly_sal.get(y, 0) + item.get('金额', 0)
            if yearly_sal:
                 sal_rows = "; ".join([f"{y}年: {utils.format_currency(v)}" for y, v in sorted(yearly_sal.items())])
                 content_html += f"""<p style="text-indent: 4em;">(分年度工资: {sal_rows})</p>"""
            
            props = family_assets.get(person, {}).get('房产', []) if family_assets else []
            vehs = family_assets.get(person, {}).get('车辆', []) if family_assets else []
            content_html += f"""<p><strong>2. 名下资产</strong>: 房产 {len(props)} 套，车辆 {len(vehs)} 辆。</p>"""
            content_html += f"""<p><strong>3. 金融资产</strong>: 持有实际主力银行卡 <strong>{active_cards_count}</strong> 张。理财购买总额 {utils.format_currency(wealth.get('wealth_purchase', 0))}。</p>"""
            if account_rows:
                content_html += f"""<table><thead><tr><th>序号</th><th>银行</th><th>卡号</th><th>状态</th><th>余额</th></tr></thead><tbody>{account_rows}</tbody></table>"""
            content_html += f"""<p><strong>4. 主要交易对手</strong>:<br>来源: {_get_top_counterparties_str(person, 'in')}<br>去向: {_get_top_counterparties_str(person, 'out')}</p>"""

    # Family Summary
    total_family_income = sum(p['summary'].get('real_income', 0) for p in profiles.values() if p['has_data'] and p.get('entity_name', '') in core_persons)
    content_html += f"""<div class="subsection-title">【家庭数据汇总分析】</div><p><strong>家庭总真实收入(估算)</strong>: {utils.format_currency(total_family_income)}。</p></div>"""

    # Company Section
    content_html += """<div class="page"><div class="section-title">三、公司资金分析</div>"""
    for company in involved_companies:
        content_html += f"""<div class="subsection-title">【{company}】</div>"""
        comp_profile = next((p for p in profiles.values() if company in p.get('entity_name', '')), None)
        if not comp_profile: content_html += "<p>(暂无数据)</p>"; continue
        summary = comp_profile['summary']
        content_html += f"""<p><strong>1. 资金概况</strong>: 累计进账 {utils.format_currency(summary['total_income'])}，累计支出 {utils.format_currency(summary['total_expense'])}。</p>"""
        related_text = "未发现直接资金往来。"
        if cleaned_data and company in cleaned_data:
             df = cleaned_data[company]
             if not df[df['counterparty'].isin(core_persons)].empty: related_text = "发现与核心人员存在资金往来。"
        content_html += f"""<p><strong>2. 与核查人员往来</strong>: {related_text}</p>"""
        content_html += f"""<p><strong>3. 主要资金去向</strong>: {_get_top_counterparties_str(company, 'out', 3)}</p>"""
    content_html += "</div>"
    
    # Conclusion
    content_html += """<div class="page"><div class="section-title">四、结论与主要疑点</div>"""
    idx = 1
    if sum(len(v) for v in suspicions['hidden_assets'].values()) > 0:
        content_html += f"""<p><strong>{idx}. 隐形资产嫌疑</strong>: 发现相关交易。</p><ul>"""
        for ent, assets in suspicions['hidden_assets'].items():
            for asset in assets:
                 d = asset.get('date',''); amt = asset.get('amount',0); cp = asset.get('counterparty','')
                 content_html += f"""<li>{ent}: {str(d)[:10]} 支出 {utils.format_currency(amt)} (对手方: {cp})</li>"""
        content_html += "</ul>"
    content_html += "</div>"

    # 3. GENERATE VISUAL GRAPH DATA
    with open(os.path.join(os.path.dirname(output_path).replace('output/analysis_results','').replace('output\\analysis_results',''), 'templates', 'flow_visualization.html'), 'r', encoding='utf-8') as f:
        template_str = f.read()
    
    # Use config.PROJECT_ROOT if needed, but assuming relative template path or current dir logic
    # Actually output_path is d:\CJ\project\output\analysis_results\xxx.html
    # Template is d:\CJ\project\templates\flow_visualization.html
    
    flow_stats = flow_visualizer._calculate_flow_stats(cleaned_data, core_persons)
    nodes, edges, edge_stats = flow_visualizer._prepare_graph_data(flow_stats, core_persons, involved_companies)
    
    nodes_json = json.dumps([{'id':n['id'], 'label':n['label'], 'group':n['group'], 'size':n['size'], 'font':{'color':'#fff','size':14}} for n in nodes], ensure_ascii=False)
    edges_json = json.dumps([{'from':e['from'], 'to':e['to'], 'value':e['value'], 'title':e['title'], 'arrows':'to', 'color':{'color':'#00d2ff','opacity':0.8}, 'smooth':{'type':'curvedCW','roundness':0.2}} for e in edges], ensure_ascii=False)

    # 4. RENDER UNIFIED REPORT
    final_html = template_str.replace('{{NODES_JSON}}', nodes_json).replace('{{EDGES_JSON}}', edges_json)
    final_html = final_html.replace('{{GENERATE_TIME}}', datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    final_html = final_html.replace('{{CORE_PERSON_COUNT}}', str(len(core_persons)))
    final_html = final_html.replace('{{CORE_PERSON_NAMES}}', ', '.join(core_persons))
    final_html = final_html.replace('{{NODE_COUNT}}', str(len(nodes))).replace('{{EDGE_COUNT}}', str(len(edges)))
    
    # Placeholders
    for k in ['HIGH_RISK_COUNT', 'MEDIUM_RISK_COUNT', 'LOAN_PAIR_COUNT', 'NO_REPAY_COUNT']:
        final_html = final_html.replace(f'{{{{{k}}}}}', '0')
    final_html = final_html.replace('{{CORE_EDGE_COUNT}}', str(edge_stats['core']))
    final_html = final_html.replace('{{COMPANY_EDGE_COUNT}}', str(edge_stats['company']))
    final_html = final_html.replace('{{OTHER_EDGE_COUNT}}', str(edge_stats['other']))
    
    # Inject Sidebar Company
    sidebar_injection = f"""
            <div class="stat-card" style="border-left: 4px solid #ff9800;">
                <h4>涉案公司</h4>
                <div class="value">{len(involved_companies)}</div>
                <div class="desc">{', '.join(involved_companies)}</div>
            </div>
            <h3>📊 资金流向统计</h3>"""
    final_html = final_html.replace('<h3 style="margin-top: 20px;">📊 资金流向统计</h3>', sidebar_injection)

    # Inject Text Report
    report_div = f"""
    <div style="max-width: 1000px; margin: 40px auto; padding: 40px; background: #fff; border-radius: 8px; color: #333;">
        <h2 style="text-align:center; margin-bottom:30px; border-bottom:2px solid #eee; padding-bottom:10px;">📄 详细核查报告内容</h2>
        <style>
            .page {{ padding: 0; box-shadow: none; margin-bottom: 30px; }}
            .section-title {{ color: #2c3e50; border-bottom: 2px solid #3498db; margin-top: 40px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f8f9fa; }}
        </style>
        {content_html}
    </div>
    """
    final_html = final_html.replace('</body>', f'{report_div}</body>')

    with open(unified_output_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    logger.info(f"统一报告生成完毕: {unified_output_path}")
    return unified_output_path
