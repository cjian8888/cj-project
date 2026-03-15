from pathlib import Path

import pandas as pd

import wallet_data_extractor


def test_extract_wallet_data_merges_alipay_wechat_and_tenpay(tmp_path: Path):
    root = tmp_path / "data" / "补充数据" / "电子钱包" / "批次_20260315"
    root.mkdir(parents=True, exist_ok=True)

    alipay_reg = root / "768219766_注册信息_20260205111012（公开）.xlsx"
    pd.DataFrame(
        [
            {
                "用户ID": "2088412846264555",
                "登录邮箱": "",
                "登录手机": "15900578144",
                "账户名称": "马尚德",
                "证件类型": "身份证",
                "证件号": "372922197910112912",
                "可用余额": 0,
                "绑定手机": "15900578144",
                "注册时间": "2014-05-25",
                "绑定银行卡": "借记卡:COMM:6222600110033606521;借记卡:CCB:6217001210012077689;",
                "关联账户": "",
                "备注": "",
                "对应的协查数据": "372922197910112912",
            }
        ]
    ).to_excel(alipay_reg, index=False)

    alipay_tx = root / "768219766_账户明细d2_20260206160408_part1（公开）.xlsx"
    with pd.ExcelWriter(alipay_tx) as writer:
        pd.DataFrame(
            [
                {
                    "交易号": "A1",
                    "商户订单号": "O1",
                    "交易创建时间": "2025-08-09 08:50:20",
                    "付款时间": "2025-08-09 08:50:21",
                    "最近修改时间": "2025-08-09 08:50:30",
                    "交易来源地": "支付宝网站",
                    "类型": "即时到账交易",
                    "用户信息": "2088412846264555(马尚德)",
                    "交易对方信息": "2088002020170361(王云)",
                    "消费名称": "测试收入",
                    "金额（元）": 100.0,
                    "收/支": "收入",
                    "交易状态": "交易成功结束",
                    "支付方式": "",
                    "清算流水号": "",
                    "备注": "",
                    "对应的协查数据": "372922197910112912",
                },
                {
                    "交易号": "A2",
                    "商户订单号": "O2",
                    "交易创建时间": "2025-08-10 08:50:20",
                    "付款时间": "2025-08-10 08:50:21",
                    "最近修改时间": "2025-08-10 08:50:30",
                    "交易来源地": "支付宝网站",
                    "类型": "即时到账交易",
                    "用户信息": "2088412846264555(马尚德)",
                    "交易对方信息": "2088002020170361(王云)",
                    "消费名称": "测试支出",
                    "金额（元）": 50.0,
                    "收/支": "支出",
                    "交易状态": "交易成功结束",
                    "支付方式": "",
                    "清算流水号": "",
                    "备注": "",
                    "对应的协查数据": "372922197910112912",
                },
            ]
        ).to_excel(writer, sheet_name="372922197910112912", index=False)

    tenpay_dir = root / "L-1770258514959-8-masd100%" / "TP6855cf4fd" / "IDCARD" / "372922197910112912" / "big_lu_1"
    tenpay_dir.mkdir(parents=True, exist_ok=True)
    (tenpay_dir / "TenpayRegInfo（公开）.txt").write_text(
        "\n".join(
            [
                "账户状态\t账号\t注册姓名\t注册时间\t注册身份证号\t绑定手机\t绑定状态\t开户行信息\t银行账号",
                "正常\tbig_lu_1\t马尚德\t2015-01-28 02:11:13\t372922197910112912\t15900578144\t绑定确认(正常)\t交行借记卡快捷支付\t6222600110033606521",
            ]
        ),
        encoding="utf-8",
    )

    tenpay_trade_dir = root / "L-1770258514959-8-masd100%" / "TP5d4b6f6488" / "IDCARD" / "372922197910112912" / "big_lu_1"
    tenpay_trade_dir.mkdir(parents=True, exist_ok=True)
    (tenpay_trade_dir / "TenpayTrades（公开）.txt").write_text(
        "\n".join(
            [
                "用户ID\t交易单号\t大单号\t用户侧账号名称\t借贷类型\t交易业务类型\t交易用途类型\t交易时间\t交易金额(分)\t账户余额(分)\t用户银行卡号\t用户侧网银联单号\t网联/银联\t第三方账户名称\t对手方ID\t对手侧账户名称\t对手方银行卡号\t对手侧银行名称\t对手侧网银联单号\t网联/银联\t基金公司信息\t间联/非间联交易\t第三方账户名称\t对手方接收时间\t对手方接收金额(分)\t备注1\t备注2",
                "big_lu_1\tT1\tD1\t马尚德\t出\t余额支付\t转账\t2025-08-11 08:00:00\t10000\t0\t6222600110033606521\t\t网联\t\twxid_test\t王云\t\t\t\t\t\t非间连交易\t\t2025-08-11 08:00:10\t10000\t微信转账\t测试",
                "big_lu_1\tT2\tD2\t马尚德\t入\t余额支付\t转账\t2025-08-12 09:00:00\t5000\t0\t6222600110033606521\t\t网联\t\twxid_test\t王云\t\t\t\t\t\t非间连交易\t\t2025-08-12 09:00:10\t5000\t微信转账\t测试",
            ]
        ),
        encoding="utf-8",
    )

    wx_dir = root / "L-1770258514959-8-masd100%" / "WX544675d857" / "IPHONE" / "15900578144"
    wx_dir.mkdir(parents=True, exist_ok=True)
    (wx_dir / "regInfobasicInfo（公开）.txt").write_text(
        "\n".join(
            [
                "微信号: wxid_1gpmsukrzuam22",
                "别名: big_lu_1",
                "昵称: 大陆",
                "当前绑定手机号: 15900578144",
                "注册时间: 2018-09-28 12:44:02",
            ]
        ),
        encoding="utf-8",
    )

    wx_login_dir = root / "L-1770258514959-8-masd100%" / "WX7c469f4c56" / "IPHONE" / "15900578144"
    wx_login_dir.mkdir(parents=True, exist_ok=True)
    (wx_login_dir / "WX登录轨迹（公开）.txt").write_text(
        "\n".join(
            [
                "登录日志：",
                "\t时间\tIP",
                "\t2026-01-27 11:53:50 +0800 CST\t240e:46d:bf00:eb1:a427:d4ff:fefc:66e9",
            ]
        ),
        encoding="utf-8",
    )

    wallet_data = wallet_data_extractor.extract_wallet_data(
        str(tmp_path / "data"),
        known_person_names={"马尚德"},
    )

    assert wallet_data["available"] is True
    assert wallet_data["summary"]["subjectCount"] == 1
    assert wallet_data["summary"]["alipayTransactionCount"] == 2
    assert wallet_data["summary"]["tenpayTransactionCount"] == 2
    assert wallet_data["summary"]["wechatAccountCount"] == 1
    assert wallet_data["summary"]["loginEventCount"] == 1

    subject = wallet_data["subjects"][0]
    assert subject["subjectName"] == "马尚德"
    assert subject["matchedToCore"] is True
    assert subject["platforms"]["alipay"]["accountCount"] == 1
    assert subject["platforms"]["wechat"]["wechatAccountCount"] == 1
    assert subject["platforms"]["wechat"]["tenpayAccountCount"] == 1
    assert subject["crossSignals"]["phoneOverlapCount"] >= 1
    assert subject["crossSignals"]["aliasMatchCount"] >= 1
    assert subject["platforms"]["wechat"]["latestLoginAt"] == "2026-01-27 11:53:50"


