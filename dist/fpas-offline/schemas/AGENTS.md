# SCHEMAS MODULE

## OVERVIEW
Pydantic 数据模型，定义 API 数据结构和验证规则。

## STRUCTURE
```
schemas/
├── config.py       # UserConfig, AnalysisUnit, FamilyRelation
├── transaction.py  # Transaction, TransactionBatch
├── suspicion.py    # Suspicion, SuspicionReport, SuspicionSeverity
└── profile.py      # Profile, ProfileMetrics, ProfileComparison
```

## WHERE TO LOOK

| 模型 | 文件 | 用途 |
|------|------|------|
| UserConfig | config.py | 用户配置 |
| Transaction | transaction.py | 交易记录 |
| Suspicion | suspicion.py | 疑点结果 |
| Profile | profile.py | 资金画像 |

## CONVENTIONS

### 添加新 Schema
```python
from pydantic import BaseModel
from typing import List, Optional

class MyModel(BaseModel):
    id: str
    name: Optional[str] = None
    items: List[str] = []
```

### 导出规则
在 `__init__.py` 中添加到 `__all__`。

## NOTES
- 所有模型继承 `BaseModel`
- 使用 `Optional` 表示可选字段
- 验证错误会抛出 `ValidationError`
