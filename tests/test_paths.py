#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径层的打包态回归测试。"""

from pathlib import Path

import paths


def test_resource_root_prefers_meipass_when_frozen(monkeypatch):
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", r"D:\bundle\_internal", raising=False)
    monkeypatch.setattr(paths.sys, "executable", r"D:\bundle\fpas.exe", raising=False)

    assert paths.get_app_root() == Path(r"D:\bundle")
    assert paths.get_resource_root() == Path(r"D:\bundle\_internal")
    assert paths.get_dashboard_dist_dir() == Path(
        r"D:\bundle\_internal\dashboard\dist"
    )
