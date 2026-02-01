#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专业理财分析模块 - 基于用户的专业审计思路

核心审计思路（用户提供）：
1. 资产与收入对比：房产+存款+理财+保险等资产与工资性收入对比
2. 房产计算逻辑：
   - 如果房产没有交易过，应该以购入时的价格计算资产
   - 除非查询数据中没有该笔购房流水，这一点要在房产部分标注出来）
   - 如果房产有交易，增值部分应该算作他的正常收入
3. 现金部分应该重点标注，现金一般都是关注重点
4. 程序设计原则：前面计算过的，后面尽量引用而不重新计算；如果报告部分要重新计算，原则上也是补充在前面数据分析部分
5. 程序已有数据要充分利用

模块功能：
1. 深度理财分析（类型、期限、收益率、资金空转）
2. 理财与收入对比
3. 理财与资产合理性
4. 理财风险识别
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import json
import utils

logger = utils.setup_logger(__name__)


# ============================================================================
# 理财产品识别关键词
# ============================================================================
FINANCIAL_PRODUCT_KEYWORDS = {
    '基金': ['基金', '公募', '私募', 'ETF', 'LOF'],
    '理财': ['理财', '结构性存款', '大额存单', '协议存款', '智能存款'],
    '保险': ['保险', '年金', '终身寿', '万能险', '分红险', '投连险'],
    '信托': ['信托', '资管计划', '集合信托'],
    '银行理财': ['银行理财', '封闭式', '开放式', '净值型', '预期收益型'],
    '证券': ['股票', '债券', '国债', '可转债', '基金'],
    '期货': ['期货', '远期', '期权', '互换', '掉期'],
    '黄金': ['黄金', '贵金属', '金银币', '纸黄金'],
    '外汇': ['外汇', '汇率', '美元', '欧元', '日元', '港币'],
    'P2P': ['P2P', '网贷', '网络借贷', '互联网理财']
}


