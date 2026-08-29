# Repository archived by architecture cutover

Status: **LEGACY / READ-ONLY BY POLICY**

This repository is no longer an active execution, orchestration, runtime, persistence, policy, context, or evaluation authority.

The canonical writable source of truth is now:

- `DarumaPPAP/UnityAgent`
- Phase 8 cutover merge: `5345dfb1238abd7ed84f1eb9eea60f79e4a1e2e0`
- Human-reviewed Phase 8 head: `9451949f09199b0cdd219427a32e4dfc89f83284`

## Rules after cutover

- Do not add new production behavior here.
- Do not restore UnityAgent dependencies on this repository.
- Do not use this repository as a writable source of truth.
- Preserve existing history only for migration provenance and audit/reference purposes.
- New Graph / Loop / Runtime / Eval work belongs in `DarumaPPAP/UnityAgent` under its canonical module ownership.

## Archive boundary

The Phase 8 Human Gate was approved and PR #60 was merged into UnityAgent main. UnityAgent main CI passed after merge.

This marker records the final policy-level transition. GitHub's repository-level `archived=true` setting should remain aligned with this state.
