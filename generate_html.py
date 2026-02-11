import logging
import asyncio
import sys
import json
from pathlib import Path

# 临时禁用文件日志处理器，避免PermissionError
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.FileHandler):
        root_logger.removeHandler(handler)
        handler.close()

# 配置简单日志到控制台
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main():
    """生成HTML报告的主函数"""
    print("=" * 80)
    print("生成HTML报告")
    print("=" * 80)
    print()

    # 导入模块
    from api_server import (
        AnalysisConfig,
        run_analysis_refactored,
        _render_report_to_html,
    )
    from investigation_report_builder import InvestigationReportBuilder
    from report_config.primary_targets_service import PrimaryTargetsService

    # 配置
    config = AnalysisConfig(
        inputDirectory="data",
        outputDirectory="output",
        cashThreshold=50000,
        modules=None,
    )

    # 运行分析
    print("开始分析...")
    results = run_analysis_refactored(config)

    print("分析完成")
    print()

    # 检查是否已有缓存的分析结果
    cache_files = list(Path("output").rglob("*.json"))
    print(f"找到 {len(cache_files)} 个缓存文件:")
    for f in cache_files:
        print(f"  - {f}")
    print()

    # 加载归集配置
    print("加载归集配置...")
    config_service = PrimaryTargetsService(data_dir="./data", output_dir="./output")
    primary_targets_config, msg, is_new = config_service.get_or_create_config()

    if primary_targets_config is None:
        print(f"  配置加载失败: {msg}")
        return None

    print(f"  配置加载完成: is_new={is_new}")
    print()

    # 准备 analysis_cache（修复键名不匹配问题）
    print("准备 analysis_cache...")
    analysis_cache = {
        "profiles": results.get("profiles", {}),
        "derived_data": results.get("analysisResults", {}),
        "suspicions": results.get("suspicions", {}),
        "graph_data": results.get("graphData", {}),  # graphData -> graph_data
        "metadata": {},  # 元数据可选
    }

    # 添加外部数据（从 externalData 中提取）
    external_data = results.get("externalData", {})
    if external_data:
        # P0 数据
        analysis_cache["precisePropertyData"] = external_data.get("p0", {}).get(
            "precise_property_data", {}
        )
        analysis_cache["vehicleData"] = external_data.get("p1", {}).get(
            "vehicle_data", {}
        )
        analysis_cache["wealthProductData"] = external_data.get("p1", {}).get(
            "wealth_product_data", {}
        )
        analysis_cache["securitiesData"] = external_data.get("p1", {}).get(
            "securities_data", {}
        )
        analysis_cache["creditData"] = external_data.get("p0", {}).get(
            "credit_data", {}
        )
        analysis_cache["amlData"] = external_data.get("p0", {}).get("aml_data", {})

        print(f"  外部数据统计:")
        print(f"    - 房产: {len(analysis_cache['precisePropertyData'])} 条")
        print(f"    - 车辆: {len(analysis_cache['vehicleData'])} 条")
        print(f"    - 理财: {len(analysis_cache['wealthProductData'])} 条")
        print(f"    - 证券: {len(analysis_cache['securitiesData'])} 条")
    print()

    # 构建报告
    print("构建报告...")
    try:
        builder = InvestigationReportBuilder(analysis_cache)
        report = builder.build_report_with_config(
            config=primary_targets_config if primary_targets_config else None,
            case_background="",
            data_scope="",
        )
        print(f"  报告构建完成")
        print(f"  报告类型: {type(report)}")
        print(f"  报告键: {list(report.keys()) if isinstance(report, dict) else 'N/A'}")
    except Exception as e:
        print(f"  ✗ 报告构建失败: {e}")
        import traceback

        traceback.print_exc()
        return None
    print()

    # 渲染为HTML
    print("渲染HTML...")
    html_content = _render_report_to_html(report)
    print(f"  HTML渲染完成, 长度: {len(html_content)} 字符")
    print()

    # 保存HTML
    html_path = Path("output/analysis_results/初查报告_v4.html")
    html_path.parent.mkdir(parents=True, exist_ok=True)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✓ HTML报告已保存: {html_path}")
    print(f"✓ 文件大小: {html_path.stat().st_size} 字节")
    print()

    # 展示HTML内容前500行
    print("=" * 80)
    print("HTML内容预览 (前500行)")
    print("=" * 80)
    print()

    lines = html_content.split("\n")
    preview_lines = lines[: min(500, len(lines))]

    for i, line in enumerate(preview_lines, 1):
        print(line)

    print()
    print("=" * 80)
    print(f"HTML总行数: {len(lines)}")
    print("=" * 80)

    return html_path


if __name__ == "__main__":
    html_path = asyncio.run(main())
    if html_path:
        print(f"\n✓ 成功生成HTML报告: {html_path}")
    else:
        print("\n✗ HTML报告生成失败")
        sys.exit(1)
