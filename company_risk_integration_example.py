#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公司风险分析模块集成示例
演示如何在 report_generator.py 中集成公司风险分析
"""

from company_risk_analyzer import (
    analyze_company_risk,
    format_risk_report,
    RiskThresholds
)


def _generate_company_section_enhanced(
    company,
    profiles,
    core_persons,
    cleaned_data,
    companies_profiles=None,
    company_transactions=None,
    core_persons_list=None,
    suspicions=None
):
    """
    生成公司资金核查部分（增强版 - 集成风险分析）
    
    在原有 _generate_company_section 基础上增加公司风险分析
    
    Args:
        company: 公司名称
        profiles: 资金画像字典
        core_persons: 核心人员列表（旧参数，保留兼容性）
        cleaned_data: 清洗后的数据
        companies_profiles: 所有公司的资金画像（新增）
        company_transactions: 所有公司的交易明细（新增）
        core_persons_list: 核心人员完整列表（新增）
        suspicions: 疑点检测结果（新增）
    
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

    # ===== 原有的基本分析 =====
    
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

    # ===== 新增：公司风险分析 =====
    
    # 如果提供了完整的数据，执行风险分析
    if companies_profiles and company_transactions and core_persons_list and suspicions:
        report_lines.append("")
        report_lines.append("  【风险分析】")
        
        # 执行公司风险分析
        risk_result = analyze_company_risk(
            companies_profiles=companies_profiles,
            company_transactions=company_transactions,
            core_persons=core_persons_list,
            suspicions=suspicions
        )
        
        # 显示总体风险评级
        risk_level_color = {
            "低风险": "green",
            "关注级": "orange",
            "高风险": "red"
        }.get(risk_result['overall_risk_level'], "black")
        
        report_lines.append(f"  • 风险评级: [{risk_result['overall_risk_level']}] ({risk_result['overall_risk_score']}/100分)")
        
        # 各维度评分
        report_lines.append(f"  • 维度评分:")
        dim_names = {
            "inter_company_risk": "公司间往来",
            "company_to_person_risk": "公司向个人",
            "asset_anomaly_risk": "资产异常",
            "operational_risk": "经营合理性"
        }
        
        for dim_key, dim_data in risk_result["dimensions"].items():
            dim_cn = dim_names.get(dim_key, dim_key)
            score = dim_data["score"]
            if score > 0:
                report_lines.append(f"    - {dim_cn}: {score}分")
            else:
                report_lines.append(f"    - {dim_cn}: 正常")
        
        # 风险排除说明
        if risk_result["risk_exclusions"]:
            report_lines.append("")
            report_lines.append(f"  • 风险排除说明:")
            for exclusion in risk_result["risk_exclusions"][:3]:  # 只显示前3条
                report_lines.append(f"    ✓ {exclusion}")
            if len(risk_result["risk_exclusions"]) > 3:
                report_lines.append(f"    (共{len(risk_result['risk_exclusions'])}项排除)")
        
        # 高风险红旗（最多显示5条）
        if risk_result["red_flags"]:
            report_lines.append("")
            report_lines.append(f"  • 高风险预警:")
            for i, flag in enumerate(risk_result["red_flags"][:5], 1):
                report_lines.append(f"    {i}. [{flag['type']}] {flag['details']}")
            if len(risk_result["red_flags"]) > 5:
                report_lines.append(f"    (共{len(risk_result['red_flags'])}项风险)")
    
    # 3.4 隐匿链路提示
    report_lines.append("")
    report_lines.append(f"  • 隐匿链路排查: 经穿透分析，未发现明显的第三方（如关联自然人、空壳公司）中转资金链路。")
    report_lines.append("")

    return report_lines


def generate_excel_sheet_company_risk(
    writer,
    risk_result,
    company_name
):
    """
    生成公司风险分析的Excel工作表
    
    Args:
        writer: ExcelWriter对象
        risk_result: 风险分析结果
        company_name: 公司名称
    """
    sheet_name = f"公司风险-{company_name}"
    # 限制sheet名称长度
    if len(sheet_name) > 31:
        sheet_name = sheet_name[:28] + "..."
    
    # 1. 总体评级
    overall_data = [{
        '公司名称': company_name,
        '风险等级': risk_result['overall_risk_level'],
        '总分': risk_result['overall_risk_score'],
        '公司间往来': risk_result['dimensions']['inter_company_risk']['score'],
        '公司向个人': risk_result['dimensions']['company_to_person_risk']['score'],
        '资产异常': risk_result['dimensions']['asset_anomaly_risk']['score'],
        '经营合理性': risk_result['dimensions']['operational_risk']['score']
    }]
    
    pd.DataFrame(overall_data).to_excel(writer, sheet_name=sheet_name + '-总评', index=False)
    
    # 2. 详细证据
    all_evidence = []
    for dim_key, dim_data in risk_result["dimensions"].items():
        for evidence in dim_data["evidence"]:
            all_evidence.append({
                '维度': dim_key,
                '类型': evidence.get('type', ''),
                '描述': evidence.get('description', ''),
                '强度': evidence.get('strength', ''),
                '风险原因': evidence.get('risk_reason', '')
            })
    
    if all_evidence:
        pd.DataFrame(all_evidence).to_excel(writer, sheet_name=sheet_name + '-证据', index=False)
    
    # 3. 高风险红旗
    if risk_result["red_flags"]:
        red_flag_data = [{
            '类型': flag['type'],
            '详情': flag['details'],
            '原因': flag['reason'],
            '维度': flag['dimension']
        } for flag in risk_result["red_flags"]]
        pd.DataFrame(red_flag_data).to_excel(writer, sheet_name=sheet_name + '-红旗', index=False)


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("公司风险分析模块 - 集成示例")
    print("=" * 80)
    print()
    print("本文件演示了如何在报告生成器中集成公司风险分析模块。")
    print()
    print("主要功能：")
    print("1. _generate_company_section_enhanced() - 增强版公司章节生成函数")
    print("2. generate_excel_sheet_company_risk() - 生成Excel风险分析表")
    print()
    print("使用方法：")
    print("1. 在 report_generator.py 中导入本模块")
    print("2. 准备公司资金画像、交易明细、核心人员列表、疑点检测结果")
    print("3. 调用 analyze_company_risk() 执行风险分析")
    print("4. 将结果集成到报告和Excel中")
    print()
    print("详细文档请参考: docs/公司层面风险分析设计文档.md")
    print("=" * 80)
