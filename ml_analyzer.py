#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机器学习风险预测模块 (ML Analyzer) - 优化版
不依赖 scikit-learn，使用原生 Python/NumPy/Pandas 实现统计学习算法
用于发现规则引擎难以覆盖的深层异常模式

优化内容 (2026-01-08):
1. 修复团伙识别"超级巨团"问题：只在核心人员+涉案公司之间构建图
2. 扩展公共服务商户排除名单
3. 改进异常交易评分：降低正常生活消费的误报率
4. 增加交易金额门槛，减少小额交易干扰
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Set, Any, Optional
from datetime import datetime
import config
import utils

logger = utils.setup_logger(__name__)

# ===== 公共服务商户排除名单（扩展版）=====
# 这些商户会连接所有人，形成虚假的大团伙，必须排除
EXCLUDE_NODES_EXTENDED = {
    # 支付平台
    "支付宝",
    "微信",
    "财付通",
    "网银在线",
    "京东支付",
    "银联",
    "翼支付",
    "云闪付",
    "抖音支付",
    "快捷支付",
    "非银行支付机构",
    "数字货币",
    "网联",
    # 电商/外卖/出行
    "美团",
    "饿了么",
    "滴滴出行",
    "携程",
    "去哪儿",
    "飞猪",
    "高德",
    "百度地图",
    "京东",
    "淘宝",
    "天猫",
    "拼多多",
    "唯品会",
    "苏宁",
    "国美",
    # 餐饮连锁
    "金拱门",
    "麦当劳",
    "肯德基",
    "必胜客",
    "星巴克",
    "瑞幸",
    "奶茶",
    "咖啡",
    # 交通运输
    "铁路",
    "航空",
    "航旅",
    "12306",
    "地铁",
    "公交",
    "出租",
    "加油站",
    "中国石油",
    "中国石化",
    "壳牌",
    "充电",
    "停车",
    # 医疗
    "医院",
    "诊所",
    "药房",
    "药店",
    "卫生",
    "妇幼",
    "保健",
    # 政府/公共服务
    "税务",
    "社保",
    "公积金",
    "水电",
    "燃气",
    "物业",
    "电信",
    "移动",
    "联通",
    # 金融机构（非涉案）
    "银行",
    "信托",
    "基金",
    "保险",
    "证券",
    "理财",
    "贷款",
    # 通用排除词
    "手续费",
    "利息",
    "工资",
    "社保",
    "公积金",
    "消费",
    "提现",
    "充值",
    "退款",
    "红包",
    "转账",
    "零钱",
    "余额宝",
    "零钱通",
    # 物流快递
    "顺丰",
    "圆通",
    "中通",
    "韵达",
    "申通",
    "邮政",
    "快递",
    "丰巢",
    # 娱乐/订阅服务
    "视频",
    "音乐",
    "游戏",
    "直播",
}

# 低风险交易类型（评分时自动降权）
LOW_RISK_TRANSACTION_TYPES = {
    "交通": ["公交", "地铁", "出租", "加油", "充电", "停车", "航空", "铁路", "高铁"],
    "医疗": ["医院", "诊所", "药房", "药店", "卫生"],
    "政府": ["税务", "社保", "公积金", "行政", "法院"],
    "公共": ["水电", "燃气", "物业", "电信", "移动", "联通"],
    "小额消费": [],  # 金额<100的默认归入此类
}


