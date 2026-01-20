#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告数据服务模块 - 初查报告生成引擎

【数据复用铁律】
1. 本模块仅复用 analysis_cache 中已计算的分析结果
2. 严禁直接读取 Excel 重新计算任何指标
3. 确保前端展示与报告数据 100% 一致
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
    }
</style>
"""


class ReportDataBuilder:
    """
    初查报告数据构建器 - 复用已有分析结果
    
    【铁律】仅从 analysis_cache 读取预计算数据，禁止重新计算
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
        构建个人分析数据 - 100%复用缓存
        
        Args:
            person: 人员名称
            
        Returns:
            个人分析数据字典
        """
        profile = self.profiles.get(person, {})
        
        # 【修复】profiles.json 使用扁平结构，检查 totalIncome 或 transactionCount 来判断是否有数据
        if not profile or (profile.get('transactionCount', 0) == 0 and profile.get('totalIncome', 0) == 0):
            return {'name': person, 'has_data': False}
        
        # 【修复】直接读取扁平结构的字段
        total_income = profile.get('totalIncome', 0)
        total_expense = profile.get('totalExpense', 0)
        transaction_count = profile.get('transactionCount', 0)
        salary_ratio = profile.get('salaryRatio', 0)
        salary_total = profile.get('salaryTotal', 0)
        cash_total = profile.get('cashTotal', 0)
        cash_transactions = profile.get('cashTransactions', [])
        third_party_total = profile.get('thirdPartyTotal', 0)
        wealth_total = profile.get('wealthTotal', 0)
        
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
        
        return {
            'name': person,
            'has_data': True,
            'summary': {
                'transactionCount': transaction_count,
                'totalIncome': total_income,
                'totalExpense': total_expense,
                'netFlow': total_income - total_expense,
                'salaryRatio': salary_ratio,
                'salaryIncome': salary_total,
                'largeCashCount': len([t for t in cash_transactions if t.get('amount', 0) >= 50000]),
            },
            'incomeRiskText': income_risk_text,
            'topCounterparties': {
                'income': [],  # TODO: 从 graphData 中提取
                'expense': [],
            },
            'largeCash': {
                'totalAmount': cash_total,
                'count': len(cash_transactions),
                'transactions': cash_transactions[:10],
            },
            'wealthManagement': {
                'purchase': wealth_total,
                'redemption': 0,
                'estimatedHolding': wealth_total,
            },
            'thirdPartyTotal': third_party_total,
            'loanAnalysis': person_loans,
            'incomeIssues': person_income_issues,
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
        生成公文格式 HTML 报告
        
        Args:
            subjects: 选中的嫌疑人名单
            case_name: 案件名称
            doc_number: 文号（如 国监查 [2026] 第 12345 号）
            include_assets: 是否包含资产信息
            include_income: 是否包含收入分析
            include_loan: 是否包含借贷分析
            
        Returns:
            HTML 字符串
        """
        if not doc_number:
            doc_number = f"国监查 [{datetime.now().year}] 第 {datetime.now().strftime('%Y%m%d%H%M')} 号"
        
        # 构建 HTML 内容
        html_content = f"""<!DOCTYPE html>
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
"""
        
        # 生成每个嫌疑人的分析板块
        for idx, subject in enumerate(subjects, 1):
            person_data = self.build_person_report(subject)
            
            if not person_data.get('has_data'):
                html_content += f"""
        <h2>二、{subject}（无有效数据）</h2>
        <p>未查见该人员/企业的有效交易记录。</p>
"""
                continue
            
            summary = person_data.get('summary', {})
            
            html_content += f"""
        <h2>{'二' if idx == 1 else self._num_to_chinese(idx + 1)}、{subject} 资金核查情况</h2>
        
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
                html_content += f"""
        <div class="conclusion">
            <strong>⚠ 收入匹配度分析：</strong>{person_data.get('incomeRiskText')}
        </div>
"""
            
            # 主要交易对手
            top_cp = person_data.get('topCounterparties', {})
            if top_cp.get('income') or top_cp.get('expense'):
                html_content += """
        <h3>（二）主要交易对手</h3>
        <p>排除本人互转后的主要资金往来对象：</p>
        <table>
            <tr>
                <th>方向</th>
                <th>排名</th>
                <th>对手方</th>
                <th>金额（万元）</th>
            </tr>
"""
                for i, cp in enumerate(top_cp.get('income', [])[:3], 1):
                    html_content += f"""
            <tr>
                <td>收入来源</td>
                <td>{i}</td>
                <td>{cp.get('counterparty', '未知')}</td>
                <td class="number">{cp.get('amount', 0)/10000:.2f}</td>
            </tr>
"""
                for i, cp in enumerate(top_cp.get('expense', [])[:3], 1):
                    html_content += f"""
            <tr>
                <td>支出去向</td>
                <td>{i}</td>
                <td>{cp.get('counterparty', '未知')}</td>
                <td class="number">{cp.get('amount', 0)/10000:.2f}</td>
            </tr>
"""
                html_content += "        </table>\n"
        
        # 综合研判与建议
        html_content += """
        <h2>"""
        html_content += self._num_to_chinese(len(subjects) + 2)
        html_content += """、综合研判与建议</h2>
        
        <div class="conclusion">
            <strong>研判意见：</strong>
            <p>经对上述人员资金流水进行穿透分析，发现以下需进一步核实的情况：</p>
            <ul>
"""
        
        # 汇总各嫌疑人的问题
        for subject in subjects:
            person_data = self.build_person_report(subject)
            if person_data.get('incomeRiskText'):
                html_content += f"                <li><strong>{subject}</strong>：{person_data.get('incomeRiskText')}</li>\n"
        
        html_content += """
            </ul>
        </div>
        
        <div class="suggestion">
            <strong>下一步工作建议：</strong>
            <ol>
                <li>调取相关银行凭证原件进行核对</li>
                <li>对收入来源不明的资金进行约谈核实</li>
                <li>核查大额现金交易的真实用途</li>
            </ol>
        </div>
        
        <p style="text-align: right; margin-top: 50px;">
            报告生成时间：<span class="number">"""
        html_content += datetime.now().strftime('%Y年%m月%d日 %H:%M')
        html_content += """</span>
        </p>
    </div>
</body>
</html>
"""
        
        return html_content
    
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
