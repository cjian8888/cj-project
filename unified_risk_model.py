#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一风险评估模型
解决风险评估逻辑分散、标准不统一的问题
"""

import logging
from typing import Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RiskScore:
    """风险评分结果"""
    total_score: float  # 总分 (0-100)
    risk_level: str     # 风险等级: CRITICAL/HIGH/MEDIUM/LOW
    confidence: float   # 置信度 (0-1)
    reason: str         # 评分理由
    details: Dict[str, Any]  # 详细信息


class UnifiedRiskModel:
    """
    统一风险评估模型
    
    设计原则:
    1. 理财交易不应作为高风险因素
    2. 家庭内部正常转账应降低风险权重
    3. 异常交易模式应显著增加风险
    4. 资金闭环需结合业务场景判断
    """
    
    def __init__(self):
        # 配置权重
        self.weights = {
            'money_loop': 30,       # 资金闭环
            'transit_channel': 20,   # 过账通道
            'multi_entity': 10,     # 多实体关联
            'ml_anomaly': 15,       # ML异常
            'financial_products': -50, # 理财产品（负分，降低风险）
            'family_transfer': -20,   # 家庭转账（负分，降低风险）
        }
        
        # 风险等级阈值
        self.risk_thresholds = {
            'CRITICAL': 70,
            'HIGH': 50,
            'MEDIUM': 30,
            'LOW': 0
        }
    
    def calculate_score(self, entity_name: str, evidence: Dict[str, Any],
                      financial_ratio: float = None, 
                      family_ratio: float = None) -> RiskScore:
        """
        计算实体风险评分
        
        Args:
            entity_name: 实体名称
            evidence: 证据包（来自clue_aggregator）
            financial_ratio: 理财交易占比 (0-1)
            family_ratio: 家庭转账占比 (0-1)
            
        Returns:
            RiskScore 对象
        """
        logger.info(f"开始计算 {entity_name} 的统一风险评分")
        
        # 基础分
        base_score = 20.0
        
        # 资金闭环评分
        loop_score = self._score_money_loop(evidence.get('money_loops', []))
        
        # 过账通道评分
        channel_score = self._score_transit_channel(evidence.get('transit_channel', {}))
        
        # 多实体关联评分
        entity_score = self._score_multi_entity(evidence.get('related_entities', []))
        
        # ML异常评分
        ml_score = self._score_ml_anomaly(evidence.get('ml_anomalies', []))
        
        # 理财交易调整（负分）
        financial_adjust = 0
        if financial_ratio and financial_ratio > 0.3:  # 理财占比超过30%
            financial_adjust = self.weights['financial_products'] * financial_ratio
            logger.info(f"{entity_name} 理财占比 {financial_ratio:.2%}，调整分 {financial_adjust:.2f}")
        
        # 家庭转账调整（负分）
        family_adjust = 0
        if family_ratio and family_ratio > 0.2:  # 家庭转账占比超过20%
            family_adjust = self.weights['family_transfer'] * family_ratio
            logger.info(f"{entity_name} 家庭转账占比 {family_ratio:.2%}，调整分 {family_adjust:.2f}")
        
        # 计算总分
        total_score = base_score + loop_score + channel_score + entity_score + ml_score + financial_adjust + family_adjust
        
        # 限制在0-100范围
        total_score = max(0, min(100, total_score))
        
        # 确定风险等级
        risk_level = self._get_risk_level(total_score)
        
        # 生成评分理由
        reasons = []
        if loop_score > 0:
            reasons.append(f"涉及{len(evidence.get('money_loops', []))}个资金闭环")
        if channel_score > 0:
            reasons.append("疑似过账通道")
        if financial_adjust < 0:
            reasons.append(f"理财交易占比{financial_ratio:.1%}，降低风险")
        if family_adjust < 0:
            reasons.append(f"家庭转账占比{family_ratio:.1%}，降低风险")
        
        reason = "; ".join(reasons) if reasons else "无明显风险特征"
        
        logger.info(f"{entity_name} 风险评分: {total_score:.1f} ({risk_level}) - {reason}")
        
        return RiskScore(
            total_score=round(total_score, 1),
            risk_level=risk_level,
            confidence=self._calculate_confidence(evidence),
            reason=reason,
            details={
                'base_score': base_score,
                'loop_score': loop_score,
                'channel_score': channel_score,
                'entity_score': entity_score,
                'ml_score': ml_score,
                'financial_adjust': financial_adjust,
                'family_adjust': family_adjust
            }
        )
    
    def _score_money_loop(self, money_loops: List[Dict]) -> float:
        """
        资金闭环评分
        
        规则:
        - 闭环数量多: 高风险
        - 闭环涉及金额大: 加倍风险
        - 闭环频率高: 高风险
        """
        if not money_loops:
            return 0.0
        
        loop_count = len(money_loops)
        base_score = min(loop_count * 1.0, 30.0)  # 最多30分
        
        # 检查是否是理财相关的闭环
        financial_keywords = ['理财', '基金', '证券', '结构性存款']
        financial_loop_count = sum(
            1 for loop in money_loops
            if any(kw in str(loop) for kw in financial_keywords)
        )
        
        # 如果主要是理财闭环，降低风险
        if financial_loop_count > loop_count * 0.5:
            base_score *= 0.3  # 降低70%的风险权重
            logger.info(f"检测到理财相关闭环 {financial_loop_count}/{loop_count}，降低风险权重")
        
        return base_score
    
    def _score_transit_channel(self, transit_channel: Dict) -> float:
        """
        过账通道评分
        
        规则:
        - 进出比接近100%: 高风险（纯过账）
        - 进出比<50%或>150%: 低风险（正常业务）
        """
        if not transit_channel:
            return 0.0
        
        in_amount = transit_channel.get('in', 0)
        out_amount = transit_channel.get('out', 0)
        
        if out_amount == 0:
            return 0.0
        
        ratio = in_amount / out_amount
        
        # 进出比在80%-120%之间，认为是纯过账
        if 0.8 <= ratio <= 1.2:
            return self.weights['transit_channel']
        # 进出比在60%-80%或120%-140%，中度风险
        elif 0.6 <= ratio < 0.8 or 1.2 < ratio <= 1.4:
            return self.weights['transit_channel'] * 0.5
        else:
            return 0.0
    
    def _score_multi_entity(self, related_entities: List[str]) -> float:
        """
        多实体关联评分
        
        规则:
        - 关联实体>=3个: 高分
        - 关联实体2个: 中分
        - 关联实体1个: 低分
        """
        entity_count = len(set(related_entities))
        
        if entity_count >= 3:
            return self.weights['multi_entity']
        elif entity_count == 2:
            return self.weights['multi_entity'] * 0.5
        else:
            return 0.0
    
    def _score_ml_anomaly(self, ml_anomalies: List[Dict]) -> float:
        """
        ML异常评分
        
        规则:
        - 异常数量多: 高风险
        - Z值高: 高风险
        """
        if not ml_anomalies:
            return 0.0
        
        anomaly_count = len(ml_anomalies)
        base_score = min(anomaly_count * 0.5, self.weights['ml_anomaly'])
        
        # 检查Z值（如果有的话）
        high_z_count = sum(
            1 for anomaly in ml_anomalies
            if isinstance(anomaly, dict) and anomaly.get('z_score', 0) > 5
        )
        
        if high_z_count > 0:
            base_score = min(base_score * 1.5, self.weights['ml_anomaly'])
        
        return base_score
    
    def _get_risk_level(self, score: float) -> str:
        """根据分数确定风险等级"""
        if score >= self.risk_thresholds['CRITICAL']:
            return 'CRITICAL'
        elif score >= self.risk_thresholds['HIGH']:
            return 'HIGH'
        elif score >= self.risk_thresholds['MEDIUM']:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _calculate_confidence(self, evidence: Dict) -> float:
        """
        计算置信度
        
        规则:
        - 数据完整度高: 高置信度
        - 数据量小: 低置信度
        """
        base_confidence = 0.7
        
        # 根据交易记录数调整
        record_count = evidence.get('total_records', 0)
        if record_count > 10000:
            base_confidence = 0.9
        elif record_count > 1000:
            base_confidence = 0.8
        elif record_count < 100:
            base_confidence = 0.5
        
        return min(base_confidence, 1.0)


def calculate_financial_ratio(df, income_col: str = 'income', 
                             transaction_desc_col: str = 'description') -> float:
    """
    计算理财交易占比
    
    Args:
        df: 交易数据
        income_col: 收入列名
        transaction_desc_col: 交易描述列名
        
    Returns:
        理财交易占比 (0-1)
    """
    if df.empty:
        return 0.0
    
    # 理财关键词
    financial_keywords = ['理财', '基金', '证券', '结构性存款', '申购', '赎回']
    
    # 识别理财交易
    financial_mask = df[transaction_desc_col].str.contains(
        '|'.join(financial_keywords), na=False
    )
    
    financial_amount = df.loc[financial_mask, income_col].sum()
    total_income = df[income_col].sum()
    
    if total_income == 0:
        return 0.0
    
    return financial_amount / total_income


def calculate_family_transfer_ratio(df, counterparty_col: str = '交易对手',
                                   family_members: List[str] = None) -> float:
    """
    计算家庭转账占比
    
    Args:
        df: 交易数据
        counterparty_col: 交易对手列名
        family_members: 家庭成员名单
        
    Returns:
        家庭转账占比 (0-1)
    """
    if df.empty or not family_members:
        return 0.0
    
    # 识别家庭转账
    family_mask = df[counterparty_col].isin(family_members)
    
    # 【P1 修复 2026-01-27】使用正确的列名"收入(元)"和"支出(元)"
    family_transfer_amount = df.loc[family_mask, '收入(元)'].sum() + df.loc[family_mask, '支出(元)'].sum()
    total_amount = df['收入(元)'].sum() + df['支出(元)'].sum()
    
    if total_amount == 0:
        return 0.0
    
    return family_transfer_amount / total_amount
