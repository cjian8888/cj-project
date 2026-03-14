# 前后端集成改进计划

**创建日期**: 2026-01-14  
**状态**: 待实施

---

## 一、改进目标

将前端与后端完全集成，实现真实的分析流程、实时日志推送和报告下载功能。

---

## 二、改进任务清单

### 阶段 1：后端依赖修复（立即）

- [ ] 安装 WebSocket 支持库
- [ ] 重启后端服务验证 WebSocket 功能

### 阶段 2：前端 API 集成（立即）

- [ ] 修改 `AppContext.tsx` 的 `startAnalysis` 函数调用后端 API
- [ ] 实现 WebSocket 日志接收和进度更新
- [ ] 实现分析完成后获取结果

### 阶段 3：报告功能实现（短期）

- [ ] 修改 `TabContent.tsx` 的 `AuditReportTab` 从后端获取报告列表
- [ ] 实现报告下载功能
- [ ] 添加加载状态和错误处理

### 阶段 4：测试验证（短期）

- [ ] 测试完整分析流程
- [ ] 测试 WebSocket 实时日志
- [ ] 测试报告下载功能
- [ ] 验证数据展示正确性

---

## 三、详细实施步骤

### 步骤 1：安装 WebSocket 支持库

```bash
pip install 'uvicorn[standard]'
```

### 步骤 2：修改前端 AppContext.tsx

**文件**: `dashboard/src/contexts/AppContext.tsx`

**修改内容**:
1. 导入 API 服务
2. 修改 `startAnalysis` 函数调用后端 API
3. 添加 WebSocket 订阅处理
4. 移除模拟数据和 setTimeout

### 步骤 3：修改前端 TabContent.tsx

**文件**: `dashboard/src/components/TabContent.tsx`

**修改内容**:
1. 修改 `AuditReportTab` 组件
2. 添加 `useEffect` 从后端获取报告列表
3. 实现报告下载处理函数
4. 添加加载状态

### 步骤 4：重启服务并测试

1. 重启后端服务
2. 刷新前端页面
3. 测试完整流程

---

## 四、预期结果

- ✅ 前端点击"启动引擎"后调用后端 API
- ✅ WebSocket 实时推送分析日志
- ✅ 分析完成后显示真实结果
- ✅ 报告列表显示真实文件
- ✅ 报告下载功能正常工作
