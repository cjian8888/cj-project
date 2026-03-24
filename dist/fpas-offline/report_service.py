#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告数据服务模块 - 初查报告生成引擎

【数据复用铁律】详见 docs/data_processing_principle.md
1. 按优先级从三个数据源获取数据:
   - 优先级1: output/cleaned_data/ - 标准化银行流水
   - 优先级2: output/analysis_cache/ - JSON缓存（程序首选）
   - 优先级3: output/analysis_results/资金核查底稿.xlsx - Excel核查底稿（回退）
2. 严禁读取原始数据目录 (data/国监查XXX) 进行重复计算
3. JSON缓存优先，Excel作为补充数据源
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import utils

logger = utils.setup_logger(__name__)


# ==================== 公文排版 HTML 模板 ====================

OFFICIAL_REPORT_CSS = """
<style>
    @page {
        size: A4;
        margin: 25mm 20mm;
    }
    
    body {
        font-family: 'FangSong', 'STFangSong', '仿宋', serif;
        font-size: 16pt;
        line-height: 1.8;
        color: #000;
        background-color: #f3f4f6;
        margin: 0;
        padding: 20px;
    }
    
    .a4-page {
        width: 210mm;
        min-height: 297mm;
        margin: 0 auto 20px auto;
        padding: 25mm 20mm;
        background-color: white;
        box-shadow: 0 0 15px rgba(0,0,0,0.1);
        box-sizing: border-box;
    }
    
    /* 一级标题：黑体 二号 居中 */
    h1 {
        font-family: 'SimHei', 'STHeiti', '黑体', sans-serif;
        font-size: 22pt;
        font-weight: bold;
        text-align: center;
        margin-bottom: 30px;
        letter-spacing: 2px;
    }
    
    /* 二级标题：楷体/黑体 三号 加粗 */
    h2 {
        font-family: 'KaiTi', 'STKaiti', '楷体', serif;
        font-size: 16pt;
        font-weight: bold;
        margin-top: 25px;
        margin-bottom: 15px;
        border-bottom: 1px solid #333;
        padding-bottom: 5px;
    }
    
    /* 三级标题 */
    h3 {
        font-family: 'SimHei', '黑体', sans-serif;
        font-size: 14pt;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    
    /* 正文：仿宋 三号/四号 */
    p {
        text-indent: 2em;
        margin-bottom: 12px;
        text-align: justify;
    }
    
    /* 数字/英文：Times New Roman */
    .number {
        font-family: 'Times New Roman', serif;
    }
    
    /* 表格样式 */
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
        font-size: 12pt;
    }
    
    th, td {
        border: 1px solid #000;
        padding: 8px 10px;
        text-align: center;
    }
    
    th {
        background-color: #f2f2f2;
        font-weight: bold;
        font-family: 'SimHei', '黑体', sans-serif;
    }
    
    /* 高亮风险项 */
    .highlight-risk {
        color: #c00;
        font-weight: bold;
    }
    
    .highlight-warning {
        color: #f90;
    }
    
    /* 红头文件样式 */
    .red-header {
        color: #c00;
        font-size: 28pt;
        font-weight: bold;
        text-align: center;
        border-bottom: 3px solid #c00;
        padding-bottom: 10px;
        margin-bottom: 20px;
        letter-spacing: 8px;
    }
    
    .doc-number {
        text-align: center;
        font-size: 14pt;
        margin-bottom: 20px;
    }
    
    /* 结论区域 */
    .conclusion {
        background-color: #fff9e6;
        border-left: 4px solid #f90;
        padding: 15px 20px;
        margin: 20px 0;
    }
    
    .suggestion {
        background-color: #e6f7ff;
        border-left: 4px solid #1890ff;
        padding: 15px 20px;
        margin: 20px 0;
    }
    
    /* ========== 新增样式 ========== */
    
    /* 风险标签 */
    .risk-tag {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.9em;
        font-weight: bold;
        color: white;
    }
    .risk-high { background-color: #e74c3c; }
    .risk-medium { background-color: #f39c12; }
    .risk-low { background-color: #27ae60; }
    
    /* 资产卡片 */
    .asset-summary {
        display: flex;
        justify-content: space-between;
        margin-bottom: 20px;
        flex-wrap: wrap;
    }
    .asset-card {
        flex: 1;
        min-width: 150px;
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px;
        margin-right: 15px;
        border-radius: 8px;
        text-align: center;
    }
    .asset-card:last-child { margin-right: 0; }
    .asset-value { font-size: 1.4em; font-weight: bold; color: #2c3e50; margin-top: 5px; }
    .asset-label { color: #7f8c8d; font-size: 0.9em; }

    /* 打印适配 */
    @media print {
        body {
            background-color: white;
            padding: 0;
        }
        .a4-page {
            box-shadow: none;
            margin: 0;
            page-break-after: always;
        }
        .no-print {
            display: none;
        }
        table {
            page-break-inside: avoid;
        }
        .asset-card {
            border: 1px solid #ccc;
        }
    }
</style>
"""