class GraphCommunityDetector:
    """
    轻量级图社区发现算法 (Graph Community Detection) - 优化版
    纯 Python 实现，不依赖 NetworkX 或 Scikit-learn

    优化点：
    1. 只在核心人员+涉案公司之间构建图（过滤公共商户）
    2. 设置最低交易金额门槛（默认1000元）
    3. 使用更严格的团伙判定条件
    """

    def __init__(
        self,
        core_entities: Set[str] = None,
        min_amount: float = config.INCOME_MIN_AMOUNT,
    ):
        """
        Args:
            core_entities: 核心实体集合（核心人员+涉案公司），只在这些实体之间构建图
            min_amount: 最低交易金额门槛，低于此金额的交易不纳入图
        """
        self.adj = {}  # 邻接表: {u: {v: amount}}
        self.nodes = set()
        self.core_entities = core_entities or set()
        self.min_amount = min_amount
        self.edge_count = 0

    def _should_exclude(self, name: str) -> bool:
        """判断是否应该排除该节点"""
        if not name or str(name) == "nan":
            return True
        name_str = str(name)
        return any(keyword in name_str for keyword in EXCLUDE_NODES_EXTENDED)

    def _is_core_entity(self, name: str) -> bool:
        """判断是否为核心实体"""
        if not self.core_entities:
            return True  # 如果未指定核心实体，则不过滤
        name_str = str(name)
        # 精确匹配或包含匹配
        for entity in self.core_entities:
            if entity in name_str or name_str in entity:
                return True
        return False

    def build_graph(self, transactions: List[Dict], strict_mode: bool = True):
        """
        从交易列表构建有向加权图

        Args:
            transactions: 交易列表，每个交易包含 source, target, amount
            strict_mode: 严格模式，只在核心实体之间构建边
        """
        for tx in transactions:
            u, v = str(tx["source"]), str(tx["target"])
            amt = tx["amount"]

            # 金额门槛过滤
            if amt < self.min_amount:
                continue

            # 排除公共服务商户
            if self._should_exclude(u) or self._should_exclude(v):
                continue

            # 严格模式：只在核心实体之间构建边
            if strict_mode and self.core_entities:
                u_is_core = self._is_core_entity(u)
                v_is_core = self._is_core_entity(v)

                # 至少一端是核心实体才纳入
                if not u_is_core and not v_is_core:
                    continue

            self.nodes.add(u)
            self.nodes.add(v)

            if u not in self.adj:
                self.adj[u] = {}
            if v not in self.adj[u]:
                self.adj[u][v] = 0
            self.adj[u][v] += amt
            self.edge_count += 1

        logger.info(f"图构建完成: {len(self.nodes)} 个节点, {self.edge_count} 条边")

    def _tarjan_scc(self):
        """
        使用 Tarjan 算法寻找强连通分量 (SCC)
        SCC 中的任意两个节点都互相可达，这在资金网络中意味着"资金闭环"
        """
        visited = {}  # 访问顺序
        low = {}  # 能追溯到的最早还在栈中的节点
        stack = []
        on_stack = set()
        self.timer = 0
        self.sccs = []

        def dfs(u):
            visited[u] = low[u] = self.timer
            self.timer += 1
            stack.append(u)
            on_stack.add(u)

            if u in self.adj:
                for v in self.adj[u]:
                    if v not in visited:
                        dfs(v)
                        low[u] = min(low[u], low[v])
                    elif v in on_stack:
                        low[u] = min(low[u], visited[v])

            # 发现一个SCC
            if low[u] == visited[u]:
                component = []
                while True:
                    node = stack.pop()
                    on_stack.remove(node)
                    component.append(node)
                    if node == u:
                        break
                self.sccs.append(component)

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        return self.sccs

    def detect_communities(
        self, min_size: int = 2, min_amount: float = config.ASSET_LARGE_AMOUNT_THRESHOLD
    ) -> List[Dict]:
        """
        检测资金团伙

        Args:
            min_size: 最小团伙成员数（默认2人）
            min_amount: 最小内部交易总额（默认5万）

        Returns:
            List of {members, total_amount, type, core_members}
        """
        sccs = self._tarjan_scc()
        communities = []

        for group in sccs:
            if len(group) < min_size:
                continue

            # 计算团伙内部交易
            internal_amt = 0
            edge_count = 0
            edge_details = []

            for u in group:
                if u in self.adj:
                    for v in self.adj[u]:
                        if v in group:
                            internal_amt += self.adj[u][v]
                            edge_count += 1
                            edge_details.append(
                                {"from": u, "to": v, "amount": self.adj[u][v]}
                            )

            # 过滤条件：金额和成员数
            if internal_amt < min_amount:
                continue

            # 识别核心成员（涉案人员/公司）
            core_in_group = [m for m in group if self._is_core_entity(m)]

            # 至少有2个核心成员才算有效团伙
            if len(core_in_group) < 2:
                continue

            # 确定团伙类型
            if len(group) >= 3:
                gang_type = "资金闭环团伙"
            else:
                gang_type = "高频双向交易"

            communities.append(
                {
                    "members": group,
                    "core_members": core_in_group,
                    "count": len(group),
                    "core_count": len(core_in_group),
                    "total_amount": internal_amt,
                    "edge_count": edge_count,
                    "edge_details": edge_details[:10],  # 只保留前10条边的详情
                    "type": gang_type,
                }
            )

        # 按内部交易金额排序
        return sorted(communities, key=lambda x: x["total_amount"], reverse=True)


