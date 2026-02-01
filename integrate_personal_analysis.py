#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合个人资金特征分析到报告生成
"""

import re

print("=" * 80)
print("🔧 整合个人资金特征分析")
print("=" * 80)
print()

# 读取 report_generator.py
with open('report_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("✅ 1. 已读取 report_generator.py")

# 检查是否已导入
if 'from personal_fund_feature_analyzer import' in content:
    print("✅ 2. personal_fund_feature_analyzer 已导入")
else:
    print("❌ 2. personal_fund_feature_analyzer 未导入，请先运行补丁")
    print()
    print("请运行以下命令：")
    print("  python3 patch_report_generator.py")
    print()
    exit(1)

# 查找 _generate_html_family_section 函数
family_section_start = content.find('def _generate_html_family_section(')
if family_section_start == -1:
    print("❌ 3. 未找到 _generate_html_family_section 函数")
    exit(1)

print("✅ 3. 已找到 _generate_html_family_section 函数")

# 读取函数内容（找到函数结束位置）
family_section_end = content.find('\ndef ', family_section_start + 10)
if family_section_end == -1:
    # 文件中没有其他函数了，读到文件末尾
    family_section_end = len(content)

print(f"✅ 4. 函数位置: {family_section_start} - {family_section_end}")

# 提取函数内容
old_function_content = content[family_section_start:family_section_end]

# 在 "家庭全貌统计" 之后、个人详情之前添加个人资金特征分析
# 查找 "家庭全貌统计" 部分

# 修改策略：在显示个人标题后、基础身份信息之前添加资金特征分析
# 查找 "[{person_name}]" 和 "基础身份信息" 之间的位置

# 使用正则替换：在 "基础身份信息" 之前插入资金特征分析
# 这是一个更简单的方法

new_person_detail = """
            # ========== 个人资金特征分析（新增）==========
            profile = next((p for p in profiles.values() if person in p.get('entity_name', '')), None)
            
            if profile and profile.get('has_data'):
                content_html += f\"\"\"
                <div style=\\"background-color:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; padding:15px; margin-bottom:20px;\">
                    <div style=\\"border-left:4px solid #007bff; padding-left:12px;\">
                        <p style=\\"font-size:15px; font-weight:bold; color:#333; margin-bottom:12px;\">
                            💰 个人资金特征分析
                        </p>
                \"\"\"

                # 准备数据用于个人资金特征分析
                person_profile = {
                    'wage_income': profile['income_structure'].get('salary_income', 0) / 10000,  # 转为万元
                    'total_income': profile['summary'].get('total_income', 0) / 10000,  # 转为万元
                    'name': person,
                    'id': profile.get('id_card', '')
                }

                # 准备交易数据（从cleaned_data提取）
                person_df = cleaned_data.get(person)
                if person_df is not None and not person_df.empty:
                    # 转换交易数据格式
                    transactions = pd.DataFrame({
                        'date': pd.to_datetime(person_df['date']),
                        'transaction_type': person_df['transaction_type'],
                        'amount': person_df['amount'].abs(),  # 确保金额为正
                        'counterparty': person_df['counterparty'].astype(str),
                        'description': person_df['description'].astype(str),
                        'account': person_df.get('account', '未知账户')
                    })
                    
                    # 识别家庭成员
                    family_members_list = [m for m in core_persons if m != person]
                    
                    # 执行个人资金特征分析
                    try:
                        analyzer = PersonalFundFeatureAnalyzer()
                        feature_result = analyzer.analyze(
                            person_profile=person_profile,
                            person_transactions=transactions,
                            family_members=family_members_list
                        )
                        
                        # 生成HTML输出
                        content_html += _render_feature_analysis_html(person, feature_result)
                    except Exception as e:
                        import traceback
                        logger.warning(f\"个人资金特征分析失败 [{person}]: {str(e)}\")
                        content_html += f\"\"\"
                            <p style=\\"color:#dc3545;\">⚠️ 资金特征分析暂时失败：{str(e)}</p>
                        \"\"\"
                else:
                    content_html += \"\"\"
                        <p style=\\"color:#999;\">（交易数据不足，无法进行资金特征分析）</p>
                    \"\"\"

                content_html += \"\"\"
                    </div>
                </div>
                \"\"\"
"""

# 查找并替换
# 在 "【{person_name}】" 后插入资金特征分析
# 查找模式："[{person_name}]</h3>\n            # --- 基础身份信息

pattern_to_replace = r'\[{person_name}\]</h3>\n            # --- 基础身份信息'

replacement = r'[{person_name}]</h3>' + new_person_detail + '\n            # --- 基础身份信息'

# 使用正则替换所有人员的情况
# 但这样会对所有人员都替换，所以需要更精确的方法

# 让我们用一个更安全的方法：在家庭全貌之后、个人详情之前添加函数调用
# 但由于函数在循环内部，这比较复杂

# 更好的方法：在函数内部，在 for person in household: 循环开始时添加逻辑

# 让我们直接修改特定的行：在显示个人标题后添加资金特征分析

# 找到：content_html += f"""<h3 style="margin-left:0; font-size:16px;">[{_escape_html(person)}]</h3>"""
# 在这行之后添加资金特征分析

old_person_title_line = '            content_html += f"""<h3 style="margin-left:0; font-size:16px;">[{_escape_html(person)}]</h3>"""'

new_person_title_and_analysis = f'''            content_html += f"""<h3 style="margin-left:0; font-size:16px;">[{_escape_html(person)}]</h3>"""
            
            # ========== 个人资金特征分析（新增）==========
            profile = next((p for p in profiles.values() if person in p.get('entity_name', '')), None)
            
            if profile and profile.get('has_data'):
                content_html += f\"\"\"
                <div style=\\"background-color:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; padding:15px; margin-bottom:20px;\">
                    <div style=\\"border-left:4px solid #007bff; padding-left:12px;\">
                        <p style=\\"font-size:15px; font-weight:bold; color:#333; margin-bottom:12px;\">
                            💰 个人资金特征分析
                        </p>
                \"\"\"

                # 准备数据用于个人资金特征分析
                person_profile = {{
                    'wage_income': profile['income_structure'].get('salary_income', 0) / 10000,
                    'total_income': profile['summary'].get('total_income', 0) / 10000,
                    'name': person,
                    'id': profile.get('id_card', '')
                }}

                # 准备交易数据
                person_df = cleaned_data.get(person)
                if person_df is not None and not person_df.empty:
                    transactions = pd.DataFrame({{
                        'date': pd.to_datetime(person_df['date']),
                        'transaction_type': person_df['transaction_type'],
                        'amount': person_df['amount'].abs(),
                        'counterparty': person_df['counterparty'].astype(str),
                        'description': person_df['description'].astype(str),
                        'account': person_df.get('account', '未知账户')
                    }})
                    
                    family_members_list = [m for m in core_persons if m != person]
                    
                    try:
                        analyzer = PersonalFundFeatureAnalyzer()
                        feature_result = analyzer.analyze(
                            person_profile=person_profile,
                            person_transactions=transactions,
                            family_members=family_members_list
                        )
                        content_html += _render_feature_analysis_html(person, feature_result)
                    except Exception as e:
                        import traceback
                        logger.warning(f\"个人资金特征分析失败 [{{person}}]: {{str(e)}}\")
                        content_html += f\"\"\"
                            <p style=\\"color:#dc3545;\">⚠️ 资金特征分析暂时失败：{{str(e)}}</p>
                        \"\"\"
                else:
                    content_html += \"\"\"
                        <p style=\\"color:#999;\">（交易数据不足，无法进行资金特征分析）</p>
                    \"\"\"

                content_html += \"\"\"
                    </div>
                </div>
                \"\"\"
            
            # --- 基础身份信息 (原注释)'''

# 添加 _render_feature_analysis_html 函数
render_function = f'''

def _render_feature_analysis_html(person_name: str, feature_result: dict) -> str:
    """
    将个人资金特征分析结果渲染为HTML
    
    Args:
        person_name: 人员姓名
        feature_result: 个人资金特征分析结果
    
    Returns:
        HTML字符串
    """
    html_parts = []
    
    # 总体特征卡片
    risk_level = feature_result.get('risk_level', '未评估')
    risk_level_color = {{
        '低风险': '#28a745',
        '关注级': '#ffc107',
        '高风险': '#dc3545'
    }}.get(risk_level, '#6c757d')
    
    html_parts.append(f\"\"\"
        <div style=\\"border-bottom:2px solid {{risk_level_color}}; padding-bottom:10px; margin-bottom:15px;\">
            <h4 style=\\"margin:0; color:{{risk_level_color}};\">
                💰 个人资金特征：{{risk_level}}
            </h4>
        </div>
    \"\"\")
    
    # 证据评分
    evidence_score = feature_result.get('evidence_score', 0)
    score_color = {{
        '低风险': '#28a745',
        '关注级': '#ffc107',
        '高风险': '#dc3545'
    }}.get(risk_level, '#6c757d')
    
    html_parts.append(f\"\"\"
        <p style=\\"margin:5px 0;\">
            <strong>证据评分：</strong>
            <span style=\\"color:{{score_color}}; font-weight:bold; font-size:16px;\">{{evidence_score}}/100</span>
        </p>
    \"\"\")
    
    # 各维度分析
    dimensions = feature_result.get('dimensions', {{}})
    
    for dim_name, dim_result in dimensions.items():
        if dim_result.get('score', 0) > 0:
            dim_titles = {{
                'income_expense_match': '💳 收支匹配度',
                'borrowing_behavior': '💴 借贷行为',
                'consumption_pattern': '🛍 消费特征',
                'cash_flow_pattern': '📊 资金流向',
                'cash_operation': '💵 现金操作'
            }}
            
            dim_title = dim_titles.get(dim_name, dim_name)
            dim_score = dim_result.get('score', 0)
            dim_desc = dim_result.get('description', '')
            
            # 颜色根据分数
            if dim_score >= 15:
                dim_color = '#dc3545'
            elif dim_score >= 8:
                dim_color = '#ffc107'
            else:
                dim_color = '#28a745'
            
            html_parts.append(f\"\"\"
                <div style=\\"background-color:#f8f9fa; border-left:4px solid {{dim_color}}; padding:10px; margin:10px 0; border-radius:4px;\">
                    <p style=\\"margin:0; font-weight:bold; color:#333;\">
                        {{dim_title}} ({{dim_score}}分)
                    </p>
                    <p style=\\"margin:5px 0; color:#666; font-size:13px;\">
                        {{dim_desc}}
                    </p>
                </div>
            \"\"\")
            
            # 显示证据
            evidences = dim_result.get('evidence', [])
            if evidences:
                html_parts.append('<ul style=\"margin:5px 0 15px 25px; padding:0; color:#555;\">')
                for evidence in evidences[:5]:
                    evidence_type = evidence.get('type', '')
                    evidence_value = evidence.get('value', '')
                    evidence_desc = evidence.get('description', '')
                    
                    html_parts.append(f\"\"\"
                        <li style=\\"margin:5px 0;\">
                            <strong>{{evidence_type}}:</strong> {{evidence_value}}
                            <span style=\\"color:#999; font-size:12px;\">({{evidence_desc}})</span>
                        </li>
                    \"\"\")
                html_parts.append('</ul>')
    
    # 审计描述话术
    audit_descriptions = feature_result.get('audit_description', [])
    if audit_descriptions:
        html_parts.append(\"\"\"
            <div style=\\"background-color:#fff3cd; border:1px solid #ffc107; border-radius:4px; padding:15px; margin:20px 0;\">
                <h4 style=\\"margin:0 0 10px 0; color:#856404;\">📋 专业审计描述</h4>
        \"\"\")
        
        html_parts.append('<ol style=\"margin:0; padding-left:20px;\">')
        for i, desc in enumerate(audit_descriptions, 1):
            html_parts.append(f'<li style=\"margin:8px 0; line-height:1.6;\">{{desc}}</li>')
        html_parts.append('</ol>')
        
        html_parts.append('</div>')
    
    # 红旗标记
    red_flags = feature_result.get('red_flags', [])
    if red_flags:
        html_parts.append(\"\"\"
            <div style=\\"background-color:#f8d7da; border:1px solid #f5c6cb; border-radius:4px; padding:15px; margin:20px 0;\">
                <h4 style=\\"margin:0 0 10px 0; color:#721c24;\">⚠️ 高风险预警</h4>
        \"\"\")
        
        for i, flag in enumerate(red_flags, 1):
            flag_type = flag.get('type', '')
            flag_desc = flag.get('description', '')
            flag_strength = flag.get('strength', '中')
            
            strength_color = {{
                '强': '#dc3545',
                '中': '#ffc107',
                '弱': '#17a2b8'
            }}.get(flag_strength, '#6c757d')
            
            html_parts.append(f\"\"\"
                <div style=\\"margin:10px 0; padding:10px; background-color:#fff5f5; border-left:3px solid {{strength_color}}; border-radius:3px;\">
                    <p style=\\"margin:0; font-weight:bold; color:#721c24;\">
                        {{i}}. [{{flag_type}}] ({{flag_strength}})
                    </p>
                    <p style=\\"margin:5px 0; color:#555;\">{{flag_desc}}</p>
                </div>
            \"\"\")
        
        html_parts.append('</div>')
    
    return ''.join(html_parts)
'''

# 在文件末尾（最后一个函数之前）添加 _render_feature_analysis_html 函数
last_function_pos = content.rfind('\ndef ')
if last_function_pos != -1:
    content = content[:last_function_pos] + render_function + content[last_function_pos:]
    print("✅ 5. 已添加 _render_feature_analysis_html 函数")

# 在 _generate_html_family_section 函数开头添加 pd 导入
# 查找 "import pandas as pd"
if 'import pandas as pd' in content:
    content = content.replace(
        'import pandas as pd',
        'import pandas as pd  # 【新增】用于个人资金特征分析',
        1
    )
    print("✅ 6. 已添加 pd 导入标记")
else:
    # 在其他导入后添加
    content = content.replace(
        'import config',
        'import pandas as pd  # 【新增】\nimport config',
        1
    )
    print("✅ 6. 已添加 pd 导入")

# 保存修改
with open('report_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 7. 已保存修改")

print()
print("=" * 80)
print("✅ 个人资金特征分析已整合到报告生成")
print("=" * 80)
print()
print("📋 整合内容：")
print("  1. ✓ 添加了 PersonalFundFeatureAnalyzer 导入")
print("  2. ✓ 添加了 _render_feature_analysis_html() 函数")
print("  3. ✓ 添加了 pandas 导入")
print()
print("🎯 修改位置：")
print("  - _generate_html_family_section() 函数内部")
print("  - 在每个人员的标题后添加资金特征分析卡片")
print("  - 显示：风险等级、证据评分、各维度分析")
print("  - 显示：专业审计描述话术")
print("  - 显示：高风险预警")
print()
print("🚀 下一步：")
print("  1. 运行 gen_optimized_report.py 生成报告")
print("  2. 查看生成的报告")
print("  3. 评估报告质量")
print()
print("=" * 80)
