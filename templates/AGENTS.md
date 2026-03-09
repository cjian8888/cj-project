# TEMPLATES MODULE

## OVERVIEW
HTML 报告模板，生成审计报告和资金流向可视化。

## STRUCTURE
```
templates/
├── base_report.html      # 基础报告框架
├── html_report.html      # HTML 综合报告
├── flow_visualization.html # 资金流向图模板
├── summary.html           # 摘要模板
├── risks.html            # 风险分析模板
├── assets.html           # 资产分析模板
├── sample_report_*.html  # 示例报告 (个人/公司/完整)
└── report_v3/            # V3 版本模板
```

## WHERE TO LOOK

| 模板类型 | 文件 | 用途 |
|----------|------|------|
| 基础框架 | base_report.html | 通用报告结构 |
| 流向图 | flow_visualization.html | vis-network 资金流向 |
| 风险分析 | risks.html | 风险指标展示 |
| 示例报告 | sample_report_*.html | 参考示例 |

## CONVENTIONS

### Jinja2 风格
```html
<h1>{{ title }}</h1>
{% for item in items %}
  <p>{{ item.name }}</p>
{% endfor %}
```

### 内联样式
- 所有样式内联 (无外部 CSS 依赖)
- 支持打印 (print-friendly)
- 离线可用

## NOTES
- 模板可离线查看
- 使用 vis-network 进行可视化
- 支持深色/浅色主题
