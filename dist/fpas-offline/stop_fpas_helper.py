#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stop FPAS package processes for the current delivery root."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
CreateToolhelp32Snapshot.restype = wintypes.HANDLE
Process32FirstW = kernel32.Process32FirstW
Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
Process32FirstW.restype = wintypes.BOOL
Process32NextW = kernel32.Process32NextW
Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
Process32NextW.restype = wintypes.BOOL
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE
QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
QueryFullProcessImageNameW.restype = wintypes.BOOL
CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


def _normalize_path(value: str) -> str:
    return os.path.normcase(os.path.abspath(value))


def _normalize_command_text(value: str) -> str:
    return str(value or "").strip().lower().replace("/", "\\")


def _iter_processes():
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        has_entry = Process32FirstW(snapshot, ctypes.byref(entry))
        while has_entry:
            yield {
                "pid": int(entry.th32ProcessID),
                "parent_pid": int(entry.th32ParentProcessID),
                "name": entry.szExeFile,
            }
            has_entry = Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        CloseHandle(snapshot)


def _query_process_image_path(pid: int) -> str | None:
    handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        CloseHandle(handle)


def _kill_pid(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _iter_wmic_process_rows():
    try:
        result = subprocess.run(
            ["wmic", "process", "get", "ProcessId,ExecutablePath,CommandLine", "/format:csv"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []

    output_text = str(result.stdout or "").strip()
    if not output_text:
        return []

    rows = []
    reader = csv.DictReader(io.StringIO(output_text))
    for row in reader:
        if not row:
            continue
        pid_text = str(row.get("ProcessId", "") or "").strip()
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        rows.append(
            {
                "pid": pid,
                "command_line": str(row.get("CommandLine", "") or "").strip(),
                "executable_path": str(row.get("ExecutablePath", "") or "").strip(),
            }
        )
    return rows


def _collect_managed_browser_pids(browser_image_hint: str, browser_profile_hint: str) -> set[int]:
    normalized_image_hint = _normalize_path(browser_image_hint) if browser_image_hint else ""
    normalized_profile_hint = _normalize_command_text(browser_profile_hint)
    browser_pids: set[int] = set()

    for row in _iter_wmic_process_rows():
        executable_path = str(row.get("executable_path", "") or "").strip()
        if not executable_path:
            continue
        normalized_executable_path = _normalize_path(executable_path)
        if normalized_image_hint and normalized_executable_path != normalized_image_hint:
            continue

        command_line = str(row.get("command_line", "") or "")
        normalized_command_line = _normalize_command_text(command_line)
        if normalized_profile_hint and normalized_profile_hint not in normalized_command_line:
            continue

        browser_pids.add(int(row["pid"]))

    return browser_pids


def _kill_pid_set(pids: set[int], label: str) -> None:
    remaining_pids = {int(pid) for pid in pids if int(pid) > 0}
    if not remaining_pids:
        return

    for _ in range(5):
        active_pids = []
        for pid in sorted(remaining_pids):
            if _query_process_image_path(pid):
                active_pids.append(pid)
        if not active_pids:
            return
        for pid in active_pids:
            print(f"[FPAS] 正在结束{label} PID={pid}")
            _kill_pid(pid)
        time.sleep(0.8)
        remaining_pids = set(active_pids)


def _remove_tree_with_retries(path: Path, attempts: int = 10, sleep_s: float = 0.5) -> bool:
    if not path.exists():
        return True
    for _ in range(max(attempts, 1)):
        try:
            shutil.rmtree(path)
            return True
        except OSError:
            time.sleep(sleep_s)
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def main() -> int:
    root = Path(__file__).resolve().parent
    runtime_python = _normalize_path(str(root / "runtime" / "python" / "python.exe"))
    server_pid_file = root / "run" / "server.pid"
    browser_pid_file = root / "run" / "browser.pid"
    browser_profile_dir = root / "run" / "browser-profile"
    stopping_flag = root / "run" / "stopping.flag"
    self_pid = os.getpid()
    processes = list(_iter_processes())
    process_map = {proc["pid"]: proc for proc in processes}
    python_pids: set[int] = set()
    browser_pids: set[int] = set()
    cmd_pids: set[int] = set()

    stopping_flag.parent.mkdir(parents=True, exist_ok=True)
    try:
        stopping_flag.write_text("stopping\n", encoding="ascii")
    except OSError:
        pass

    for proc in processes:
        pid = proc["pid"]
        if pid == self_pid:
            continue
        image_path = _query_process_image_path(pid)
        if image_path is None:
            continue
        if _normalize_path(image_path) != runtime_python:
            continue
        python_pids.add(pid)
        parent = process_map.get(proc["parent_pid"])
        if parent and str(parent["name"]).lower() == "cmd.exe":
            cmd_pids.add(parent["pid"])

    if server_pid_file.exists():
        try:
            recorded_pid = int(server_pid_file.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            recorded_pid = 0
        if recorded_pid and recorded_pid != self_pid:
            python_pids.add(recorded_pid)

    browser_guard_pid = 0
    browser_pid = 0
    browser_image_hint = ""
    browser_profile_hint = _normalize_path(str(browser_profile_dir))
    if browser_pid_file.exists():
        try:
            browser_lines = [line.strip() for line in browser_pid_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError:
            browser_lines = []
        if len(browser_lines) >= 5 and browser_lines[4] == "managed-job":
            try:
                browser_guard_pid = int(browser_lines[0])
            except ValueError:
                browser_guard_pid = 0
            try:
                browser_pid = int(browser_lines[1])
            except ValueError:
                browser_pid = 0
            if len(browser_lines) > 2:
                browser_image_hint = _normalize_path(browser_lines[2])
            if len(browser_lines) > 3:
                browser_profile_hint = _normalize_path(browser_lines[3])
        elif browser_lines:
            try:
                browser_pid = int(browser_lines[0])
            except ValueError:
                browser_pid = 0
            if len(browser_lines) > 1:
                browser_image_hint = _normalize_path(browser_lines[1])
            if len(browser_lines) > 2:
                browser_profile_hint = _normalize_path(browser_lines[2])
        if browser_guard_pid and browser_guard_pid != self_pid:
            python_pids.add(browser_guard_pid)
        if browser_pid and browser_pid != self_pid:
            current_image_path = _query_process_image_path(browser_pid)
            if current_image_path:
                normalized_image_path = _normalize_path(current_image_path)
                if not browser_image_hint or normalized_image_path == browser_image_hint:
                    browser_pids.add(browser_pid)

    if not python_pids and not browser_pids and not cmd_pids:
        print("[FPAS] 未发现当前交付包的运行中后端进程")
        return 0

    _kill_pid_set(python_pids, "后端进程")
    time.sleep(1.0)
    if browser_image_hint or browser_profile_hint:
        browser_pids.update(_collect_managed_browser_pids(browser_image_hint, browser_profile_hint))
    browser_pids.discard(self_pid)
    _kill_pid_set(browser_pids, "受控浏览器")
    _kill_pid_set(cmd_pids, "关联启动窗口")

    if server_pid_file.exists():
        try:
            server_pid_file.unlink()
        except OSError:
            pass

    if browser_pid_file.exists():
        try:
            browser_pid_file.unlink()
        except OSError:
            pass

    _remove_tree_with_retries(browser_profile_dir, attempts=12, sleep_s=0.5)
    if stopping_flag.exists():
        try:
            stopping_flag.unlink()
        except OSError:
            pass

    print("[FPAS] 停止脚本执行完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
