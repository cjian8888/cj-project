"""
可疑模式检测器 - SuspiciousPatternDetector
检测可疑的交易模式，如分散转入集中转出等。
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple

from detectors.base_detector import BaseDetector
from schemas.suspicion import SuspicionSeverity, SuspicionType


class SuspiciousPatternDetector(BaseDetector):
    """检测可疑的资金流动模式。
    
    该检测器分析资金流向，识别可疑的模式，如：
    - 分散转入、集中转出（资金归集）
    - 集中转入、分散转出（资金拆分）
    - 快进快出（资金过账）
    - 循环转账（资金空转）
    """

    @property
    def name(self) -> str:
        return "suspicious_pattern"

    @property
    def description(self) -> str:
        return "检测可疑模式，如分散转入集中转出等"

    @property
    def risk_level(self) -> str:
        return "高"

    def detect(self, data: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行可疑模式检测。
        
        Args:
            data: 包含交易数据的字典，必须包含 'transactions' 键
            config: 检测配置参数
                - window_days: 时间窗口天数（默认7）
                - min_inflow_sources: 最小转入来源数（默认3）
                - min_outflow_targets: 最小转出目标数（默认3）
                - min_amount: 最低金额阈值（默认50000）
                - fast_in_out_hours: 快进快出时间窗口（小时，默认24）
                - fast_in_out_ratio: 快进快出金额比例（默认0.8）
                
        Returns:
            List[Dict]: 检测到的疑点列表
        """
        transactions = data.get("transactions", [])
        entity_name = data.get("entity_name", "未知实体")
        
        if not transactions or len(transactions) < 2:
            return []
        
        window_days = config.get("window_days", 7)
        min_inflow_sources = config.get("min_inflow_sources", 3)
        min_outflow_targets = config.get("min_outflow_targets", 3)
        min_amount = config.get("min_amount", 50000)
        fast_in_out_hours = config.get("fast_in_out_hours", 24)
        fast_in_out_ratio = config.get("fast_in_out_ratio", 0.8)
        
        parsed_transactions = self._parse_transactions(transactions)
        
        results = []
        
        # 检测分散转入集中转出
        scatter_gather = self._detect_scatter_gather(
            parsed_transactions, window_days, min_inflow_sources, min_amount
        )
        results.extend(self._create_scatter_gather_suspicions(scatter_gather, entity_name))
        
        # 检测集中转入分散转出
        gather_scatter = self._detect_gather_scatter(
            parsed_transactions, window_days, min_outflow_targets, min_amount
        )
        results.extend(self._create_gather_scatter_suspions(gather_scatter, entity_name))
        
        # 检测快进快出
        fast_in_out = self._detect_fast_in_out(
            parsed_transactions, fast_in_out_hours, min_amount, fast_in_out_ratio
        )
        results.extend(self._create_fast_in_out_suspicions(fast_in_out, entity_name))
        
        return results

    def _parse_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """解析交易数据。"""
        parsed = []
        for tx in transactions:
            try:
                dt = self._parse_datetime(tx.get("tx_date"))
                if dt:
                    parsed.append({
                        "datetime": dt,
                        "date": dt.date(),
                        "amount": float(tx.get("amount", 0)),
                        "tx_type": tx.get("tx_type", ""),
                        "counterparty": tx.get("counterparty", ""),
                        "account": tx.get("account", ""),
                        "bank": tx.get("bank", ""),
                        "raw_data": tx
                    })
            except (ValueError, TypeError):
                continue
        return sorted(parsed, key=lambda x: x["datetime"])

    def _parse_datetime(self, date_value: Any) -> Optional[datetime]:
        """解析日期字段为 datetime 对象。"""
        if isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, date):
            return datetime.combine(date_value, datetime.min.time())
        if isinstance(date_value, str):
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%Y-%m-%d",
                "%Y/%m/%d"
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue
        return None

    def _detect_scatter_gather(
        self, 
        transactions: List[Dict], 
        window_days: int,
        min_sources: int,
        min_amount: float
    ) -> List[Dict]:
        """检测分散转入集中转出模式。"""
        anomalies = []
        window_delta = timedelta(days=window_days)
        
        # 按天分组分析
        daily_inflows = defaultdict(lambda: defaultdict(list))
        for tx in transactions:
            if tx["amount"] > 0 and abs(tx["amount"]) >= min_amount:
                daily_inflows[tx["date"]][tx["counterparty"]].append(tx)
        
        # 检查每一天的转入情况
        for tx_date, sources in daily_inflows.items():
            if len(sources) >= min_sources:
                total_inflow = sum(
                    sum(t["amount"] for t in txs) 
                    for txs in sources.values()
                )
                
                # 检查随后窗口期内是否有大额转出
                window_end = tx_date + window_delta
                outflows = [
                    tx for tx in transactions
                    if tx["amount"] < 0 
                    and tx_date < tx["date"] <= window_end
                    and abs(tx["amount"]) >= min_amount
                ]
                
                if outflows:
                    total_outflow = sum(abs(tx["amount"]) for tx in outflows)
                    anomalies.append({
                        "date": tx_date,
                        "pattern_type": "scatter_gather",
                        "source_count": len(sources),
                        "total_inflow": total_inflow,
                        "total_outflow": total_outflow,
                        "sources": list(sources.keys()),
                        "outflow_targets": list(set(tx["counterparty"] for tx in outflows)),
                        "inflow_transactions": [tx for txs in sources.values() for tx in txs],
                        "outflow_transactions": outflows
                    })
        
        return anomalies

    def _detect_gather_scatter(
        self, 
        transactions: List[Dict], 
        window_days: int,
        min_targets: int,
        min_amount: float
    ) -> List[Dict]:
        """检测集中转入分散转出模式。"""
        anomalies = []
        window_delta = timedelta(days=window_days)
        
        # 按天分组分析
        daily_outflows = defaultdict(lambda: defaultdict(list))
        for tx in transactions:
            if tx["amount"] < 0 and abs(tx["amount"]) >= min_amount:
                daily_outflows[tx["date"]][tx["counterparty"]].append(tx)
        
        # 检查每一天的转出情况
        for tx_date, targets in daily_outflows.items():
            if len(targets) >= min_targets:
                total_outflow = sum(
                    sum(abs(t["amount"]) for t in txs)
                    for txs in targets.values()
                )
                
                # 检查此前窗口期内是否有大额转入
                window_start = tx_date - window_delta
                inflows = [
                    tx for tx in transactions
                    if tx["amount"] > 0
                    and window_start <= tx["date"] < tx_date
                    and tx["amount"] >= min_amount
                ]
                
                if inflows:
                    total_inflow = sum(tx["amount"] for tx in inflows)
                    anomalies.append({
                        "date": tx_date,
                        "pattern_type": "gather_scatter",
                        "target_count": len(targets),
                        "total_inflow": total_inflow,
                        "total_outflow": total_outflow,
                        "targets": list(targets.keys()),
                        "inflow_sources": list(set(tx["counterparty"] for tx in inflows)),
                        "inflow_transactions": inflows,
                        "outflow_transactions": [tx for txs in targets.values() for tx in txs]
                    })
        
        return anomalies

    def _detect_fast_in_out(
        self, 
        transactions: List[Dict], 
        window_hours: int,
        min_amount: float,
        ratio: float
    ) -> List[Dict]:
        """检测快进快出模式。"""
        anomalies = []
        window_delta = timedelta(hours=window_hours)
        
        # 按账户分析
        account_transactions = defaultdict(list)
        for tx in transactions:
            account_transactions[tx["account"]].append(tx)
        
        for account, account_txs in account_transactions.items():
            sorted_txs = sorted(account_txs, key=lambda x: x["datetime"])
            
            for i, inflow in enumerate(sorted_txs):
                if inflow["amount"] <= 0 or inflow["amount"] < min_amount:
                    continue
                
                inflow_time = inflow["datetime"]
                inflow_amount = inflow["amount"]
                
                # 查找时间窗口内的转出
                window_end = inflow_time + window_delta
                outflows = []
                for j in range(i + 1, len(sorted_txs)):
                    tx = sorted_txs[j]
                    if tx["datetime"] > window_end:
                        break
                    if tx["amount"] < 0 and abs(tx["amount"]) >= min_amount * ratio:
                        outflows.append(tx)
                
                total_outflow = sum(abs(tx["amount"]) for tx in outflows)
                
                if outflows and total_outflow >= inflow_amount * ratio:
                    anomalies.append({
                        "account": account,
                        "inflow_time": inflow_time,
                        "inflow_amount": inflow_amount,
                        "outflow_amount": total_outflow,
                        "time_diff_hours": (outflows[-1]["datetime"] - inflow_time).total_seconds() / 3600,
                        "outflow_count": len(outflows),
                        "outflow_targets": list(set(tx["counterparty"] for tx in outflows)),
                        "inflow_transaction": inflow,
                        "outflow_transactions": outflows
                    })
        
        # 去重并保留最严重的
        return anomalies[:5]

    def _create_scatter_gather_suspicions(self, anomalies: List[Dict], entity_name: str) -> List[Dict[str, Any]]:
        """创建分散转入集中转出疑点。"""
        if not anomalies:
            return []
        
        results = []
        for i, anomaly in enumerate(anomalies[:3]):
            suspicion_id = f"SP{datetime.now().strftime('%Y%m%d')}{str(i+1).zfill(3)}"
            
            total_inflow = anomaly["total_inflow"]
            total_outflow = anomaly["total_outflow"]
            source_count = anomaly["source_count"]
            sources_str = ", ".join(anomaly["sources"][:5])
            
            all_txs = anomaly["inflow_transactions"] + anomaly["outflow_transactions"]
            related_tx_ids = [
                f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
                for tx in all_txs[:50]
            ]
            
            description = (
                f"发现分散转入集中转出模式：{anomaly['date']} 当天从 {source_count} 个不同来源"
                f"共转入 {total_inflow:,.2f} 元（来源：{sources_str}...），"
                f"随后转出 {total_outflow:,.2f} 元。此模式符合资金归集特征，可能用于规避监管。"
            )
            
            suspicion = {
                "suspicion_id": suspicion_id,
                "suspicion_type": SuspicionType.FREQUENT_TRANSFER.value,
                "severity": SuspicionSeverity.HIGH.value,
                "description": description,
                "related_transactions": related_tx_ids,
                "amount": max(total_inflow, total_outflow),
                "detection_date": date.today(),
                "entity_name": entity_name,
                "confidence": 0.85,
                "evidence": f"分散转入: {source_count}个来源, 总金额: {total_inflow:,.2f}元, 集中转出: {total_outflow:,.2f}元",
                "status": "待核实"
            }
            results.append(suspicion)
        
        return results

    def _create_gather_scatter_suspions(self, anomalies: List[Dict], entity_name: str) -> List[Dict[str, Any]]:
        """创建集中转入分散转出疑点。"""
        if not anomalies:
            return []
        
        results = []
        for i, anomaly in enumerate(anomalies[:3]):
            suspicion_id = f"SP{datetime.now().strftime('%Y%m%d')}{str(i+4).zfill(3)}"
            
            total_inflow = anomaly["total_inflow"]
            total_outflow = anomaly["total_outflow"]
            target_count = anomaly["target_count"]
            targets_str = ", ".join(anomaly["targets"][:5])
            
            all_txs = anomaly["inflow_transactions"] + anomaly["outflow_transactions"]
            related_tx_ids = [
                f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}"
                for tx in all_txs[:50]
            ]
            
            description = (
                f"发现集中转入分散转出模式：在{anomaly['date']}之前有 {total_inflow:,.2f} 元转入，"
                f"随后当天向 {target_count} 个不同目标转出 {total_outflow:,.2f} 元"
                f"（目标：{targets_str}...）。此模式符合资金拆分特征，可能用于规避大额交易监管。"
            )
            
            suspicion = {
                "suspicion_id": suspicion_id,
                "suspicion_type": SuspicionType.FREQUENT_TRANSFER.value,
                "severity": SuspicionSeverity.HIGH.value,
                "description": description,
                "related_transactions": related_tx_ids,
                "amount": max(total_inflow, total_outflow),
                "detection_date": date.today(),
                "entity_name": entity_name,
                "confidence": 0.85,
                "evidence": f"集中转入: {total_inflow:,.2f}元, 分散转出: {target_count}个目标, 总金额: {total_outflow:,.2f}元",
                "status": "待核实"
            }
            results.append(suspicion)
        
        return results

    def _create_fast_in_out_suspicions(self, anomalies: List[Dict], entity_name: str) -> List[Dict[str, Any]]:
        """创建快进快出疑点。"""
        if not anomalies:
            return []
        
        results = []
        for i, anomaly in enumerate(anomalies[:3]):
            suspicion_id = f"SP{datetime.now().strftime('%Y%m%d')}{str(i+7).zfill(3)}"
            
            inflow_amount = anomaly["inflow_amount"]
            outflow_amount = anomaly["outflow_amount"]
            time_diff = anomaly["time_diff_hours"]
            outflow_count = anomaly["outflow_count"]
            
            related_tx_ids = [
                f"TX_{anomaly['inflow_transaction']['raw_data'].get('tx_date', '')}_{anomaly['inflow_transaction']['amount']}"
            ]
            for tx in anomaly["outflow_transactions"][:10]:
                related_tx_ids.append(f"TX_{tx['raw_data'].get('tx_date', '')}_{tx['amount']}")
            
            description = (
                f"发现快进快出模式：账户 {anomaly['account'][-4:]} 在 {anomaly['inflow_time'].strftime('%Y-%m-%d %H:%M')} "
                f"转入 {inflow_amount:,.2f} 元，随后在 {time_diff:.1f} 小时内"
                f"分 {outflow_count} 笔转出共 {outflow_amount:,.2f} 元。"
                f"资金停留时间极短，可能为过账通道或洗钱行为。"
            )
            
            suspicion = {
                "suspicion_id": suspicion_id,
                "suspicion_type": SuspicionType.FREQUENT_TRANSFER.value,
                "severity": SuspicionSeverity.HIGH.value,
                "description": description,
                "related_transactions": related_tx_ids[:50],
                "amount": max(inflow_amount, outflow_amount),
                "detection_date": date.today(),
                "entity_name": entity_name,
                "confidence": 0.9,
                "evidence": f"快进快出: 转入{inflow_amount:,.2f}元, 停留{time_diff:.1f}小时, 转出{outflow_amount:,.2f}元",
                "status": "待核实"
            }
            results.append(suspicion)
        
        return results
