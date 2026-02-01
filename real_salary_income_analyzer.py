#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实工资收入分析器

功能：
1. 从交易数据中识别工资收入
2. 处理早期数据缺失问题
3. 按年统计工资收入
4. 计算年均工资
5. 生成数据质量说明
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re


@dataclass
class SalaryThresholds:
    """工资识别阈值配置"""
    low_salary_threshold_ratio: float = 0.3  # 低于年均工资30%的年份标记为数据缺失

    @classmethod
    def custom_thresholds(cls, **kwargs):
        """自定义阈值"""
        for key, value in kwargs.items():
            if hasattr(cls, key):
                setattr(cls, key, value)


class RealSalaryIncomeAnalyzer:
    """
    真实工资收入分析器

    核心功能：
    1. 识别真正的工资收入
    2. 处理早期数据缺失问题
    3. 按年统计工资收入
    4. 计算年均工资
    5. 生成数据质量说明
    """

    def __init__(self, thresholds: Optional[SalaryThresholds] = None):
        """初始化分析器"""
        self.thresholds = thresholds or SalaryThresholds()

        # 对方账户关键词
        self.salary_account_keywords = [
            '工资', '代发', '薪金', '奖金', '绩效',
            '社保', '公积金', '税务局', '财政局',
            '人力资源', '人事', '发薪'
        ]

        # 交易摘要关键词
        self.salary_desc_keywords = [
            '工资', '奖金', '薪', '绩效', '年终奖',
            '十三薪', '过节费', '高温补贴', '交通补贴',
            '代发工资', '代发奖金', '工资发放', '薪金发放',
            '基本工资', '岗位工资', '技能工资', '绩效工资'
        ]

        # 排除关键词（非工资收入）
        # 注意：不能排除"补贴"，因为补贴通常是工资的一部分
        self.exclude_keywords = [
            '报销', '退款', '转入', '上存',
            '提现', '取款', # 提现/取款不是工资，但可以保留用于对账
            '利息', '股息', '分红',
            '理财', '基金', '投资',
            '还款', '还贷', '贷款', '按揭'
        ]

    def analyze(self,
              transactions: pd.DataFrame,
              person_name: str) -> Dict[str, Any]:
        """
        分析真实工资收入

        Args:
            transactions: 交易明细（DataFrame）
            person_name: 当前人员姓名

        Returns:
            工资收入分析结果字典
        """
        # 1. 识别工资交易
        salary_df = self._identify_salary_transactions(transactions, person_name)

        if salary_df.empty:
            return {
                'total_salary': 0,
                'average_salary': 0,
                'years_count': 0,
                'yearly_salary': {},
                'salary_transactions_count': 0,
                'low_salary_years': {},
                'data_quality_note': '未识别到工资收入数据，可能交易数据缺失或关键字不匹配。'
            }

        # 2. 按年统计工资
        salary_df['year'] = pd.to_datetime(salary_df['date']).dt.year
        yearly_salary = salary_df.groupby('year')['amount'].sum() / 10000  # 转换为万元
        yearly_salary_dict = yearly_salary.to_dict()

        # 3. 计算统计信息
        total_salary = yearly_salary.sum()
        years_count = len(yearly_salary)

        # 4. 计算年均工资（只计算有数据的年份）
        if years_count > 0:
            average_salary = total_salary / years_count
        else:
            average_salary = 0

        # 5. 识别数据缺失年份
        low_salary_years, data_quality_note = self._identify_missing_data_years(
            yearly_salary_dict, average_salary
        )

        # 6. 生成统计摘要
        summary = self._generate_summary(
            person_name, total_salary, average_salary, years_count,
            yearly_salary_dict, low_salary_years
        )

        return {
            'total_salary': total_salary,
            'average_salary': average_salary,
            'years_count': years_count,
            'yearly_salary': yearly_salary_dict,
            'salary_transactions_count': len(salary_df),
            'low_salary_years': low_salary_years,
            'data_quality_note': data_quality_note,
            'summary': summary
        }

    def _identify_salary_transactions(self,
                                     transactions: pd.DataFrame,
                                     person_name: str) -> pd.DataFrame:
        """识别工资交易"""

        # 只分析收入交易
        income_df = transactions[transactions['direction'] == 'income'].copy()

        if income_df.empty:
            return income_df

        # 1. 排除明确的非工资收入（只排除明确的，不用 str.contains）
        # 创建排除条件
        def is_non_wage(row):
            desc = str(row.get('description', '')).lower()
            
            # 明确的非工资关键词
            non_wage_exact = ['报销', '退款', '利息', '股息', '分红']
            if any(nw in desc for nw in non_wage_exact):
                return True
            
            # 理财相关（但不包括工资转理财）
            fund_keywords = ['赎回', '申购', '买入', '卖出', '起息', '产品']
            if any(fk in desc for fk in fund_keywords):
                # 如果同时包含"工资"、"奖金"等，可能是工资转理财，保留
                if any(sk in desc for sk in ['工资', '奖金', '薪', '绩效']):
                    return False  # 可能是工资转理财，保留
                return True  # 纯理财，排除
            
            return False
        
        # 应用排除
        income_df = income_df[~income_df.apply(is_non_wage, axis=1)]

        # 2. 匹配对方账户关键词
        account_mask = income_df['counterparty'].str.contains(
            '|'.join(self.salary_account_keywords), na=False, case=False
        )

        # 3. 匹配交易摘要关键词
        desc_mask = income_df['description'].str.contains(
            '|'.join(self.salary_desc_keywords), na=False, case=False
        )

        # 4. 匹配固定金额（如整万的工资）
        # 工资通常是整数（万为单位）
        round_amount_mask = (income_df['amount'] % 10000 == 0) & (income_df['amount'] > 0)

        # 5. 合并所有匹配条件
        salary_mask = account_mask | desc_mask | round_amount_mask

        # 6. 进一步筛选：合理的工资范围
        # 注意：很多工资是按年或按季度发放的，所以单笔金额可能很大
        # 不能用月工资范围来过滤，应该放宽条件

        # 只排除明显不合理的极小金额
        reasonable_salary_mask = (income_df['amount'] >= 1000)  # 排除 < 1000 元的

        # 不再限制单笔最大金额，因为工资可能是按年、按季度发放的
        # 如果单笔金额确实很大，应该在关键词匹配时就排除（如"投资"、"理财"）
        
        # 7. 最终匹配（不需要再过滤了，因为工资可能是按年、按季度发放的）
        salary_df = income_df[salary_mask & reasonable_salary_mask]
        
        return salary_df

    def _identify_missing_data_years(self,
                                    yearly_salary: Dict[int, float],
                                    average_salary: float) -> tuple:
        """识别数据缺失年份"""

        if not yearly_salary or average_salary == 0:
            return {}, "无工资数据"

        low_salary_years = {}

        # 找出工资异常低的年份
        for year, salary in yearly_salary.items():
            if salary < average_salary * self.thresholds.low_salary_threshold_ratio:
                low_salary_years[year] = salary

        # 生成数据质量说明
        if not low_salary_years:
            data_quality_note = "工资数据完整，无缺失年份。"
        else:
            low_years = sorted(low_salary_years.keys())
            recent_years = [y for y in low_years if y >= 2010]
            very_old_years = [y for y in low_years if y < 2010]

            notes = []
            if recent_years:
                notes.append(f"{recent_years}年工资收入明显偏低（可能存在银行数据提取不完整的问题）")
            if very_old_years:
                notes.append(f"{very_old_years}年工资收入明显偏低（可能为早期银行数据缺失）")

            # 参考建议
            if low_years:
                max_low_year = max(low_years)
                ref_years = [y for y in low_years if y > max_low_year][:3]
                if ref_years:
                    notes.append(f"建议参考{ref_years}年的工资水平进行估算（{ref_years[0]}年：{yearly_salary[ref_years[0]]:.2f}万元）")

            data_quality_note = " ".join(notes)

        return low_salary_years, data_quality_note

    def _generate_summary(self,
                         person_name: str,
                         total_salary: float,
                         average_salary: float,
                         years_count: int,
                         yearly_salary: Dict[int, float],
                         low_salary_years: Dict[int, float]) -> str:
        """生成统计摘要"""

        summary_parts = [
            f"{person_name}的工资收入分析：",
            f"识别出工资收入{total_salary/10000:.2f}万元，跨{years_count}年，年均工资{average_salary/10000:.2f}万元。"
        ]

        if low_salary_years:
            low_years = sorted(low_salary_years.keys())
            recent_low_years = [y for y in low_years if y >= 2010]
            if recent_low_years:
                summary_parts.append(f"注意：{recent_low_years}年工资收入偏低，可能存在数据缺失问题。")
            else:
                summary_parts.append(f"注意：{low_years}年工资收入偏低，可能为早期银行数据缺失。")

        return " ".join(summary_parts)


if __name__ == '__main__':
    print("真实工资收入分析器模块加载成功")
