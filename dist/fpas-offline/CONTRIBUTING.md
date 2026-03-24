# 贡献指南

感谢您对资金穿透与关联排查系统的关注！

## 快速开始

### 环境准备

```bash
# 克隆仓库
git clone <repository-url>
cd cj-project

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_utils.py -v
```

### 运行程序

```bash
# 命令行模式
python main.py ./data ./output

# Web界面模式
streamlit run streamlit_app.py
```

## 代码规范

### 文件结构

```
cj-project/
├── main.py              # 主程序入口
├── config.py            # 配置常量
├── config/              # YAML配置文件
├── *_analyzer.py        # 各类分析模块
├── utils.py             # 工具函数
├── tests/               # 单元测试
├── docs/                # 文档
└── templates/           # 报告模板
```

### 命名规范

- **模块名**: 小写下划线，如 `income_analyzer.py`
- **类名**: 大驼峰，如 `MoneyGraph`
- **函数名**: 小写下划线，如 `detect_suspicious_income`
- **常量**: 大写下划线，如 `LARGE_CASH_THRESHOLD`

### 注释规范

```python
def function_name(param: Type) -> ReturnType:
    """
    函数简要说明
    
    Args:
        param: 参数说明
        
    Returns:
        返回值说明
    """
    pass
```

## 配置规范

### 通用性原则

1. **配置文件中不包含特定案件信息**（如具体人名、公司名）
2. **节假日自动生成**，无需手动配置
3. **案件特定配置**应在运行时通过 `USER_DEFINED_*` 参数指定

### 新增配置项

在 `config.py` 中添加新配置时：
1. 添加清晰的注释说明
2. 设置合理的默认值
3. 同步更新 `config/default.yaml`

## 提交规范

### Commit Message

```
<type>: <subject>

<body>
```

**Type**:
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 其他杂项

**示例**:
```
feat: 新增分期受贿检测功能

- 检测从同一人处每月收到固定金额的可疑模式
- 增加多维度风险因素评分
- 自动区分HIGH/MEDIUM风险等级
```

## 安全提示

⚠️ **数据安全**: 本系统处理敏感金融数据，请：
- 在安全、隔离的内网环境中开发和测试
- 不要将真实数据提交到版本控制
- 确保 `.gitignore` 正确配置

## 联系方式

如有问题或建议，请联系系统管理员。
