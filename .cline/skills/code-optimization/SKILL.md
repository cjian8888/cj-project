---
name: code-optimization
description: 针对 Python/Pandas 后端和 React 前端进行内存优化和性能调优
---

# Performance & Memory Optimization Specialist

## When to use
- 当用户抱怨“内存不足”、“程序卡顿”或“运行缓慢”时。
- 当用户要求“优化代码”或“减少资源占用”时。

## Optimization Strategy (必须严格执行)

### 1. Python/Pandas Backend Optimization (Priority: High)
**目标**：减少 Pandas DataFrame 的内存占用，防止 OOM (Out of Memory)。

- **Action A: Optimize Dtypes (类型压缩)**
  - 扫描所有 `pd.read_excel` 或 `pd.read_csv` 的地方。
  - **强制转换类型**：
    - 金额/数字列：从 `int64/float64` 降级为 `int32/float32` (如果精度允许)。
    - 枚举类文本（如“交易类型”、“借贷标志”）：从 `object` 转换为 `category`。
    - 日期列：确保使用 `pd.to_datetime`。
  - *代码示例*：
    ```python
    # Bad
    df = pd.read_excel(...)
    # Good
    df = pd.read_excel(..., dtype={'status': 'category', 'amount': 'float32'})
    ```

- **Action B: Aggressive Garbage Collection (主动垃圾回收)**
  - 在大型分析函数（如 `financial_profiler.py`）的每一步结束后。
  - 插入代码：使用 `del temporary_df` 删除不再使用的中间 DataFrame，紧接着调用 `import gc; gc.collect()`。

- **Action C: Chunk Processing (分块处理 - 仅针对超大文件)**
  - 如果检测到文件读取逻辑，建议增加 `chunksize` 参数。

### 2. Frontend Visualization Optimization
**目标**：防止浏览器因渲染过多 DOM 节点而崩溃。

- **Action A: Graph Sampling (图谱采样)**
  - 在返回给前端的 API (如 `/api/analysis/graph-data`) 中增加逻辑。
  - **限制节点数**：默认只返回 `Top 200` 权重的节点（按金额或连接数排序）。
  - 不要把 10,000 条连线全扔给前端。

### 3. VS Code / Environment
- 提醒用户在 `.clineignore` 中排除大型数据文件 (`*.xlsx`, `*.csv`)。

## Output Report
优化完成后，输出：
1.  📉 **内存节省策略**：(列出你修改了哪些数据类型)
2.  🧹 **GC 插入点**：(列出你在哪里加了垃圾回收)
3.  🔒 **安全检查**：(确认优化没有影响计算精度)