#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初查报告构建器 - 复用缓存数据生成完整报告

【数据复用铁律】
1. 本模块仅复用 analysis_cache 中已计算的分析结果
2. 严禁直接读取 Excel 重新计算任何指标
3. 所有数据必须来自 profiles.json, derived_data.json, suspicions.json

版本: 1.0.0
日期: 2026-01-20
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import asdict

import config
import utils
from report_schema import (
    InvestigationReport, InvestigationMeta, InvestigationFamily,
    FamilyMember, FamilySummary, FamilyAssetsSummary,
    MemberDetails, PersonAssets, PersonAnalysis,
    BankAccountInfo, YearlySalaryStats,
    IncomeGapAnalysis, LargeCashAnalysis, LargeTransferAnalysis,
    InflowAnalysis, OutflowAnalysis, CounterpartyFlow, ExternalDataPlaceholder,
    CompanyReport, InvestigationUnitFlows, KeyPersonTransfers, CompanyCashAnalysis,
    InvestigationConclusion, IssueItem
)

logger = utils.setup_logger(__name__)


# 银行账户剔除关键词
ACCOUNT_EXCLUDE_KEYWORDS = ['基金', '理财', '证券', '期货', '信托', '资管', '托管']


class InvestigationReportBuilder:
    """
    初查报告构建器
    
    【铁律】仅从 analysis_cache 读取预计算数据，禁止重新读取 Excel
    
    数据来源：
    - profiles.json: 个人/公司画像数据
    - derived_data.json: 派生分析数据（借贷、大额交易、家庭汇总）
    - suspicions.json: 可疑交易检测结果
    - graph_data.json: 关系图谱数据
    """
    
    def __init__(self, analysis_cache: Dict):
        """
        初始化
        
        Args:
            analysis_cache: 由 api_server.py 的 _load_analysis_cache() 加载的完整结果
        """
        self.profiles = analysis_cache.get('profiles', {})
        self.derived_data = analysis_cache.get('derived_data', {})
        self.suspicions = analysis_cache.get('suspicions', {})
        self.graph_data = analysis_cache.get('graph_data', {})
        self.metadata = analysis_cache.get('metadata', {})
        
        # 缓存核心人员列表
        self._core_persons = self._extract_core_persons()
        self._companies = self._extract_companies()
        
        logger.info(f"[初查报告构建器] 已加载 {len(self.profiles)} 个实体画像")
        logger.info(f"[初查报告构建器] 核心人员: {len(self._core_persons)}, 公司: {len(self._companies)}")
    
    def _extract_core_persons(self) -> List[str]:
        """提取核心人员列表"""
        persons = []
        for name, profile in self.profiles.items():
            # 排除公司（通常公司名称较长或包含特定关键词）
            if not self._is_company(name):
                persons.append(name)
        return persons
    
    def _extract_companies(self) -> List[str]:
        """提取公司列表"""
        companies = []
        for name in self.profiles.keys():
            if self._is_company(name):
                companies.append(name)
        return companies
    
    def _is_company(self, name: str) -> bool:
        """判断是否为公司"""
        company_keywords = ['公司', '集团', '有限', '股份', '企业', '中心', '事务所']
        return any(kw in name for kw in company_keywords)
    
    # ==================== 主入口 ====================
    
    def build_complete_report(self,
                               primary_person: str,
                               doc_number: str = None,
                               case_background: str = None,
                               data_scope: str = None,
                               include_companies: List[str] = None) -> Dict:
        """
        生成完整初查报告
        
        Args:
            primary_person: 核查对象（户主）
            doc_number: 文号
            case_background: 案件背景
            data_scope: 数据范围
            include_companies: 需要包含的公司列表（可选）
            
        Returns:
            完整报告字典
        """
        logger.info(f"[初查报告] 开始生成报告，核查对象: {primary_person}")
        
        # 1. 构建元信息
        meta = self._build_meta(doc_number, case_background, data_scope)
        
        # 2. 构建家庭部分
        family = self._build_family_section(primary_person)
        
        # 3. 构建成员详情
        member_details = self._build_all_member_details(primary_person, family)
        
        # 4. 构建公司报告
        companies_to_include = include_companies or self._companies
        company_reports = [self._build_company_report(c) for c in companies_to_include]
        
        # 5. 生成综合研判
        conclusion = self._build_conclusion(member_details, company_reports)
        
        # 组装完整报告
        report = InvestigationReport(
            meta=meta,
            family=family,
            member_details=member_details,
            companies=company_reports,
            conclusion=conclusion
        )
        
        logger.info(f"[初查报告] 报告生成完成，包含 {len(member_details)} 个成员，{len(company_reports)} 个公司")
        
        return report.to_dict()
    
    # ==================== Meta 构建 ====================
    
    def _build_meta(self, doc_number: str, case_background: str, data_scope: str) -> InvestigationMeta:
        """构建元信息"""
        # 从 metadata 中提取数据范围
        if not data_scope and self.metadata:
            date_range = self.metadata.get('date_range', {})
            if date_range:
                start = date_range.get('start', '')
                end = date_range.get('end', '')
                if start and end:
                    data_scope = f"{start[:10]} 至 {end[:10]} 银行流水数据"
        
        return InvestigationMeta(
            doc_number=doc_number or "",
            case_background=case_background or "",
            data_scope=data_scope or "",
            generated_at=datetime.now().isoformat(),
            version="1.0.0",
            generator="穿云审计初查报告引擎"
        )
    
    # ==================== 家庭部分构建 ====================
    
    def _build_family_section(self, primary_person: str) -> InvestigationFamily:
        """构建家庭部分"""
        # 获取家庭成员
        family_summary_data = self.derived_data.get('family_summary', {})
        
        members = []
        family_members_names = []
        
        # 方法1: 从 family_summary.family_members 列表获取
        cached_members = family_summary_data.get('family_members', [])
        
        # 方法2: 如果没有，从 member_transfers 字典的 keys 获取
        if not cached_members:
            member_transfers = family_summary_data.get('member_transfers', {})
            cached_members = list(member_transfers.keys())
        
        # 方法3: 如果还没有，从 profiles 中获取所有个人（非公司）
        if not cached_members:
            cached_members = self._core_persons.copy()
        
        logger.info(f"[初查报告] 家庭成员列表: {cached_members}")
        
        # 先添加核查对象本人
        if primary_person in cached_members:
            members.append(FamilyMember(
                name=primary_person,
                relation="本人",
                has_data=primary_person in self.profiles
            ))
            family_members_names.append(primary_person)
        
        # 添加其他家庭成员
        for name in cached_members:
            if name != primary_person and name not in family_members_names:
                relation = self._infer_relation(primary_person, name)
                members.append(FamilyMember(
                    name=name,
                    relation=relation,
                    has_data=name in self.profiles
                ))
                family_members_names.append(name)
        
        # 构建家庭汇总
        summary = self._build_family_summary(family_members_names, family_summary_data)
        
        logger.info(f"[初查报告] 构建完成，共 {len(members)} 个成员")
        
        return InvestigationFamily(
            primary_person=primary_person,
            members=members,
            summary=summary
        )
    
    def _infer_relation(self, primary: str, member: str) -> str:
        """推断成员关系（简化版）"""
        # TODO: 可以从 family_analyzer 的结果中获取更准确的关系
        return "家庭成员"
    
    def _build_family_summary(self, members: List[str], family_summary_data: Dict) -> FamilySummary:
        """构建家庭汇总"""
        total_income = 0.0
        total_expense = 0.0
        
        # 汇总所有成员收支
        for name in members:
            profile = self.profiles.get(name, {})
            total_income += profile.get('totalIncome', 0) or 0
            total_expense += profile.get('totalExpense', 0) or 0
        
        # 从 family_summary 获取净收支（已剔除互转）
        net_income = family_summary_data.get('total_net_income', total_income)
        net_expense = family_summary_data.get('total_net_expense', total_expense)
        internal_transfers = family_summary_data.get('internal_transfers_total', 0)
        
        # 构建资产汇总
        assets = self._build_family_assets(members)
        
        return FamilySummary(
            total_income=total_income,
            total_expense=total_expense,
            net_income=net_income,
            net_expense=net_expense,
            internal_transfers=internal_transfers,
            assets=assets
        )
    
    def _build_family_assets(self, members: List[str]) -> FamilyAssetsSummary:
        """构建家庭资产汇总"""
        deposits = 0.0
        wealth_holdings = 0.0
        
        for name in members:
            profile = self.profiles.get(name, {})
            # 理财持仓
            wealth_holdings += profile.get('wealthTotal', 0) or 0
            # 存款估算 (使用最后余额或其他方式)
            # TODO: 需要从 bank_accounts 获取真实余额
        
        return FamilyAssetsSummary(
            real_estate_count=0,  # 需外部数据
            real_estate_value=0.0,
            vehicle_count=0,  # 需外部数据
            deposits=deposits / 10000,  # 转万元
            wealth_holdings=wealth_holdings / 10000,
            total_assets=(deposits + wealth_holdings) / 10000
        )
    
    # ==================== 成员详情构建 ====================
    
    def _build_all_member_details(self, primary: str, family: InvestigationFamily) -> List[MemberDetails]:
        """构建所有成员详情"""
        details = []
        
        for member in family.members:
            if member.has_data:
                detail = self._build_member_details(member.name, member.relation)
                details.append(detail)
        
        return details
    
    def _build_member_details(self, name: str, relation: str) -> MemberDetails:
        """构建单个成员详情"""
        profile = self.profiles.get(name, {})
        
        # 基础信息
        total_income = profile.get('totalIncome', 0) or 0
        total_expense = profile.get('totalExpense', 0) or 0
        transaction_count = profile.get('transactionCount', 0) or 0
        
        # 资产板块
        assets = self._build_person_assets(name, profile)
        
        # 分析板块
        analysis = self._build_person_analysis(name, profile)
        
        return MemberDetails(
            name=name,
            relation=relation,
            total_income=total_income,
            total_expense=total_expense,
            transaction_count=transaction_count,
            assets=assets,
            analysis=analysis
        )
    
    def _build_person_assets(self, name: str, profile: Dict) -> PersonAssets:
        """构建个人资产板块"""
        # 工资统计
        salary_total = profile.get('salaryTotal', 0) or 0
        salary_ratio = profile.get('salaryRatio', 0) or 0
        
        # 年度工资明细
        yearly_salary_data = profile.get('yearlySalary', {}).get('yearly_stats', {})
        yearly_salary = []
        for year, stats in yearly_salary_data.items():
            yearly_salary.append(YearlySalaryStats(
                year=str(year),
                total=stats.get('total', 0),
                months=stats.get('months', 0),
                avg_monthly=stats.get('avg_monthly', 0),
                transaction_count=stats.get('transaction_count', 0)
            ))
        
        # 理财
        wealth_total = profile.get('wealthTotal', 0) or 0
        
        # 银行账户（剔除非真实账户）
        bank_accounts = self._build_bank_accounts(name, profile)
        
        return PersonAssets(
            salary_total=salary_total,
            salary_ratio=salary_ratio,
            yearly_salary=yearly_salary,
            wealth_total=wealth_total,
            wealth_holding=0.0,  # TODO: 需要估算
            bank_accounts=bank_accounts,
            bank_account_count=len(bank_accounts)
        )
    
    def _build_bank_accounts(self, name: str, profile: Dict) -> List[BankAccountInfo]:
        """构建银行账户列表（剔除非真实账户，整合官方余额数据）"""
        accounts = []
        raw_accounts = profile.get('bankAccounts', []) or profile.get('bank_accounts', []) or []
        
        # 获取官方账户数据（含余额）用于匹配
        official_accounts = profile.get('bank_accounts_official', []) or []
        # 构建账号到余额的映射
        balance_map = {}
        for oa in official_accounts:
            if isinstance(oa, dict):
                acc_num = oa.get('account_number', '') or oa.get('card_number', '')
                if acc_num:
                    balance_map[acc_num] = oa.get('balance', 0) or oa.get('available_balance', 0) or 0
        
        for acc in raw_accounts:
            if isinstance(acc, dict):
                # 支持中文字段名和英文字段名
                bank_name = acc.get('银行名称', '') or acc.get('bank_name', '') or acc.get('bankName', '')
                account_number = acc.get('完整账号', '') or acc.get('账号', '') or acc.get('account_number', '')
                account_type = acc.get('账户类别', '') or acc.get('account_type', '个人账户')
                card_type = acc.get('账户类型', '') or acc.get('card_type', '借记卡')
                status = acc.get('账户状态', '') or acc.get('status', '正常')
                last_tx_date = acc.get('最后交易时间', '') or acc.get('last_transaction_date', '')
                
                # 使用缓存中的 是否真实银行卡 字段（如有），否则自行判断
                is_real = acc.get('是否真实银行卡', None)
                if is_real is None:
                    is_real = self._is_real_bank_account(bank_name, account_number, card_type)
                
                if is_real:
                    # 尝试从官方数据匹配余额
                    balance = acc.get('balance', 0) or acc.get('余额', 0) or 0
                    if balance == 0 and account_number in balance_map:
                        balance = balance_map[account_number]
                    
                    accounts.append(BankAccountInfo(
                        bank_name=bank_name,
                        account_number=account_number,
                        account_type=account_type,
                        card_type=card_type,
                        status=status,
                        balance=balance,
                        last_transaction_date=str(last_tx_date)[:19] if last_tx_date else ''
                    ))
        
        # 如果流水账户为空，直接使用官方账户
        if not accounts and official_accounts:
            for oa in official_accounts:
                if isinstance(oa, dict):
                    bank_name = oa.get('bank_name', '') or oa.get('反馈单位', '')
                    account_number = oa.get('account_number', '') or oa.get('card_number', '')
                    if self._is_real_bank_account(bank_name, account_number, ''):
                        accounts.append(BankAccountInfo(
                            bank_name=bank_name,
                            account_number=account_number,
                            account_type=oa.get('account_type', '个人账户'),
                            card_type='借记卡',
                            status=oa.get('status', '正常'),
                            balance=oa.get('balance', 0) or oa.get('available_balance', 0) or 0,
                            last_transaction_date=oa.get('last_transaction', '') or ''
                        ))
        
        return accounts
    
    def _is_real_bank_account(self, bank_name: str, account_number: str, card_type: str = '') -> bool:
        """判断是否为真实银行账户"""
        # 剔除包含关键词的账户
        combined = f"{bank_name}{account_number}{card_type}"
        for keyword in ACCOUNT_EXCLUDE_KEYWORDS:
            if keyword in combined:
                return False
        
        # 检查账号长度（真实银行卡通常16-19位）
        digits = ''.join(c for c in account_number if c.isdigit())
        if len(digits) < 10 or len(digits) > 25:
            return False
        
        return True
    
    def _build_person_analysis(self, name: str, profile: Dict) -> PersonAnalysis:
        """构建个人分析板块"""
        # 收支匹配分析
        income_gap = self._build_income_gap_analysis(profile)
        
        # 资金流入分析（新增）
        inflow_analysis = self._build_inflow_analysis(profile)
        
        # 资金流出分析（新增）
        outflow_analysis = self._build_outflow_analysis(name, profile)
        
        # 大额现金分析
        large_cash = self._build_large_cash_analysis(profile)
        
        # 大额转账分析
        large_transfers = self._build_large_transfer_analysis(name)
        
        # 第三方支付
        third_party_total = profile.get('thirdPartyTotal', 0) or 0
        
        # 可疑交易统计
        income_classification = profile.get('incomeClassification', {})
        suspicious_details = income_classification.get('suspicious_details', [])
        suspicious_count = len(suspicious_details)
        
        return PersonAnalysis(
            income_gap=income_gap,
            inflow_analysis=inflow_analysis,
            outflow_analysis=outflow_analysis,
            large_cash=large_cash,
            large_transfers=large_transfers,
            third_party_total=third_party_total,
            suspicious_count=suspicious_count,
            # 外部数据占位提示
            identity_info=ExternalDataPlaceholder(available=False, message="基本身份信息需外部数据源"),
            property_info=ExternalDataPlaceholder(available=False, message="房产信息需不动产数据"),
            vehicle_info=ExternalDataPlaceholder(available=False, message="车辆信息需外部数据源")
        )
    
    def _build_inflow_analysis(self, profile: Dict) -> InflowAnalysis:
        """构建资金流入分析"""
        income_classification = profile.get('incomeClassification', {})
        total_income = profile.get('totalIncome', 0) or 0
        
        # 从 incomeClassification 提取各类收入
        unknown_details = income_classification.get('unknown_source_details', [])
        suspicious_details = income_classification.get('suspicious_details', [])
        
        # 计算来源不明金额
        unknown_source_amount = sum(d.get('amount', 0) for d in unknown_details)
        unknown_source_ratio = (unknown_source_amount / total_income * 100) if total_income > 0 else 0
        
        # 按对手方分组统计（从 unknown_details 和 suspicious_details 中提取）
        counterparty_totals = {}
        all_details = unknown_details + suspicious_details
        for d in all_details:
            cp = d.get('counterparty', '未知')
            if cp and cp != 'nan':
                if cp not in counterparty_totals:
                    counterparty_totals[cp] = {'amount': 0, 'count': 0, 'category': d.get('reason', '未分类')}
                counterparty_totals[cp]['amount'] += d.get('amount', 0)
                counterparty_totals[cp]['count'] += 1
        
        # 排序并取 Top 10
        sorted_sources = sorted(counterparty_totals.items(), key=lambda x: x[1]['amount'], reverse=True)[:10]
        top_sources = [
            CounterpartyFlow(
                counterparty=cp,
                total_amount=data['amount'],
                count=data['count'],
                percentage=(data['amount'] / total_income * 100) if total_income > 0 else 0,
                category=data['category']
            )
            for cp, data in sorted_sources
        ]
        
        # 按类别汇总
        category_summary = {}
        for d in all_details:
            reason = d.get('reason', '未分类')
            if reason not in category_summary:
                category_summary[reason] = 0
            category_summary[reason] += d.get('amount', 0)
        
        # 提取三类收入占比（合法/不明/可疑）
        legitimate_income = income_classification.get('legitimate_income', 0) or 0
        legitimate_ratio = income_classification.get('legitimate_ratio', 0) or 0
        suspicious_income = income_classification.get('suspicious_income', 0) or 0
        suspicious_ratio = income_classification.get('suspicious_ratio', 0) or 0
        unknown_income = income_classification.get('unknown_income', 0) or unknown_source_amount
        unknown_ratio = income_classification.get('unknown_ratio', 0) or unknown_source_ratio
        
        # 如果没有从 incomeClassification 获取到分类数据，使用明细计算
        if legitimate_income == 0 and total_income > 0:
            legitimate_details = income_classification.get('legitimate_details', [])
            legitimate_income = sum(d.get('amount', 0) for d in legitimate_details)
            legitimate_ratio = (legitimate_income / total_income * 100) if total_income > 0 else 0
        
        return InflowAnalysis(
            total_inflow=total_income,
            top_sources=top_sources,
            category_summary=category_summary,
            unknown_source_amount=unknown_income,
            unknown_source_ratio=unknown_ratio,
            legitimate_income=legitimate_income,
            legitimate_ratio=legitimate_ratio,
            suspicious_income=suspicious_income,
            suspicious_ratio=suspicious_ratio
        )
    
    def _build_outflow_analysis(self, name: str, profile: Dict) -> OutflowAnalysis:
        """构建资金流出分析"""
        total_expense = profile.get('totalExpense', 0) or 0
        
        # 从 large_transactions 中提取支出
        large_transactions = self.derived_data.get('large_transactions', [])
        person_expenses = []
        if isinstance(large_transactions, list):
            person_expenses = [t for t in large_transactions 
                              if t.get('person') == name and t.get('direction') == 'expense']
        
        # 按对手方分组
        counterparty_totals = {}
        for t in person_expenses:
            cp = t.get('counterparty', '未知')
            if cp and cp != 'nan':
                if cp not in counterparty_totals:
                    counterparty_totals[cp] = {'amount': 0, 'count': 0}
                counterparty_totals[cp]['amount'] += t.get('amount', 0)
                counterparty_totals[cp]['count'] += 1
        
        # 排序并取 Top 10
        sorted_dests = sorted(counterparty_totals.items(), key=lambda x: x[1]['amount'], reverse=True)[:10]
        top_destinations = [
            CounterpartyFlow(
                counterparty=cp,
                total_amount=data['amount'],
                count=data['count'],
                percentage=(data['amount'] / total_expense * 100) if total_expense > 0 else 0,
                category=''
            )
            for cp, data in sorted_dests
        ]
        
        # 大额单笔支出（超过10万）
        large_single_payments = [
            {
                'date': t.get('date', ''),
                'amount': t.get('amount', 0),
                'counterparty': t.get('counterparty', ''),
                'description': t.get('description', '')
            }
            for t in person_expenses if t.get('amount', 0) >= 100000
        ][:20]
        
        return OutflowAnalysis(
            total_outflow=total_expense,
            top_destinations=top_destinations,
            category_summary={},  # 后续可从其他数据源补充
            large_single_payments=large_single_payments
        )
    
    def _build_income_gap_analysis(self, profile: Dict) -> IncomeGapAnalysis:
        """构建收支匹配分析"""
        total_income = profile.get('totalIncome', 0) or 0
        salary_total = profile.get('salaryTotal', 0) or 0
        ratio = profile.get('salaryRatio', 0) or 0
        
        # 生成判定结论
        ratio_percent = ratio * 100
        if ratio_percent >= 80:
            verdict = "正常，工资为主要收入来源"
        elif ratio_percent >= 50:
            verdict = "基本正常，工资占比适中"
        elif ratio_percent >= 30:
            verdict = f"工资占比偏低（{ratio_percent:.1f}%），需核实其他收入来源"
        else:
            verdict = f"工资占比过低（{ratio_percent:.1f}%），收入来源可疑"
        
        return IncomeGapAnalysis(
            total_income=total_income,
            salary_income=salary_total,
            ratio=ratio_percent,
            verdict=verdict
        )
    
    def _build_large_cash_analysis(self, profile: Dict) -> LargeCashAnalysis:
        """构建大额现金分析"""
        cash_total = profile.get('cashTotal', 0) or 0
        cash_income = profile.get('cashIncome', 0) or 0
        cash_expense = profile.get('cashExpense', 0) or 0
        cash_transactions = profile.get('cashTransactions', []) or []
        
        return LargeCashAnalysis(
            total_amount=cash_total,
            deposit_amount=cash_income,
            withdraw_amount=cash_expense,
            count=len(cash_transactions),
            transactions=cash_transactions[:20]  # 限制数量
        )
    
    def _build_large_transfer_analysis(self, name: str) -> LargeTransferAnalysis:
        """构建大额转账分析"""
        large_transactions = self.derived_data.get('large_transactions', [])
        
        # large_transactions 是一个列表，按 person 字段筛选
        person_transactions = []
        if isinstance(large_transactions, list):
            person_transactions = [t for t in large_transactions if t.get('person') == name]
        elif isinstance(large_transactions, dict):
            person_transactions = large_transactions.get(name, []) or []
        
        total_amount = sum(t.get('amount', 0) for t in person_transactions)
        
        return LargeTransferAnalysis(
            threshold=getattr(config, 'LARGE_TRANSACTION_THRESHOLD', 50000),
            count=len(person_transactions),
            total_amount=total_amount,
            transactions=person_transactions[:20]  # 限制数量
        )
    
    # ==================== 公司报告构建 ====================
    
    def _build_company_report(self, company: str) -> CompanyReport:
        """
        构建公司报告
        
        五个核心维度：
        1. 资金规模 - 进账/支出/交易笔数
        2. 调查单位往来 - 与配置的调查单位资金往来
        3. 关键人员关联 - 与核心人员的转账
        4. 现金交易 - 提现/存现统计
        5. 基础信息 - 账户列表
        """
        profile = self.profiles.get(company, {})
        
        # 资金规模
        total_income = profile.get('totalIncome', 0) or 0
        total_expense = profile.get('totalExpense', 0) or 0
        transaction_count = profile.get('transactionCount', 0) or 0
        
        # 与调查单位往来
        investigation_unit_flows = self._analyze_investigation_unit_flows(company, profile)
        
        # 与关键人员关联
        key_person_transfers = self._find_key_person_transfers(company)
        
        # 现金交易分析
        cash_analysis = self._build_company_cash_analysis(profile)
        
        # 银行账户
        bank_accounts = self._build_bank_accounts(company, profile)
        
        return CompanyReport(
            company_name=company,
            total_income=total_income,
            total_expense=total_expense,
            transaction_count=transaction_count,
            account_count=len(bank_accounts),
            investigation_unit_flows=investigation_unit_flows,
            key_person_transfers=key_person_transfers,
            cash_analysis=cash_analysis,
            bank_accounts=bank_accounts
        )
    
    def _analyze_investigation_unit_flows(self, company: str, profile: Dict) -> InvestigationUnitFlows:
        """分析与调查单位的资金往来"""
        # 获取调查单位关键词
        keywords = getattr(config, 'INVESTIGATION_UNIT_KEYWORDS', [])
        if not keywords:
            return InvestigationUnitFlows(has_flows=False)
        
        # 从 derived_data 中查找与调查单位的往来
        investigation_flows = self.derived_data.get('investigation_unit_flows', {})
        company_flows = investigation_flows.get(company, {})
        
        if not company_flows:
            return InvestigationUnitFlows(has_flows=False)
        
        total = company_flows.get('total_amount', 0)
        total_flow = profile.get('totalIncome', 0) + profile.get('totalExpense', 0)
        percentage = (total / total_flow * 100) if total_flow > 0 else 0
        
        return InvestigationUnitFlows(
            has_flows=total > 0,
            total_amount=total,
            percentage=percentage,
            transactions=company_flows.get('transactions', [])
        )
    
    def _find_key_person_transfers(self, company: str) -> KeyPersonTransfers:
        """查找与关键人员的关联交易"""
        # 从 suspicions 中查找直接转账
        direct_transfers = self.suspicions.get('direct_transfers', []) or []
        
        # 筛选涉及该公司的转账
        company_transfers = []
        for t in direct_transfers:
            if t.get('from') == company or t.get('to') == company:
                company_transfers.append(t)
        
        if not company_transfers:
            return KeyPersonTransfers(has_transfers=False)
        
        total_amount = sum(t.get('amount', 0) for t in company_transfers)
        unique_persons = set()
        for t in company_transfers:
            if t.get('from') != company:
                unique_persons.add(t.get('from'))
            if t.get('to') != company:
                unique_persons.add(t.get('to'))
        
        return KeyPersonTransfers(
            has_transfers=True,
            total_amount=total_amount,
            transfer_count=len(company_transfers),
            unique_persons=len(unique_persons),
            details=company_transfers[:20]
        )
    
    def _build_company_cash_analysis(self, profile: Dict) -> CompanyCashAnalysis:
        """构建公司现金交易分析"""
        cash_total = profile.get('cashTotal', 0) or 0
        cash_income = profile.get('cashIncome', 0) or 0
        cash_expense = profile.get('cashExpense', 0) or 0
        cash_income_count = profile.get('cashIncomeCount', 0) or 0
        cash_expense_count = profile.get('cashExpenseCount', 0) or 0
        
        return CompanyCashAnalysis(
            has_cash=cash_total > 0,
            total_amount=cash_total,
            deposit_amount=cash_income,
            withdraw_amount=cash_expense,
            deposit_count=cash_income_count,
            withdraw_count=cash_expense_count
        )
    
    # ==================== 综合研判构建 ====================
    
    def _build_conclusion(self, member_details: List[MemberDetails], 
                          company_reports: List[CompanyReport]) -> InvestigationConclusion:
        """生成综合研判"""
        issues = self._collect_issues(member_details, company_reports)
        next_steps = self._generate_next_steps(issues)
        summary_text = self._generate_summary_text(issues)
        
        # 统计风险等级
        high_count = sum(1 for i in issues if i.severity == 'high')
        medium_count = sum(1 for i in issues if i.severity == 'medium')
        low_count = sum(1 for i in issues if i.severity == 'low')
        
        # 统计确认程度
        confirmed_count = sum(1 for i in issues if i.verification_status == 'confirmed')
        highly_suspicious_count = sum(1 for i in issues if i.verification_status == 'highly_suspicious')
        need_verification_count = sum(1 for i in issues if i.verification_status == 'need_verification')
        
        # 计算问题涉及总金额
        total_amount = sum(i.amount for i in issues)
        
        return InvestigationConclusion(
            summary_text=summary_text,
            issues=issues,
            next_steps=next_steps,
            high_risk_count=high_count,
            medium_risk_count=medium_count,
            low_risk_count=low_count,
            confirmed_count=confirmed_count,
            highly_suspicious_count=highly_suspicious_count,
            need_verification_count=need_verification_count,
            total_amount=total_amount
        )
    
    def _collect_issues(self, member_details: List[MemberDetails], 
                        company_reports: List[CompanyReport]) -> List[IssueItem]:
        """收集所有问题"""
        issues = []
        
        # 1. 个人收支不抵问题
        for member in member_details:
            ratio = member.analysis.income_gap.ratio
            total_income = member.analysis.income_gap.total_income
            salary_income = member.analysis.income_gap.salary_income
            unknown_amount = total_income - salary_income
            
            if ratio < 30:
                # 工资占比不足30%，高度可疑
                issues.append(IssueItem(
                    person=member.name,
                    issue_type="收支不抵",
                    description=f"工资收入占比仅{ratio:.1f}%，远低于50%，收入来源不明",
                    severity="high",
                    verification_status="highly_suspicious",
                    amount=unknown_amount
                ))
            elif ratio < 50:
                # 工资占比50%以下，需核实
                issues.append(IssueItem(
                    person=member.name,
                    issue_type="收支不抵",
                    description=f"工资收入占比{ratio:.1f}%，低于50%，需核实其他收入来源",
                    severity="medium",
                    verification_status="need_verification",
                    amount=unknown_amount
                ))
        
        # 2. 大额现金问题
        for member in member_details:
            cash_total = member.analysis.large_cash.total_amount
            if cash_total > 500000:  # 超过50万
                # 大额现金需核实
                v_status = "highly_suspicious" if cash_total > 1000000 else "need_verification"
                issues.append(IssueItem(
                    person=member.name,
                    issue_type="大额现金",
                    description=f"现金交易总额{cash_total/10000:.1f}万元，需核实现金来源及去向",
                    severity="high" if cash_total > 1000000 else "medium",
                    verification_status=v_status,
                    amount=cash_total
                ))
        
        # 3. 公司与关键人员关联问题
        for company in company_reports:
            if company.key_person_transfers.has_transfers:
                transfers = company.key_person_transfers
                # 公司与关键人员有直接转账，高度可疑
                issues.append(IssueItem(
                    person=company.company_name,
                    issue_type="异常资金往来",
                    description=f"与{transfers.unique_persons}名关键人员存在{transfers.transfer_count}笔直接转账，"
                               f"金额合计{transfers.total_amount/10000:.1f}万元",
                    severity="high",
                    verification_status="highly_suspicious",
                    amount=transfers.total_amount
                ))
        
        # 4. 从 suspicions 获取更多问题
        for suspicion in (self.suspicions.get('direct_transfers', []) or []):
            amount = suspicion.get('amount', 0)
            risk_level = suspicion.get('risk_level', 'medium')
            # 根据风险等级判断确认程度
            v_status = "confirmed" if risk_level == "critical" else ("highly_suspicious" if risk_level == "high" else "need_verification")
            issues.append(IssueItem(
                person=f"{suspicion.get('from', '')}→{suspicion.get('to', '')}",
                issue_type="异常资金往来",
                description=f"直接转账 {amount/10000:.1f}万元，摘要：{suspicion.get('description', '')}",
                severity=risk_level,
                verification_status=v_status,
                amount=amount
            ))
        
        # 5. 借贷异常
        loan_details = self.derived_data.get('loan', {}).get('details', []) or []
        for loan in loan_details:
            if loan.get('risk_level') == 'high':
                issues.append(IssueItem(
                    person=loan.get('person', ''),
                    issue_type="借贷异常",
                    description=f"与{loan.get('counterparty', '')}存在异常借贷关系：{loan.get('risk_reason', '')}",
                    severity="high",
                    verification_status="need_verification",
                    amount=loan.get('total_amount', 0)
                ))
        
        return issues
    
    def _generate_next_steps(self, issues: List[IssueItem]) -> List[str]:
        """生成下一步工作建议"""
        steps = set()
        
        STEP_TEMPLATES = {
            "收支不抵": "对相关人员的不明收入来源进行约谈核实",
            "异常资金往来": "调取相关银行凭证原件进行核对",
            "大额现金": "核实大额现金交易的来源及去向",
            "借贷异常": "核实相关借贷关系的真实性",
            "资金来源不明": "对资金来源进行深入调查"
        }
        
        for issue in issues:
            if issue.issue_type in STEP_TEMPLATES:
                steps.add(STEP_TEMPLATES[issue.issue_type])
        
        # 添加通用建议
        if issues:
            steps.add("对高风险问题进行重点核实")
            steps.add("形成初步调查意见报告")
        
        return list(steps)
    
    def _generate_summary_text(self, issues: List[IssueItem]) -> str:
        """生成研判意见文本"""
        if not issues:
            return "经对相关人员资金流水进行穿透分析，未发现明显异常。"
        
        high_count = sum(1 for i in issues if i.severity == 'high')
        medium_count = sum(1 for i in issues if i.severity == 'medium')
        
        text = f"经对相关人员资金流水进行穿透分析，共发现{len(issues)}项问题"
        
        if high_count > 0:
            text += f"，其中高风险问题{high_count}项"
        if medium_count > 0:
            text += f"，中风险问题{medium_count}项"
        
        text += "。建议对上述问题进行进一步核实。"
        
        return text
    
    # ==================== 导出功能 ====================
    
    def export_report(self, report: Dict, output_path: str):
        """导出JSON格式报告"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"[初查报告] 报告已导出: {output_path}")
    
    def get_available_primary_persons(self) -> List[str]:
        """获取可选的核查对象列表"""
        return self._core_persons.copy()
    
    def get_available_companies(self) -> List[str]:
        """获取可选的公司列表"""
        return self._companies.copy()


# ==================== 加载器函数 ====================

def load_investigation_report_builder(output_dir: str = './output') -> Optional[InvestigationReportBuilder]:
    """
    加载初查报告构建器
    
    Args:
        output_dir: 输出目录路径
        
    Returns:
        InvestigationReportBuilder 实例，如果缓存不存在则返回 None
    """
    cache_dir = os.path.join(output_dir, 'analysis_cache')
    
    # 检查缓存目录
    if not os.path.exists(cache_dir):
        logger.warning(f"[初查报告] 缓存目录不存在: {cache_dir}")
        return None
    
    # 加载各个缓存文件
    analysis_cache = {}
    
    cache_files = {
        'profiles': 'profiles.json',
        'derived_data': 'derived_data.json',
        'suspicions': 'suspicions.json',
        'graph_data': 'graph_data.json',
        'metadata': 'metadata.json'
    }
    
    for key, filename in cache_files.items():
        filepath = os.path.join(cache_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    analysis_cache[key] = json.load(f)
                logger.info(f"[初查报告] 已加载: {filename}")
            except Exception as e:
                logger.warning(f"[初查报告] 加载 {filename} 失败: {e}")
                analysis_cache[key] = {}
        else:
            logger.warning(f"[初查报告] 文件不存在: {filepath}")
            analysis_cache[key] = {}
    
    return InvestigationReportBuilder(analysis_cache)


# ==================== 测试入口 ====================

if __name__ == '__main__':
    import sys
    
    output_dir = sys.argv[1] if len(sys.argv) > 1 else './output'
    
    builder = load_investigation_report_builder(output_dir)
    if builder:
        print(f"可选核查对象: {builder.get_available_primary_persons()}")
        print(f"可选公司: {builder.get_available_companies()}")
        
        # 生成测试报告
        primary = builder.get_available_primary_persons()[0] if builder.get_available_primary_persons() else None
        if primary:
            report = builder.build_complete_report(
                primary_person=primary,
                doc_number="国监查 [2026] 第 000001 号",
                case_background="测试案件背景"
            )
            print(json.dumps(report, ensure_ascii=False, indent=2)[:2000])
    else:
        print("无法加载报告构建器")
