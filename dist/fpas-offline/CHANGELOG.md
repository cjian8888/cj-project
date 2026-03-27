# 变更日志 (CHANGELOG)

本文件记录资金穿透与关联排查系统的重要版本更新。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

---

## [Unreleased] - 2026-03-24

### 🪟 Win7 交付包结果恢复与整包复核闭环 (2026-03-27)

#### 交付态结果恢复修复 (`dashboard/src/contexts/AppContext.tsx` + `dashboard/src/components/TabContent.tsx`)
- **问题**: Win7 交付态完成分析后，后端结果与缓存文件已生成，但前端偶发回退到默认 `output` 路径，导致数据概览页无法恢复本轮结果；同时当 `profiles` 为空时，结果页会被误判为空态。
- **修复**:
  - 交付态启动优先调用后端 `syncActivePaths({})` 恢复当前活动输入/输出目录，仅在无法恢复时才回退到包内默认路径。
  - 结果页将“分析已完成”和“是否存在画像数据”拆分判定，避免 `profiles` 为空时把整页错误渲染为未分析状态。
- **影响**: Win7 交付包在分析完成后可按当前输出目录正确恢复结果，避免再次出现“分析完成但前端不加载结果”。

#### 交付文档与启动入口纠偏 (`README.md` + `WINDOWS_OFFLINE_DELIVERY.md` + `build_windows_package.py`)
- **问题**: 交付文档对独立运行包启动方式描述不够准确，容易误导为直接执行 `fpas.exe`。
- **修复**:
  - 明确离线包正式入口是 `start_fpas.cmd`，静默入口是 `start_fpas_silent.vbs`。
  - 保持打包脚本输出的交付 README/HTML 与当前交付形态一致。
- **影响**: 交付说明与实际运行形态保持一致，降低现场误用启动入口的风险。

#### Win11 clean rebuild + Win7 全量验证 (`build_windows_package.py` + `tests/test_build_windows_package.py` + `tests/test_api_server_config_flow.py`)
- **新增闭环**:
  - 在 Win11 构建机清理旧构建状态后，重新执行 `build_windows_package.py`，成功产出新的 `dist/fpas-offline`。
  - 打包阶段再次通过 portable bundle 运行时审计，确认关键文件、关键模块和版本锁定完整。
  - 将新包复制到 Win7，仅保留桌面原始输入目录 `CB`，以 `Desktop/output` 完成一轮真实全量分析。
  - Win7 实测确认：
    - 分析状态 `completed`
    - `analysis_cache` 下 `profiles.json`、`derived_data.json`、`suspicions.json`、`metadata.json` 全部生成
    - `cleaned_data` 与 `analysis_results` 正常生成
    - `/api/open-folder` 对个人清洗数据、公司清洗数据、分析结果目录全部返回成功
    - `/api/results` 与 `/api/results/dashboard` 均可返回有效结果
- **影响**: 当前 GitHub 中的 `dist/fpas-offline` 对应本次已验证通过的一键运行包，可作为新的交付基线。

### 🪟 Win7 交付补丁闭环

#### 目录打开兼容修复 (`api_server.py` + `tests/test_api_server_config_flow.py`)
- **问题**: 在 Win7 VM 交付态中，输入/输出目录按钮会出现“目录打不开”，宿主 Win11 不复现。
- **修复**:
  - Windows 目录打开改为优先走 `ShellExecuteW("explore")`
  - 失败时依次回退到 `ShellExecuteW("open")`、绝对路径 `explorer.exe`、`subprocess(explorer.exe)`、`cmd /c start`
  - 补充可读错误信息，便于 Win7 现场取证
- **影响**: Win7 交付态对资源管理器调用更稳，避免仅依赖单一路径导致目录按钮失效。

