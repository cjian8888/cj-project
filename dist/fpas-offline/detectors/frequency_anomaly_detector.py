"""
频率异常检测器 - FrequencyAnomalyDetector
检测频率异常，如短时间内大量交易。
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional

import utils
from detectors.base_detector import BaseDetector
from schemas.suspicion import SuspicionSeverity, SuspicionType


class FrequencyAnomalyDetector(BaseDetector):
    """检测短时间内的大量交易活动。

    该检测器分析交易的时间分布，识别在短时间内（如一天、一周）
    发生的大量交易，这类模式可能表明异常资金活动或规避监管行为。
    """

    @property
    def name(self) -> str:
        return "frequency_anomaly"

    @property
    def description(self) -> str:
        return "检测频率异常，如短时间内大量交易"

    @property
    def risk_level(self) -> str:
        return "高"

    def detect(
        self, data: Dict[str, Any], config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行频率异常检测。

        Args:
            data: 包含交易数据的字典，必须包含 'transactions' 键
            config: 检测配置参数
                - daily_threshold: 单日交易数量阈值（默认10）
                - hourly_threshold: 单小时交易数量阈值（默认5）
                - window_hours: 滑动窗口小时数（默认24）
                - window_tx_threshold: 窗口内交易数量阈值（默认15）
                - min_amount: 检测的最低单笔金额（默认1000）

        Returns:
            List[Dict]: 检测到的疑点列表
        """
        transactions = data.get("transactions", [])
        entity_name = data.get("entity_name", "未知实体")

        if not transactions or len(transactions) < 2:
            return []

        daily_threshold = config.get("daily_threshold", 10)
        hourly_threshold = config.get("hourly_threshold", 5)
        window_hours = config.get("window_hours", 24)
        window_tx_threshold = config.get("window_tx_threshold", 15)
        min_amount = config.get("min_amount", 1000)

        parsed_transactions = self._parse_transactions(transactions)

        # 过滤小额交易
        filtered_txs = [
            tx for tx in parsed_transactions if abs(tx["amount"]) >= min_amount
        ]

        if len(filtered_txs) < 2:
            return []

        results = []

        # 检测单日高频
        daily_anomalies = self._detect_daily_frequency(filtered_txs, daily_threshold)
        results.extend(self._create_daily_suspicions(daily_anomalies, entity_name))

        # 检测单小时高频
        hourly_anomalies = self._detect_hourly_frequency(filtered_txs, hourly_threshold)
        results.extend(self._create_hourly_suspicions(hourly_anomalies, entity_name))

        # 检测滑动窗口高频
        window_anomalies = self._detect_sliding_window(
            filtered_txs, window_hours, window_tx_threshold
        )
        results.extend(self._create_window_suspicions(window_anomalies, entity_name))

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
                            "datetime": dt,
                            "date": dt.date(),
                            "hour": dt.hour,
                            "amount": utils.format_amount(tx.get("amount", 0)),
                            "tx_type": tx.get("tx_type", ""),
                            "counterparty": tx.get("counterparty", ""),
                            "account": tx.get("account", ""),
                            "bank": tx.get("bank", ""),
                            "raw_data": tx,
                        }
                    )
            except (ValueError, TypeError):
                continue
        return sorted(parsed, key=lambda x: x["datetime"])

    def _parse_datetime(
        self, date_value: Any, time_value: Any = None
    ) -> Optional[datetime]:
        """解析日期和时间字段为 datetime 对象。"""
        parsed_date = utils.parse_date(date_value)
        if parsed_date is None:
            return None
        if time_value:
            t = self._parse_time(time_value)
            if t:
                return datetime.combine(parsed_date.date(), t)
        if isinstance(parsed_date, datetime):
            return parsed_date
        from datetime import time as dt_time

        return datetime.combine(parsed_date, dt_time.min)

    def _parse_time(self, time_value: Any):
        """解析时间字段为 time 对象。"""
        from datetime import time as dt_time

        if hasattr(time_value, "hour"):
            return time_value
        if isinstance(time_value, str):
            formats = ["%H:%M:%S", "%H:%M"]
            for fmt in formats:
                try:
                    return datetime.strptime(time_value, fmt).time()
                except ValueError:
                    continue
        return None

    def _detect_daily_frequency(
        self, transactions: List[Dict], threshold: int
    ) -> List[Dict]:
        """检测单日高频交易。"""
        daily_groups = defaultdict(list)
        for tx in transactions:
            daily_groups[tx["date"]].append(tx)

        anomalies = []
        for d, txs in daily_groups.items():
            if len(txs) >= threshold:
                total_amount = sum(abs(tx.get("amount") or 0) for tx in txs)
                anomalies.append(
                    {
                        "date": d,
                        "count": len(txs),
                        "total_amount": total_amount,
                        "transactions": txs,
                    }
                )

        return sorted(anomalies, key=lambda x: x["count"], reverse=True)

    def _detect_hourly_frequency(
        self, transactions: List[Dict], threshold: int
    ) -> List[Dict]:
        """检测单小时高频交易。"""
        hourly_groups = defaultdict(list)
        for tx in transactions:
            hour_key = (tx["date"], tx["hour"])
            hourly_groups[hour_key].append(tx)

        anomalies = []
        for (d, h), txs in hourly_groups.items():
            if len(txs) >= threshold:
                total_amount = sum(abs(tx.get("amount") or 0) for tx in txs)
                anomalies.append(
                    {
                        "date": d,
                        "hour": h,
                        "count": len(txs),
                        "total_amount": total_amount,
                        "transactions": txs,
                    }
                )

        return sorted(anomalies, key=lambda x: x["count"], reverse=True)[:5]

    def _detect_sliding_window(
        self, transactions: List[Dict], window_hours: int, threshold: int
    ) -> List[Dict]:
        """使用滑动窗口检测高频交易。"""
        if len(transactions) < threshold:
            return []

        anomalies = []
        window_delta = timedelta(hours=window_hours)

        for i, tx in enumerate(transactions):
            window_start = tx["datetime"]
            window_end = window_start + window_delta

            window_txs = [tx]
            for j in range(i + 1, len(transactions)):
                if transactions[j]["datetime"] <= window_end:
                    window_txs.append(transactions[j])
                else:
                    break

            if len(window_txs) >= threshold:
                total_amount = sum(abs(t.get("amount") or 0) for t in window_txs)
                anomalies.append(
                    {
                        "window_start": window_start,
                        "window_end": window_end,
                        "count": len(window_txs),
                        "total_amount": total_amount,
                        "transactions": window_txs,
                    }
                )

        # 去重：保留交易量最大的窗口
        unique_anomalies = []
        for anomaly in anomalies:
            is_subset = False
            for existing in unique_anomalies:
                if set(id(t) for t in anomaly["transactions"]) <= set(
                    id(t) for t in existing["transactions"]
                ):
                    is_subset = True
                    break
            if not is_subset:
                unique_anomalies.append(anomaly)

        return sorted(unique_anomalies, key=lambda x: x["count"], reverse=True)[:3]

    def _create_daily_suspicions(
        self, anomalies: List[Dict], entity_name: str
    ) -> List[Dict[str, Any]]:
        """创建单日高频交易疑点。"""
        if not anomalies:
            return []

        results = []
        for i, anomaly in enumerate(anomalies[:3]):
            suspicion_id = f"FR{datetime.now().strftime('%Y%m%d')}{str(i + 1).zfill(3)}"

            tx_count = anomaly["count"]
            total_amount = anomaly["total_amount"]
            tx_date = anomaly["date"]
            transactions = anomaly["transactions"]

            related_tx_ids = [
                f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
                for tx in transactions[:50]
            ]

            description = (
                f"发现单日高频交易异常：{tx_date} 当日发生 {tx_count} 笔交易，"
                f"涉及总金额 {total_amount:,.2f} 元。单日大量交易可能表明异常资金活动。"
            )

            severity = (
                SuspicionSeverity.HIGH.value
                if tx_count >= 20
                else SuspicionSeverity.MEDIUM.value
            )
            confidence = min(0.6 + tx_count * 0.02, 0.95)

            suspicion = {
                "suspicion_id": suspicion_id,
                "suspicion_type": SuspicionType.FREQUENT_TRANSFER.value,
                "severity": severity,
                "description": description,
                "related_transactions": related_tx_ids,
                "amount": total_amount,
                "detection_date": date.today(),
                "entity_name": entity_name,
                "confidence": confidence,
                "evidence": f"单日交易: {tx_count}笔, 日期: {tx_date}, 总金额: {total_amount:,.2f}元",
                "status": "待核实",
            }
            results.append(suspicion)

        return results

    def _create_hourly_suspicions(
        self, anomalies: List[Dict], entity_name: str
    ) -> List[Dict[str, Any]]:
        """创建单小时高频交易疑点。"""
        if not anomalies:
            return []

        results = []
        for i, anomaly in enumerate(anomalies[:3]):
            suspicion_id = f"FR{datetime.now().strftime('%Y%m%d')}{str(i + 4).zfill(3)}"

            tx_count = anomaly["count"]
            total_amount = anomaly["total_amount"]
            tx_date = anomaly["date"]
            hour = anomaly["hour"]
            transactions = anomaly["transactions"]

            related_tx_ids = [
                f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
                for tx in transactions[:50]
            ]

            description = (
                f"发现单小时高频交易异常：{tx_date} {hour}:00-{hour + 1}:00 时段内发生 {tx_count} 笔交易，"
                f"涉及总金额 {total_amount:,.2f} 元。短时间内大量交易需要重点关注。"
            )

            severity = (
                SuspicionSeverity.HIGH.value
                if tx_count >= 10
                else SuspicionSeverity.MEDIUM.value
            )
            confidence = min(0.65 + tx_count * 0.03, 0.95)

            suspicion = {
                "suspicion_id": suspicion_id,
                "suspicion_type": SuspicionType.FREQUENT_TRANSFER.value,
                "severity": severity,
                "description": description,
                "related_transactions": related_tx_ids,
                "amount": total_amount,
                "detection_date": date.today(),
                "entity_name": entity_name,
                "confidence": confidence,
                "evidence": f"单小时交易: {tx_count}笔, 时段: {tx_date} {hour}:00, 总金额: {total_amount:,.2f}元",
                "status": "待核实",
            }
            results.append(suspicion)

        return results

    def _create_window_suspicions(
        self, anomalies: List[Dict], entity_name: str
    ) -> List[Dict[str, Any]]:
        """创建滑动窗口高频交易疑点。"""
        if not anomalies:
            return []

        results = []
        for i, anomaly in enumerate(anomalies):
            suspicion_id = f"FR{datetime.now().strftime('%Y%m%d')}{str(i + 7).zfill(3)}"

            tx_count = anomaly["count"]
            total_amount = anomaly["total_amount"]
            window_start = anomaly["window_start"]
            window_end = anomaly["window_end"]
            transactions = anomaly["transactions"]

            related_tx_ids = [
                f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
                for tx in transactions[:50]
            ]

            description = (
                f"发现连续时段高频交易异常：在 {window_start.strftime('%Y-%m-%d %H:%M')} 至 "
                f"{window_end.strftime('%Y-%m-%d %H:%M')} 的24小时内发生 {tx_count} 笔交易，"
                f"涉及总金额 {total_amount:,.2f} 元。连续时段内的大量交易可能表明资金快进快出。"
            )

            severity = SuspicionSeverity.HIGH.value
            confidence = min(0.7 + tx_count * 0.02, 0.95)

            suspicion = {
                "suspicion_id": suspicion_id,
                "suspicion_type": SuspicionType.FREQUENT_TRANSFER.value,
                "severity": severity,
                "description": description,
                "related_transactions": related_tx_ids,
                "amount": total_amount,
                "detection_date": date.today(),
                "entity_name": entity_name,
                "confidence": confidence,
                "evidence": f"24小时窗口交易: {tx_count}笔, 总金额: {total_amount:,.2f}元",
                "status": "待核实",
            }
            results.append(suspicion)

        return results
