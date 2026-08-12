# MyUnityMCP Final Completion Graph

This is the case-specific execution contract for completing the current MyUnityMCP roadmap with Codex and validating it against the local `CG` Unity project.

## Why this is a dedicated branch

The general GraphEngineering framework remains on `main`. This case lives on `feature/myunitymcp-final-completion` so MyUnityMCP-specific goals, assumptions, validation fixtures, and promotion rules do not become generic framework policy.

Product changes are isolated again in `DarumaPPAP/MyUnityMCP` on `graph/myunitymcp-final-completion`, created from the current 77-tool candidate baseline. Only verified changes should later be promoted to `delivery/stage2-8-integration` after a Human Gate.

## Local CG validation

`CG` is not controlled through a GitHub validation branch. Codex resolves the local Unity project directly and uses it as the integration environment.

Default boundary:

- existing CG assets: read-only
- validation artifacts: `Assets/__MyUnityMcpValidation/**`
- CG remote push: prohibited
- persistent ProjectSettings changes: Human Gate
- unrelated package installation: prohibited
- transient MyUnityMCP package binding: allowed only when needed for this goal, with exact before-state and rollback evidence

This gives the verifier real Unity project coverage without turning CG into a second product branch or polluting existing production content.

## Current product surface

The candidate target is 77 tools:

- Graphics 32
- Agent 10
- WorldCreator 3
- Profiler 8
- Addressables 4
- UI 5
- Animation 5
- Audio 5
- Cinematic 5

Explicitly excluded:

- Player Build Domain
- Addressables Content Build
- MovieCreator runtime
- LiveCreator runtime

Addressables remains focused on inspect / prepare_entry / apply_entry / get_support_matrix. Package absence is an expected `UNSUPPORTED` condition and never authorizes automatic installation.

## Completion flow

```text
Freeze Authority
  -> Reconcile Current Roadmap
  -> Implement Remaining Gaps
  -> Static Contract Verification
  -> Bind Local CG
  -> Compile + Exact 77 Discovery
  -> Agent Capability Check
  -> Read-only Smoke
  -> Shared Safety Contract
  -> Isolated Validation Fixtures
  -> Profiler / Addressables / UI / Animation / Audio / Cinematic E2E
  -> Agent Delegation
  -> Timeout / Cancel / Reload Regression
  -> Cross-domain Workflow
  -> Production 45 Regression
  -> Final Contract/Evidence Update
  -> CG Cleanup
  -> Promotion Readiness
  -> HUMAN GATE
```

Failures stay inside the owning node. Codex may make a minimal root-cause repair and retry up to three times. The same failure signature twice stops the node and produces a BLOCKED report instead of endless mutation.

## Promotion boundary

The graph can finish only at `PROMOTION_READY` or `BLOCKED`.

It must not automatically:

- merge `graph/myunitymcp-final-completion` into `delivery/stage2-8-integration`
- mark MyUnityMCP PR #39 ready
- merge PR #39 into main

Those remain explicit Human Gates.
