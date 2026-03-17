# 穿云审计 (F.P.A.S)

资金穿透与关联排查系统。当前主交付形态为 `Windows 单机离线 one-folder 包`，开发态使用 `FastAPI + React/Vite`。

系统目标不是做一套泛化 BI，而是把审计排查里最费人工的几件事固化下来：

- 银行流水清洗与统一标准化
- 真实收入/真实支出重估
- 资金闭环、过账通道、关系碰撞、同源线索穿透
- 外部协查数据与银行流水的融合画像
- 可直接交付的 TXT / Excel / HTML / 图谱产物

## 核心特性

- `api_server.py` 是唯一后端入口
- 以 `output/cleaned_data/` 为唯一成品数据源
- 分析流程分为 7 个 Phase，外部数据先提取、再融合画像、再做全面分析
- 报告阶段优先读取 `analysis_cache`，不回到原始 `data/` 重算
- 支持银行流水主链 + 电子钱包补充层双轨并行
- 支持后端直接承载前端生产构建：`/dashboard/`
- 支持完全离线运行，不依赖 CDN 和在线服务

---

## 系统架构

```mermaid
flowchart TD
    A[data/ 原始数据目录] --> B[Phase 1 文件扫描]
    B --> C[Phase 2 数据清洗]
    C --> D[output/cleaned_data]

    A --> E[Phase 4 外部数据提取]
    E --> E0[P0 核心上下文]
    E --> E1[P1 资产数据]
    E --> E2[P2 行为数据]
    E --> EW[电子钱包补充层]

    D --> F[Phase 5 融合画像]
    E0 --> F
    E1 --> F
    E2 --> F
    EW --> F

    F --> G[financial_profiler<br/>真实收入 / 工资 / 理财 / 家庭口径]
    F --> H[Phase 6 全面分析<br/>时序 / 借贷 / 穿透 / 关联 / ML]
    H --> I[Phase 7 疑点检测插件]
    G --> J[clue_aggregator 线索聚合]
    H --> J
    I --> J

    F --> K[output/analysis_cache]
    H --> K
    I --> K
    J --> K

    K --> L[investigation_report_builder]
    K --> M[specialized_reports]
    K --> N[report_generator / wallet_report_builder]

    N --> O[output/analysis_results]
    M --> O
    L --> O

    K --> P[FastAPI]
    P --> Q[/dashboard/ 生产前端]
    P --> R[Vite 开发前端]
```

---

## 分析主链路

`run_analysis_refactored()` 当前按以下 7 个 Phase 执行：

1. `Phase 1` 文件扫描
2. `Phase 2` 数据清洗与标准化
3. `Phase 3` 线索提取
4. `Phase 4` 外部数据提取
5. `Phase 5` 融合数据画像
6. `Phase 6` 全面分析
7. `Phase 7` 疑点检测

### Phase 4 外部数据分层

#### P0 核心上下文

- 人民银行账户
- 反洗钱数据与预警
- 企业登记信息
- 征信数据与预警
- 银行业金融机构账户信息

#### P1 资产数据

- 机动车
- 银行理财产品
- 证券信息
- 精准房产查询

#### P2 行为数据

- 保险
- 出入境
- 旅馆住宿 / 同住
- 同住址 / 同车违章
- 铁路
- 航班

#### 电子钱包补充层

- 支付宝实名账户 / 交易
- 微信注册信息 / 登录轨迹
- 财付通实名账户 / 交易

电子钱包不进入银行主清洗链，而是以补充证据层进入画像、聚合评分和专项报告。

---

## 关键技术实现

这部分是当前 README 里最容易失真的地方。下面按现有代码口径描述。

### 1. 数据清洗与标准化

核心文件：

- `data_cleaner.py`
- `bank_formats.py`
- `utils/safe_types.py`
- `data_validator.py`

实现重点：

- 将不同银行、不同字段命名的流水统一到标准列
- 统一日期、金额、对手方、摘要、账号等字段类型
- 保留来源文件和来源行号，后续所有报告支持回溯
- 个人 / 公司清洗结果分别落到 `output/cleaned_data/个人` 与 `output/cleaned_data/公司`

这是全系统的“真源层”。后续页面、图谱、报告都应该建立在这里之上。

### 2. 真实收入识别与工资口径收口

核心文件：

- `financial_profiler.py`
- `classifiers/category_engine.py`
- `classifiers/salary_classifier.py`
- `classifiers/self_transfer_classifier.py`
- `classifiers/wealth_classifier.py`

当前实现不是单一规则，而是分层扣减：

1. 先做工资识别
   - 关键词匹配
   - 发薪主体别名集合
   - 银联代付 / 委托代发 / 批量代发等发薪通道语义
2. 再做自转识别
   - 同名账户
   - 本人名下账号集合
   - 虚拟账户 / 理财账户 / 映射账户
