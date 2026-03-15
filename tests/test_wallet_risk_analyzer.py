import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import wallet_risk_analyzer


def _build_wallet_data(subject_name: str, subject_id: str, matched_to_core: bool) -> dict:
    subject = {
        "subjectId": subject_id,
        "subjectName": subject_name,
        "matchedToCore": matched_to_core,
        "platforms": {
            "alipay": {"topCounterparties": []},
            "wechat": {"topCounterparties": []},
        },
    }
    return {
        "available": True,
        "subjects": [subject],
        "subjectsById": {subject_id: subject},
        "subjectsByName": {subject_name: subject},
        "alerts": [],
    }


def test_enhance_wallet_alerts_adds_transaction_level_rules():
    wallet_data = _build_wallet_data("待确认主体", "340825200107190410", False)
    artifact_details = {
        "alipayTransactionRows": [
            {
                "subjectId": "340825200107190410",
                "subjectName": "待确认主体",
                "isEffective": True,
                "direction": "收入",
                "createdAt": f"2025-08-01 09:{index:02d}:00",
                "amountYuan": 5000.0,
                "counterpartyName": f"付款人{index}",
                "itemName": "拆分收入",
            }
            for index in range(8)
        ]
        + [
            {
                "subjectId": "340825200107190410",
                "subjectName": "待确认主体",
                "isEffective": True,
                "direction": "收入",
                "createdAt": "2025-08-02 10:00:00",
                "amountYuan": 120000.0,
                "counterpartyName": "渠道A",
                "itemName": "大额收入",
            },
            {
                "subjectId": "340825200107190410",
                "subjectName": "待确认主体",
                "isEffective": True,
                "direction": "支出",
                "createdAt": "2025-08-03 09:00:00",
                "amountYuan": 90000.0,
                "counterpartyName": "外部账户",
                "itemName": "次日转出",
            },
        ],
        "tenpayTransactionRows": [
            {
                "subjectId": "340825200107190410",
                "subjectName": "待确认主体",
                "direction": "入",
                "transactionTime": f"2025-08-04 23:{index:02d}:00",
                "amountYuan": 7000.0,
                "counterpartyName": f"夜间对手{index}",
                "remark1": "夜间收入",
            }
            for index in range(8)
        ],
    }

    enhanced = wallet_risk_analyzer.enhance_wallet_alerts(
        wallet_data=wallet_data,
        artifact_details=artifact_details,
        cleaned_data={},
    )

    alerts_by_type = {item["alert_type"]: item for item in enhanced["alerts"]}

    assert "wallet_split_collection" in alerts_by_type
    assert "wallet_quick_pass_through" in alerts_by_type
    assert "wallet_night_activity" in alerts_by_type
    assert alerts_by_type["wallet_split_collection"]["rule_code"] == "WALLET-SPLIT-COLLECTION-001"
    assert alerts_by_type["wallet_quick_pass_through"]["rule_code"] == "WALLET-QUICK-PASS-THROUGH-001"
    assert alerts_by_type["wallet_night_activity"]["rule_code"] == "WALLET-NIGHT-ACTIVITY-001"
    assert alerts_by_type["wallet_quick_pass_through"]["risk_score"] >= 55
    assert alerts_by_type["wallet_night_activity"]["confidence"] >= 0.7


def test_enhance_wallet_alerts_adds_bank_linkage_rules():
    wallet_data = _build_wallet_data("张三", "110101199001010011", True)
    artifact_details = {
        "alipayTransactionRows": [
            {
                "subjectId": "110101199001010011",
                "subjectName": "张三",
                "isEffective": True,
                "direction": "收入",
                "createdAt": "2025-08-01 10:00:00",
                "amountYuan": 20000.0,
                "counterpartyName": "李四",
                "itemName": "往来收入",
            },
            {
                "subjectId": "110101199001010011",
                "subjectName": "张三",
                "isEffective": True,
                "direction": "收入",
                "createdAt": "2025-08-02 10:00:00",
                "amountYuan": 20000.0,
                "counterpartyName": "李四",
                "itemName": "往来收入",
            },
            {
                "subjectId": "110101199001010011",
                "subjectName": "张三",
                "isEffective": True,
                "direction": "收入",
                "createdAt": "2025-08-03 10:00:00",
                "amountYuan": 20000.0,
                "counterpartyName": "李四",
                "itemName": "往来收入",
            },
            {
                "subjectId": "110101199001010011",
                "subjectName": "张三",
                "isEffective": True,
                "direction": "收入",
                "createdAt": "2025-08-05 10:00:00",
                "amountYuan": 120000.0,
                "counterpartyName": "渠道甲",
                "itemName": "大额流入",
            },
        ],
        "tenpayTransactionRows": [],
    }
    cleaned_data = {
        "张三": pd.DataFrame(
            [
                {"日期": "2025-08-01", "收入": 0, "支出": 20000, "交易对手": "李四", "交易摘要": "转账"},
                {"日期": "2025-08-02", "收入": 0, "支出": 20000, "交易对手": "李四", "交易摘要": "转账"},
                {"日期": "2025-08-03", "收入": 0, "支出": 20000, "交易对手": "李四", "交易摘要": "转账"},
                {"日期": "2025-08-05", "收入": 0, "支出": 50000, "交易对手": "公司A", "交易摘要": "对外付款"},
                {"日期": "2025-08-06", "收入": 0, "支出": 50000, "交易对手": "公司B", "交易摘要": "对外付款"},
            ]
        )
    }

    enhanced = wallet_risk_analyzer.enhance_wallet_alerts(
        wallet_data=wallet_data,
        artifact_details=artifact_details,
        cleaned_data=cleaned_data,
        id_to_name_map={"110101199001010011": "张三"},
    )

    alerts_by_type = {item["alert_type"]: item for item in enhanced["alerts"]}

    assert "wallet_bank_counterparty_overlap" in alerts_by_type
    assert "wallet_bank_quick_outflow" in alerts_by_type
    assert alerts_by_type["wallet_bank_counterparty_overlap"]["counterparty"] == "李四"
    assert alerts_by_type["wallet_bank_counterparty_overlap"]["rule_code"] == "WALLET-BANK-COUNTERPARTY-001"
    assert alerts_by_type["wallet_bank_quick_outflow"]["rule_code"] == "WALLET-BANK-OUTFLOW-001"
    assert alerts_by_type["wallet_bank_quick_outflow"]["risk_score"] >= 60
    assert "银行支出" in alerts_by_type["wallet_bank_quick_outflow"]["evidence_summary"]


def test_enhance_wallet_alerts_tolerates_missing_bank_text_columns():
    wallet_data = _build_wallet_data("张三", "110101199001010011", True)
    artifact_details = {
        "alipayTransactionRows": [
            {
                "subjectId": "110101199001010011",
                "subjectName": "张三",
                "isEffective": True,
                "direction": "收入",
                "createdAt": "2025-08-05 10:00:00",
                "amountYuan": 120000.0,
                "counterpartyName": "渠道甲",
                "itemName": "大额流入",
            }
        ],
        "tenpayTransactionRows": [],
    }
    cleaned_data = {
        "张三": pd.DataFrame(
            [
                {"日期": "2025-08-05", "收入": 0, "支出": 50000},
                {"日期": "2025-08-06", "收入": 0, "支出": 40000},
            ]
        )
    }

    enhanced = wallet_risk_analyzer.enhance_wallet_alerts(
        wallet_data=wallet_data,
        artifact_details=artifact_details,
        cleaned_data=cleaned_data,
    )

    assert isinstance(enhanced["alerts"], list)
