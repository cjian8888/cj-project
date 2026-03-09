# CONFIG MODULE

## OVERVIEW
调查配置模块，存储初查配置模板、主要目标配置、风险阈值。

## STRUCTURE
```
config/
├── __init__.py              # 包导出
├── default.yaml             # 默认调查配置 (23KB)
├── investigation_config.template.yaml  # 配置模板
├── primary_targets_schema.py   # 主要目标 Pydantic 模型
├── primary_targets_service.py  # 主要目标服务
└── rules.yaml               # 规则配置
```

## WHERE TO LOOK

| 配置类型 | 文件 | 说明 |
|----------|------|------|
| 调查配置模板 | default.yaml | 完整调查配置示例 |
| 主要目标模型 | primary_targets_schema.py | Pydantic 验证 |
| 目标服务 | primary_targets_service.py | CRUD 操作 |
| 风险规则 | rules.yaml | 规则定义 |

## CONVENTIONS

### 配置加载
```python
from config_loader import load_config
config = load_config('config/default.yaml')
```

### YAML 结构
```yaml
investigation:
  primary_target:
    name: "姓名"
    id_number: "身份证号"
  analysis_units:
    - name: "分析单元名"
      type: "person|company"
```

## NOTES
- YAML 使用 UTF-8 编码
- 配置变更需重启服务
- 与 `report_config/` 配合使用
