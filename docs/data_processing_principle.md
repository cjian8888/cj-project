# 数据处理原则与核查底稿机制

> **创建时间**: 2026-01-20
> 
> **核心原则**: 所有数据以Excel为载体,遵循"唯一数据来源"原则

---

## 🎯 核心原则

### 数据复用铁律

**禁止**: 下游模块重新读取原始Excel或重新计算已有数据

**正确**: 所有模块必须从以下三个位置获取数据:

| 优先级 | 数据源 | 路径 | 说明 |
|--------|--------|------|------|
| 1 | 清洗数据 | `output/cleaned_data/` | 标准化银行流水数据 |
| 2 | JSON缓存 | `output/analysis_cache/` | 程序首选数据源 |
| 3 | 核查底稿Excel | `output/analysis_results/资金核查底稿.xlsx` | 人工审阅载体 |

**优先级规则**:
- **JSON缓存优先**: 程序读取数据时优先使用JSON，速度快、结构清晰
- **Excel补充**: 当JSON缓存中缺失数据时，可回退到核查底稿Excel读取
- **保持同步**: 任何新增计算输出必须同时写入JSON缓存和核查底稿Excel

---

## 📊 数据处理流程

### 1. 原始数据 → 清洗数据

**输入**: `data/国监查【2024】第XXXXXX号/` 原始Excel文件

**处理模块**: `data_cleaner.py`

**输出**: `output/cleaned_data/个人/` 和 `output/cleaned_data/公司/`
- 格式: `{姓名}_合并流水.xlsx` 和 `{姓名}_合并流水.parquet`
- 内容: 标准化的银行流水数据

**数据特点**:
- 列名统一: `交易时间`, `收入(元)`, `支出(元)`, `余额(元)`, `交易对手`, `交易摘要`, `交易分类`, `所属银行`, `本方账号`, `现金`, `来源文件` 等
- 已去重、已标准化
- **这是后续所有分析的唯一数据来源**

---

### 2. 清洗数据 → 分析结果 → 核查底稿Excel

**输入**: `output/cleaned_data/` 中的清洗数据

**处理模块**: 
- `financial_profiler.py` - 资金画像
- `income_analyzer.py` - 异常收入分析
- `loan_analyzer.py` - 借贷分析
- `suspicion_detector.py` - 可疑交易检测
- 等...

**中间缓存**: `output/analysis_cache/`
- `profiles.json` - 资金画像
- `suspicions.json` - 可疑交易
- `derived_data.json` - 衍生数据
- `graph_data.json` - 图谱数据

**最终输出**: `output/analysis_results/资金核查底稿.xlsx`
- 多工作表Excel文件
- 每个工作表对应一类分析结果
- **这是前端展示和报告生成的数据来源**

---

### 3. 外部数据源 → 核查底稿Excel (新增模式)

**输入**: `data/国监查【2024】第XXXXXX号/` 中的外部数据源
- 中国人民银行银行账户
- 中国人民银行反洗钱
- 市场监管总局企业登记信息
- 征信数据
- 公安部机动车
- 证券信息
- 保险信息
- 等...

**处理模式**: 
1. **解析**: 从原始Excel/PDF/Doc中提取有效数据
2. **标准化**: 转换为统一的数据格式
3. **写入核查底稿**: 将数据写入 `资金核查底稿.xlsx` 的对应工作表中
4. **缓存**: 同时写入JSON缓存文件,供程序引用

**输出位置**:
- **Excel工作表**: `output/analysis_results/资金核查底稿.xlsx` 中新增工作表
- **JSON缓存**: `output/analysis_cache/` 中对应的JSON文件

**核心要求**:
- ✅ 所有外部数据源的有效数据都要写入核查底稿Excel
- ✅ 核查底稿Excel是人工审阅的主要载体
- ✅ JSON缓存是程序计算的数据来源
- ✅ 两者保持同步,数据一致

---

## 📋 核查底稿Excel结构

### 现有工作表 (已实现)