def test_build_wallet_alerts_covers_large_scale_and_unmatched_account():
    wallet_data = {
        "subjects": [
            {
                "subjectId": "372922197910112912",
                "subjectName": "马尚德",
                "matchedToCore": True,
                "signals": ["存在 2 张跨平台绑定银行卡重叠"],
                "crossSignals": {
                    "matchBasis": ["身份证号匹配", "手机号匹配"],
                    "bankCardOverlapCount": 2,
                    "aliasMatchCount": 1,
                },
                "platforms": {
                    "alipay": {
                        "accountCount": 1,
                        "transactionCount": 80,
                        "incomeTotalYuan": 180000.0,
                        "expenseTotalYuan": 170000.0,
                        "topCounterparties": [
                            {"name": "王云", "count": 8, "totalAmountYuan": 82000.0},
                        ],
                    },
                    "wechat": {
                        "wechatAccountCount": 1,
                        "tenpayAccountCount": 1,
                        "tenpayTransactionCount": 30,
                        "incomeTotalYuan": 150000.0,
                        "expenseTotalYuan": 120000.0,
                        "loginEventCount": 12,
                        "latestLoginAt": "2026-01-27 11:53:50",
                        "topCounterparties": [
                            {"name": "测试商户", "count": 6, "totalAmountYuan": 56000.0},
                        ],
                    },
                },
            }
        ],
        "unmatchedWechatAccounts": [
            {
                "phone": "15900578144",
                "nickname": "大陆",
                "latestLoginAt": "2026-01-27 11:53:50",
            }
        ],
    }

    alerts = wallet_data_extractor.build_wallet_alerts(wallet_data)
    alert_types = {item["alert_type"] for item in alerts}

    assert "wallet_large_scale" in alert_types
    assert "wallet_unmatched_account" in alert_types
    assert any(item["risk_level"] in {"high", "medium"} for item in alerts)
    assert all("risk_score" in item for item in alerts)
    assert all("confidence" in item for item in alerts)
    assert all("rule_code" in item for item in alerts)
    assert all("evidence_summary" in item for item in alerts)


def test_build_wallet_alerts_covers_unmapped_large_scale_subject():
    wallet_data = {
        "subjects": [
            {
                "subjectId": "340825200107190410",
                "subjectName": "待确认主体",
                "matchedToCore": False,
                "signals": [],
                "crossSignals": {
                    "matchBasis": [],
                    "bankCardOverlapCount": 0,
                    "aliasMatchCount": 0,
                },
                "platforms": {
                    "alipay": {
                        "accountCount": 1,
                        "transactionCount": 180,
                        "incomeTotalYuan": 620000.0,
                        "expenseTotalYuan": 180000.0,
                        "topCounterparties": [],
                    },
                    "wechat": {
                        "wechatAccountCount": 1,
                        "tenpayAccountCount": 1,
                        "tenpayTransactionCount": 90,
                        "incomeTotalYuan": 160000.0,
                        "expenseTotalYuan": 70000.0,
                        "loginEventCount": 8,
                        "latestLoginAt": "2026-01-27 11:53:50",
                        "topCounterparties": [],
                    },
                },
            }
        ],
        "unmatchedWechatAccounts": [],
    }

    alerts = wallet_data_extractor.build_wallet_alerts(wallet_data)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["alert_type"] == "wallet_unmapped_large_scale"
    assert alert["risk_level"] == "high"
    assert alert["rule_code"] == "WALLET-UNMAPPED-LARGE-001"
    assert alert["risk_score"] >= 70
    assert 0.55 <= alert["confidence"] <= 0.96
    assert "未命中主链" in alert["evidence_summary"]
