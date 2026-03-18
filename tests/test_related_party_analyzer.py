#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""关联方分析家庭关系回归测试。"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from related_party_analyzer import _analyze_direct_flows, _build_relationship_clusters


def test_direct_flows_mark_family_relationship_context():
    all_transactions = {
        "朱明": pd.DataFrame(
            [
                {
                    "counterparty": "吴嘉欣",
                    "date": "2025-01-03",
                    "income": 0,
                    "expense": 88000,
                    "description": "家庭内部转账",
                }
            ]
        )
    }

    direct_flows = _analyze_direct_flows(
        all_transactions,
        ["朱明", "吴嘉欣"],
        family_pair_keys={frozenset(("朱明", "吴嘉欣"))},
    )

    assert len(direct_flows) == 1
    assert direct_flows[0]["relationship_context"] == "family"
    assert direct_flows[0]["from"] == "朱明"
    assert direct_flows[0]["to"] == "吴嘉欣"
    assert direct_flows[0]["direction"] == "pay"


def test_direct_flows_dedupe_mirrored_side_ledgers_and_preserve_refs():
    all_transactions = {
        "朱明": pd.DataFrame(
            [
                {
                    "counterparty": "吴嘉欣",
                    "date": pd.Timestamp("2025-01-03 12:00:00"),
                    "income": 0,
                    "expense": 88000,
                    "description": "家庭内部转账",
                    "数据来源": "朱明侧.xlsx",
                    "source_row_index": 8,
                }
            ]
        ),
        "吴嘉欣": pd.DataFrame(
            [
                {
                    "counterparty": "朱明",
                    "date": pd.Timestamp("2025-01-03 12:00:01"),
                    "income": 88000,
                    "expense": 0,
                    "description": "家庭内部转账入账",
                    "数据来源": "吴嘉欣侧.xlsx",
                    "source_row_index": 18,
                }
            ]
        ),
    }

    direct_flows = _analyze_direct_flows(
        all_transactions,
        ["朱明", "吴嘉欣"],
        family_pair_keys={frozenset(("朱明", "吴嘉欣"))},
    )

    assert len(direct_flows) == 1
    flow = direct_flows[0]
    assert flow["from"] == "朱明"
    assert flow["to"] == "吴嘉欣"
    assert flow["amount"] == 88000
    assert flow["direction"] == "pay"
    assert flow["relationship_context"] == "family"
    assert flow["source_file"] == "朱明侧.xlsx"
    assert flow["source_row_index"] == 8
    assert flow["transaction_refs_total"] == 2
    assert {item["direction"] for item in flow["transaction_refs"]} == {"pay", "receive"}


def test_relationship_cluster_downgrades_family_only_direct_flows():
    results = {
        "direct_flows": [
            {
                "from": "朱明",
                "to": "吴嘉欣",
                "date": "2025-01-03",
                "amount": 88000,
                "relationship_context": "family",
            }
        ],
        "third_party_relays": [],
        "fund_loops": [],
    }

    clusters = _build_relationship_clusters(
        results,
        ["朱明", "吴嘉欣"],
        family_pair_keys={frozenset(("朱明", "吴嘉欣"))},
    )

    assert len(clusters) == 1
    cluster = clusters[0]

    assert cluster["relationship_context"] == "family"
    assert cluster["external_members"] == []
    assert cluster["risk_score"] < 30
    assert any("家庭成员关系" in item for item in cluster["evidence"])
