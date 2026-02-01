#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收支匹配度分析器

功能：
1. 计算收支匹配度
2. 生成收支缺口分析
3. 提供数据质量说明
4. 生成审计描述
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MatchThresholds:
    """匹配度分析阈值配置"""
    coverage_ratio_high: float = 80.0  # 工资覆盖率高阈值
    coverage_ratio_medium: float = 50.0  # 工资覆盖率中阈值
    coverage_ratio_low: float = 30.0  # 工资覆盖率低阈值
    
    @classmethod
    def custom_thresholds(cls, **kwargs):
        """自定义阈值"""
        for key, value in kwargs.items():
            if hasattr(cls, key):
                setattr(cls, key, value)


class IncomeExpenseMatchAnalyzer:
    """
    收支匹配度分析器
    
    核心功能：
    1. 计算工资覆盖率（工资收入 / 有效消费）
    2. 生成收支缺口分析
    3. 识别额外收入来源
    4. 生成专业的审计描述
    5. 提供数据质量说明
    """
    
    def __init__(self, thresholds: Optional[MatchThresholds] = None):
        """初始化分析器"""
        self.thresholds = thresholds or MatchThresholds()
        
        self.description_templates = {
            "good_match": "该人员工资性收入累计{real_salary:.2f}万元，与有效消费支出{effective_expense:.2f}万元基本匹配，工资收入能够覆盖{coverage_ratio:.1f}%的消费支出，收入来源相对稳定，消费模式未见明显异常。",
            "medium_match": "该人员工资性收入累计{real_salary:.2f}万元，与有效消费支出{effective_expense:.2f}万元存在一定差距，工资收入仅能覆盖{coverage_ratio:.1f}%的消费支出，存在{gap:.2f}万元的资金缺口，需关注其他收入来源的合理性。",
            "poor_match": "该人员工资性收入累计{real_salary:.2f}万元，但同期有效消费支出{effective_expense:.2f}万元，存在{gap:.2f}万元的收支缺口，工资收入仅能覆盖{coverage_ratio:.1f}%的消费支出，收入结构明显失衡，存在资金来源不明风险。{extra_income_note}",
            "serious_mismatch": "该人员工资性收入累计{real_salary:.2f}万元，但同期有效消费支出{effective_expense:.2f}万元，存在{gap:.2f}万元的巨额收支缺口，工资收入仅能覆盖{coverage_ratio:.1f}%的消费支出，存在严重的资金来源不明风险，需深入核查其其他收入来源的真实性和稳定性。"
        }
    
    def analyze(self,
              real_salary: float,
              effective_expense: float,
              extra_income: float = 0,
              extra_income_types: Optional[list] = None,
              data_quality_note: str = "") -> Dict[str, Any]:
        """
        分析收支匹配度
        
        Args:
            real_salary: 真实工资收入（万元）
            effective_expense: 有效消费支出（万元）
            extra_income: 额外收入（万元）
            extra_income_types: 额外收入类型列表
            data_quality_note: 数据质量说明
        
        Returns:
            分析结果字典
        """
        # 计算关键指标
        total_income = real_salary + extra_income
        gap = effective_expense - real_salary
        coverage_ratio = (real_salary / effective_expense * 100) if effective_expense > 0 else 100
        extra_ratio = (extra_income / total_income * 100) if total_income > 0 else 0
        
        # 计算评分
        score = 0
        if coverage_ratio >= self.thresholds.coverage_ratio_high:
            score = 5  # 收支基本匹配
        elif coverage_ratio >= self.thresholds.coverage_ratio_medium:
            score = 10  # 收支匹配度偏低
        elif coverage_ratio >= self.thresholds.coverage_ratio_low:
            score = 15  # 收支不匹配
        else:
            score = 20  # 收支严重不匹配
        
        # 额外收入扣分（如果额外收入占比高）
        if extra_ratio > 50 and score < 15:
            score = min(20, score - 5)
        
        # 判断风险等级
        if coverage_ratio >= self.thresholds.coverage_ratio_high:
            risk_level = "低风险"
        elif coverage_ratio >= self.thresholds.coverage_ratio_medium:
            risk_level = "关注级"
        else:
            risk_level = "高风险"
        
        # 生成描述
        description = self._generate_description(
            coverage_ratio, real_salary, effective_expense, 
            gap, extra_income, extra_income_types, data_quality_note
        )
        
        # 生成证据
        evidence = [
            {"type": "真实工资收入", "value": f"{real_salary:.2f}万元", "description": "识别出的真实工资收入总额"},
            {"type": "有效消费支出", "value": f"{effective_expense:.2f}万元", "description": "剔除空转后的真实消费支出"},
            {"type": "收支缺口", "value": f"{gap:.2f}万元", "description": f"消费支出与工资收入的差额（{'盈余' if gap < 0 else '缺口'}）"},
            {"type": "工资覆盖率", "value": f"{coverage_ratio:.1f}%", "description": "工资收入对消费的覆盖比例"}
        ]
        
        if extra_income > 0:
            evidence.append({
                "type": "额外收入",
                "value": f"{extra_income:.2f}万元",
                "description": f"除工资外的其他收入，占总收入的{extra_ratio:.1f}%"
            })
        
        # 生成红旗标记
        red_flags = []
        
        if coverage_ratio < self.thresholds.coverage_ratio_low:
            red_flags.append({
                "type": "收支严重失衡",
                "strength": "强",
                "description": f"工资收入仅能覆盖{coverage_ratio:.1f}%的消费支出，存在{gap:.2f}万元的巨额资金缺口"
            })
        elif coverage_ratio < self.thresholds.coverage_ratio_medium:
            red_flags.append({
                "type": "收支失衡",
                "strength": "中",
                "description": f"工资收入仅能覆盖{coverage_ratio:.1f}%的消费支出，存在{gap:.2f}万元的资金缺口"
            })
        
        if extra_ratio > 50:
            red_flags.append({
                "type": "收入来源复杂",
                "strength": "中",
                "description": f"额外收入占比达{extra_ratio:.1f}%，收入来源相对复杂，需核查其真实性和合规性"
            })
        
        return {
            "score": score,
            "risk_level": risk_level,
            "description": description,
            "evidence": evidence,
            "metrics": {
                "real_salary": real_salary,
                "effective_expense": effective_expense,
                "total_income": total_income,
                "gap": gap,
                "coverage_ratio": coverage_ratio,
                "extra_income": extra_income,
                "extra_ratio": extra_ratio,
                "extra_income_types": extra_income_types or []
            },
            "data_quality_note": data_quality_note,
            "red_flags": red_flags
        }
    
    def _generate_description(self,
                           coverage_ratio: float,
                           real_salary: float,
                           effective_expense: float,
                           gap: float,
                           extra_income: float,
                           extra_income_types: Optional[list],
                           data_quality_note: str) -> str:
        """生成描述"""
        
        # 根据覆盖率选择模板
        if coverage_ratio >= self.thresholds.coverage_ratio_high:
            template_key = "good_match"
        elif coverage_ratio >= self.thresholds.coverage_ratio_medium:
            template_key = "medium_match"
        elif coverage_ratio >= self.thresholds.coverage_ratio_low:
            template_key = "poor_match"
        else:
            template_key = "serious_mismatch"
        
        template = self.description_templates[template_key]
        
        # 处理额外收入说明
        extra_income_note = ""
        if extra_income > 0 and extra_income_types:
            income_types_str = "、".join(extra_income_types[:3])
            if len(extra_income_types) > 3:
                income_types_str += f" 等{len(extra_income_types)}种"
            extra_income_note = f" 该人员收入中包含{income_types_str}等额外劳务收入，累计{extra_income:.2f}万元。"
        
        # 替换模板中的占位符
        description = template.format(
            real_salary=real_salary,
            effective_expense=effective_expense,
            coverage_ratio=coverage_ratio,
            gap=gap,
            extra_income_note=extra_income_note
        )
        
        # 添加数据质量说明
        if data_quality_note:
            description += f" {data_quality_note}"
        
        return description


if __name__ == '__main__':
    print("收支匹配度分析器模块加载成功")