3. 再做理财与定存识别
   - `WealthAccountAnalyzer` 对账号做账户级分类
   - 结合同日配对、利息尾差、长账号、内部账户等信号识别本金回流
4. 再做收入来源分类
   - 合法收入
   - 来源不明
   - 个人转账
   - 家庭转入
   - 报销 / 退款 / 贷款 / 理财赎回等剔除项
5. 最后重算 `real_income` / `real_expense`

当前真实收入计算已经专门补强以下易漏场景：

- `网银跨行汇款CHN` 二次识别
- `无法足额扣款，请补足账户余额`
- `还款成功 , 谢谢 !`
- 银行产品回摆 / 账单分期 / 还款冲销类文本

并且工资相关口径已对齐，避免出现“工资统计进去了，但真实收入已经剔除了”的口径错位。

### 3. 资金穿透图与闭环识别

核心文件：

- `fund_penetration.py`
- `flow_visualizer.py`

实现重点：

- 以交易对手关系构建有向加权资金图
- 对镜像转账做去重，避免同一笔双边流水被算成两条边
- 资金闭环检测加入：
  - 单步时间窗口
  - 全链路时间窗口
  - 工资边排除
  - 公共支付平台节点过滤
- 过账通道识别不只看“中转次数”，还看：
  - 入出金额匹配度
  - 时间连续性
  - 语义角色
  - 支撑流水数量
- 所有闭环 / 通道都会生成 explainability 结构，供图谱页和报告直接引用

### 4. 关联方与关系碰撞分析

核心文件：

- `related_party_analyzer.py`
- `multi_source_correlator.py`
- `family_analyzer.py`
- `cohabitation_extractor.py`

实现重点：

- 在核心人员、企业、同户成员、同住址、同住宿、同行记录之间建立碰撞关系
- 检测资金闭环、直接往来、共享节点、高频交互
- 将同住址、同车违章、住宿同住、铁路/航班同行等“非资金证据”转成可聚合的关系证据

这里的设计目标不是“关系越多越好”，而是尽量减少公共节点和常见平台带来的伪关联。

### 5. 时序异常分析

核心文件：

- `time_series_analyzer.py`
- `holiday_service.py`

主要输出：

- 周期性收入模式
- 资金突变事件
- 固定延迟转账

实现方式：

- 周期性收入：按对手方、金额、时间间隔寻找稳定模式
- 突变：使用统计波动和 `z-score` 检测异常峰值
- 延迟转账：寻找稳定的先入后出 / 先出后入延迟模式
- 节假日判断优先识别法定节日，普通周末不再误判为“节假日”

### 6. 电子钱包补充层

核心文件：

- `wallet_data_extractor.py`
- `wallet_risk_analyzer.py`
- `wallet_report_builder.py`

这部分不是简单“导入支付宝 Excel”，而是补一层跨平台证据：

- 统一归并主体 ID / 姓名 / 别名 / 手机号
- 汇总平台级收支、交易笔数、实名账户、登录轨迹
- 输出跨平台交叉信号：
  - 银行卡重叠
  - 别名重叠
  - 手机号重叠
  - 未归并微信账号
- 高风险增强会主动排除误报：
  - 本人互转
  - 家庭成员往来
  - 已明确识别为工资的对手方
  - 工资入账后的快速转出

### 7. 疑点检测插件系统

核心文件：

- `suspicion_engine.py`
- `detectors/`

当前疑点检测是插件化加载，不是写死在一个大函数里。

已接入的检测器包括：

- 直接转账检测
- 现金碰撞检测
- 固定金额检测
- 固定频率检测
- 频率异常检测
- 整数金额检测
- 异常模式检测
- 时间异常检测

`SuspicionEngine` 会自动扫描 `detectors/` 目录，加载所有继承 `BaseDetector` 的检测器。

### 8. 线索聚合与统一风险评分

核心文件：

- `clue_aggregator.py`
- `risk_scoring.py`
- `unified_risk_model.py`

实现重点：

- 按实体维护 `evidence_pack`
- 将闭环、过账、时序异常、钱包预警、ML 异常、关系碰撞统一归档
- 每类证据都保留风险分、置信度、支撑证据、路径解释
- 最终统一计算：
  - 实体总风险分
  - 风险等级
  - 最强证据分
  - 高优先级线索数
  - explainability 指标

这一步的产物会直接喂给：

- Dashboard 概览页
- 报告摘要
- 实体证据包
- 风险排序

### 9. ML 异常分析

核心文件：

- `ml_analyzer.py`

当前实现不是依赖 `scikit-learn` 的黑盒模型，而是原生 `Python/NumPy/Pandas` 统计学习方案。

主要做两类事：

- 单笔异常交易打分
- 基于交易图的轻量社区发现

