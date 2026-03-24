# UTILS MODULE

## OVERVIEW

工具函数包，提供类型安全转换和通用辅助函数。核心: `safe_types.py`。

## STRUCTURE

```
utils/
├── __init__.py        # 包导出 (re-exports from utils.py)
├── safe_types.py      # 类型安全转换函数 ⭐
└── phrase_loader.py   # 报告短语加载器
```

## WHERE TO LOOK

| 功能 | 文件 | 说明 |
|------|------|------|
| 类型转换 | `safe_types.py` | `safe_str`, `safe_float`, `safe_int`, `safe_date` |
| ID提取 | `safe_types.py` | `extract_id_from_filename()` |
| 列名标准化 | `safe_types.py` | `normalize_column_name()` |
| 短语加载 | `phrase_loader.py` | `PhraseLoader` 类 |

## CONVENTIONS

### 统一类型转换 (MANDATORY)

**⚠️ 所有数据提取器必须使用 `utils/safe_types.py`，禁止重复定义！**

```python
from utils.safe_types import (
    safe_str,           # → Optional[str]
    safe_float,         # → Optional[float]
    safe_int,           # → Optional[int]
    safe_date,          # → Optional[str] (YYYY-MM-DD)
    safe_datetime,      # → Optional[str] (YYYY-MM-DD HH:MM:SS)
    extract_id_from_filename,   # 从文件名提取身份证
    normalize_column_name,      # 标准化列名
)
```

### 函数规范

- 所有 `safe_*` 函数返回 `Optional[T]`，空值返回 `None`
- 使用 `pd.isna()` 检查空值，处理 pandas 和原生类型
- 异常静默处理：转换失败返回 `None`，不抛出

## NOTES

- `utils/__init__.py` 通过动态导入 re-export 根目录 `utils.py` 的函数
- `safe_types.py` 被 16+ 个提取器导入使用
- `PhraseLoader` 支持模板变量渲染和简单表达式计算
