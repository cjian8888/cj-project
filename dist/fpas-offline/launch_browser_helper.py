#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launch a manageable browser instance for the packaged FPAS dashboard."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
CreateJobObjectW = kernel32.CreateJobObjectW
CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
CreateJobObjectW.restype = wintypes.HANDLE
SetInformationJobObject = kernel32.SetInformationJobObject
SetInformationJobObject.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
]
SetInformationJobObject.restype = wintypes.BOOL
AssignProcessToJobObject = kernel32.AssignProcessToJobObject
AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
AssignProcessToJobObject.restype = wintypes.BOOL
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE
CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


def _normalize_path(value: str) -> str:
    return os.path.normcase(os.path.abspath(value))


def _extract_executable(command: str) -> str | None:
    text = str(command or "").strip()
    if not text:
        return None
    match = re.match(
        r'^\s*(?:"([^"]+?\.exe)"|(.+?\.exe))(?:\s|$)',
        text,
        re.IGNORECASE,
    )
    if match:
        candidate = (match.group(1) or match.group(2) or "").strip()
        return candidate or None
    return None


def _resolve_default_browser_executable() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except Exception:
        return None

    registry_candidates = []
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
            if prog_id:
                registry_candidates.extend(
                    [
                        (winreg.HKEY_CLASSES_ROOT, rf"{prog_id}\shell\open\command"),
                        (
                            winreg.HKEY_CURRENT_USER,
                            rf"Software\Classes\{prog_id}\shell\open\command",
                        ),
                    ]
                )
    except OSError:
        pass

    registry_candidates.extend(
        [
            (winreg.HKEY_CLASSES_ROOT, r"http\shell\open\command"),
            (winreg.HKEY_CLASSES_ROOT, r"https\shell\open\command"),
        ]
    )

    for hive, subkey in registry_candidates:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                command, _ = winreg.QueryValueEx(key, "")  # type: ignore[arg-type]
        except OSError:
            continue
        executable = _extract_executable(command)
        if executable and os.path.exists(executable):
            return executable
    return None


def _known_browser_candidates() -> list[str]:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    return [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files\Chromium\Application\chrome.exe",
        r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
        os.path.join(local_app_data, r"Google\Chrome\Application\chrome.exe"),
        os.path.join(local_app_data, r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(local_app_data, r"Mozilla Firefox\firefox.exe"),
        os.path.join(
            local_app_data, r"BraveSoftware\Brave-Browser\Application\brave.exe"
        ),
        os.path.join(local_app_data, r"Chromium\Application\chrome.exe"),
    ]


def _iter_browser_candidates() -> list[str]:
    override = os.environ.get("FPAS_BROWSER_EXE", "").strip()
    default_browser = _resolve_default_browser_executable()
    candidates = [override, default_browser, *_known_browser_candidates()]
    unique_candidates = []
    seen = set()
    for candidate in candidates:
        normalized = _normalize_path(candidate) if candidate else ""
        if not candidate or normalized in seen or not os.path.exists(candidate):
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)
    return unique_candidates


def _is_managed_browser(browser_exe: str) -> bool:
    exe_name = Path(browser_exe).name.lower()
    return "firefox" in exe_name or any(
        token in exe_name for token in ("chrome", "msedge", "chromium", "brave")
    )


def _close_handle(handle: int | None) -> None:
    if handle:
        CloseHandle(handle)