class LightweightAnomalyDetector:
    """
    轻量级异常检测器 (Z-Score & IQR Ensemble) - 优化版

    优化点：
    1. 对低风险交易类型自动降权
    2. 提高小额交易的评分阈值
    3. 增加时间段的合理性判断
    """

    def __init__(self):
        self.stats = {}

    def fit_predict(
        self, df: pd.DataFrame, features: List[str], raw_mapping: Dict = None
    ) -> pd.Series:
        """
        训练并预测异常分数

        Args:
            df: 特征DataFrame
            features: 特征列名列表
            raw_mapping: 原始交易映射（用于降权处理）

        Returns:
            0~100 的异常分数 (越高越异常)
        """
        if df.empty:
            return pd.Series(dtype=float)

        scores = pd.Series(0.0, index=df.index)

        for feature in features:
            data = df[feature].fillna(0)

            # 1. Z-Score (标准差偏离度)
            mean = data.mean()
            std = data.std()
            if std == 0:
                continue
            z_scores = np.abs((data - mean) / std)

            # 2. IQR (四分位距) - 对长尾分布更鲁棒
            q1 = data.quantile(0.25)
            q3 = data.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                iqr_scores = z_scores  # 回退到 Z-Score
            else:
                # 0.7413 是正态分布下 IQR 到 Sigma 的转换系数
                iqr_scores = np.abs((data - data.median()) / (iqr * 0.7413))

            # 融合分数：取两者较大值
            feature_scores = np.maximum(z_scores, iqr_scores)

            # 累加到总分 (加权)
            # 金额类特征权重更高
            weight = 1.5 if "amount" in feature else 1.0
            scores += feature_scores * weight

            # 记录统计量用于后续解释
            self.stats[feature] = {
                "mean": mean,
                "std": std,
                "median": data.median(),
                "q3": q3,
            }

        # 降权处理：对低风险交易类型降低分数
        if raw_mapping:
            for idx in scores.index:
                if idx in raw_mapping:
                    info = raw_mapping[idx]
                    counterparty = str(info.get("counterparty", ""))
                    description = str(info.get("description", ""))
                    amount = info.get("amount", 0)
                    hour = info.get("hour", 12)

                    # 小额交易降权 (低于100元大幅降权)
                    if amount < 100:
                        scores[idx] *= 0.3
                    elif amount < 500:
                        scores[idx] *= 0.6

                    # 低风险类别降权
                    is_low_risk = False
                    for category, keywords in LOW_RISK_TRANSACTION_TYPES.items():
                        if any(
                            kw in counterparty or kw in description for kw in keywords
                        ):
                            is_low_risk = True
                            break
                    if is_low_risk:
                        scores[idx] *= 0.5

                    # 正常工作时间交易降权 (8:00-20:00)
                    if 8 <= hour <= 20:
                        scores[idx] *= 0.8

        return scores