class ReportDataBuilder:
    """
    初查报告数据构建器 - 复用已有分析结果
    
    【数据复用铁律】详见 docs/data_processing_principle.md
    按优先级从三个数据源获取: cleaned_data → analysis_cache → 核查底稿Excel
    """
    
    def __init__(self, analysis_cache: Dict):
        """
        初始化时接收已有的分析缓存
        
        Args:
            analysis_cache: 由 api_server.py 的 _load_analysis_cache() 加载的完整结果
        """
        self.profiles = analysis_cache.get('profiles', {})
        self.suspicions = analysis_cache.get('suspicions', {})
        self.analysis_results = analysis_cache.get('analysisResults', {})
        self.graph_data = analysis_cache.get('graphData', {})
        self.persons = analysis_cache.get('persons', [])
        self.companies = analysis_cache.get('companies', [])
        self._meta = analysis_cache.get('_meta', {})
        
        logger.info(f"[ReportDataBuilder] 初始化完成: {len(self.persons)} 人员, {len(self.companies)} 企业")
    
    def get_available_subjects(self) -> List[Dict]:
        """
        获取可选嫌疑人列表（从缓存中读取）
        
        Returns:
            嫌疑人列表，包含名称、类型和基本信息
        """
        subjects = []
        
        # 添加个人
        for person in self.persons:
            profile = self.profiles.get(person, {})
            summary = profile.get('summary', {})
            
            subjects.append({
                'name': person,
                'type': 'person',
                'transactionCount': summary.get('transaction_count', 0),
                'totalIncome': summary.get('total_income', 0),
                'totalExpense': summary.get('total_expense', 0),
                'salaryRatio': summary.get('salary_ratio', 0),
            })
        
        # 添加企业
        for company in self.companies:
            profile = self.profiles.get(company, {})
            summary = profile.get('summary', {})
            
            subjects.append({
                'name': company,
                'type': 'company',
                'transactionCount': summary.get('transaction_count', 0),
                'totalIncome': summary.get('total_income', 0),
                'totalExpense': summary.get('total_expense', 0),
            })
        
        return subjects
    
    def build_person_report(self, person: str) -> Dict:
        """
        构建个人分析数据 - 100%复用缓存 (适配 profiles.json 扁平化结构)
        
        Args:
            person: 人员名称
            
        Returns:
            个人分析数据字典
        """
        profile = self.profiles.get(person, {})
        
        # 检查是否有数据 (使用扁平化后的 camelCase 键)
        if not profile or (profile.get('transactionCount', 0) == 0 and profile.get('totalIncome', 0) == 0):
            return {'name': person, 'has_data': False}
        
        # 提取概要信息 (直接从顶层获取)
        total_income = profile.get('totalIncome', 0)
        total_expense = profile.get('totalExpense', 0)
        transaction_count = profile.get('transactionCount', 0)
        salary_ratio = profile.get('salaryRatio', 0)
        large_cash_count = profile.get('cashIncomeCount', 0) + profile.get('cashExpenseCount', 0)
        
        # 提取资产信息
        vehicles = profile.get('vehicles', [])
        properties = profile.get('properties_precise', []) # 扁平化缓存可能使用此前缀
        
        # 提取理财 (扁平化后的键名需确认，若未保留则给空值或从 summary 尝试获取)
        wealth_holding = profile.get('wealthTotal', 0)
        
        # 计算收入匹配度风险话术
        income_risk_text = None
        if salary_ratio < 0.5:
            income_risk_text = f"正常收入占比仅为{salary_ratio*100:.1f}%，不足以支撑消费，存在资金来源不明嫌疑"
        
        # 获取相关借贷分析结果
        loan_results = self.analysis_results.get('loan', {})
        person_loans = self._filter_by_person(loan_results, person)
        
        # 获取相关收入异常分析结果
        income_results = self.analysis_results.get('income', {})
        person_income_issues = self._filter_by_person(income_results, person)
        
        # 获取相关可疑交易
        suspicions = {}
        if self.suspicions:
            suspicions['direct_transfers'] = [t for t in self.suspicions.get('direct_transfers', []) if t.get('person') == person]
            suspicions['cash_collisions'] = [t for t in self.suspicions.get('cash_collisions', []) if t.get('person_a') == person or t.get('person_b') == person]
        
        return {
            'name': person,
            'type': 'person',
            'has_data': True,
            'summary': {
                'transactionCount': transaction_count,
                'totalIncome': total_income,
                'totalExpense': total_expense,
                'transactionCount': transaction_count,
                'salaryRatio': salary_ratio,
                'largeCashCount': large_cash_count,
            },
            'incomeRiskText': income_risk_text,
            'assets': {
                'bank_card_count': len(profile.get('bank_accounts_official', [])),
                'properties': properties,
                'vehicles': vehicles,
                'wealth_holding': wealth_holding,
                'accounts': profile.get('bank_accounts_official', [])[:5]
            },
            'loanAnalysis': person_loans,
            'incomeIssues': person_income_issues,
            'suspicions': suspicions
        }
    
    def _filter_by_person(self, results: Dict, person: str) -> Dict:
        """过滤指定人员的分析结果"""
        filtered = {}
        for key, items in results.items():
            if isinstance(items, list):
                filtered[key] = [
                    item for item in items 
                    if item.get('person') == person or item.get('entity') == person
                ]
        return filtered
    
    def _is_company(self, name: str) -> bool:
        """判断是否为公司（通过 companies 列表判断）"""
        return name in self.companies
    
    def build_company_report(self, company: str) -> Dict:
        """
        构建公司分析数据 (适配 profiles.json 扁平化结构)
        """
        profile = self.profiles.get(company, {})
        # 检查是否有数据
        if not profile or (profile.get('transactionCount', 0) == 0 and profile.get('totalIncome', 0) == 0):
            return {'name': company, 'has_data': False}
            
        # 提取概要信息 (扁平结构)
        total_income = profile.get('totalIncome', 0)
        total_expense = profile.get('totalExpense', 0)
        transaction_count = profile.get('transactionCount', 0)
        net_flow = total_income - total_expense
        
        # 提取大额现金 (缓存中可能以 cashTransactions 存在)
        cash_transactions = profile.get('cashTransactions', [])
        
        # 获取相关可疑交易
        suspicions = {}
        if self.suspicions:
            suspicions['direct_transfers'] = [
                t for t in self.suspicions.get('direct_transfers', []) 
                if t.get('person') == company or t.get('company') == company
            ]
            
        return {
            'name': company,
            'type': 'company',
            'has_data': True,
            'summary': {
                'transactionCount': transaction_count,
                'totalIncome': total_income,
                'totalExpense': total_expense,
                'netFlow': net_flow,
                'largeCashCount': len(cash_transactions),
            },
            'largeCash': {
                'totalAmount': sum(t.get('amount', 0) for t in cash_transactions) if cash_transactions else 0,
                'count': len(cash_transactions),
                'transactions': cash_transactions[:10],
            },
            'suspicions': suspicions
        }

    def generate_html_report(
        self, 
        subjects: List[str],
        case_name: str = "初查报告",
        doc_number: str = None,
        include_assets: bool = True,
        include_income: bool = True,
        include_loan: bool = True,
    ) -> str:
        """
        生成公文格式 HTML 报告 (V2.0 区分公司/个人)
        """
        if not doc_number:
            doc_number = f"国监查 [{datetime.now().year}] 第 {datetime.now().strftime('%Y%m%d%H%M')} 号"
        
        # 1. 准备数据模块
        report_sections = []
        
        for idx, subject in enumerate(subjects, 1):
            # 判断是个人还是公司
            is_company = self._is_company(subject)
            
            if is_company:
                # === 公司模板 ===
                comp_data = self.build_company_report(subject)
                
                if not comp_data.get('has_data'):
                     html = f"""
            <h2>{self._num_to_chinese(idx + 1)}、{subject}（无有效数据）</h2>
            <p>未查见该公司的有效交易记录。</p>
            """
                     report_sections.append(html)
                     continue
                
                summary = comp_data.get('summary', {})
                
                # 公司基本概况
                html = f"""
            <h2>{self._num_to_chinese(idx + 1)}、{subject} 资金核查情况</h2>
            
            <h3>（一）资金概览</h3>
            <table>
                <tr>
                    <th>指标</th>
                    <th>数值</th>
                    <th>备注</th>
                </tr>
                <tr>
                    <td>交易笔数</td>
                    <td class="number">{summary.get('transactionCount', 0):,}</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>资金流入总额</td>
                    <td class="number">¥{summary.get('totalIncome', 0)/10000:,.2f} 万元</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>资金流出总额</td>
                    <td class="number">¥{summary.get('totalExpense', 0)/10000:,.2f} 万元</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>资金净流量</td>
                    <td class="number">¥{summary.get('netFlow', 0)/10000:,.2f} 万元</td>
                    <td>{'净流入' if summary.get('netFlow', 0) > 0 else '净流出'}</td>
                </tr>
                <tr>
                    <td>大额现金笔数</td>
                    <td class="number">{summary.get('largeCashCount', 0)}</td>
                    <td>{'需核实' if summary.get('largeCashCount', 0) > 0 else '-'}</td>
                </tr>
            </table>
            """
                
                # 公司风险分析
                suspicions = comp_data.get('suspicions', {})
                direct_transfers = suspicions.get('direct_transfers', [])
                
                if direct_transfers:
                    html += """<h3>（二）风险预警</h3><p><strong>发现与核心人员存在直接资金往来：</strong></p><ul>"""
                    for t in direct_transfers:
                          html += f"""<li>{t.get('date')[:10]} 与 <strong>{t.get('person')}</strong> {t.get('direction')} {t.get('amount'):,} 元。</li>"""
                    html += "</ul>"
                else:
                    html += """<h3>（二）风险预警</h3><p>未发现与核心人员的直接资金往来。</p>"""
                
                report_sections.append(html)

            else:
                # === 个人模板 ===
                person_data = self.build_person_report(subject)
                
                if not person_data.get('has_data'):
                    html = f"""
            <h2>{self._num_to_chinese(idx + 1)}、{subject}（无有效数据）</h2>
            <p>未查见该人员的有效交易记录。</p>
            """
                    report_sections.append(html)
                    continue
                
                summary = person_data.get('summary', {})
                
                html = f"""
            <h2>{self._num_to_chinese(idx + 1)}、{subject} 资金核查情况</h2>
            
            <h3>（一）资金概览</h3>
            <table>
                <tr>
                    <th>指标</th>
                    <th>数值</th>
                    <th>备注</th>
                </tr>
                <tr>
                    <td>交易笔数</td>
                    <td class="number">{summary.get('transactionCount', 0):,}</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>资金流入总额</td>
                    <td class="number">¥{summary.get('totalIncome', 0)/10000:,.2f} 万元</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>资金流出总额</td>
                    <td class="number">¥{summary.get('totalExpense', 0)/10000:,.2f} 万元</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>工资性收入占比</td>
                    <td class="number {' highlight-risk' if summary.get('salaryRatio', 0) < 0.5 else ''}">{summary.get('salaryRatio', 0)*100:.1f}%</td>
                    <td>{'⚠ 低于50%' if summary.get('salaryRatio', 0) < 0.5 else '正常'}</td>
                </tr>
                <tr>
                    <td>大额现金笔数</td>
                    <td class="number">{summary.get('largeCashCount', 0)}</td>
                    <td>{'需核实' if summary.get('largeCashCount', 0) > 5 else '-'}</td>
                </tr>
            </table>
            """
                
                # 收入风险提示
                if person_data.get('incomeRiskText'):
                    html += f"""
            <div class="conclusion">
                <strong>⚠ 收入匹配度分析：</strong>{person_data.get('incomeRiskText')}
            </div>
            """
                
                # --- 资产状况 ---
                assets = person_data.get('assets', {})
                html += f"""
            <h3>（二）资产状况</h3>
            <div class="asset-summary">
                <div class="asset-card">
                    <div class="asset-label">银行卡(张)</div>
                    <div class="asset-value">{assets.get('bank_card_count', 0)}</div>
                </div>
                <div class="asset-card">
                    <div class="asset-label">房产(套)</div>
                    <div class="asset-value">{len(assets.get('properties', []))} <span style="font-size:12px;color:#999">(待补充)</span></div>
                </div>
                <div class="asset-card">
                    <div class="asset-label">车辆(辆)</div>
                    <div class="asset-value">{len(assets.get('vehicles', []))} <span style="font-size:12px;color:#999">(待补充)</span></div>
                </div>
                <div class="asset-card">
                    <div class="asset-label">理财持仓(万元)</div>
                    <div class="asset-value">{assets.get('wealth_holding', 0)/10000:.2f}</div>
                </div>
            </div>
            """
                # 银行卡列表 (Top 5)
                if assets.get('accounts'):
                    html += """
            <p><strong>1. 主要活跃银行账户</strong></p>
            <table>
                <tr>
                    <th>账号</th>
                    <th>开户行</th>
                    <th>总收入(万元)</th>
                    <th>总支出(万元)</th>
                </tr>
            """
                    for acc in assets.get('accounts', [])[:5]:
                        html += f"""
                <tr>
                    <td>{acc.get('account_number')}</td>
                    <td>{acc.get('bank_name', '-')}</td>
                    <td class="number">{acc.get('total_income', 0)/10000:.2f}</td>
                    <td class="number">{acc.get('total_expense', 0)/10000:.2f}</td>
                </tr>
            """
                    html += "        </table>\n"

                # 房产列表 (Placeholder if empty)
                html += """<p><strong>2. 名下房产信息</strong> <span style="color:#999;font-size:0.9em;">(需接入不动产登记系统)</span></p>"""
                if assets.get('properties'):
                     # Existing logic
                     pass
                else: 
                     html += """<p style="text-indent:2em; color:#999;">暂无系统登记数据。</p>"""


                # --- 异常资金分析 ---
                html += """
            <h3>（三）异常资金分析</h3>
            """
                loan_analysis = person_data.get('loanAnalysis', {})
                income_issues = person_data.get('incomeIssues', {})
                suspicions = person_data.get('suspicions', {})
                
                has_anomaly = False
                
                # 1. 借贷分析
                bidirectional = loan_analysis.get('bidirectional_flows', [])
                if bidirectional:
                    has_anomaly = True
                    html += """
            <p><strong>1. 疑似民间借贷（双向频繁往来）</strong></p>
            <table>
                <tr>
                    <th>对手方</th>
                    <th>借入(万元)</th>
                    <th>偿还(万元)</th>
                    <th>风险等级</th>
                </tr>
            """
                    for item in bidirectional:
                         html += f"""
                <tr>
                    <td>{item.get('counterparty')}</td>
                    <td class="number">{item.get('income_total', 0)/10000:.2f}</td>
                    <td class="number">{item.get('expense_total', 0)/10000:.2f}</td>
                    <td><span class="risk-tag risk-{item.get('risk_level', 'low')}">{item.get('risk_level', 'normal').upper()}</span></td>
                </tr>
            """
                    html += "        </table>\n"

                # 2. 异常收入
                regular_income = income_issues.get('regular_non_salary', [])
                if regular_income:
                    has_anomaly = True
                    html += """
            <p><strong>2. 异常来源收入（规律性非工资）</strong></p>
            <table>
                <tr>
                    <th>来源方</th>
                    <th>总金额(万元)</th>
                    <th>月均(万元)</th>
                    <th>判定依据</th>
                </tr>
            """
                    for item in regular_income:
                        html += f"""
                <tr>
                    <td>{item.get('counterparty')}</td>
                    <td class="number">{item.get('total_amount', 0)/10000:.2f}</td>
                    <td class="number">{item.get('avg_amount', 0)/10000:.2f}</td>
                    <td>{item.get('income_type', '-')}</td>
                </tr>
            """
                    html += "        </table>\n"

                # 3. 风险预警 (利益输送/现金)
                direct_transfers = suspicions.get('direct_transfers', [])
                if direct_transfers:
                    has_anomaly = True
                    html += """
            <p><strong>3. 重点风险预警（直接利益输送/现金伴随）</strong></p>
            <table>
                <tr>
                    <th>日期</th>
                    <th>对手方</th>
                    <th>类型</th>
                    <th>金额(元)</th>
                </tr>
            """
                    for t in direct_transfers:
                        html += f"""
                <tr>
                    <td>{t.get('date')[:10]}</td>
                    <td>{t.get('counterparty', t.get('company'))}</td>
                    <td>{t.get('direction', '转账')}</td>
                    <td class="number">{t.get('amount', 0):,.2f}</td>
                </tr>
            """
                    html += "        </table>\n"

                if not has_anomaly:
                    html += "<p>未发现显著的异常资金往来特征。</p>"
                
                report_sections.append(html)
        
        # 2. 组装整体报告
        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{case_name}</title>
    {OFFICIAL_REPORT_CSS}