| 序号 | 工作表名称 | 数据来源 | 说明 |
|------|-----------|----------|------|
| 1 | 资金画像汇总 | `profiles.json` | 所有人员/公司的资金概况 |
| 2 | 直接转账关系 | `suspicions.json` | 核心人员与涉案公司的直接往来 |
| 3 | 现金时空伴随 | `suspicions.json` | 现金取存配对分析 |
| 4 | 隐形资产明细 | `suspicions.json` | 疑似隐形房产/车辆线索 |
| 5 | 固定频率异常进账 | `suspicions.json` | 规律性异常收入 |
| 6 | 大额现金明细 | `profiles.json` | 大额现金交易记录 |
| 7-9 | 第三方支付明细 | `profiles.json` | 微信/支付宝/财付通交易 |
| 10-12 | 理财产品明细 | `profiles.json` | 理财购买/赎回/持仓 |
| 13 | 家族关系图谱 | `family_tree` | 家庭成员关系 |
| 14-15 | 家族资产汇总 | `family_assets` | 房产/车辆等资产 |
| 16 | 数据验证结果 | `validation_results` | 数据质量检查 |
| 17-21 | 资金穿透分析 | `penetration_results` | 个人↔公司资金穿透 |
| 22-26 | 借贷行为分析 | `loan_results` | 双向往来/无还款/规律还款 |
| 27-28 | 异常收入分析 | `income_results` | 异常收入汇总/疑似分期受贿 |
| 29-30 | 时序分析 | `time_series_results` | 资金突变/固定延迟 |
| 31-33 | 资金闭环分析 | `penetration_results` | 闭环路径/过账通道/枢纽节点 |

### 待新增工作表 (Phase 6-8)

| 序号 | 工作表名称 | 数据来源 | 说明 | Phase |
|------|-----------|----------|------|-------|
| 34 | 银行账户清单 | 人民银行银行账户 | 完整账户列表+状态 | Phase 6 |
| 35 | 反洗钱预警 | 人民银行反洗钱 | 可疑交易监测结果 | Phase 6 |
| 36-40 | 企业登记信息 | 市场监管总局 | 基本信息/出资/人员/变更/补充 | Phase 6 |
| 41 | 征信报告 | 征信数据 | 信用评分/负债/贷款 | Phase 6 |
| 42 | 机动车登记 | 公安部机动车 | 车辆详细信息 | Phase 7 |
| 43-44 | 证券持仓 | 证券信息 | 证券账户/持仓明细 | Phase 7 |
| 45 | 保险信息 | 保险数据 | 保险公司/险种/保额 | Phase 8 |
| 46 | 出入境记录 | 公安部出入境 | 出入境时间线 | Phase 8 |
| 47 | 旅馆住宿 | 公安部旅馆住宿 | 住宿记录/同住人 | Phase 8 |
| 48 | 航班进出港 | 中航信航班 | 航班出行轨迹 | Phase 8 |

---

## 🔄 数据流向图

```
原始数据源
    ↓
┌─────────────────────────────────────────┐
│  data/国监查【2024】第XXXXXX号/         │
│  ├── 银行业金融机构交易流水/            │
│  ├── 中国人民银行银行账户/              │
│  ├── 市场监管总局企业登记信息/          │
│  └── ... (28个数据源)                   │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  数据清洗与解析                          │
│  ├── data_cleaner.py (银行流水)         │
│  ├── bank_account_extractor.py (新建)   │
│  ├── company_info_extractor.py (新建)   │
│  └── ... (各类解析模块)                  │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  清洗数据 (唯一来源)                     │
│  output/cleaned_data/                   │
│  ├── 个人/{姓名}_合并流水.xlsx          │
│  └── 公司/{公司名}_合并流水.xlsx        │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  分析计算                                │
│  ├── financial_profiler.py              │
│  ├── income_analyzer.py                 │
│  ├── loan_analyzer.py                   │
│  └── ... (各类分析模块)                  │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  分析结果缓存                            │
│  output/analysis_cache/                 │
│  ├── profiles.json                      │
│  ├── suspicions.json                    │
│  ├── derived_data.json                  │
│  ├── bank_accounts.json (新增)          │
│  ├── company_info.json (新增)           │
│  └── ... (各类缓存)                      │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  核查底稿Excel (最终产出)                │
│  output/analysis_results/               │
│  └── 资金核查底稿.xlsx                   │
│      ├── 资金画像汇总                    │
│      ├── 直接转账关系                    │
│      ├── 银行账户清单 (新增)             │
│      ├── 企业登记信息 (新增)             │
│      └── ... (40+个工作表)               │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  前端展示 & 报告生成                     │
│  ├── api_server.py (读取Excel)          │
│  ├── report_generator.py (生成报告)     │
│  └── dashboard (前端展示)               │
└─────────────────────────────────────────┘
```