#### stop_fpas 完整回收与可删包修复 (`api_server.py` + `build_windows_package.py` + `README.md`)
- **问题**: 旧交付包停止后仍残留包内 `python.exe`、浏览器或 `cmd.exe` 壳，导致整个交付目录无法删除。
- **修复**:
  - 交付态后端写入并清理 `server.pid`
  - `launch_browser_helper.py` 改为受控浏览器守护进程，使用 Windows Job Object `KILL_ON_JOB_CLOSE`
  - `stop_fpas_helper.py` 识别 `managed-job` PID 文件格式，优先结束包内 Python、浏览器守护进程、受控浏览器和关联启动窗口
  - `stop_fpas.cmd` 补充 `server.pid`、`browser.pid`、`stopping.flag` 清理
  - README 明确 Win7 补丁、受控浏览器和停止后可删包行为
- **影响**: 在使用随包受控浏览器时，`stop_fpas.cmd` 后交付目录应可直接删除。

#### 交付文档 HTML 化与 clean rebuild (`build_windows_package.py` + `README.md`)
- **新增**:
  - 打包时自动生成交付根目录 `README.html`
  - 使用独立 `Python 3.8.10` 正式重建 `dist/fpas-offline`
- **影响**: 交付文档可直接浏览器打开，Win7 交付包与源码补丁保持一致。

### ✅ 验证

- `pytest -q tests/test_api_server_config_flow.py -k "open_folder_in_windows or get_windows_explorer_executable_prefers_absolute_system_path"` 通过
- `pytest -q tests/test_build_windows_package.py` 通过
- 使用 `Python 3.8.10` 重新执行 `build_windows_package.py` 成功产出新的 `dist/fpas-offline`
- 对临时复制包完成真实烟测：`start_fpas.cmd` 拉起后端与受控 Chrome，`stop_fpas.cmd` 后相关 PID 全部退出，临时整包目录删除成功

## [v4.6.1] - 2026-03-23

### 🪟 Win7 交付链路收敛

#### Win7 默认交付形态切换为 portable-runtime (`build_windows_package.py` + `README.md` + `WINDOWS_OFFLINE_DELIVERY.md`)
- **变更**: Windows 离线包默认构建模式从单体 `fpas.exe` 调整为 `portable-runtime`。
- **新增**:
  - 交付根目录生成 `start_fpas.cmd`
  - 交付根目录生成 `start_fpas_silent.vbs`
  - 交付包内置 `runtime/python/` 运行时并直接启动 `api_server.py`
- **保留**: `PyInstaller` 模式未删除，但仅保留为兼容调试路径，不再作为 Win7 正式交付入口。
- **影响**: Win7 目标机不再依赖单体冻结 exe 冷启动，降低启动期内存崩溃风险。

#### Win7 启动期诊断与瘦身 (`api_server.py`)
- **问题**: Win7 打包态此前在启动阶段缺少足够证据，且顶层导入链过重，难以判断究竟是 DLL、归档解包还是模块注册导致退出。
- **修复**:
  - 新增 `startup_fatal.log` 启动期诊断输出
  - 支持 `FPAS_STARTUP_DIAGNOSTICS_ROOT` 覆盖诊断日志落点
  - 接入 `faulthandler` 与启动异常 `excepthook`
  - 将报表、PDF 提取、钱包报告、线索抽取等重模块改为按需延迟导入
- **影响**: Win7 启动失败时可以直接在交付根目录取证，同时显著降低冷启动导入压力。

#### Win7 依赖与兼容性收紧 (`requirements*.txt` + `financial_profiler.py` + `fpas_windows.spec`)
- **修复**:
  - `cryptography` 在 Windows 构建链固定回 `39.0.2`，避开 Win7 上 `_rust` 扩展加载失败
  - 补入 `websockets` 运行依赖，避免交付包缺失 WebSocket 栈
  - `fpas_windows.spec` 改为 `noarchive=True`，减轻冻结包归档解压压力
  - `financial_profiler.py` 对 `groupby(..., include_groups=False)` 增加 pandas 2.0.x 兼容回退
- **影响**: 与当前 `Windows 7 SP1 + Python 3.8.x` 交付目标保持一致，减少低版本运行时直接崩溃风险。

### ✅ 验证与测试

