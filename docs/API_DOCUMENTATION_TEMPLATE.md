# API 文档模板

本文档提供了 API 端点的标准文档格式，用于指导开发者编写完整的 API 文档。

## 文档格式标准

每个 API 端点应包含以下部分：

### 1. 端点信息
```markdown
### 端点名称

**方法**: `GET` / `POST` / `PUT` / `DELETE`  
**路径**: `/api/endpoint`  
**描述**: 端点的功能描述
```

### 2. 请求参数
```markdown
#### 请求参数

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
|--------|------|------|----------|------|
| param1 | string | 是 | - | 参数1的描述 |
| param2 | integer | 否 | 10 | 参数2的描述 |
```

### 3. 请求示例
```markdown
#### 请求示例

**请求体**:
```json
{
  "param1": "value1",
  "param2": 100
}
```

**cURL 示例**:
```bash
curl -X POST http://localhost:8000/api/endpoint \
  -H "Content-Type: application/json" \
  -d '{"param1": "value1", "param2": 100}'
```
```

### 4. 响应格式
```markdown
#### 响应格式

**成功响应** (200):
```json
{
  "status": "success",
  "data": {
    "field1": "value1",
    "field2": 100
  }
}
```

**错误响应** (400/500):
```json
{
  "status": "error",
  "message": "错误描述",
  "code": "ERROR_CODE"
}
```
```

### 5. 错误码说明
```markdown
#### 错误码

| 错误码 | HTTP状态码 | 描述 | 解决方案 |
|----------|------------|------|----------|
| INVALID_INPUT | 400 | 输入参数无效 | 检查参数格式和必填性 |
| NOT_FOUND | 404 | 资源不存在 | 确认资源ID是否正确 |
| INTERNAL_ERROR | 500 | 服务器内部错误 | 联系管理员或稍后重试 |
```

### 6. 使用示例
```markdown
#### 使用示例

**Python 示例**:
```python
import requests

response = requests.post(
    'http://localhost:8000/api/endpoint',
    json={'param1': 'value1', 'param2': 100}
)

if response.status_code == 200:
    data = response.json()
    print(data['data'])
else:
    print(f"Error: {response.json()['message']}")
```

**JavaScript 示例**:
```javascript
fetch('http://localhost:8000/api/endpoint', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    param1: 'value1',
    param2: 100
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```
```

## FastAPI 文档增强

FastAPI 自动生成 OpenAPI 文档，但可以通过以下方式增强：

### 1. 使用 Pydantic 模型
```python
from pydantic import BaseModel, Field

class RequestModel(BaseModel):
    """请求模型"""
    param1: str = Field(
        ...,
        description="参数1的描述",
        example="value1"
    )
    param2: int = Field(
        default=10,
        description="参数2的描述",
        example=100
    )

class ResponseModel(BaseModel):
    """响应模型"""
    status: str = Field(..., description="响应状态")
    data: Dict[str, Any] = Field(..., description="响应数据")
```

### 2. 添加详细的 docstring
```python
@app.post("/api/endpoint")
async def endpoint_name(request: RequestModel) -> ResponseModel:
    """
    端点功能描述
    
    ## 功能说明
    详细描述端点的功能和用途
    
    ## 参数说明
    - param1: 参数1的详细说明
    - param2: 参数2的详细说明
    
    ## 返回值说明
    - status: 响应状态（success/error）
    - data: 响应数据，包含以下字段：
      - field1: 字段1的说明
      - field2: 字段2的说明
    
    ## 错误码
    - INVALID_INPUT (400): 输入参数无效
    - NOT_FOUND (404): 资源不存在
    - INTERNAL_ERROR (500): 服务器内部错误
    
    ## 使用示例
    ```python
    import requests
    response = requests.post(
        'http://localhost:8000/api/endpoint',
        json={'param1': 'value1'}
    )
    print(response.json())
    ```
    """
    # 实现逻辑
    pass
```

### 3. 添加响应示例
```python
from fastapi.responses import JSONResponse

@app.post("/api/endpoint")
async def endpoint_name(request: RequestModel) -> ResponseModel:
    """
    端点功能描述
    
    ## 响应示例
    ### 成功响应 (200)
    ```json
    {
      "status": "success",
      "data": {
        "field1": "value1",
        "field2": 100
      }
    }
    ```
    
    ### 错误响应 (400)
    ```json
    {
      "status": "error",
      "message": "参数1不能为空",
      "code": "INVALID_INPUT"
    }
    ```
    """
    # 实现逻辑
    pass
```

## API 端点分类

### 1. 系统管理
- `GET /` - 根路径
- `GET /api/status` - 获取系统状态
- `GET /api/cache/info` - 获取缓存信息
- `POST /api/cache/invalidate` - 使缓存失效

### 2. 分析管理
- `POST /api/analysis/start` - 启动分析
- `POST /api/analysis/stop` - 停止分析
- `GET /api/results` - 获取分析结果
- `GET /api/analysis/stats` - 获取分析统计

### 3. 报告管理
- `GET /api/reports` - 列出报告
- `GET /api/reports/subjects` - 获取报告对象
- `GET /api/reports/available-sections` - 获取可用章节
- `POST /api/reports/generate` - 生成报告
- `GET /api/reports/{filename}` - 下载报告

### 4. 初查报告
- `GET /api/investigation-report/subjects` - 获取核查对象
- `POST /api/investigation-report/generate` - 生成初查报告
- `GET /api/investigation-report/{filename}` - 下载初查报告

### 5. 归集配置
- `GET /api/primary-targets` - 获取归集配置
- `POST /api/primary-targets` - 保存归集配置
- `GET /api/primary-targets/entities` - 获取可用实体
- `POST /api/primary-targets/generate-default` - 生成默认配置

### 6. 文件管理
- `POST /api/open-folder` - 打开文件夹
- `GET /api/audit-navigation` - 获取审计导航

### 7. 数据可视化
- `GET /api/analysis/graph-data` - 获取图谱数据

### 8. WebSocket
- `WS /ws` - WebSocket 连接端点

## 文档生成工具

### 1. 使用 FastAPI 自动文档
访问 `http://localhost:8000/docs` 查看 Swagger UI

### 2. 导出 OpenAPI 规范
```bash
curl http://localhost:8000/openapi.json > openapi.json
```

### 3. 生成静态文档
```bash
# 使用 redoc 生成文档
pip install redoc
redoc-cli build openapi.json -o api_documentation.html
```

## 最佳实践

1. **保持一致性**: 所有端点使用相同的文档格式
2. **提供示例**: 为每个端点提供请求和响应示例
3. **详细说明**: 详细说明每个参数和返回字段的含义
4. **错误处理**: 列出所有可能的错误码和解决方案
5. **版本控制**: 在文档中标注 API 版本
6. **更新及时**: API 变更时及时更新文档
