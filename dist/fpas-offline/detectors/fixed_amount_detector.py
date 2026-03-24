"""
固定金额检测器 - FixedAmountDetector
检测固定金额的交易模式，如每次恰好50000元的交易。
"""
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Any, Optional

from detectors.base_detector import BaseDetector
from schemas.suspicion import SuspicionSeverity, SuspicionType
import utils


class FixedAmountDetector(BaseDetector):
    """检测固定金额交易模式。
    
    该检测器分析交易数据，识别出金额完全相同且频繁出现的交易金额，
    这类模式可能表明人为设定的固定金额交易，如规避监管的拆分交易。
    """

    @property
    def name(self) -> str:
        return "fixed_amount"

    @property
    def description(self) -> str:
        return "检测固定金额交易模式，识别频繁出现的相同金额交易"

    @property
    def risk_level(self) -> str:
        return "中"

    def detect(self, data: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行固定金额检测。
        
        Args:
            data: 包含交易数据的字典，必须包含 'transactions' 键
            config: 检测配置参数
                - min_occurrences: 最小出现次数阈值（默认3）
                - amount_threshold: 最低金额阈值（默认10000）
                - tolerance: 金额容差（默认0，即要求精确相等）
                
        Returns:
            List[Dict]: 检测到的疑点列表
        """
        transactions = data.get("transactions", [])
        entity_name = data.get("entity_name", "未知实体")
        
        if not transactions or len(transactions) < 2:
            return []
        
        # 从配置获取阈值
        min_occurrences = config.get("min_occurrences", 3)
        amount_threshold = config.get("amount_threshold", 10000)
        tolerance = config.get("tolerance", 0)
        
        # 解析交易
        parsed_transactions = self._parse_transactions(transactions)
        
        # 按金额分组
        amount_groups = self._group_by_amount(parsed_transactions, tolerance)
        
        # 找出异常固定金额
        anomalies = []
        for amount, txs in amount_groups.items():
            if abs(amount) >= amount_threshold and len(txs) >= min_occurrences:
                anomalies.append({
                    "amount": amount,
                    "occurrences": len(txs),
                    "transactions": txs
                })
        
        return self._create_suspicion_results(anomalies, entity_name)

    def _parse_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """解析交易数据，标准化日期和金额格式。"""
        parsed = []
        for tx in transactions:
            try:
                parsed_tx = {
                    "date": self._parse_date(tx.get("tx_date")),
                    "amount": utils.format_amount(tx.get("amount", 0)),
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
        parsed = utils.parse_date(date_value)
        return parsed.date() if parsed else None

    def _group_by_amount(self, transactions: List[Dict], tolerance: float) -> Dict[float, List[Dict]]:
        """按金额对交易进行分组。"""
        groups = defaultdict(list)
        
        for tx in transactions:
            amount = tx.get("amount", 0)
            abs_amount = abs(amount)
            
            if tolerance == 0:
                # 精确匹配
                groups[abs_amount].append(tx)
            else:
                # 容差匹配
                found = False
                for existing_amount in list(groups.keys()):
                    if abs(existing_amount - abs_amount) / max(existing_amount, 1) <= tolerance:
                        groups[existing_amount].append(tx)
                        found = True
                        break
                if not found:
                    groups[abs_amount].append(tx)
        
        return dict(groups)

    def _create_suspicion_results(
        self, 
        anomalies: List[Dict], 
        entity_name: str
    ) -> List[Dict[str, Any]]:
        """创建疑点检测结果。"""
        results = []
        
        for i, anomaly in enumerate(anomalies):
            suspicion_id = f"FA{datetime.now().strftime('%Y%m%d')}{str(i+1).zfill(3)}"
            
            amount = anomaly["amount"]
            occurrences = anomaly["occurrences"]
            transactions = anomaly["transactions"]
            
            # 计算总金额
            total_amount = amount * occurrences
            
            # 获取交易类型描述
            income_count = sum(1 for tx in transactions if tx["amount"] > 0)
            expense_count = sum(1 for tx in transactions if tx["amount"] < 0)
            
            if income_count > 0 and expense_count > 0:
                tx_type_desc = f"双向交易（收入{income_count}次，支出{expense_count}次）"
            elif income_count > 0:
                tx_type_desc = f"收入交易"
            else:
                tx_type_desc = f"支出交易"
            
            description = (
                f"发现固定金额异常：金额 {amount:,.2f} 元在 {occurrences} 笔交易中出现，"
                f"涉及总金额 {total_amount:,.2f} 元，交易类型为{tx_type_desc}。"
                f"该金额重复出现可能为规避监管的拆分交易或固定额度的利益输送。"
            )
            
            related_tx_ids = [
                f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
                for tx in transactions[:50]
            ]
            
            # 根据出现次数确定严重程度和置信度
            if occurrences >= 10:
                severity = SuspicionSeverity.HIGH.value
                confidence = 0.9
            elif occurrences >= 5:
                severity = SuspicionSeverity.MEDIUM.value
                confidence = 0.75
            else:
                severity = SuspicionSeverity.LOW.value
                confidence = 0.6
            
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
                "evidence": f"固定金额: {amount:,.2f}元, 出现次数: {occurrences}, 交易类型: {tx_type_desc}",
                "status": "待核实"
            }
            
            results.append(suspicion)
        
        return results