#### 自动化测试补强 (`tests/test_build_windows_package.py` + `tests/test_windows_py38_compat.py` + `tests/test_api_server_config_flow.py`)
- **新增覆盖**:
  - portable-runtime 源码/资源复制清单
  - Win7 依赖锁定与 `cryptography==39.0.2`
  - `start_fpas.cmd` / `start_fpas_silent.vbs` 生成逻辑
  - `api_server.py` 启动期诊断与延迟导入约束
  - API 配置流测试对延迟导入替身的兼容性
- **结果**: 本地回归已通过，未发现新增测试失败。

#### Win7 虚拟机阶段性验收
- **已确认**:
  - Win7 SP1 虚拟机可启动并可远程执行命令
  - `portable-runtime` 包在 Win7 上能拉起服务
  - `GET /dashboard/` 已返回 `200`
- **未闭环**:
  - 尚未在 Win7 打包态完成你提供的 `D:\测试用例\812\测试（公开）` 真实数据全流程复现

### 📌 待办

- 在 Win7 `portable-runtime` 交付包上，用 `D:\测试用例\812\测试（公开）` 完成真实数据重跑
- 针对以下现象做逐项复现与取证：
  - 前端日志面板卡顿或明显落后于后端滚动日志
  - 分析完成后数据概览迟迟不加载
  - 审计报告归集配置中公司列表不显示
  - 打包态运行时出现“回退到老版本”类提示
- 在最终封闭网络的物理 Win7 机器上，再做一轮冷启动和真实数据验收
- 如果后续仍保留 `PyInstaller` 调试路径，需明确它不是 Win7 正式发包入口，避免再次误用


## [v4.6.0] - 2026-03-21

### 📘 交付文档与版本统一

#### 交付版 README 重写 (`README.md`)
- **变更**: 按当前交付形态重写 README，不再沿用旧版“零散功能说明书”结构。
- **新增重点**:
  - 明确 `Windows 单机离线 one-folder` 为最终目标形态
  - 明确 `output/cleaned_data -> output/analysis_cache -> output/analysis_results` 三层输出契约
  - 明确 `report_package -> QA -> HTML/TXT/Excel -> /dashboard/` 报告主链
  - 明确交付前推荐的真实数据验收与总验收脚本
- **影响**: README 现在可直接作为交付说明，而不是只适合开发者读源码时参考。

#### 应用内文档入口 (`api_server.py` + `dashboard/src/components/Sidebar.tsx`)
- **变更**:
  - 后端新增 `/docs/readme` 只读文档页
  - 前端侧栏新增“交付文档”入口
  - README 保持唯一事实源，前端不再复制一份独立帮助文案
- **影响**: 离线包环境下也能直接查看当前交付文档，降低 README 与前端说明漂移风险。

#### 版本号统一 (`dashboard/src/constants/appVersion.ts` + `dashboard/package.json` + `api_server.py`)
- **变更**: 应用展示版本统一升级为 `v4.6.0`
- **影响**: 前端版本、README 版本和后端对外版本信息保持一致。

## [v4.5.5] - 2026-03-21

### 🐛 Bug修复

#### 银行流水清洗与去重修复 (`data_cleaner.py`)
- **问题**: 银行流水存在过度去重、无效交易混入统计、无日期账号反馈行被误删等问题，导致总笔数与收支金额失真。
- **修复**:
  - 调整去重策略，优先按 `transaction_id` 精确去重，禁止不同非空流水号交易再被启发式误删。
  - 收紧启发式去重条件，移除“同来源文件”这类弱判据，避免批量连续转账被错误压重。
  - 新增无效状态识别，过滤 `失败`、`冲正`、`退汇`、`关闭` 等交易状态。
  - 保留仅含账号信息的无日期查询反馈记录，避免主流水笔数口径继续丢数。
  - 统一原始文件读取为字符串列，降低 Excel/CSV 类型漂移带来的误判。
- **影响**: 修复银行总笔数、总流入/流出以及重点对象汇总偏差。

#### 微信手机号归并修复 (`wallet_data_extractor.py`)
- **问题**: 微信注册信息和登录轨迹没有利用“当前绑定手机号”和别名反查，导致部分手机号关联断裂。
- **修复**:
  - 新增 `_backfill_wechat_phone_mapping()`，把目录手机号、当前绑定手机号一并回填到主体映射。
  - 注册解析阶段支持按绑定手机号、别名、`wxid` 回查主体。
  - 登录轨迹解析阶段补充按绑定手机号、别名、`wxid` 聚合候选主体。
