"""
时间异常检测器 - TimeAnomalyDetector
检测异常时间的交易，如凌晨、节假日等的交易。
"""

from datetime import date, datetime, time
from typing import Dict, List, Any, Optional, Set, Tuple

from detectors.base_detector import BaseDetector
from schemas.suspicion import SuspicionSeverity, SuspicionType


class TimeAnomalyDetector(BaseDetector):
    """检测异常时间的交易活动。

    该检测器分析交易发生的时间，识别在凌晨、深夜、节假日等
    非正常工作时间的交易，这类交易可能具有特殊目的或风险。
    """

    @property
    def name(self) -> str:
        return "time_anomaly"

    @property
    def description(self) -> str:
        return "检测异常时间的交易，如凌晨、节假日等"

    @property
    def risk_level(self) -> str:
        return "中"

    def detect(
        self, data: Dict[str, Any], config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行时间异常检测。

        Args:
            data: 包含交易数据的字典，必须包含 'transactions' 键
            config: 检测配置参数
                - off_hours_start: 非工作时段开始时间（小时，默认22）
                - off_hours_end: 非工作时段结束时间（小时，默认6）
                - holiday_threshold: 节假日大额交易阈值（默认50000）
                - weekend_threshold: 周末大额交易阈值（默认50000）
                - min_amount: 检测的最低金额（默认10000）

        Returns:
            List[Dict]: 检测到的疑点列表
        """
        transactions = data.get("transactions", [])
        entity_name = data.get("entity_name", "未知实体")

        if not transactions:
            return []

        off_hours_start = config.get("off_hours_start", 22)
        off_hours_end = config.get("off_hours_end", 6)
        holiday_threshold = config.get("holiday_threshold", 50000)
        weekend_threshold = config.get("weekend_threshold", 50000)
        min_amount = config.get("min_amount", 10000)
        holidays = config.get("holidays", self._get_default_holidays())

        parsed_transactions = self._parse_transactions(transactions)

        off_hours_txs = []
        holiday_txs = []
        weekend_txs = []

        for tx in parsed_transactions:
            abs_amount = abs(tx["amount"])
            if abs_amount < min_amount:
                continue

            if self._is_off_hours(tx["datetime"], off_hours_start, off_hours_end):
                off_hours_txs.append(tx)

            if (
                self._is_holiday(tx["date"], holidays)
                and abs_amount >= holiday_threshold
            ):
                holiday_txs.append(tx)

            if self._is_weekend(tx["date"]) and abs_amount >= weekend_threshold:
                weekend_txs.append(tx)

        results = []
        results.extend(self._create_off_hours_suspicions(off_hours_txs, entity_name))
        results.extend(self._create_holiday_suspicions(holiday_txs, entity_name))
        results.extend(self._create_weekend_suspicions(weekend_txs, entity_name))

        return results

    def _parse_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """解析交易数据，提取日期时间信息。"""
        parsed = []
        for tx in transactions:
            try:
                dt = self._parse_datetime(tx.get("tx_date"), tx.get("tx_time"))
                if dt:
                    parsed.append(
                        {
                            "date": dt.date(),
                            "datetime": dt,
                            "amount": float(tx.get("amount", 0)),
                            "tx_type": tx.get("tx_type", ""),
                            "counterparty": tx.get("counterparty", ""),
                            "account": tx.get("account", ""),
                            "bank": tx.get("bank", ""),
                            "raw_data": tx,
                        }
                    )
            except (ValueError, TypeError):
                continue
        return parsed

    def _parse_datetime(
        self, date_value: Any, time_value: Any = None
    ) -> Optional[datetime]:
        """解析日期和时间字段为 datetime 对象。"""
        if isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, date):
            if time_value:
                t = self._parse_time(time_value)
                if t:
                    return datetime.combine(date_value, t)
            return datetime.combine(date_value, time.min)
        if isinstance(date_value, str):
            formats = ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"]
            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue
        return None

    def _parse_time(self, time_value: Any) -> Optional[time]:
        """解析时间字段为 time 对象。"""
        if isinstance(time_value, time):
            return time_value
        if isinstance(time_value, str):
            formats = ["%H:%M:%S", "%H:%M", "%H:%M:%S.%f"]
            for fmt in formats:
                try:
                    return datetime.strptime(time_value, fmt).time()
                except ValueError:
                    continue
        return None

    def _is_off_hours(self, dt: datetime, start_hour: int, end_hour: int) -> bool:
        """判断时间是否在非工作时段。"""
        hour = dt.hour
        if start_hour <= end_hour:
            return start_hour <= hour <= end_hour
        else:
            return hour >= start_hour or hour <= end_hour

    def _is_holiday(self, d: date, holidays: List[Tuple[str, str, str]]) -> bool:
        """判断日期是否为节假日。"""
        for start, end, _ in holidays:
            try:
                start_date = datetime.strptime(start, "%Y-%m-%d").date()
                end_date = datetime.strptime(end, "%Y-%m-%d").date()
                if start_date <= d <= end_date:
                    return True
            except ValueError:
                continue
        return False

    def _is_weekend(self, d: date) -> bool:
        """判断日期是否为周末。"""
        return d.weekday() >= 5

    def _get_default_holidays(self) -> List[Tuple[str, str, str]]:
        """获取默认节假日列表。"""
        return [
            ("2024-01-01", "2024-01-01", "元旦"),
            ("2024-02-10", "2024-02-17", "春节"),
            ("2024-04-04", "2024-04-06", "清明节"),
            ("2024-05-01", "2024-05-05", "劳动节"),
            ("2024-06-08", "2024-06-10", "端午节"),
            ("2024-09-15", "2024-09-17", "中秋节"),
            ("2024-10-01", "2024-10-07", "国庆节"),
            ("2025-01-01", "2025-01-01", "元旦"),
            ("2025-01-28", "2025-02-04", "春节"),
            ("2025-04-04", "2025-04-06", "清明节"),
            ("2025-05-01", "2025-05-05", "劳动节"),
            ("2025-05-31", "2025-06-02", "端午节"),
            ("2025-10-01", "2025-10-08", "国庆节"),
        ]

    def _create_off_hours_suspicions(
        self, transactions: List[Dict], entity_name: str
    ) -> List[Dict[str, Any]]:
        """创建非工作时段交易疑点。"""
        if not transactions:
            return []

        results = []
        suspicion_id = f"TA{datetime.now().strftime('%Y%m%d')}001"

        total_amount = sum(abs(tx.get("amount") or 0) for tx in transactions)
        tx_count = len(transactions)

        related_tx_ids = [
            f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
            for tx in transactions[:50]
        ]

        sample_times = [tx["datetime"].strftime("%H:%M") for tx in transactions[:5]]

        description = (
            f"发现非工作时段交易异常：在22:00-06:00时段发生 {tx_count} 笔交易，"
            f"涉及总金额 {total_amount:,.2f} 元。样本交易时间：{', '.join(sample_times)}。"
            f"非工作时段的大额交易可能具有特殊目的或风险。"
        )

        severity = (
            SuspicionSeverity.HIGH.value
            if total_amount >= 500000
            else SuspicionSeverity.MEDIUM.value
        )
        confidence = min(0.5 + tx_count * 0.05, 0.9)

        suspicion = {
            "suspicion_id": suspicion_id,
            "suspicion_type": SuspicionType.UNUSUAL_TIME.value,
            "severity": severity,
            "description": description,
            "related_transactions": related_tx_ids,
            "amount": total_amount,
            "detection_date": date.today(),
            "entity_name": entity_name,
            "confidence": confidence,
            "evidence": f"非工作时段交易: {tx_count}笔, 总金额: {total_amount:,.2f}元, 时段: 22:00-06:00",
            "status": "待核实",
        }

        results.append(suspicion)
        return results

    def _create_holiday_suspicions(
        self, transactions: List[Dict], entity_name: str
    ) -> List[Dict[str, Any]]:
        """创建节假日交易疑点。"""
        if not transactions:
            return []

        results = []
        suspicion_id = f"TA{datetime.now().strftime('%Y%m%d')}002"

        total_amount = sum(abs(tx.get("amount") or 0) for tx in transactions)
        tx_count = len(transactions)

        related_tx_ids = [
            f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
            for tx in transactions[:50]
        ]

        description = (
            f"发现节假日大额交易异常：在法定节假日发生 {tx_count} 笔大额交易，"
            f"涉及总金额 {total_amount:,.2f} 元。节假日期间的大额资金往来需要关注。"
        )

        severity = (
            SuspicionSeverity.HIGH.value
            if total_amount >= 1000000
            else SuspicionSeverity.MEDIUM.value
        )
        confidence = min(0.6 + tx_count * 0.03, 0.85)

        suspicion = {
            "suspicion_id": suspicion_id,
            "suspicion_type": SuspicionType.UNUSUAL_TIME.value,
            "severity": severity,
            "description": description,
            "related_transactions": related_tx_ids,
            "amount": total_amount,
            "detection_date": date.today(),
            "entity_name": entity_name,
            "confidence": confidence,
            "evidence": f"节假日大额交易: {tx_count}笔, 总金额: {total_amount:,.2f}元",
            "status": "待核实",
        }

        results.append(suspicion)
        return results

    def _create_weekend_suspicions(
        self, transactions: List[Dict], entity_name: str
    ) -> List[Dict[str, Any]]:
        """创建周末交易疑点。"""
        if not transactions:
            return []

        results = []
        suspicion_id = f"TA{datetime.now().strftime('%Y%m%d')}003"

        total_amount = sum(abs(tx.get("amount") or 0) for tx in transactions)
        tx_count = len(transactions)

        related_tx_ids = [
            f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
            for tx in transactions[:50]
        ]

        description = (
            f"发现周末大额交易异常：在周末发生 {tx_count} 笔大额交易，"
            f"涉及总金额 {total_amount:,.2f} 元。周末的大额资金往来值得关注。"
        )

        severity = (
            SuspicionSeverity.MEDIUM.value
            if total_amount >= 500000
            else SuspicionSeverity.LOW.value
        )
        confidence = min(0.55 + tx_count * 0.02, 0.8)

        suspicion = {
            "suspicion_id": suspicion_id,
            "suspicion_type": SuspicionType.UNUSUAL_TIME.value,
            "severity": severity,
            "description": description,
            "related_transactions": related_tx_ids,
            "amount": total_amount,
            "detection_date": date.today(),
            "entity_name": entity_name,
            "confidence": confidence,
            "evidence": f"周末大额交易: {tx_count}笔, 总金额: {total_amount:,.2f}元",
            "status": "待核实",
        }

        results.append(suspicion)
        return results