# 列名映射 (兼容中文和英文)
COLUMN_MAPPING = {
    "counterparty": ["counterparty", "交易对手", "对方户名", "交易对方名称"],
    "description": ["description", "交易摘要", "摘要"],
    "date": ["date", "交易时间", "交易日期"],
    "income": ["income", "收入", "收入(元)", "收入(万元)", "贷方发生额"],
    "expense": ["expense", "支出", "支出(元)", "支出(万元)", "借方发生额"],
    "amount": ["amount", "交易金额", "交易金额(万元)", "金额", "金额(万元)"],
}


def _get_column_value(
    row: pd.Series, col_type: str, col_map: Dict[str, List[str]]
) -> Any:
    """
    从行数据中获取指定类型的列值。

    Args:
        row: 行数据
        col_type: 列类型（如'counterparty', 'amount'等）
        col_map: 列名映射字典

    Returns:
        列值，未找到返回None
    """
    for c in col_map[col_type]:
        if c in row.index:
            return row[c]
    return None


def _count_counterparties_globally(
    all_transactions: Dict[str, pd.DataFrame], col_map: Dict[str, List[str]]
) -> Dict[str, int]:
    """
    全局统计所有对手方的出现次数。

    第一遍遍历：统计每个对手方在全部交易中出现的总次数，
    用于后续特征工程中的对手方频率编码。

    Args:
        all_transactions: 所有交易数据
        col_map: 列名映射字典

    Returns:
        对手方计数字典 {counterparty: count}
    """
    cp_counts = {}

    for key, df in all_transactions.items():
        if df.empty:
            continue

        # 确定对手方列名
        cp_col = None
        for c in col_map["counterparty"]:
            if c in df.columns:
                cp_col = c
                break

        if not cp_col:
            continue

        for cp in df[cp_col]:
            cp = str(cp)
            cp_counts[cp] = cp_counts.get(cp, 0) + 1

    return cp_counts


def _get_person_transactions(
    all_transactions: Dict[str, pd.DataFrame], person: str
) -> Optional[pd.DataFrame]:
    """
    获取指定人员的交易数据。

    优先通过精确匹配获取，如果失败则尝试模糊匹配
    （用于从文件名加载的情况）。

    Args:
        all_transactions: 所有交易数据
        person: 人员名称

    Returns:
        该人员的交易DataFrame，未找到返回None
    """
    # 直接通过key获取数据
    if person in all_transactions:
        return all_transactions[person]

    # 尝试模糊匹配（从文件名加载的情况）
    for k, v in all_transactions.items():
        if person in k and "公司" not in k:
            return v

    return None


def _parse_transaction_date(date_val: Any) -> Optional[datetime]:
    """
    解析交易日期。

    支持datetime对象和字符串格式的日期。

    Args:
        date_val: 日期值

    Returns:
        解析后的datetime对象，解析失败返回None
    """
    if isinstance(date_val, datetime):
        return date_val
    return utils.parse_date(date_val)


def _extract_transaction_amount(row: pd.Series, col_map: Dict[str, List[str]]) -> float:
    """
    从交易行中提取金额。

    优先使用amount列，如果不存在则使用income+expense。

    Args:
        row: 交易行数据
        col_map: 列名映射字典

    Returns:
        交易金额（绝对值）
    """
    val_amt = _get_column_value(row, "amount", col_map)
    if val_amt is not None:
        amount_col_name = next((c for c in col_map["amount"] if c in row.index), "amount")
        return abs(utils.format_amount(val_amt, utils.get_amount_unit_hint_multiplier(amount_col_name)))

    income_col_name = next((c for c in col_map["income"] if c in row.index), "income")
    expense_col_name = next((c for c in col_map["expense"] if c in row.index), "expense")
    inc = utils.format_amount(
        _get_column_value(row, "income", col_map) or 0,
        utils.get_amount_unit_hint_multiplier(income_col_name),
    )
    exp = utils.format_amount(
        _get_column_value(row, "expense", col_map) or 0,
        utils.get_amount_unit_hint_multiplier(expense_col_name),
    )
    return abs(inc + exp)


