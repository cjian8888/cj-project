# 待解决问题

## 2026-02-04 发现的问题

### 问题1：家庭成员关系配置在报告中未生效

**优先级**: 高

**问题描述**:
用户在前端配置了家庭成员关系（例如：施灵设为"本人"），但生成的HTML报告中，所有成员都显示为"家庭成员"，没有正确显示配置的关系（本人、配偶、子女等）。

**根本原因**:
`investigation_report_builder.py` 中的 `_build_member_details_dict()` 方法调用 `_infer_relation_from_config(name)` 时，没有传递 `anchor` 参数（核查对象/本人），导致无法正确判断谁是"本人"，所有人都被推断为默认的"家庭成员"。

**问题代码位置**:
- `investigation_report_builder.py` 第524-531行（调用处）
- `investigation_report_builder.py` 第656-667行（方法定义）

**影响范围**:
- HTML报告的"家庭单元概览"章节
- HTML报告的"家庭成员资金分析"章节标题
- 成员排序顺序（本人在前，其他成员在后）

**修复状态**: ⏳ 已修改代码，待验证

**修复内容**:
1. 修改 `_build_member_details_dict(self, name: str)` 为 `_build_member_details_dict(self, name: str, anchor: str = None)`
2. 修改调用处，传递 `unit.anchor` 参数：`self._build_member_details_dict(m, unit.anchor)`

---

### 问题2：后端HTML报告缺少"四、涉案公司分析"章节

**优先级**: 中

**问题描述**:
后端 `_render_report_to_html()` 函数生成的HTML报告中缺少"四、涉案公司分析"章节，导致通过后端API生成的HTML报告不完整。

**根本原因**:
`api_server.py` 第2410-2556行的 `_render_report_to_html()` 函数中，没有渲染 `company_reports` 或 `companies` 的部分。

**影响范围**:
- 后端API `/api/reports/generate` 生成的HTML报告（html格式）
- 前端使用旧API生成的HTML报告

**解决方案**:
当前工作流程已调整为：
1. 前端使用v3格式生成报告（前端渲染HTML，包含公司分析）
2. 前端通过 `/api/investigation-report/save-html` API将HTML保存到输出目录
3. 后端的html格式API（`/api/reports/generate`）暂时不修复，不再使用

---

## 2026-02-04 修复的问题

### 修复1：前端只显示2个txt文件

**问题描述**:
前端报告列表只显示 `报告目录清单.txt` 和 `核查结果分析报告.txt`，缺少7个专项报告文件。

**根本原因**:
`api_server.py` 的 `/api/reports` 端点只扫描根目录，不递归扫描子目录，导致 `专项报告/` 目录下的文件不被包含。

**修复内容**:
- 修改 `/api/reports` 端点，使用 `scan_directory()` 递归扫描所有子目录
- 在子目录中的文件，文件名格式为 `子目录/文件名`

**修复状态**: ✅ 已修复并验证

---

### 修复2：前端HTML报告"未知公司"问题

**问题描述**:
前端生成的HTML报告中，所有公司都显示为"未知公司"。

**根本原因**:
前端 `ReportBuilder.tsx` 的 `renderV3ReportToHtml()` 函数使用了 `report.companies`，但后端返回的字段名是 `companies`（没有company_reports）。

**修复内容**:
- 修改前端代码，从 `report.companies` 读取数据
- 添加数据转换逻辑，将后端返回的公司数据格式转换为前端渲染所需的格式

**修复状态**: ✅ 已修复，待用户重新生成报告验证

---

### 修复3：TXT报告年度工资为空

**问题描述**:
生成的TXT报告中，家庭年度工资收入表格为空，没有显示按年统计的工资数据。

**根本原因**:
`investigation_report_builder.py` 的 `_aggregate_family_yearly_salary()` 方法中，使用了错误的字段名 `yearly_salary`，实际字段名是 `yearlySalary`（驼峰式）。

**修复内容**:
- 修改 `_aggregate_family_yearly_salary()` 方法，使用 `yearlySalary.yearly` 而非 `yearly_salary.yearly`

**修复状态**: ✅ 已修复并验证，家庭年度工资表格正常显示2003-2024年数据

---

### 修复4：TXT报告字段名错误导致数据全为0

**问题描述**:
生成的TXT报告中，家庭总收入、家庭总支出、个人资金规模等数据全部显示为0.00万元。

**根本原因**:
`investigation_report_builder.py` 的 `generate_complete_txt_report()` 方法中，使用了错误的字段名 `totalInflow` 和 `totalOutflow`，实际字段名是 `totalIncome` 和 `totalExpense`（驼峰式）。

**修复内容**:
- 修改 `generate_complete_txt_report()` 方法，使用正确的驼峰式字段名：
  - `totalInflow` → `totalIncome`
  - `totalOutflow` → `totalExpense`
  - `totalBankBalance` → `wealthTotal`

**修复状态**: ✅ 已修复并验证，数据正常显示

---

### 修复5：HTML报告自动保存到输出目录

**需求**:
用户希望：
1. 前端配置家庭归集后，点击"生成报告"
2. 前端显示预览，可以下载
3. 输出目录同步生成同样的HTML报告

**实现方案**:
1. 后端添加 `/api/investigation-report/save-html` API端点，接收HTML内容并保存到 `output/analysis_results/` 目录
2. 前端 `ReportBuilder.tsx` 修改 `generateReport()` 函数，在生成HTML后自动调用保存API

**修复状态**: ✅ 已修复并测试

---

## 技术债务

### 1. 后端HTML报告功能不完整
- `_render_report_to_html()` 函数缺少公司分析章节
- 建议：如果需要使用后端HTML格式，需要完整重写

### 2. 家庭成员关系配置的一致性问题
- 分析阶段使用自动识别的关系
- 报告阶段使用用户配置的关系
- 建议：提供两种模式（自动/手动）或让用户配置后重新分析

### 3. 前后端类型定义不一致
- 前端和后端都有 `AnalysisUnit` 类型定义，但字段不完全一致
- 建议：统一类型定义，共享schema
