#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asset_extractor 精准房产目录扫描回归测试。"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from asset_extractor import extract_precise_property_info


def test_extract_precise_property_info_merges_multiple_directories(tmp_path, monkeypatch):
    first_dir = tmp_path / "案件A" / "自然资源部精准查询（定向查询）"
    second_dir = tmp_path / "案件B" / "自然资源部精准查询（定向查询）"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)

    first_file = first_dir / "张三_310101199001010011_自然资源部（精准查询）.xlsx"
    second_file = second_dir / "李四_310101199001010022_自然资源部（精准查询）.xlsx"
    duplicate_file = second_dir / "张三_310101199001010011_自然资源部（精准查询）_补充.xlsx"

    for path in (first_file, second_file, duplicate_file):
        path.write_text("", encoding="utf-8")

    def fake_parse(file_path: str):
        filename = os.path.basename(file_path)
        if "李四" in filename:
            return [
                {
                    "owner_name": "李四",
                    "owner_id": "310101199001010022",
                    "location": "测试路2号201室",
                    "property_number": "P-2",
                }
            ]
        return [
            {
                "owner_name": "张三",
                "owner_id": "310101199001010011",
                "location": "测试路1号101室",
                "property_number": "P-1",
            }
        ]

    monkeypatch.setattr("asset_extractor.parse_precise_property_file", fake_parse)

    result = extract_precise_property_info(str(tmp_path))

    assert sorted(result.keys()) == ["310101199001010011", "310101199001010022"]
    assert len(result["310101199001010011"]) == 1
    assert result["310101199001010011"][0]["location"] == "测试路1号101室"
    assert len(result["310101199001010022"]) == 1
    assert result["310101199001010022"][0]["location"] == "测试路2号201室"


def test_extract_precise_property_info_respects_person_filter_across_directories(
    tmp_path, monkeypatch
):
    first_dir = tmp_path / "案件A" / "自然资源部精准查询（定向查询）"
    second_dir = tmp_path / "案件B" / "自然资源部精准查询（定向查询）"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)

    first_file = first_dir / "张三_310101199001010011_自然资源部（精准查询）.xlsx"
    second_file = second_dir / "李四_310101199001010022_自然资源部（精准查询）.xlsx"

    for path in (first_file, second_file):
        path.write_text("", encoding="utf-8")

    def fake_parse(file_path: str):
        filename = os.path.basename(file_path)
        owner_name = "张三" if "张三" in filename else "李四"
        owner_id = "310101199001010011" if "张三" in filename else "310101199001010022"
        return [
            {
                "owner_name": owner_name,
                "owner_id": owner_id,
                "location": f"{owner_name}名下房产",
                "property_number": owner_id,
            }
        ]

    monkeypatch.setattr("asset_extractor.parse_precise_property_file", fake_parse)

    result = extract_precise_property_info(
        str(tmp_path), person_id="310101199001010022"
    )

    assert list(result.keys()) == ["310101199001010022"]
    assert result["310101199001010022"][0]["owner_name"] == "李四"


def test_extract_precise_property_info_backfills_transaction_price_from_national_index(
    tmp_path, monkeypatch
):
    precise_dir = tmp_path / "案件A" / "自然资源部精准查询（定向查询）"
    precise_dir.mkdir(parents=True)
    precise_file = precise_dir / "张三_310101199001010011_自然资源部（精准查询）.xlsx"
    precise_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "asset_extractor.parse_precise_property_file",
        lambda *_: [
            {
                "owner_name": "张三",
                "owner_id": "310101199001010011",
                "location": "测试路1号101室",
                "property_number": "P-1",
                "transaction_price": 0.0,
                "transaction_price_wan": 0.0,
            }
        ],
    )
    monkeypatch.setattr(
        "asset_extractor._build_national_property_price_index",
        lambda *_args, **_kwargs: {
            "310101199001010011": {
                "id:P-1": 347.18,
            }
        },
    )

    result = extract_precise_property_info(str(tmp_path))

    assert result["310101199001010011"][0]["transaction_price_wan"] == 347.18
    assert result["310101199001010011"][0]["交易金额"] == "347.18万"