---

## ✅ 实施要点

### Phase 1-5: 现有模块增强

**目标**: 增强现有的清洗数据和分析能力

**数据处理**:
- 继续使用 `output/cleaned_data/` 作为唯一数据来源
- 增强数据清洗逻辑(如账户类型识别)
- 新增计算字段写入缓存JSON
- 更新核查底稿Excel的现有工作表

### Phase 6-8: 外部数据源解析

**目标**: 解析外部数据源,写入核查底稿Excel

**数据处理**:
1. **解析模块**: 创建专门的解析模块(如 `bank_account_extractor.py`)
2. **数据标准化**: 将原始数据转换为统一格式
3. **写入Excel**: 在 `report_generator.py` 中新增工作表生成函数
4. **写入缓存**: 同时写入JSON缓存文件
5. **数据引用**: 后续计算从JSON缓存读取

**示例 - 银行账户解析**:

```python
# 1. 解析模块: bank_account_extractor.py
def extract_bank_accounts(data_dir):
    """从人民银行账户数据中提取账户信息"""
    accounts = []
    # 解析Excel文件
    for file in glob(f"{data_dir}/中国人民银行银行账户/*.xlsx"):
        df = pd.read_excel(file)
        # 提取有效数据
        for _, row in df.iterrows():
            accounts.append({
                '姓名': row['名称'],
                '银行名称': row['开户银行名称'],
                '账号': row['帐号'],
                '账户性质': row['账户性质'],
                '账户状态': row['账户状态'],
                '开户时间': row['开户时间'],
                '销户时间': row['销户时间']
            })
    return accounts

# 2. 写入缓存: 在main.py或专门的缓存模块中
bank_accounts = extract_bank_accounts(data_dir)
with open('output/analysis_cache/bank_accounts.json', 'w') as f:
    json.dump(bank_accounts, f, ensure_ascii=False, indent=2)

# 3. 写入Excel: 在report_generator.py中新增函数
def _generate_bank_accounts_sheet(writer, bank_accounts):
    """生成银行账户清单工作表"""
    if not bank_accounts:
        return
    df = pd.DataFrame(bank_accounts)
    df.to_excel(writer, sheet_name='银行账户清单', index=False)

# 4. 在generate_excel_workbook()中调用
with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    # ... 现有工作表 ...
    _generate_bank_accounts_sheet(writer, bank_accounts)
```

---

## 🚫 禁止的做法

1. ❌ 在 `api_server.py` 中直接读取原始数据
2. ❌ 在报告生成时重新计算已有的分析结果
3. ❌ 绕过核查底稿Excel,直接从JSON缓存生成报告
4. ❌ 外部数据源解析后不写入核查底稿Excel
5. ❌ Excel和JSON缓存数据不一致

---

## ✅ 正确的做法

1. ✅ 所有原始数据只读取一次,写入清洗数据或缓存
2. ✅ 下游模块从清洗数据或缓存读取
3. ✅ 核查底稿Excel是人工审阅的主要载体
4. ✅ JSON缓存是程序计算的数据来源
5. ✅ Excel和JSON保持同步

---

## 📝 版本记录

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-01-20 | 初始版本,明确数据处理原则和核查底稿机制 |
