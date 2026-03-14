#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一风险模型第二阶段回归测试。"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unified_risk_model import UnifiedRiskModel


def test_unified_risk_model_scores_relay_cluster_and_external_nodes():
    model = UnifiedRiskModel()
    result = model.calculate_score(
        entity_name="张三",
        evidence={
            "money_loops": [],
            "transit_channel": {},
            "transit_channels": [],
            "relay_chains": [
                {"risk_score": 82, "confidence": 0.91},
                {"risk_score": 75, "confidence": 0.85},
            ],
            "relationship_clusters": [
                {
                    "risk_score": 84,
                    "confidence": 0.88,
                    "loop_count": 1,
                    "relay_count": 2,
                }
            ],
            "discovered_nodes": [
                {"risk_score": 68, "confidence": 0.8, "occurrences": 3}
            ],
            "direct_relations": [
                {"amount": 260000},
                {"amount": 180000},
            ],
            "related_entities": ["外围账户B", "李四", "王五"],
            "ml_anomalies": [],
            "total_records": 1200,
        },
        financial_ratio=0.0,
        family_ratio=0.0,
    )

    assert result.total_score > 45
    assert result.risk_level in {"HIGH", "CRITICAL"}
    assert "第三方中转" in result.reason
    assert "关系簇" in result.reason
    assert "外围节点" in result.reason
    assert result.details["relay_score"] > 0
    assert result.details["cluster_score"] > 0
    assert result.details["external_node_score"] > 0
    assert result.details["direct_relation_score"] > 0


def test_unified_risk_model_confidence_penalizes_truncated_search():
    model = UnifiedRiskModel()
    result = model.calculate_score(
        entity_name="李四",
        evidence={
            "money_loops": [{"risk_score": 88, "confidence": 0.95}],
            "relay_chains": [{"risk_score": 79, "confidence": 0.9}],
            "relationship_clusters": [],
            "discovered_nodes": [],
            "direct_relations": [],
            "related_entities": ["外围账户B"],
            "ml_anomalies": [],
            "total_records": 5000,
            "money_loop_meta": {"truncated": True},
        },
        financial_ratio=0.0,
        family_ratio=0.0,
    )

    assert 0.6 <= result.confidence <= 0.95