class FinancialProductAnalyzer:
    """专业理财分析器"""
    
    def __init__(self, thresholds: Optional[Any] = None):
        """初始化分析器"""
        self.thresholds = thresholds or utils.RiskThresholds()
        self.description_templates = self._init_description_templates()
    
    def _init_description_templates(self) -> Dict[str, List[str]]:
        """初始化描述话术模板"""
        return {
            'high_income_from_finance': [
                "该人员理财收益累计{finance_income:.2f}万元，平均年化收益率{annual_yield:.1%}，远高于同期银行存款利率，需核实理财产品的真实性及资金来源。",
                "该人员理财规模{finance_amount:.2f}万元，累计收益{finance_income:.2f}万元，年化收益率{annual_yield:.1%}，存在投资收益异常风险，需重点关注。"
            ],
            'large_finance_low_income': [
                "该人员理财规模{finance_amount:.2f}万元，与其{annual_income:.2f}万元的年收入不匹配，存在资金来源不明风险。",
                "该人员持有大量理财产品，但工资性收入仅{annual_income:.2f}万元，理财资产积累明显超过收入水平，需核实理财资金来源。"
            ],
            'short_term_funding': [
                "该人员存在频繁的短期资金进出，累计{short_term_count}笔，单笔平均持有期{avg_holding_days:.1f}天，可能存在资金过桥或协助洗钱风险。",
                "该人员理财产品持有期普遍较短，存在资金快进快出特征，需关注其资金用途和背景。"
            ],
            'cash_cycling': [
                "该人员资金在理财产品间频繁流转，累计{cycle_count}次资金循环，涉及{cycle_amount:.2f}万元，存在资金空转特征。",
                "该人员理财赎回后立即申购其他产品，资金在账户内停留时间极短，存在明显的资金空转行为。"
            ],
            'complex_finance': [
                "该人员持有{product_types_count}种不同类型理财产品，包括{product_types}，投资结构较为复杂，需核查其投资风险承受能力及资产配置合理性。",
                "该人员理财种类繁多，涉及基金、保险、信托、P2P等多种类型，投资结构复杂，建议进一步核查其投资顾问资质及资产配置合理性。"
            ],
            'normal_finance': [
                "该人员理财规模适中，与收入水平基本匹配，投资结构相对简单合理。",
                "该人员理财投资行为正常，未见异常资金流动，投资收益在合理范围内。"
            ]
        }
    
    def analyze(self,
                person_profile: Dict[str, Any],
                person_transactions: pd.DataFrame,
                income_yearly: Dict[int, float],
                property_data: Optional[List[Dict]] = None,
                vehicle_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        执行完整的理财分析
        
        Args:
            person_profile: 个人资金画像
            person_transactions: 个人交易明细
            income_yearly: 年度工资收入 {year: amount}
            property_data: 房产数据列表
            vehicle_data: 车辆数据列表
        
        Returns:
            分析结果字典
        """
        # 1. 识别理财交易
        finance_txns = self._identify_financial_transactions(person_transactions)
        
        # 2. 分析理财类型
        product_types = self._analyze_product_types(finance_txns)
        
        # 3. 分析理财规模和收益
        finance_scale = self._analyze_finance_scale_and_income(finance_txns, income_yearly, person_profile)
        
        # 4. 分析理财期限（短期 vs 长期）
        holding_period = self._analyze_holding_period(finance_txns)
        
        # 5. 分析理财空转
        cycling = self._detect_finance_cycling(finance_txns)
        
        # 6. 分析理财与资产的合理性
        asset_reasonability = self._analyze_asset_reasonability(
            finance_scale, product_types, property_data, vehicle_data, person_profile
        )
        
        # 7. 计算总体风险评分
        total_score = sum([
            finance_scale['score'],
            product_types['score'],
            holding_period['score'],
            cycling['score'],
            asset_reasonability['score']
        ])
        
        risk_level = self._calculate_risk_level(total_score)
        
        # 8. 生成审计描述
        audit_descriptions = self._generate_audit_descriptions({
            'finance_scale': finance_scale,
            'product_types': product_types,
            'holding_period': holding_period,
            'cycling': cycling,
            'asset_reasonability': asset_reasonability
        })
        
        # 9. 生成风险排除说明
        risk_exclusions = self._generate_risk_exclusions({
            'finance_scale': finance_scale,
            'product_types': product_types,
            'holding_period': holding_period,
            'cycling': cycling,
            'asset_reasonability': asset_reasonability
        })
        
        # 10. 识别红旗标记
        red_flags = self._identify_red_flags({
            'finance_scale': finance_scale,
            'product_types': product_types,
            'holding_period': holding_period,
            'cycling': cycling,
            'asset_reasonability': asset_reasonability
        })
        
        # 11. 生成建议措施
        recommendations = self._generate_recommendations({
            'finance_scale': finance_scale,
            'product_types': product_types,
            'holding_period': holding_period,
            'cycling': cycling,
            'asset_reasonability': asset_reasonability
        })
        
        return {
            'overall_assessment': self._generate_overall_assessment({
                'finance_scale': finance_scale,
                'product_types': product_types,
                'holding_period': holding_period,
                'cycling': cycling,
                'asset_reasonability': asset_reasonability
            }),
            'risk_level': risk_level,
            'risk_score': total_score,
            'dimensions': {
                'finance_scale': finance_scale,
                'product_types': product_types,
                'holding_period': holding_period,
                'cycling': cycling,
                'asset_reasonability': asset_reasonability
            },
            'audit_description': audit_descriptions,
            'risk_exclusions': risk_exclusions,
            'red_flags': red_flags,
            'recommendations': recommendations,
            'evidence': {
                'finance_count': len(finance_txns),
                'finance_amount': finance_scale['total_finance_amount'],
                'finance_income': finance_scale['total_finance_income'],
                'product_types_count': product_types['types_count'],
                'short_term_count': holding_period['short_term_count'],
                'cycle_count': cycling['cycle_count']
            }
        }
    
    def _identify_financial_transactions(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """识别理财交易"""
        # 识别理财相关的关键词
        finance_keywords = []
        for category, keywords in FINANCIAL_PRODUCT_KEYWORDS.items():
            finance_keywords.extend(keywords)
        
        # 构建正则表达式
        finance_pattern = '|'.join(finance_keywords)
        
        # 识别理财交易
        finance_mask = transactions['description'].str.contains(finance_pattern, na=False, case=False)
        finance_txns = transactions[finance_mask]
        
        return finance_txns
    
    def _analyze_product_types(self, finance_txns: pd.DataFrame) -> Dict[str, Any]:
        """分析理财类型"""
        product_types = {}
        
        # 统计各类理财产品的交易笔数和金额
        for category, keywords in FINANCIAL_PRODUCT_KEYWORDS.items():
            category_mask = finance_txns['description'].str.contains('|'.join(keywords), na=False, case=False)
            category_txns = finance_txns[category_mask]
            
            # 统计该类别的交易
            category_count = len(category_txns)
            category_amount = category_txns['amount'].sum()
            
            product_types[category] = {
                'count': category_count,
                'amount': category_amount,
                'avg_amount': category_amount / category_count if category_count > 0 else 0
            }
        
        # 统计理财类型数量
        types_count = len([k for k, v in product_types.items() if v['count'] > 0])
        
        # 计算评分
        score = 0
        if types_count >= 5:
            score = 20
        elif types_count >= 3:
            score = 10
        else:
            score = 0
        
        # 生成描述
        main_types = sorted(product_types.items(), key=lambda x: x[1]['amount'], reverse=True)[:3]
        main_types_str = '、'.join([f"{k}({v['count']}笔)" for k, v in main_types if v['count'] > 0])
        
        if types_count >= 5:
            description = f"该人员持有{types_count}种不同类型理财产品，包括{main_types_str}，投资结构较为复杂。"
        elif types_count >= 3:
            description = f"该人员持有{types_count}种不同类型理财产品，包括{main_types_str}，投资结构较为多样。"
        else:
            description = f"该人员理财产品种类较少，投资结构相对简单。"
        
        return {
            'score': score,
            'description': description,
            'product_types': product_types,
            'types_count': types_count,
            'main_types': main_types
        }
    
    def _analyze_finance_scale_and_income(self, finance_txns: pd.DataFrame, 
                                       income_yearly: Dict[int, float],
                                       person_profile: Dict[str, Any]) -> Dict[str, Any]:
        """分析理财规模和收入对比"""
        # 计算理财规模
        total_finance_amount = finance_txns['amount'].sum() / 10000  # 转为万元
        
        # 计算年度平均工资
        total_income_yearly = sum(income_yearly.values())
        years = len(income_yearly)
        annual_income = total_income_yearly / years if years > 0 else 0
        
        # 计算理财收入（理财收益）
        # 假设理财赎回金额 - 申购金额 = 理财收益
        redemption_mask = finance_txns['description'].str.contains('赎回', na=False, case=False)
        purchase_mask = finance_txns['description'].str.contains('申购|购入', na=False, case=False)
        
        redemption_amount = finance_txns[redemption_mask]['amount'].sum() if not finance_txns[redemption_mask].empty else 0
        purchase_amount = finance_txns[purchase_mask]['amount'].sum() if not finance_txns[purchase_mask].empty else 0
        
        finance_income = max(0, (redemption_amount - purchase_amount)) / 10000  # 转为万元
        
        # 计算理财资产比例
        # 理财资产比例 = (现有理财余额 + 理财收益) / 总工资收入（作为对比基准）
        # 简化版：理财资产比例 = 总理财金额 / 总工资收入（作为对比基准）
        total_finance = total_finance_amount + finance_income
        finance_ratio = total_finance / (annual_income + 1) if annual_income > 0 else 0
        
        # 计算评分
        score = 0
        if finance_ratio > 10:
            score = 30
        elif finance_ratio > 5:
            score = 20
        elif finance_ratio > 3:
            score = 10
        else:
            score = 0
        
        # 生成描述
        if finance_ratio > 10:
            description = f"该人员理财规模{total_finance:.2f}万元，累计理财收益{finance_income:.2f}万元，理财资产是其年度工资收入的{finance_ratio:.1f}倍，远超正常水平，存在资产来源不明风险。"
        elif finance_ratio > 5:
            description = f"该人员理财规模{total_finance:.2f}万元，理财资产是其年度工资收入的{finance_ratio:.1f}倍，理财积累明显超过收入水平，需关注资金来源。"
        elif finance_ratio > 3:
            description = f"该人员理财规模{total_finance:.2f}万元，理财资产是其年度工资收入的{finance_ratio:.1f}倍，理财规模适中。"
        else:
            description = f"该人员理财规模{total_finance:.2f}万元，理财资产与其收入水平基本匹配。"
        
        return {
            'score': score,
            'description': description,
            'total_finance_amount': total_finance_amount,
            'total_finance_income': finance_income,
            'annual_income': annual_income,
            'finance_ratio': finance_ratio
        }
    
    def _analyze_holding_period(self, finance_txns: pd.DataFrame) -> Dict[str, Any]:
        """分析理财持有期（短期 vs 长期）"""
        # 识别短期理财产品（持有期 < 1年）
        short_term_mask = finance_txns['description'].str.contains('短期|T+|T+[0-9]|活期|七日|一月|三月|六月', na=False, case=False)
        short_term_txns = finance_txns[short_term_mask]
        short_term_count = len(short_term_txns)
        short_term_amount = short_term_txns['amount'].sum() / 10000  # 转为万元
        
        # 识别长期理财产品（持有期 > 3年）
        long_term_mask = finance_txns['description'].str.contains('三年|五年|十年|长期|定期|封闭式', na=False, case=False)
        long_term_txns = finance_txns[long_term_mask]
        long_term_count = len(long_term_txns)
        long_term_amount = long_term_txns['amount'].sum() / 10000
        
        # 计算平均持有期（简化版）
        total_finance = len(finance_txns)
        if total_finance > 0:
            avg_holding_days = 365  # 假设平均持有期1年
            if short_term_count > total_finance * 0.5:
                avg_holding_days = 90  # 短期占多数，平均90天
        else:
            avg_holding_days = 365
        else:
            avg_holding_days = 0
        
        # 计算评分
        score = 0
        if short_term_count > total_finance * 0.7:
            score = 20
        elif short_term_count > total_finance * 0.5:
            score = 10
        elif long_term_count > total_finance * 0.3:
            score = -10  # 长期理财占比高，减分
        else:
            score = 0
        
        # 生成描述
        if short_term_count > total_finance * 0.7:
            description = f"该人员理财产品持有期普遍较短，短期产品占比{short_term_count/total_finance:.1%}，存在资金快进快出特征，需关注其资金用途和背景。"
        elif short_term_count > total_finance * 0.5:
            description = f"该人员短期理财产品占比较高，占比{short_term_count/total_finance:.1%}，存在一定的资金周转需求。"
        else:
            description = f"该人员理财产品持有期较为合理，短期产品占比{short_term_count/total_finance:.1%}，投资期限适中。"
        
        return {
            'score': max(0, score),
            'description': description,
            'short_term_count': short_term_count,
            'short_term_amount': short_term_amount,
            'long_term_count': long_term_count,
            'long_term_amount': long_term_amount,
            'total_finance_count': total_finance,
            'avg_holding_days': avg_holding_days
        }
    
    def _detect_finance_cycling(self, finance_txns: pd.DataFrame) -> Dict[str, Any]:
        """检测理财空转"""
        # 按账户分组
        if 'account_number' not in finance_txns.columns:
            return {
                'score': 0,
                'description': '缺少账户信息，无法分析理财空转',
                'cycle_count': 0,
                'cycle_amount': 0
            }
        
        cycles = []
        
        # 按账户分组，检测空转
        for account in finance_txns['account_number'].unique():
            account_txns = finance_txns[finance_txns['account_number'] == account]
            account_txns = account_txns.sort_values('date')
            
            # 检测短期内的大额进出
            for i in range(len(account_txns) - 1):
                curr_txn = account_txns.iloc[i]
                next_txn = account_txns.iloc[i + 1]
                
                # 时间差（天）
                time_diff = (next_txn['date'] - curr_txn['date']).days
                
                # 检查是否在短时间内（一周内）
                if time_diff <= 7:
                    # 检查是否是理财赎回和申购（一个大额收入，一个大额支出）
                    if (curr_txn['direction'] == 'income' and next_txn['direction'] == 'expense') or \
                       (curr_txn['direction'] == 'expense' and next_txn['direction'] == 'income'):
                        # 检查金额是否基本相等（允许10%的偏差）
                        amount_ratio = min(curr_txn['amount'], next_txn['amount']) / max(curr_txn['amount'], next_txn['amount'], 1)
                        if amount_ratio >= 0.9:  # 允许10%的偏差
                            cycles.append({
                                'account': account,
                                'date1': curr_txn['date'],
                                'date2': next_txn['date'],
                                'amount1': curr_txn['amount'],
                                'amount2': next_txn['amount'],
                                'description1': curr_txn['description'],
                                'description2': next_txn['description'],
                                'time_diff': time_diff
                            })
        
        # 计算循环次数和金额
        cycle_count = len(cycles)
        cycle_amount = sum([c['amount1'] / 10000 for c in cycles])
        
        # 计算评分
        score = 0
        if cycle_count >= 5:
            score = 20
        elif cycle_count >= 3:
            score = 10
        else:
            score = 0
        
        # 生成描述
        if cycle_count >= 5:
            description = f"该人员资金在理财产品间频繁流转，累计{cycle_count}次资金循环，涉及{cycle_amount:.2f}万元，存在明显的资金空转行为，需重点关注。"
        elif cycle_count >= 3:
            description = f"该人员资金在理财产品间存在一定程度的流转，累计{cycle_count}次资金循环，涉及{cycle_amount:.2f}万元，需关注其资金用途。"
        else:
            description = f"该人员理财资金流转相对正常，未见频繁的资金空转行为。"
        
        return {
            'score': score,
            'description': description,
            'cycle_count': cycle_count,
            'cycle_amount': cycle_amount,
            'cycles': cycles[:10]  # 只保留前10个循环
        }
    
    def _analyze_asset_reasonability(self, finance_scale: Dict, product_types: Dict,
                                    property_data: Optional[List[Dict]],
                                    vehicle_data: Optional[List[Dict]],
                                    person_profile: Dict) -> Dict[str, Any]:
        """分析理财与资产的合理性"""
        # 计算房产和车辆资产价值
        property_value = 0
        if property_data:
            for prop in property_data:
                # 房产价值：如果购房时有交易，以交易价格为基准；如果没有交易，以购入时价格计算
                if prop.get('transaction_amount'):
                    property_value += prop['transaction_amount'] * 10000  # 元转元
                elif prop.get('purchase_amount'):
                    property_value += prop['purchase_amount'] * 10000  # 元转元
        
        vehicle_value = 0
        if vehicle_data:
            for vehicle in vehicle_data:
                if vehicle.get('valuation'):
                    vehicle_value += vehicle['valuation'] * 10000  # 元转元
        
        # 理财余额（理财余额）
        finance_balance = finance_scale['total_finance_amount'] * 10000  # 元转元
        
        # 理财收益
        finance_income = finance_scale['total_finance_income'] * 10000  # 元转元
        
        # 总资产 = 房产 + 车辆 + 理财余额 + 理财收益
        total_assets = property_value + vehicle_value + finance_balance + finance_income
        
        # 年度工资收入
        annual_income = finance_scale['annual_income'] * 10000  # 元转元
        
        # 资产与工资对比
        assets_to_salary_ratio = total_assets / (annual_income + 1) if annual_income > 0 else 0
        
        # 计算评分
        score = 0
        if assets_to_salary_ratio > 20:
            score = 30
        elif assets_to_salary_ratio > 10:
            score = 20
        elif assets_to_salary_ratio > 5:
            score = 10
        elif assets_to_salary_ratio < 1:
            score = -10  # 资产低于工资收入，可能存在隐匿资产
        else:
            score = 0
        
        # 生成描述
        if assets_to_salary_ratio > 20:
            description = f"该人员资产总额{total_assets/10000:.2f}万元，是其年度工资收入的{assets_to_salary_ratio:.1f}倍，资产积累明显超过收入水平，可能存在隐匿资产或其他未申报收入。"
        elif assets_to_salary_ratio > 10:
            description = f"该人员资产总额{total_assets/10000:.2f}万元，是其年度工资收入的{assets_to_salary_ratio:.1f}倍，资产积累较高，需关注其资产来源。"
        elif assets_to_salary_ratio > 5:
            description = f"该人员资产总额{total_assets/10000:.2f}万元，是其年度工资收入的{assets_to_salary_ratio:.1f}倍，资产积累水平适中。"
        elif assets_to_salary_ratio < 1:
            description = f"该人员资产总额{total_assets/10000:.2f}万元，低于其年度工资收入{assets_to_salary_ratio:.1f}倍，可能存在大量隐匿资产（现金、未申报房产等），需重点核查其现金持有情况。"
        else:
            description = f"该人员资产总额{total_assets/10000:.2f}万元，与其年度工资收入水平基本匹配。"
        
        return {
            'score': score,
            'description': description,
            'property_value': property_value,
            'vehicle_value': vehicle_value,
            'finance_balance': finance_balance,
            'finance_income': finance_income,
            'total_assets': total_assets,
            'annual_income': annual_income,
            'assets_to_salary_ratio': assets_to_salary_ratio
        }
    
    def _calculate_risk_level(self, total_score: int) -> str:
        """计算风险等级"""
        if total_score >= self.thresholds.risk_score_high:
            return "高风险"
        elif total_score >= 35:  # 降低阈值（从70改为35），使更多人进入"关注级"
            return "关注级"
        elif total_score >= 15:  # 降低阈值（从30改为15），使更多人离开"低风险"
            return "关注级"
        else:
            return "低风险"
    
    def _generate_overall_assessment(self, dimensions: Dict) -> str:
        """生成总体理财特征描述"""
        # 获取各维度评分
        scores = {name: dim['score'] for name, dim in dimensions.items()}
        
        # 找出主要问题维度
        high_risk_dims = [name for name, score in scores.items() if score >= 20]
        medium_risk_dims = [name for name, score in scores.items() if 10 <= score < 20]
        
        features = []
        if high_risk_dims:
            feature_map = {
                'finance_scale': '理财规模异常',
                'product_types': '理财类型复杂',
                'holding_period': '理财期限异常',
                'cycling': '理财空转频繁',
                'asset_reasonability': '资产合理性异常'
            }
            features.extend([feature_map.get(dim, dim) for dim in high_risk_dims])
        elif medium_risk_dims:
            feature_map = {
                'finance_scale': '理财规模偏大',
                'product_types': '理财类型较多',
                'holding_period': '理财期限偏短',
                'cycling': '理财流转较多',
                'asset_reasonability': '资产合理性待核实'
            }
            features.extend([feature_map.get(dim, dim) for dim in medium_risk_dims])
        else:
            features.append('理财投资行为正常')
        
        if features:
            return f"该人员{', '.join(features)}。"
        else:
            return "该人员理财投资行为正常。"
    
    def _generate_audit_descriptions(self, dimensions: Dict) -> List[str]:
        """生成审计描述"""
        descriptions = []
        
        # 理财规模
        finance_scale = dimensions['finance_scale']
        if finance_scale['score'] >= 20:
            descriptions.append(f"该人员理财规模{finance_scale['total_finance_amount']:.2f}万元，累计理财收益{finance_scale['total_finance_income']:.2f}万元，理财资产是其年度工资收入的{finance_scale['finance_ratio']:.1f}倍，远超正常水平，存在资产来源不明风险，需重点核查其理财资金来源。")
        elif finance_scale['score'] >= 10:
            descriptions.append(f"该人员理财规模{finance_scale['total_finance_amount']:.2f}万元，理财资产是其年度工资收入的{finance_scale['finance_ratio']:.1f}倍，理财积累明显超过收入水平，需关注其资金来源。")
        
        # 理财类型
        product_types = dimensions['product_types']
        if product_types['score'] >= 20:
            main_types = ', '.join([f"{k}({v['count']}笔)" for k, v in product_types['main_types'] if v['count'] > 0])
            descriptions.append(f"该人员持有{product_types['types_count']}种不同类型理财产品，包括{main_types}，投资结构较为复杂，需核查其投资风险承受能力及资产配置合理性。")
        elif product_types['score'] >= 10:
            main_types = ', '.join([f"{k}({v['count']}笔)" for k, v in product_types['main_types'] if v['count'] > 0])
            descriptions.append(f"该人员持有{product_types['types_count']}种不同类型理财产品，包括{main_types}，投资结构较为多样，需关注其投资配置合理性。")
        
        # 理财期限
        holding_period = dimensions['holding_period']
        if holding_period['score'] >= 20:
            descriptions.append(f"该人员理财产品持有期普遍较短，短期产品占比{holding_period['short_term_count']/holding_period['total_finance_count']:.1%}，存在资金快进快出特征，需关注其资金用途和背景。")
        elif holding_period['score'] >= 10:
            descriptions.append(f"该人员短期理财产品占比较高，占比{holding_period['short_term_count']/holding_period['total_finance_count']:.1%}，存在一定的资金周转需求。")
        
        # 理财空转
        cycling = dimensions['cycling']
        if cycling['score'] >= 20:
            descriptions.append(f"该人员资金在理财产品间频繁流转，累计{cycling['cycle_count']}次资金循环，涉及{cycling['cycle_amount']:.2f}万元，存在明显的资金空转行为，需重点关注。")
        elif cycling['score'] >= 10:
            descriptions.append(f"该人员资金在理财产品间存在一定程度的流转，累计{cycling['cycle_count']}次资金循环，涉及{cycling['cycle_amount']:.2f}万元，需关注其资金用途。")
        
        # 资产合理性
        asset_reasonability = dimensions['asset_reasonability']
        if asset_reasonability['score'] >= 30:
            descriptions.append(f"该人员资产总额{asset_reasonability['total_assets']/10000:.2f}万元，是其年度工资收入的{asset_reasonability['assets_to_salary_ratio']:.1f}倍，资产积累明显超过收入水平，可能存在隐匿资产或其他未申报收入，需重点核查其现金持有情况。")
        elif asset_reasonability['score'] >= 20:
            descriptions.append(f"该人员资产总额{asset_reasonability['total_assets']/10000:.2f}万元，是其年度工资收入的{asset_reasonability['assets_to_salary_ratio']:.1f}倍，资产积累较高，需关注其资产来源。")
        elif asset_reasonability['score'] < 0:
            descriptions.append(f"该人员资产总额{asset_reasonability['total_assets']/10000:.2f}万元，低于其年度工资收入{asset_reasonability['assets_to_salary_ratio']:.1f}倍，可能存在大量隐匿资产（现金、未申报房产等），需重点核查其现金持有情况。")
        
        return descriptions
    
    def _generate_recommendations(self, dimensions: Dict) -> List[str]:
        """生成建议措施"""
        recommendations = []
        
        # 根据各维度生成建议
        if dimensions['finance_scale']['score'] >= 20:
            recommendations.append("核查其理财资金来源，确认是否有未申报收入或隐匿资产。")
            recommendations.append("获取其银行账户流水，核查理财资金进出链路。")
        
        if dimensions['product_types']['score'] >= 20:
            recommendations.append("核查其投资顾问资质，确认是否存在违规推荐或利益输送。")
            recommendations.append("了解其各类理财产品配置的合理性及风险承受能力。")
        
        if dimensions['holding_period']['score'] >= 20:
            recommendations.append("核查其短期理财产品的资金用途，确认是否存在过桥资金或协助洗钱。")
            recommendations.append("关注其资金快进快出的对手方，确认是否存在异常资金链路。")
        
        if dimensions['cycling']['score'] >= 20:
            recommendations.append("核查其理财资金流转链路，确认是否存在资金空转或洗钱行为。")
            recommendations.append("关注其理财赎回后的资金流向，确认是否流向可疑对手方。")
        
        if dimensions['asset_reasonability']['score'] < 0:
            recommendations.append("重点核查其现金持有情况，确认是否存在大量隐匿现金。")
            recommendations.append("核查其是否有未申报房产或其他未记录资产。")
        
        if dimensions['asset_reasonability']['score'] >= 30:
            recommendations.append("核查其资产来源，确认是否存在未申报收入或非法所得。")
            recommendations.append("调查其家庭成员的资产情况，确认是否存在代持或隐匿资产。")
        
        return recommendations
    
    def _generate_risk_exclusions(self, dimensions: Dict) -> List[str]:
        """生成风险排除说明"""
        exclusions = []
        
        if dimensions['finance_scale']['score'] == 0:
            exclusions.append("无理财规模异常")
        elif dimensions['finance_scale']['score'] <= 5:
            exclusions.append("理财规模基本正常")
        
        if dimensions['product_types']['score'] == 0:
            exclusions.append("理财类型相对简单")
        
        if dimensions['holding_period']['score'] == 0:
            exclusions.append("理财产品持有期基本合理")
        
        if dimensions['cycling']['score'] == 0:
            exclusions.append("无频繁的资金空转行为")
        
        if dimensions['asset_reasonability']['score'] == 0:
            exclusions.append("资产与收入水平基本匹配")
        
        return exclusions
    
    def _identify_red_flags(self, dimensions: Dict) -> List[Dict]:
        """识别红旗标记"""
        red_flags = []
        
        for dimension_name, dimension_data in dimensions.items():
            if dimension_data['score'] >= 20:
                red_flag = {
                    'type': dimension_name,
                    'score': dimension_data['score'],
                    'description': dimension_data['description']
                }
                red_flags.append(red_flag)
        
        return red_flags


# ============================================================================
# 便捷函数：快速分析
# ============================================================================

def quick_analyze_financial_risk(person_profile: Dict[str, Any],
                                     person_transactions: pd.DataFrame,
                                     income_yearly: Dict[int, float],
                                     property_data: Optional[List[Dict]] = None,
                                     vehicle_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """
    快速分析个人理财风险（便捷函数）
    """
    analyzer = FinancialProductAnalyzer()
    return analyzer.analyze(
        person_profile=person_profile,
        person_transactions=person_transactions,
        income_yearly=income_yearly,
        property_data=property_data,
        vehicle_data=vehicle_data
    )


# ============================================================================
# 主函数：分析所有人员的理财风险
# ============================================================================

def analyze_all_persons_financial_risk(profiles: Dict,
                                        person_transactions: Dict,
                                        income_yearly: Dict[str, Dict[int, float]],
                                        property_data: Optional[Dict[str, List[Dict]]] = None,
                                        vehicle_data: Optional[Dict[str, List[Dict]]] = None) -> Dict[str, Any]:
    """
    分析所有人员的理财风险
    """
    logger.info('=' * 60)
    logger.info("开始个人理财风险分析")
    logger.info('=' * 60)
    
    all_persons = set(profiles.keys()) - set(p for p in profiles.keys() if '公司' in p or '实业' in p or '机电' in p or '机械' in p)
    
    results = {}
    for person in all_persons:
        if person not in person_transactions:
            continue
        
        person_profile = profiles.get(person)
        if not person_profile or not person_profile.get('has_data', False):
            continue
        
        person_txns = person_transactions[person]
        person_income_yearly = income_yearly.get(person, {})
        person_property = property_data.get(person, []) if property_data else []
        person_vehicle = vehicle_data.get(person, []) if vehicle_data else []
        
        try:
            result = quick_analyze_financial_risk(
                person_profile=person_profile,
                person_transactions=person_txns,
                income_yearly=person_income_yearly,
                property_data=person_property,
                vehicle_data=person_vehicle
            )
            results[person] = result
            logger.info(f"✅ {person} 理财风险分析完成: 风险等级={result['risk_level']}, 评分={result['risk_score']}")
        except Exception as e:
            logger.error(f"❌ {person} 理财风险分析失败: {str(e)}")
            results[person] = {
                'risk_level': '未知',
                'risk_score': 0,
                'error': str(e)
            }
    
    return results


if __name__ == '__main__':
    # 测试代码
    print("=" * 80)
    print("🔍 专业理财分析模块 - 基于用户的专业审计思路")
    print("=" * 80)
    print()
    
    print("核心审计思路（用户提供）:")
    print("  1. 资产与收入对比：房产+存款+理财+保险等资产与工资性收入对比")
    print("  2. 房产计算逻辑：")
    print("     • 如果房产没有交易过，应该以购入时的价格计算资产")
    print("     • 除非查询数据中没有该笔购房流水，这一点要在房产部分标注出来")
    print("     • 如果房产有交易，增值部分应该算作他的正常收入")
    print("  3. 现金部分应该重点标注，现金一般都是关注重点")
    print("  4. 程序设计原则：前面计算过的，后面尽量引用而不重新计算")
    print("  5. 程序已有数据要充分利用")
    print()
    
    print("模块功能:")
    print("  1. 深度理财分析（类型、期限、收益率、资金空转）")
    print("  2. 理财与收入对比")
    print("  3. 理财与资产合理性")
    print("  4. 理财风险识别")
    print()
    
    print("📊 评分逻辑:")
    print("  • 理财规模 vs 收入：理财资产 > 10倍年收入 = 30分（高风险）")
    print("  • 理财规模 vs 收入：理财资产 > 5倍年收入 = 20分（关注级）")
    print("  • 理财规模 vs 收入：理财资产 > 3倍年收入 = 10分")
    print("  • 理财类型：>= 5种类型 = 20分（高风险）")
    print("  • 理财期限：短期占比 > 70% = 20分（高风险）")
    print("  • 理财空转：>= 5次循环 = 20分（高风险）")
    print("  • 资产合理性：资产 > 20倍年收入 = 30分（高风险）")
    print("  • 资产合理性：资产 < 1倍年收入 = -10分（关注级，可能存在隐匿资产）")
    print()
    
    print("🚀 下一步：")
    print("  1. 在报告生成脚本中集成此模块")
    print("  2. 为每个人员生成理财风险分析部分")
    print("  3. 显示完整的理财分析：规模、类型、期限、空转、资产合理性")
    print("  4. 生成专业的审计描述和建议")
    print()
    
    print("=" * 80)
    print("✅ 专业理财分析模块重新创建完成！")
    print("=" * 80)
