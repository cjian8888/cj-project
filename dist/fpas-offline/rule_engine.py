#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务规则推理引擎

【模块定位】
基于规则的审计推理引擎，用于：
1. 定义和执行纪检监察审计业务规则
2. 支持规则的动态配置和组合
3. 提供规则优先级和冲突解决机制
4. 生成规则推理报告

【审计价值】
- 将审计经验固化为可执行的规则
- 支持规则的灵活配置和调整
- 提高审计分析的标准化和可追溯性

【技术实现】
- 规则定义：基于Python函数的规则定义
- 规则执行：支持规则链和规则组
- 规则优先级：支持规则权重和优先级
- 规则冲突：支持冲突检测和解决
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json

import config
import utils

logger = utils.setup_logger(__name__)


class RulePriority(Enum):
    """规则优先级"""
    CRITICAL = 5  # 极高优先级
    HIGH = 4      # 高优先级
    MEDIUM = 3    # 中优先级
    LOW = 2       # 低优先级
    INFO = 1      # 信息级


class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = "critical"  # 极高风险
    HIGH = "high"          # 高风险
    MEDIUM = "medium"      # 中风险
    LOW = "low"           # 低风险
    INFO = "info"          # 信息


@dataclass
class RuleResult:
    """规则执行结果"""
    rule_id: str
    rule_name: str
    passed: bool
    risk_level: RiskLevel
    score: float  # 风险评分 0-100
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Rule:
    """业务规则定义"""
    rule_id: str
    rule_name: str
    description: str
    priority: RulePriority
    risk_level: RiskLevel
    condition: Callable[[Dict[str, Any]], bool]  # 规则条件函数
    action: Callable[[Dict[str, Any]], RuleResult]  # 规则执行函数
    enabled: bool = True
    tags: List[str] = field(default_factory=list)


