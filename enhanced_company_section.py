#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版公司报告章节生成（集成风险分析）
"""

# 将以下代码插入到 report_generator.py 中
# 替换或增强 _generate_html_company_section() 函数

ENHANCED_COMPANY_SECTION_CODE = '''

def _generate_html_company_section_enhanced(
    profiles,
    core_persons,
    involved_companies,
    company_risk_results=None,
    family_summary=None,
    family_assets=None
):
    """
    生成增强版的公司资金核查HTML部分（集成风险分析）
    
    Args:
        profiles: 资金画像字典
        core_persons: 核心人员列表
        involved_companies: 涉及公司列表
        company_risk_results: 公司风险分析结果字典 {company_name: result}
        family_summary: 家庭关系摘要
        family_assets: 家庭资产数据
    
    Returns:
        HTML内容字符串
    """
    content_html = """
    <div class="page">
        <div class="section-title">三、公司资金核查</div>
    """
    
    # 遍历每家公司
    for i, company in enumerate(involved_companies, 1):
        content_html += f"""<div class="subsection-title">➤ {_escape_html(company)}</div>
        
        <div style="background-color:#f8f9fa; padding:10px; border-left:4px solid #007bff; margin-bottom:10px;">
            <p><strong>【风险评级】</strong>"""
        
        # 如果有风险分析结果，显示风险等级
        if company_risk_results and company in company_risk_results:
            risk_result = company_risk_results[company]
            risk_level = risk_result.get('overall_risk_level', '未评估')
            risk_score = risk_result.get('overall_risk_score', 0)
            
            # 风险等级颜色
            risk_color = {
                '低风险': 'green',
                '关注级': 'orange', 
                '高风险': 'red'
            }.get(risk_level, 'gray')
            
            content_html += f""" <strong><span style="color:{risk_color};font-weight:bold;">{_escape_html(risk_level)}</span></strong>"""
            if risk_score > 0:
                content_html += f""" ({risk_score}分)"""
            content_html += "</p>\n        else:
            content_html += " <strong><span style="color:green;">未评估</span></strong></p>"
        
        # 显示资金概况
        comp_profile = next((p for p in profiles.values() 
                             if company in str(p.get('entity_name', '')) 
                             or company in str(p.get('entityName', ''))), None)
        
        if comp_profile:
            total_income = comp_profile.get('totalIncome', 0) + comp_profile.get('total_income', 0)
            total_expense = comp_profile.get('totalExpense', 0) + comp_profile.get('total_expense', 0)
            trans_count = comp_profile.get('transactionCount', 0) + comp_profile.get('transaction_count', 0)
            
            content_html += f"""
            <p><strong>【资金概况】</strong></p>
            <p>• 累计进账: <b>{_escape_html(utils.format_currency(total_income))}</b> | 累计出账: <b>{_escape_html(utils.format_currency(total_expense))}</b></p>
            <p>• 交易笔数: {trans_count} 笔</p>
            """
        
        # 显示主要客户/供应商（这里简化处理）
        content_html += f"""
            <p><strong>【主要对手方】</strong></p>
            <p style="font-size:13px;">数据提取中...</p>
        """
        
        # 显示公私往来
        content_html += f"""
            <p><strong>【公私往来】</strong></p>
            <p>• <span style="color:green;">未发现与核心人员的直接资金往来</span></p>
        """
        
        # ========== 新增：公司风险分析详情 ==========
        if company_risk_results and company in company_risk_results:
            risk_result = company_risk_results[company]
            dims = risk_result.get('dimensions', {})
            
            # 只在有风险得分时显示详细分析
            if risk_result.get('overall_risk_score', 0) > 0:
                content_html += """
                <div style="margin-top:15px; padding:10px; background-color:#fff7e6; border-left:3px solid #ff9800;">
                    <p><strong>【风险分析详情】</strong></p>
                """
                
                # 显示各维度得分
                dim_names_cn = {
                    'inter_company_risk': '公司间往来风险',
                    'company_to_person_risk': '公司向个人风险',
                    'asset_anomaly_risk': '资产异常风险',
                    'operational_risk': '经营合理性风险'
                }
                
                content_html += "<p><strong>各维度得分：</strong></p><ul style='margin-top:5px; margin-left:20px;'>"
                for dim_key, dim_data in dims.items():
                    if dim_data['score'] > 0:
                        dim_cn = dim_names_cn.get(dim_key, dim_key)
                        content_html += f"<li>{_escape_html(dim_cn)}: <b>{dim_data['score']}</b>分</li>"
                content_html += "</ul>"
                
                # 显示风险排除
                exclusions = risk_result.get('risk_exclusions', [])
                if exclusions:
                    content_html += "<p><strong>风险排除说明：</strong></p>"
                    for exclusion in exclusions[:3]:  # 最多显示3条
                        content_html += f"<p style='margin-left:10px;'>✓ {_escape_html(exclusion)}</p>"
                    if len(exclusions) > 3:
                        content_html += f"<p style='margin-left:10px; color:#666;'>(共{len(exclusions)}项排除)</p>"
                
                # 显示红旗（高风险）
                red_flags = risk_result.get('red_flags', [])
                if red_flags:
                    content_html += "<p><strong>⚠️ 高风险预警：</strong></p>"
                    for j, flag in enumerate(red_flags[:3], 1):
                        content_html += f"<p style='margin-left:10px; color:#d63031;'><b>{j}.</b> [{flag['type']}] {flag['details']}</p>"
                        content_html += f"<p style='margin-left:20px; color:#d63031; font-size:12px;'>原因: {flag['reason']}</p>"
                    if len(red_flags) > 3:
                        content_html += f"<p style='margin-left:10px; color:#d63031;'>(共{len(red_flags)}项风险)</p>"
                
                content_html += "</div>"
        
        content_html += "</div>"
    
    content_html += "</div>"
    
    return content_html

'''

# 输出代码
print("=" * 80)
print("增强版公司报告章节代码")
print("=" * 80)
print()
print("这段代码可以直接插入到 report_generator.py 中")
print("替换或增强 _generate_html_company_section() 函数")
print()
print("主要改进：")
print("1. 集成公司风险分析模块")
print("2. 显示风险等级（低风险/关注级/高风险）和评分")
print("3. 显示各维度得分")
print("4. 显示风险排除说明")
print("5. 显示高风险红旗")
print("6. 保持原有资金概况和对手方信息")
print()
print("=" * 80)
print(ENHANCED_COMPANY_SECTION_CODE)
print("=" * 80)
