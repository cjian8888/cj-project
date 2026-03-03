# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-03
**Mode:** Update (existing conventions preserved)

---

## OVERVIEW

穿云审计 (F.P.A.S) - 资金穿透与关联排查系统。Python 3.9+ FastAPI 后端 + React 19 TypeScript 前端。核心功能: 交易数据清洗、疑点检测、资金画像、借贷分析、关联方穿透、ML风险预测。

**唯一入口**: `api_server.py` (`main.py` 已废弃)

---

## STRUCTURE

```
project/
├── api_server.py          # ⭐ 唯一入口 - FastAPI 服务
├── config.py             # 全局配置
├── data_cleaner.py       # 数据清洗
├── financial_profiler.py # 资金画像
├── suspicion_engine.py   # 疑点检测
├── loan_analyzer.py      # 借贷分析
├── *_extractor.py        # 数据提取器 (16+)
├── *_analyzer.py         # 数据分析器 (14+)
├── classifiers/          # 交易分类引擎
├── detectors/            # 疑点检测器插件 (8个)
├── schemas/              # Pydantic 数据模型
├── learners/             # ML 学习模块
├── knowledge/            # 行业知识库 (YAML)
├── utils/                # 工具函数
├── tests/                # pytest 测试
└── dashboard/            # React 前端
    ├── src/components/  # UI 组件
    ├── src/contexts/    # 全局状态
    ├── src/services/     # API 调用
    └── src/types/       # TypeScript 类型
```

---

## WHERE TO LOOK

| 任务 | 位置 | 关键文件 |
|------|------|--------|
| 修改 API 端点 | 根目录 | `api_server.py` |
| 修改配置 | 根目录 | `config.py`, `config_loader.py` |
| 添加检测器 | `detectors/` | 继承 `BaseDetector` |
| 添加分类器 | `classifiers/` | 实现 `classify()` |
| 修改数据模型 | `schemas/` | 继承 `BaseModel` |
| 修改前端组件 | `dashboard/src/components/` | `*.tsx` |
| 工具函数 | `utils/` | `safe_types.py` |
| 测试 | `tests/` | `test_*.py` |

---

## CODE MAP

| 符号 | 类型 | 位置 | 职责 |
|------|------|------|------|
| `api_server.py` | FastAPI | 根目录 | 唯一入口，所有 API 端点 |
| `config.py` | 配置 | 根目录 | 全局阈值参数 |
| `data_cleaner.py` | 清洗 | 根目录 | 数据清洗管道 |
| `financial_profiler.py` | 分析 | 根目录 | 资金画像生成 |
| `suspicion_engine.py` | 检测 | 根目录 | 疑点检测协调 |
| `clue_aggregator.py` | 聚合 | 根目录 | 线索聚合引擎 |
| `BaseDetector` | 基类 | `detectors/` | 检测器抽象基类 |
| `CategoryEngine` | 引擎 | `classifiers/` | 分类引擎入口 |
| `safe_str/float/int` | 函数 | `utils/safe_types.py` | 类型安全转换 |

---

## COMMANDS

```bash
# 启动后端 (唯一入口)
python api_server.py

# 启动前端
cd dashboard && npm run dev

# 运行测试
pytest tests/ -v

# 类型检查
cd dashboard && npm run type-check
```

---

## NOTES

### 数据源铁律
**所有 API 必须从 `output/cleaned_data/` 读取** - 禁止数据造假

### 批量文件说明
- 根目录 76 个 Python 文件 (扁平结构，建议重构)
- `api_server.py` 3438 行 (最大文件)
- 无 CI/CD 配置 (手动部署)

### 废弃代码
- `main.py` 已废弃，使用 `api_server.py`

---

## CONVENTIONS

### 🔧 工具函数统一规范

**⚠️ 重要**: 所有数据提取器必须使用统一的工具函数模块，**禁止**在各自文件中重复定义！

#### 统一工具函数位置
**模块**: `utils/safe_types.py`

**必须使用这些函数**:
```python
from utils.safe_types import (
    safe_str,           # 安全转换为字符串 (返回 Optional[str])
    safe_float,         # 安全转换为浮点数 (返回 Optional[float])
    safe_int,           # 安全转换为整数 (返回 Optional[int])
    safe_date,          # 安全转换为日期 YYYY-MM-DD (返回 Optional[str])
    safe_datetime,      # 安全转换为日期时间 YYYY-MM-DD HH:MM:SS (返回 Optional[str])
    extract_id_from_filename,  # 从文件名提取身份证号
    normalize_column_name,     # 标准化列名
)
```

#### 为什么需要统一？
1. **避免代码重复** - 之前16个文件中有46处重复定义
2. **行为一致性** - 统一空值检查、异常处理、类型注解
3. **易于维护** - 修改只需在一个地方进行
4. **减少bug** - 消除不同实现之间的细微差异

