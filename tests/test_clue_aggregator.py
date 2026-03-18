#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""线索聚合 explainability 回归测试。"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from clue_aggregator import ClueAggregator, generate_aggregation_report


def _stub_ratio_calculators(monkeypatch):
    monkeypatch.setattr(
        ClueAggregator,
        "_calculate_financial_ratio",
        lambda self, entity: 0.0,
    )
    monkeypatch.setattr(
        ClueAggregator,
        "_calculate_family_transfer_ratio",
        lambda self, entity: 0.0,
    )


def test_aggregator_consumes_phase1_related_party_and_outputs_ranked_entities(monkeypatch):
    _stub_ratio_calculators(monkeypatch)

    aggregator = ClueAggregator(["张三", "李四"], [])
    aggregator.aggregate_penetration_results(
        {
            "analysis_metadata": {
                "fund_cycles": {
                    "truncated": True,
                    "truncated_reasons": ["timeout"],
                    "timeout_seconds": 30,
                }
            },
            "fund_cycles": [
                {
                    "participants": ["张三", "外围账户B", "李四"],
                    "path": "张三 → 外围账户B → 李四 → 张三",
                    "risk_score": 86,
                    "confidence": 0.91,
                    "evidence": ["形成穿透闭环"],
                }
            ],
            "pass_through_channels": [
                {
                    "node": "张三",
                    "inflow": 500_000,
                    "outflow": 490_000,
                    "ratio": 0.98,
                    "risk_score": 75,
                    "confidence": 0.88,
                    "evidence": ["进出平衡"],
                }
            ],
        }
    )
    aggregator.aggregate_related_party_results(
        {
            "analysis_metadata": {
                "third_party_relays": {"returned_count": 1},
                "fund_loops": {"truncated": False},
            },
            "direct_flows": [
                {
                    "from": "张三",
                    "to": "李四",
                    "amount": 200_000,
                    "date": "2024-01-02",
                }
            ],
            "third_party_relays": [
                {
                    "from": "张三",
                    "relay": "外围账户B",
                    "to": "李四",
                    "outflow_amount": 180_000,
                    "risk_score": 79,
                    "confidence": 0.9,
                    "evidence": ["6小时内近额回流"],
                }
            ],
            "fund_loops": [
                {
                    "participants": ["张三", "外围账户B", "张三"],
                    "path": "张三 → 外围账户B → 张三",
                    "risk_score": 82,
                    "confidence": 0.87,
                    "evidence": ["关联方闭环"],
                }
            ],
            "discovered_nodes": [
                {
                    "name": "外围账户B",
                    "linked_cores": ["张三", "李四"],
                    "occurrences": 2,
                    "risk_score": 68,
                    "confidence": 0.76,
                    "evidence": ["多次出现在 relay/loop 中"],
                }
            ],
            "relationship_clusters": [
                {
                    "cluster_id": "cluster_1",
                    "core_members": ["张三", "李四"],
                    "external_members": ["外围账户B"],
                    "loop_count": 1,
                    "relay_count": 1,
                    "direct_flow_count": 1,
                    "risk_score": 84,
                    "confidence": 0.89,
                    "evidence": ["形成混合型关系簇"],
                }
            ],
        }
    )

    aggregator.calculate_entity_risk_scores()
    result = aggregator.to_dict()

    zhang_pack = result["evidencePacks"]["张三"]
    li_pack = result["evidencePacks"]["李四"]

    assert len(zhang_pack["evidence"]["fund_cycles"]) == 2
    assert len(zhang_pack["evidence"]["third_party_relays"]) == 1
    assert len(zhang_pack["evidence"]["discovered_nodes"]) == 1
    assert len(zhang_pack["evidence"]["relationship_clusters"]) == 1
    assert len(li_pack["evidence"]["relationship_clusters"]) == 1
    assert result["analysisMetadata"]["penetration"]["fund_cycles"]["truncated"] is True
    assert result["analysisMetadata"]["related_party"]["third_party_relays"]["returned_count"] == 1
    assert result["rankedEntities"][0]["riskConfidence"] >= 0.5
    assert result["summary"]["风险实体总数"] == 2
    assert result["summary"]["高优先线索实体数"] >= 1
    top_clue = result["rankedEntities"][0]["aggregationExplainability"]["top_clues"][0]
    assert top_clue["evidence_template"]["headline"]


