#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
线索聚合引擎（Phase 4 新增 - 2026-01-11）

【模块定位】
将各模块发现的独立线索，按"人员"或"案件"进行聚合，形成完整的"证据包"。

【解决的痛点】
- 各模块输出独立，审计员需要在脑海中手动关联
- 证据链非连续，报告是"风险清单"而非"案情推演"

【核心功能】
1. 以"人员"为索引键，聚合该人员的所有发现
2. 计算人员综合风险分
3. 生成"人员证据包"视图
4. 支持快速定位高风险人员

【输出结构】
{
    "张三": {
        "risk_score": 85,
        "risk_level": "high",
        "summary": "涉及2个资金闭环，3笔高风险交易...",
        "evidence": {
            "fund_cycles": [...],
            "high_risk_transactions": [...],
            "communities": [...],
            "periodic_income": [...],
            "sudden_changes": [...]
        }
    }
}
"""

import json
import pandas as pd
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import defaultdict

import config
import utils
import risk_scoring
from name_normalizer import normalize_for_matching
from unified_risk_model import UnifiedRiskModel, calculate_financial_ratio, calculate_family_transfer_ratio
from utils.path_explainability import (
    build_cluster_path_explainability,
    build_cycle_path_explainability,
    build_relay_path_explainability,
    get_or_build_path_evidence_template,
)

logger = utils.setup_logger(__name__)

# 正规金融机构白名单（不应被识别为高风险对手方）
LEGITIMATE_FINANCIAL_INSTITUTIONS = [
    # 支付平台
    '支付宝', '蚂蚁', '微信', '财付通', '京东支付', '银联', '云闪付', '翼支付', '网联',
    # 基金公司
    '基金销售', '基金管理', '天弘基金', '南方基金', '嘉实基金', '易方达', '汇添富', '广发基金',
    '博时基金', '工银基金', '建信基金', '中银基金', '招商基金',
    # 证券公司
    '证券', '投资咨询', '国泰君安', '海通证券', '中信证券', '中金公司', '广发证券', '招商证券',
    # 保险公司
    '人寿保险', '太平洋保险', '中国平安', '中国太保', '新华保险', '众安保险',
    # 银行理财/内部账户（重要！）
    '银行', '信托', '贷款',
    '理财产品', '余额宝', '零钱通', '天天增利', '添利宝',
    '财富业务', '清算帐号', '专户', '业务专户',  # 银行内部账户
    '资产管理', '瑞赢', '季增利', '月增利', '周增利', '添利', '稳利', '安心', # 理财产品
    '非凡资产', '增利', '理财', '申购', '赎回', '本息', '结息', '分红',
    # 物业/公共服务
    '物业', '水电', '燃气', '电信', '租赁', '健身', '健身房',
    # 交通
    '铁路', '航空', '地铁', '公交', '停车', '加油', '中石油', '中石化',
    # 商场/大厦  
    '购物中心', '大厦', '广场', '商场', '运营', '管理公司'
]


def _is_family_cycle(cycle: tuple, core_persons: List[str]) -> bool:
    """
    【P4 优化】判断资金闭环是否为家庭成员闭环
    
    如果闭环中的所有节点都是核心人员（通常为家庭成员），
    则认为是家庭内部资金往来，降低风险评分。
    
    Args:
        cycle: 资金闭环，可能是元组如 ('张三', '李四', '王五', '张三')
               或字典如 {'cycle': (...), 'cycle_str': '...', 'length': N}
        core_persons: 核心人员列表
        
    Returns:
        是否为家庭成员闭环
    """
    if not cycle or not core_persons:
        return False
    
    # 处理字典格式（存储在 evidence_packs 中的格式）
    if isinstance(cycle, dict):
        cycle = cycle.get('cycle', ())
    
    if not cycle:
        return False
    
    # 闭环中的所有节点（排除首尾重复）
    try:
        unique_nodes = set(cycle[:-1]) if len(cycle) > 1 else set(cycle)
    except (TypeError, KeyError):
        return False
    
    # 判断所有节点是否都是核心人员
    for node in unique_nodes:
        if node not in core_persons:
            return False
    
    return True


# 理财产品关键词（用于过滤资金突变中的理财交易）
WEALTH_MANAGEMENT_KEYWORDS = [
    '理财', '申购', '赎回', '本息', '结息', '分红', '到期', '转存', '定期',
    '资产管理', '瑞赢', '增利', '月增利', '周增利', '季增利', '年增利',
    '稳利', '安心', '财富', '专户', '清算', '宝', '计划'
]

GENERIC_WALLET_COUNTERPARTIES = {
    '电子钱包总体',
    '跨平台账户映射',
    '夜间活跃交易',
    '电子钱包收入聚集',
    '电子钱包快速转手',
    '银行账户支出',
}

def is_legitimate_institution(name: str) -> bool:
    """检查是否为正规金融机构/公共服务"""
    if not name:
        return False
    name_str = str(name)
    return any(inst in name_str for inst in LEGITIMATE_FINANCIAL_INSTITUTIONS)

def is_wealth_management_related(text: str) -> bool:
    """检查是否为理财相关交易"""
    if not text:
        return False
    text_str = str(text)
    return any(kw in text_str for kw in WEALTH_MANAGEMENT_KEYWORDS)


class ClueAggregator:
    """
    线索聚合引擎
    
    将各模块的独立线索按人员聚合，形成完整证据包
    """
    
    def __init__(self, core_persons: List[str], companies: List[str]):
        self.core_persons = core_persons
        self.companies = companies
        self.all_entities = core_persons + companies
        self.entity_alias_map = self._build_entity_alias_map()
        self.analysis_metadata = {
            'penetration': {},
            'related_party': {},
        }
        self._bucket_seen_keys = defaultdict(lambda: defaultdict(set))
        self._bucket_item_indexes = defaultdict(lambda: defaultdict(dict))
        
        # 每个实体的证据包
        self.evidence_packs = {entity: self._create_empty_pack() for entity in self.all_entities}

    def _build_entity_alias_map(self) -> Dict[str, str]:
        """构建实体别名索引，兼容括号、空格和人员后缀差异。"""
        alias_map = {}
        for entity in self.all_entities:
            entity_name = str(entity).strip()
            if not entity_name:
                continue
            aliases = {
                entity_name,
                utils.normalize_name(entity_name),
                utils.normalize_person_name(entity_name),
                normalize_for_matching(entity_name),
            }
            for alias in aliases:
                if alias:
                    alias_map[alias] = entity_name
        return alias_map

    @staticmethod
    def _serialize_dedupe_key(item: Any) -> str:
        """为去重生成稳定键。"""
        try:
            return json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return str(item)

    def _build_bucket_dedupe_key(self, bucket: str, item: Any) -> str:
        if bucket == 'related_party' and isinstance(item, dict):
            amount = item.get('amount')
            if amount is None:
                amount = item.get('金额')
            if amount is None:
                amount = max(
                    self._safe_float(item.get('收入')),
                    self._safe_float(item.get('支出')),
                )
            normalized_item = {
                'from': item.get('from') or item.get('发起方') or item.get('person1') or '',
                'to': item.get('to') or item.get('接收方') or item.get('person2') or '',
                'amount': round(self._safe_float(amount), 2),
                'date': item.get('date') or item.get('日期') or item.get('交易日期') or item.get('time') or '',
                'description': item.get('description') or item.get('摘要') or '',
            }
            return self._serialize_dedupe_key(normalized_item)
        return self._serialize_dedupe_key(item)

    @staticmethod
    def _is_empty_value(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ''
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) == 0
        return False

    def _merge_related_party_item(self, existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(existing) if isinstance(existing, dict) else {}
        if not isinstance(incoming, dict):
            return merged

        for key, value in incoming.items():
            if self._is_empty_value(value):
                continue
            if self._is_empty_value(merged.get(key)):
                merged[key] = value
                continue
            if key == 'relationship_context':
                existing_rank = {'family': 2, 'external': 1}.get(str(merged.get(key, '') or '').strip().lower(), 0)
                incoming_rank = {'family': 2, 'external': 1}.get(str(value or '').strip().lower(), 0)
                if incoming_rank > existing_rank:
                    merged[key] = value
        return merged

    @staticmethod
    def _normalize_risk_level(level: Any, score: Any = None) -> str:
        normalized = str(level or '').strip().lower()
        if normalized in {'critical', 'high', 'medium', 'low'}:
            return normalized
        return risk_scoring.score_to_risk_level(score or 0)

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _resolve_entity(self, candidate: Any) -> Optional[str]:
        """把任意名称解析为排查对象实体。"""
        if candidate is None:
            return None

        text = str(candidate).strip()
        if not text or text.lower() in {'nan', 'none', 'null', 'nat'}:
            return None
        if text in self.evidence_packs:
            return text

        aliases = (
            text,
            utils.normalize_name(text),
            utils.normalize_person_name(text),
            normalize_for_matching(text),
        )
        for alias in aliases:
            if alias and alias in self.entity_alias_map:
                return self.entity_alias_map[alias]
        return None

    def _append_entity_evidence(self, entity: str, bucket: str, item: Dict) -> bool:
        """向实体证据包追加去重后的线索。"""
        if entity not in self.evidence_packs:
            return False

        dedupe_key = self._build_bucket_dedupe_key(bucket, item)
        seen_keys = self._bucket_seen_keys[entity][bucket]
        if dedupe_key in seen_keys:
            if bucket == 'related_party':
                existing_index = self._bucket_item_indexes[entity][bucket].get(dedupe_key)
                if existing_index is not None:
                    existing_item = self.evidence_packs[entity]['evidence'][bucket][existing_index]
                    self.evidence_packs[entity]['evidence'][bucket][existing_index] = (
                        self._merge_related_party_item(existing_item, item)
                    )
            return False

        seen_keys.add(dedupe_key)
        bucket_items = self.evidence_packs[entity]['evidence'][bucket]
        bucket_items.append(item)
        self._bucket_item_indexes[entity][bucket][dedupe_key] = len(bucket_items) - 1
        return True

    def _append_to_entities(self, bucket: str, item: Dict, *candidates: Any) -> List[str]:
        """把线索挂到匹配到的实体证据包上。"""
        matched_entities = []
        seen_entities = set()
        pending = list(candidates)

        while pending:
            candidate = pending.pop(0)
            if isinstance(candidate, (list, tuple, set)):
                pending.extend(candidate)
                continue

            entity = self._resolve_entity(candidate)
            if entity and entity not in seen_entities:
                if self._append_entity_evidence(entity, bucket, item):
                    matched_entities.append(entity)
                seen_entities.add(entity)

        return matched_entities

    @staticmethod
    def _include_wallet_counterparty_for_entity_count(alert: Dict[str, Any]) -> bool:
        if not isinstance(alert, dict):
            return False
        role = str(alert.get('counterparty_role', '') or '').strip().lower()
        if role in {'self', 'family', 'salary_payer'}:
            return False
        counterparty = str(alert.get('counterparty', '') or '').strip()
        if not counterparty or counterparty in GENERIC_WALLET_COUNTERPARTIES:
            return False
        return True

    def _normalize_fund_cycle_record(
        self,
        raw_cycle: Any,
        source: str,
        analysis_metadata: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """统一闭环记录格式，兼容旧 list 和新 explainability dict。"""
        if raw_cycle is None:
            return None

        if isinstance(raw_cycle, dict):
            record = dict(raw_cycle)
            participants = (
                record.get('participants')
                or record.get('nodes')
                or record.get('cycle')
                or []
            )
        else:
            participants = list(raw_cycle) if isinstance(raw_cycle, (list, tuple)) else []
            record = {
                'participants': participants,
                'nodes': participants,
                'cycle': participants,
            }

        participants = [str(node).strip() for node in participants if str(node).strip()]
        path = record.get('path') or record.get('cycle_str') or ''
        if not path and participants:
            path = ' → '.join(participants + [participants[0]])
        if not participants and not path:
            return None

        risk_score = risk_scoring.normalize_risk_score(record.get('risk_score', 0))
        normalized_record = dict(record)
        normalized_record.update(
            {
                'participants': participants,
                'nodes': normalized_record.get('nodes') or participants,
                'cycle': normalized_record.get('cycle') or participants,
                'path': path,
                'cycle_str': normalized_record.get('cycle_str') or path,
                'length': int(normalized_record.get('length', len(participants))),
                'risk_score': risk_score,
                'risk_level': self._normalize_risk_level(
                    normalized_record.get('risk_level'),
                    risk_score,
                ),
                'confidence': risk_scoring.normalize_confidence(
                    normalized_record.get('confidence', 0.05)
                ),
                'evidence': list(normalized_record.get('evidence', []) or []),
                'source': source,
            }
        )

        if analysis_metadata:
            normalized_record['analysis_metadata'] = dict(analysis_metadata)
            if analysis_metadata.get('truncated'):
                normalized_record['search_truncated'] = True

        if not normalized_record['evidence']:
            normalized_record['evidence'] = [
                f"来自{'资金穿透' if source == 'penetration' else '关联方分析'}的闭环线索"
            ]
        if not isinstance(normalized_record.get('path_explainability'), dict):
            normalized_record['path_explainability'] = build_cycle_path_explainability(
                nodes=participants,
                path=path,
                total_amount=float(normalized_record.get('total_amount', 0) or 0),
                search_metadata=analysis_metadata,
            )

        return normalized_record

    @staticmethod
    def _describe_clue(bucket: str, item: Dict) -> str:
        label_mapping = {
            'fund_cycles': '资金闭环',
            'pass_through': '过账通道',
            'high_risk_transactions': '高风险交易',
            'communities': '团伙关系',
            'periodic_income': '周期性收入',
            'sudden_changes': '资金突变',
            'delayed_transfers': '固定延迟转账',
            'related_party': '直接往来',
            'loans': '借贷关系',
            'third_party_relays': '第三方中转',
            'discovered_nodes': '外围节点',
            'relationship_clusters': '关系簇',
            'wallet_summaries': '电子钱包补充摘要',
            'wallet_alerts': '电子钱包预警',
        }
        label = label_mapping.get(bucket, bucket)

        if not isinstance(item, dict):
            return label
        if item.get('path'):
            return f"{label}: {item.get('path')}"
        if item.get('cycle_str'):
            return f"{label}: {item.get('cycle_str')}"
        if isinstance(item.get('path_explainability'), dict):
            evidence_template = get_or_build_path_evidence_template(item['path_explainability'])
            headline = str(evidence_template.get('headline', '') or '').strip()
            if headline:
                return f"{label}: {headline}"
            summary = str(item['path_explainability'].get('summary', '')).strip()
            if summary:
                return f"{label}: {summary}"
        if item.get('relay'):
            return f"{label}: {item.get('from', '未知')} → {item.get('relay')} → {item.get('to', '未知')}"
        if item.get('cluster_id'):
            return f"{label}: {item.get('cluster_id')}"
        if item.get('name'):
            return f"{label}: {item.get('name')}"
        if item.get('counterparty'):
            return f"{label}: {item.get('counterparty')}"
        if item.get('to'):
            return f"{label}: {item.get('from', '未知')} → {item.get('to')}"
        return label

    def _build_explainability_metrics(self, pack: Dict) -> Dict:
        """基于各类线索的 explainability 生成聚合排序辅助信息。"""
        scored_clues = []
        evidence_counts = {}

        for bucket, items in pack.get('evidence', {}).items():
            evidence_counts[bucket] = len(items) if isinstance(items, list) else 0
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                if 'risk_score' not in item and 'confidence' not in item:
                    continue

                score = risk_scoring.normalize_risk_score(item.get('risk_score', 0))
                confidence = risk_scoring.normalize_confidence(item.get('confidence', 0.05))
                scored_clues.append(
                    {
                        'bucket': bucket,
                        'risk_score': score,
                        'confidence': confidence,
                        'description': self._describe_clue(bucket, item),
                        'evidence': list(item.get('evidence', []) or [])[:3],
                        'path_explainability': item.get('path_explainability', {}),
                        'evidence_template': get_or_build_path_evidence_template(
                            item.get('path_explainability', {})
                        ),
                    }
                )

        scored_clues.sort(
            key=lambda clue: (
                -clue['risk_score'],
                -clue['confidence'],
                clue['description'],
            )
        )

        scores = [clue['risk_score'] for clue in scored_clues]
        confidences = [clue['confidence'] for clue in scored_clues]
        model_confidence = risk_scoring.normalize_confidence(pack.get('model_confidence', 0.05))
        if confidences:
            avg_confidence = round(sum(confidences) / len(confidences), 2)
            max_confidence = max(confidences)
            risk_confidence = risk_scoring.normalize_confidence(
                model_confidence * 0.45 + avg_confidence * 0.35 + max_confidence * 0.20
            )
        else:
            avg_confidence = model_confidence
            max_confidence = model_confidence
            risk_confidence = model_confidence

        top_evidence_score = max(scores) if scores else 0.0
        high_priority_clue_count = sum(1 for score in scores if score >= 50)

        return {
            'risk_confidence': risk_confidence,
            'top_evidence_score': top_evidence_score,
            'high_priority_clue_count': high_priority_clue_count,
            'aggregation_explainability': {
                'model_confidence': model_confidence,
                'average_evidence_confidence': avg_confidence,
                'max_evidence_confidence': max_confidence,
                'scored_clue_count': len(scored_clues),
                'evidence_bucket_counts': evidence_counts,
                'top_clues': scored_clues[:3],
            },
        }
    
    def _create_empty_pack(self) -> Dict:
        """创建空证据包"""
        return {
            'risk_score': 0,
            'risk_level': 'low',
            'risk_confidence': 0.05,
            'model_confidence': 0.05,
            'top_evidence_score': 0.0,
            'high_priority_clue_count': 0,
            'aggregation_explainability': {
                'model_confidence': 0.05,
                'average_evidence_confidence': 0.05,
                'max_evidence_confidence': 0.05,
                'scored_clue_count': 0,
                'evidence_bucket_counts': {},
                'top_clues': [],
            },
            'summary': '',
            'evidence': {
                'fund_cycles': [],           # 涉及的资金闭环
                'pass_through': [],          # 过账通道相关
                'hub_connections': [],       # 作为资金枢纽的连接
                'high_risk_transactions': [],# 高风险交易
                'communities': [],           # 涉及的团伙
                'periodic_income': [],       # 周期性收入
                'sudden_changes': [],        # 资金突变
                'delayed_transfers': [],     # 固定延迟转账
                'related_party': [],         # 关联方往来
                'third_party_relays': [],    # 第三方中转
                'discovered_nodes': [],      # 外围节点
                'relationship_clusters': [], # 关系簇
                'loans': [],                 # 借贷关系
                'wallet_summaries': [],      # 电子钱包主体摘要
                'wallet_alerts': [],         # 电子钱包预警
            },
            'statistics': {
                'total_inflow': 0,
                'total_outflow': 0,
                'transaction_count': 0,
                'high_risk_count': 0,
                'medium_risk_count': 0
            }
        }
    
    def aggregate_penetration_results(self, penetration_results: Dict):
        """聚合资金穿透分析结果"""
        logger.info('聚合资金穿透分析结果...')
        self.analysis_metadata['penetration'] = penetration_results.get('analysis_metadata', {}) or {}
        
        # 聚合资金闭环（去重）
        for cycle in penetration_results.get('fund_cycles', []):
            cycle_record = self._normalize_fund_cycle_record(
                cycle,
                source='penetration',
                analysis_metadata=self.analysis_metadata['penetration'].get('fund_cycles'),
            )
            if not cycle_record:
                continue

            self._append_to_entities(
                'fund_cycles',
                cycle_record,
                cycle_record.get('participants', []),
            )
        
        # 聚合过账通道
        for channel in penetration_results.get('pass_through_channels', []):
            entity = self._resolve_entity(channel.get('node'))
            if entity:
                self._append_entity_evidence(entity, 'pass_through', channel)
        
        # 聚合资金枢纽
        for hub in penetration_results.get('hub_nodes', []):
            entity = self._resolve_entity(hub.get('node'))
            if entity:
                self._append_entity_evidence(entity, 'hub_connections', hub)

    def aggregate_ml_results(self, ml_results: Dict):
        """聚合机器学习分析结果"""
        logger.info('聚合机器学习分析结果...')
        
        # 聚合高风险交易（过滤正规金融机构和自我转账）
        for anomaly in ml_results.get('anomalies', []):
            entity = anomaly.get('person')
            counterparty = str(anomaly.get('counterparty', ''))
            
            # 过滤自我转账
            if entity == counterparty:
                continue
                
            # 过滤正规金融机构
            if is_legitimate_institution(counterparty):
                continue
                
            if entity in self.evidence_packs:
                self.evidence_packs[entity]['evidence']['high_risk_transactions'].append(anomaly)
        
        # 聚合团伙（过滤理财账户成员）
        for community in ml_results.get('communities', []):
            members = community.get('members', [])
            # 过滤掉理财账户成员
            filtered_members = [m for m in members if not is_wealth_management_related(m)]
            
            # 如果过滤后成员太少（<2个真实成员），跳过这个团伙
            if len(filtered_members) < 2:
                continue
                
            for member in members:
                if member in self.evidence_packs:
                    self.evidence_packs[member]['evidence']['communities'].append({
                        'community_id': id(community),
                        'members': filtered_members,  # 使用过滤后的成员
                        'total_amount': community.get('total_amount', 0),
                        'type': community.get('type', '未知')
                    })
    
    def aggregate_time_series_results(self, ts_results: Dict):
        """聚合时序分析结果"""
        logger.info('聚合时序分析结果...')
        
        # 聚合周期性收入（过滤理财相关）
        for pattern in ts_results.get('periodic_income', []):
            counterparty = str(pattern.get('counterparty', ''))
            # 跳过理财相关的周期性收入（这是正常的理财到期）
            if is_wealth_management_related(counterparty):
                continue
            entity = pattern.get('person')
            if entity in self.evidence_packs:
                self.evidence_packs[entity]['evidence']['periodic_income'].append(pattern)
        
        # 聚合资金突变（这里暂不过滤，因为突变数据没有对手方信息）
        # 但在报告中会标注需人工判断
        for change in ts_results.get('sudden_changes', []):
            entity = change.get('person')
            if entity in self.evidence_packs:
                self.evidence_packs[entity]['evidence']['sudden_changes'].append(change)
        
        # 聚合固定延迟转账
        for transfer in ts_results.get('delayed_transfers', []):
            entity = transfer.get('person')
            if entity in self.evidence_packs:
                self.evidence_packs[entity]['evidence']['delayed_transfers'].append(transfer)
    
    def aggregate_related_party_results(self, rp_results: Dict):
        """聚合关联方分析结果"""
        logger.info('聚合关联方分析结果...')
        self.analysis_metadata['related_party'] = rp_results.get('analysis_metadata', {}) or {}
        
        # 兼容旧结构 direct_transactions，并正式消费新结构 direct_flows
        direct_flows = rp_results.get('direct_flows', []) or rp_results.get('direct_transactions', [])
        for flow in direct_flows:
            self._append_to_entities(
                'related_party',
                flow,
                flow.get('from'),
                flow.get('to'),
                flow.get('person1'),
                flow.get('person2'),
            )

        for relay in rp_results.get('third_party_relays', []):
            relay_record = dict(relay) if isinstance(relay, dict) else {}
            if relay_record and not isinstance(relay_record.get('path_explainability'), dict):
                relay_record['path_explainability'] = build_relay_path_explainability(relay_record)
            self._append_to_entities(
                'third_party_relays',
                relay_record,
                relay_record.get('from'),
                relay_record.get('to'),
            )

        loop_meta = self.analysis_metadata['related_party'].get('fund_loops')
        for loop in rp_results.get('fund_loops', []):
            loop_record = self._normalize_fund_cycle_record(
                loop,
                source='related_party',
                analysis_metadata=loop_meta,
            )
            if not loop_record:
                continue
            self._append_to_entities(
                'fund_cycles',
                loop_record,
                loop_record.get('participants', []),
            )

        for node in rp_results.get('discovered_nodes', []):
            self._append_to_entities(
                'discovered_nodes',
                node,
                node.get('linked_cores', []),
            )

        for cluster in rp_results.get('relationship_clusters', []):
            cluster_record = dict(cluster) if isinstance(cluster, dict) else {}
            if cluster_record and not isinstance(cluster_record.get('path_explainability'), dict):
                cluster_record['path_explainability'] = build_cluster_path_explainability(cluster_record)
            self._append_to_entities(
                'relationship_clusters',
                cluster_record,
                cluster_record.get('core_members', []),
                cluster_record.get('external_members', []),
                cluster_record.get('all_nodes', []),
            )
    
    def aggregate_loan_results(self, loan_results: Dict):
        """聚合借贷分析结果"""
        logger.info('聚合借贷分析结果...')
        
        # 双向往来
        relations = loan_results.get('bidirectional_flows', loan_results.get('bidirectional', []))
        for relation in relations:
            entity = relation.get('person')
            if entity in self.evidence_packs:
                self.evidence_packs[entity]['evidence']['loans'].append(relation)

    def _normalize_wallet_summary_record(self, summary: Dict) -> Optional[Dict]:
        """标准化电子钱包主体摘要，用于聚合评分。"""
        if not isinstance(summary, dict):
            return None

        platforms = summary.get('platforms', {}) or {}
        if not isinstance(platforms, dict):
            platforms = {}
        alipay = platforms.get('alipay', {}) or {}
        wechat = platforms.get('wechat', {}) or {}
        cross = summary.get('crossSignals', {}) or {}
        if not isinstance(cross, dict):
            cross = {}

        third_party_total = (
            self._safe_float(alipay.get('incomeTotalYuan'))
            + self._safe_float(alipay.get('expenseTotalYuan'))
            + self._safe_float(wechat.get('incomeTotalYuan'))
            + self._safe_float(wechat.get('expenseTotalYuan'))
        )
        transaction_count = int(self._safe_float(alipay.get('transactionCount'))) + int(
            self._safe_float(wechat.get('tenpayTransactionCount'))
        )
        bank_overlap = int(self._safe_float(cross.get('bankCardOverlapCount')))
        alias_overlap = int(self._safe_float(cross.get('aliasMatchCount')))
        phone_overlap = int(self._safe_float(cross.get('phoneOverlapCount')))
        login_event_count = int(self._safe_float(wechat.get('loginEventCount')))

        risk_score = 0.0
        if third_party_total >= 1_000_000:
            risk_score += 34
        elif third_party_total >= 300_000:
            risk_score += 24
        elif third_party_total >= 100_000:
            risk_score += 14
        elif third_party_total > 0:
            risk_score += 6

        if transaction_count >= 200:
            risk_score += 12
        elif transaction_count >= 100:
            risk_score += 8
        elif transaction_count >= 30:
            risk_score += 4

        risk_score += min(bank_overlap * 6, 12)
        risk_score += min(alias_overlap * 6, 12)
        risk_score += min(phone_overlap * 4, 8)
        if login_event_count >= 20:
            risk_score += 4

        confidence = 0.68
        if summary.get('matchedToCore'):
            confidence += 0.08
        if bank_overlap or alias_overlap or phone_overlap:
            confidence += 0.08

        evidence = []
        if third_party_total > 0:
            evidence.append(f"电子钱包累计收支约{third_party_total / 10000:.2f}万元")
        if transaction_count > 0:
            evidence.append(f"电子钱包交易共{transaction_count}笔")
        if bank_overlap:
            evidence.append(f"跨平台银行卡重叠{bank_overlap}张")
        if alias_overlap:
            evidence.append(f"微信别名与财付通账号重叠{alias_overlap}组")
        if phone_overlap:
            evidence.append(f"跨平台手机号重叠{phone_overlap}组")

        top_counterparties = []
        for source_items in (
            alipay.get('topCounterparties', []) or [],
            wechat.get('topCounterparties', []) or [],
        ):
            if not isinstance(source_items, list):
                continue
            for item in source_items[:3]:
                if isinstance(item, dict) and item.get('name'):
                    top_counterparties.append(str(item.get('name')).strip())

        return {
            'person': summary.get('subjectName') or summary.get('subjectId') or '',
            'subject_id': summary.get('subjectId', ''),
            'matched_to_core': bool(summary.get('matchedToCore')),
            'third_party_total': round(third_party_total, 2),
            'transaction_count': transaction_count,
            'alipay_tx_count': int(self._safe_float(alipay.get('transactionCount'))),
            'tenpay_tx_count': int(self._safe_float(wechat.get('tenpayTransactionCount'))),
            'login_event_count': login_event_count,
            'bank_card_overlap_count': bank_overlap,
            'alias_match_count': alias_overlap,
            'phone_overlap_count': phone_overlap,
            'top_counterparties': top_counterparties[:5],
            'risk_score': min(risk_score, 62.0),
            'risk_level': self._normalize_risk_level(None, risk_score),
            'confidence': risk_scoring.normalize_confidence(confidence),
            'evidence': evidence,
        }

    def _normalize_wallet_alert_record(self, alert: Dict) -> Optional[Dict]:
        """标准化电子钱包预警记录。"""
        if not isinstance(alert, dict):
            return None

        level = str(alert.get('risk_level', 'medium') or 'medium').strip().lower()
        amount = self._safe_float(alert.get('amount'))
        derived_score = {
            'high': 58.0,
            'medium': 40.0,
            'low': 20.0,
        }.get(level, 32.0)
        if amount >= 1_000_000:
            derived_score += 8
        elif amount >= 300_000:
            derived_score += 5
        elif amount >= 100_000:
            derived_score += 3

        source_score = self._safe_float(alert.get('risk_score'))
        base_score = source_score if source_score > 0 else derived_score

        derived_confidence = {
            'high': 0.84,
            'medium': 0.76,
            'low': 0.62,
        }.get(level, 0.68)
        source_confidence = self._safe_float(alert.get('confidence'))
        confidence = source_confidence if source_confidence > 0 else derived_confidence

        evidence = []
        if alert.get('description'):
            evidence.append(str(alert.get('description')))
        if alert.get('risk_reason'):
            evidence.append(str(alert.get('risk_reason')))
        if alert.get('evidence_summary'):
            evidence.append(str(alert.get('evidence_summary')))

        return {
            **alert,
            'person': alert.get('person', ''),
            'counterparty': alert.get('counterparty', ''),
            'amount': round(amount, 2),
            'risk_score': min(base_score, 72.0),
            'risk_level': self._normalize_risk_level(level, base_score),
            'confidence': risk_scoring.normalize_confidence(confidence),
            'evidence': evidence[:3],
        }

    def aggregate_wallet_results(self, wallet_results: Dict):
        """聚合电子钱包补充数据。"""
        logger.info('聚合电子钱包补充数据...')
        if not isinstance(wallet_results, dict):
            return

        for summary in wallet_results.get('subjects', []) or []:
            normalized = self._normalize_wallet_summary_record(summary)
            if not normalized:
                continue
            self._append_to_entities(
                'wallet_summaries',
                normalized,
                summary.get('subjectName'),
                summary.get('subjectId'),
                normalized.get('person'),
            )

        for alert in wallet_results.get('alerts', []) or []:
            normalized = self._normalize_wallet_alert_record(alert)
            if not normalized:
                continue
            self._append_to_entities(
                'wallet_alerts',
                normalized,
                normalized.get('person'),
            )
    
    def calculate_entity_risk_scores(self):
        """
        计算每个实体的综合风险分
        
        【P1 修复 2026-01-27】使用统一风险模型
        解决问题:
        - 理财交易被误判为高风险
        - 家庭内部正常转账被误判为资金闭环
        - 风险评分与常识不符
        
        改进方案:
        1. 引入 UnifiedRiskModel 统一风险评分
        2. 计算理财交易占比，降低风险权重
        3. 计算家庭转账占比，降低风险权重
        4. 区分理财相关的资金闭环
        """
        logger.info('计算实体综合风险分（使用统一风险模型）...')
        
        # 初始化统一风险模型
        risk_model = UnifiedRiskModel()
        
        for entity, pack in self.evidence_packs.items():
            evidence = pack['evidence']
            stats = pack.get('statistics', {})
            hub_entities = [
                hub.get('node') if isinstance(hub, dict) else hub
                for hub in evidence.get('hub_connections', [])
            ]
            community_members = [
                member
                for community in evidence.get('communities', [])
                if isinstance(community, dict)
                for member in community.get('members', [])
            ]
            relay_entities = [
                relay.get('relay')
                for relay in evidence.get('third_party_relays', [])
                if isinstance(relay, dict) and relay.get('relay')
            ]
            discovered_entities = [
                node.get('name')
                for node in evidence.get('discovered_nodes', [])
                if isinstance(node, dict) and node.get('name')
            ]
            cluster_entities = [
                member
                for cluster in evidence.get('relationship_clusters', [])
                if isinstance(cluster, dict)
                for member in (
                    list(cluster.get('core_members', []) or [])
                    + list(cluster.get('external_members', []) or [])
                    + list(cluster.get('all_nodes', []) or [])
                )
            ]
            direct_relation_entities = []
            for relation in evidence.get('related_party', []):
                if not isinstance(relation, dict):
                    continue
                direct_relation_entities.extend(
                    [
                        relation.get('from'),
                        relation.get('to'),
                        relation.get('发起方'),
                        relation.get('接收方'),
                        relation.get('person1'),
                        relation.get('person2'),
                    ]
                )
            
            # 准备风险评分所需的数据
            risk_evidence = {
                'money_loops': evidence.get('fund_cycles', []),
                'transit_channel': self._extract_transit_channel_info(evidence),
                'transit_channels': evidence.get('pass_through', []),
                'relay_chains': evidence.get('third_party_relays', []),
                'relationship_clusters': evidence.get('relationship_clusters', []),
                'discovered_nodes': evidence.get('discovered_nodes', []),
                'direct_relations': evidence.get('related_party', []),
                'wallet_summaries': evidence.get('wallet_summaries', []),
                'wallet_alerts': evidence.get('wallet_alerts', []),
                'related_entities': [x for x in (hub_entities + community_members) if x],
                'ml_anomalies': evidence.get('high_risk_transactions', []),
                'total_records': stats.get('total_records', stats.get('transaction_count', 0)),
                'money_loop_meta': self.analysis_metadata.get('penetration', {}).get('fund_cycles', {}),
                'relay_meta': self.analysis_metadata.get('related_party', {}).get('third_party_relays', {}),
                'relationship_meta': self.analysis_metadata.get('related_party', {}).get('fund_loops', {}),
            }
            risk_evidence['related_entities'] = [
                item
                for item in (
                    hub_entities
                    + community_members
                    + relay_entities
                    + discovered_entities
                    + cluster_entities
                    + direct_relation_entities
                    + [
                        alert.get('counterparty')
                        for alert in evidence.get('wallet_alerts', [])
                        if self._include_wallet_counterparty_for_entity_count(alert)
                    ]
                )
                if item and item != entity
            ]
            
            # 计算理财交易占比（从cleaned_data中读取）
            financial_ratio = self._calculate_financial_ratio(entity)
            
            # 计算家庭转账占比
            family_ratio = self._calculate_family_transfer_ratio(entity)
            
            # 使用统一风险模型计算评分
            risk_score = risk_model.calculate_score(
                entity_name=entity,
                evidence=risk_evidence,
                financial_ratio=financial_ratio,
                family_ratio=family_ratio
            )
            
            # 更新风险评分到evidence_pack
            pack['risk_score'] = risk_score.total_score
            pack['risk_level'] = self._normalize_risk_level(
                risk_score.risk_level,
                risk_score.total_score,
            )
            pack['summary'] = risk_score.reason
            pack['model_confidence'] = risk_score.confidence
            pack['risk_details'] = risk_score.details

            explainability_metrics = self._build_explainability_metrics(pack)
            pack['risk_confidence'] = explainability_metrics['risk_confidence']
            pack['top_evidence_score'] = explainability_metrics['top_evidence_score']
            pack['high_priority_clue_count'] = explainability_metrics['high_priority_clue_count']
            pack['aggregation_explainability'] = explainability_metrics['aggregation_explainability']

            top_clues = pack['aggregation_explainability'].get('top_clues', [])
            if top_clues:
                top_categories = '、'.join(
                    clue.get('description', '').split(':', 1)[0]
                    for clue in top_clues
                    if clue.get('description')
                )
                if top_categories and top_categories not in pack['summary']:
                    pack['summary'] = (
                        f'{pack["summary"]}；重点线索：{top_categories}'
                        if pack['summary']
                        else f'重点线索：{top_categories}'
                    )
            
            logger.info(
                f"{entity} 统一风险评分: {risk_score.total_score:.1f} "
                f"({pack['risk_level']}, confidence={pack['risk_confidence']:.2f})"
            )
    
    def _extract_transit_channel_info(self, evidence: Dict) -> Dict:
        """提取过账通道信息"""
        channels = evidence.get('pass_through', [])
        if not channels:
            return {}
        
        # 聚合所有过账通道的进出总额
        in_amount = 0.0
        out_amount = 0.0
        for channel in channels:
            if not isinstance(channel, dict):
                continue
            in_amount += float(channel.get('inflow', 0) or 0)
            out_amount += float(channel.get('outflow', 0) or 0)

        return {
            'in': in_amount,
            'out': out_amount
        }
    
    def _calculate_financial_ratio(self, entity: str) -> float:
        """
        计算理财交易占比
        
        Returns:
            理财收入占总收入的比例 (0-1)
        """
        try:
            # 尝试读取cleaned_data
            import os
            import config
            
            output_dir = config.OUTPUT_DIR
            if entity in self.core_persons:
                cleaned_file = os.path.join(output_dir, 'cleaned_data', '个人', f'{entity}_合并流水.xlsx')
            else:
                cleaned_file = os.path.join(output_dir, 'cleaned_data', '公司', f'{entity}_合并流水.xlsx')
            
            if not os.path.exists(cleaned_file):
                logger.warning(f"找不到 {entity} 的清洗数据文件: {cleaned_file}")
                return 0.0
            
            df = pd.read_excel(cleaned_file)
            # 【P1 修复 2026-01-27】添加文件大小检查和日志
            file_size = os.path.getsize(cleaned_file) / (1024 * 1024)  # MB
            logger.info(f"正在计算理财占比: {entity} ({file_size:.1f}MB)")
            
            # 使用统一的函数计算理财占比
            from unified_risk_model import calculate_financial_ratio
            financial_ratio = calculate_financial_ratio(
                df, 
                income_col='收入(元)', 
                transaction_desc_col='交易摘要'
            )
            
            logger.info(f"{entity} 理财交易占比: {financial_ratio*100:.1f}%")
            return financial_ratio
            
        except Exception as e:
            logger.warning(f"计算 {entity} 理财占比失败: {e}")
            return 0.0
    
    def _calculate_family_transfer_ratio(self, entity: str) -> float:
        """
        计算家庭转账占比
        
        Returns:
            家庭转账占总交易的比例 (0-1)
        """
        try:
            if entity not in self.core_persons:
                return 0.0  # 公司不计算家庭转账
            
            import os
            import config
            
            output_dir = config.OUTPUT_DIR
            cleaned_file = os.path.join(output_dir, 'cleaned_data', '个人', f'{entity}_合并流水.xlsx')
            
            if not os.path.exists(cleaned_file):
                return 0.0
            
            # 【P1 修复 2026-01-27】添加日志
            file_size = os.path.getsize(cleaned_file) / (1024 * 1024)  # MB
            logger.info(f"  正在计算家庭转账占比: {entity} ({file_size:.1f}MB)")
            
            df = pd.read_excel(cleaned_file)
            
            # 使用统一的函数计算家庭转账占比
            from unified_risk_model import calculate_family_transfer_ratio
            family_ratio = calculate_family_transfer_ratio(
                df,
                counterparty_col='交易对手',
                family_members=self.core_persons
            )
            
            logger.info(f"{entity} 家庭转账占比: {family_ratio*100:.1f}%")
            return family_ratio
            
        except Exception as e:
            logger.warning(f"计算 {entity} 家庭转账占比失败: {e}")
            return 0.0
    
    def get_ranked_entities(self) -> List[Dict]:
        """获取按风险分排序的实体列表"""
        entities = []
        for entity, pack in self.evidence_packs.items():
            if pack['risk_score'] > 0:  # 只返回有发现的实体
                entity_type = 'person' if entity in self.core_persons else 'company'
                evidence_count = sum(len(v) for v in pack['evidence'].values())
                entities.append({
                    'name': entity,
                    'entity': entity,
                    'entity_type': entity_type,
                    'entityType': entity_type,
                    'risk_score': pack['risk_score'],
                    'riskScore': pack['risk_score'],
                    'risk_level': self._normalize_risk_level(pack.get('risk_level'), pack['risk_score']),
                    'riskLevel': self._normalize_risk_level(pack.get('risk_level'), pack['risk_score']),
                    'risk_confidence': pack.get('risk_confidence', 0.05),
                    'riskConfidence': pack.get('risk_confidence', 0.05),
                    'top_evidence_score': pack.get('top_evidence_score', 0.0),
                    'topEvidenceScore': pack.get('top_evidence_score', 0.0),
                    'high_priority_clue_count': pack.get('high_priority_clue_count', 0),
                    'highPriorityClueCount': pack.get('high_priority_clue_count', 0),
                    'summary': pack['summary'],
                    'evidence_count': evidence_count,
                    'evidenceCount': evidence_count,
                    'aggregation_explainability': pack.get('aggregation_explainability', {}),
                    'aggregationExplainability': pack.get('aggregation_explainability', {}),
                    'reasons': [
                        clue.get('description')
                        for clue in pack.get('aggregation_explainability', {}).get('top_clues', [])
                        if clue.get('description')
                    ],
                })
        
        # 按风险分、风险置信度、最强证据强度、高优先线索数降序
        entities.sort(
            key=lambda item: (
                -item['riskScore'],
                -item['riskConfidence'],
                -item['topEvidenceScore'],
                -item['highPriorityClueCount'],
                -item['evidenceCount'],
                item['entity'],
            )
        )
        return entities

    def get_summary(self) -> Dict[str, int]:
        """生成聚合排序摘要。"""
        ranked = self.get_ranked_entities()
        critical = sum(1 for item in ranked if item.get('riskLevel') == 'critical')
        high = sum(1 for item in ranked if item.get('riskLevel') == 'high')
        medium = sum(1 for item in ranked if item.get('riskLevel') == 'medium')
        return {
            '极高风险实体数': critical,
            '高风险实体数': high,
            '中风险实体数': medium,
            '风险实体总数': len(ranked),
            '高优先线索实体数': sum(
                1 for item in ranked if int(item.get('highPriorityClueCount', 0) or 0) > 0
            ),
        }

    def to_dict(self) -> Dict:
        """对外稳定输出聚合结果，兼容前端 camelCase 和旧逻辑 snake_case。"""
        ranked = self.get_ranked_entities()
        summary = self.get_summary()
        evidence_packs = {}

        for entity, pack in self.evidence_packs.items():
            normalized_pack = dict(pack)
            normalized_pack['risk_level'] = self._normalize_risk_level(
                pack.get('risk_level'),
                pack.get('risk_score', 0),
            )
            normalized_pack['riskLevel'] = normalized_pack['risk_level']
            normalized_pack['riskScore'] = pack.get('risk_score', 0)
            normalized_pack['riskConfidence'] = pack.get('risk_confidence', 0.05)
            normalized_pack['topEvidenceScore'] = pack.get('top_evidence_score', 0.0)
            normalized_pack['highPriorityClueCount'] = pack.get('high_priority_clue_count', 0)
            normalized_pack['aggregationExplainability'] = pack.get('aggregation_explainability', {})
            evidence_packs[entity] = normalized_pack

        return {
            'rankedEntities': ranked,
            'summary': summary,
            'evidencePacks': evidence_packs,
            'analysisMetadata': self.analysis_metadata,
            'corePersons': self.core_persons,
            'companies': self.companies,
            'allEntities': self.all_entities,
            # 兼容旧字段
            'ranked_entities': ranked,
            'evidence_packs': evidence_packs,
            'analysis_metadata': self.analysis_metadata,
            'core_persons': self.core_persons,
            'all_entities': self.all_entities,
        }
    
    def get_entity_evidence_pack(self, entity: str) -> Dict:
        """获取指定实体的完整证据包"""
        return self.evidence_packs.get(entity, self._create_empty_pack())


def aggregate_all_results(
    core_persons: List[str],
    companies: List[str],
    penetration_results: Dict = None,
    ml_results: Dict = None,
    ts_results: Dict = None,
    related_party_results: Dict = None,
    loan_results: Dict = None,
    wallet_results: Dict = None,
) -> ClueAggregator:
    """
    聚合所有分析结果
    
    Args:
        core_persons: 核心人员列表
        companies: 涉案公司列表
        penetration_results: 资金穿透结果
        ml_results: 机器学习结果
        ts_results: 时序分析结果
        related_party_results: 关联方分析结果
        loan_results: 借贷分析结果
        wallet_results: 电子钱包补充结果
        
    Returns:
        ClueAggregator 实例
    """
    logger.info('='*60)
    logger.info('开始线索聚合')
    logger.info('='*60)
    
    aggregator = ClueAggregator(core_persons, companies)
    
    if penetration_results:
        aggregator.aggregate_penetration_results(penetration_results)
    
    if ml_results:
        aggregator.aggregate_ml_results(ml_results)
    
    if ts_results:
        aggregator.aggregate_time_series_results(ts_results)
    
    if related_party_results:
        aggregator.aggregate_related_party_results(related_party_results)
    
    if loan_results:
        aggregator.aggregate_loan_results(loan_results)

    if wallet_results:
        aggregator.aggregate_wallet_results(wallet_results)
    
    # 计算综合风险分
    aggregator.calculate_entity_risk_scores()
    
    # 输出摘要
    ranked = aggregator.get_ranked_entities()
    logger.info(f'线索聚合完成: {len(ranked)} 个实体有发现')
    
    for entity in ranked[:5]:
        logger.info(f'  [{entity["risk_level"].upper()}] {entity["entity"]}: {entity["risk_score"]}分 - {entity["summary"][:50]}')
    
    return aggregator


def _write_aggregation_report_header(f) -> None:
    """写入报告头部（含专业说明）"""
    f.write('线索聚合报告（证据包视图）\n')
    f.write('='*60 + '\n')
    f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
    
    # 报告说明
    f.write('【报告用途】\n')
    f.write('本报告以人员/公司为中心，聚合所有分析模块的发现，形成完整的“证据包”\n')
    f.write('每个实体的证据包包括：资金闭环、过账通道、高风险交易、周期性收入等\n\n')
    
    f.write('【风险评分逻辑】\n')
    f.write('1. 基础分 20 分\n')
    f.write('2. 涉及资金闭环: +30分\n')
    f.write('3. 过账通道特征: +20分\n')
    f.write('4. 连接多个实体: +10分(>=3个)\n')
    f.write('5. ML模型检测异常: +15分\n')
    f.write('6. 排序并列时，进一步比较风险置信度、最强证据分和高优先线索数\n\n')
    
    f.write('【风险等级划分】\n')
    f.write('• 极高风险 (70-100分): 建议立即核查\n')
    f.write('• 高风险 (50-70分): 优先核查\n')
    f.write('• 中风险 (30-50分): 酌情关注\n\n')
    
    f.write('【人工复核重点】\n')
    f.write('★ 极高风险实体: 核实证据包中所有线索\n')
    f.write('★ 资金闭环: 核实闭环形成原因\n')
    f.write('★ 过账通道: 核实账户业务实质\n\n')
    
    f.write('='*60 + '\n\n')


def _write_risk_overview_section(f, ranked: List[Dict]) -> None:
    """写入风险概览部分"""
    critical = [e for e in ranked if str(e.get('risk_level', '')).upper() == 'CRITICAL']
    high = [e for e in ranked if str(e.get('risk_level', '')).upper() == 'HIGH']
    medium = [e for e in ranked if str(e.get('risk_level', '')).upper() == 'MEDIUM']
    
    f.write('一、风险概览\n')
    f.write('-'*40 + '\n')
    f.write(f'极高风险 (70-100分): {len(critical)} 个\n')
    f.write(f'高风险 (50-70分): {len(high)} 个\n')
    f.write(f'中风险 (30-50分): {len(medium)} 个\n\n')


def _write_fund_cycles_section(f, cycles: List[Dict]) -> None:
    """写入资金闭环部分"""
    # 去重
    seen_str = set()
    unique_cycles = []
    for cycle in cycles:
        if cycle['cycle_str'] not in seen_str:
            seen_str.add(cycle['cycle_str'])
            unique_cycles.append(cycle)
    
    f.write(f'    ▶ 涉及的资金闭环（{len(unique_cycles)}个不重复）:\n')
    for j, cycle in enumerate(unique_cycles[:5], 1):
        f.write(f'      {j}. {cycle["cycle_str"]}\n')
    if len(unique_cycles) > 5:
        f.write(f'      ... 等共{len(unique_cycles)}个\n')
    f.write('\n')


def _write_pass_through_section(f, pass_through: List[Dict]) -> None:
    """写入过账通道部分"""
    f.write('    ▶ 过账通道特征:\n')
    for ch in pass_through[:3]:
        f.write(
            f'      进账: {ch.get("inflow", 0)/10000:.2f}万 | 出账: {ch.get("outflow", 0)/10000:.2f}万 '
            f'| 进出比: {ch.get("ratio", 0)*100:.1f}% | 证据分: {ch.get("risk_score", 0):.1f}\n'
        )
    f.write('\n')


def _write_high_risk_transactions_section(f, transactions: List[Dict]) -> None:
    """写入高风险交易部分"""
    f.write('    ▶ 高风险交易 (已排除正规金融机构):\n')
    for j, tx in enumerate(transactions[:5], 1):
        date_str = str(tx.get('date', ''))[:10]
        cp = tx.get('counterparty', '未知')
        if len(cp) > 15:
            cp = cp[:15] + '...'
        f.write(f'      {j}. [{date_str}] {cp}: {tx.get("amount", 0)/10000:.2f}万\n')
    if len(transactions) > 5:
        f.write(f'      ... 共{len(transactions)}笔\n')
    f.write('\n')


def _write_periodic_income_section(f, periodic_income: List[Dict]) -> None:
    """写入周期性收入部分"""
    f.write('    ▶ 周期性收入模式:\n')
    for j, p in enumerate(periodic_income[:3], 1):
        f.write(f'      {j}. ← {p.get("counterparty", "未知")}: {p.get("period_type", "")} 均额{p.get("avg_amount", 0)/10000:.2f}万\n')
    f.write('\n')


def _write_sudden_changes_section(f, sudden_changes: List[Dict]) -> None:
    """写入资金突变部分"""
    # 计算时间范围
    dates = [s.get('date', '') for s in sudden_changes if s.get('date')]
    date_range = ''
    if dates:
        dates_sorted = sorted([str(d)[:10] for d in dates])
        date_range = f' [{dates_sorted[0]} ~ {dates_sorted[-1]}]'
    
    f.write(f'    ▶ 资金突变事件{date_range} (需人工核实是否理财):\n')
    for j, s in enumerate(sudden_changes[:3], 1):
        f.write(f'      {j}. {str(s.get("date", ""))[:10]}: {s.get("amount", 0)/10000:.2f}万 (Z值{s.get("z_score", 0):.1f})\n')
    if len(sudden_changes) > 3:
        f.write(f'      ... 共{len(sudden_changes)}次 (可能含理财买卖)\n')
    f.write('\n')


def _write_delayed_transfers_section(f, delayed_transfers: List[Dict]) -> None:
    """写入固定延迟转账部分（修复 nan 显示）"""
    def safe_str(val, max_len=10):
        if val is None:
            return '(未知)'
        s = str(val)
        if s == 'nan' or not s:
            return '(未知)'
        return s[:max_len] if len(s) > max_len else s
    
    f.write('    ▶ 固定延迟转账模式:\n')
    for j, d in enumerate(delayed_transfers[:3], 1):
        count = d.get('occurrences', d.get('count', 0))
        income_from = safe_str(d.get('income_from', d.get('income_counterparty', '')))
        expense_to = safe_str(d.get('expense_to', d.get('expense_counterparty', '')))
        f.write(f'      {j}. ← {income_from} 收入后{d.get("delay_days", 0)}天 → {expense_to}\n')
        f.write(f'         次数: {count} | 总额: {d.get("total_amount", 0)/10000:.2f}万\n')
    f.write('\n')


def _write_third_party_relays_section(f, relays: List[Dict]) -> None:
    """写入第三方中转部分。"""
    f.write('    ▶ 第三方中转链路:\n')
    for j, relay in enumerate(relays[:3], 1):
        f.write(
            f'      {j}. {relay.get("from", "未知")} → {relay.get("relay", "未知")} → {relay.get("to", "未知")} '
            f'| 金额: {relay.get("outflow_amount", 0)/10000:.2f}万 | 证据分: {relay.get("risk_score", 0):.1f}\n'
        )
    if len(relays) > 3:
        f.write(f'      ... 共{len(relays)}条\n')
    f.write('\n')


def _write_discovered_nodes_section(f, nodes: List[Dict]) -> None:
    """写入外围节点部分。"""
    f.write('    ▶ 外围节点发现:\n')
    for j, node in enumerate(nodes[:3], 1):
        linked_cores = '、'.join(node.get('linked_cores', [])[:3]) or '未知核心对象'
        f.write(
            f'      {j}. {node.get("name", "未知节点")} | 核心关联: {linked_cores} '
            f'| 出现次数: {node.get("occurrences", 0)} | 证据分: {node.get("risk_score", 0):.1f}\n'
        )
    if len(nodes) > 3:
        f.write(f'      ... 共{len(nodes)}个\n')
    f.write('\n')


def _write_relationship_clusters_section(f, clusters: List[Dict]) -> None:
    """写入关系簇部分。"""
    f.write('    ▶ 关系簇识别:\n')
    for j, cluster in enumerate(clusters[:3], 1):
        core_members = '、'.join(cluster.get('core_members', [])[:3]) or '未知'
        external_members = '、'.join(cluster.get('external_members', [])[:3]) or '无'
        f.write(
            f'      {j}. 核心成员: {core_members} | 外围成员: {external_members} '
            f'| 闭环/中转/直连: {cluster.get("loop_count", 0)}/{cluster.get("relay_count", 0)}/{cluster.get("direct_flow_count", 0)} '
            f'| 证据分: {cluster.get("risk_score", 0):.1f}\n'
        )
    if len(clusters) > 3:
        f.write(f'      ... 共{len(clusters)}个\n')
    f.write('\n')


def _write_wallet_summaries_section(f, summaries: List[Dict]) -> None:
    """写入电子钱包主体摘要部分。"""
    f.write('    ▶ 电子钱包补充摘要:\n')
    for j, item in enumerate(summaries[:3], 1):
        f.write(
            f'      {j}. 累计收支: {item.get("third_party_total", 0)/10000:.2f}万 | '
            f'交易笔数: {item.get("transaction_count", 0)} | '
            f'银行卡/别名重叠: {item.get("bank_card_overlap_count", 0)}/{item.get("alias_match_count", 0)} | '
            f'证据分: {item.get("risk_score", 0):.1f}\n'
        )
    if len(summaries) > 3:
        f.write(f'      ... 共{len(summaries)}条\n')
    f.write('\n')


def _write_wallet_alerts_section(f, alerts: List[Dict]) -> None:
    """写入电子钱包预警部分。"""
    f.write('    ▶ 电子钱包预警:\n')
    for j, item in enumerate(alerts[:3], 1):
        f.write(
            f'      {j}. {item.get("person", "未知")} → {item.get("counterparty", "未知")} | '
            f'金额: {item.get("amount", 0)/10000:.2f}万 | '
            f'等级: {str(item.get("risk_level", "medium")).upper()} | '
            f'证据分: {item.get("risk_score", 0):.1f}\n'
        )
    if len(alerts) > 3:
        f.write(f'      ... 共{len(alerts)}条\n')
    f.write('\n')


def _write_communities_section(f, communities: List[Dict]) -> None:
    """写入团伙部分"""
    # 只显示有意义的团伙
    valid_communities = [c for c in communities if len(c.get('members', [])) >= 2]
    if valid_communities:
        f.write('    ▶ 关联资金团伙 (已排除理财账户):\n')
        for j, c in enumerate(valid_communities[:3], 1):
            members_str = ', '.join(c.get('members', [])[:5])
            if members_str:
                f.write(f'      {j}. {c.get("type", "")}: {members_str}\n')
        f.write('\n')


def _write_entity_evidence_pack(f, aggregator: ClueAggregator, entity_info: Dict, index: int) -> None:
    """写入单个实体的证据包"""
    entity = entity_info['entity']
    pack = aggregator.get_entity_evidence_pack(entity)
    
    f.write(f'【{index}】{entity}\n')
    f.write(f'    风险评分: {pack["risk_score"]}分 [{pack["risk_level"].upper()}]\n')
    f.write(
        f'    风险置信度: {pack.get("risk_confidence", 0.05):.2f} | '
        f'最强证据分: {pack.get("top_evidence_score", 0.0):.1f} | '
        f'高优先线索数: {pack.get("high_priority_clue_count", 0)}\n'
    )
    f.write(f'    综合评估: {pack["summary"]}\n\n')
    
    evidence = pack['evidence']
    
    # 资金闭环
    if evidence['fund_cycles']:
        _write_fund_cycles_section(f, evidence['fund_cycles'])
    
    # 过账通道
    if evidence['pass_through']:
        _write_pass_through_section(f, evidence['pass_through'])
    
    # 高风险交易
    if evidence['high_risk_transactions']:
        _write_high_risk_transactions_section(f, evidence['high_risk_transactions'])
    
    # 周期性收入
    if evidence['periodic_income']:
        _write_periodic_income_section(f, evidence['periodic_income'])
    
    # 资金突变
    if evidence['sudden_changes']:
        _write_sudden_changes_section(f, evidence['sudden_changes'])
    
    # 固定延迟转账
    if evidence['delayed_transfers']:
        _write_delayed_transfers_section(f, evidence['delayed_transfers'])

    # 第三方中转
    if evidence['third_party_relays']:
        _write_third_party_relays_section(f, evidence['third_party_relays'])

    # 外围节点
    if evidence['discovered_nodes']:
        _write_discovered_nodes_section(f, evidence['discovered_nodes'])

    # 关系簇
    if evidence['relationship_clusters']:
        _write_relationship_clusters_section(f, evidence['relationship_clusters'])

    # 电子钱包摘要
    if evidence['wallet_summaries']:
        _write_wallet_summaries_section(f, evidence['wallet_summaries'])

    # 电子钱包预警
    if evidence['wallet_alerts']:
        _write_wallet_alerts_section(f, evidence['wallet_alerts'])
    
    # 团伙
    if evidence['communities']:
        _write_communities_section(f, evidence['communities'])
    
    f.write('-'*60 + '\n\n')


def generate_aggregation_report(aggregator: ClueAggregator, output_dir: str) -> str:
    """生成线索聚合报告"""
    import os
    report_path = os.path.join(output_dir, '线索聚合报告.txt')
    
    ranked = aggregator.get_ranked_entities()
    
    with open(report_path, 'w', encoding='utf-8') as f:
        _write_aggregation_report_header(f)
        
        # 风险概览
        _write_risk_overview_section(f, ranked)
        
        # 逐个输出证据包
        f.write('二、实体证据包（按风险分排序）\n')
        f.write('='*60 + '\n\n')
        
        for i, entity_info in enumerate(ranked, 1):
            _write_entity_evidence_pack(f, aggregator, entity_info, i)
    
    logger.info(f'线索聚合报告已生成: {report_path}')
    return report_path