def _extract_transaction_features(
    row: pd.Series, col_map: Dict[str, List[str]], cp_counts: Dict[str, int]
) -> Optional[Tuple[Dict, Dict]]:
    """
    从单条交易数据中提取ML特征。

    提取的特征包括：
    - amount_log: 金额对数（解决长尾分布）
    - hour_sin/hour_cos: 时间周期编码
    - is_round_num: 是否为整数金额
    - freq_enc: 对手方频率编码
    - desc_len: 摘要长度

    Args:
        row: 交易行数据
        col_map: 列名映射字典
        cp_counts: 对手方计数字典

    Returns:
        (features_dict, raw_info_dict)元组，提取失败返回None
    """
    try:
        # 获取金额
        amount = _extract_transaction_amount(row, col_map)
        if amount == 0:
            return None

        # 获取日期
        date_val = _get_column_value(row, "date", col_map)
        date = _parse_transaction_date(date_val)
        if not date:
            return None

        # 获取其他字段
        cp = str(_get_column_value(row, "counterparty", col_map) or "")
        desc = str(_get_column_value(row, "description", col_map) or "")

        # 特征1: 金额对数（解决金额长尾分布问题）
        amount_log = np.log1p(amount)

        # 特征2&3: 时间周期编码（保留时序距离）
        hour = date.hour
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)

        # 特征4: 是否为整数（异常交易往往是整数）
        is_round = 1.0 if amount % 100 == 0 else 0.0

        # 特征5: 对手方频率编码（罕见对手方更可疑）
        # 取倒数，频率越低值越大
        freq = cp_counts.get(cp, 1)
        freq_enc = 1.0 / np.log1p(freq)

        # 特征6: 摘要长度（过短的摘要可能掩盖意图）
        desc_len = len(desc)

        features = {
            "amount_log": amount_log,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "is_round_num": is_round,
            "freq_enc": freq_enc,
            "desc_len": desc_len,
        }

        raw_info = {
            "amount": amount,
            "date": date,
            "counterparty": cp,
            "description": desc,
            "hour": hour,
        }

        return features, raw_info

    except Exception:
        return None


def _feature_engineering(
    all_transactions: Dict[str, pd.DataFrame], core_persons: List[str]
) -> Tuple[pd.DataFrame, Dict]:
    """
    特征工程：将原始交易转换为ML特征。

    处理流程：
    1. 第一遍遍历：全局统计对手方出现次数
    2. 第二遍遍历：为每笔交易提取特征

    提取的特征包括金额对数、时间编码、整数标记、对手方频率、摘要长度等。

    Args:
        all_transactions: 所有交易数据 {person: DataFrame}
        core_persons: 核心人员列表

    Returns:
        (features_df, raw_mapping)
        - features_df: 特征DataFrame
        - raw_mapping: 索引到原始交易信息的映射
    """
    features_list = []
    raw_mapping = {}  # 索引 -> 原始信息
    global_idx = 0

    # 第一遍遍历：统计全局对手方计数
    cp_counts = _count_counterparties_globally(all_transactions, COLUMN_MAPPING)

    # 第二遍遍历：为每个人构建特征
    for person in core_persons:
        df = _get_person_transactions(all_transactions, person)
        if df is None or df.empty:
            continue

        for _, row in df.iterrows():
            result = _extract_transaction_features(row, COLUMN_MAPPING, cp_counts)
            if result is None:
                continue

            features, raw_info = result
            features_list.append(features)

            # 保存原始信息用于后续分析
            raw_mapping[global_idx] = {"person": person, **raw_info}
            global_idx += 1

    return pd.DataFrame(features_list), raw_mapping


