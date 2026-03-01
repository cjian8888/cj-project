"""
固定频率检测器 - FixedFrequencyDetector
检测固定频率的收入或支出模式，识别规律性资金往来。
"""

from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Any, Optional
import uuid

from detectors.base_detector import BaseDetector
from schemas.suspicion import SuspicionSeverity, SuspicionType


class FixedFrequencyDetector(BaseDetector):
    """检测固定频率的资金往来模式。

    该检测器分析交易数据，识别出以固定时间间隔（如每月、每周）
    发生的相似金额交易，这类模式可能表明规律性收入、还款或
    其他周期性资金往来。
    """

    @property
    def name(self) -> str:
        return "fixed_frequency"

    @property
    def description(self) -> str:
        return "检测固定频率的收入或支出模式，识别规律性资金往来"

    @property
    def risk_level(self) -> str:
        return "中"

    def detect(
        self, data: Dict[str, Any], config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行固定频率检测。

        Args:
            data: 包含交易数据的字典，必须包含 'transactions' 键
            config: 检测配置参数
                - min_occurrences: 最小出现次数阈值（默认3）
                - amount_tolerance: 金额容差比例（默认0.1，即10%）
                - day_tolerance: 日期容差天数（默认3天）

        Returns:
            List[Dict]: 检测到的疑点列表，每个元素符合 Suspicion 模型
        """
        transactions = data.get("transactions", [])
        entity_name = data.get("entity_name", "未知实体")

        if not transactions or len(transactions) < 2:
            return []

        min_occurrences = config.get("min_occurrences", 3)
        amount_tolerance = config.get("amount_tolerance", 0.1)
        day_tolerance = config.get("day_tolerance", 3)

        parsed_transactions = self._parse_transactions(transactions)
        patterns = self._find_frequency_patterns(
            parsed_transactions, min_occurrences, amount_tolerance, day_tolerance
        )

        return self._create_suspicion_results(patterns, entity_name)

    def _parse_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """解析交易数据，标准化日期和金额格式。"""
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
                    "raw_data": tx,
                }
                if parsed_tx["date"] is not None:
                    parsed.append(parsed_tx)
            except (ValueError, TypeError):
                continue
        return sorted(parsed, key=lambda x: x["date"])

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

    def _find_frequency_patterns(
        self,
        transactions: List[Dict],
        min_occurrences: int,
        amount_tolerance: float,
        day_tolerance: int,
    ) -> List[Dict]:
        """查找固定频率模式。"""
        patterns = []

        if len(transactions) < min_occurrences:
            return patterns

        grouped = self._group_by_counterparty_and_amount(transactions, amount_tolerance)

        for group_key, group_transactions in grouped.items():
            if len(group_transactions) < min_occurrences:
                continue

            counterparty, abs_amount = group_key
            dates = [tx["date"] for tx in group_transactions]

            interval_pattern = self._analyze_interval_pattern(dates, day_tolerance)

            if interval_pattern["is_regular"]:
                pattern = {
                    "counterparty": counterparty,
                    "amount": abs_amount,
                    "tx_type": group_transactions[0]["tx_type"],
                    "occurrences": len(group_transactions),
                    "dates": dates,
                    "interval_type": interval_pattern["type"],
                    "transactions": group_transactions,
                }
                patterns.append(pattern)

        return patterns

    def _group_by_counterparty_and_amount(
        self, transactions: List[Dict], tolerance: float
    ) -> Dict:
        """按对手方和金额对交易进行分组。"""
        groups = defaultdict(list)

        for tx in transactions:
            counterparty = tx.get("counterparty", "").strip()
            amount = tx.get("amount", 0)
            abs_amount = abs(amount)

            key_found = False
            for cp, amt in list(groups.keys()):
                if cp == counterparty:
                    if abs(amt - abs_amount) / max(amt, 1) <= tolerance:
                        groups[(cp, amt)].append(tx)
                        key_found = True
                        break

            if not key_found:
                groups[(counterparty, abs_amount)].append(tx)

        return dict(groups)

    def _analyze_interval_pattern(
        self, dates: List[date], day_tolerance: int
    ) -> Dict[str, Any]:
        """分析日期间隔模式。"""
        if len(dates) < 2:
            return {"is_regular": False, "type": "unknown"}

        sorted_dates = sorted(dates)
        intervals = []

        for i in range(1, len(sorted_dates)):
            delta = (sorted_dates[i] - sorted_dates[i - 1]).days
            intervals.append(delta)

        if not intervals:
            return {"is_regular": False, "type": "unknown"}

        # 【P1修复】空列表除法检查
        avg_interval = sum(intervals) / len(intervals) if intervals else 0

        is_regular = all(
            abs(interval - avg_interval) <= day_tolerance for interval in intervals
        )

        pattern_type = self._classify_interval_type(avg_interval)

        return {
            "is_regular": is_regular,
            "type": pattern_type,
            "avg_interval": avg_interval,
        }

    def _classify_interval_type(self, avg_interval: float) -> str:
        """根据平均间隔天数分类周期类型。"""
        if 6 <= avg_interval <= 8:
            return "每周"
        elif 13 <= avg_interval <= 15:
            return "双周"
        elif 27 <= avg_interval <= 32:
            return "每月"
        elif 85 <= avg_interval <= 95:
            return "每季度"
        elif 360 <= avg_interval <= 370:
            return "每年"
        else:
            return f"每{int(avg_interval)}天"

    def _create_suspicion_results(
        self, patterns: List[Dict], entity_name: str
    ) -> List[Dict[str, Any]]:
        """创建疑点检测结果。"""
        results = []

        for i, pattern in enumerate(patterns):
            suspicion_id = f"FF{datetime.now().strftime('%Y%m%d')}{str(i + 1).zfill(3)}"

            amount = pattern["amount"]
            occurrences = pattern["occurrences"]
            counterparty = pattern["counterparty"]
            interval_type = pattern["interval_type"]
            tx_type = pattern["tx_type"]

            if tx_type == "收入":
                description = (
                    f"发现规律性收入模式：与{counterparty}存在{interval_type}固定金额"
                    f"收入 {occurrences} 次，每次金额约 {amount:,.2f} 元"
                )
            else:
                description = (
                    f"发现规律性支出模式：向{counterparty}进行{interval_type}固定金额"
                    f"支出 {occurrences} 次，每次金额约 {abs(amount):,.2f} 元"
                )

            related_tx_ids = [
                f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
                for tx in pattern["transactions"]
            ]

            confidence = min(0.5 + (occurrences - 3) * 0.1, 0.95)

            suspicion = {
                "suspicion_id": suspicion_id,
                "suspicion_type": SuspicionType.FREQUENT_TRANSFER.value,
                "severity": SuspicionSeverity.MEDIUM.value,
                "description": description,
                "related_transactions": related_tx_ids[:100],
                "amount": abs(amount) * occurrences,
                "detection_date": date.today(),
                "entity_name": entity_name,
                "confidence": confidence,
                "evidence": f"周期类型: {interval_type}, 发生次数: {occurrences}",
                "status": "待核实",
            }

            results.append(suspicion)

        return results