class RuleEngine:
    """
    业务规则推理引擎
    
    功能：
    1. 规则注册和管理
    2. 规则执行和推理
    3. 规则结果聚合
    4. 规则报告生成
    
    【P2 优化 - 2026-01-18】
    5. 支持从 YAML 配置文件加载规则参数
    """
    
    # 默认配置文件路径
    DEFAULT_CONFIG_PATH = "config/rules.yaml"
    
    def __init__(self, config_path: str = None):
        self.rules: Dict[str, Rule] = {}
        self.rule_groups: Dict[str, List[str]] = {}
        self.rule_config: Dict[str, Any] = {}
        
        # 加载配置
        if config_path:
            self.load_config(config_path)
        else:
            self._try_load_default_config()
        
        self._register_default_rules()
    
    def load_config(self, config_path: str) -> bool:
        """
        从 YAML 文件加载规则配置
        
        Args:
            config_path: YAML 配置文件路径
            
        Returns:
            是否加载成功
        """
        try:
            import yaml
            import os
            
            if not os.path.exists(config_path):
                logger.warning(f'规则配置文件不存在: {config_path}')
                return False
            
            with open(config_path, 'r', encoding='utf-8') as f:
                self.rule_config = yaml.safe_load(f) or {}
            
            logger.info(f'从 {config_path} 加载规则配置成功')
            return True
            
        except ImportError:
            logger.warning('PyYAML 未安装，跳过配置加载。可通过 pip install pyyaml 安装')
            return False
        except Exception as e:
            logger.error(f'加载规则配置失败: {e}')
            return False
    
    def _try_load_default_config(self):
        """尝试加载默认配置文件"""
        import os
        default_path = os.path.join(os.path.dirname(__file__), self.DEFAULT_CONFIG_PATH)
        if os.path.exists(default_path):
            self.load_config(default_path)
    
    def get_rule_param(self, group: str, rule: str, param: str, default: Any = None) -> Any:
        """
        获取规则参数
        
        Args:
            group: 规则组名（如 'fund_anomaly'）
            rule: 规则名（如 'large_cash_income'）
            param: 参数名（如 'threshold'）
            default: 默认值
            
        Returns:
            参数值
        """
        try:
            return self.rule_config.get(group, {}).get(rule, {}).get(param, default)
        except Exception:
            return default
    
    def register_rule(self, rule: Rule):
        """注册规则"""
        self.rules[rule.rule_id] = rule
        logger.debug(f'注册规则: {rule.rule_id} - {rule.rule_name}')
    
    def unregister_rule(self, rule_id: str):
        """注销规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.debug(f'注销规则: {rule_id}')
    
    def enable_rule(self, rule_id: str):
        """启用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
    
    def disable_rule(self, rule_id: str):
        """禁用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
    
    def create_rule_group(self, group_name: str, rule_ids: List[str]):
        """创建规则组"""
        self.rule_groups[group_name] = rule_ids
        logger.debug(f'创建规则组: {group_name} 包含 {len(rule_ids)} 条规则')
    
    def get_rules_by_tag(self, tag: str) -> List[Rule]:
        """按标签获取规则"""
        return [rule for rule in self.rules.values() if tag in rule.tags]
    
    def get_rules_by_priority(self, priority: RulePriority) -> List[Rule]:
        """按优先级获取规则"""
        return [rule for rule in self.rules.values() if rule.priority == priority]
    
    def execute_rule(self, rule_id: str, context: Dict[str, Any]) -> Optional[RuleResult]:
        """执行单条规则"""
        rule = self.rules.get(rule_id)
        if not rule:
            logger.warning(f'规则不存在: {rule_id}')
            return None
        
        if not rule.enabled:
            logger.debug(f'规则已禁用: {rule_id}')
            return None
        
        try:
            # 检查条件
            if rule.condition(context):
                # 执行规则
                result = rule.action(context)
                logger.debug(f'规则执行: {rule_id} - {result.risk_level.value} - {result.score}')
                return result
            else:
                logger.debug(f'规则条件不满足: {rule_id}')
                return None
        except Exception as e:
            logger.error(f'规则执行失败: {rule_id} - {e}')
            return None
    
    def execute_rule_group(self, group_name: str, context: Dict[str, Any]) -> List[RuleResult]:
        """执行规则组"""
        rule_ids = self.rule_groups.get(group_name, [])
        results = []
        
        for rule_id in rule_ids:
            result = self.execute_rule(rule_id, context)
            if result:
                results.append(result)
        
        return results
    
    def execute_all_rules(self, context: Dict[str, Any], 
                        tags: Optional[List[str]] = None) -> List[RuleResult]:
        """执行所有规则（可按标签过滤）"""
        results = []
        
        # 按优先级排序
        sorted_rules = sorted(
            self.rules.values(),
            key=lambda r: r.priority.value,
            reverse=True
        )
        
        for rule in sorted_rules:
            # 标签过滤
            if tags and not any(tag in rule.tags for tag in tags):
                continue
            
            result = self.execute_rule(rule.rule_id, context)
            if result:
                results.append(result)
        
        return results
    
    def aggregate_results(self, results: List[RuleResult]) -> Dict[str, Any]:
        """聚合规则执行结果"""
        if not results:
            return {
                'total_rules': 0,
                'passed_rules': 0,
                'failed_rules': 0,
                'risk_levels': {},
                'average_score': 0.0,
                'critical_issues': [],
                'high_issues': [],
                'medium_issues': [],
                'low_issues': []
            }
        
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        
        risk_levels = {}
        for level in RiskLevel:
            risk_levels[level.value] = sum(1 for r in results if r.risk_level == level)
        
        avg_score = np.mean([r.score for r in results])
        
        critical_issues = [r for r in results if r.risk_level == RiskLevel.CRITICAL]
        high_issues = [r for r in results if r.risk_level == RiskLevel.HIGH]
        medium_issues = [r for r in results if r.risk_level == RiskLevel.MEDIUM]
        low_issues = [r for r in results if r.risk_level == RiskLevel.LOW]
        
        return {
            'total_rules': len(results),
            'passed_rules': passed,
            'failed_rules': failed,
            'risk_levels': risk_levels,
            'average_score': avg_score,
            'critical_issues': critical_issues,
            'high_issues': high_issues,
            'medium_issues': medium_issues,
            'low_issues': low_issues
        }
    
    def generate_report(self, results: List[RuleResult], output_path: str) -> str:
        """生成规则推理报告"""
        aggregation = self.aggregate_results(results)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('业务规则推理报告\n')
            f.write('='*60 + '\n')
            f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
            
            # 汇总信息
            f.write('一、执行汇总\n')
            f.write('-'*40 + '\n')
            f.write(f'执行规则数: {aggregation["total_rules"]}\n')
            f.write(f'通过规则数: {aggregation["passed_rules"]}\n')
            f.write(f'失败规则数: {aggregation["failed_rules"]}\n')
            f.write(f'平均风险评分: {aggregation["average_score"]:.2f}\n\n')
            
            # 风险等级分布
            f.write('二、风险等级分布\n')
            f.write('-'*40 + '\n')
            for level, count in aggregation['risk_levels'].items():
                f.write(f'{level.upper()}: {count}\n')
            f.write('\n')
            
            # 极高风险问题
            if aggregation['critical_issues']:
                f.write('三、极高风险问题\n')
                f.write('-'*40 + '\n')
                f.write('★ 需要立即关注和处置\n\n')
                for i, issue in enumerate(aggregation['critical_issues'], 1):
                    f.write(f'{i}. [{issue.rule_id}] {issue.rule_name}\n')
                    f.write(f'   风险评分: {issue.score:.2f}\n')
                    f.write(f'   说明: {issue.message}\n')
                f.write('\n')
            
            # 高风险问题
            if aggregation['high_issues']:
                f.write('四、高风险问题\n')
                f.write('-'*40 + '\n')
                f.write('★ 需要重点关注和核查\n\n')
                for i, issue in enumerate(aggregation['high_issues'], 1):
                    f.write(f'{i}. [{issue.rule_id}] {issue.rule_name}\n')
                    f.write(f'   风险评分: {issue.score:.2f}\n')
                    f.write(f'   说明: {issue.message}\n')
                f.write('\n')
            
            # 中风险问题
            if aggregation['medium_issues']:
                f.write('五、中风险问题\n')
                f.write('-'*40 + '\n')
                for i, issue in enumerate(aggregation['medium_issues'], 1):
                    f.write(f'{i}. [{issue.rule_id}] {issue.rule_name}\n')
                    f.write(f'   风险评分: {issue.score:.2f}\n')
                    f.write(f'   说明: {issue.message}\n')
                f.write('\n')
            
            # 低风险问题
            if aggregation['low_issues']:
                f.write('六、低风险问题\n')
                f.write('-'*40 + '\n')
                for i, issue in enumerate(aggregation['low_issues'], 1):
                    f.write(f'{i}. [{issue.rule_id}] {issue.rule_name}\n')
                    f.write(f'   风险评分: {issue.score:.2f}\n')
                    f.write(f'   说明: {issue.message}\n')
                f.write('\n')
            
            # 详细结果
            f.write('七、详细执行结果\n')
            f.write('-'*40 + '\n')
            for result in results:
                f.write(f'[{result.rule_id}] {result.rule_name}\n')
                f.write(f'  通过: {result.passed}\n')
                f.write(f'  风险等级: {result.risk_level.value}\n')
                f.write(f'  风险评分: {result.score:.2f}\n')
                f.write(f'  说明: {result.message}\n')
                if result.details:
                    f.write(f'  详情: {json.dumps(result.details, ensure_ascii=False)}\n')
                f.write('\n')
        
        logger.info(f'规则推理报告已生成: {output_path}')
        return output_path
    
    def _register_default_rules(self):
        """注册默认规则"""
        # 资金异常规则组
        self._register_fund_anomaly_rules()
        
        # 交易行为规则组
        self._register_transaction_behavior_rules()
        
        # 关联关系规则组
        self._register_relationship_rules()
        
        # 资产负债规则组
        self._register_asset_liability_rules()
    
    def _register_fund_anomaly_rules(self):
        """注册资金异常规则"""
        
        # 规则1: 大额现金收入
        def large_cash_income_condition(ctx):
            return ctx.get('max_cash_income', 0) > 50000
        
        def large_cash_income_action(ctx):
            amount = ctx.get('max_cash_income', 0)
            score = min(100, amount / 1000)
            return RuleResult(
                rule_id='R001',
                rule_name='大额现金收入',
                passed=False,
                risk_level=RiskLevel.HIGH if amount > 100000 else RiskLevel.MEDIUM,
                score=score,
                message=f'发现大额现金收入 {amount/10000:.2f}万元',
                details={'amount': amount}
            )
        
        self.register_rule(Rule(
            rule_id='R001',
            rule_name='大额现金收入',
            description='检测单笔或累计大额现金收入',
            priority=RulePriority.HIGH,
            risk_level=RiskLevel.HIGH,
            condition=large_cash_income_condition,
            action=large_cash_income_action,
            tags=['fund', 'cash', 'income']
        ))
        
        # 规则2: 收支严重失衡
        def income_expense_imbalance_condition(ctx):
            income = ctx.get('total_income', 0)
            expense = ctx.get('total_expense', 0)
            return income > 0 and expense > income * 2
        
        def income_expense_imbalance_action(ctx):
            income = ctx.get('total_income', 0)
            expense = ctx.get('total_expense', 0)
            ratio = expense / income if income > 0 else 0
            score = min(100, (ratio - 2) * 20)
            return RuleResult(
                rule_id='R002',
                rule_name='收支严重失衡',
                passed=False,
                risk_level=RiskLevel.HIGH if ratio > 5 else RiskLevel.MEDIUM,
                score=score,
                message=f'支出是收入的 {ratio:.2f} 倍',
                details={'income': income, 'expense': expense, 'ratio': ratio}
            )
        
        self.register_rule(Rule(
            rule_id='R002',
            rule_name='收支严重失衡',
            description='检测支出远超收入的异常情况',
            priority=RulePriority.HIGH,
            risk_level=RiskLevel.HIGH,
            condition=income_expense_imbalance_condition,
            action=income_expense_imbalance_action,
            tags=['fund', 'balance']
        ))
        
        # 规则3: 短期大额资金流入
        def short_term_large_inflow_condition(ctx):
            return ctx.get('max_single_income', 0) > 100000
        
        def short_term_large_inflow_action(ctx):
            amount = ctx.get('max_single_income', 0)
            score = min(100, amount / 2000)
            return RuleResult(
                rule_id='R003',
                rule_name='短期大额资金流入',
                passed=False,
                risk_level=RiskLevel.HIGH if amount > 500000 else RiskLevel.MEDIUM,
                score=score,
                message=f'发现单笔大额收入 {amount/10000:.2f}万元',
                details={'amount': amount}
            )
        
        self.register_rule(Rule(
            rule_id='R003',
            rule_name='短期大额资金流入',
            description='检测单笔大额资金流入',
            priority=RulePriority.HIGH,
            risk_level=RiskLevel.HIGH,
            condition=short_term_large_inflow_condition,
            action=short_term_large_inflow_action,
            tags=['fund', 'income', 'large']
        ))
        
        # 创建规则组
        self.create_rule_group('fund_anomaly', ['R001', 'R002', 'R003'])
    
    def _register_transaction_behavior_rules(self):
        """注册交易行为规则"""
        
        # 规则4: 频繁小额现金交易
        def frequent_small_cash_condition(ctx):
            return ctx.get('small_cash_count', 0) > 20
        
        def frequent_small_cash_action(ctx):
            count = ctx.get('small_cash_count', 0)
            score = min(100, count * 2)
            return RuleResult(
                rule_id='R004',
                rule_name='频繁小额现金交易',
                passed=False,
                risk_level=RiskLevel.MEDIUM,
                score=score,
                message=f'发现 {count} 笔小额现金交易',
                details={'count': count}
            )
        
        self.register_rule(Rule(
            rule_id='R004',
            rule_name='频繁小额现金交易',
            description='检测频繁的小额现金交易',
            priority=RulePriority.MEDIUM,
            risk_level=RiskLevel.MEDIUM,
            condition=frequent_small_cash_condition,
            action=frequent_small_cash_action,
            tags=['transaction', 'cash', 'frequency']
        ))
        
        # 规则5: 节假日大额交易
        def holiday_large_transaction_condition(ctx):
            return ctx.get('holiday_large_count', 0) > 0
        
        def holiday_large_transaction_action(ctx):
            count = ctx.get('holiday_large_count', 0)
            score = min(100, count * 30)
            return RuleResult(
                rule_id='R005',
                rule_name='节假日大额交易',
                passed=False,
                risk_level=RiskLevel.HIGH if count > 3 else RiskLevel.MEDIUM,
                score=score,
                message=f'发现 {count} 笔节假日大额交易',
                details={'count': count}
            )
        
        self.register_rule(Rule(
            rule_id='R005',
            rule_name='节假日大额交易',
            description='检测节假日的大额交易',
            priority=RulePriority.HIGH,
            risk_level=RiskLevel.HIGH,
            condition=holiday_large_transaction_condition,
            action=holiday_large_transaction_action,
            tags=['transaction', 'holiday', 'timing']
        ))
        
        # 规则6: 固定频率转账
        def fixed_frequency_transfer_condition(ctx):
            return ctx.get('fixed_frequency_count', 0) > 0
        
        def fixed_frequency_transfer_action(ctx):
            count = ctx.get('fixed_frequency_count', 0)
            score = min(100, count * 25)
            return RuleResult(
                rule_id='R006',
                rule_name='固定频率转账',
                passed=False,
                risk_level=RiskLevel.HIGH if count > 3 else RiskLevel.MEDIUM,
                score=score,
                message=f'发现 {count} 个固定频率转账模式',
                details={'count': count}
            )
        
        self.register_rule(Rule(
            rule_id='R006',
            rule_name='固定频率转账',
            description='检测固定频率的转账模式',
            priority=RulePriority.HIGH,
            risk_level=RiskLevel.HIGH,
            condition=fixed_frequency_transfer_condition,
            action=fixed_frequency_transfer_action,
            tags=['transaction', 'frequency', 'pattern']
        ))
        
        # 创建规则组
        self.create_rule_group('transaction_behavior', ['R004', 'R005', 'R006'])
    
    def _register_relationship_rules(self):
        """注册关联关系规则"""
        
        # 规则7: 与涉案公司直接往来
        def direct_company_transfer_condition(ctx):
            return ctx.get('suspicious_company_count', 0) > 0
        
        def direct_company_transfer_action(ctx):
            count = ctx.get('suspicious_company_count', 0)
            score = min(100, count * 20)
            return RuleResult(
                rule_id='R007',
                rule_name='与涉案公司直接往来',
                passed=False,
                risk_level=RiskLevel.CRITICAL if count > 3 else RiskLevel.HIGH,
                score=score,
                message=f'与 {count} 家涉案公司有直接资金往来',
                details={'count': count}
            )
        
        self.register_rule(Rule(
            rule_id='R007',
            rule_name='与涉案公司直接往来',
            description='检测与涉案公司的直接资金往来',
            priority=RulePriority.CRITICAL,
            risk_level=RiskLevel.CRITICAL,
            condition=direct_company_transfer_condition,
            action=direct_company_transfer_action,
            tags=['relationship', 'company', 'suspicious']
        ))
        
        # 规则8: 家族成员资金往来
        def family_transfer_condition(ctx):
            return ctx.get('family_transfer_count', 0) > 5
        
        def family_transfer_action(ctx):
            count = ctx.get('family_transfer_count', 0)
            score = min(100, count * 5)
            return RuleResult(
                rule_id='R008',
                rule_name='家族成员资金往来',
                passed=False,
                risk_level=RiskLevel.MEDIUM,
                score=score,
                message=f'与家族成员有 {count} 笔资金往来',
                details={'count': count}
            )
        
        self.register_rule(Rule(
            rule_id='R008',
            rule_name='家族成员资金往来',
            description='检测与家族成员的资金往来',
            priority=RulePriority.MEDIUM,
            risk_level=RiskLevel.MEDIUM,
            condition=family_transfer_condition,
            action=family_transfer_action,
            tags=['relationship', 'family']
        ))
        
        # 规则9: 第三方中转
        def third_party_relay_condition(ctx):
            return ctx.get('relay_chain_count', 0) > 0
        
        def third_party_relay_action(ctx):
            count = ctx.get('relay_chain_count', 0)
            score = min(100, count * 30)
            return RuleResult(
                rule_id='R009',
                rule_name='第三方中转',
                passed=False,
                risk_level=RiskLevel.HIGH if count > 2 else RiskLevel.MEDIUM,
                score=score,
                message=f'发现 {count} 条第三方中转链路',
                details={'count': count}
            )
        
        self.register_rule(Rule(
            rule_id='R009',
            rule_name='第三方中转',
            description='检测通过第三方中转的资金链路',
            priority=RulePriority.HIGH,
            risk_level=RiskLevel.HIGH,
            condition=third_party_relay_condition,
            action=third_party_relay_action,
            tags=['relationship', 'relay', 'hidden']
        ))
        
        # 创建规则组
        self.create_rule_group('relationship', ['R007', 'R008', 'R009'])
    
    def _register_asset_liability_rules(self):
        """注册资产负债规则"""
        
        # 规则10: 资产收入不匹配
        def asset_income_mismatch_condition(ctx):
            return ctx.get('asset_income_ratio', 0) > 10
        
        def asset_income_mismatch_action(ctx):
            ratio = ctx.get('asset_income_ratio', 0)
            score = min(100, ratio * 5)
            return RuleResult(
                rule_id='R010',
                rule_name='资产收入不匹配',
                passed=False,
                risk_level=RiskLevel.HIGH if ratio > 20 else RiskLevel.MEDIUM,
                score=score,
                message=f'资产是收入的 {ratio:.2f} 倍',
                details={'ratio': ratio}
            )
        
        self.register_rule(Rule(
            rule_id='R010',
            rule_name='资产收入不匹配',
            description='检测资产与收入不匹配的情况',
            priority=RulePriority.HIGH,
            risk_level=RiskLevel.HIGH,
            condition=asset_income_mismatch_condition,
            action=asset_income_mismatch_action,
            tags=['asset', 'income', 'mismatch']
        ))
        
        # 规则11: 大额负债
        def large_liability_condition(ctx):
            return ctx.get('total_liability', 0) > 500000
        
        def large_liability_action(ctx):
            amount = ctx.get('total_liability', 0)
            score = min(100, amount / 10000)
            return RuleResult(
                rule_id='R011',
                rule_name='大额负债',
                passed=False,
                risk_level=RiskLevel.HIGH if amount > 1000000 else RiskLevel.MEDIUM,
                score=score,
                message=f'发现大额负债 {amount/10000:.2f}万元',
                details={'amount': amount}
            )
        
        self.register_rule(Rule(
            rule_id='R011',
            rule_name='大额负债',
            description='检测大额负债情况',
            priority=RulePriority.HIGH,
            risk_level=RiskLevel.HIGH,
            condition=large_liability_condition,
            action=large_liability_action,
            tags=['liability', 'large']
        ))
        
        # 创建规则组
        self.create_rule_group('asset_liability', ['R010', 'R011'])


# 全局单例实例
_engine = None


def get_engine() -> RuleEngine:
    """获取全局规则引擎实例"""
    global _engine
    if _engine is None:
        _engine = RuleEngine()
    return _engine


def analyze_with_rules(
    cleaned_data: Dict[str, pd.DataFrame],
    all_persons: List[str],
    all_companies: List[str],
    profiles: Dict,
    suspicions: Dict,
    output_dir: str
) -> Dict:
    """
    使用规则引擎进行分析
    
    Args:
        cleaned_data: 清洗后的交易数据
        all_persons: 所有人员
        all_companies: 所有公司
        profiles: 资金画像
        suspicions: 疑点检测结果
        output_dir: 输出目录
        
    Returns:
        分析结果
    """
    logger.info('='*60)
    logger.info('开始业务规则推理分析')
    logger.info('='*60)
    
    engine = get_engine()
    all_results = []
    
    # 对每个实体执行规则
    for entity_name, df in cleaned_data.items():
        if entity_name not in all_persons:
            continue
        
        # 构建上下文
        context = _build_context(entity_name, df, profiles, suspicions, all_companies)
        
        # 执行所有规则
        results = engine.execute_all_rules(context)
        all_results.extend(results)
        
        logger.info(f'{entity_name}: 触发 {len(results)} 条规则')
    
    # 聚合结果
    aggregation = engine.aggregate_results(all_results)
    
    # 生成报告
    report_path = f'{output_dir}/业务规则推理报告.txt'
    engine.generate_report(all_results, report_path)
    
    logger.info(f'规则推理完成: 共执行 {len(all_results)} 条规则')
    logger.info(f'  极高风险: {len(aggregation["critical_issues"])}')
    logger.info(f'  高风险: {len(aggregation["high_issues"])}')
    logger.info(f'  中风险: {len(aggregation["medium_issues"])}')
    logger.info(f'  低风险: {len(aggregation["low_issues"])}')
    
    return {
        'results': all_results,
        'aggregation': aggregation,
        'report_path': report_path
    }


def _build_context(
    entity_name: str,
    df: pd.DataFrame,
    profiles: Dict,
    suspicions: Dict,
    all_companies: List[str]
) -> Dict[str, Any]:
    """构建规则执行上下文"""
    context = {
        'entity_name': entity_name,
    }
    
    # 资金画像数据
    profile = profiles.get(entity_name, {})
    context['total_income'] = profile.get('total_income', 0)
    context['total_expense'] = profile.get('total_expense', 0)
    context['net_income'] = profile.get('net_income', 0)
    context['transaction_count'] = profile.get('transaction_count', 0)
    
    # 交易数据统计
    if 'income' in df.columns:
        context['max_single_income'] = df['income'].max()
        context['max_cash_income'] = df[df['description'].str.contains('现金', na=False)]['income'].max() if not df.empty else 0
        context['small_cash_count'] = len(df[(df['income'] > 0) & (df['income'] < 5000) & (df['description'].str.contains('现金', na=False))])
    
    # 疑点数据
    context['fixed_frequency_count'] = sum(len(v) for v in suspicions.get('fixed_frequency', {}).get(entity_name, {}).values())
    context['holiday_large_count'] = len(suspicions.get('holiday_transactions', {}).get(entity_name, []))
    
    # 关联关系
    if 'counterparty' in df.columns:
        suspicious_companies = [cp for cp in df['counterparty'].unique() if cp in all_companies]
        context['suspicious_company_count'] = len(suspicious_companies)
    
    # 资产负债（简化处理）
    context['asset_income_ratio'] = context['total_income'] / max(context['total_income'], 1) * 5  # 模拟数据
    context['total_liability'] = 0  # 需要从资产分析模块获取
    
    return context