def _build_graph_transactions(all_transactions: Dict[str, pd.DataFrame]) -> List[Dict]:
    """
    构建图交易列表

    Args:
        all_transactions: 所有交易数据

    Returns:
        图交易列表
    """
    graph_transactions = []
    col_map = {
        "counterparty": ["counterparty", "交易对手", "对方户名", "交易对方名称"],
        "income": ["income", "收入", "收入(元)", "贷方发生额"],
        "expense": ["expense", "支出", "支出(元)", "借方发生额"],
        "amount": ["amount", "交易金额"],
    }

    def get_row_val(row, col_type):
        for c in col_map[col_type]:
            if c in row.index:
                return row[c]
        return None

    # 遍历所有数据构建图交易列表
    for person_key, df in all_transactions.items():
        if df.empty:
            continue

        source = person_key

        for _, row in df.iterrows():
            try:
                target = str(get_row_val(row, "counterparty") or "")
                if not target:
                    continue

                # 计算金额
                amt = 0.0
                val_amt = get_row_val(row, "amount")
                if val_amt is not None:
                    amount_col_name = next((c for c in col_map["amount"] if c in row.index), "amount")
                    amt = utils.format_amount(
                        val_amt, utils.get_amount_unit_hint_multiplier(amount_col_name)
                    )
                else:
                    income_col_name = next((c for c in col_map["income"] if c in row.index), "income")
                    expense_col_name = next((c for c in col_map["expense"] if c in row.index), "expense")
                    inc = utils.format_amount(
                        get_row_val(row, "income") or 0,
                        utils.get_amount_unit_hint_multiplier(income_col_name),
                    )
                    exp = utils.format_amount(
                        get_row_val(row, "expense") or 0,
                        utils.get_amount_unit_hint_multiplier(expense_col_name),
                    )
                    amt = inc + exp
                amt = abs(amt)

                # 确定方向
                is_income = False
                val_inc = get_row_val(row, "income")
                if utils.format_amount(
                    val_inc or 0,
                    utils.get_amount_unit_hint_multiplier(
                        next((c for c in col_map["income"] if c in row.index), "income")
                    ),
                ) > 0:
                    is_income = True

                if amt > 0:
                    if is_income:
                        graph_transactions.append(
                            {"source": target, "target": source, "amount": amt}
                        )
                    else:
                        graph_transactions.append(
                            {"source": source, "target": target, "amount": amt}
                        )

            except Exception:
                continue

    return graph_transactions


def _detect_statistical_anomalies(
    features_df: pd.DataFrame, raw_mapping: Dict
) -> Tuple[List[Dict], float]:
    """
    统计异常检测

    Args:
        features_df: 特征DataFrame
        raw_mapping: 原始交易映射

    Returns:
        (异常列表, 最高分数)
    """
    ml_anomalies = []
    final_scores_max = 0

    if features_df.empty:
        return ml_anomalies, final_scores_max

    detector = LightweightAnomalyDetector()

    feature_cols = [
        "amount_log",
        "hour_sin",
        "hour_cos",
        "is_round_num",
        "desc_len",
        "freq_enc",
    ]

    scores = detector.fit_predict(features_df, feature_cols, raw_mapping)

    if scores.max() > 0:
        final_scores = (scores / scores.max()) * 100
    else:
        final_scores = scores

    final_scores_max = round(final_scores.max(), 1)
    features_df["anomaly_score"] = final_scores

    # 提高阈值到85，减少误报
    threshold = 85
    anomalies_df = features_df[features_df["anomaly_score"] >= threshold].sort_values(
        "anomaly_score", ascending=False
    )

    for idx, row in anomalies_df.iterrows():
        original_info = raw_mapping.get(idx)
        if not original_info:
            continue

        # 额外过滤：金额至少500元的交易才纳入报告
        if original_info["amount"] < 500:
            continue

        # 过滤自我转账（同名账户间转账是正常的）
        if original_info["person"] == original_info.get("counterparty", ""):
            continue

        reasons = []
        if row["amount_log"] > detector.stats.get("amount_log", {}).get("q3", 0):
            reasons.append("金额显著偏离常规")
        if original_info["hour"] < 6 or original_info["hour"] >= 23:
            reasons.append("深夜/凌晨交易")
        if row["is_round_num"] > 0 and original_info["amount"] >= 1000:
            reasons.append("大额整数交易")
        if row["desc_len"] < 2:
            reasons.append("摘要信息缺失")

        ml_anomalies.append(
            {
                "person": original_info["person"],
                "date": original_info["date"],
                "amount": original_info["amount"],
                "counterparty": original_info["counterparty"],
                "description": original_info["description"],
                "score": round(row["anomaly_score"], 1),
                "reasons": "、".join(reasons) if reasons else "综合统计异常",
            }
        )

    return ml_anomalies, final_scores_max


