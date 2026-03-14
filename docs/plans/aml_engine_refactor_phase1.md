# AML 分析引擎重构第一阶段实施方案

## 阶段目标

第一阶段只做三类事情：

1. 统一严格时间排序与交易事件标准化
2. 修复最明显的性能与误配问题
3. 在不打断报告和前端输入的前提下开始替换高风险算法

## 第一阶段范围

### 1. 公共底座

文件：

- `utils.py`
- `utils/__init__.py`

新增能力：

- 严格排序键构建
- 稳定交易排序
- 公共账户字段识别
- 可供借贷、时序、现金检测复用的事件标准化能力

### 2. 现金碰撞优化

文件：

- `suspicion_detector.py`

目标函数：

- `detect_cash_time_collision()`

本阶段动作：

- 单实体现金碰撞从笛卡尔积改为滑动窗口候选匹配
- 使用严格排序避免同秒多笔不稳定
- 默认一笔存现只取最优取现候选，降低噪声

### 3. 时序延迟转账优化

文件：

- `time_series_analyzer.py`

目标函数：

- `_normalize_time_series_df()`
- `detect_delayed_transfers()`

本阶段动作：

- 全部时序输入统一严格排序
- 延迟转账从双重循环改为时间窗口搜索
- 输出保持兼容，并补充别名字段供旧报告消费

### 4. 借贷台账重构启动

文件：

- `loan_analyzer.py`

目标函数：

- `_detect_loan_pairs()`
- `_detect_no_repayment_loans()`

本阶段动作：

- 先引入统一排序与更稳的序列处理
- 优先解决明显的重复计提风险
- 输出结构保持兼容

说明：

- 如果本阶段无法安全完成全部借贷语义重构，则必须保证阶段内先不破坏报告字段
- 复杂的利息归因与关系网络增强留到下一轮实现

## 第一阶段非目标

- 不改前端输入界面
- 不切换报告主口径到新图模型
- 不引入复杂图社区算法或黑箱模型
- 不一次性替换所有关系分析模块

## 报告兼容策略

- 继续输出 `loan_pairs`
- 继续输出 `no_repayment_loans`
- 继续输出 `regular_repayments`
- 新增 metadata 时必须是附加字段，不替换现有字段

## 验收标准

### 算法

- 同秒多笔下结果稳定
- 单实体现金碰撞不再使用全量交叉连接
- 延迟转账不再是全量双重循环
- 借贷未还款判定不再直接对未来支出无约束求和

### 兼容

- 现有报告生成入口不崩
- 前端界面输入不变
- 旧字段仍可被现有消费者读取

### 测试

- 至少覆盖严格排序
- 至少覆盖现金碰撞最优匹配
- 至少覆盖延迟转账乱序输入

## 本阶段拟修改函数树

```text
Phase 1
├── utils.py
│   ├── build_transaction_order_columns()
│   ├── sort_transactions_strict()
│   └── detect_account_identifier_column()
├── suspicion_detector.py
│   ├── detect_cash_time_collision()
│   └── detect_cross_entity_cash_collision()  # 稳定排序兼容
├── time_series_analyzer.py
│   ├── _normalize_time_series_df()
│   └── detect_delayed_transfers()
└── loan_analyzer.py
    ├── _detect_loan_pairs()
    └── _detect_no_repayment_loans()
```

## 阶段完成后必须记录

- 哪些函数已经完成改造
- 哪些函数仅完成底座接入
- 哪些问题明确留到第二阶段