def test_ranked_entities_use_risk_confidence_as_tie_breaker():
    aggregator = ClueAggregator(["张三", "李四"], [])

    aggregator.evidence_packs["张三"].update(
        {
            "risk_score": 60.0,
            "risk_level": "high",
            "risk_confidence": 0.91,
            "top_evidence_score": 82.0,
            "high_priority_clue_count": 2,
            "summary": "张三证据更强",
            "aggregation_explainability": {
                "top_clues": [{"description": "关系簇: cluster_1"}]
            },
        }
    )
    aggregator.evidence_packs["张三"]["evidence"]["fund_cycles"].append(
        {"path": "张三 → 外围账户B → 张三"}
    )

    aggregator.evidence_packs["李四"].update(
        {
            "risk_score": 60.0,
            "risk_level": "high",
            "risk_confidence": 0.63,
            "top_evidence_score": 88.0,
            "high_priority_clue_count": 3,
            "summary": "李四证据分更高但置信度更低",
            "aggregation_explainability": {
                "top_clues": [{"description": "资金闭环: 张三 → 李四 → 张三"}]
            },
        }
    )
    aggregator.evidence_packs["李四"]["evidence"]["fund_cycles"].append(
        {"path": "张三 → 李四 → 张三"}
    )

    ranked = aggregator.get_ranked_entities()

    assert ranked[0]["entity"] == "张三"
    assert ranked[1]["entity"] == "李四"


def test_top_clues_preserve_path_explainability(monkeypatch):
    _stub_ratio_calculators(monkeypatch)

    aggregator = ClueAggregator(["张三"], [])
    aggregator.aggregate_related_party_results(
        {
            "analysis_metadata": {
                "third_party_relays": {"returned_count": 1},
                "fund_loops": {"truncated": False},
            },
            "third_party_relays": [
                {
                    "from": "张三",
                    "relay": "外围账户B",
                    "to": "张三",
                    "outflow_amount": 200000,
                    "inflow_amount": 198000,
                    "amount_diff": 2000,
                    "time_diff_hours": 4.0,
                    "risk_level": "high",
                    "risk_score": 82,
                    "confidence": 0.91,
                }
            ],
        }
    )

    aggregator.calculate_entity_risk_scores()
    result = aggregator.to_dict()
    top_clue = result["rankedEntities"][0]["aggregationExplainability"]["top_clues"][0]

    assert top_clue["bucket"] == "third_party_relays"
    assert top_clue["path_explainability"]["path_type"] == "third_party_relay"
    assert top_clue["path_explainability"]["relay_node"] == "外围账户B"
    assert len(top_clue["path_explainability"]["time_axis"]) == 2


def test_generate_aggregation_report_includes_phase1_explainability_sections(tmp_path):
    aggregator = ClueAggregator(["张三"], [])
    aggregator.evidence_packs["张三"].update(
        {
            "risk_score": 83.0,
            "risk_level": "critical",
            "risk_confidence": 0.88,
            "top_evidence_score": 84.0,
            "high_priority_clue_count": 3,
            "summary": "存在混合型回流结构",
        }
    )
    aggregator.evidence_packs["张三"]["evidence"]["third_party_relays"].append(
        {
            "from": "张三",
            "relay": "外围账户B",
            "to": "张三",
            "outflow_amount": 120_000,
            "risk_score": 79,
        }
    )
    aggregator.evidence_packs["张三"]["evidence"]["discovered_nodes"].append(
        {
            "name": "外围账户B",
            "linked_cores": ["张三"],
            "occurrences": 2,
            "risk_score": 68,
        }
    )
    aggregator.evidence_packs["张三"]["evidence"]["relationship_clusters"].append(
        {
            "core_members": ["张三"],
            "external_members": ["外围账户B"],
            "loop_count": 1,
            "relay_count": 1,
            "direct_flow_count": 0,
            "risk_score": 84,
        }
    )

    report_path = generate_aggregation_report(aggregator, str(tmp_path))
    content = open(report_path, "r", encoding="utf-8").read()

    assert "风险置信度" in content
    assert "第三方中转链路" in content
    assert "外围节点发现" in content
    assert "关系簇识别" in content


