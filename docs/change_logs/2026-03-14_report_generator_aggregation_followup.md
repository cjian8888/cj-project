# 2026-03-14 report_generator 聚合导出收口

## 本轮目标

- 把 `report_generator.py` 剩余的老导出链路继续统一到 `aggregation` explainability
- 同步修正文档，避免计划文档与真实代码状态脱节

## 本次改动

### 1. `report_generator.py`

- `generate_word_report()` 新增可选入参：
  - `aggregator`
  - `derived_data`
- Word 结论页已与 TXT / HTML / Excel 统一复用 `_build_aggregation_overview()`
- Word 导出新增输出：
  - `【聚合排序】`
  - `【高风险实体】`
  - `【重点线索】`
  - 聚合排序识别出的重点核查对象
- 兼容回退逻辑保留：
  - 若无 `aggregation`，仍按旧口径回退到 `direct_transfers` / `hidden_assets`

### 2. `tests/test_report_generator.py`

- 新增 Word 回归测试
- 验证 Word 结论页优先输出聚合排序、高风险实体与重点线索

### 3. 计划文档同步

- `docs/plans/aml_engine_refactor_phase2.md`
  - 已把 `report_generator.py` 老导出链路统一标记为完成
- `docs/plans/aml_engine_refactor_master_plan.md`
  - 进度快照已同步到当前真实状态

## 涉及函数树

```text
report_generator.py
├── _build_aggregation_overview
└── generate_word_report

tests/test_report_generator.py
└── test_generate_word_report_prefers_aggregation_highlights
```

## 当前影响判断

- 前端输入界面：
  - 不变
- API 入参：
  - 不变
- 老导出链路：
  - Word 已与 TXT / HTML / Excel 一致优先消费聚合结果
- 兼容性：
  - 未移除旧字段
  - 无 `aggregation` 时仍可按旧逻辑生成报告

## 回归建议

- `python3 -m py_compile report_generator.py`
- `pytest -q tests/test_report_generator.py tests/test_aml_phase1_foundation.py`