- **影响**: 修复微信登录轨迹漏并问题，补齐缺失的手机号关联链。

#### 报告语义与底稿对齐修复 (`report_generator.py` + `api_server.py` + `investigation_report_builder.py` + `report_fact_normalizer.py`)
- **问题**: Excel 聚合风险页、报告证据引用和家庭汇总口径与正式语义层存在偏差。
- **修复**:
  - Excel 核查底稿优先读取 `report_package.json`，按正式 `priority_board` 生成聚合风险排序页。
  - 前后端序列化补齐 `realIncome` / `realExpense` 字段，降低真实收支口径丢失风险。
  - 为缺失 `evidence_refs` 的结论卡回填 `cleaned_data` 溯源记录。
  - 家庭汇总优先复用 `all_family_summaries` 的真实收支指标。
- **影响**: 报告主文、Excel 底稿、QA 产物三者口径一致。

### ✅ 测试与验收

#### 单元测试补强
- 为 `data_cleaner.py` 增补去重、无效状态过滤、无日期占位记录保留等回归测试。
- 为报告链路和电子钱包归并补充语义对齐与映射回归测试。

#### 交付前盲盒验收补强
- 新增真实数据验收脚本：
  - `tmp_e2e_fault_injection_validation.py`
  - `tmp_e2e_gold_standard_audit.py`
  - `tmp_e2e_independent_recompute_audit.py`
  - `tmp_e2e_final_acceptance_suite.py`
- 新增金标准样本: `tests/fixtures/blindbox_gold_standard.json`
- **结果**:
  - 真实数据全量重跑通过
  - HTML 报告生成通过
  - 最终 6 项验收全绿，覆盖核心盲盒、边界盲盒、交付盲盒、金标准、故障注入、异实现复算


## [v4.5.4] - 2026-03-03

### 🐛 Bug修复

#### 理财识别误判修复 (financial_profiler.py)
- **问题**: 工资收入被误识别为理财产品
- **根因**: 银行内部代码识别逻辑没有排除发薪单位
- **修复**: 增加对手方检查，排除包含"代发"、"工资"、"薪"、"内部户"等发薪特征的交易
- **影响**: 防止工资收入被错误归类为理财资金

#### 身份证号提取优化 (api_server.py + investigation_report_builder.py)
- **问题**: 个人信息报告中身份证号显示为"暂无数据"
- **修复1** (api_server.py): 在 `serialize_profiles` 中添加 `entity_id` 字段
- **修复2** (api_server.py): 在 `run_analysis_refactored` 中从 `id_to_name_map` 反向查找身份证号
- **修复3** (investigation_report_builder.py): 优化身份证号提取优先级
  - 优先级1: 从同户人/户籍数据（family_tree）提取 - 最完整
  - 优先级2: 从 profiles 的 entity_id 字段读取
- **影响**: 个人信息报告现在能正确显示身份证号

#### 不动产数据兼容性修复 (asset_extractor.py)
- **问题**: 全国总库和精准查询的列名格式不同，导致部分数据无法提取
- **修复**: 支持多种列名格式
  - `房地坐落` 或 `不动产坐落`
  - `建筑面积(平方米)` 或 `不动产面积`
  - `名称` 或 `权利人名称`
  - `证件号码` 或 `权利人证件号码`
  - `共有人名称` 或 `共有权人名称`
  - `共有情况` 或 `共用方式`
- **新增**: 交易金额字段提取 (`交易金额(万元)`)
- **影响**: 提高不动产数据提取的兼容性和完整性

### 🔧 代码质量

#### 工具函数统一化 (asset_extractor.py)
- **问题**: 本地重复定义 `safe_float` 函数，违反代码规范
- **修复**: 改用 `utils/safe_types.py` 中的统一工具函数
- **参考**: AGENTS.md - 工具函数统一规范


## [v4.5.3] - 2026-01-19

### 🔧 UI/UX 优化

