# Codex Starter — MyUnityMCP Final Completion

Use `Unity-Graph-Engineering` as the execution control-plane source of truth and run the dedicated MyUnityMCP completion graph.

## Goal

Execute:

- `goals/myunitymcp-final-completion.yaml`
- `workflows/myunitymcp-final-completion.yaml`
- `policies/myunitymcp-validation.yaml`
- `templates/myunitymcp-validation-state.yaml`

Execution mode is explicitly authorized as `graph_loop` with `personal_full_control` for this goal.

## Repositories / workspaces

Product repository:

- `DarumaPPAP/MyUnityMCP`
- work only on `graph/myunitymcp-final-completion`
- branch was created from candidate `4bbe412e64126a22a94b255ef2001feb215c7b14`
- do not mutate `main` or `delivery/stage2-8-integration` directly

Validation project:

- local Unity project named `CG`
- access it directly from the local Codex workspace/filesystem
- do not require or use a CG GitHub validation branch
- do not push CG validation work to GitHub
- discover the real local path; do not invent one

## Execution rules

1. Reconcile the current roadmap from repository sources before implementing anything. Superseded 85/79-tool plans are historical only.
2. Current target is exactly 77 tools: Graphics 32, Agent 10, WorldCreator 3, Profiler 8, Addressables 4, UI 5, Animation 5, Audio 5, Cinematic 5.
3. Player Build Domain and Addressables Content Build are out of scope and must not be reintroduced.
4. Modify MyUnityMCP only on `graph/myunitymcp-final-completion`.
5. Use CG as the real Unity integration project. Existing CG production assets are read-only by default.
6. Put validation fixtures only under `Assets/__MyUnityMcpValidation/**`.
7. If CG does not already load the candidate, a transient local MyUnityMCP package binding is authorized for this goal. Capture the original manifest, change only the MyUnityMCP binding, and preserve a deterministic rollback. Do not install unrelated packages or modify ProjectSettings.
8. Run implementation -> independent verification -> minimal repair loops. Maximum three attempts per mutating node; stop after the same failure signature twice.
9. Never call Player Build or Addressables Content Build. Do not auto Save, full Bake, Force, or bypass safety.
10. `unavailable` is not PASS. GitHub Actions with `steps=null` remain `not_verified`.
11. Store raw evidence/state outside chat according to GraphEngineering rules.
12. Stop at `PROMOTION_READY`. Do not merge into `delivery/stage2-8-integration`, do not mark PR #39 ready, and do not merge main.

## Required final report

Report:

- reconciled roadmap
- final MyUnityMCP branch HEAD
- local CG path actually used
- compile/discovery result and exact tool composition
- every quality gate and raw evidence reference
- repairs performed and attempts consumed
- CG files created/modified and rollback status
- excluded build surfaces confirmation
- remaining unavailable gates
- `PROMOTION_READY` or `BLOCKED`
- exact human action required next

Begin with `freeze-authority`; do not skip directly to implementation.
