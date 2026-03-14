# HTML报告数据流分析报告

## 执行摘要

**问题**: HTML报告始终为空（家庭成员数为 0，财务数据为 0）  
**根本原因**: `family_units_v2` 数据在 Phase 8 保存缓存时丢失  
**影响范围**: 完整报告生成流程  
**严重程度**: 🔴 高优先级（阻断功能）

---

## 1. 完整函数调用链

### 1.1 入口点
```
run_analysis_refactored() [api_server.py:571]
  ├─ Phase 1-7: 数据清洗 → 外部数据提取 → 融合画像 → 全面分析 → 疑点检测
  │   └─ analysis_results["family_units_v2"] = family_units_list  [api_server.py:1219]
  │
  └─ Phase 8: 报告生成 [api_server.py:1432-1490]
      │
      ├─ 1️⃣ 加载报告构建器
      │   load_investigation_report_builder(output_dir) [api_server.py:1447]
      │   └─ investigation_report_builder.py:7416
      │       └─ 从分散缓存文件加载:
      │           - profiles.json → analysis_cache["profiles"]
      │           - derived_data.json → analysis_cache["derived_data"]
      │           - suspicions.json → analysis_cache["suspicions"]
      │           - graph_data.json → analysis_cache["graph_data"]
      │
      ├─ 2️⃣ 加载归集配置
      │   config_service.get_or_create_config() [api_server.py:1456]
      │   └─ 读取 data/primary_targets.json (存在 ✓)
      │
      ├─ 3️⃣ 生成报告
      │   builder.build_report_with_config(config) [api_server.py:1466]
      │   └─ investigation_report_builder.py:445
      │       ├─ 读取 self.derived_data["family_units_v2"]
      │       └─ ❌ 缺失！值为空 {}
      │
      ├─ 4️⃣ 渲染HTML
      │   _render_report_to_html(report) [api_server.py:1473]
      │   └─ api_server.py:2548
      │       └─ 使用 report["family"]["summary"] (为空)
      │
      └─ 5️⃣ 保存HTML
          write 初查报告_v4.html [api_server.py:1476]
```

### 1.2 缓存保存流程
```
_save_analysis_cache_refactored(results, cache_dir) [api_server.py:1671]
  └─ cache_mgr.save_results(results) [cache_manager.py:211]
      └─ 分析 results 字典中的键:
          - profiles ✅ → save_cache("profiles", results["profiles"])
          - analysisResults ❌ → save_cache("derived_data", results["analysisResults"])
          - graphData ✅ → save_cache("graph_data", results["graphData"])
          - externalData ✅ → 保存为 separate cache files
          - ❌ 缺少 family_units_v2 (不在 results 中!)
```

---

## 2. 关键数据流图

### 2.1 当前流程（❌ 数据丢失）

```
Phase 6 家庭分析
  ├─ family_analyzer.build_family_units() → family_units_list [api_server.py:1210]
  ├─ family_analyzer.get_family_summary() → family_summary [api_server.py:1214]
  └─ analysis_results["family_units_v2"] = family_units_list  ✅ 已生成
         ↓
Phase 8 报告生成
  ├─ load_investigation_report_builder()
  │   └─ 读取 analysis_cache["derived_data"]
  │       └─ ❌ family_units_v2 字段缺失！
  │
  ├─ builder.build_report_with_config()
  │   ├─ self.derived_data.get("family_summary", {})  ✅ 存在
  │   └─ self.derived_data.get("family_units_v2", []) ❌ 空数组！
  │
  ├─ _render_report_to_html()
  │   └─ report["family"]["summary"] → 家庭汇总为 0
  │
  └─ 保存 HTML → 报告为空
         ↓
缓存保存
  ├─ analysis_state.results["profiles"] ✅
  ├─ analysis_state.results["analysisResults"] ✅
  ├─ analysis_state.results["graphData"] ✅
  └─ analysis_state.results["family_units_v2"] ❌ 缺失！
```

---

## 3. 潜在数据丢失点（3个）

### 🔴 点1: 分析结果传递缺失（最关键）

**位置**: api_server.py:1340  
**问题描述**: 
```python
derived_data = {
    "loan": analysis_results.get("loan", {}),
    "income": analysis_results.get("income", {}),
    "time_series": analysis_results.get("timeSeries", {}),
    "large_transactions": analysis_results.get("large_transactions", []),
    "family_summary": analysis_results.get("family_summary", {}),  # ✅
    "family_relations": analysis_results.get("family_relations", {}),  # ✅
    # ❌ 缺少 "family_units_v2" 字段！
}
analysis_state.results["analysisResults"] = derived_data  # 缓存保存
```

**影响**:
- `InvestigationReportBuilder` 从 `analysis_cache["derived_data"]` 读取
- `family_units_v2` 字段缺失 → 家庭成员数据为空
- 报告生成时无法构建家庭单元结构

**修复方案**:
```python
derived_data = {
    "loan": analysis_results.get("loan", {}),
    "income": analysis_results.get("income", {}),
    "time_series": analysis_results.get("timeSeries", {}),
    "large_transactions": analysis_results.get("large_transactions", []),
    "family_summary": analysis_results.get("family_summary", {}),
    "family_relations": analysis_results.get("family_relations", {}),
    "family_units_v2": analysis_results.get("family_units_v2", []),  # ✅ 添加
}
```

---

### 🟡 点2: 缓存文件缺失

