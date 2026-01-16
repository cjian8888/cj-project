# Phase 0: 深度逻辑扫描报告

**执行时间**: 2026-01-16 14:50
**状态**: 分析完成

---

## 问题 1: 关于路径 (The Path Logic)

### 数据流追踪

#### 1. 前端输入路径的传递
**位置**: `AppContext.tsx` → `api.startAnalysis()`
```typescript
await api.startAnalysis({
    inputDirectory: config.dataSources.inputDirectory,
    outputDirectory: config.dataSources.outputDirectory,  // 用户输入
    cashThreshold: config.thresholds.cashThreshold,
    timeWindow: config.thresholds.timeWindow,
    modules: modules,
});
```

#### 2. 后端接收路径
**位置**: `api_server.py` 第254-263行
```python
@app.post("/api/analysis/start")
async def start_analysis(config: AnalysisConfig, background_tasks: BackgroundTasks):
    # 接收到 config.outputDirectory
    background_tasks.add_task(run_analysis, config)
```

#### 3. 后端存储路径
**位置**: `api_server.py` 第450-648行 `run_analysis()` 函数
```python
def run_analysis(analysis_config: AnalysisConfig):
    data_dir = analysis_config.inputDirectory
    output_dir = analysis_config.outputDirectory  # 第459行
    
    # 创建输出目录
    output_dirs = create_output_directories(output_dir)  # 第480行
    
    # ⚠️ 但是！路径只在函数内部使用，没有保存到 analysis_state
```

**关键发现**: `AnalysisState` 类（第112-162行）**没有** `output_dir` 属性！
```python
class AnalysisState:
    def __init__(self):
        self.status = "idle"
        self.progress = 0
        self.current_phase = ""
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.results: Optional[Dict] = None  # 只存结果，不存路径
        self.lock = threading.Lock()
```

#### 4. 读取图谱数据时的路径
**位置**: `api_server.py` 第318-425行 `get_graph_data()`
```python
@app.get("/api/analysis/graph-data")
async def get_graph_data():
    # 第331行：使用硬编码的 config.DATA_DIR
    data_dir = config.DATA_DIR  # ⚠️ 这是写死的 "./data"
    categorized_files = file_categorizer.categorize_files(data_dir)
```

### 🔴 结论 1: 为什么前端会报 404？

**根本原因**: **路径失忆症 (Path Amnesia)**

1. 用户在前端输入 `outputDirectory: "D:/my_output"`
2. 后端 `run_analysis()` 收到路径，生成文件到 `D:/my_output/`
3. 但 `analysis_state` **没有保存** `output_dir`
4. 前端请求 `/api/analysis/graph-data` 时
5. 后端从 `config.DATA_DIR` (写死的 `./data`) 读取
6. 找不到文件 → **404 错误**

**证据链**:
- `run_analysis()` 使用 `analysis_config.outputDirectory` ✅
- `AnalysisState` 没有 `output_dir` 属性 ❌
- `get_graph_data()` 使用 `config.DATA_DIR` (硬编码) ❌

---

## 问题 2: 关于实体 (The Entity Logic)

### "系统检测" 字符串的来源

**位置**: `api_server.py` 第662-739行 `_enhance_suspicions_with_analysis()`

#### 发现 3 处硬编码:

1. **第682行** - 资金突变记录:
```python
enhanced["direct_transfers"].append({
    "person": change.get("entity", ...),
    "company": "系统检测",  # ⚠️ 硬编码
    "description": "资金突变: income_spike",
    ...
})
```

2. **第696行** - 延迟转账记录:
```python
enhanced["direct_transfers"].append({
    "person": dt.get("source_person", ...),
    "company": dt.get("target_person", "系统检测"),  # ⚠️ 默认值
    ...
})
```

3. **第710行** - 周期性收入记录:
```python
enhanced["direct_transfers"].append({
    "person": pi.get("entity", ...),
    "company": pi.get("counterparty", "系统检测"),  # ⚠️ 默认值
    ...
})
```

### 前端图谱节点渲染逻辑

**位置**: `NetworkGraph.tsx` 第307-324行

```typescript
const processedNodes = graphData.nodes.map(node => {
  let nodeSize = node.size || 20;
  // ... 计算大小 ...
  
  return {
    id: node.id,
    label: node.label,  // ⚠️ 直接使用后端的 label，没有格式化！
    value: nodeSize,
    size: nodeSize,
    group: node.group,
    title: `【${node.label}】\n${getGroupLabel(node.group || 'other')}`
  };
});
```

**关键发现**: 
- 第318行 `label: node.label` **没有应用** `formatPartyName()`
- 第322行 `title` 也直接使用 `node.label`

### 🔴 结论 2: 为什么图谱里的节点依然显示"系统检测"？

**根本原因**: **双重漏网 (Double Escape)**

1. **后端生成**: `api_server.py` 在 3 处生成 `"company": "系统检测"`
2. **后端传输**: 这些数据通过 `/api/analysis/graph-data` 返回给前端
3. **前端接收**: `NetworkGraph.tsx` 收到 `node.label = "系统检测"`
4. **前端渲染**: 第318行 **直接使用** `node.label`，**未调用** `formatPartyName()`
5. 结果: 图谱显示 "系统检测" ❌

**证据链**:
- 后端 3 处生成 "系统检测" ✅ (已确认)
- 前端 `formatPartyName()` 函数存在 ✅ (已确认)
- 前端 `NetworkGraph.tsx` 未调用 `formatPartyName()` ❌ (第318行)
- 表格组件已调用 `formatPartyName()` ✅ (TabContent.tsx 已修复)

---

## 总结

| 问题 | 根本原因 | 影响 |
|------|---------|------|
| 图谱 404 | `AnalysisState` 没有保存 `output_dir`，读取时用硬编码路径 | 🔴 严重 |
| 节点显示"系统检测" | 前端 `NetworkGraph.tsx` 未调用翻译函数 | 🟡 中等 |

---

## Phase 1 修复方案

### 修复 1: 路径持久化
**文件**: `api_server.py`
1. `AnalysisState.__init__` 添加 `self.output_dir = None`
2. `run_analysis()` 中保存: `analysis_state.output_dir = output_dir`
3. `get_graph_data()` 改为: `data_dir = analysis_state.output_dir or config.DATA_DIR`

### 修复 2: 节点标签翻译
**文件**: `NetworkGraph.tsx`
1. 第318行改为: `label: formatPartyName(node.label)`
2. 第322行改为: `title: \`【${formatPartyName(node.label)}】...\``

---

**Phase 0 完成，等待指令执行 Phase 1**
