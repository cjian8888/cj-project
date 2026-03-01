
---

## 📋 代码规范约定 (2026-03-01 更新)

### 🔧 工具函数统一规范

**⚠️ 重要**: 所有数据提取器必须使用统一的工具函数模块，**禁止**在各自文件中重复定义！

#### 统一工具函数位置
**模块**: `utils/safe_types.py`

**必须使用这些函数**:
```python
from utils.safe_types import (
    safe_str,           # 安全转换为字符串 (返回 Optional[str])
    safe_float,         # 安全转换为浮点数 (返回 Optional[float])
    safe_int,           # 安全转换为整数 (返回 Optional[int])
    safe_date,          # 安全转换为日期 YYYY-MM-DD (返回 Optional[str])
    safe_datetime,      # 安全转换为日期时间 YYYY-MM-DD HH:MM:SS (返回 Optional[str])
    extract_id_from_filename,  # 从文件名提取身份证号
    normalize_column_name,     # 标准化列名
)
```

#### 为什么需要统一？
1. **避免代码重复** - 之前16个文件中有46处重复定义
2. **行为一致性** - 统一空值检查、异常处理、类型注解
3. **易于维护** - 修改只需在一个地方进行
4. **减少bug** - 消除不同实现之间的细微差异

#### 使用示例
```python
# ✅ 正确做法
from utils.safe_types import safe_str, safe_float, safe_date

name = safe_str(row.get("姓名"))           # 返回 Optional[str]
amount = safe_float(row.get("金额"))       # 返回 Optional[float]
date = safe_date(row.get("交易日期"))      # 返回 Optional[str]

# ❌ 错误做法 - 禁止在文件中重新定义这些函数
def _safe_str(value):   # 不要这样做！
    ...

def _safe_float(value): # 不要这样做！
    ...
```

#### 受影响的文件（必须遵守）
- `*_extractor.py` - 所有数据提取器
- `*_analyzer.py` - 数据分析器
- 任何需要数据类型转换的模块

### 🚨 禁止的代码模式

1. **禁止重复定义工具函数**
   ```python
   # 禁止
   def _safe_str(value): ...
   def _safe_float(value): ...
   ```

2. **禁止不一致的返回类型**
   ```python
   # 禁止 - 有的返回空字符串，有的返回None
   def _safe_str(value) -> str:  # 应该返回 Optional[str]
       if pd.isna(value):
           return ""  # 不一致！
       return str(value)
   ```

3. **禁止硬编码路径**
   ```python
   # 禁止
   os.chdir("D:/CJ/project")  # Windows绝对路径
   
   # 应该
   from paths import APP_ROOT
   os.chdir(APP_ROOT)
   ```

### 📁 文件组织约定

| 用途 | 位置 | 说明 |
|------|------|------|
| 工具函数 | `utils/` 目录 | safe_types.py, logging_config.py 等 |
| 数据提取器 | 根目录 `*_extractor.py` | 必须导入 utils.safe_types |
| 配置管理 | `config.py` + `config_loader.py` | 禁止硬编码配置 |
| 数据模型 | `schemas/` 目录 | Pydantic 模型 |

### 🔄 后续Agent修改代码时必须检查

1. 是否在新增数据提取器？→ 必须使用 `utils.safe_types`
2. 是否修改现有提取器？→ 检查是否有重复定义，迁移到统一模块
3. 是否添加新工具函数？→ 考虑是否通用，通用则加入 `utils.safe_types`
