# TESTS MODULE

## OVERVIEW

pytest 测试框架，22 个测试文件，无 conftest.py（手动路径注入）。

## STRUCTURE

```
tests/
├── test_*.py           # 单元测试 (21个)
├── phrase_loader_test.py  # 短语加载测试
└── __init__.py         # 空文件
```

## WHERE TO LOOK

| 测试类型 | 文件 | 测试内容 |
|---------|------|----------|
| 工具函数 | test_utils.py | safe_str, safe_float, 日期解析 |
| 数据清洗 | test_data_cleaner.py | 去重、验证、标准化 |
| 银行格式 | test_bank_formats.py | ICBC, CCB, 通用格式 |
| 检测器 | test_*_detector.py | 8 个检测器的单元测试 |
| Schema | test_schemas.py | Pydantic 模型验证 |
| 性能 | test_financial_profiler.py | 10万条记录性能测试 |

## CONVENTIONS

### 测试文件结构
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模块描述"""

import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from module import ...

class TestClassName:
    """测试类描述"""
    
    def test_scenario(self):
        """测试场景描述"""
        # 测试代码

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### 测试数据模式
```python
df = pd.DataFrame({
    'column_name': [values],
})
```

### 性能测试约定
```python
def test_performance(self):
    start = time.time()
    # ... 操作 ...
    elapsed = time.time() - start
    assert elapsed < 5.0, f"耗时 {elapsed:.2f} 秒，超过限制"
```

## COMMANDS

```bash
# 运行所有测试
pytest tests/ -v

# 运行单个测试文件
python tests/test_utils.py

# 运行特定测试
pytest tests/test_utils.py::TestClassName::test_method -v
```

## NOTES

- **无 conftest.py** - 每个文件手动路径注入
- **无共享 fixtures** - 直接创建测试数据
- **无 coverage 配置** - 可添加 pytest-cov
- **Bug 修复文档** - 部分文件包含修复说明注释