</head>
<body>
    <div class="a4-page">
        <div class="doc-number">{doc_number}</div>
        <h1>{case_name}</h1>
        
        <h2>一、案源及核查范围</h2>
        <p>依据相关线索，对以下 <span class="number">{len(subjects)}</span> 名人员/公司进行资金穿透核查：
        <strong>{', '.join(subjects)}</strong>。</p>
        <p>数据范围：本次核查基于银行流水等金融数据，分析时间覆盖全部交易记录。</p>
        
        <!-- 报告部分 -->
        {''.join(report_sections)}

        <h2>{self._num_to_chinese(len(subjects) + 2)}、综合研判与建议</h2>
        
        <div class="conclusion">
            <strong>研判意见：</strong>
            <p>经对上述 {len(subjects)} 个主体资金流水进行穿透分析，建议关注资金来源不明及大额现金交易风险。</p>
        </div>
        
        <div class="suggestion">
            <strong>下一步工作建议：</strong>
            <ol>
                <li>调取相关银行凭证原件进行核对</li>
                <li>对收入来源不明的资金进行约谈核实</li>
                <li>核查大额现金交易的真实用途</li>
            </ol>
        </div>
        
        <div style="margin-top: 80px; text-align: right;">
            <p>报告生成时间：<span class="number">{datetime.now().strftime('%Y年%m月%d日')}</span></p>
        </div>
    </div>
