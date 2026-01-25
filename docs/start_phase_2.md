# Phase 2 启动文档

## 背景

我正在进行穿云审计系统的初查报告引擎开发工作。

## 已完成阶段

- ✅ Phase -1: 归集配置（G-01 ~ G-05）
- ✅ Phase 0: 样本报告与数据契约（R-01 ~ R-07）

## 当前阶段

**Phase 2: 报告结构重构**

## Phase 0 完成成果

1. **3个完整的HTML样本报告**：
   - `/templates/sample_report_personal.html` - 个人核查部分（8个Section）
   - `/templates/sample_report_company.html` - 公司核查专章
   - `/templates/sample_report_complete.html` - 完整报告（黄金标准）

2. **数据需求清单**：
   - `/docs/report_data_requirements.md` - 定义了100+个字段

3. **更新的Schema**：
   - `report_schema.py` - 新增PropertyInfo、VehicleInfo、AnalysisUnit等数据类

## Phase 2 任务目标

实现三段式报告结构：**前言 + 分析单元循环体 + 综合研判**

### 任务清单（S-01 ~ S-06）

| 任务ID | 任务名称 | 状态 | 预估时间 |
|--------|---------|------|---------|
| S-01 | 重构为三段式全局结构 | [/] 进行中 | 3h |
| S-02 | 实现前言章节 | ⬜ 待开始 | 1h |
| S-03 | 实现个人单元循环体(8个Section) | ⬜ 待开始 | 6h |
| S-04 | 实现公司深度核查专章 | ⬜ 待开始 | 4h |
| S-05 | 实现公司间交叉分析专章 | ⬜ 待开始 | 3h |
| S-06 | 实现全局尾部综合研判 | ⬜ 待开始 | 2h |

## 当前进度

### S-01: 重构为三段式全局结构

**已完成**：
- [x] 分析现有 `investigation_report_builder.py`（1783行）
- [x] 发现已有归集配置功能（G-05）
- [x] 确认需要基于样本报告重构

**进行中**：
- [/] 设计三段式结构的主函数

**待完成**：
- [ ] 实现报告骨架生成逻辑

## 关键设计原则

1. **数据复用铁律**：100% 复用 analysis_cache 数据，禁止读取原始 Excel
2. **对照样本报告**：所有输出必须与样本报告结构一致
3. **话术专业性**：使用样本报告中的专业话术
4. **规则引擎**：基于 If-Else 规则树，禁止使用 AI/LLM

## 现有代码分析

### 文件结构

`investigation_report_builder.py` 包含：
- `InvestigationReportBuilder` 类（主类）
- `build_complete_report()` - 旧接口（兼容性）
- `build_report_with_config()` - 新接口（G-05，按归集配置生成）
- `_build_analysis_unit_section()` - 构建分析单元章节
- `_aggregate_family_unit_data()` - 聚合家庭数据
- 其他辅助方法...

### 需要重构的部分

1. **新增三段式主函数**：
   ```python
   def build_report_v3(self, config: PrimaryTargetsConfig) -> Dict:
       """
       v3.0 三段式报告生成
       
       结构：
       1. 前言（章节〇）
       2. 分析单元循环体（个人核查 Section I-VIII）
       3. 公司深度核查专章
       4. 公司间交叉分析专章
       5. 综合研判（章节Z）
       """
   ```

2. **实现各个章节生成函数**：
   - `_build_preface()` - 前言
   - `_build_person_section_1()` - Section I: 身份与履历
   - `_build_person_section_2()` - Section II: 资产存量分析
   - ... (共8个Section)
   - `_build_company_deep_analysis()` - 公司深度核查
   - `_build_inter_company_analysis()` - 公司间交叉分析
   - `_build_comprehensive_conclusion()` - 综合研判

## 下一步工作

1. **完成 S-01**：
   - 在 `investigation_report_builder.py` 中新增 `build_report_v3()` 方法
   - 实现三段式骨架结构
   - 测试骨架生成

2. **执行 S-02**：
   - 实现前言章节生成
   - 包括：核查依据、数据范围、核查对象列表

3. **执行 S-03**：
   - 逐个实现8个Section的生成函数
   - 严格对照样本报告确保输出一致

## 参考文档

- **执行计划**：`.agent/workflows/report-engine-plan.md`
- **样本报告**：`/templates/sample_report_complete.html`
- **数据需求**：`/docs/report_data_requirements.md`
- **数据契约**：`/docs/report_data_contract.md`
- **Schema定义**：`report_schema.py`

## 开始工作

请按照以下步骤继续：

1. 查看 `task.md` 了解当前任务进度
2. 查看样本报告 `/templates/sample_report_complete.html` 了解目标输出
3. 在 `investigation_report_builder.py` 中实现 `build_report_v3()` 方法
4. 完成每个子任务后更新 `task.md`
5. 完成整个阶段后创建交接文档

---

**创建时间**: 2026-01-23 20:30  
**当前Token使用**: 122k/200k  
**建议**: 在新对话中继续，避免token溢出
