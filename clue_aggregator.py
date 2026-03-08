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

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

import config
import utils
from unified_risk_model import UnifiedRiskModel, calculate_financial_ratio, calculate_family_transfer_ratio

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
        
        # 每个实体的证据包
        self.evidence_packs = {entity: self._create_empty_pack() for entity in self.all_entities}
        
    def _create_empty_pack(self) -> Dict:
        """创建空证据包"""
        return {
            'risk_score': 0,
            'risk_level': 'low',
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
                'loans': []                  # 借贷关系
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
        
        # 聚合资金闭环（去重）
        seen_cycles = set()
        for cycle in penetration_results.get('fund_cycles', []):
            # 【P1 修复 2026-01-27】处理不同数据格式
            # cycle 可能是 List[str] 或 Dict
            if isinstance(cycle, dict):
                # 如果是字典，提取 cycle 键的值
                cycle_list = cycle.get('cycle', [])
                cycle_str = cycle.get('cycle_str', ' → '.join(cycle_list) if cycle_list else '')
            else:
                cycle_list = cycle
                cycle_str = ' → '.join(cycle) if cycle else ''
            
            # 【P1 修复 2026-01-28】使用 json 序列化作为唯一标识，避免包含字典
            # 这样无论 cycle_list 中是什么类型，都可以放入 set
            try:
                cycle_key = tuple(cycle_list) if cycle_list else ()
                # 检查是否所有元素都是字符串
                all_strings = all(isinstance(item, str) for item in cycle_key)
                if not all_strings:
                    # 如果包含非字符串元素，使用 json 序列化
                    import json
                    cycle_key = json.dumps(cycle, sort_keys=True, ensure_ascii=False)
                
                if cycle_key in seen_cycles:
                    continue
                seen_cycles.add(cycle_key)
            except (TypeError, ValueError) as e:
                # 如果 cycle_list 包含不可排序的元素或无法序列化，跳过
                logger.warning(f"跳过无法处理的闭环: {cycle}, 错误: {e}")
                continue
            
            # 闭环涉及的所有实体
            for entity in cycle_list:
                if entity in self.evidence_packs:
                    self.evidence_packs[entity]['evidence']['fund_cycles'].append({
                        'cycle': cycle_list,
                        'cycle_str': cycle_str,
                        'length': len(cycle_list)
                    })
        
        # 聚合过账通道
        for channel in penetration_results.get('pass_through_channels', []):
            entity = channel.get('node')
            if entity in self.evidence_packs:
                self.evidence_packs[entity]['evidence']['pass_through'].append(channel)
        
        # 聚合资金枢纽
        for hub in penetration_results.get('hub_nodes', []):
            entity = hub.get('node')
            if entity in self.evidence_packs:
                self.evidence_packs[entity]['evidence']['hub_connections'].append(hub)
        
        # 聚合直接往来
        for tx_type in ['person_to_company', 'company_to_person', 'person_to_person', 'company_to_company']:
            for tx in penetration_results.get(tx_type, []):
                sender = tx.get('发起方')
                receiver = tx.get('接收方')
                if sender in self.evidence_packs:
                    self.evidence_packs[sender]['evidence']['related_party'].append(tx)
                if receiver in self.evidence_packs:
                    self.evidence_packs[receiver]['evidence']['related_party'].append(tx)
    
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
        
        # 直接往来
        for tx in rp_results.get('direct_transactions', []):
            for entity in self.all_entities:
                if entity in str(tx.get('person1', '')) or entity in str(tx.get('person2', '')):
                    if entity in self.evidence_packs:
                        self.evidence_packs[entity]['evidence']['related_party'].append(tx)
    
    def aggregate_loan_results(self, loan_results: Dict):
        """聚合借贷分析结果"""
        logger.info('聚合借贷分析结果...')
        
        # 双向往来
        relations = loan_results.get('bidirectional_flows', loan_results.get('bidirectional', []))
        for relation in relations:
            entity = relation.get('person')
            if entity in self.evidence_packs:
                self.evidence_packs[entity]['evidence']['loans'].append(relation)
    
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
            
            # 准备风险评分所需的数据
            risk_evidence = {
                'money_loops': evidence.get('fund_cycles', []),
                'transit_channel': self._extract_transit_channel_info(evidence),
                'related_entities': [x for x in (hub_entities + community_members) if x],
                'ml_anomalies': evidence.get('high_risk_transactions', []),
                'total_records': stats.get('total_records', stats.get('transaction_count', 0))
            }
            
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
            pack['risk_level'] = risk_score.risk_level
            pack['summary'] = risk_score.reason
            pack['risk_confidence'] = risk_score.confidence
            pack['risk_details'] = risk_score.details
            
            logger.info(f"{entity} 统一风险评分: {risk_score.total_score:.1f} ({risk_score.risk_level})")
    
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
                entities.append({
                    'entity': entity,
                    'entity_type': 'person' if entity in self.core_persons else 'company',
                    'risk_score': pack['risk_score'],
                    'risk_level': pack['risk_level'],
                    'summary': pack['summary'],
                    'evidence_count': sum(len(v) for v in pack['evidence'].values())
                })
        
        # 按风险分降序
        entities.sort(key=lambda x: -x['risk_score'])
        return entities
    
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
    loan_results: Dict = None
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
    f.write('5. ML模型检测异常: +15分\n\n')
    
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
        f.write(f'      进账: {ch.get("inflow", 0)/10000:.2f}万 | 出账: {ch.get("outflow", 0)/10000:.2f}万 | 进出比: {ch.get("ratio", 0)*100:.1f}%\n')
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
