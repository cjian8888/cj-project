"""
时间异常检测器 - TimeAnomalyDetector
检测异常时间的交易，如凌晨、节假日等的交易。
"""

from datetime import date, datetime, time, timedelta
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd

import config as global_config
import utils
from detectors.base_detector import BaseDetector
from holiday_service import build_holiday_window
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
            data: 包含交易数据的字典，支持两种结构：
                - {'transactions': [...], 'entity_name': '...'}
                - {'cleaned_data': {entity_name: DataFrame, ...}}
            config: 检测配置参数
                - off_hours_start: 非工作时段开始时间（小时，默认取 config.NON_WORKING_HOURS_START）
                - off_hours_end: 非工作时段结束时间（小时，默认取 config.NON_WORKING_HOURS_END）
                - holiday_threshold: 节假日大额交易阈值（默认50000）
                - weekend_threshold: 周末大额交易阈值（默认50000）
                - min_amount: 检测的最低金额（默认10000）
                - holiday_days_before: 节前纳入窗口的天数
                - holiday_days_after: 节后纳入窗口的天数

        Returns:
            List[Dict]: 检测到的疑点列表
        """
        if "transactions" in data:
            return self._detect_for_entity(
                transactions=data.get("transactions", []),
                entity_name=data.get("entity_name", "未知实体"),
                config=config,
            )

        cleaned_data = data.get("cleaned_data", {})
        if not isinstance(cleaned_data, dict) or not cleaned_data:
            return []

        results: List[Dict[str, Any]] = []
        for entity_name, df in cleaned_data.items():
            transactions = self._extract_transactions_from_dataframe(df)
            results.extend(
                self._detect_for_entity(
                    transactions=transactions,
                    entity_name=entity_name,
                    config=config,
                )
            )
        return results

    def _detect_for_entity(
        self,
        transactions: List[Dict[str, Any]],
        entity_name: str,
        config: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """对单个实体的交易执行时间异常检测。"""
        if not transactions:
            return []

        off_hours_start = int(
            config.get(
                "off_hours_start",
                getattr(global_config, "NON_WORKING_HOURS_START", 20),
            )
        )
        off_hours_end = int(
            config.get(
                "off_hours_end",
                getattr(global_config, "NON_WORKING_HOURS_END", 8),
            )
        )
        holiday_threshold = float(
            config.get(
                "holiday_threshold",
                getattr(global_config, "HOLIDAY_LARGE_AMOUNT_THRESHOLD", 50000),
            )
        )
        weekend_threshold = float(config.get("weekend_threshold", holiday_threshold))
        min_amount = float(config.get("min_amount", 10000))
        weekend_detection_enabled = bool(
            config.get(
                "weekend_detection_enabled",
                getattr(global_config, "WEEKEND_DETECTION_ENABLED", True),
            )
        )

        parsed_transactions = self._parse_transactions(transactions)
        holiday_lookup = self._build_holiday_lookup(parsed_transactions, config)

        off_hours_txs = []
        holiday_txs = []
        weekend_txs = []

        for tx in parsed_transactions:
            abs_amount = abs(tx["amount"])
            if abs_amount < min_amount:
                continue

            if self._is_off_hours(tx["datetime"], off_hours_start, off_hours_end):
                off_hours_txs.append(tx)

            holiday_info = holiday_lookup.get(tx["date"])
            if holiday_info and abs_amount >= holiday_threshold:
                holiday_name, holiday_period = holiday_info
                holiday_txs.append(
                    {
                        **tx,
                        "holiday_name": holiday_name,
                        "holiday_period": holiday_period,
                    }
                )

            if (
                weekend_detection_enabled
                and self._is_weekend(tx["date"])
                and abs_amount >= weekend_threshold
            ):
                weekend_txs.append(tx)

        results = []
        results.extend(
            self._create_off_hours_suspicions(
                off_hours_txs,
                entity_name,
                off_hours_start,
                off_hours_end,
            )
        )
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
                            "amount": self._safe_float(tx.get("amount", 0)),
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

    def _extract_transactions_from_dataframe(self, df: Any) -> List[Dict[str, Any]]:
        """将 cleaned_data 中的 DataFrame 行转换为检测器标准交易结构。"""
        if df is None or not hasattr(df, "iterrows"):
            return []

        date_col = self._pick_column(df, "date", "交易时间", "交易日期", "日期")
        if not date_col:
            return []

        counterparty_col = self._pick_column(df, "counterparty", "交易对手", "对手方")
        description_col = self._pick_column(df, "description", "交易摘要", "摘要")
        account_col = self._pick_column(df, "account", "本方账号", "账号")
        bank_col = self._pick_column(df, "银行来源", "所属银行", "bank")

        transactions: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            amount = self._extract_amount_from_row(row)
            if amount <= 0:
                continue

            transactions.append(
                {
                    "tx_date": row.get(date_col),
                    "amount": amount,
                    "tx_type": self._extract_tx_type(row),
                    "counterparty": self._clean_text(row.get(counterparty_col, "")),
                    "description": self._clean_text(row.get(description_col, "")),
                    "account": self._clean_text(row.get(account_col, "")),
                    "bank": self._clean_text(row.get(bank_col, "")),
                }
            )

        return transactions

    @staticmethod
    def _pick_column(container: Any, *candidates: str) -> str:
        """从 DataFrame/Series 中挑选第一个存在的列名。"""
        columns = getattr(container, "columns", None)
        if columns is None:
            columns = getattr(container, "index", [])
        for column in candidates:
            if column in columns:
                return column
        return ""

    def _extract_amount_from_row(self, row: Any) -> float:
        """从 DataFrame 行中提取绝对金额。"""
        income = self._safe_float(row.get("income", row.get("收入(元)", 0)))
        expense = self._safe_float(row.get("expense", row.get("支出(元)", 0)))
        if income or expense:
            return max(abs(income), abs(expense))

        return abs(self._safe_float(row.get("amount", 0)))

    def _extract_tx_type(self, row: Any) -> str:
        """从 DataFrame 行中提取交易方向。"""
        income = self._safe_float(row.get("income", row.get("收入(元)", 0)))
        expense = self._safe_float(row.get("expense", row.get("支出(元)", 0)))
        if income > 0 and income >= expense:
            return "收入"
        if expense > 0:
            return "支出"

        amount = self._safe_float(row.get("amount", 0))
        if amount > 0:
            return "收入"
        if amount < 0:
            return "支出"
        return ""

    def _safe_float(self, value: Any) -> float:
        """安全转换为浮点数。"""
        return utils.format_amount(value)

    def _clean_text(self, value: Any) -> str:
        """安全转换为字符串。"""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass

        text = str(value)
        return "" if text == "nan" else text

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
        parsed = utils.parse_date(date_value)
        if parsed is None:
            return None
        if time_value:
            t = self._parse_time(time_value)
            if t:
                return datetime.combine(parsed.date(), t)
        return parsed

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

    def _build_holiday_lookup(
        self, transactions: List[Dict[str, Any]], config: Dict[str, Any]
    ) -> Dict[date, Tuple[str, str]]:
        """基于交易时间范围构建节前/节中/节后检测窗口。"""
        if not transactions:
            return {}

        detection_config = config.get(
            "holiday_detection_config",
            getattr(global_config, "HOLIDAY_DETECTION_CONFIG", {}),
        ) or {}
        days_before = int(
            config.get(
                "holiday_days_before",
                detection_config.get("days_before", 3),
            )
        )
        days_after = int(
            config.get(
                "holiday_days_after",
                detection_config.get("days_after", 2),
            )
        )

        tx_dates = [tx["date"] for tx in transactions]
        start_date = min(tx_dates)
        end_date = max(tx_dates)

        custom_holidays = config.get("holidays")
        if custom_holidays:
            return self._build_window_from_ranges(
                custom_holidays,
                start_date,
                end_date,
                days_before,
                days_after,
            )

        return build_holiday_window(
            start_date,
            end_date,
            days_before=days_before,
            days_after=days_after,
        )

    def _is_weekend(self, d: date) -> bool:
        """判断日期是否为周末。"""
        return d.weekday() >= 5

    def _build_window_from_ranges(
        self,
        holidays: List[Tuple[str, str, str]],
        start_date: date,
        end_date: date,
        days_before: int,
        days_after: int,
    ) -> Dict[date, Tuple[str, str]]:
        """将显式传入的节假日区间构建为节前/节中/节后窗口。"""
        lookup: Dict[date, Tuple[str, str]] = {}
        priority = {"during": 3, "before": 2, "after": 2}

        def assign(target_date: date, name: str, period: str) -> None:
            if target_date < start_date or target_date > end_date:
                return
            existing = lookup.get(target_date)
            if existing and priority.get(existing[1], 0) >= priority.get(period, 0):
                return
            lookup[target_date] = (name, period)

        for start, end, name in holidays:
            try:
                holiday_start = datetime.strptime(start, "%Y-%m-%d").date()
                holiday_end = datetime.strptime(end, "%Y-%m-%d").date()
            except ValueError:
                continue

            for offset in range(days_before, 0, -1):
                assign(holiday_start - timedelta(days=offset), name, "before")

            current = holiday_start
            while current <= holiday_end:
                assign(current, name, "during")
                current += timedelta(days=1)

            for offset in range(1, days_after + 1):
                assign(holiday_end + timedelta(days=offset), name, "after")

        return lookup

    def _create_off_hours_suspicions(
        self,
        transactions: List[Dict],
        entity_name: str,
        start_hour: int,
        end_hour: int,
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
            f"发现非工作时段交易异常：在{start_hour:02d}:00-{end_hour:02d}:00时段发生 {tx_count} 笔交易，"
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
            "evidence": (
                f"非工作时段交易: {tx_count}笔, 总金额: {total_amount:,.2f}元, "
                f"时段: {start_hour:02d}:00-{end_hour:02d}:00"
            ),
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
        holiday_names = sorted(
            {tx.get("holiday_name", "节假日") for tx in transactions if tx.get("holiday_name")}
        )
        period_order = {"before": 0, "during": 1, "after": 2}
        holiday_periods = sorted(
            {tx.get("holiday_period", "during") for tx in transactions if tx.get("holiday_period")},
            key=lambda item: period_order.get(item, 99),
        )
        period_labels = {
            "before": "节前",
            "during": "节中",
            "after": "节后",
        }
        period_text = "、".join(period_labels.get(item, item) for item in holiday_periods)
        holiday_text = "、".join(holiday_names[:3]) if holiday_names else "节假日"

        description = (
            f"发现节假日敏感窗口大额交易异常：在{holiday_text}{period_text or '相关时段'}"
            f"发生 {tx_count} 笔大额交易，涉及总金额 {total_amount:,.2f} 元。"
            f"节假日及临近窗口的大额资金往来需要重点关注。"
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
            "evidence": (
                f"节假日敏感窗口交易: {tx_count}笔, 总金额: {total_amount:,.2f}元, "
                f"节日: {holiday_text}, 时段: {period_text or '节中'}"
            ),
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
