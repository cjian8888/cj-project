from pathlib import Path
import sys
import importlib.util

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def _load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(
        module_name,
        PROJECT_ROOT / relative_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


import utils

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

loan_analyzer = _load_module("phase1_loan_analyzer", "loan_analyzer.py")
suspicion_detector = _load_module("phase1_suspicion_detector", "suspicion_detector.py")
time_series_analyzer = _load_module("phase1_time_series_analyzer", "time_series_analyzer.py")
related_party_analyzer = _load_module("phase1_related_party_analyzer", "related_party_analyzer.py")
fund_penetration = _load_module("phase2_fund_penetration", "fund_penetration.py")


def test_sort_transactions_strict_orders_same_second_by_source_row_index():
    df = pd.DataFrame(
        [
            {"date": "2026-01-01 10:00:00", "source_row_index": 9, "amount": 100},
            {"date": "2026-01-01 10:00:00", "source_row_index": 2, "amount": 200},
            {"date": "2026-01-01 09:59:59", "source_row_index": 5, "amount": 300},
        ]
    )

    sorted_df = utils.sort_transactions_strict(df, date_col="date", dropna_date=True)

    assert sorted_df["source_row_index"].tolist() == [5, 2, 9]


def test_detect_cash_time_collision_uses_best_single_match_in_window():
    withdrawals = pd.DataFrame(
        [
            {"date": "2026-01-01 09:00:00", "amount": 1000, "source_row_index": 3},
            {"date": "2026-01-01 08:00:00", "amount": 1800, "source_row_index": 1},
        ]
    )
    deposits = pd.DataFrame(
        [
            {"date": "2026-01-01 10:00:00", "amount": 1020, "source_row_index": 8},
            {"date": "2026-01-01 10:30:00", "amount": 1010, "source_row_index": 9},
        ]
    )

    collisions = suspicion_detector.detect_cash_time_collision(withdrawals, deposits, "张三")

    assert len(collisions) == 1
    assert collisions[0]["withdrawal_amount"] == 1000
    assert collisions[0]["deposit_amount"] == 1020


def test_detect_delayed_transfers_handles_unsorted_input_and_keeps_alias_fields():
    df = pd.DataFrame(
        [
            {"date": "2026-01-05", "income": 0, "expense": 10050, "counterparty": "乙方", "source_row_index": 6},
            {"date": "2026-01-01", "income": 10001, "expense": 0, "counterparty": "甲方", "source_row_index": 1},
            {"date": "2026-01-12", "income": 0, "expense": 12000, "counterparty": "乙方", "source_row_index": 8},
            {"date": "2026-01-08", "income": 12000, "expense": 0, "counterparty": "甲方", "source_row_index": 2},
            {"date": "2026-01-19", "income": 0, "expense": 15000, "counterparty": "乙方", "source_row_index": 9},
            {"date": "2026-01-15", "income": 15000, "expense": 0, "counterparty": "甲方", "source_row_index": 4},
        ]
    )

    results = time_series_analyzer.detect_delayed_transfers(
        {"张三": df},
        ["张三"],
        delay_range=(4, 4),
        min_pairs=3,
    )

    assert len(results) == 1
    result = results[0]
    assert result["person"] == "张三"
    assert result["occurrences"] == 3
    assert result["count"] == 3
    assert result["income_from"] == "甲方"
    assert result["income_counterparty"] == "甲方"
    assert result["expense_to"] == "乙方"
    assert result["expense_counterparty"] == "乙方"


def test_no_repayment_loans_do_not_reuse_single_future_expense_for_multiple_loans():
    df = pd.DataFrame(
        [
            {"date": "2024-01-01", "income": 100000, "expense": 0, "counterparty": "李四", "source_row_index": 1, "description": "借入1"},
            {"date": "2024-02-01", "income": 100000, "expense": 0, "counterparty": "李四", "source_row_index": 2, "description": "借入2"},
            {"date": "2024-03-01", "income": 0, "expense": 100000, "counterparty": "李四", "source_row_index": 3, "description": "还款"},
        ]
    )

    results = loan_analyzer._detect_no_repayment_loans(
        {"张三_账户": df},
        ["张三"],
        min_amount=50000,
        min_days=30,
    )

    assert len(results) == 1
    assert results[0]["income_date"].strftime("%Y-%m-%d") == "2024-02-01"
    assert results[0]["repay_ratio"] == 0


def test_loan_pairs_support_installment_repayments_under_serial_allocation():
    df = pd.DataFrame(
        [
            {"date": "2026-01-01", "income": 100000, "expense": 0, "counterparty": "李四", "source_row_index": 1, "description": "借入"},
            {"date": "2026-02-01", "income": 0, "expense": 30000, "counterparty": "李四", "source_row_index": 2, "description": "还款1"},
            {"date": "2026-03-01", "income": 0, "expense": 30000, "counterparty": "李四", "source_row_index": 3, "description": "还款2"},
            {"date": "2026-04-01", "income": 0, "expense": 40000, "counterparty": "李四", "source_row_index": 4, "description": "还款3"},
        ]
    )

    results = loan_analyzer._detect_loan_pairs({"张三_账户": df}, ["张三"], time_window_days=365)

    assert len(results) == 1
    pair = results[0]
    assert pair["loan_amount"] == 100000
    assert pair["repay_amount"] == 100000
    assert pair["repayment_count"] == 3
    assert pair["allocation_mode"] == "serial_allocation"


def test_loan_pairs_keep_single_repayment_amount_when_only_one_loan_is_eligible():
    df = pd.DataFrame(
        [
            {"date": "2026-01-01", "income": 100000, "expense": 0, "counterparty": "李四", "source_row_index": 1, "description": "借入"},
            {"date": "2026-02-01", "income": 0, "expense": 110000, "counterparty": "李四", "source_row_index": 2, "description": "一次性还本付息"},
        ]
    )

    results = loan_analyzer._detect_loan_pairs({"张三_账户": df}, ["张三"], time_window_days=365)

    assert len(results) == 1
    pair = results[0]
    assert pair["loan_amount"] == 100000
    assert pair["repay_amount"] == 110000
    assert pair["repayment_count"] == 1
    assert pair["allocation_mode"] == "single_repayment"


def test_related_party_fund_loops_detects_single_core_with_outer_ring_cycle():
    all_transactions = {
        "张三": pd.DataFrame(
            [
                {"date": "2026-01-01", "income": 0, "expense": 50000, "counterparty": "外围账户B", "数据来源": "zhangsan.xlsx", "source_row_index": 11},
            ]
        ),
        "外围账户B": pd.DataFrame(
            [
                {"date": "2026-01-02", "income": 0, "expense": 50000, "counterparty": "外围账户C", "数据来源": "relay_b.xlsx", "source_row_index": 22},
            ]
        ),
        "外围账户C": pd.DataFrame(
            [
                {"date": "2026-01-03", "income": 0, "expense": 50000, "counterparty": "张三", "数据来源": "relay_c.xlsx", "source_row_index": 33},
            ]
        ),
    }

    loops = related_party_analyzer._detect_fund_loops(all_transactions, ["张三"], max_depth=4)

    assert len(loops) == 1
    loop = loops[0]
    assert loop["path"] == "张三 → 外围账户B → 外围账户C → 张三"
    assert loop["core_node_count"] == 1
    assert loop["external_node_count"] == 2
    assert loop["risk_score"] >= 50
    assert loop["confidence"] >= 0.5
    assert any("闭环路径" in evidence for evidence in loop["evidence"])
    assert loop["path_explainability"]["path_type"] == "fund_cycle"
    assert len(loop["path_explainability"]["edge_segments"]) == 3
    assert loop["path_explainability"]["bottleneck_edge"]["amount"] == 50000
    assert loop["path_explainability"]["edge_segments"][0]["transaction_refs"][0]["source_file"] == "zhangsan.xlsx"
    assert loop["path_explainability"]["edge_segments"][0]["transaction_refs_total"] == 1
    assert loop["path_explainability"]["edge_segments"][0]["transaction_ref_sample_count"] == 1
    assert loop["path_explainability"]["edge_segments"][0]["transaction_refs_returned"] == 1
    assert loop["path_explainability"]["edge_segments"][0]["transaction_refs_truncated"] is False
    assert loop["path_explainability"]["evidence_template"]["headline"] == loop["path"]
    assert loop["path_explainability"]["evidence_template"]["supporting_refs"]["total"] == 3


def test_analyze_related_party_flows_exposes_discovered_nodes_and_clusters():
    all_transactions = {
        "张三": pd.DataFrame(
            [
                {"date": "2026-01-01", "income": 0, "expense": 50000, "counterparty": "外围账户B", "description": "转出", "数据来源": "zhangsan.xlsx", "source_row_index": 11},
            ]
        ),
        "李四": pd.DataFrame(
            [
                {"date": "2026-01-02", "income": 48000, "expense": 0, "counterparty": "外围账户B", "description": "转入", "数据来源": "lisi.xlsx", "source_row_index": 12},
            ]
        ),
        "外围账户B": pd.DataFrame(
            [
                {"date": "2026-01-03", "income": 0, "expense": 50000, "counterparty": "张三", "description": "回流", "数据来源": "relay_b.xlsx", "source_row_index": 13},
            ]
        ),
    }

    results = related_party_analyzer.analyze_related_party_flows(all_transactions, ["张三", "李四"])

    discovered = results["discovered_nodes"]
    clusters = results["relationship_clusters"]
    summary = results["summary"]

    assert any(node["name"] == "外围账户B" for node in discovered)
    discovered_node = next(node for node in discovered if node["name"] == "外围账户B")
    cluster = next(cluster for cluster in clusters if "外围账户B" in cluster["external_members"])
    assert set(cluster["core_members"]) == {"张三", "李四"}
    assert "third_party_relay" in cluster["relation_types"] or "fund_loop" in cluster["relation_types"]
    assert discovered_node["risk_score"] >= 40
    assert discovered_node["confidence"] >= 0.5
    assert cluster["risk_score"] >= 40
    assert cluster["confidence"] >= 0.5
    assert results["third_party_relays"][0]["path_explainability"]["path_type"] == "third_party_relay"
    assert len(results["third_party_relays"][0]["path_explainability"]["time_axis"]) == 2
    assert results["third_party_relays"][0]["path_explainability"]["time_axis"][0]["source_file"] == "zhangsan.xlsx"
    assert results["third_party_relays"][0]["path_explainability"]["time_axis_total"] == 2
    assert results["third_party_relays"][0]["path_explainability"]["time_axis_truncated"] is False
    assert cluster["path_explainability"]["path_type"] == "relationship_cluster"
    assert cluster["path_explainability"]["representative_path_count"] >= 1
    assert len(cluster["path_explainability"]["representative_paths"]) >= 1
    relay_path = next(
        item
        for item in cluster["path_explainability"]["representative_paths"]
        if item["path_type"] == "third_party_relay"
    )
    assert relay_path["nodes"] == ["张三", "外围账户B", "李四"]
    assert relay_path["priority_score"] > 0
    assert relay_path["priority_reason"]
    assert relay_path["path_explainability"]["evidence_template"]["headline"] == "张三 → 外围账户B → 李四"
    assert relay_path["path_explainability"]["time_axis"][0]["source_file"] == "zhangsan.xlsx"
    assert cluster["path_explainability"]["evidence_template"]["supporting_refs"]["total"] >= 1
    assert results["analysis_metadata"]["fund_loops"]["truncated"] is False
    assert summary["外围节点数"] >= 1
    assert summary["关系簇数"] >= 1


def test_analyze_fund_penetration_enriches_cycles_with_scores_and_metadata():
    personal_data = {
        "张三": pd.DataFrame(
            [
                {"date": "2026-01-01", "income": 0, "expense": 120000, "counterparty": "外围账户B", "数据来源": "zhangsan.xlsx", "source_row_index": 101},
            ]
        ),
        "外围账户B": pd.DataFrame(
            [
                {"date": "2026-01-02", "income": 0, "expense": 120000, "counterparty": "外围账户C", "数据来源": "relay_b.xlsx", "source_row_index": 102},
            ]
        ),
        "外围账户C": pd.DataFrame(
            [
                {"date": "2026-01-03", "income": 0, "expense": 120000, "counterparty": "张三", "数据来源": "relay_c.xlsx", "source_row_index": 103},
            ]
        ),
    }

    results = fund_penetration.analyze_fund_penetration(
        personal_data=personal_data,
        company_data={},
        core_persons=["张三"],
        companies=[],
    )

    assert len(results["fund_cycles"]) == 1
    cycle = results["fund_cycles"][0]
    assert cycle["path"] == "张三 → 外围账户B → 外围账户C → 张三"
    assert cycle["total_amount"] == 120000
    assert cycle["risk_score"] >= 60
    assert cycle["confidence"] >= 0.6
    assert cycle["path_explainability"]["path_type"] == "fund_cycle"
    assert len(cycle["path_explainability"]["edge_segments"]) == 3
    assert cycle["path_explainability"]["bottleneck_edge"]["amount"] == 120000
    assert cycle["path_explainability"]["edge_segments"][0]["transaction_refs"][0]["source_row_index"] == 101
    assert cycle["path_explainability"]["edge_segments"][0]["transaction_refs_total"] == 1
    assert cycle["path_explainability"]["edge_segments"][0]["transaction_ref_sample_count"] == 1
    assert cycle["path_explainability"]["edge_segments"][0]["transaction_refs_returned"] == 1
    assert cycle["path_explainability"]["edge_segments"][0]["transaction_refs_truncated"] is False
    assert cycle["path_explainability"]["evidence_template"]["supporting_refs"]["returned"] == 3
    assert results["analysis_metadata"]["fund_cycles"]["returned_count"] == 1
    assert results["analysis_metadata"]["fund_cycles"]["truncated"] is False


def test_analyze_fund_penetration_returns_full_cycle_transaction_refs_when_under_cap():
    personal_data = {
        "张三": pd.DataFrame(
            [
                {"date": f"2026-01-{day:02d}", "income": 0, "expense": 20000, "counterparty": "外围账户B", "数据来源": "zhangsan.xlsx", "source_row_index": 200 + day}
                for day in range(1, 8)
            ]
        ),
        "外围账户B": pd.DataFrame(
            [
                {"date": "2026-01-08", "income": 0, "expense": 140000, "counterparty": "外围账户C", "数据来源": "relay_b.xlsx", "source_row_index": 301},
            ]
        ),
        "外围账户C": pd.DataFrame(
            [
                {"date": "2026-01-09", "income": 0, "expense": 140000, "counterparty": "张三", "数据来源": "relay_c.xlsx", "source_row_index": 302},
            ]
        ),
    }

    results = fund_penetration.analyze_fund_penetration(
        personal_data=personal_data,
        company_data={},
        core_persons=["张三"],
        companies=[],
    )

    cycle = results["fund_cycles"][0]
    first_segment = cycle["path_explainability"]["edge_segments"][0]

    assert first_segment["transaction_refs_total"] == 7
    assert first_segment["transaction_ref_sample_count"] == 7
    assert first_segment["transaction_refs_returned"] == 7
    assert first_segment["transaction_refs_truncated"] is False
    assert first_segment["transaction_refs_limit"] == 200
    assert len(first_segment["transaction_refs"]) == 7


def test_analyze_fund_penetration_truncates_cycle_transaction_refs_when_over_cap():
    personal_data = {
        "张三": pd.DataFrame(
            [
                {"date": f"2026-02-{(day % 28) + 1:02d}", "income": 0, "expense": 1000 + day, "counterparty": "外围账户B", "数据来源": "zhangsan.xlsx", "source_row_index": 3000 + day}
                for day in range(220)
            ]
        ),
        "外围账户B": pd.DataFrame(
            [
                {"date": "2026-03-01", "income": 0, "expense": 300000, "counterparty": "外围账户C", "数据来源": "relay_b.xlsx", "source_row_index": 4001},
            ]
        ),
        "外围账户C": pd.DataFrame(
            [
                {"date": "2026-03-02", "income": 0, "expense": 300000, "counterparty": "张三", "数据来源": "relay_c.xlsx", "source_row_index": 4002},
            ]
        ),
    }

    results = fund_penetration.analyze_fund_penetration(
        personal_data=personal_data,
        company_data={},
        core_persons=["张三"],
        companies=[],
    )

    first_segment = results["fund_cycles"][0]["path_explainability"]["edge_segments"][0]

    assert first_segment["transaction_refs_total"] == 220
    assert first_segment["transaction_refs_returned"] == 200
    assert first_segment["transaction_ref_sample_count"] == 200
    assert first_segment["transaction_refs_truncated"] is True
    assert first_segment["transaction_refs_limit"] == 200
    assert len(first_segment["transaction_refs"]) == 200
