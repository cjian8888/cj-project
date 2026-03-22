# REPORT_CONFIG MODULE

## OVERVIEW
报告配置模块，存储报告短语模板和风险阈值配置。

## STRUCTURE
```
report_config/
├── __init__.py           # 包导出
├── report_config.py     # 报告配置服务
├── report_phrases.yaml  # 报告短语模板 (20KB)
└── risk_thresholds.yaml # 风险阈值
```

## WHERE TO LOOK

| 配置类型 | 文件 | 说明 |
|----------|------|------|
| 短语模板 | report_phrases.yaml | 场景化中文短语 |
| 风险阈值 | risk_thresholds.yaml | 收入/支出/综合风险阈值 |
| 配置服务 | report_config.py | Python 加载逻辑 |

## CONVENTIONS

### 短语变量
```yaml
# report_phrases.yaml
income_analysis:
  normal: "收入结构正常，{name}的年度总收入为 {total_income}元"
  warning: "收入波动较大..."
```

### 阈值配置
```yaml
# risk_thresholds.yaml
risk_scores:
  high: 60
  medium: 30
  low: 0
```

## NOTES
- 与 `config/` 目录协同工作
- 短语支持变量插值: `{name}`, `{total_income}`
- YAML 使用 UTF-8 编码
