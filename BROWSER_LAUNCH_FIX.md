# 浏览器拉起问题修复说明

## 问题描述
Windows 7/11 一键运行包无法自动拉起浏览器访问 `http://127.0.0.1:8000/dashboard/`

## 根本原因

### 1. 环境变量传递问题 (核心问题)
`start_fpas.cmd` 使用 `start /b` 启动浏览器助手时，**没有传递环境变量**，导致 `launch_browser_helper.py` 无法读取 `FPAS_PORT`、`FPAS_BROWSER_PID_FILE` 等关键配置。

### 2. Win7 兼容性问题
- 使用了 `CREATE_NO_WINDOW` 标志，在 Win7 上可能导致浏览器无法正常显示
- 缺少 `--no-first-run` 和 `--no-default-browser-check` 参数，导致 Chrome 首次运行时卡住

### 3. 注册表查询问题
`winreg.QueryValueEx(key, None)` 在某些情况下可能失败

## 修复内容

### 修改的文件

1. **`build_windows_package.py`** (源文件)
   - 更新了 `render_portable_start_cmd()` 函数，显式传递所有环境变量
   - 更新了 `render_portable_launch_browser_helper_py()` 函数，添加 Win7 兼容性修复和调试日志

2. **`dist/fpas-offline/start_fpas.cmd`** (已打包文件)
   - 使用 `cmd /c` 包装器显式传递所有环境变量
   - 添加了 `FPAS_PORT` 环境变量设置

3. **`dist/fpas-offline/launch_browser_helper.py`** (已打包文件)
   - 移除了 `CREATE_NO_WINDOW` 标志
   - 添加了 `--no-first-run` 和 `--no-default-browser-check` 参数
   - 添加了详细的调试日志功能
   - 修复了注册表查询问题

## 关键修改详情

### start_fpas.cmd
```batch
# 修复前
start "" /b "%FPAS_PYTHON%" "%FPAS_ROOT%\launch_browser_helper.py"

# 修复后
if not defined FPAS_PORT set "FPAS_PORT=8000"
start "" /b cmd /c "set FPAS_ROOT=%FPAS_ROOT% && set FPAS_RUN_DIR=%FPAS_RUN_DIR% && ... && "%FPAS_PYTHON%" "%FPAS_ROOT%\launch_browser_helper.py""
```

### launch_browser_helper.py
```python
# 修复前
args.extend([
    f"--user-data-dir={profile_dir}",
    "--new-window",
    f"--app={url}",
])
creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# 修复后
args.extend([
    f"--user-data-dir={profile_dir}",
    "--new-window",
    "--no-first-run",          # Win7兼容
    "--no-default-browser-check",  # Win7兼容
    url,
])
creationflags = 0  # Win7兼容
```

## 验证步骤

1. **重新打包** (在 Windows 机器上):
   ```bash
   python build_windows_package.py
   ```

2. **测试运行**:
   - 双击 `start_fpas.cmd` 或 `start_fpas_silent.vbs`
   - 检查是否自动打开浏览器访问 `http://127.0.0.1:8000/dashboard/`

3. **查看日志** (如果仍有问题):
   - `run/browser_launch_debug.log` - 调试日志，记录启动流程
   - `run/browser_launch_error.log` - 错误日志，记录启动失败原因
   - `startup_fatal.log` - 启动错误日志

## 注意事项

1. 当前修复已应用到 `dist/fpas-offline/` 目录下的已打包文件
2. 如果要重新打包，修复会自动应用到新包中（因为 `build_windows_package.py` 已更新）
3. 调试日志会记录详细的启动过程，便于排查问题

## 可能的后续问题

如果仍然无法拉起浏览器，请检查：

1. **Win7 系统**: 确认已安装 4 个必要补丁和 Chrome 109
2. **浏览器路径**: 检查 `run/browser_launch_debug.log` 中列出的浏览器候选列表
3. **端口占用**: 确认 8000 端口未被其他程序占用
4. **防火墙/杀毒软件**: 检查是否被安全软件阻止