**位置**: output/analysis_cache/  
**问题描述**:
```bash
$ ls -lh output/analysis_cache/
total 0  # ❌ 空目录

$ test -f output/analysis_results_cache.json
NOT EXISTS  # ❌ 完整缓存文件不存在
```

**影响**:
- `load_investigation_report_builder()` 回退到分散缓存文件
- 如果分散缓存文件不存在或内容不完整，报告构建失败

**修复方案**:
确保 `_save_analysis_cache_refactored()` 正常执行：
```python
def _save_analysis_cache_refactored(results, cache_dir):
    try:
        cache_mgr = CacheManager(cache_dir)
        cache_mgr.save_results(results)  # ✅ 确保保存成功
        logger.info(f"✓ 缓存已保存: {cache_dir}")
    except Exception as e:
        logger.error(f"✗ 保存缓存失败: {e}")  # ✅ 检查错误日志
```

---

### 🟡 点3: 缓存文件命名不匹配

**位置**: cache_manager.py:29 vs investigation_report_builder.py:7416  

**问题描述**:
- `CacheManager.save_results()` 保存为 `derived_data.json` (cache_manager.py:29)
- `InvestigationReportBuilder` 期望从 `analysis_cache["derived_data"]` 读取
- 但 `load_investigation_report_builder()` 回退时使用 `derived_data` 作为键 (line 7462)

**代码验证**:
```python
# cache_manager.py:29
CACHE_FILES = {
    "profiles": "profiles.json",
    "profiles_full": "profiles_full.json",
    "suspicions": "suspicions.json",
    "derived_data": "derived_data.json",  # ✅ 正确
    "graph_data": "graph_data.json",
    "metadata": "metadata.json",
    "analysis_results": "analysis_results.json",
}

# investigation_report_builder.py:7462
cache_files = {
    "profiles": "profiles.json",
    "derived_data": "derived_data.json",  # ✅ 匹配
    "suspicions": "suspicions.json",
    "graph_data": "graph_data.json",
    "metadata": "metadata.json",
}
```

**结论**: ✅ 命名匹配，这不是问题

---

## 4. 证据链

### 4.1 代码证据

**api_server.py:1219** - Phase 6 确实生成了 family_units_v2
```python
family_units_list = family_analyzer.build_family_units(
    all_persons, data_dir
)
analysis_results["family_units_v2"] = family_units_list  # ✅ 有数据
```

**api_server.py:1340** - 但保存到 results 时缺少这个字段
```python
derived_data = {
    "loan": ...,
    "income": ...,
    "time_series": ...,
    "large_transactions": ...,
    "family_summary": ...,
    "family_relations": ...,
    # ❌ 缺少 family_units_v2
}
```

**api_server.py:1572** - cache_mgr.save_results() 依赖这个 results 字典
```python
_save_analysis_cache_refactored(
    analysis_state.results, output_dirs["analysis_cache"]
)
```

**investigation_report_builder.py:7462** - 构建器期望读取 derived_data
```python
family_yearly_salary = []
family_units = self.derived_data.get("family_units_v2", [])  # ❌ 空数组！
```

### 4.2 文件系统证据

```bash
$ ls -lh output/analysis_cache/
total 0  # ❌ 缓存目录为空

$ ls -lh output/analysis_results/
total 0  # ❌ 报告目录为空
```

这证实了缓存保存失败或内容为空。

---

## 5. 修复优先级

| 优先级 | 位置 | 问题 | 修复难度 | 影响 |
|--------|------|------|----------|------|
| 🔴 P0 | api_server.py:1340 | 缺少 family_units_v2 字段 | 简单（3行代码） | 中断功能 |
| 🟡 P1 | cache_manager.py:211 | save_results() 错误处理 | 中等（需验证） | 防止重复问题 |
| 🟡 P2 | api_server.py:1572 | 调试日志增强 | 简单（增加日志） | 便于后续排查 |

---

## 6. 下一步行动

### 立即执行（P0）
1. **修改 api_server.py:1340**，在 `derived_data` 字典中添加 `family_units_v2`
2. **重新运行分析**，验证缓存是否正常保存
3. **检查输出** `output/analysis_cache/` 是否包含文件

### 短期执行（P1）
1. **增强缓存保存日志**，添加详细的错误堆栈
2. **验证分散缓存文件**是否正常生成
3. **检查 primary_targets.json** 是否正确加载

### 长期优化（P2）
1. **统一缓存命名**，确保所有缓存键命名一致
2. **添加缓存完整性验证**，保存前检查关键字段
3. **重构缓存保存逻辑**，使用 `investigation_report_builder` 的缓存结构

---

## 7. 测试验证

修复后，执行以下验证：

```bash
# 1. 重新运行分析
# 2. 检查缓存文件
ls -lh output/analysis_cache/
# 期望: profiles.json, derived_data.json, suspicions.json, graph_data.json

# 3. 检查 derived_data.json 内容
cat output/analysis_cache/derived_data.json | grep family_units_v2
# 期望: "family_units_v2": [...]

# 4. 生成 HTML 报告
# 5. 打开 初查报告_v4.html
# 期望: 家庭成员数 > 0，家庭财务汇总 > 0
```

---

## 附录: 完整文件位置

| 文件 | 关键行号 | 关键函数 |
|------|---------|---------|
| `api_server.py` | 571 | `run_analysis_refactored()` |
| `api_server.py` | 1210-1219 | Phase 6 家庭分析 |
| `api_server.py` | 1340 | 保存 derived_data |
| `api_server.py` | 1447-1476 | Phase 8 报告生成 |
| `api_server.py` | 1671 | `_save_analysis_cache_