def test_aggregator_risk_score_consumes_relays_clusters_and_discovered_nodes(monkeypatch):
    _stub_ratio_calculators(monkeypatch)

    aggregator = ClueAggregator(["张三"], [])
    aggregator.aggregate_related_party_results(
        {
            "analysis_metadata": {
                "third_party_relays": {"returned_count": 1, "truncated": False},
                "fund_loops": {"truncated": False},
            },
            "direct_flows": [
                {"from": "张三", "to": "李四", "amount": 300_000}
            ],
            "third_party_relays": [
                {
                    "from": "张三",
                    "relay": "外围账户B",
                    "to": "李四",
                    "outflow_amount": 260_000,
                    "risk_score": 80,
                    "confidence": 0.9,
                }
            ],
            "discovered_nodes": [
                {
                    "name": "外围账户B",
                    "linked_cores": ["张三"],
                    "occurrences": 3,
                    "risk_score": 70,
                    "confidence": 0.82,
                }
            ],
            "relationship_clusters": [
                {
                    "cluster_id": "cluster_1",
                    "core_members": ["张三"],
                    "external_members": ["外围账户B"],
                    "loop_count": 0,
                    "relay_count": 1,
                    "direct_flow_count": 1,
                    "risk_score": 83,
                    "confidence": 0.88,
                }
            ],
        }
    )

    aggregator.calculate_entity_risk_scores()
    pack = aggregator.get_entity_evidence_pack("张三")

    assert pack["risk_score"] > 20
    assert "第三方中转" in pack["summary"] or "关系簇" in pack["summary"] or "外围节点" in pack["summary"]
    assert pack["risk_details"]["relay_score"] > 0
    assert pack["risk_details"]["cluster_score"] > 0
    assert pack["risk_details"]["external_node_score"] > 0


def test_aggregator_consumes_wallet_results_and_emits_wallet_evidence(monkeypatch):
    _stub_ratio_calculators(monkeypatch)

    aggregator = ClueAggregator(["张三"], [])
    aggregator.aggregate_wallet_results(
        {
            "subjects": [
                {
                    "subjectId": "110101199001010011",
                    "subjectName": "张三",
                    "matchedToCore": True,
                    "crossSignals": {
                        "phoneOverlapCount": 1,
                        "bankCardOverlapCount": 2,
                        "aliasMatchCount": 1,
                    },
                    "platforms": {
                        "alipay": {
                            "transactionCount": 60,
                            "incomeTotalYuan": 220000,
                            "expenseTotalYuan": 150000,
                            "topCounterparties": [{"name": "李四", "count": 6, "totalAmountYuan": 62000}],
                        },
                        "wechat": {
                            "tenpayTransactionCount": 40,
                            "incomeTotalYuan": 120000,
                            "expenseTotalYuan": 100000,
                            "loginEventCount": 18,
                            "topCounterparties": [{"name": "王五", "count": 5, "totalAmountYuan": 58000}],
                        },
                    },
                }
            ],
            "alerts": [
                {
                    "person": "张三",
                    "counterparty": "李四",
                    "amount": 62000,
                    "risk_level": "medium",
                    "description": "与李四电子钱包往来密集",
                    "risk_reason": "高频对手方",
                    "alert_type": "wallet_dense_counterparty",
                }
            ],
        }
    )

    aggregator.calculate_entity_risk_scores()
    result = aggregator.to_dict()
    pack = result["evidencePacks"]["张三"]

    assert len(pack["evidence"]["wallet_summaries"]) == 1
    assert len(pack["evidence"]["wallet_alerts"]) == 1
    assert result["rankedEntities"][0]["aggregationExplainability"]["top_clues"][0]["bucket"] in {
        "wallet_alerts",
        "wallet_summaries",
    }