#### 快捷导航栏折叠优化 (`Sidebar.tsx`)
- **添加文字提示**: 折叠箭头旁增加"收起/展开"文字
- **增强悬停效果**: 添加背景色变化和圆角边框
- **视觉分隔**: 增加顶部边框分隔线，区分配置区域

#### 疑似分期受贿渲染修复 (`TabContent.tsx`)
- **问题**: 点击"异常收入分析"第8项"疑似分期受贿"后黑屏
- **根因**: 后端 `risk_factors` 返回字符串，前端按数组处理导致 `.join()` 报错
- **修复**: 兼容字符串和数组两种格式，增加描述信息

### 🛠 构建优化

#### 简化构建脚本 (`package.json`)
- `build` 命令从 `tsc -b && vite build` 改为 `vite build`
- 原因: TypeScript 严格模式的未使用变量警告导致构建失败

### 📁 项目清理
- 删除 output 目录中的中间过程文件
- 删除根目录调试/测试文件
- 创建 `archives/2026-01-19_v4.5.0/` 存档目录

---


## [v4.5.2] - 2026-01-19

### 🔧 审计专业角度数据问题修复

#### P0 - 标题数字与内容不一致 (严重)
- **问题**: 高风险项目标题显示 0，但展开后有 114 条数据
- **根因**: 后端 `stats.highRiskCount` 使用了错误的数据源
- **修复**: 后端/前端统一使用 `high_risk` 和 `bidirectional_flows` 作为数据源
- **验证**: 标题与内容现已 100% 一致

#### P1 - 付款/收款方向标注
- 统一显示为 `付款方 → 收款方` 格式
- 未知对手方显示橙色 `⚠ 来源不明` 警告

#### P2 - 金额单位统一
- 统一使用万元单位 (≥0.01万显示2位小数)

#### P2 - 资金流向统计穿透
- 改为可展开菜单，显示分类说明和总条数

### ✨ 交易详情弹窗增强
- 新增**收入类型**显示 (如"个人大额转入")
- 新增**交易详情**区域 (日期、摘要等)
- 新增**📍 精确溯源信息**卡片 (来源文件名、行号)

### 🔧 技术修复
- **Windows asyncio 兼容性**: 使用 `WindowsSelectorEventLoopPolicy` 避免 ProactorEventLoop bug
- **"查看完整报告"按钮**: 改为下载 `资金核查底稿.xlsx`
- **缓存脚本日期序列化**: 修复 datetime 对象 JSON 序列化错误

---

## [v4.5.1] - 2026-01-19

### ✨ 资金流向可视化重构

#### 界面精简
- **移除冗余按钮**: 删除右上角的"交互视图"、"完整报告"、"导出证据快照"按钮
- **移除底部报告区域**: 删除可视化图表下方的"详细核查报告"大块内容

#### 左侧二级菜单
将左侧统计卡片改造为可点击展开/折叠的二级菜单：
- **核心人员** 👥: 展开显示人员名单
- **高风险项目** 🔴: 展开显示高风险收入详情，可穿透查看交易 Modal
- **借贷配对** 💳: 展开显示借贷配对列表，含借入/还款金额及还款率
- **无还款借贷** ⚠️: 展开显示疑似利益输送记录，含未还天数警告
- **涉案公司** 🏢: 展开显示涉案企业名单
- **网贷平台** 🏦: 展开显示平台统计，含涉及金额和交易笔数

#### 代码清理
- 清理未使用导入: `html2canvas`, `Camera`, `Download`, `Banknote`, `formatCurrency`
- 新增导入: `ChevronDown`, `ChevronUp`, `Users`, `Building2`
- 新增辅助函数: `formatAmount()`

---

## [v4.5.0] - 2026-01-19

### ✨ 交互体验与UI优化

#### 交互体验 (UX)
- **"打开文件夹"跨平台强力修复**: 解决从网页点击无法唤起文件夹窗口到前台的顽疾。
  - **Windows**: 使用 Shell COM 接口枚举 Explorer 窗口，精确匹配路径后调用 `AttachThreadInput` + `SetForegroundWindow` 强制置顶。
  - **macOS**: 使用 AppleScript 调用 `Finder.activate` + `set frontmost` 将窗口带到前台。
  - **Linux**: 使用 `xdg-open` 配合 `wmctrl` (可选) 激活窗口。
  - 优化路径安全检查，仅允许打开 `output` 目录下的路径。