def run_ml_analysis(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    involved_companies: List[str] = None,
) -> Dict:
    """
    执行机器学习风险分析

    包含:
    1. 统计异常检测 (Statistical Anomaly Detection)
    2. 图团伙挖掘 (Graph Community Detection) - 仅在核心实体之间

    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        involved_companies: 涉案公司列表
    """
    logger.info("=" * 60)
    logger.info("开始机器学习风险预测 (ML Analysis) - 优化版")
    logger.info("=" * 60)

    involved_companies = involved_companies or []

    # 构建核心实体集合
    core_entities = set(core_persons) | set(involved_companies)
    logger.info(
        f"核心实体: {len(core_entities)} 个 ({len(core_persons)}人 + {len(involved_companies)}公司)"
    )

    # --- Part 1: 数据准备 ---
    logger.info("【阶段1】特征工程与图构建")
    features_df, raw_mapping = _feature_engineering(all_transactions, core_persons)

    # 提取所有交易用于图分析
    graph_transactions = _build_graph_transactions(all_transactions)

    # --- Part 2: 统计异常检测 ---
    logger.info(f"【阶段2】统计模型分析 (样本数: {len(features_df)})")
    ml_anomalies, final_scores_max = _detect_statistical_anomalies(
        features_df, raw_mapping
    )

    if ml_anomalies:
        logger.info(f"  识别出 {len(ml_anomalies)} 笔高置信度异常交易")
    else:
        logger.warning("没有足够的数据进行统计ML分析")

    # --- Part 3: 图团伙挖掘（核心实体之间）---
    logger.info("【阶段3】资金团伙挖掘 (Graph Mining) - 仅核心实体")

    # 使用优化后的图检测器，只在核心实体之间构建图
    graph_detector = GraphCommunityDetector(
        core_entities=core_entities,
        min_amount=1000,  # 最低1000元的交易才纳入
    )
    graph_detector.build_graph(graph_transactions, strict_mode=True)

    # 挖掘至少2人的闭环
    communities = graph_detector.detect_communities(min_size=2, min_amount=50000)
    logger.info(f"  发现 {len(communities)} 个可疑资金网络/团伙")

    return {
        "anomalies": ml_anomalies,
        "communities": communities,
        "summary": {
            "total_samples": len(features_df),
            "anomaly_count": len(ml_anomalies),
            "community_count": len(communities),
            "max_score": final_scores_max,
            "graph_nodes": len(graph_detector.nodes),
            "graph_edges": graph_detector.edge_count,
        },
    }


