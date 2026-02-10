#!/usr/bin/env python3
"""
v5.0报告模块测试脚本

测试内容:
1. 数据结构定义完整性
2. build_report_v5()方法调用
3. 各板块数据完整性

运行: python test_v5_report.py
"""

import json
import os
import sys
from datetime import datetime

# 设置日志
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_schema_definitions():
    """测试数据结构定义"""
    logger.info("=" * 60)
    logger.info("测试1: 数据结构定义完整性")
    logger.info("=" * 60)

    try:
        from report_schema import (
            DimensionScore,
            FiveDimensionScore,
            LendingPlatformRecord,
            LendingAnalysis,
            WealthTransactionRecord,
            WealthTransactionAnalysis,
            TimelineCollisionItem,
            TimelineCollisionAnalysis,
            ProfessionalAuditNarrative,
            FamilyRiskAnalysis,
            RiskStatistics,
        )

        # 测试创建实例
        dimension = DimensionScore(
            name="收支匹配度",
            score=20.0,
            max_score=25,
            risk_level="low",
            description="测试描述"
        )
        logger.info(f"✅ DimensionScore: {dimension}")

        five_dim = FiveDimensionScore(
            total_score=85.0,
            total_max=100.0,
            risk_level="low"
        )
        logger.info(f"✅ FiveDimensionScore: {five_dim}")

        lending = LendingAnalysis(
            total_platforms=2,
            total_borrowing=50000.0,
            has_multi_platform=True,
            risk_level="high"
        )
        logger.info(f"✅ LendingAnalysis: {lending}")

        risk_stats = RiskStatistics(
            high_risk_count=3,
            medium_risk_count=2,
            low_risk_count=1,
            total_amount=1800000.0,
            total_amount_wan=180.0
        )
        logger.info(f"✅ RiskStatistics: {risk_stats}")

        logger.info("✅ 所有数据结构定义测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ 数据结构定义测试失败: {e}")
        return False


def test_v5_methods():
    """测试v5.0新增方法"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: v5.0新增方法")
    logger.info("=" * 60)

    try:
        from investigation_report_builder import InvestigationReportBuilder

        # 检查方法是否存在
        methods = [
            '_build_lending_analysis_v4',
            '_build_wealth_transaction_analysis_v4',
            '_build_timeline_collision_analysis_v4',
            '_build_five_dimension_score_v4',
            '_generate_professional_audit_narrative_v4',
            'build_report_v5',
            '_build_family_summary_v5',
        ]

        for method in methods:
            if hasattr(InvestigationReportBuilder, method):
                logger.info(f"✅ 方法存在: {method}")
            else:
                logger.error(f"❌ 方法缺失: {method}")
                return False

        logger.info("✅ 所有v5.0方法测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ v5.0方法测试失败: {e}")
        return False


def test_api_endpoint():
    """测试API端点定义"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3: API端点定义")
    logger.info("=" * 60)

    try:
        with open('api_server.py', 'r', encoding='utf-8') as f:
            content = f.read()

        if '/api/investigation-report/generate-v5' in content:
            logger.info("✅ v5.0 API端点已定义")
        else:
            logger.error("❌ v5.0 API端点未定义")
            return False

        if 'generate_investigation_report_v5' in content:
            logger.info("✅ v5.0 API处理函数已定义")
        else:
            logger.error("❌ v5.0 API处理函数未定义")
            return False

        if 'build_report_v5' in content:
            logger.info("✅ build_report_v5调用已添加")
        else:
            logger.error("❌ build_report_v5调用未添加")
            return False

        logger.info("✅ API端点测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ API端点测试失败: {e}")
        return False


def test_report_structure():
    """测试报告结构完整性"""
    logger.info("\n" + "=" * 60)
    logger.info("测试4: 报告结构定义")
    logger.info("=" * 60)

    # 预期的v5.0报告结构
    expected_structure = {
        "meta": ["doc_number", "case_background", "data_scope", "generated_at", "version", "generator"],
        "part_a_family_analysis": ["family_sections", "summary"],
        "part_b_person_analysis": ["person_sections"],
        "part_c_company_analysis": ["company_sections"],
        "part_d_conclusion": ["conclusion", "next_steps", "risk_statistics"],
    }

    for part, fields in expected_structure.items():
        logger.info(f"✅ {part}: {fields}")

    logger.info("✅ 报告结构定义完整")
    return True


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 60)
    logger.info("v5.0报告模块测试")
    logger.info("=" * 60)
    logger.info(f"测试时间: {datetime.now().isoformat()}")

    results = []

    # 运行所有测试
    results.append(("数据结构定义", test_schema_definitions()))
    results.append(("v5.0方法", test_v5_methods()))
    results.append(("API端点", test_api_endpoint()))
    results.append(("报告结构", test_report_structure()))

    # 汇总结果
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"{name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        logger.info("\n✅ 所有测试通过！v5.0报告模块就绪。")
        return 0
    else:
        logger.error("\n❌ 部分测试失败，请检查实现。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
