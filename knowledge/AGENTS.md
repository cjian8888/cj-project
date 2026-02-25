# KNOWLEDGE MODULE

## OVERVIEW
行业知识库，存储金融术语、银行产品代码、检测规则。

## STRUCTURE
```
knowledge/
├── __init__.py              # 加载函数
├── financial_terms.yaml     # 金融术语
├── bank_product_lines.yaml  # 银行产品线
├── product_code_prefixes.yaml # 产品代码前缀
└── suspicion_rules.yaml     # 疑点检测规则
```

## WHERE TO LOOK

| 知识类型 | 文件 | 内容 |
|----------|------|------|
| 金融术语 | financial_terms.yaml | 转账类型、摘要关键词 |
| 银行产品 | bank_product_lines.yaml | 各银行产品分类 |
| 代码前缀 | product_code_prefixes.yaml | 交易代码含义 |
| 检测规则 | suspicion_rules.yaml | 疑点判定逻辑 |

## USAGE

```python
from knowledge import load_financial_terms, load_bank_products

terms = load_financial_terms()
products = load_bank_products()
```

## NOTES
- YAML 文件使用 UTF-8 编码
- 加载失败返回空字典 `{}`
- 知识库只读，运行时不应修改