def generate_ml_report(results: Dict, output_dir: str) -> str:
    """生成机器学习分析报告"""
    import os

    report_path = os.path.join(output_dir, "机器学习风险预测报告.txt")

    anomalies = results.get("anomalies", [])
    communities = results.get("communities", [])
    summary = results.get("summary", {})

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("机器学习风险预测报告 (增强版)\n")
        f.write("=" * 60 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")

        # 报告说明
        f.write("【报告用途】\n")
        f.write("本报告使用机器学习算法发现规则引擎难以覆盖的深层异常模式：\n")
        f.write("• 统计异常检测 - 多维特征的综合偏离度\n")
        f.write("• 图团伙挖掘 - Tarjan 算法检测资金闭环\n\n")

        f.write("【分析逻辑与规则】\n")
        f.write(
            "1. 特征工程: 金额对数、时间周期编码、整数判定、对手方频率编码、摘要长度\n"
        )
        f.write("2. 异常检测: Z-Score + IQR 融合，阈值 85 分\n")
        f.write("3. 图团伙: 仅在核心实体之间构建图，金额门槛 1000 元\n\n")

        f.write("【可能的误判情况】\n")
        f.write("⚠ 非标走时间的工作交易可能被标记为异常\n")
        f.write("⚠ 大额年终奖/报销可能产生误报\n")
        f.write("⚠ 正常业务往来可能被识别为团伙\n\n")

        f.write("【人工复核重点】\n")
        f.write("★ 高分异常: 核实交易背景\n")
        f.write("★ 资金闭环团伙: 核实闭环形成原因\n")
        f.write("★ 深夜交易: 核实交易时间合理性\n\n")

        f.write("=" * 60 + "\n\n")

        f.write("一、模型分析摘要\n")
        f.write("-" * 40 + "\n")
        f.write(f"分析样本总数: {summary.get('total_samples', 0)}\n")
        f.write(f"交易图节点数: {summary.get('graph_nodes', 0)}\n")
        f.write(f"交易图边数: {summary.get('graph_edges', 0)}\n")
        f.write(f"单笔异常数量: {summary.get('anomaly_count', 0)}\n")
        f.write(f"发现团伙数量: {summary.get('community_count', 0)}\n")
        f.write(f"最高异常评分: {summary.get('max_score', 0)}\n\n")

        # --- 团伙分析结果 ---
        if communities:
            f.write("二、可疑资金团伙分析 (Community Detection)\n")
            f.write("-" * 40 + "\n")
            f.write("说明: 基于图论算法发现的核心人员/涉案公司之间的资金闭环。\n\n")

            for i, comm in enumerate(communities, 1):
                f.write(f"团伙 #{i} [{comm['type']}]\n")
                f.write(
                    f"  核心成员: {', '.join(comm.get('core_members', comm['members']))}\n"
                )
                f.write(
                    f"  成员数量: {comm['count']} 人 (其中核心 {comm.get('core_count', '?')} 人)\n"
                )
                f.write(
                    f"  闭环交易总额: {utils.format_currency(comm['total_amount'])}\n"
                )
                f.write(f"  内部交易笔数: {comm.get('edge_count', 'N/A')} 笔\n")

                # 显示部分交易详情
                edge_details = comm.get("edge_details", [])
                if edge_details:
                    f.write(f"  主要交易链:\n")
                    for edge in edge_details[:5]:
                        f.write(
                            f"    {edge['from']} -> {edge['to']}: {utils.format_currency(edge['amount'])}\n"
                        )
                f.write("\n")
        else:
            f.write("二、可疑资金团伙分析\n")
            f.write("-" * 40 + "\n")
            f.write("未发现核心人员/涉案公司之间的强连通资金闭环。\n\n")

        f.write("三、高风险异常交易 (Top Anomalies)\n")
        f.write("-" * 40 + "\n")
        f.write(
            "注：评分(Score)基于交易金额、时间、对手方罕见度等维度的综合偏离度计算\n"
        )
        f.write("    已过滤小额交易和低风险类别\n")
        f.write(f"共 {len(anomalies)} 条记录\n\n")

        for i, item in enumerate(anomalies, 1):
            date_str = item["date"].strftime("%Y-%m-%d %H:%M")
            amount_str = utils.format_currency(item["amount"])

            f.write(f"{i}. 【评分 {item['score']}】 {item['person']} \n")
            f.write(f"   交易: {amount_str} -> {item['counterparty']} ({date_str})\n")
            f.write(
                f"   摘要: {item['description'][:50]}{'...' if len(item['description']) > 50 else ''}\n"
            )
            f.write(f"   原因: {item['reasons']}\n\n")

    logger.info(f"机器学习报告已生成: {report_path}")
    return report_path
