---
name: architecture_walkthrough
description: 执行“资金穿透审计系统”的全程序架构走读，包含核心计算、多源数据解析及API服务层检查。
---

# Skill: Capital Audit System Architecture Walkthrough

## Description
执行“资金穿透审计系统”的全程序架构走读。
本技能基于项目当前的完整开发状态（特别是 Phase 1-8 功能补全后），模拟【纪检审计专业人员】（验收方）与【资深高级程序规划师】（执行方）的交互。
采用“后台静默走读”模式，通过静态代码分析，执行【检查-更改-验证】循环，确保系统架构符合“铁律”且数据流向正确。

## Triggers
- "运行架构走读"
- "检查系统完整性"
- "verify system architecture"
- "full code walkthrough"

## Roles
1.  **Auditor (纪检审计师)**: 
    - **职责**：基于审计业务逻辑验收功能。关注数据流是否合规、指标是否遗漏、外部数据是否完整集成。
    - **语调**：严厉、专业、怀疑主义。
    - **关注点**：数据清洗的纯净度、资金计算的准确性、14类外部数据的完整归集。
2.  **Architect (资深规划师)**:
    - **职责**：根据 Auditor 的发现，直接定位并修改 Python/TS 代码。
    - **语调**：高效、技术导向、解决问题。

## The Walkthrough Protocol (The Loop)
Agent 必须按顺序执行以下 Checkpoints。
**循环规则**：
- 在任意 Checkpoint 发现不合规（Fail），立即停止检查 -> 执行代码修复 -> **强制重置**回 Checkpoint 1 重新开始。
- 只有当所有 Checkpoint 均为 Pass 时，才允许输出“🏆 架构验收通过”。

### Checkpoint 1: 数据清洗与流向铁律 (Data Flow Iron Law)
**Target**: `backend/services/data_cleaner.py`
**Audit Rules**:
1.  **物理隔离**: 必须严格区分 `data/` (原始) 和 `output/cleaned_data/` (清洗后)。禁止后续分析模块直接读取 `data/`。
2.  **双轨输出**: 清洗过程必须同时生成可读的 Excel (`.xlsx`) 和高性能 Parquet (`.parquet`)。
3.  **标准化**: 是否调用了 `standardize_bank_fields`？是否识别了核心字段 `is_cash`（现金标志）和 `opponent_name`（对手方）？
4.  **去重**: 是否包含 `deduplicate_transactions` 逻辑以防止重复流水？

### Checkpoint 2: 核心资金画像与疑点 (Core Profiling)
**Target**: `financial_profiler.py`, `income_analyzer.py`, `loan_analyzer.py`, `suspicion_detector.py`
**Audit Rules**:
1.  **工资核算**: `financial_profiler` 是否计算了 `yearly_salary` 和 `salary_ratio`？(<50% 必须标记异常)。
2.  **大额甄别**: `income_analyzer` 是否包含 `_detect_large_single_income`（单笔大额）和 `classify_income_sources`（来源分类）？
3.  **借贷分析**: `loan_analyzer` 是否具备 `without_interest`（无息借款）和 `bidirectional`（双向往来）的识别逻辑？
4.  **现金伴随**: `suspicion_detector` 是否实现了 `detect_cash_time_collision`（存取款时间碰撞）算法？

### Checkpoint 3: 全维外部数据集成 (External Data Integration)
**Target**: `api_server.py`, `*_extractor.py` (Phase 6-8 Modules)
**Audit Rules**:
1.  **全量覆盖**: 检查 `api_server.py` 是否集成了全部 3 个层级的外部数据：
    - **P0 基础级**: 央行账户、反洗钱、企业工商、征信、银行卡信息。
    - **P1 资产级**: 机动车、理财、证券、不动产、统一信用码。
    - **P2 轨迹级**: 保险、出入境、旅馆住宿、同住/违章、铁路、航班。
2.  **异常隔离**: 每个 Extractor 的调用必须被 `try-except` 包裹，防止单源数据缺失导致整体崩溃。
3.  **数据归仓**: 解析结果必须正确写入 `profiles[id]` 的对应字段（如 `immigration_records`, `flight_records`），禁止数据 "悬空"。

### Checkpoint 4: 服务层边界与缓存 (Service Boundary)
**Target**: `backend/services/report_service.py`, `backend/api_server.py`
**Audit Rules**:
1.  **只读缓存**: `report_service` 必须只读取 `analysis_cache` 中的 JSON 结果，严禁在报告生成阶段重新触发计算逻辑。
2.  **接口透传**: API 是否将 `salary_ratio`、`risk_labels`、`family_structure` 等关键审计指标完整透传给前端？

### Checkpoint 5: 环境适应性 (Configuration)
**Target**: `backend/config.py`
**Audit Rules**:
1.  **路径安全**: `output_dir` 等路径是否使用了 `os.path.abspath` 强制转为绝对路径？（防止 Windows/Mac 路径差异导致的 404）。
2.  **关键词配置**: 检查 `INVESTIGATION_UNIT_KEYWORDS`（调查单位）和 `BANK_ACCOUNT_EXCLUDE_KEYWORDS`（虚拟账户排除）是否已配置。

### Checkpoint 6: 户主优先原则 (Householder Priority)
**Target**: `investigation_report_builder.py`, `family_analyzer.py`
**背景**: 2026-01-25 发现滕雳未被正确识别为施灵家庭成员，原因是代码仅使用 `extended_relatives`（推断关系）而非 `family_units_v2`（真实户籍数据）。
**Audit Rules**:
1.  **户籍数据优先**: `_build_families_from_cache()` 必须**优先**使用 `family_units_v2`（来自公安部同户人数据），只有未覆盖的人员才回退到 `extended_relatives` 推断。
2.  **关系获取优先级**: `_infer_relation_from_members()` 必须**优先**从 `family_units_v2.member_details` 获取真实"与户主关系"（如"妻"、"子"），而非仅使用推断关系。
3.  **日志可追溯**: 家庭分组时必须输出 `[户主优先原则]` 日志，记录每个家庭的 anchor 和成员列表。
4.  **数据完整性**: `family_units_v2` 必须包含 `anchor/householder`、`members`、`member_details`（含 name、relation）字段。

## Execution Instructions
1.  **Initialize**: Load context from `docs/work_plan_master.md` and `docs/final_summary.md`.
2.  **Start Loop**: Begin at Checkpoint 1.
3.  **Inspect**: Read the actual code of the target files using `view_file`.
4.  **Evaluate**:
    - **Pass**: Log "✅ **Checkpoint X Passed**: [Evidence/Reason]". Proceed to X+1.
    - **Fail**: 
        - Log "❌ **Checkpoint X Failed**: [Detailed Error]".
        - **ACT**: Switch to Architect role, propose/apply the fix immediately.
        - **RESTART**: Log "🔄 **Resetting Walkthrough** to Checkpoint 1...".
5.  **Finish**: When Checkpoint 6 is Passed, output: "🏆 **资金穿透审计系统 - 架构一致性校验完成。Ready for Deployment.**"

## Constraints
- **NO Browser Interaction**: Code analysis only.
- **Strict Matching**: Verify function existence and call sites.
- **Phase 8 Awareness**: Pay special attention to the newly added P2 extractors in Checkpoint 3.
- **Householder Priority**: Checkpoint 6 是防止家庭成员识别错误的关键检查点，必须严格验证。

