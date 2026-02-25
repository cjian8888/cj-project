# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-25
**Commit:** af7f7e2
**Branch:** main

## OVERVIEW

穿云审计 (F.P.A.S) - 专业金融审计分析平台，用于资金流向分析、可疑交易检测、关联关系排查。
**Stack:** Python 3.9+ (FastAPI) + React 19.2 (TypeScript/Vite)

## STRUCTURE

```
cj-project/
├── api_server.py           # ⭐ 唯一入口 - FastAPI 服务
├── config.py               # 主配置 (951行，所有阈值/关键词)
├── detectors/              # 8个疑点检测器
├── classifiers/            # 交易分类引擎
├── schemas/                # Pydantic 数据模型
├── knowledge/              # YAML 行业知识库
├── learners/               # ML 学习器
├── dashboard/              # React 前端
├── output/
│   ├── cleaned_data/       # 🔴 成品数据 (唯一真理源)
│   ├── analysis_cache/     # 分析缓存 (JSON)
│   └── analysis_results/   # 报告输出
└── scripts/                # 工具脚本 (43个)
```

## WHERE TO LOOK

| 任务 | 位置 | 说明 |
|------|------|------|
| 添加检测器 | `detectors/` | 继承 `BaseDetector` |
| 修改阈值 | `config.py` + `config/risk_thresholds.yaml` | 双层配置 |
| 添加API | `api_server.py` | 单文件，按功能分section |
| 报告模板 | `templates/report_v3/` | Jinja2 HTML |
| 前端组件 | `dashboard/src/components/` | React + TailwindCSS |

## CONVENTIONS

### Python
- 文件头: `#!/usr/bin/env python3` + `# -*- coding: utf-8 -*-`
- 命名: snake_case (函数/变量), PascalCase (类), UPPER_SNAKE_CASE (常量)
- 类型注解: 必须
- 中文注释/文档: 允许

### 数据流铁律
```
🚨 任何API必须从 cleaned_data 读取，禁止虚构数据
📌 Excel里有什么，界面就显示什么
```

### Git提交
```
<type>: <subject>
feat/fix/docs/refactor/perf
```

## ANTI-PATTERNS (本项目)

- **禁止** `main.py` 作为入口 (已废弃)
- **禁止** 在 config 中硬编码案件特定数据
- **禁止** 空异常处理 `except: pass`
- **禁止** TODO/FIXME 残留在生产代码

## COMMANDS

```bash
# 启动后端
python api_server.py              # http://localhost:8000

# 启动前端
cd dashboard && npm run dev       # http://localhost:5173

# 测试
pytest tests/

# 类型检查 (前端)
cd dashboard && npm run type-check
```

## KEY THRESHOLDS

| 参数 | 值 | 说明 |
|------|-----|------|
| LARGE_CASH_THRESHOLD | 50,000 | 大额现金阈值(元) |
| CASH_TIME_WINDOW_HOURS | 48 | 现金碰撞窗口(小时) |
| LOAN_MIN_AMOUNT | 5,000 | 借贷分析最低金额 |
| INCOME_HIGH_RISK_MIN | 50,000 | 高风险收入阈值 |

## NOTES

- `investigation_report_builder.py` (416KB) 和 `api_server.py` (124KB) 是最大文件，考虑拆分
- 无 CI/CD 配置，手动部署
- 前端深色玻璃态主题，主色 `#3b82f6`
