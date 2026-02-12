# Profiles 数据流改进方案

## 问题背景

### 为什么会有两个 profiles 文件？

| 文件 | 大小 | 数据来源 | 用途 | 数据结构 |
|------|------|----------|------|----------|
| `profiles.json` | 3.5 KB | `serialize_profiles()` 函数 | 前端展示 | 扁平化 camelCase |
| `profiles_full.json` | 44 MB | 原始分析数据 | 报告生成 | 嵌套 snake_case |

### 设计初衷

```python
# api_server.py 第 1543-1551 行
analysis_state.results = {
    "profiles": serialize_profiles(profiles),      # → profiles.json (前端用)
    "_profiles_raw": profiles,                       # → profiles_full.json (后端用)
    ...
}
```

**原始意图**：前端需要扁平化结构方便展示，后端需要完整嵌套结构进行报告生成。

### 实际存在的问题

1. **`serialize_profiles()` 缺失关键字段**
   - 没有序列化 `yearly_salary` 字段
   - 没有序列化 `summary`、`fund_flow` 等嵌套结构

2. **验证逻辑错误**
   - `investigation_report_builder.py` 第 8247 行检查 `totalIncome`，但 `profiles_full.json` 使用的是 `summary.total_income`

3. **多处重复实现"降级加载"逻辑**
   - `_build_salary_income_v4` 方法
   - `_build_bank_accounts` 方法
   - `_build_family_summary_v4` 方法
   - 初始化加载逻辑

4. **字段命名混乱**
   - 简化版：`yearlySalary` (不存在), `totalIncome`
   - 完整版：`yearly_salary`, `summary.total_income`

---

## 改进方案（已实施）

### 核心思想

**统一数据结构**：只保留一个 `profiles.json`，同时包含：
1. 前端需要的扁平化字段（兼容现有前端代码）
2. 后端需要的完整原始数据（供报告生成器使用）

### 修改内容

#### 1. 修改 `api_server.py` - `serialize_profiles()` 函数

```python
# 构建前端期望的扁平化结构（同时保留完整原始数据）
frontend_profile = {
    # === 前端扁平字段（camelCase）===
    "entityName": name,
    "totalIncome": summary.get("total_income", 0),
    "totalExpense": summary.get("total_expense", 0),
    ...
    
    # === 后端完整数据（snake_case）===
    "entity_name": profile_dict.get("entity_name", name),
    "summary": summary,
    "income_structure": income_structure,
    "fund_flow": fund_flow,
    "yearly_salary": profile_dict.get("yearly_salary", {}),
    "bank_accounts": profile_dict.get("bank_accounts", []),
    ...
}
```

#### 2. 简化 `investigation_report_builder.py` 加载逻辑

**修改前**：
```python
# 优先加载 profiles_full.json，失败再回退到 profiles.json
if key == "profiles":
    # 尝试加载完整版
    if os.path.exists("profiles_full.json"):
        profiles_full = json.load(f)
        if profiles_full[first_person].get("totalIncome"):  # 错误：使用 camelCase 检查
            use profiles_full
    # 回退到简化版
    use profiles.json
```

**修改后**：
```python
# 统一使用 profiles.json，验证逻辑同时支持两种字段名
if key == "profiles":
    profiles = json.load(f)
    if profiles[first_person].get("totalIncome") or \
       profiles[first_person].get("summary", {}).get("total_income"):
        use profiles
```

#### 3. 移除冗余的降级加载逻辑

删除了以下方法中的 `profiles_full.json` 降级加载代码：
- `_build_salary_income_v4()`
- `_build_bank_accounts()`
- `_build_family_summary_v4()`

#### 4. 创建数据升级脚本

`scripts/update_profiles_unified.py`：
- 将现有的 `profiles.json` 从简化版升级为统一版
- 创建备份 `profiles.json.backup`
- 合并 `profiles_full.json` 的完整数据

---

## 改进效果

### 文件对比

| 文件 | 修改前 | 修改后 |
|------|--------|--------|
| `profiles.json` | 3.5 KB（简化版） | 44 MB（统一版） |
| `profiles_full.json` | 44 MB（完整版） | 仍然存在（向后兼容） |

### 代码简化

| 指标 | 修改前 | 修改后 |
|------|--------|--------|
| 降级加载逻辑处数 | 4 处 | 0 处 |
| 需要维护的文件数 | 2 个 | 1 个（主要） |
| 字段命名风格 | 混乱 | 统一 |

### 数据验证

```
=== 验证报告数据 ===
年份出现次数: 71
从业单位: 2 个
收入来源结构分析: 4
五维度综合评分: 4

=== 改进成功 ===
✓ 统一使用 profiles.json
✓ 移除了降级加载逻辑
```

---

## 后续建议

### 1. 长期规划

考虑完全移除 `profiles_full.json`：
- 当前保留是为了向后兼容
- 确认所有代码都迁移到统一版后，可以删除

### 2. 缓存管理器优化

`cache_manager.py` 可以简化：
```python
# 当前
CACHE_FILES = {
    "profiles": "profiles.json",
    "profiles_full": "profiles_full.json",  # 可以移除
    ...
}

# 优化后
CACHE_FILES = {
    "profiles": "profiles.json",
    ...
}
```

### 3. 文档更新

更新 `AGENTS.md` 和 `docs/` 目录下的文档，说明：
- `profiles.json` 现在包含完整数据
- 不再需要同时维护两个文件
- 新代码应该使用 `profiles.json`

---

## 总结

**根本问题**：`serialize_profiles()` 函数过度简化，剔除了后端需要的字段，导致必须维护两个文件。

**解决方案**：让 `serialize_profiles()` 保留完整原始数据，同时添加前端需要的扁平字段，实现"一份数据，两种用途"。

**收益**：
- 消除数据不一致问题
- 简化代码逻辑
- 减少维护成本
- 避免未来再次犯错