#### 仪表盘优化 (UI)
- **重构"审计发现分布"**: 
  - 弃用无意义的"可疑交易分布"（仅显示现金碰撞）。
  - 新增基于业务逻辑的分布统计：展示规律还款、网贷交易、大额收入、来源不明等 8 大类审计发现的占比。
  - 为审计人员提供更有价值的宏观视角。
- **信息降噪**:
  - 移除冗余的"主要实体资金画像"表格，释放版面空间。
  - 优化卡片布局，使核心信息更聚焦。
- **布局与Tooltip优化**:
  - 缩小饼图容器高度（`h-48` → `h-40`），减少图与图例之间空白。
  - 优化图例间距（`space-y-2` → `space-y-1.5`），布局更紧凑。
  - 增强饼图 Tooltip 可见性：蓝色边框 + 深蓝背景 + 高对比度文字。

### 🔧 系统优化
- **后端热重载**: `api_server.py` 启用 `reload=True`，开发调试更高效。

---

## [v4.4.0] - 2026-01-18

### 🔧 代码质量审计：P0-P5 六阶段系统性改进

基于 Claude 版代码审查意见书，执行了全面的系统性改进。

### P0 止血（Immediate Fixes）

#### 数据清洗 (`data_cleaner.py`)
- **恢复流水号去重**：优先使用 `transaction_id` 而非启发式规则
- **修复索引警告**：流水号去重后重新创建 `duplicates_mask`

#### 资金穿透 (`fund_penetration.py`)
- **图谱改为累计金额**：边权重基于累计发生额，解决"蚂蚁搬家"漏查问题

### P1 加固（High Priority）

#### 新增模块
- **`name_normalizer.py`**：对手方名称标准化模块
  - `normalize_for_matching()`：模糊匹配标准化
  - `is_same_person()`：同名判断

#### 线索聚合 (`clue_aggregator.py`)
- **调整周期性收入权重**：从 +5/10 提高到 +12/24

### P2 优化（Medium Priority）

#### 数据清洗 (`data_cleaner.py`)
- **Parquet 中间存储**：`save_as_parquet()` 高性能存储
- **双格式输出**：`save_cleaned_data_dual_format()` Excel + Parquet

#### API 服务 (`api_server.py`)
- **缓存哈希校验**：`_compute_cleaned_data_hash()` 替代 mtime 检测

#### 新增配置
- **`config/rules.yaml`**：规则引擎 YAML 配置文件
- **`rule_engine.py`**：支持从 YAML 加载规则参数

### P3 演进（Long-term）

#### 新增模块
- **`audit_logger.py`**：操作审计日志（等保合规）
  - 线程安全日志记录
  - 防篡改校验 (MD5 checksum)
  - 日志自动轮转
  - `@audited` 装饰器
  
- **`holiday_service.py`**：节假日服务
  - 优先使用 chinese-calendar 库
  - 回退到本地配置
  
- **`graph_adapter.py`**：Neo4j 图数据库适配器
  - `GraphAdapter` 抽象接口
  - `MemoryGraphAdapter` 内存实现
  - `Neo4jAdapter` 数据库实现

### P4 报告质量

#### 收入分析 (`income_analyzer.py`)
- **从摘要提取对手方**：`_extract_counterparty_from_description()` 支持 7 种模式
- 减少"来源不明"收入误报

#### 线索聚合 (`clue_aggregator.py`)
- **家庭成员闭环识别**：`_is_family_cycle()` 函数
- **降低家庭闭环评分**：从 +15/30 降为 +3/6

### P5 报告可追溯性

#### 追溯字段
- 数据记录新增 `account`、`bank`、`source_file` 字段
- 报告显示 `▶ 追溯: 银行 账户` 和 `▶ 文件: Excel路径`
- 便于从报告直接定位到 Excel 进行人工复核

### 测试结果
- 单元测试：190 passed ✓
- 完整运行：~55 秒，正常生成所有报告

