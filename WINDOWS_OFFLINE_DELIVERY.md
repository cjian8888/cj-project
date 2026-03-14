# Windows 离线交付基线

更新时间：2026-03-14

## 当前结论

这个项目已经明确转向以下交付形态：

- 目标平台：Windows
- 运行方式：单机、离线
- 交付形式：`one-folder` 离线包
- 前后端形态：后端进程直接承载前端生产构建产物，不再依赖 `Vite dev server`

## 这次架构变化的核心点

1. 前端生产构建挂载在后端 `GET /dashboard/`
2. 前端默认 API 改为同源访问
3. WebSocket 默认改为同源 `ws(s)://<host>/ws`
4. Vite 开发态继续通过代理访问后端
5. Windows 启动脚本不再写死磁盘路径
6. 已新增 Windows 打包入口：
   - `build_windows_package.py`
   - `build_windows_package.bat`
   - `fpas_windows.spec`
   - `requirements-windows-build.txt`

## 开发态与交付态的边界

### 开发态

- 后端：`python api_server.py`
- 前端：`cd dashboard && npm run dev`
- 访问地址：`http://localhost:5173`

### 交付态 / 打包态

- 先构建前端：`cd dashboard && npm run build`
- 后端直接提供前端页面：`http://localhost:8000/dashboard/`
- Windows 打包入口：`python build_windows_package.py`

## 明天在 Windows 机器上继续工作时要优先知道的事

如果你是新的编程代理、Codex CLI 或 OpenCode，请先接受以下事实，不要再按旧思路处理：

1. 这个项目的最终目标不是“双开发服务器长期运行”，而是“Windows 单机离线 one-folder 包”
2. `api_server.py` 仍然是唯一后端入口
3. 前端生产构建必须由后端承载，路径是 `/dashboard/`
4. 新增功能时必须考虑：
   - 不能依赖互联网
   - 不能依赖本地 Node 开发服务器作为最终运行方式
   - 不能写死 macOS/Windows 的绝对路径
   - 新增运行时资源必须能被 PyInstaller 一起带走
5. 如果修改前端 API 地址逻辑，必须保持“默认同源，开发态可代理”这个原则

## Windows 构建命令

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-windows-build.txt
cd dashboard
npm install
npm run build
cd ..
python build_windows_package.py
```

## 当前仍需继续验证的事项

这些事情已经进入主链路，但还需要在真实 Windows 环境里做最终验证：

- PyInstaller 真机构建是否完整通过
- 打包后 `/dashboard/` 页面是否完整可用
- Excel / 模板 / 配置 / 知识库是否都已被带入包内
- 空白或近似空白 Windows 机器上的离线运行验证
- 最终交付目录结构与启动方式确认
