import os
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import wallet_data_extractor
import wallet_report_builder


def _create_wallet_sample(root: Path) -> Path:
    data_root = root / "data" / "补充数据" / "电子钱包" / "批次_20260315"
    data_root.mkdir(parents=True, exist_ok=True)

    alipay_reg = data_root / "768219766_注册信息_20260205111012（公开）.xlsx"
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

    alipay_tx = data_root / "768219766_账户明细d2_20260206160408_part1（公开）.xlsx"
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
                    "消费名称": "=169273935992423088=",
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

    tenpay_reg_dir = (
        data_root
        / "L-1770258514959-8-masd100%"
        / "TP6855cf4fd"
        / "IDCARD"
        / "372922197910112912"
        / "big_lu_1"
    )
    tenpay_reg_dir.mkdir(parents=True, exist_ok=True)
    (tenpay_reg_dir / "TenpayRegInfo（公开）.txt").write_text(
        "\n".join(
            [
                "账户状态\t账号\t注册姓名\t注册时间\t注册身份证号\t绑定手机\t绑定状态\t开户行信息\t银行账号",
                "正常\tbig_lu_1\t马尚德\t2015-01-28 02:11:13\t372922197910112912\t15900578144\t绑定确认(正常)\t交行借记卡快捷支付\t6222600110033606521",
            ]
        ),
        encoding="utf-8",
    )

    tenpay_trade_dir = (
        data_root
        / "L-1770258514959-8-masd100%"
        / "TP5d4b6f6488"
        / "IDCARD"
        / "372922197910112912"
        / "big_lu_1"
    )
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

    wx_dir = data_root / "L-1770258514959-8-masd100%" / "WX544675d857" / "IPHONE" / "15900578144"
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

    wx_login_dir = data_root / "L-1770258514959-8-masd100%" / "WX7c469f4c56" / "IPHONE" / "15900578144"
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

    return root / "data"


def test_extract_wallet_artifact_bundle_contains_normalized_rows(tmp_path: Path):
    data_root = _create_wallet_sample(tmp_path)

    bundle = wallet_data_extractor.extract_wallet_artifact_bundle(
        str(data_root),
        known_person_names={"马尚德"},
    )

    wallet_data = bundle["walletData"]
    artifacts = bundle["artifacts"]

    assert wallet_data["available"] is True
    assert wallet_data["summary"]["subjectCount"] == 1
    assert len(artifacts["sourceFiles"]) == 6
    assert all(not os.path.isabs(item["relativePath"]) for item in artifacts["sourceFiles"])
    assert all(not os.path.isabs(item["filePath"]) for item in artifacts["sourceFiles"])
    assert len(artifacts["alipayRegistrationRows"]) == 1
    assert len(artifacts["alipayTransactionRows"]) == 2
    assert all(
        not os.path.isabs(row["sourceFile"]) for row in artifacts["alipayTransactionRows"]
    )
    assert len(artifacts["wechatRegistrationRows"]) == 1
    assert len(artifacts["wechatLoginRows"]) == 1
    assert len(artifacts["tenpayRegistrationRows"]) == 1
    assert len(artifacts["tenpayTransactionRows"]) == 2
    assert artifacts["wechatRegistrationRows"][0]["matchStatus"] == "matched"
    assert artifacts["tenpayTransactionRows"][0]["counterpartyName"] == "王云"


def test_generate_wallet_artifacts_outputs_txt_and_excel(tmp_path: Path):
    data_root = _create_wallet_sample(tmp_path)
    bundle = wallet_data_extractor.extract_wallet_artifact_bundle(
        str(data_root),
        known_person_names={"马尚德"},
    )
    bundle["walletData"]["alerts"] = [
        {
            "risk_level": "high",
            "alert_type": "wallet_large_scale",
            "person": "马尚德",
            "counterparty": "电子钱包总体",
            "date": "2025-08-12 09:00:00",
            "amount": 350000.0,
            "description": "马尚德电子钱包交易规模较大。",
            "risk_reason": "建议优先核查。",
        }
    ]
    bundle["walletData"]["unmatchedWechatAccounts"] = [
        {
            "phone": "13900000000",
            "wxid": "wxid_unmatched",
            "alias": "tmp_alias",
            "nickname": "待确认账号",
            "registeredAt": "2024-01-01 00:00:00",
            "latestLoginAt": "2026-01-01 12:00:00",
            "loginEventCount": 3,
        }
    ]
    bundle["walletData"]["summary"]["unmatchedWechatCount"] = 1

    output_dir = tmp_path / "output" / "analysis_results"
    paths = wallet_report_builder.generate_wallet_artifacts(
        str(output_dir),
        bundle["walletData"],
        bundle["artifacts"],
    )

    txt_path = Path(paths["txt"])
    excel_path = Path(paths["excel"])
    focus_txt_path = Path(paths["focus_txt"])
    assert txt_path.exists()
    assert excel_path.exists()
    assert focus_txt_path.exists()

    txt_content = txt_path.read_text(encoding="utf-8")
    focus_txt_content = focus_txt_path.read_text(encoding="utf-8")
    assert "电子钱包补充分析报告" in txt_content
    assert "马尚德" in txt_content
    assert "来源文件清单" in txt_content
    assert "电子钱包重点核查清单" in focus_txt_content
    assert "高风险电子钱包预警" in focus_txt_content
    assert "待确认账号" in focus_txt_content

    workbook = pd.ExcelFile(excel_path)
    assert workbook.sheet_names == [
        "样本概览",
        "来源文件清单",
        "主体汇总",
        "支付宝实名账户",
        "支付宝交易明细",
        "微信注册信息",
        "微信登录轨迹",
        "财付通实名账户",
        "财付通交易明细",
        "电子钱包预警",
        "未归并微信账号",
    ]

    source_df = pd.read_excel(excel_path, sheet_name="来源文件清单")
    subject_df = pd.read_excel(excel_path, sheet_name="主体汇总")
    wx_reg_df = pd.read_excel(excel_path, sheet_name="微信注册信息")
    alipay_tx_df = pd.read_excel(excel_path, sheet_name="支付宝交易明细")
    tenpay_tx_df = pd.read_excel(excel_path, sheet_name="财付通交易明细")

    assert len(source_df) == 6
    assert "原始路径" not in source_df.columns
    assert all(not os.path.isabs(str(value)) for value in source_df["相对路径"].tolist())
    assert subject_df.iloc[0]["主体姓名"] == "马尚德"
    assert wx_reg_df.iloc[0]["匹配状态"] == "已归并"
    assert all(not os.path.isabs(str(value)) for value in alipay_tx_df["来源文件"].tolist())
    assert len(tenpay_tx_df) == 2

    workbook_obj = load_workbook(excel_path, data_only=False)
    alipay_sheet = workbook_obj["支付宝交易明细"]
    assert alipay_sheet["O2"].data_type != "f"
    assert alipay_sheet["U2"].value == bundle["artifacts"]["alipayTransactionRows"][0]["sourceFile"]