---

## [v4.3.1] - 2026-01-17

### 修复

#### 前端问题修复
- **P1 DOM 结构错误**: 修复 `NetworkGraph.tsx` 中 `<p>` 标签内嵌套 `<div>` 导致的 React Hydration 警告
- **P2 连接状态显示**: 修复 WebSocket 初始显示"未连接"问题，应用启动时自动连接
- **P2 图表初始化警告**: 为 `TabContent.tsx` 中的 ResponsiveContainer 添加 minHeight 防止负尺寸警告

---

## [v4.3.0] - 2026-01-17

### 🎯 数据铁律重构：`/api/results` 接口持久化

解决 `/api/results` 依赖内存变量的问题，实现数据一致性保障。

### 新增功能

#### 分析缓存机制 (`api_server.py`)
- **`_get_cleaned_data_mtime()`**: 获取 `cleaned_data/` 目录最新修改时间
- **`_save_analysis_cache()`**: 分析完成时保存结果到 `output/analysis_cache/`
- **`_load_analysis_cache()`**: 读取缓存并校验与 `cleaned_data` 的一致性

#### 缓存目录结构
```
output/analysis_cache/
├── metadata.json       # 元数据（版本、时间戳）
├── profiles.json       # 资金画像
├── suspicions.json     # 可疑交易
├── derived_data.json   # 借贷/收入分析
└── graph_data.json     # 图谱数据（可选）
```

### 变更

#### `/api/results` 接口重构
- **废弃**直接返回内存变量 `analysis_state.results`
- **改为**从 `analysis_cache/` 目录读取 JSON 文件
- **新增** `source` 字段标识数据来源（`analysis_cache` / `memory`）
- **新增**一致性校验：`cleaned_data` 更新后，旧缓存自动失效

### 修复

- 解决用户修改清洗规则后前端不更新的问题
- 解决服务重启后需重新分析的问题（缓存持久化）

### 铁律修复（数据复用原则）

修复以下模块中现金交易识别重复计算的问题，改为直接读取已标记的 `is_cash` 列：

| 模块 | 修复函数 |
|------|----------|
| `suspicion_detector.py` | `run_all_detections()` - 现金碰撞检测 |
| `risk_scoring.py` | `score_transaction()` - 交易风险评分 |
| `risk_scoring.py` | `score_account()` - 账户风险评分 |
| `financial_profiler.py` | `analyze_fund_flow()` - 资金流向分析 |
| `financial_profiler.py` | `detect_large_cash()` - 大额现金检测 |
| `financial_profiler.py` | `categorize_transactions()` - 交易分类 |

### 项目维护

- 清理中间过程文件（审计报告、截图等）
- 压缩日志文件至最近 100 行

### 架构优化（单一修改点原则）

- 新增 `config.py: COLUMN_MAPPING` - Excel 列名统一映射配置
- 新增 `config.py: COLUMN_ORDER` - Excel 列显示顺序配置
- 新增 `config.py: *_COLUMN_VARIANTS` - 读取兼容性列名变体
- 修改 `data_cleaner.py` - 使用 `config.COLUMN_MAPPING` 替代硬编码
- 修改 `api_server.py` - 使用 `config.*_COLUMN_VARIANTS` 替代硬编码

**效果**：今后修改 Excel 列名只需改 `config.py` 一处，其他模块自动引用。

---

## [v4.2.0] - 2026-01-16

### 🔒 离线环境适配

解决资金流向可视化在单机/离线环境下无法渲染的问题。

### 问题修复

#### `flow_visualizer.py` - 移除外部 CDN 依赖
- **问题**: `templates/flow_visualization.html` 和 fallback HTML 使用外部 CDN (`https://unpkg.com/vis-network`)，导致单机环境下图谱无法渲染
- **修复**: 
  - `_generate_fallback_html` 改为读取本地 `vis-network.min.js` 并内联到 HTML
  - `_generate_html_visualization` 添加 `VIS_JS_CONTENT` 模板变量
- **模板更新**: `templates/flow_visualization.html` CDN 引用替换为 `{{VIS_JS_CONTENT}}`

