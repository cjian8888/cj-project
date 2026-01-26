---
name: handover
description: 移交协议 (Handover) - 用于在不同会话间生成和读取项目进度快照。
---

# Skill: 移交协议 (Handover Protocol)
## 触发指令 (Triggers)
- "生成接力快照", "保存进度", "交接工作"
- "读取接力快照", "恢复工作", "加载进度"

## Usage
- **Generate Snapshot**: When user says "生成接力快照", summarize:
  1. Active files (e.g., api_server.py).
  2. Identified anomalies.
  3. Next immediate steps.
  - Save to `MISSION_SNAPSHOT.md`.
- **Load Snapshot**: When user says "读取接力快照", read `MISSION_SNAPSHOT.md` and restore context.
