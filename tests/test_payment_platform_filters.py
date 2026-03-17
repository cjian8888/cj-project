import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flow_visualizer
import fund_penetration
import related_party_analyzer
from counterparty_utils import (
    is_payment_platform_counterparty,
    should_skip_payment_platform_counterparty,
)


def test_payment_platform_helpers_keep_only_direct_transfer_semantics():
    assert is_payment_platform_counterparty("支付宝（中国）网络技术有限公司")
    assert is_payment_platform_counterparty("财付通-微信转账")
    assert should_skip_payment_platform_counterparty(
        "支付宝（中国）网络技术有限公司",
        "网上支付 商家消费",
    )
    assert not should_skip_payment_platform_counterparty(
        "支付宝（中国）网络技术有限公司",
        "支付宝转账给张三",
    )
    assert not should_skip_payment_platform_counterparty(
        "微信转账",
        "好友转账",
    )


def test_flow_visualizer_skips_platform_consumption_but_keeps_direct_transfer():
    all_transactions = {
        "张三": pd.DataFrame(
            [
                {
                    "date": "2026-01-01 09:00:00",
                    "counterparty": "支付宝（中国）网络技术有限公司",
                    "description": "网上支付 商家消费",
                    "income": 0,
                    "expense": 2000,
                },
                {
                    "date": "2026-01-01 10:00:00",
                    "counterparty": "微信转账",
                    "description": "好友转账",
                    "income": 0,
                    "expense": 3000,
                },
                {
                    "date": "2026-01-01 11:00:00",
                    "counterparty": "财付通-微信转账",
                    "description": "红包转入",
                    "income": 1800,
                    "expense": 0,
                },
            ]
        )
    }

    flow_stats = flow_visualizer._calculate_flow_stats(all_transactions, ["张三"])

    assert ("张三", "支付宝（中国）网络技术有限公司") not in flow_stats
    assert flow_stats[("张三", "微信转账")]["total"] == 3000
    assert flow_stats[("财付通-微信转账", "张三")]["total"] == 1800


def test_payment_platform_nodes_do_not_create_cycles_or_outer_ring_entities():
    all_transactions = {
        "张三": pd.DataFrame(
            [
                {
                    "date": "2026-01-01",
                    "income": 0,
                    "expense": 50000,
                    "counterparty": "支付宝（中国）网络技术有限公司",
                    "description": "支付宝转账",
                    "数据来源": "zhangsan.xlsx",
                    "source_row_index": 11,
                },
            ]
        ),
        "支付宝（中国）网络技术有限公司": pd.DataFrame(
            [
                {
                    "date": "2026-01-02",
                    "income": 0,
                    "expense": 50000,
                    "counterparty": "陈斌",
                    "description": "转账给陈斌",
                    "数据来源": "alipay.xlsx",
                    "source_row_index": 12,
                },
            ]
        ),
        "陈斌": pd.DataFrame(
            [
                {
                    "date": "2026-01-03",
                    "income": 0,
                    "expense": 50000,
                    "counterparty": "微信转账",
                    "description": "微信转账",
                    "数据来源": "chenbin.xlsx",
                    "source_row_index": 13,
                },
            ]
        ),
        "微信转账": pd.DataFrame(
            [
                {
                    "date": "2026-01-04",
                    "income": 0,
                    "expense": 50000,
                    "counterparty": "张三",
                    "description": "转账给张三",
                    "数据来源": "wechat.xlsx",
                    "source_row_index": 14,
                },
            ]
        ),
    }

    penetration_results = fund_penetration.analyze_fund_penetration(
        personal_data=all_transactions,
        company_data={},
        core_persons=["张三", "陈斌"],
        companies=[],
    )
    related_party_results = related_party_analyzer.analyze_related_party_flows(
        all_transactions,
        ["张三", "陈斌"],
    )

    assert penetration_results["fund_cycles"] == []
    assert not any(
        channel["node"] in {"支付宝（中国）网络技术有限公司", "微信转账"}
        for channel in penetration_results["pass_through_channels"]
    )
    assert not any(
        hub["node"] in {"支付宝（中国）网络技术有限公司", "微信转账"}
        for hub in penetration_results["hub_nodes"]
    )
    assert related_party_results["fund_loops"] == []
    assert not any(
        node["name"] in {"支付宝（中国）网络技术有限公司", "微信转账"}
        for node in related_party_results["discovered_nodes"]
    )
    assert not any(
        {"支付宝（中国）网络技术有限公司", "微信转账"}
        & set(cluster.get("external_members", []))
        for cluster in related_party_results["relationship_clusters"]
    )
