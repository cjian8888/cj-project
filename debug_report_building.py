#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试报告构建过程
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from investigation_report_builder import InvestigationReportBuilder

# 加载builder
builder = InvestigationReportBuilder({
    "profiles": json.load(open("./output/analysis_cache/profiles.json")),
    "derived_data": json.load(open("./output/analysis_cache/derived_data.json")),
    "suspicions": json.load(open("./output/analysis_cache/suspicions.json")),
    "metadata": json.load(open("./output/analysis_cache/metadata.json")),
})

# 测试施灵的数据
name = "施灵"
profile = builder.profiles.get(name, {})

print("=" * 80)
print(f"调试 {name} 的数据")
print("=" * 80)

print("\n【Profile中的yearlySalary】")
yearly_salary = profile.get("yearlySalary") or profile.get("yearly_salary", {})
print(f"  yearly_salary: {json.dumps(yearly_salary, ensure_ascii=False, indent=2)[:800]}")

print("\n【调用 _build_salary_income_v4】")
salary_result = builder._build_salary_income_v4(name, profile)
print(f"  yearly_breakdown: {salary_result.get('yearly_breakdown')}")
print(f"  total_wan: {salary_result.get('total_wan')}")
print(f"  narrative: {salary_result.get('narrative')}")

print("\n【调用 _build_personal_background】")
bg_result = builder._build_personal_background(name, profile)
print(f"  employer: {bg_result.get('employer')}")
print(f"  birth_place: {bg_result.get('birth_place')}")
