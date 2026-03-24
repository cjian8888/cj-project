# Windows 离线交付基线

更新时间：2026-03-23

## 当前结论

这个项目面向 `Windows 7 SP1+` 的最终交付结论已经收敛为：

- 目标平台：`Windows 7 SP1+`
- 运行方式：单机、离线
- 交付形式：`one-folder` 离线包
- 默认交付模式：`portable-runtime`
- 默认启动入口：`dist/fpas-offline/start_fpas.cmd`
- 可选静默入口：`dist/fpas-offline/start_fpas_silent.vbs`
- 访问地址：`http://127.0.0.1:8000/dashboard/`

`PyInstaller one-folder exe` 这条链路在 Win7 实机验证中仍会出现启动期 `MemoryError`，因此不再作为 Win7 默认交付方案。它现在只保留为可选调试路径，不再是主交付形态。

## 为什么改成 portable-runtime

截至 `2026-03-23` 的 Win7 实测结果：

- 源码态：`python api_server.py` 可在 Win7 上稳定启动，并监听 `0.0.0.0:8000`
- portable-runtime 包：`start_fpas.cmd` 拉起后，Win7 上 `/dashboard/` 返回 `200`
- PyInstaller 冻结包：即使已回退 `cryptography`、关闭归档压缩并持续瘦身启动链，Win7 上 `fpas.exe` 仍会在启动期触发 `MemoryError`

这说明问题已经不是“补一个 DLL”或“再调一个 hook”就能稳定解决，而是 Win7 对大体量冻结进程的容忍度不够。继续把整套应用强行冻成单体 `exe`，风险高于收益。

因此，当前主交付方案改为：

- 复制完整应用源码和前端生产产物
- 复制 Windows Python 3.8 运行时
- 把当前虚拟环境的 `site-packages` 合并进包内运行时
- 用 `start_fpas.cmd` 调用包内 `runtime/python/python.exe api_server.py`

目标机仍然不需要额外安装 Python。

## 当前已经固化到代码里的约束

1. Windows 打包统一入口仍是 `build_windows_package.py`
2. 默认构建模式改为 `portable-runtime`
3. `build_windows_package.py --bundle-mode pyinstaller` 仅保留为兼容调试路径
4. 打包脚本正式构建时仍要求 `Windows + Python 3.8.x`
5. 前端生产构建仍由后端 `/dashboard/` 承载，不依赖 `Vite dev server`
6. 交付包会生成以下入口文件：
   - `start_fpas.cmd`
   - `start_fpas_silent.vbs`
7. 启动失败诊断日志默认落在交付根目录：
   - `dist/fpas-offline/startup_fatal.log`

## Win7 最小环境支持清单

必须满足：

- 操作系统：`Windows 7 SP1`
- 补丁：`KB2533623`
- Universal CRT：满足其一即可
  - `KB2999226`
  - 或 `C:\Windows\System32\ucrtbase.dll` 已存在
- 浏览器：必须有一款可用的现代浏览器；仅 `IE11` 不视为满足前端运行条件
- 位数：交付包内置运行时位数必须与目标系统位数一致

强烈建议安装：

- `KB4490628`
- `KB4474419`

最小核对命令：

```bat
wmic qfe | findstr 2533623
wmic qfe | findstr 2999226
dir C:\Windows\System32\ucrtbase.dll
```

## 当前已验证通过的 Win7 构建/验收机

截至 `2026-03-23`，下面这台 Win7 虚拟机已完成真实验收：

- 虚拟机：`Win7-SP1-FPAS`
- 系统：`Windows 7 Professional SP1 x64`
- Python：`3.8.10 x64`
- 打包模式：`portable-runtime`

已验证通过的事实：

- `build_windows_package.py` 默认构建成功
- 生成目录：`dist/fpas-offline`
- 包内存在：
  - `start_fpas.cmd`
  - `start_fpas_silent.vbs`
  - `runtime/python/python.exe`
- 在 Win7 上通过任务计划调用 `start_fpas.cmd` 后：
  - `0.0.0.0:8000` 进入 `LISTENING`
  - `GET http://127.0.0.1:8000/dashboard/` 返回 `200`

## Windows 侧推荐构建步骤

### 1. 建立 Python 3.8 虚拟环境

```bash
python -m venv .venv38
.venv38\Scripts\activate
```

### 2. 安装运行依赖和构建依赖

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-windows-build.txt
```

### 3. 构建前端

```bash
cd dashboard
npm install
npm run build
cd ..
```

### 4. 产出 Win7 交付包

```bash
python build_windows_package.py
```

默认会输出：

- `dist/fpas-offline/start_fpas.cmd`
- `dist/fpas-offline/start_fpas_silent.vbs`
- `dist/fpas-offline/runtime/python/`

### 5. 目标机启动方式

首选：

```text
双击 start_fpas.cmd
```

如果希望隐藏控制台窗口：

```text
双击 start_fpas_silent.vbs
```

启动成功后应能访问：

```text
http://127.0.0.1:8000/dashboard/
```

如果启动失败，先看：

```text
dist/fpas-offline/startup_fatal.log
```

## 在 mac 上现在能完成什么

mac / Linux 侧当前仍然只能做交付前准备，不能产出最终 Win7 包：

1. `python3 build_windows_package.py --preflight`
2. `cd dashboard && npm run build`
3. 回归测试
4. 语法检查
5. 打包资源审计

真正的 Win7 交付包，必须回到 `Windows + Python 3.8.x` 构建机完成。

## 剩余边界

当前仍未闭环的只剩这些：

- 还没有在你那台最终封闭网络的物理 Win7 机器上做最终验收
- 还没有把新的 `portable-runtime` 交付说明同步到所有历史文档和发包流程里
- `PyInstaller` 路径虽然保留，但不应再被当作 Win7 正式交付入口

## 对后续开发者的要求

1. 不要再把 `fpas.exe` 当成 Win7 默认交付入口
2. 不要把 `npm run dev` 当成最终交付方式
3. 新增静态资源、模板、知识库或配置目录时，要同时纳入 portable bundle 复制清单
4. 不要使用高于 `Python 3.8.x` 的运行时去宣称兼容 `Windows 7`
5. Win7 交付前必须再次在真实 Win7 环境执行 `start_fpas.cmd` 验收
