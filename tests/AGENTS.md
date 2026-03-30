# TESTS MODULE

## OVERVIEW
pytest 测试框架，48 个测试文件，无 conftest.py（手动路径注入）。

## STRUCTURE
```
tests/
├── __init__.py                           # 空文件
├── test_utils.py                         # safe_str/float/日期解析 (83方法)
├── test_data_cleaner.py                  # 去重/验证/标准化 (64方法)
├── test_api_server_config_flow.py        # API配置与缓存 (75方法)
├── test_financial_profiler.py            # 画像性能测试 (73方法)
├── test_investigation_report_builder_metrics.py  # 报告构建指标 (55方法)
├── test_schemas.py                       # Pydantic模型验证 (21方法)
├── test_bank_formats.py                  # 银行格式解析 (25方法)
├── test_exceptions.py                    # 异常处理 (30方法)
├── test_data_extractor.py                # 数据提取 (19方法)
├── test_report_generator.py              # 报告生成 (6方法)
├── test_report_package_builder.py        # 报告包构建 (36方法)
├── test_specialized_reports.py           # 专项报告 (22方法)
├── test_income_classification.py         # 收入分类 (36方法)
├── test_amount_hardening.py              # 金额硬化 (18方法)
├── test_build_windows_package.py         # Windows打包 (25方法)
├── test_*_detector.py                    # 8个检测器各自测试
├── test_behavioral_profiler.py           # 行为画像
├── test_wallet_risk_analyzer.py          # 钱包风险分析
├── test_clue_aggregator.py              # 线索聚合
└── ... (共48文件)
```

## WHERE TO LOOK

| 测试类型 | 文件 | 测试内容 |
|---------|------|----------|
| 工具函数 | test_utils.py | safe_str, safe_float, 日期解析 |
| 数据清洗 | test_data_cleaner.py | 去重、验证、标准化 |
| API 流程 | test_api_server_config_flow.py | 端点测试、缓存、配置 |
| 性能基准 | test_financial_profiler.py | 10万条记录性能测试 |
| 报告构建 | test_report_package_builder.py | report_package 结构验证 |
| 银行格式 | test_bank_formats.py | ICBC, CCB, 通用格式 |
| 检测器 | test_*_detector.py (8个) | 各检测器单元测试 |
| Schema | test_schemas.py | Pydantic 模型验证 |
| 金额硬化 | test_amount_hardening.py | 安全金额转换 |
| Windows打包 | test_build_windows_package.py | 打包完整性验证 |

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
        """测试场景描述 (中文docstring)"""
        # 测试代码
        assert result == expected, f"描述性错误信息"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
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
- **无 conftest.py** - 每个文件手动 `sys.path.insert`
- **无共享 fixtures** - 直接创建测试数据
- **无 coverage 配置** - 可添加 pytest-cov
- **中文 docstrings** - 测试描述使用中文
- **无 pytest.ini / pyproject.toml** - 使用默认 pytest 发现
- **CI**: GitHub Actions 仅做打包发布，不跑测试
