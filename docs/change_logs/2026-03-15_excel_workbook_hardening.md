# 2026-03-15 Excel 底稿整改说明

## 背景

本次整改聚焦 `output/analysis_results/资金核查底稿.xlsx`。该文件定位为后续人工核查、复盘追溯、报告对账的正式工作底稿，要求同时满足以下目标：

- 能承接当前分析链路的关键结果，不出现数据断层
- 表名、列名尽量中文化，便于审计人员直接阅读
- 保留必要的来源追溯信息，支持回查原始记录
- 消除 `nan` / `None` / `NaT` 等脏值，避免影响人工判断
- 与当前 HTML / TXT / 图谱等分析产物保持一致口径

## 本次确认的问题

- Excel 底稿对部分新分析链路继承不完整，存在专题 sheet 缺失
- 多条分析结果存在历史别名差异，导致部分数据未稳定落表
- 部分字段保留英文枚举或原始编码，人工可读性不足
- 身份证号等长数字字段存在被 Excel 误转科学计数法的风险
- 来源文件、来源行号在部分专题表中缺失，追溯能力不足
- 整列空值字段会制造噪音，影响人工核查效率

## 整改内容

### 1. 补齐底稿承接范围

新增或补齐以下分析结果的 Excel 承接：

- `家族关系图谱`
- `家庭总资产汇总`
- `成员间转账明细`
- `穿透-过账通道`
- `时序-资金突变`
- `时序-固定延迟`
- `异常收入-来源不明`
- `异常收入-同源多次`
- `异常收入-大额转入`
- `异常收入-大额单笔`
- `异常收入-疑似分期受贿`
- `关联分析-汇总`
- `同行分析-航班`
- `同行分析-铁路`
- `同行分析-资金关联`
- `同住宿分析-明细`
- `同住宿分析-资金关联`
- `快递联系-明细`
- `快递联系-高频地址`
- `快递联系-资金关联`

### 2. 修正数据继承与兼容

- 在 `api_server.py` 中补传 `family_tree`
- 在 `api_server.py` 中补传 `derived_data["timeSeries"]`
- 在 `api_server.py` 中补传 `derived_data["family_tree"]`
- 在 `report_generator.py` 中兼容 `snake_case`、`camelCase` 和历史别名
- 覆盖典型兼容键：
  - `pass_through_channels / passthrough_channels`
  - `large_individual_income / large_personal_income`
  - `unknown_source_income / unknown_source`
  - `same_source_multi / multi_source`
  - `potential_bribe_installment / suspected_bribery`
  - `sudden_changes / 突变事件`
  - `delayed_transfers / 延迟转账`

### 3. 提升正式成品质控

- 统一清洗 `nan`、`None`、`NaT`
- 风险等级统一中文化
- 节点类型统一中文化
- 时序异常类型统一中文化
- 日期、时间格式统一
- 身份证号按文本写入，避免科学计数法
- 增加冻结首行、自动筛选、列宽优化
- 对整列全空字段自动剔除，降低噪音

### 4. 补强追溯能力

在各专题 sheet 中统一补充来源追溯字段：

- `来源文件`
- `来源行号`

## 影响文件

- `report_generator.py`
- `api_server.py`
- `tests/test_report_generator.py`

## 正式产物状态

当前正式底稿位置：

- `output/analysis_results/资金核查底稿.xlsx`

复核结果：

- sheet 数量为 `40`
- 已包含 `关联分析-汇总`
- `家族关系图谱` 中身份证号按文本落盘
- `时序-资金突变` 中异常类型已中文化为 `收入突增`
- `第三方支付-收入`、`异常收入-汇总` 等表已清洗 `nan` / `None`

## 验证结果

已完成验证：

- `pytest -q tests/test_report_generator.py tests/test_api_server_config_flow.py` = `21 passed`
- 抽查正式底稿：
  - `关联分析-汇总` 存在且有数据
  - `家族关系图谱` 关键身份证号字段保持文本
  - `时序-资金突变` 风险等级与异常类型已中文化
  - `第三方支付-收入` 保留来源追溯字段
  - `异常收入-汇总` 未再出现脏值字面量

## 结论

本轮 Excel 底稿已完成从“开发侧导出物”向“正式人工核查底稿”的收口整改。当前未发现新的阻断问题，可以作为本阶段交付物之一继续使用。