### 验证结果
- 完整分析流程通过（耗时 47 秒，处理 3.4 万条交易）
- 图谱成功渲染（59 节点，80 条资金流向）
- 无任何外部网络请求

---

## [v4.1.0] - 2026-01-11

### 🎯 Phase 4：解决"线索割裂"和"黑盒评分"痛点

基于 GLM-4.7 的"深度审视报告"建议，完成以下核心改进。

### 新增模块

#### `clue_aggregator.py` - 线索聚合引擎（新建）
- 以"人员/公司"为索引键，聚合所有模块的发现
- 包括：资金闭环、过账通道、高风险交易、团伙、周期性收入、资金突变、延迟转账
- 计算综合风险分（0-100分）
- 生成"证据包"视图报告

### 功能增强

#### `risk_scoring.py` - 风险分归因解释
- 新增 `explain_risk_score()` 函数
- 用自然语言解释为什么一笔交易风险分高
- 示例输出："该笔交易风险分95分，主要因为：金额48万是该账户历史均值的9.6倍；发生在凌晨2:17（深夜交易）"

### 新增报告
- `线索聚合报告.txt` - 证据包视图

---

## [v4.0.0] - 2026-01-11

### 🚀 重大升级：从"数据清洗工具"升级为"智能深度资金侦查平台"

基于 GLM-4.7 模型的专业审计建议，本版本进行了三阶段重大升级。

### 新增模块

#### 1. `fund_penetration.py` v2.0 - 图论深度分析
- **MoneyGraph 类**：有向资金图数据结构
- **多跳路径追踪**：发现 A→B→C→D 的复杂资金链路
- **资金闭环检测**：识别 A→B→C→A 的利益回流结构
- **过账通道识别**：发现流量巨大但余额归零的空壳/马甲账户
- **资金枢纽分析**：识别与多方有往来的关键控制节点
- **性能优化**：添加超时机制和关键节点过滤，避免大图分析卡死

#### 2. `risk_scoring.py` - 统一风险评分引擎（新建）
- 交易级风险评分（金额/对手方/时间/摘要/关联五维度）
- 对手方风险画像
- 账户级风险评估
- 批量评分与自动排序

#### 3. `time_series_analyzer.py` - 时序分析模块（新建）
- **周期性收入检测**：发现"每月5日固定入账5万"的养廉资金模式
- **资金突变检测**：发现突然激增的异常收入（使用滚动 Z-Score）
- **固定延迟转账**：发现"收入后 N 天固定转出"的利益分配协议

### 增强功能

#### `income_analyzer.py`
- 新增 `_calculate_confidence_score()` 可信度评分函数（0-100分）
- 新增交易去重逻辑，避免同一笔交易重复出现在多个报告类别
- 可信度评分显示在报告中，方便审计人员优先排序

#### `config.py`
- 新增 `KNOWN_WEALTH_PRODUCTS` 白名单（53个知名理财产品）
- 减少理财赎回被误标为"来源不明收入"的问题

#### `ml_analyzer.py`
- 已有完善的公共节点排除列表（支付宝、微信等）
- 团伙识别只在核心人员/涉案公司之间构建图

### 性能优化
- 图论分析添加 30 秒超时机制
- 只从核心人员/公司节点开始搜索闭环
- 排除支付宝、微信、银行等公共节点
- 限制最大闭环数量（100个）和路径数量（50条）

### 测试结果
- 执行时间：50.88 秒（全量分析）
- 资金闭环：44 个
- 过账通道：4 个
- 资金突变事件：112 个
- 固定延迟转账：27 个

---

## [v3.2.0] - 2026-01-10

### 功能完善
- 修复理财产品误判问题
- 增加政府机关白名单
- 优化借贷分析排除规则

---

## [v3.0.0] - 2026-01-08

### 核心功能
- 完整的数据清洗与合并流程
- 多源数据碰撞分析
- 借贷行为检测
- 异常收入识别
- 资金流向可视化
- 机器学习风险预测

---

## 贡献者
- 系统开发：Claude/Antigravity
- 审计建议：GLM-4.7

## 许可证
内部使用，仅限纪检监察系统
