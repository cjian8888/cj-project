#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告配置文件 - 资金穿透与关联排查系统

【2026-01-27 修复】配置化硬编码的样式、文本和权重
"""

# ============================================================
# 报告样式配置
# ============================================================

REPORT_STYLES = {
    'font_family': '"SimSun", "Songti SC", serif',
    'primary_color': '#007bff',
    'warning_color': '#dc3545',
    'success_color': '#28a745',
    'info_color': '#17a2b8',
    'section_border': '1px solid #ddd',
    'family_section_bg': '#fcfcfc',
    'family_section_padding': '10px',
    'subsection_title_icon': '➤',
}

# ============================================================
# 报告文本配置
# ============================================================

REPORT_TEXT = {
    'family_asset_overview': '【家庭资产全貌】',
    'fund_scale': '资金规模',
    'income_structure': '收入结构',
    'cash_analysis': '现金分析',
    'risk_warning': '⚠ 预警',
    'fund_overview': '【资金概况】',
    'main_sources': '主要资金来源',
    'main_destinations': '主要资金去向',
    'private_public_transactions': '公私往来',
    'suspicious_benefits': '【疑似利益输送】',
    'suspected_hidden_assets': '【疑似隐形资产】',
    'main_issues_investigation': '四、主要疑点与核查建议',
    'data_source_label': '📍 数据来源',
}

# ============================================================
# 风险评分权重配置
# ============================================================

RISK_FACTORS_WEIGHTS = {
    'cash_timing': 0.15,       # 现金时序模式
    'large_amount': 0.20,       # 大额交易
    'frequency': 0.10,          # 频繁交易
    'direct_transfer': 0.20,     # 直接转账
    'hidden_assets': 0.15,       # 隐形资产
    'low_salary_ratio': 0.20,   # 低工资占比
    'weekend_transaction': 0.10, # 周末交易
    'holiday_transaction': 0.10, # 节假日交易
    'unknown_counterparty': 0.15, # 未知对手方
}

# ============================================================
# 去重配置
# ============================================================

DEDUP_CONFIG = {
    'time_tolerance_seconds': 300,    # 时间容差：5分钟
    'amount_tolerance': 0.01,        # 金额容差：0.01元
    'check_window_size': 20,         # 检查窗口：20条记录
    'large_amount_threshold': 50000, # 大额交易阈值：5万元
}

# ============================================================
# 数据质量配置
# ============================================================

DATA_QUALITY_CONFIG = {
    'max_file_size_mb': 100,         # 最大文件大小：100MB
    'max_pdf_size_mb': 50,           # 最大PDF大小：50MB
    'max_pdf_pages': 100,            # 最大PDF页数：100
    'invalid_date_handling': 'skip',   # 无效日期处理：skip/remove/keep
    'zero_amount_handling': 'warn',   # 零金额处理：warn/remove/keep
}