同时引入了大量低风险公共商户排除，避免把支付平台、公共服务、生活消费误聚成“大团伙”。

### 10. 报告构建与缓存优先读取

核心文件：

- `investigation_report_builder.py`
- `report_generator.py`
- `specialized_reports.py`
- `report_service.py`
- `cache_manager.py`

当前报告层最重要的工程约束：

- 优先读 `output/analysis_cache/`
- 不在报告阶段回 `data/` 重算
- `profiles.json` 已承载完整画像数据，不再维护 `profiles_full.json`
- 报告构建器按需加载 `walletData`、`precisePropertyData`、`hotelData`、`flightData` 等外部缓存

这保证了“页面看到什么，报告写什么，缓存里就是什么”，减少多套口径漂移。

---

## 输出目录说明

当前程序的输出目录不是只有三四个文件，而是分层落盘。

```text
output/
├── cleaned_data/                    # 成品清洗层，唯一真理源
│   ├── 个人/
│   └── 公司/
├── analysis_cache/                  # JSON 缓存层
│   ├── profiles.json                # 完整画像
│   ├── suspicions.json              # 疑点检测结果
│   ├── derived_data.json            # 全面分析结果
│   ├── graph_data.json              # 图谱数据
│   ├── metadata.json                # 元信息、版本、生成时间、id 映射
│   ├── walletData.json              # 电子钱包补充层（按需）
│   ├── external_p0.json             # P0 外部数据总缓存（按需）
│   ├── external_p1.json             # P1 外部数据总缓存（按需）
│   ├── external_p2.json             # P2 外部数据总缓存（按需）
│   ├── amlData.json                 # 细分外部缓存（按需）
│   ├── creditData.json
│   ├── precisePropertyData.json
│   ├── vehicleData.json
│   ├── wealthProductData.json
│   ├── securitiesData.json
│   ├── insuranceData.json
│   ├── immigrationData.json
│   ├── hotelData.json
│   ├── hotelCohabitation.json
│   ├── railwayData.json
│   ├── flightData.json
│   ├── coaddressData.json
│   └── coviolationData.json
├── analysis_results/                # 正式报告层
│   ├── 核查结果分析报告.txt
│   ├── 资金核查底稿.xlsx
│   ├── 分析执行日志.txt
│   ├── 报告目录清单.txt
│   ├── 电子钱包补充分析报告.txt      # 按需
│   ├── 电子钱包补充清洗表.xlsx       # 按需
│   ├── 电子钱包重点核查清单.txt      # 按需
│   └── 专项报告/
│       ├── 借贷行为分析报告.txt
│       ├── 时序分析报告.txt
│       ├── 行为特征分析报告.txt
│       ├── 疑点检测分析报告.txt
│       ├── 异常收入来源分析报告.txt
│       ├── 资产全貌分析报告.txt
│       └── 资金穿透分析报告.txt
├── analysis_logs/                   # 运行日志固化层
│   ├── analysis_run_*.log
│   └── analysis_run_latest.log
└── audit_system.db                  # 审计库
```

说明：

- `analysis_cache` 的核心文件是固定的，外部缓存和电子钱包缓存按数据存在情况落盘
- `analysis_results` 是最终交付物
- `cleaned_data` 是后续所有分析的基础真源，不能直接跳过

---

## 项目结构

下面是按职责重组后的结构图，比“列几个脚本名”更接近当前代码现实：