def _create_kill_on_close_job() -> int | None:
    if sys.platform != "win32":
        return None
    job_handle = CreateJobObjectW(None, None)
    if not job_handle:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not SetInformationJobObject(
        job_handle,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        _close_handle(job_handle)
        return None
    return int(job_handle)


def _assign_process_to_job(job_handle: int | None, pid: int) -> bool:
    if not job_handle or pid <= 0:
        return False
    process_handle = OpenProcess(
        PROCESS_SET_QUOTA | PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid,
    )
    if not process_handle:
        return False
    try:
        return bool(AssignProcessToJobObject(job_handle, process_handle))
    finally:
        _close_handle(process_handle)


def _write_managed_browser_pid_file(
    browser_pid_file: Path,
    browser_pid: int,
    browser_exe: str,
    browser_profile_dir: Path,
) -> None:
    browser_pid_file.parent.mkdir(parents=True, exist_ok=True)
    browser_pid_file.write_text(
        f"{os.getpid()}\n{browser_pid}\n{_normalize_path(browser_exe)}\n{_normalize_path(str(browser_profile_dir))}\nmanaged-job\n",
        encoding="utf-8",
    )


def _guard_managed_browser(
    process: subprocess.Popen,
    job_handle: int,
    browser_pid_file: Path,
    browser_exe: str,
    browser_profile_dir: Path,
    stopping_flag: Path,
) -> int:
    _write_managed_browser_pid_file(
        browser_pid_file,
        int(process.pid),
        browser_exe,
        browser_profile_dir,
    )
    try:
        while True:
            if process.poll() is not None:
                return int(process.returncode or 0)
            if stopping_flag.exists():
                return 0
            time.sleep(0.5)
    finally:
        try:
            lines = [
                line.strip()
                for line in browser_pid_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except OSError:
            lines = []
        if lines:
            try:
                recorded_guard_pid = int(lines[0])
            except ValueError:
                recorded_guard_pid = 0
            if recorded_guard_pid == os.getpid():
                try:
                    browser_pid_file.unlink()
                except OSError:
                    pass
        _close_handle(job_handle)


def _launch_managed_browser(
    browser_exe: str, url: str, profile_dir: Path
) -> tuple[int | None, subprocess.Popen | None, int | None]:
    if not _is_managed_browser(browser_exe):
        return None, None, None

    exe_name = Path(browser_exe).name.lower()
    args = [browser_exe]

    if "firefox" in exe_name:
        shutil.rmtree(profile_dir, ignore_errors=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        args.extend(["-new-instance", "-profile", str(profile_dir), url])
    else:
        shutil.rmtree(profile_dir, ignore_errors=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        # Win7兼容: 使用 --no-first-run 和 --no-default-browser-check 避免启动问题
        args.extend(
            [
                f"--user-data-dir={profile_dir}",
                "--new-window",
                "--no-first-run",
                "--no-default-browser-check",
                url,
            ]
        )

    try:
        # Win7兼容: 不使用CREATE_NO_WINDOW，让浏览器正常显示
        creationflags = 0
        process = subprocess.Popen(args, creationflags=creationflags)
        job_handle = _create_kill_on_close_job()
        if job_handle and not _assign_process_to_job(job_handle, int(process.pid)):
            _close_handle(job_handle)
            job_handle = None
        return int(process.pid), process, job_handle
    except Exception as e:
        # 记录启动失败
        try:
            root = Path(__file__).resolve().parent
            log_path = root / "run" / "browser_launch_error.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Failed to launch {browser_exe}: {e}\n"
                )
                f.write(f"  Args: {args}\n")
        except:
            pass
        return None, None, None


def _open_url_fallback(url: str, browser_exe: str | None = None) -> None:
    """Win7/Win11兼容的回退打开方式"""
    # Win7兼容: 不使用CREATE_NO_WINDOW
    creationflags = 0

    if browser_exe and os.path.exists(browser_exe):
        try:
            subprocess.Popen([browser_exe, url], creationflags=creationflags)
            return
        except Exception as e:
            # 记录错误
            try:
                root = Path(__file__).resolve().parent
                log_path = root / "run" / "browser_launch_error.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(
                        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fallback browser failed: {e}\n"
                    )
            except:
                pass

    # 使用系统默认方式打开
    try:
        subprocess.Popen(["cmd", "/c", "start", "", url], creationflags=creationflags)
    except Exception as e:
        try:
            root = Path(__file__).resolve().parent
            log_path = root / "run" / "browser_launch_error.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] System start command failed: {e}\n"
                )
        except:
            pass


def _log_debug(message: str) -> None:
    """记录调试日志"""
    try:
        root = Path(__file__).resolve().parent
        log_path = root / "run" / "browser_launch_debug.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except:
        pass


def main() -> int:
    root = Path(__file__).resolve().parent
    browser_pid_file = Path(
        os.environ.get("FPAS_BROWSER_PID_FILE", "") or root / "run" / "browser.pid"
    )
    browser_profile_dir = Path(
        os.environ.get("FPAS_BROWSER_PROFILE_DIR", "")
        or root / "run" / "browser-profile"
    )
    stopping_flag = Path(
        os.environ.get("FPAS_STOPPING_FLAG", "") or root / "run" / "stopping.flag"
    )
    port = str(os.environ.get("FPAS_PORT", "8000") or "8000").strip() or "8000"
    dashboard_url = f"http://127.0.0.1:{port}/dashboard/"
    auto_open_browser = (
        str(os.environ.get("FPAS_AUTO_OPEN_BROWSER", "1") or "1").strip().lower()
    )

    _log_debug(f"Browser helper started")
    _log_debug(f"PORT={port}, AUTO_OPEN={auto_open_browser}")
    _log_debug(f"URL={dashboard_url}")

    if auto_open_browser in {"0", "false", "no", "off"}:
        _log_debug("Auto open disabled, exiting")
        return 0

    # 等待服务器启动
    _log_debug("Waiting for server to start...")
    for i in range(60):
        try:
            import urllib.request

            with urllib.request.urlopen(dashboard_url, timeout=2) as response:
                if response.getcode() == 200:
                    _log_debug(f"Server ready after {i + 1} attempts")
                    break
        except Exception as e:
            if i == 0 or i == 30:  # 只在开始和中间记录一次
                _log_debug(f"Server not ready yet (attempt {i + 1}): {e}")
            time.sleep(0.5)
    else:
        _log_debug("Server failed to start within timeout")
        return 0

    # 获取浏览器候选列表
    candidates = _iter_browser_candidates()
    _log_debug(f"Found {len(candidates)} browser candidates: {candidates}")

    browser_pid = None
    fallback_browser_exe = None
    for browser_exe in candidates:
        if fallback_browser_exe is None:
            fallback_browser_exe = browser_exe
        _log_debug(f"Trying browser: {browser_exe}")
        try:
            browser_pid, process, job_handle = _launch_managed_browser(
                browser_exe,
                dashboard_url,
                browser_profile_dir,
            )
            _log_debug(
                f"Launch result: pid={browser_pid}, process={process is not None}, job={job_handle is not None}"
            )
        except Exception as e:
            _log_debug(f"Launch exception: {e}")
            browser_pid = None
            process = None
            job_handle = None
        if browser_pid:
            if process is not None and job_handle is not None:
                _log_debug(f"Using managed browser with job object")
                return _guard_managed_browser(
                    process,
                    job_handle,
                    browser_pid_file,
                    browser_exe,
                    browser_profile_dir,
                    stopping_flag,
                )
            _log_debug(f"Browser launched without job object, writing pid file")
            browser_pid_file.parent.mkdir(parents=True, exist_ok=True)
            browser_pid_file.write_text(
                f"{browser_pid}\n{_normalize_path(browser_exe)}\n{_normalize_path(str(browser_profile_dir))}\n",
                encoding="utf-8",
            )
            return 0

    _log_debug(f"All managed browsers failed, using fallback")
    _open_url_fallback(dashboard_url, fallback_browser_exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
