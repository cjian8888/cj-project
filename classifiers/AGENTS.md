# CLASSIFIERS MODULE

## OVERVIEW
交易分类引擎，识别交易类型（工资、理财、内部转账等）。

## STRUCTURE
```
classifiers/
├── category_engine.py      # 分类引擎入口
├── salary_classifier.py    # 工资识别
├── wealth_classifier.py    # 理财产品识别
└── self_transfer_classifier.py # 内部转账识别
```

## WHERE TO LOOK

| 分类类型 | 文件 | 关键词来源 |
|----------|------|------------|
| 工资收入 | salary_classifier.py | config.SALARY_KEYWORDS |
| 理财产品 | wealth_classifier.py | config.KNOWN_WEALTH_PRODUCTS |
| 内部转账 | self_transfer_classifier.py | 同名账户检测 |

## CONVENTIONS

### 分类器接口
```python
class Classifier:
    def classify(self, transaction: pd.Series) -> Optional[str]:
        """返回分类标签或 None"""
        pass
```

### 集成点
- `CategoryEngine` 聚合所有分类器
- 被 `income_analyzer.py`, `financial_profiler.py` 调用

## NOTES
- 分类优先级: 工资 > 理财 > 内部转账
- 关键词配置在 `config.py`
