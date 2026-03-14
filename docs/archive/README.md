# Archive Guide

本目录用于收纳已退出主工作区、但仍需要保留的历史材料。

- `root-history/`: 原先堆在根目录的阶段性记录、修复说明、交接文档和历史报告。
- `root-history/`: 也收纳历史待办、状态快照与阶段性问题清单。
- `dashboard-backups/`: 不参与当前前端运行的备份主题与旧版 UI 文件。
- `legacy-root-frontend/`: 根目录遗留的早期 Vite 脚手架文件，当前正式前端位于 `dashboard/`。
- `legacy-modules/`: 已脱离当前主链路、但暂时保留源码供参考的历史模块。
- `assets/`: 与历史文档配套的截图和图片。

当前主开发入口仍然是：

- 后端：`api_server.py`
- 前端：`dashboard/`
- 测试：`tests/`
