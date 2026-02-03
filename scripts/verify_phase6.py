#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 6 & 7 缓存验证脚本"""

import json
import os

cache_path = "output/analysis_results_cache.json"

if not os.path.exists(cache_path):
    print(f"❌ 缓存文件不存在: {cache_path}")
    exit(1)

with open(cache_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 50)
print("Phase 6 & 7 缓存字段验证")
print("=" * 50)

phase6_fields = [
    ("pbocAccounts", "6.1 人民银行银行账户"),
    ("amlData", "6.2 人民银行反洗钱"),
    ("companyRegistry", "6.3 市场监管总局企业登记"),
    ("creditData", "6.4 征信数据"),
    ("bankAccountInfo", "6.5 银行业金融机构账户")
]

phase7_fields = [
    ("vehicleData", "7.1 公安部机动车"),
    ("wealthProductData", "7.2 银行理财产品"),
    ("securitiesData", "7.3 证券信息"),
    ("precisePropertyData", "7.4 精准房产查询"),
    ("creditCodeData", "7.5 统一社会信用代码")
]

all_present = True

print("\n--- Phase 6: P0 级 ---")
for field, description in phase6_fields:
    value = data.get(field, None)
    if value is not None:
        count = len(value)
        status = "✅"
        print(f"{status} {description}: {count} 条记录")
    else:
        status = "❌"
        print(f"{status} {description}: 字段不存在")
        all_present = False

print("\n--- Phase 7: P1 级 ---")
for field, description in phase7_fields:
    value = data.get(field, None)
    if value is not None:
        count = len(value)
        status = "✅"
        print(f"{status} {description}: {count} 条记录")
    else:
        status = "❌"
        print(f"{status} {description}: 字段不存在")
        all_present = False

phase8_fields = [
    ("insuranceData", "8.1 保险信息"),
    ("immigrationData", "8.2 出入境记录"),
    ("hotelData", "8.3 旅馆住宿"),
    ("cohabitationData", "8.4 同住址/同车违章"),
    ("railwayData", "8.5 铁路票面信息")
]

print("\n--- Phase 8: P2 级 ---")
for field, description in phase8_fields:
    value = data.get(field, None)
    if value is not None:
        if isinstance(value, dict) and "coaddress" in value:  # 8.4 特殊处理
            count = f"{len(value.get('coaddress', {}))} + {len(value.get('coviolation', {}))}"
        else:
            count = len(value)
        status = "✅"
        print(f"{status} {description}: {count} 条记录")
    else:
        status = "❌"
        print(f"{status} {description}: 字段不存在")
        all_present = False

print("\n" + "=" * 50)
if all_present:
    print("✅ Phase 6 & 7 & 8 集成验证通过!")
else:
    print("❌ 部分字段缺失")