</body>
</html>
"""
        return full_html

    def _num_to_chinese(self, num: int) -> str:
        """数字转中文"""
        chinese_nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
                        '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十']
        if 0 <= num < len(chinese_nums):
            return chinese_nums[num]
        return str(num)


def load_report_builder(output_dir: str = './output') -> Optional[ReportDataBuilder]:
    """
    加载报告数据构建器
    
    从 analysis_cache 加载已有分析结果并创建 ReportDataBuilder 实例
    
    Args:
        output_dir: 输出目录路径
        
    Returns:
        ReportDataBuilder 实例，如果缓存不存在则返回 None
    """
    cache_dir = os.path.join(output_dir, 'analysis_cache')
    
    if not os.path.exists(cache_dir):
        logger.warning(f"分析缓存目录不存在: {cache_dir}")
        return None
    
    try:
        # 加载各个缓存文件
        profiles = {}
        suspicions = {}
        analysis_results = {}
        graph_data = None
        metadata = {}
        
        metadata_path = os.path.join(cache_dir, 'metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        
        profiles_path = os.path.join(cache_dir, 'profiles.json')
        if os.path.exists(profiles_path):
            with open(profiles_path, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
        
        suspicions_path = os.path.join(cache_dir, 'suspicions.json')
        if os.path.exists(suspicions_path):
            with open(suspicions_path, 'r', encoding='utf-8') as f:
                suspicions = json.load(f)
        
        derived_path = os.path.join(cache_dir, 'derived_data.json')
        if os.path.exists(derived_path):
            with open(derived_path, 'r', encoding='utf-8') as f:
                analysis_results = json.load(f)
        
        graph_path = os.path.join(cache_dir, 'graph_data.json')
        if os.path.exists(graph_path):
            with open(graph_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
        
        # 组装完整结果
        cache = {
            'persons': metadata.get('persons', []),
            'companies': metadata.get('companies', []),
            'profiles': profiles,
            'suspicions': suspicions,
            'analysisResults': analysis_results,
            'graphData': graph_data,
            '_meta': {
                'source': 'analysis_cache',
                'generatedAt': metadata.get('generatedAt'),
            }
        }
        
        return ReportDataBuilder(cache)
        
    except Exception as e:
        logger.error(f"加载分析缓存失败: {e}")
        return None