def test_aggregator_wallet_alert_prefers_source_risk_score_and_confidence(monkeypatch):
    _stub_ratio_calculators(monkeypatch)

    aggregator = ClueAggregator(["张三"], [])
    aggregator.aggregate_wallet_results(
        {
            "subjects": [],
            "alerts": [
                {
                    "person": "张三",
                    "counterparty": "待确认电子钱包主体",
                    "amount": 1_280_000,
                    "risk_level": "high",
                    "description": "张三尚未归并到主链主体，但电子钱包规模较大。",
                    "risk_reason": "补充数据中存在规模较大的未映射电子钱包主体。",
                    "alert_type": "wallet_unmapped_large_scale",
                    "rule_code": "WALLET-UNMAPPED-LARGE-001",
                    "risk_score": 88.5,
                    "confidence": 0.72,
                    "evidence_summary": "未命中主链，电子钱包累计320笔，累计128.0万元。",
                }
            ],
        }
    )

    pack = aggregator.to_dict()["evidencePacks"]["张三"]
    alert = pack["evidence"]["wallet_alerts"][0]

    assert alert["risk_score"] == 72.0
    assert alert["confidence"] == 0.72
    assert alert["rule_code"] == "WALLET-UNMAPPED-LARGE-001"
    assert any("未命中主链" in item for item in alert["evidence"])


def test_aggregator_dedupes_related_party_records_across_sources(monkeypatch):
    _stub_ratio_calculators(monkeypatch)

    aggregator = ClueAggregator(["张三", "李四"], [])
    shared_flow = {
        "from": "张三",
        "to": "李四",
        "amount": 200000,
        "date": "2024-01-02",
        "description": "转账",
        "relationship_context": "family",
    }

    aggregator.aggregate_penetration_results(
        {
            "person_to_person": [
                {
                    "发起方": "张三",
                    "接收方": "李四",
                    "金额": 200000,
                    "日期": "2024-01-02",
                    "摘要": "转账",
                }
            ]
        }
    )
    aggregator.aggregate_related_party_results({"direct_flows": [shared_flow]})

    pack = aggregator.get_entity_evidence_pack("张三")

    assert len(pack["evidence"]["related_party"]) == 1
    assert pack["evidence"]["related_party"][0]["relationship_context"] == "family"


def test_penetration_direct_transactions_do_not_pollute_related_party_bucket(monkeypatch):
    _stub_ratio_calculators(monkeypatch)

    aggregator = ClueAggregator(["朱明", "吴嘉欣"], [])
    aggregator.aggregate_penetration_results(
        {
            "person_to_person": [
                {
                    "发起方": "朱明",
                    "接收方": "吴嘉欣",
                    "金额": 10000,
                    "日期": "2024-01-02T10:00:00",
                    "摘要": "旧格式侧账",
                }
            ]
        }
    )
    aggregator.aggregate_related_party_results(
        {
            "direct_flows": [
                {
                    "from": "朱明",
                    "to": "吴嘉欣",
                    "amount": 10000,
                    "date": "2024-01-02T10:00:00",
                    "description": "转账",
                    "relationship_context": "family",
                    "transaction_refs_total": 2,
                    "transaction_refs": [
                        {"date": "2024-01-02T10:00:00", "amount": 10000},
                        {"date": "2024-01-02T10:00:01", "amount": 10000},
                    ],
                }
            ]
        }
    )

    pack = aggregator.get_entity_evidence_pack("朱明")

    assert len(pack["evidence"]["related_party"]) == 1
    assert pack["evidence"]["related_party"][0]["transaction_refs_total"] == 2
    assert "发起方" not in pack["evidence"]["related_party"][0]


def test_aggregator_excludes_family_and_generic_wallet_counterparties_from_entity_count(monkeypatch):
    _stub_ratio_calculators(monkeypatch)

    aggregator = ClueAggregator(["朱明"], [])
    aggregator.aggregate_wallet_results(
        {
            "subjects": [],
            "alerts": [
                {
                    "person": "朱明",
                    "counterparty": "吴嘉欣",
                    "counterparty_role": "family",
                    "amount": 120000,
                    "risk_level": "low",
                    "alert_type": "wallet_bank_counterparty_overlap",
                },
                {
                    "person": "朱明",
                    "counterparty": "电子钱包总体",
                    "counterparty_role": "external",
                    "amount": 220000,
                    "risk_level": "medium",
                    "alert_type": "wallet_quick_pass_through",
                },
            ],
        }
    )

    aggregator.calculate_entity_risk_scores()
    pack = aggregator.get_entity_evidence_pack("朱明")

    assert pack["risk_details"]["entity_score"] == 0.0
