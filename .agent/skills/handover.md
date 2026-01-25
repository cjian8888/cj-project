# Skill: @handover
## Description
Used to seamlessly transfer the context of the F.P.A.S (Fund Penetration Audit System) project between different agent sessions or accounts.

## Instruction
1. When user says "Generate Handover Snapshot":
   - Summarize current progress on F.P.A.S (e.g., active debugging tasks in `api_server.py`, identified fund anomalies).
   - List the immediate next steps (e.g., "Fix 'black screen' bug in Dashboard").
   - Save this summary to `MISSION_SNAPSHOT.md` in the root directory.
   
2. When user says "Load Handover Snapshot":
   - Read `MISSION_SNAPSHOT.md`.
   - Adopt the persona of the "Audit Project Lead".
   - Confirm readiness to continue from the exact point left off.
