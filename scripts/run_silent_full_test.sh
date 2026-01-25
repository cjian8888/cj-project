#!/bin/bash
# 后台静默运行全量程序测试脚本
# 用于循环运行程序并记录所有输出

set -e  # 遇到错误立即退出

# 配置
PROJECT_DIR="/Users/chenjian/Desktop/Code/cj-project"
LOG_DIR="${PROJECT_DIR}/logs/silent_test"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/silent_test_${TIMESTAMP}.log"
ERROR_LOG="${LOG_DIR}/silent_test_errors_${TIMESTAMP}.log"
TEST_RESULTS="${LOG_DIR}/test_results_${TIMESTAMP}.json"

# 创建日志目录
mkdir -p "${LOG_DIR}"

# 初始化测试结果JSON
echo "{
  \"test_runs\": [],
  \"start_time\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",
  \"total_runs\": 0,
  \"success_count\": 0,
  \"error_count\": 0
}" > "${TEST_RESULTS}"

# 记录日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" | tee -a "${ERROR_LOG}"
}

# 运行测试函数
run_tests() {
    local run_number=$1
    log "========================================"
    log "开始第 ${run_number} 次运行"
    log "========================================"

    local run_start=$(date +%s)
    local run_errors=0
    local run_warnings=0
    local run_info=""

    # 1. 运行单元测试（不调用浏览器）
    log "[步骤 1/3] 运行单元测试..."
    cd "${PROJECT_DIR}"
    if python3 -m pytest tests/ -v --tb=short --no-header -q 2>&1 | tee -a "${LOG_FILE}"; then
        log "[步骤 1/3] 单元测试通过"
    else
        log_error "[步骤 1/3] 单元测试失败"
        ((run_errors++))
        run_info="${run_info}|单元测试失败"
    fi

    # 2. 运行主程序分析（后台静默模式）
    log "[步骤 2/3] 运行主程序分析..."
    cd "${PROJECT_DIR}"
    
    # 创建临时配置文件用于静默运行
    cat > /tmp/silent_analysis_config.json << EOF
{
  "inputDirectory": "./data",
  "outputDirectory": "./output",
  "cashThreshold": 50000,
  "timeWindow": 48,
  "modules": {
    "profileAnalysis": true,
    "suspicionDetection": true,
    "assetAnalysis": true,
    "dataValidation": true,
    "fundPenetration": true,
    "relatedParty": true,
    "multiSourceCorrelation": true,
    "loanAnalysis": true,
    "incomeAnalysis": true,
    "flowVisualization": true,
    "mlAnalysis": true,
    "timeSeriesAnalysis": true,
    "clueAggregation": true
  }
}
EOF

    # 使用 Python 直接调用分析函数（不启动服务器）
    python3 << 'PYTHON_SCRIPT' 2>&1 | tee -a "${LOG_FILE}"
import sys
import logging
import json
from datetime import datetime
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 导入分析模块
try:
    import config
    import file_categorizer
    import data_cleaner
    import data_extractor
    import financial_profiler
    import suspicion_detector
    import report_generator
    import family_analyzer
    import asset_analyzer
    import data_validator
    import fund_penetration
    import related_party_analyzer
    import multi_source_correlator
    import loan_analyzer
    import income_analyzer
    import flow_visualizer
    import ml_analyzer
    import time_series_analyzer
    import clue_aggregator
    import behavioral_profiler
    import pboc_account_extractor
    import aml_analyzer
    import company_info_extractor
    import credit_report_extractor
    import bank_account_info_extractor
    import vehicle_extractor
    import wealth_product_extractor
    import securities_extractor
    import insurance_extractor
    import immigration_extractor
    import hotel_extractor
    import cohabitation_extractor
    import railway_extractor
    import flight_extractor
    import asset_extractor
except ImportError as e:
    logger.error(f"导入模块失败: {e}")
    sys.exit(1)

# 读取配置
with open('/tmp/silent_analysis_config.json', 'r', encoding='utf-8') as f:
    analysis_config = json.load(f)

data_dir = analysis_config["inputDirectory"]
output_dir = analysis_config["outputDirectory"]
config.LARGE_CASH_THRESHOLD = analysis_config["cashThreshold"]

logger.info("=" * 60)
logger.info("开始静默分析")
logger.info("=" * 60)

try:
    # 阶段 1: 扫描文件
    logger.info("[1/10] 扫描数据目录...")
    categorized_files = file_categorizer.categorize_files(data_dir)
    persons = list(categorized_files['persons'].keys())
    companies = list(categorized_files['companies'].keys())
    logger.info(f"发现 {len(persons)} 个个人, {len(companies)} 个企业")
    logger.info("✓ 阶段 1 完成")

    # 阶段 2: 数据清洗
    logger.info("[2/10] 数据清洗与标准化...")
    cleaned_data = {}
    
    # 创建输出目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(f"{output_dir}/cleaned_data/个人").mkdir(parents=True, exist_ok=True)
    Path(f"{output_dir}/cleaned_data/公司").mkdir(parents=True, exist_ok=True)
    Path(f"{output_dir}/analysis_results").mkdir(parents=True, exist_ok=True)
    
    # 清洗个人数据
    for p in persons:
        p_files = categorized_files['persons'].get(p, [])
        if p_files:
            df, _ = data_cleaner.clean_and_merge_files(p_files, p)
            if df is not None and not df.empty:
                cleaned_data[p] = df
                output_path = f"{output_dir}/cleaned_data/个人/{p}_合并流水.xlsx"
                data_cleaner.save_formatted_excel(df, output_path)
                logger.info(f"已保存清洗数据: {p}")
    
    # 清洗公司数据
    for c in companies:
        c_files = categorized_files['companies'].get(c, [])
        if c_files:
            df, _ = data_cleaner.clean_and_merge_files(c_files, c)
            if df is not None and not df.empty:
                cleaned_data[c] = df
                output_path = f"{output_dir}/cleaned_data/公司/{c}_合并流水.xlsx"
                data_cleaner.save_formatted_excel(df, output_path)
                logger.info(f"已保存清洗数据: {c}")

    logger.info(f"清洗完成，共 {len(cleaned_data)} 个实体数据")
    logger.info("✓ 阶段 2 完成")

    # 阶段 3: 线索提取
    logger.info("[3/10] 提取关联线索...")
    clue_persons, clue_companies = data_extractor.extract_all_clues(data_dir)
    all_persons = list(set(persons + clue_persons))
    all_companies = list(set(companies + clue_companies))
    logger.info(f"✓ 阶段 3 完成: 线索人员 {len(clue_persons)} 人, 线索公司 {len(clue_companies)} 家")

    # 阶段 4: 资金画像
    logger.info("[4/10] 执行资金画像分析...")
    profiles = {}
    id_to_name_map = {}
    logger.info(f"开始处理 {len(cleaned_data)} 个实体的资金画像...")
    
    for entity, df in cleaned_data.items():
        try:
            profiles[entity] = financial_profiler.generate_profile_report(df, entity)
            if entity in all_persons:
                try:
                    profiles[entity]['bank_accounts'] = financial_profiler.extract_bank_accounts(df)
                except Exception as e:
                    logger.warning(f"提取 {entity} 银行账户失败: {e}")
        except Exception as e:
            logger.warning(f"生成 {entity} 画像失败: {e}")
            import traceback
            logger.warning(f"详细错误: {traceback.format_exc()}")

    # 阶段 5: 疑点检测
    logger.info("[5/10] 检测可疑交易模式...")
    suspicions = suspicion_detector.run_all_detections(cleaned_data, all_persons, all_companies)
    logger.info(f"✓ 阶段 5 完成: 发现 {len(suspicions.get('direct_transfers', []))} 条直接往来")

    # 阶段 6: 高级分析
    logger.info("[6/10] 运行高级分析模块...")
    analysis_results = {}
    logger.info("开始高级分析...")

    # 借贷分析
    try:
        analysis_results["loan"] = loan_analyzer.analyze_loan_behaviors(cleaned_data, all_persons)
    except Exception as e:
        logger.warning(f"借贷分析失败: {e}")

    # 收入分析
    try:
        analysis_results["income"] = income_analyzer.detect_suspicious_income(cleaned_data, all_persons)
    except Exception as e:
        logger.warning(f"收入分析失败: {e}")

    # 关联方分析
    try:
        analysis_results["relatedParty"] = related_party_analyzer.analyze_related_party_flows(
            cleaned_data, all_persons
        )
    except Exception as e:
        logger.warning(f"关联方分析失败: {e}")

    # 多源数据碰撞
    try:
        analysis_results["correlation"] = multi_source_correlator.run_all_correlations(
            data_dir, cleaned_data, all_persons
        )
    except Exception as e:
        logger.warning(f"多源数据碰撞分析失败: {e}")

    # 时序分析
    try:
        analysis_results["timeSeries"] = time_series_analyzer.analyze_time_series(
            cleaned_data, all_persons
        )
    except Exception as e:
        logger.warning(f"时序分析失败: {e}")

    # 线索汇总
    try:
        analysis_results["aggregation"] = clue_aggregator.aggregate_all_results(
            all_persons, all_companies,
            penetration_results=None,
            ml_results=None,
            ts_results=analysis_results.get("timeSeries"),
            related_party_results=analysis_results.get("relatedParty"),
            loan_results=analysis_results.get("loan")
        )
    except Exception as e:
        logger.warning(f"线索汇总失败: {e}")

    # 家庭分析
    try:
        family_units_list = family_analyzer.build_family_units(all_persons, data_dir)
        family_tree = family_analyzer.build_family_tree(all_persons, data_dir)
        family_summary = family_analyzer.get_family_summary(family_tree)
        analysis_results["family_tree"] = family_tree
        analysis_results["family_units"] = family_summary
        analysis_results["family_relations"] = family_tree
        analysis_results["family_units_v2"] = family_units_list
        logger.info(f"家庭分析完成: {len(family_units_list)} 个家庭")
    except Exception as e:
        logger.warning(f"家庭分析失败: {e}")
        import traceback
        logger.warning(f"详细错误: {traceback.format_exc()}")

    # 外部数据解析 - P0
    logger.info("[7/10] 解析 P0 级外部数据源...")
    logger.info("开始 P0 数据解析...")
    try:
        pboc_accounts = pboc_account_extractor.extract_pboc_accounts(data_dir)
        analysis_results["pboc_accounts"] = pboc_accounts
        logger.info(f"人民银行账户解析完成: {len(pboc_accounts)} 个主体")
    except Exception as e:
        logger.warning(f"人民银行账户解析失败: {e}")

    try:
        aml_data = aml_analyzer.extract_aml_data(data_dir)
        aml_alerts = aml_analyzer.get_aml_alerts(data_dir)
        analysis_results["aml_data"] = aml_data
        if aml_alerts:
            suspicions["aml_alerts"] = aml_alerts
        logger.info(f"反洗钱数据解析完成: {len(aml_data)} 个主体, {len(aml_alerts)} 条预警")
    except Exception as e:
        logger.warning(f"反洗钱数据解析失败: {e}")

    try:
        company_info = company_info_extractor.extract_company_info(data_dir)
        analysis_results["company_info"] = company_info
        logger.info(f"企业登记信息解析完成: {len(company_info)} 个企业")
    except Exception as e:
        logger.warning(f"企业登记信息解析失败: {e}")

    try:
        credit_data = credit_report_extractor.extract_credit_data(data_dir)
        credit_alerts = credit_report_extractor.get_credit_alerts(data_dir)
        analysis_results["credit_data"] = credit_data
        if credit_alerts:
            suspicions["credit_alerts"] = credit_alerts
        logger.info(f"征信数据解析完成: {len(credit_data)} 个主体, {len(credit_alerts)} 条预警")
    except Exception as e:
        logger.warning(f"征信数据解析失败: {e}")

    try:
        bank_account_info = bank_account_info_extractor.extract_bank_account_info(data_dir)
        analysis_results["bank_account_info"] = bank_account_info
        logger.info(f"银行账户信息解析完成: {len(bank_account_info)} 个主体")
    except Exception as e:
        logger.warning(f"银行账户信息解析失败: {e}")

    # 外部数据解析 - P1
    logger.info("[8/10] 解析 P1 级外部数据源...")
    logger.info("开始 P1 数据解析...")
    try:
        vehicle_data = vehicle_extractor.extract_vehicle_data(data_dir)
        analysis_results["vehicle_data"] = vehicle_data
        logger.info(f"公安部机动车解析完成: {len(vehicle_data)} 个主体")
    except Exception as e:
        logger.warning(f"公安部机动车解析失败: {e}")

    try:
        wealth_product_data = wealth_product_extractor.extract_wealth_product_data(data_dir)
        analysis_results["wealth_product_data"] = wealth_product_data
        logger.info(f"银行理财产品解析完成: {len(wealth_product_data)} 个主体")
    except Exception as e:
        logger.warning(f"银行理财产品解析失败: {e}")

    try:
        securities_data = securities_extractor.extract_securities_data(data_dir)
        analysis_results["securities_data"] = securities_data
        logger.info(f"证券信息解析完成: {len(securities_data)} 个主体")
    except Exception as e:
        logger.warning(f"证券信息解析失败: {e}")

    try:
        precise_property_data = asset_extractor.extract_precise_property_info(data_dir)
        analysis_results["precise_property_data"] = precise_property_data
        logger.info(f"自然资源部精准查询解析完成: {len(precise_property_data)} 个主体")
    except Exception as e:
        logger.warning(f"自然资源部精准查询解析失败: {e}")

    # 外部数据解析 - P2
    logger.info("[9/10] 解析 P2 级外部数据源...")
    logger.info("开始 P2 数据解析...")
    try:
        insurance_data = insurance_extractor.extract_insurance_data(data_dir)
        analysis_results["insurance_data"] = insurance_data
        logger.info(f"保险信息解析完成: {len(insurance_data)} 个主体")
    except Exception as e:
        logger.warning(f"保险信息解析失败: {e}")

    try:
        immigration_data = immigration_extractor.extract_immigration_data(data_dir)
        analysis_results["immigration_data"] = immigration_data
        logger.info(f"公安部出入境记录解析完成: {len(immigration_data)} 个主体")
    except Exception as e:
        logger.warning(f"公安部出入境记录解析失败: {e}")

    try:
        hotel_data = hotel_extractor.extract_hotel_data(data_dir)
        cohabitation_analysis = hotel_extractor.analyze_cohabitation(data_dir)
        analysis_results["hotel_data"] = hotel_data
        analysis_results["hotel_cohabitation"] = cohabitation_analysis
        logger.info(f"公安部旅馆住宿解析完成: {len(hotel_data)} 个主体")
    except Exception as e:
        logger.warning(f"公安部旅馆住宿解析失败: {e}")

    try:
        coaddress_data = cohabitation_extractor.extract_coaddress_data(data_dir)
        coviolation_data = cohabitation_extractor.extract_coviolation_data(data_dir)
        relationship_graph = cohabitation_extractor.get_relationship_graph(data_dir)
        analysis_results["coaddress_data"] = coaddress_data
        analysis_results["coviolation_data"] = coviolation_data
        analysis_results["relationship_graph"] = relationship_graph
        logger.info(f"公安部同住址/同车违章解析完成: {len(coaddress_data)} + {len(coviolation_data)} 个主体")
    except Exception as e:
        logger.warning(f"公安部同住址/同车违章解析失败: {e}")

    try:
        railway_data = railway_extractor.extract_railway_data(data_dir)
        railway_timeline = railway_extractor.get_travel_timeline(data_dir)
        analysis_results["railway_data"] = railway_data
        analysis_results["railway_timeline"] = railway_timeline
        logger.info(f"铁路票面信息解析完成: {len(railway_data)} 个主体")
    except Exception as e:
        logger.warning(f"铁路票面信息解析失败: {e}")

    try:
        flight_data = flight_extractor.extract_flight_data(data_dir)
        flight_timeline = flight_extractor.get_flight_timeline(data_dir)
        analysis_results["flight_data"] = flight_data
        analysis_results["flight_timeline"] = flight_timeline
        logger.info(f"中航信航班进出港信息解析完成: {len(flight_data)} 个主体")
    except Exception as e:
        logger.warning(f"中航信航班进出港信息解析失败: {e}")

    # 阶段 7: 生成报告
    logger.info("[10/10] 生成分析报告...")
    logger.info("开始生成 Excel 报告...")
    try:
        report_generator.generate_excel_workbook(
            profiles, 
            suspicions, 
            f"{output_dir}/analysis_results/{config.OUTPUT_EXCEL_FILE}"
        )
        logger.info("Excel报告已生成")
    except Exception as e:
        logger.warning(f"生成Excel报告失败: {e}")
        import traceback
        logger.warning(f"详细错误: {traceback.format_exc()}")

    # 行为特征分析
    try:
        behavioral_results = behavioral_profiler.analyze_behavioral_patterns(cleaned_data, all_persons)
        sedimentation_results = behavioral_profiler.analyze_fund_sedimentation(cleaned_data, all_persons)
        behavioral_results['sedimentation'] = sedimentation_results
        analysis_results["behavioral"] = behavioral_results
        logger.info("行为特征分析完成")
    except Exception as e:
        logger.warning(f"行为特征分析失败: {e}")
        import traceback
        logger.warning(f"详细错误: {traceback.format_exc()}")

    # 机器学习分析
    try:
        ml_results = ml_analyzer.run_ml_analysis(cleaned_data, all_persons, all_companies)
        analysis_results["ml"] = ml_results
        logger.info("机器学习预测完成")
    except Exception as e:
        logger.warning(f"机器学习预测失败: {e}")
        import traceback
        logger.warning(f"详细错误: {traceback.format_exc()}")

    logger.info("=" * 60)
    logger.info("分析完成")
    logger.info("=" * 60)
    logger.info(f"处理人员: {len(all_persons)}")
    logger.info(f"处理公司: {len(all_companies)}")
    logger.info(f"生成画像: {len(profiles)}")
    logger.info(f"疑点检测: {len(suspicions.get('direct_transfers', []))} 条直接往来")
    logger.info("=" * 60)
    logger.info("所有分析阶段完成")
    logger.info("=" * 60)

except Exception as e:
    logger.error(f"分析过程中发生错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

PYTHON_SCRIPT

    if [ $? -eq 0 ]; then
        log "[步骤 2/3] 主程序分析完成"
    else
        log_error "[步骤 2/3] 主程序分析失败"
        ((run_errors++))
        run_info="${run_info}|主程序分析失败"
    fi

    # 3. 检查输出文件
    log "[步骤 3/3] 检查输出文件..."
    cd "${PROJECT_DIR}"
    
    local missing_files=0
    local expected_files=(
        "output/analysis_results/资金核查底稿.xlsx"
        "output/analysis_results/数据验证报告.txt"
    )
    
    for file in "${expected_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "缺失文件: $file"
            ((missing_files++))
            ((run_errors++))
        else
            log "文件存在: $file"
        fi
    done
    
    if [ $missing_files -eq 0 ]; then
        log "[步骤 3/3] 所有输出文件检查通过"
    else
        run_info="${run_info}|缺失${missing_files}个输出文件"
    fi

    # 计算运行时间
    local run_end=$(date +%s)
    local run_duration=$((run_end - run_start))
    
    # 更新测试结果
    local run_result="success"
    if [ $run_errors -gt 0 ]; then
        run_result="failed"
    fi
    
    # 确保 run_info 已初始化
    if [ -z "${run_info}" ]; then
        run_info="无错误"
    fi
    
    # 更新JSON结果
    python3 << PYTHON_UPDATE
import json
import sys
from datetime import datetime

test_results_file = "${TEST_RESULTS}"

with open(test_results_file, 'r', encoding='utf-8') as f:
    results = json.load(f)

# 使用 Python 处理时间戳（兼容 macOS）
run_start_ts = ${run_start}
run_end_ts = ${run_end}

run_data = {
    "run_number": ${run_number},
    "result": "${run_result}",
    "start_time": datetime.fromtimestamp(run_start_ts, datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
    "end_time": datetime.fromtimestamp(run_end_ts, datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
    "duration_seconds": ${run_duration},
    "errors": ${run_errors},
    "warnings": ${run_warnings},
    "info": "${run_info}"
}

results["test_runs"].append(run_data)
results["total_runs"] += 1
if run_result == "success":
    results["success_count"] += 1
else:
    results["error_count"] += 1

with open(test_results_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"第 ${run_number} 次运行结果已记录: ${run_result}")
PYTHON_UPDATE

    log "第 ${run_number} 次运行完成，耗时 ${run_duration} 秒"
    log "错误数: ${run_errors}, 警告数: ${run_warnings}"
    log ""
    
    return $run_errors
}

# 主循环
MAX_RUNS=3
CURRENT_RUN=0

log "========================================"
log "开始后台静默测试"
log "========================================"
log "最大运行次数: ${MAX_RUNS}"
log "日志文件: ${LOG_FILE}"
log "错误日志: ${ERROR_LOG}"
log "测试结果: ${TEST_RESULTS}"
log "========================================"
log ""

while [ $CURRENT_RUN -lt $MAX_RUNS ]; do
    CURRENT_RUN=$((CURRENT_RUN + 1))
    
    if ! run_tests $CURRENT_RUN; then
        log_error "第 ${CURRENT_RUN} 次运行发现错误"
    fi
    
    # 如果不是最后一次运行，等待一段时间
    if [ $CURRENT_RUN -lt $MAX_RUNS ]; then
        log "等待 5 秒后开始下一次运行..."
        sleep 5
    fi
done

# 生成最终报告
log "========================================"
log "所有测试运行完成"
log "========================================"

python3 << PYTHON_FINAL
import json
from datetime import datetime, timezone

test_results_file = "${TEST_RESULTS}"

with open(test_results_file, 'r', encoding='utf-8') as f:
    results = json.load(f)

results["end_time"] = datetime.now(timezone.utc).isoformat() + "Z"

# 统计问题
all_errors = []
all_warnings = []

for run in results["test_runs"]:
    if run["info"]:
        all_errors.append(f"运行{run['run_number']}: {run['info']}")

# 生成问题清单（防止除以零）
total_runs = results["total_runs"]
success_rate = "0.0%"
if total_runs > 0:
    success_rate = f"{(results['success_count'] / total_runs * 100):.1f}%"

problem_report = {
    "summary": {
        "total_runs": total_runs,
        "success_count": results["success_count"],
        "error_count": results["error_count"],
        "success_rate": success_rate
    },
    "problems": all_errors,
    "recommendations": []
}

# 生成改进建议
if results["error_count"] > 0:
    problem_report["recommendations"].append("存在运行错误，需要修复相关模块")
if results["success_count"] < results["total_runs"]:
    problem_report["recommendations"].append("部分运行失败，建议检查数据质量和模块兼容性")

# 保存问题报告
problem_report_file = "${LOG_DIR}/problem_report_${TIMESTAMP}.json"
with open(problem_report_file, 'w', encoding='utf-8') as f:
    json.dump(problem_report, f, ensure_ascii=False, indent=2)

print(f"问题报告已生成: {problem_report_file}")
print(f"总运行次数: {results['total_runs']}")
print(f"成功次数: {results['success_count']}")
print(f"失败次数: {results['error_count']}")
print(f"成功率: {problem_report['summary']['success_rate']}")

if all_errors:
    print("\n发现的问题:")
    for err in all_errors:
        print(f"  - {err}")

if problem_report["recommendations"]:
    print("\n改进建议:")
    for rec in problem_report["recommendations"]:
        print(f"  - {rec}")
PYTHON_FINAL

log ""
log "测试完成！"
log "详细日志: ${LOG_FILE}"
log "错误日志: ${ERROR_LOG}"
log "测试结果: ${TEST_RESULTS}"
