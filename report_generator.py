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
                            family_assets: Dict = None) -> str:
    """
    生成公文格式的核查结果分析报告
    """
    # 同时也生成HTML报告
    html_path = output_path.replace('.txt', '.html')
    generate_html_report(profiles, suspicions, core_persons, involved_companies, html_path, family_summary, family_assets)
    
    if output_path is None:
        output_path = config.OUTPUT_REPORT_FILE.replace('.docx', '.txt')
    
    logger.info(f'正在生成公文报告: {output_path}')
    
    report_lines = []
    
    import os
    
    # 标题
    report_lines.append(f"{config.REPORT_TITLE}")
    report_lines.append("=" * 60)
    report_lines.append(f"生成日期: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
    report_lines.append("")
    
    # 统计过程文件 (带去重)
    process_files = set()  # 使用集合去重
    base_dir = 'output/cleaned_data'
    if os.path.exists(base_dir):
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                if f.endswith('.xlsx') and not f.startswith('~'):
                    # 只记录合并流水，避免太乱
                    if '合并流水' in f or 'cleaning_log' in f:
                        process_files.add(f)
    
    # 转换为排序后的列表
    process_files = sorted(list(process_files))
    
    report_lines.append(f"【过程数据清单】 (共生成 {len(process_files)} 个核心数据表)")
    for i, f in enumerate(process_files, 1):
        report_lines.append(f"  {i}. {f}")
    report_lines.append("-" * 60)
    report_lines.append("")
    
    # 插入账户架构分析 (新增)
    import account_analyzer
    report_lines.append("一、账户架构深度分析")
    report_lines.append("-" * 60)
    for entity, profile in profiles.items():
        # 只分析核心人员
        is_core = any(p in entity for p in core_persons)
        if is_core and profile['has_data']:
            # 我们需要原始dataframe，这里假设profile中没存df，需要重新读取或者传递
            # 实际上在main.py中我们有cleaned_data，但这里generate_official_report只接了profiles
            # 这是一个架构问题。为了快速修复，我们在profile生成时最好把account_report放进去
            # 或者这里临时读一下文件（不太好但可行）
            pass 
            
    # 由于架构限制，我们先把骨架搭好，还是在main.py里生成好报告内容传进来比较好
    # 但为了不改动接口，我们在main.py里调用 account_analyzer 生成每个人的报告文本，
    # 存入 profile['account_analysis_text'] 字段
    
    for entity, profile in profiles.items():
        if 'account_analysis_text' in profile:
            report_lines.append(profile['account_analysis_text'])
            report_lines.append("")

    # 二、基本情况 (原一、基本情况，顺延)
    report_lines.append("二、基本情况")
    report_lines.append("-" * 60)
    report_lines.append(f"本次核查共涉及核心人员 {len(core_persons)} 人,涉案公司 {len(involved_companies)} 家。")
    report_lines.append(f"核心人员名单: {', '.join(core_persons)}")
    report_lines.append(f"涉案公司名单: {', '.join(involved_companies)}")
    report_lines.append("")
    
    total_transactions = sum(
        p['summary']['transaction_count'] for p in profiles.values() if p['has_data']
    )
    report_lines.append(f"共分析银行流水 {total_transactions} 笔交易记录。")
    report_lines.append("")
    
    # 三、个人资产及资金分析
    report_lines.append("三、个人资产及资金分析")
    report_lines.append("-" * 60)
    
    for person in core_persons:
        person_profile = None
        for entity, profile in profiles.items():
            if person in entity and profile['has_data']:
                person_profile = profile
                break
        
        report_lines.append(f"\n【{person}】")
        
        if person_profile:
            summary = person_profile['summary']
            income_structure = person_profile.get('income_structure', {})
            
            # 1. 基础收支
            report_lines.append("  1. 基础收支情况")
            report_lines.append(f"     数据时间范围: {summary['date_range'][0].strftime('%Y-%m-%d')} 至 {summary['date_range'][1].strftime('%Y-%m-%d')}")
            report_lines.append(f"     资金流入总额: {utils.format_currency(summary['total_income'])} (其中真实收入: {utils.format_currency(summary.get('real_income', summary['total_income']))})")
            report_lines.append(f"     资金流出总额: {utils.format_currency(summary['total_expense'])} (其中真实支出: {utils.format_currency(summary.get('real_expense', summary['total_expense']))})")
            report_lines.append(f"     工资性收入: {utils.format_currency(income_structure.get('salary_income', 0))} (占比 {summary['salary_ratio']:.1%})")
            
            # 分年度工资统计
            salary_details = income_structure.get('salary_details', [])
            if salary_details:
                salary_yearly = {}
                for item in salary_details:
                    d = item.get('日期')
                    if hasattr(d, 'year'):
                        year = d.year
                    else:
                        try:
                            year = int(str(d)[:4])
                        except (ValueError, TypeError):
                            continue
                    salary_yearly[year] = salary_yearly.get(year, 0) + item.get('金额', 0)
                
                if salary_yearly:
                    report_lines.append("     分年度工资收入:")
                    for year in sorted(salary_yearly.keys()):
                        report_lines.append(f"       - {year}年: {utils.format_currency(salary_yearly[year])}")
            
            
            # 1.5 理财分析 (新增)
            wealth_mgmt = person_profile.get('wealth_management', {})
            if wealth_mgmt.get('total_transactions', 0) > 0:
                report_lines.append("  2. 理财及资金运作情况")
                report_lines.append(f"     理财购买: {utils.format_currency(wealth_mgmt.get('wealth_purchase', 0))} ({wealth_mgmt.get('wealth_purchase_count', 0)}笔)")
                report_lines.append(f"     理财赎回: {utils.format_currency(wealth_mgmt.get('wealth_redemption', 0))} ({wealth_mgmt.get('wealth_redemption_count', 0)}笔)")
                report_lines.append(f"     理财收益: {utils.format_currency(wealth_mgmt.get('wealth_income', 0))} ({wealth_mgmt.get('wealth_income_count', 0)}笔)")
                report_lines.append(f"     真实理财净收益: {utils.format_currency(wealth_mgmt.get('real_wealth_profit', 0))}")
                
                # 分类统计
                cats = wealth_mgmt.get('category_stats', {})
                active_cats = [k for k, v in cats.items() if v['笔数'] > 0]
                if active_cats:
                    report_lines.append(f"     主要涉足理财类型: {', '.join(active_cats)}")
            
            # 2. 大额资产与信贷线索
            asset_trails = _analyze_person_asset_trails(person)
            if asset_trails:
                report_lines.append("\n  3. 大额资产购值及信贷线索")
                report_lines.extend(asset_trails)
            else:
                report_lines.append("\n  3. 大额资产线索")
                report_lines.append("     (流水中未发现明显的房产/车辆大额支出或规律性还贷记录)")
                
        else:
            report_lines.append("  (暂无该人员银行流水数据)")
        
        report_lines.append("")

    # 四、家族关系及资产情况
    if family_summary or family_assets:
        report_lines.append("四、家族关系及资产情况")
        report_lines.append("-" * 60)
        
        # 合并展示：先讲关系，再讲资产(房/车)
        # 获取所有相关人员
        all_family_keys = set()
        if family_summary: all_family_keys.update(family_summary.keys())
        if family_assets: all_family_keys.update(family_assets.keys())
        
        for person in all_family_keys:
            report_lines.append(f"\n【{person}】家族概况")
            
            # 关系
            if family_summary and person in family_summary:
                rels = family_summary[person]
                members = []
                for k, v in rels.items():
                    if v: members.extend([f"{m}({k})" for m in v])
                if members:
                    report_lines.append(f"  关联成员: {', '.join(members)}")
            
            # 资产
            if family_assets and person in family_assets:
                assets = family_assets[person]
                report_lines.append(f"  名下房产: {assets['房产套数']} 套 | 车辆: {assets['车辆数量']} 辆")
                
                # 房产明细 (修复价格显示)
                if assets['房产']:
                    for i, prop in enumerate(assets['房产'], 1):
                        price = prop.get('交易金额', 0)
                        # 逻辑修正：金额<=5或None显示为未获取
                        try:
                            price_val = float(price)
                            price_str = f"{price_val:.2f}万元" if price_val > 5 else "未在查询数据中获取"
                        except (ValueError, TypeError):
                            price_str = "未在查询数据中获取"
                            
                        report_lines.append(f"  [房产{i}] {prop['房地坐落']}")
                        
                        # 日期校验：1900年之前的日期视为异常
                        reg_time = prop.get('登记时间', '未知')
                        if reg_time and '1899' in str(reg_time) or '1900' in str(reg_time)[:4]:
                            reg_time_str = "日期数据异常"
                        else:
                            reg_time_str = str(reg_time)
                        
                        report_lines.append(f"     面积: {prop['建筑面积']}㎡ | 金额: {price_str} | 购买时间: {reg_time_str}")
                
                # 车辆明细
                if assets['车辆']:
                    for i, vehicle in enumerate(assets['车辆'], 1):
                        report_lines.append(f"  [车辆{i}] {vehicle['中文品牌']} {vehicle['号牌号码']} ({vehicle['初次登记日期']})")
            report_lines.append("")

    # 五、涉案公司资金流向
    report_lines.append("五、涉案公司资金流向")
    report_lines.append("-" * 60)
    for company in involved_companies:
        company_profile = None
        for entity, profile in profiles.items():
            if company in entity and profile['has_data']:
                company_profile = profile
                break
        
        if company_profile:
            summary = company_profile['summary']
            report_lines.append(f"\n【{company}】")
            report_lines.append(f"  资金流转: 流入 {utils.format_currency(summary['total_income'])} / 流出 {utils.format_currency(summary['total_expense'])}")
            report_lines.append(f"  主要流向: 第三方支付占比 {summary['third_party_ratio']:.1%}")
        else:
            report_lines.append(f"\n【{company}】 (暂无流水数据)")
    report_lines.append("")
    
    # 六、主要疑点发现
    report_lines.append("六、主要疑点发现")
    report_lines.append("-" * 60)
    
    total_suspicions = (
        len(suspicions['direct_transfers']) +
        len(suspicions['cash_collisions']) +
        sum(len(v) for v in suspicions['hidden_assets'].values()) +
        sum(len(v) for v in suspicions['fixed_frequency'].values())
    )
    
    report_lines.append(f"经系统分析,共锁定 {total_suspicions} 个异常风险点:\n")
    
    # 动态子章节编号
    sub_idx = 1
    
    if suspicions['direct_transfers']:
        num_str = utils.number_to_chinese(sub_idx)
        report_lines.append(f"({num_str}) 利益输送嫌疑 (直接资金往来 {len(suspicions['direct_transfers'])} 笔)")
        sub_idx += 1
        for i, t in enumerate(suspicions['direct_transfers'], 1):
            d = '收到' if t['direction'] == 'receive' else '支付'
            report_lines.append(f"  {i}. {t['person']} {d} {t['company']} {utils.format_currency(t['amount'])} (摘要:{t['description']})")
    
    if suspicions['cash_collisions']:
        num_str = utils.number_to_chinese(sub_idx)
        report_lines.append(f"\n({num_str}) 现金走账嫌疑 (时空伴随 {len(suspicions['cash_collisions'])} 对)")
        sub_idx += 1
        for i, c in enumerate(suspicions['cash_collisions'][:5], 1):
            report_lines.append(f"  {i}. {c['withdrawal_date'].strftime('%m-%d')} 取现 vs {c['deposit_date'].strftime('%m-%d')} 存现 | 金额: {c['withdrawal_amount']} -> {c['deposit_amount']}")

    if sum(len(v) for v in suspicions['hidden_assets'].values()) > 0:
        num_str = utils.number_to_chinese(sub_idx)
        report_lines.append(f"\n({num_str}) 隐形资产嫌疑 (疑似购房/购车)")
        sub_idx += 1
        global_idx = 1
        for ent, assets in suspicions['hidden_assets'].items():
            for asset in assets:
                 report_lines.append(f"  {global_idx}. {ent}: {asset['date'].strftime('%Y-%m-%d')} 支出 {utils.format_currency(asset['amount'])}")
                 report_lines.append(f"     对手方: {asset['counterparty']}")
                 report_lines.append(f"     摘要: {asset.get('description', '未知')}")
                 global_idx += 1
    
    if sum(len(v) for v in suspicions['fixed_frequency'].values()) > 0:
        num_str = utils.number_to_chinese(sub_idx)
        report_lines.append(f"\n({num_str}) 固定频率异常进账 (共 {sum(len(v) for v in suspicions['fixed_frequency'].values())} 个模式)")
        sub_idx += 1
        global_idx = 1
        for ent, patterns in suspicions['fixed_frequency'].items():
            for p in patterns:
                 report_lines.append(f"  {global_idx}. {ent}: 每月{p['day_avg']}日, 均额 {utils.format_currency(p['amount_avg'])} (出现{p['occurrences']}次)")
                 global_idx += 1

    report_lines.append("")
    report_lines.append("=" * 60)
    report_lines.append(f"(本报告由资金穿透与关联排查系统自动生成)")
    
    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    logger.info(f'公文报告生成完成: {output_path}')
    return output_path

def _analyze_person_asset_trails(person_name: str) -> List[str]:
    """
    针对单个核心人员的资产线索分析 (车/房)
    读取该人员的清洗后Excel进行深度挖掘
    """
    import os
    text_lines = []
    
    file_path = f'output/cleaned_data/个人/{person_name}_合并流水.xlsx'
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

def generate_html_report(profiles: Dict,
                        suspicions: Dict,
                        core_persons: List[str],
                        involved_companies: List[str],
                        output_path: str,
                        family_summary: Dict = None,
                        family_assets: Dict = None) -> str:
    """
    生成HTML格式的精美报告 (修复版)
    
    修复内容:
    1. 使用正确的列名读取银行账户和余额
    2. 动态计算现金收支
    3. 增强结论生成逻辑
    """
    logger.info(f'正在生成HTML报告: {output_path}')
    
    content_html = ""
    
    # 1. 标题页
    person_list_str = "、".join(core_persons[:3]) + (f"等{len(core_persons)}人" if len(core_persons) > 3 else "")
    company_list_str = "、".join(involved_companies[:2]) + (f"等{len(involved_companies)}家公司" if len(involved_companies) > 2 else "")
    
    title_html = f"""
    <div class="page">
        <h1>关于{person_list_str}等信息查询结果分析报告</h1>
        
        <p>
            依据纪检监察组转来的关于相关问题线索，我单位申请查询了{person_list_str}的银行账户、交易流水、金融理财、不动产信息、反洗钱、理财产品、保险产品、信托产品，证券账户、证券持有变动信息，同户籍、机动车，企业登记、纳税、同行人等信息，申请查询了{company_list_str}的银行账户信息、交易流水，企业登记信息，现对反馈的查询结果进行分析报告如下：
        </p>
    """
    content_html += title_html
    
    # 2. 个人/公司分析部分 (Loop)
    section_index = 1
    
    # 定义公司关键词
    company_keywords = ['公司', '有限', '集团', '企业', '股份', '实业', '投资', '贸易']
    
    def is_company(name):
        """判断是否为公司"""
        return any(kw in name for kw in company_keywords)
    
    for person in core_persons:
        # 获取个人数据
        profile = None
        for entity, p in profiles.items():
            if person in entity and p['has_data']:
                profile = p
                break
        
        if not profile:
            continue
            
        summary = profile['summary']
        income = profile.get('income_structure', {})
        
        # 尝试获取家庭信息
        family_text = f"{person}，身份信息待补充。"
        if family_summary and person in family_summary:
            rels = family_summary[person]
            members = []
            for k, v in rels.items():
                if v: members.extend([f"{m}" for m in v])
            if members:
                family_text += f" 家庭成员包括：{', '.join(members)}。"
        
        # 家庭资产
        prop_text = "名下未查见房产信息。"
        vehicle_text = "名下未查见车辆信息。"
        if family_assets and person in family_assets:
            assets = family_assets[person]
            if assets['房产']:
                prop_text = f"名下查见房产 {len(assets['房产'])} 套。"
                prop_details = []
                for p_item in assets['房产']:
                    prop_details.append(f"{p_item.get('房地坐落', '未知地址')} ({p_item.get('建筑面积', 0)}平米)")
                prop_text += "具体为：" + "；".join(prop_details) + "。"
            
            if assets['车辆']:
                vehicle_text = f"名下查见车辆 {len(assets['车辆'])} 辆。"
                veh_details = []
                for v_item in assets['车辆']:
                    veh_details.append(f"{v_item.get('中文品牌', '汽车')} (车牌:{v_item.get('号牌号码', '-')})")
                vehicle_text += "具体为：" + "；".join(veh_details) + "。"

        # 工资收入
        salary_val = income.get('salary_income', 0)
        salary_text = f"{summary['date_range'][0].year}年至{summary['date_range'][1].year}年共取得工资收入 {utils.format_currency(salary_val)}。"
        
        # 银行账户表格 - 使用正确的列名
        account_rows = ""
        bank_files = glob.glob(f'output/cleaned_data/个人/{person}_合并流水.xlsx')
        account_count = 0
        balance_total = 0
        
        # 计算现金收支
        cash_deposit = 0
        cash_withdrawal = 0
        
        if bank_files:
            try:
                df_flow = pd.read_excel(bank_files[0])
                
                # === 计算现金收支 ===
                # 检查现金列
                if '现金' in df_flow.columns:
                    cash_df = df_flow[df_flow['现金'] == True]
                    if '收入(元)' in df_flow.columns:
                        cash_deposit = cash_df['收入(元)'].sum()
                    if '支出(元)' in df_flow.columns:
                        cash_withdrawal = cash_df['支出(元)'].sum()
                
                # === 银行账户统计 ===
                # 正确的列名: 本方账号, 余额(元), 所属银行
                account_col = None
                balance_col = None
                bank_col = None
                
                for col in ['本方账号', '账户号', '交易卡号', '卡号']:
                    if col in df_flow.columns:
                        account_col = col
                        break
                        
                for col in ['余额(元)', '余额', '交易后余额', '账户余额']:
                    if col in df_flow.columns:
                        balance_col = col
                        break
                        
                for col in ['所属银行', '交易开户行', '开户行', '银行名称']:
                    if col in df_flow.columns:
                        bank_col = col
                        break
                
                if account_col and balance_col:
                    # 按账号分组
                    account_groups = df_flow.groupby(account_col)
                    
                    real_accounts = []
                    
                    for acc_no, group in account_groups:
                        # 1. 基本信息获取
                        last_row = group.iloc[-1]
                        bank_name = str(last_row.get(bank_col, '未知银行'))
                        
                        # 2. 排除明确的理财账户标识
                        if '理财' in bank_name or '基金' in bank_name or '证券' in bank_name or '信托' in bank_name:
                            continue
                            
                        # 3. 交易行为特征分析
                        # 获取该账户的所有交易摘要
                        descriptions = group['摘要'].fillna('').astype(str).tolist()
                        counterparties = group['交易对手'].fillna('').astype(str).tolist() if '交易对手' in group.columns else []
                        
                        total_tx = len(group)
                        if total_tx == 0: continue
                        
                        # 特征A: 理财关键词密度
                        wealth_keywords = ['理财', '赎回', '申购', '认购', '分红', '收益', '结息', '利息', '到期', '本息']
                        wealth_count = sum(1 for d in descriptions if any(k in d for k in wealth_keywords))
                        
                        # 特征B: 仅与本人往来 (影子账户)
                        self_tx_count = sum(1 for cp in counterparties if person in cp or cp == 'nan' or not cp)
                        
                        # 判定规则:
                        # 如果 90% 以上是理财相关，且无明显生活消费/工资，判定为理财子账户
                        is_wealth_account = False
                        if total_tx > 0 and (wealth_count / total_tx) > 0.9:
                             is_wealth_account = True
                        
                        # 如果 100% 是自我转账/空对手方，且摘要含理财/利息，判定为影子账户
                        if total_tx > 0 and (self_tx_count / total_tx) > 0.99 and wealth_count > 0:
                            is_wealth_account = True
                            
                        if not is_wealth_account:
                            # 只有真实账户才加入列表
                            bal = last_row.get(balance_col, 0)
                            try:
                                bal_float = float(bal) if pd.notna(bal) else 0
                                balance_total += bal_float
                            except:
                                bal_float = 0
                            
                            real_accounts.append({
                                'bank': bank_name[:15] if bank_name else '未知银行',
                                'no': str(acc_no),
                                'balance': bal_float
                            })
                    
                    # 按余额降序排序，只展示前 20 个主要账户 (避免表格过长)
                    real_accounts.sort(key=lambda x: x['balance'], reverse=True)
                    account_count = len(real_accounts)
                    
                    for i, acc in enumerate(real_accounts[:20]):
                         account_rows += f"""
                        <tr>
                            <td>{i + 1}</td>
                            <td>{acc['bank']}</td>
                            <td>{acc['no']}</td>
                            <td>借记卡</td>
                            <td>正常</td>
                            <td>{utils.format_currency(acc['balance'])}</td>
                        </tr>
                        """
                    
                    if len(real_accounts) > 20:
                         account_rows += f"""
                        <tr>
                            <td colspan="6" style="text-align: center; color: #666;">(仅展示余额最大的前20个账户，已隐藏 {len(real_accounts)-20} 个小额/非活跃账户)</td>
                        </tr>
                        """
            except Exception as e:
                logger.error(f"Error reading account info for HTML: {e}")

        
        # 根据是个人还是公司，生成不同的报告内容
        entity_is_company = is_company(person)
        
        if entity_is_company:
            # 公司报告模板
            person_section = f"""
        <div class="section-title">{utils.number_to_chinese(section_index)}、{person}资金往来情况及数据分析</div>

        <div class="subsection-title">（一）{person}基本情况</div>
        <p>
            {person}，企业信息待补充。
        </p>

        <p><strong>1、银行账户情况</strong></p>
        <p>{person}持有银行账户余额 {utils.format_currency(balance_total)}，共涉及 {account_count} 个银行账户。</p>
        
        <table>
            <thead>
                <tr>
                    <th>序号</th>
                    <th>反馈单位</th>
                    <th>账号</th>
                    <th>账户类别</th>
                    <th>账户状态</th>
                    <th>账户余额</th>
                </tr>
            </thead>
            <tbody>
                {account_rows if account_rows else '<tr><td colspan="6">暂无账户明细数据</td></tr>'}
            </tbody>
        </table>

        <div class="subsection-title">（二）资金往来分析</div>
        
        <p><strong>1、资金流入流出概况</strong></p>
        <p>
            查询{person}名下银行账户流水，{summary['date_range'][0].strftime('%Y年%m月')}至{summary['date_range'][1].strftime('%Y年%m月')}间资金流入总额 {utils.format_currency(summary['total_income'])}，资金流出总额 {utils.format_currency(summary['total_expense'])}。
        </p>

        <p><strong>2、银行流水交易对象分析</strong></p>
        <p>
            资金流入方面：总资金流入 {utils.format_currency(summary['total_income'])}。
        </p>
        <p>
            资金流出方面：总资金流出 {utils.format_currency(summary['total_expense'])}。
        </p>

        <p><strong>3、大额现金交易</strong></p>
        <p>累计发生现金类收支，其中收款 {utils.format_currency(cash_deposit)}，支出 {utils.format_currency(cash_withdrawal)}。</p>
        """
        else:
            # 个人报告模板（原有逻辑）
            person_section = f"""
        <div class="section-title">{utils.number_to_chinese(section_index)}、{person}家庭资产收入情况及数据分析</div>

        <div class="subsection-title">（一）{person}家庭资产收入情况</div>
        <p>
            {family_text}
        </p>

        <p><strong>1、房产情况</strong></p>
        <p>{prop_text}</p>

        <p><strong>2、工资奖金收入</strong></p>
        <p>
            {salary_text}
            年平均收入 {utils.format_currency(salary_val / ((summary['date_range'][1] - summary['date_range'][0]).days / 365) if (summary['date_range'][1] - summary['date_range'][0]).days > 0 else 0)}。
        </p>

        <p><strong>3、银行存款情况</strong></p>
        <p>{person}持有银行卡余额 {utils.format_currency(balance_total)}，共涉及 {account_count} 个银行账户。</p>
        
        <table>
            <thead>
                <tr>
                    <th>序号</th>
                    <th>反馈单位</th>
                    <th>卡号</th>
                    <th>账户类别</th>
                    <th>账户状态</th>
                    <th>账户余额</th>
                </tr>
            </thead>
            <tbody>
                {account_rows if account_rows else '<tr><td colspan="6">暂无账户明细数据</td></tr>'}
            </tbody>
        </table>

        <p><strong>4、车辆情况</strong></p>
        <p>{vehicle_text}</p>

        <div class="subsection-title">（二）数据分析</div>
        
        <p><strong>1、家庭存款与家庭收入匹配分析</strong></p>
        <p>
            查询{person}名下银行卡流水，{summary['date_range'][0].strftime('%Y年%m月')}至{summary['date_range'][1].strftime('%Y年%m月')}间资金流入总额 {utils.format_currency(summary['total_income'])} (真实收入: {utils.format_currency(summary.get('real_income', summary['total_income']))})，资金流出总额 {utils.format_currency(summary['total_expense'])} (真实支出: {utils.format_currency(summary.get('real_expense', summary['total_expense']))})。
            其中工资性收入占比 {summary['salary_ratio']:.1%}。
        </p>

        <p><strong>2、银行流水交易对象分析</strong></p>
        <p>
            资金流入方面：资金流入总额 {utils.format_currency(summary['total_income'])}。
            主要包括：工资收入 {utils.format_currency(salary_val)}、
            现金存入 {utils.format_currency(cash_deposit)}。
        </p>
        <p>
            资金流出方面：资金流出总额 {utils.format_currency(summary['total_expense'])}。
            主要包括：现金取款 {utils.format_currency(cash_withdrawal)}、
            日常消费及其他支出。
        </p>

        <p><strong>3、大额存取现分析</strong></p>
        <p>累计发生现金类收支，其中收款 {utils.format_currency(cash_deposit)}，支出 {utils.format_currency(cash_withdrawal)}。</p>
        """
        content_html += person_section
        section_index += 1
    
    # 3. 结论部分
    conclusion_html = f"""
    <div class="section-title">{utils.number_to_chinese(section_index)}、结论</div>
    <p>通过对查询结果分析，发现以下情况：</p>
    """
    
    # 自动生成结论点
    idx = 1
    
    # 疑点1: 隐形资产
    hidden_suspects = []
    if suspicions.get('hidden_assets'):
        for p in suspicions['hidden_assets']:
            if p in core_persons:  # 只报告核心人员
                hidden_suspects.append(p)
    if hidden_suspects:
        conclusion_html += f"<p>{idx}、{', '.join(hidden_suspects)} 存在疑似购房/购车的大额资金支出。</p>"
        idx += 1
        
    # 疑点2: 资金缺口（支出>工资2倍）
    gap_suspects = []
    for p in core_persons:
        for entity, profile in profiles.items():
            if p in entity and profile['has_data']:
                salary = profile.get('income_structure', {}).get('salary_income', 0)
                expense = profile['summary']['total_expense']
                if salary > 0 and expense > salary * 2:
                    gap_suspects.append(p)
                break
    if gap_suspects:
        conclusion_html += f"<p>{idx}、{', '.join(gap_suspects)} 个人支出规模显著高于工资收入水平，需进一步核实收入来源。</p>"
        idx += 1

    # 疑点3: 直接资金往来
    if suspicions.get('direct_transfers') and len(suspicions['direct_transfers']) > 0:
        conclusion_html += f"<p>{idx}、发现核心人员与涉案公司之间存在 {len(suspicions['direct_transfers'])} 笔直接资金往来。</p>"
        idx += 1

    # 疑点4: 现金时空伴随
    if suspicions.get('cash_collisions') and len(suspicions['cash_collisions']) > 0:
        conclusion_html += f"<p>{idx}、发现 {len(suspicions['cash_collisions'])} 对现金时空伴随记录，疑似现金走账。</p>"
        idx += 1

    if idx == 1:
        conclusion_html += "<p>未发现明显异常情况。</p>"

    conclusion_html += f"""
    <div class="section-title">{utils.number_to_chinese(section_index + 1)}、下一步工作计划</div>
    <p>1、针对发现的异常资金往来，建议进一步开展核查。</p>
    <p>2、对疑似隐形资产线索进行实地核实。</p>
    <p>3、如需进一步查证，建议调取微信、支付宝等第三方支付平台明细。</p>
    </div>
    """
    
    content_html += conclusion_html
    
    # 渲染最终HTML（使用文件开头定义的HTML_TEMPLATE）
    final_html = HTML_TEMPLATE.replace('<!-- CONTENT_PLACEHOLDER -->', content_html)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
        
    logger.info(f'HTML报告生成完成: {output_path}')
    return output_path

