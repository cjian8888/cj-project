# 修复记录 - 2026-02-27

## 问题描述
后端重启后，前端"数据概览"模块无法显示数据，其他模块正常。

## 根本原因
1. `cache_manager.py` 的 `load_results()` 方法没有从元数据中提取 `persons` 和 `companies` 字段
2. 后端重启后 `analysis_state.status` 重置为 `"idle"`，导致前端 `hasRealData` 判断为 false

## 修复内容

### 1. cache_manager.py
**位置**: `load_results()` 方法 (第 316-318 行)
**修改**: 添加从元数据中提取 persons 和 companies
```python
results = {
    "profiles": profiles,
    "_profiles_raw": None,
    "suspicions": self.load_cache("suspicions"),
    "analysisResults": self.load_cache("derived_data"),
    "graphData": self.load_cache("graph_data"),
    # 【修复】从元数据中提取 persons 和 companies
    "persons": metadata.get("persons", []),
    "companies": metadata.get("companies", []),
    # ... 其他字段
}
```

### 2. api_server.py
**位置**: 全局函数 `_restore_analysis_state_from_cache()` (第 173-194 行)
**功能**: 启动时自动从缓存恢复分析状态
```python
def _restore_analysis_state_from_cache():
    """启动时从缓存恢复分析状态"""
    global analysis_state
    _logger = logging.getLogger(__name__)
    try:
        cache_dir = os.path.join(str(OUTPUT_DIR), "analysis_cache")
        if not os.path.exists(cache_dir):
            return

        cache_mgr = CacheManager(cache_dir)
        if cache_mgr.is_cache_valid("metadata"):
            metadata = cache_mgr.load_cache("metadata")
            if metadata and metadata.get("persons"):
                # 恢复分析状态
                analysis_state.status = "completed"
                analysis_state.progress = 100
                analysis_state.phase = "从缓存恢复"
                analysis_state.end_time = datetime.fromisoformat(...)
```

---

# 修复记录 - 2026-02-28

## 问题描述
清空缓存后重新分析，分析完成后前端"数据概览"模块无法自动加载数据。

## 根本原因
`serialize_for_json()` 函数无法处理以下类型：
1. `datetime.date` 类型（`timeSeries.sudden_changes` 中包含）
2. `ClueAggregator` 对象（`aggregation` 字段返回的是对象而非字典）
3. 其他自定义 Python 对象

导致 `/api/results` 返回 500 错误，前端无法获取数据。

## 修复内容

### 1. api_server.py - serialize_for_json() 函数

**位置**: 第 250-305 行

**修改内容**:

#### 1.1 添加 `date` 类型导入
```python
from datetime import datetime, timedelta, date
```

#### 1.2 添加 `datetime.date` 类型处理
```python
elif isinstance(obj, date):
    # Handle datetime.date (different from datetime.datetime)
    return obj.isoformat()
```

#### 1.3 添加任意 Python 对象处理
```python
# Handle arbitrary Python objects (like ClueAggregator)
# Check if it has a to_dict method
if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
    return serialize_for_json(obj.to_dict())

# Check if it has __dict__ attribute (custom class instance)
if hasattr(obj, '__dict__') and not isinstance(obj, type):
    # Convert to dict, excluding private attributes and methods
    obj_dict = {}
    for key, value in obj.__dict__.items():
        if not key.startswith('_') and not callable(value):
            obj_dict[key] = serialize_for_json(value)
    return obj_dict
```

### 2. adapters/key_mapper.py - to_camel_case() 函数

**位置**: 第 49-90 行

**修改内容**: 添加 numpy/pandas 类型转换

```python
def to_camel_case(obj: Any) -> Any:
    import numpy as np
    import pandas as pd
    from datetime import datetime
    
    # Handle numpy/pandas types first (before dict/list check)
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return to_camel_case(obj.tolist())
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    # Handle NaN/NaT - use try-except to avoid array ambiguity
    try:
        if pd.isna(obj):
            return None
    except (ValueError, TypeError):
        pass
    # ... rest of function
```

### 3. api_server.py - /api/results 端点

**位置**: 第 1834-1889 行

**修改内容**: 使用 `Response` 类 + 手动 `json.dumps()` 绕过 FastAPI 的序列化问题

```python
from fastapi.responses import Response
import json

@app.get("/api/results")
async def get_results():
    # ... serialize data ...
    response_body = json.dumps(
        {"message": "分析结果获取成功", "data": results_data},
        ensure_ascii=False
    )
    return Response(content=response_body, media_type="application/json")
```

## 验证结果
- 清空 `output/` 目录
- 杀掉所有项目进程
- 重新启动前后端
- 点击"开始分析"
- 分析完成后，数据概览模块自动显示：6 实体，23,459 笔交易，¥6348.10万 资金规模

## 问题描述
后端重启后，前端"数据概览"模块无法显示数据，其他模块正常。

## 根本原因
1. `cache_manager.py` 的 `load_results()` 方法没有从元数据中提取 `persons` 和 `companies` 字段
2. 后端重启后 `analysis_state.status` 重置为 `"idle"`，导致前端 `hasRealData` 判断为 false

## 修复内容

### 1. cache_manager.py
**位置**: `load_results()` 方法 (第 316-318 行)
**修改**: 添加从元数据中提取 persons 和 companies
```python
results = {
    "profiles": profiles,
    "_profiles_raw": None,
    "suspicions": self.load_cache("suspicions"),
    "analysisResults": self.load_cache("derived_data"),
    "graphData": self.load_cache("graph_data"),
    # 【修复】从元数据中提取 persons 和 companies
    "persons": metadata.get("persons", []),
    "companies": metadata.get("companies", []),
    # ... 其他字段
}
```

### 2. api_server.py
**位置**: 全局函数 `_restore_analysis_state_from_cache()` (第 173-194 行)
**功能**: 启动时自动从缓存恢复分析状态
```python
def _restore_analysis_state_from_cache():
    """启动时从缓存恢复分析状态"""
    global analysis_state
    _logger = logging.getLogger(__name__)
    try:
        cache_dir = os.path.join(str(OUTPUT_DIR), "analysis_cache")
        if not os.path.exists(cache_dir):
            return

        cache_mgr = CacheManager(cache_dir)
        if cache_mgr.is_cache_valid("metadata"):
            metadata = cache_mgr.load_cache("metadata")
            if metadata and metadata.get("persons"):
                # 恢复分析状态
                analysis_state.status = "completed"
                analysis_state.progress = 100
                analysis_state.phase = "从缓存恢复"
                analysis_state.end_time = datetime.fromisoformat(...)
                analysis_state.results = cache_mgr.load_results()
                _logger.info(f"✅ 已从缓存恢复分析状态")
    except Exception as e:
        _logger.warning(f"从缓存恢复状态失败: {e}")
```

**位置**: `lifespan()` 启动事件 (第 1752 行)
**修改**: 启动时调用恢复函数
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 资金穿透审计系统启动 (重构版)")
    # 启动时尝试从缓存恢复分析状态
    _restore_analysis_state_from_cache()
    yield
    logger.info("🛑 资金穿透审计系统关闭")
```

## 验证方法
1. 启动后端服务
2. 检查 `/api/status` 返回的 `status` 应为 `"completed"`
3. 刷新浏览器，数据概览模块应正常显示人员和企业数据

## 相关文件
- `cache_manager.py` - 缓存加载逻辑
- `api_server.py` - 后端 API 和状态管理
- `dashboard/src/components/TabContent.tsx` - 前端数据概览组件
- `dashboard/src/contexts/AppContext.tsx` - 前端状态管理
