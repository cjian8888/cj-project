"""
整数金额检测器 - RoundAmountDetector
检测整数金额交易，如10000、50000等。
"""
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Any, Optional

from detectors.base_detector import BaseDetector
from schemas.suspicion import SuspicionSeverity, SuspicionType


class RoundAmountDetector(BaseDetector):
    """检测整数金额交易模式。
    
    该检测器分析交易金额，识别偏好整数金额（如10000、50000等）的交易行为。
    频繁使用整数金额可能表明人为设定的交易，如贿赂、规避监管等。
    """

    @property
    def name(self) -> str:
        return "round_amount"

    @property
    def description(self) -> str:
        return "检测整数金额交易，如10000、50000等"

    @property
    def risk_level(self) -> str:
        return "低"

    def detect(self, data: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行整数金额检测。
        
        Args:
            data: 包含交易数据的字典，必须包含 'transactions' 键
            config: 检测配置参数
                - min_amount: 最低金额阈值（默认10000）
                - round_unit: 整数单位（默认10000，即以万为单位）
                - min_occurrences: 最小出现次数（默认5）
                - lucky_numbers: 吉利数字尾号列表（默认['88', '66', '88', '66']）
                
        Returns:
            List[Dict]: 检测到的疑点列表
        """
        transactions = data.get("transactions", [])
        entity_name = data.get("entity_name", "未知实体")
        
        if not transactions or len(transactions) < 2:
            return []
        
        min_amount = config.get("min_amount", 10000)
        round_unit = config.get("round_unit", 10000)
        min_occurrences = config.get("min_occurrences", 5)
        lucky_numbers = config.get("lucky_numbers", ['88', '66', '888', '666', '168'])
        
        parsed_transactions = self._parse_transactions(transactions)
        
        # 分类统计
        round_amount_txs = []
        lucky_number_txs = []
        
        for tx in parsed_transactions:
            abs_amount = abs(tx["amount"])
            if abs_amount < min_amount:
                continue
            
            if self._is_round_amount(abs_amount, round_unit):
                round_amount_txs.append(tx)
            
            if self._has_lucky_tail(abs_amount, lucky_numbers):
                lucky_number_txs.append(tx)
        
        results = []
        results.extend(self._create_round_amount_suspicions(
            round_amount_txs, entity_name, min_occurrences, round_unit
        ))
        results.extend(self._create_lucky_number_suspicions(
            lucky_number_txs, entity_name, min_occurrences
        ))
        
        return results

    def _parse_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """解析交易数据。"""
        parsed = []
        for tx in transactions:
            try:
                parsed_tx = {
                    "date": self._parse_date(tx.get("tx_date")),
                    "amount": float(tx.get("amount", 0)),
                    "tx_type": tx.get("tx_type", ""),
                    "counterparty": tx.get("counterparty", ""),
                    "account": tx.get("account", ""),
                    "bank": tx.get("bank", ""),
                    "raw_data": tx
                }
                parsed.append(parsed_tx)
            except (ValueError, TypeError):
                continue
        return parsed

    def _parse_date(self, date_value: Any) -> Optional[date]:
        """解析日期字段为 date 对象。"""
        if isinstance(date_value, date):
            return date_value
        if isinstance(date_value, datetime):
            return date_value.date()
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, "%Y-%m-%d").date()
            except ValueError:
                try:
                    return datetime.strptime(date_value, "%Y/%m/%d").date()
                except ValueError:
                    return None
        return None

    def _is_round_amount(self, amount: float, unit: int) -> bool:
        """判断金额是否为整数单位。"""
        remainder = amount % unit
        return remainder == 0 or remainder < 0.01

    def _has_lucky_tail(self, amount: float, lucky_numbers: List[str]) -> bool:
        """判断金额是否包含吉利数字尾号。"""
        amount_str = f"{int(amount)}"
        for tail in lucky_numbers:
            if amount_str.endswith(tail):
                return True
        return False

    def _create_round_amount_suspicions(
        self, 
        transactions: List[Dict], 
        entity_name: str,
        min_occurrences: int,
        round_unit: int
    ) -> List[Dict[str, Any]]:
        """创建整数金额疑点。"""
        if len(transactions) < min_occurrences:
            return []
        
        total_amount = sum(abs(tx["amount"]) for tx in transactions)
        tx_count = len(transactions)
        
        # 按金额分组统计
        amount_groups = defaultdict(list)
        for tx in transactions:
            amount_groups[abs(tx["amount"])].append(tx)
        
        # 找出最常见的整数金额
        top_amounts = sorted(amount_groups.items(), key=lambda x: len(x[1]), reverse=True)[:3]
        top_amounts_str = ", ".join([f"{amt:,.0f}元({len(txs)}笔)" for amt, txs in top_amounts])
        
        related_tx_ids = [
            f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
            for tx in transactions[:50]
        ]
        
        suspicion_id = f"RA{datetime.now().strftime('%Y%m%d')}001"
        
        description = (
            f"发现整数金额交易偏好：共有 {tx_count} 笔整数金额交易（以{round_unit/10000:.0f}万元为单位），"
            f"涉及总金额 {total_amount:,.2f} 元。常见金额：{top_amounts_str}。"
            f"频繁使用整数金额可能表明人为设定的交易金额。"
        )
        
        if tx_count >= 20:
            severity = SuspicionSeverity.MEDIUM.value
            confidence = 0.8
        elif tx_count >= 10:
            severity = SuspicionSeverity.LOW.value
            confidence = 0.65
        else:
            severity = SuspicionSeverity.LOW.value
            confidence = 0.5
        
        suspicion = {
            "suspicion_id": suspicion_id,
            "suspicion_type": SuspicionType.ROUND_AMOUNT.value,
            "severity": severity,
            "description": description,
            "related_transactions": related_tx_ids,
            "amount": total_amount,
            "detection_date": date.today(),
            "entity_name": entity_name,
            "confidence": confidence,
            "evidence": f"整数金额交易: {tx_count}笔, 总金额: {total_amount:,.2f}元, 单位: {round_unit/10000:.0f}万元",
            "status": "待核实"
        }
        
        return [suspicion]

    def _create_lucky_number_suspicions(
        self, 
        transactions: List[Dict], 
        entity_name: str,
        min_occurrences: int
    ) -> List[Dict[str, Any]]:
        """创建吉利数字金额疑点。"""
        if len(transactions) < min_occurrences:
            return []
        
        total_amount = sum(abs(tx["amount"]) for tx in transactions)
        tx_count = len(transactions)
        
        related_tx_ids = [
            f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
            for tx in transactions[:50]
        ]
        
        suspicion_id = f"RA{datetime.now().strftime('%Y%m%d')}002"
        
        description = (
            f"发现吉利数字金额交易：共有 {tx_count} 笔包含吉利数字尾号的交易（如88、66、168等），"
            f"涉及总金额 {total_amount:,.2f} 元。使用吉利数字作为交易金额可能具有特殊含义。"
        )
        
        severity = SuspicionSeverity.LOW.value
        confidence = 0.55
        
        suspicion = {
            "suspicion_id": suspicion_id,
            "suspicion_type": SuspicionType.ROUND_AMOUNT.value,
            "severity": severity,
            "description": description,
            "related_transactions": related_tx_ids,
            "amount": total_amount,
            "detection_date": date.today(),
            "entity_name": entity_name,
            "confidence": confidence,
            "evidence": f"吉利数字金额交易: {tx_count}笔, 总金额: {total_amount:,.2f}元",
            "status": "待核实"
        }
        
        return [suspicion]
