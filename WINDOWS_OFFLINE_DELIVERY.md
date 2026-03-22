# Windows 离线交付基线

更新时间：2026-03-22

## 当前结论

这个项目的最终交付目标已经固定为：

- 目标平台：`Windows7+`
- 运行方式：单机、离线
- 交付形式：`one-folder` 离线包
- 前后端形态：后端进程直接承载前端生产构建产物，不再依赖 `Vite dev server`

现阶段宿主机是 mac，因此这台机器只能完成“交付前准备”和“仓库预检”，不能直接产出最终 Windows 包。

## 当前已经固化到代码里的约束

1. Windows 打包统一入口为 `build_windows_package.py`
2. 打包脚本已提供 `--preflight` 模式，用于在 mac / Linux 上先做交付前检查
3. 打包脚本正式构建时会拒绝非 Windows 平台
4. 目标是 `Windows7+` 时，正式构建机会强制要求 `Python 3.8.x`
5. `requirements-windows-build.txt` 已固定 `PyInstaller==5.13.2`
6. `fpas_windows.spec` 已纳入以下关键运行资源：
   - `README.md`
   - `docs/assets/`
   - `config/`
   - `knowledge/`
   - `report_config/`
   - `templates/`
   - `dashboard/dist/`
   - `vis-network.min.js`

## 为什么 Win7 目标要收紧到 Python 3.8 + PyInstaller 5.13.2

- Python 官方当前文档已明确：如果需要 `Windows 7` 支持，应安装 `Python 3.8`
- PyInstaller 官方 6.x 的运行时基线已提升到 `Windows 8+`
- 因此，当前这条交付链如果仍使用 `PyInstaller 6.x`，就和 `Windows7+` 目标直接冲突

这不是偏好问题，而是目标平台和打包工具链的硬约束。

## 在 mac 上现在能完成什么

下面这些事情，当前都可以在 mac 上先做完：

1. 代码级预检

```bash
python3 build_windows_package.py --preflight
```

2. 前端生产构建验证

```bash
cd dashboard
npm run build
```

3. 回归测试

```bash
python3 -m pytest tests/test_build_windows_package.py -q
python3 -m pytest tests/test_paths.py -q
```

4. 后端语法检查

```bash
python3 -m py_compile api_server.py build_windows_package.py
```

5. 打包资源审计

- 检查 `fpas_windows.spec` 是否已带上文档、模板、知识库和前端生产产物
- 检查 `/docs/readme` 依赖的 `README.md` 与 `docs/assets/` 是否可被打包
- 检查路径管理是否仍走 `paths.py`，避免硬编码绝对路径

## 在 mac 上现在做不了什么

下面这些事情，必须放到 Windows 构建机上完成：

1. 产出真正的 Windows `one-folder` 包
2. 验证 exe 在 `Windows7+` 上是否能直接运行
3. 验证 UCRT / VC 运行库缺失时的行为
4. 生成最终可复现的 Windows 离线依赖锁定清单
5. 在近似空白 Windows 机器上做最终交付验收

## 推荐的 Windows 构建机基线

为了尽量贴近最终目标，建议准备一台专用构建机，至少满足：

- 操作系统：Windows 7 SP1 或更高版本
- Python：`3.8.x`
- Node.js：能完成当前 `dashboard/` 前端生产构建的稳定版本
- 构建方式：本地离线或局域网内预置 wheel / npm 缓存，不依赖公网安装

如果构建机高于 Windows 7，也必须以 `Python 3.8.x + PyInstaller 5.13.2` 为基线，并在最终成品上回到 `Windows7+` 实机验证。

## 建议的 Windows 侧最终构建步骤

### 1. 建立专用虚拟环境

```bash
python -m venv .venv38
.venv38\Scripts\activate
```

### 2. 安装运行依赖和打包依赖

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-windows-build.txt
```

### 3. 固化本次真正使用的依赖版本

```bash
python -m pip freeze > requirements-windows-lock.txt
```

这一步很重要。`requirements.txt` 目前主要是下限约束，不是最终可复现锁文件。真正交付前，必须把 Windows 3.8 构建机里实际装进去的版本冻结下来。

### 4. 构建前端

```bash
cd dashboard
npm install
npm run build
cd ..
```

### 5. 产出 one-folder 包

```bash
python build_windows_package.py
```

默认体验说明：

- 双击 `dist/fpas-offline/fpas.exe` 后，程序会自动拉起本机默认浏览器并打开 `http://127.0.0.1:8000/dashboard/`
- 如果需要关闭这一行为，可在启动前设置环境变量 `FPAS_AUTO_OPEN_BROWSER=0`

## 当前最重要的未闭环项

截至现在，下面几件事仍然不能只靠 mac 收口：

- `requirements.txt` 还不是 Windows 3.8 的最终锁文件
- 还没有在真实 Windows 机器上完成一次完整打包
- 还没有在 `Windows7+` 实机上做最终运行验收
- 还没有对最终 `dist/fpas-offline/` 成品做空环境启动验证

## 对后续代理或开发者的要求

如果后续还有人继续接手这条链路，必须先接受以下原则：

1. 不要在 mac 上误以为自己已经“打完 Windows 包”
2. 不要把 `npm run dev` 当成最终交付方式
3. 不要再把新的静态资源、模板或文档漏出 `fpas_windows.spec`
4. 不要使用高于 `Python 3.8.x + PyInstaller 5.13.2` 的构建基线去宣称兼容 `Windows7+`
5. 交付前一定要拿最终 exe 回到真实 Windows 环境做验收
