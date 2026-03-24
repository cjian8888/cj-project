# LEARNERS MODULE

## OVERVIEW
机器学习模块，从交易数据中学习模式。

## STRUCTURE
```
learners/
├── bank_code_learner.py     # 银行代码学习
├── prefix_learner.py        # 前缀模式学习
└── product_name_learner.py  # 产品名称学习
```

## WHERE TO LOOK

| 学习器 | 文件 | 学习内容 |
|--------|------|----------|
| BankCodeLearner | bank_code_learner.py | 银行代码含义 |
| PrefixLearner | prefix_learner.py | 交易摘要前缀 |
| ProductNameLearner | product_name_learner.py | 理财产品名称 |

## CONVENTIONS

### 学习器接口
```python
class Learner:
    def learn(self, transactions: pd.DataFrame) -> Dict:
        """从交易数据学习，返回知识字典"""
        pass
    
    def save(self, path: str) -> None:
        """保存学习结果"""
        pass
```

## NOTES
- 学习结果存入 `knowledge/` YAML 文件
- 增量学习: 多次调用 `learn()` 累积知识
- 用于补充静态配置无法覆盖的规则