```text
cj-project/
├── api_server.py                    # 唯一入口，FastAPI 服务与 7-Phase 主流程
├── paths.py                         # 开发态 / PyInstaller 资源路径统一解析
├── cache_manager.py                 # analysis_cache 生命周期管理
├── config.py                        # 阈值、关键词、规则常量
├── config/                          # YAML 配置
├── knowledge/                       # 知识库
├── report_config/                   # 报表配置
├── templates/                       # HTML / 报表模板
│
├── data_cleaner.py                  # 银行流水清洗主链
├── data_extractor.py                # 输入扫描与提取辅助
├── bank_formats.py                  # 银行字段映射
├── data_validator.py                # 清洗结果校验
│
├── financial_profiler.py            # 画像、工资、理财、真实收入、家庭口径
├── income_analyzer.py               # 收入分析
├── loan_analyzer.py                 # 借贷分析
├── time_series_analyzer.py          # 时序异常
├── fund_penetration.py              # 资金穿透 / 闭环 / 过账通道
├── related_party_analyzer.py        # 关联方资金关系
├── clue_aggregator.py               # 线索聚合与证据包
├── ml_analyzer.py                   # 统计学习异常分析
├── suspicion_engine.py              # 疑点检测插件调度
├── behavioral_profiler.py           # 行为特征画像
├── professional_finance_analyzer.py # 职业财务特征
│
├── *_extractor.py                   # 外部协查数据提取器
│   ├── pboc_account_extractor.py
│   ├── company_info_extractor.py
│   ├── credit_report_extractor.py
│   ├── vehicle_extractor.py
│   ├── wealth_product_extractor.py
│   ├── securities_extractor.py
│   ├── insurance_extractor.py
│   ├── immigration_extractor.py
│   ├── hotel_extractor.py
│   ├── railway_extractor.py
│   ├── flight_extractor.py
│   └── ...
│
├── wallet_data_extractor.py         # 电子钱包补充数据抽取
├── wallet_risk_analyzer.py          # 电子钱包预警增强
├── wallet_report_builder.py         # 电子钱包专项 TXT / Excel
│
├── report_generator.py              # HTML / Excel 报告生成
├── investigation_report_builder.py  # 主 TXT 报告构建器
├── specialized_reports.py           # 各专项报告
├── report_service.py                # 缓存读取与报告服务层
│
├── detectors/                       # 疑点检测插件
├── classifiers/                     # 交易分类器
├── learners/                        # 规则/学习结果辅助模块
├── schemas/                         # Pydantic / 报告数据结构
├── utils/                           # 安全类型、路径解释、通用工具
│
├── dashboard/                       # React 19 + TypeScript + Vite 前端
│   ├── src/components/
│   ├── src/contexts/
│   ├── src/services/
│   ├── src/types/
│   └── src/utils/
│
├── tests/                           # pytest
├── docs/                            # 设计、交付、变更日志
├── output/                          # 运行输出
└── dist/                            # Windows 离线打包产物
```

---

## 运行方式

### 开发态

```bash
# 后端
python api_server.py

# 前端开发服务器
cd dashboard
npm run dev
```

访问地址：

- 前端开发服务器：`http://localhost:5173/`
- 后端 API：`http://localhost:8000/`
- 后端承载生产前端：`http://localhost:8000/dashboard/`
- OpenAPI 文档：`http://localhost:8000/docs`

### 生产前端构建

```bash
cd dashboard
npm run build
```

构建产物输出到 `dashboard/dist/`，后端会直接承载它。

### Windows one-folder 打包

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-windows-build.txt
cd dashboard
npm install
npm run build
cd ..
python build_windows_package.py
```

默认产物位于 `dist/fpas-offline/`。

---

## 输入目录约定

### 银行主链数据

- 推荐放在用户选择的 `data/` 根目录下
- 程序会递归扫描个人、公司、银行、协查等常见目录

### 电子钱包补充数据

推荐目录：

```text
<inputDirectory>/补充数据/电子钱包/批次_YYYYMMDD/
```

支持的补充样本包括：

- 支付宝注册信息
- 支付宝账户明细
- 微信注册信息
- 微信登录轨迹
- 财付通注册信息
- 财付通交易明细

设计原则：

- 没有电子钱包目录时，主程序行为不变
- 有电子钱包目录时，只增强证据层与专项产物，不改写银行主链真源

---

## 技术栈

### 后端

- Python 3.9+
- FastAPI
- Uvicorn
- Pandas / NumPy
- OpenPyXL / XlsxWriter
- Jinja2
- chinese-calendar
- Neo4j 适配层（可选）

### 前端

- React 19
- TypeScript 5.9
- Vite 7
- Recharts
- vis-network
- Tailwind CSS 4
- Lucide React

### 工程约束

- 无互联网依赖
- 无 CDN 依赖
- 无硬编码绝对路径
- 前端生产构建由后端承载
- 兼容 PyInstaller one-folder

---

## 开发命令

```bash
# 后端
python api_server.py

# 前端
cd dashboard && npm run dev

# 类型检查
cd dashboard && npm run type-check

# 前端生产构建
cd dashboard && npm run build

# 测试
pytest tests/ -v
```

---

## 数据铁律

```text
任何 API、图谱、报告、统计口径，都必须以 output/cleaned_data 为基础，
并优先读取 output/analysis_cache 的已落盘结果。

原始 data/ 只负责输入，不允许在报告阶段绕过 cleaned_data/analysis_cache 直接重算并输出。
```

这条铁律对应的工程意义是：

- 防止页面口径与报告口径不一致
- 防止缓存与最终报告脱节
- 防止调试态“临时重算”污染正式产物

---

## 相关文档

- [WINDOWS_OFFLINE_DELIVERY.md](WINDOWS_OFFLINE_DELIVERY.md)
- [CHANGELOG.md](CHANGELOG.md)
- [docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md)
- [docs/change_logs](docs/change_logs)

---

## 当前 README 的边界

这个 README 主要解决四件事：

- 当前程序到底怎么跑
- 主链路模块现在怎么分工
- 输出目录现在到底会生成什么
- 几个核心算法大致怎么实现

更细的规则、阈值、专题报告格式和交付细节，请继续看对应代码与 `docs/` 下专项文档。
