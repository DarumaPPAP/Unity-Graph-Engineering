# Unity Loop Design

LoopはTask GraphのNode内部で、Agentが観測と評価を繰り返す仕組み。

## Required Fields

```yaml
loop:
  input: []
  action: ""
  observation: []
  evaluator: ""
  success_condition: []
  failure_condition: []
  max_attempts: 3
  escalation: []
```

## Maker / Checker

Maker:

- SourceやAssetを変更する
- 変更理由とExpected Resultを残す
- Testを実行してEvidenceを提供する
- APPROVE判定は行わない

Checker:

- Acceptance ContractとDiffだけから判定する
- 必要なTestを独立実行する
- Scope拡大、Test無効化、偶然のPassをRejectする
- `APPROVE | REJECT | ESCALATE_HUMAN`を返す

## Unity Loop Examples

### Compile Fix

```text
Error Log
  → smallest hypothesis
  → minimal source change
  → Unity compile
  → verifier evaluates original error and new errors
```

### Visual Correction

```text
Reference + current capture
  → one visual hypothesis
  → Scene/Material/Shader change
  → same-camera capture
  → visual verifier compares acceptance dimensions
```

### Performance Optimization

```text
Fixed capture baseline
  → one bottleneck hypothesis
  → minimal optimization
  → same capture measurement
  → verifier checks gain and visual/function regression
```

## Stop Conditions

Stop and escalate when:

- 3 attempts reached
- same failure signature occurs twice
- evidence cannot be collected
- goal changed during implementation
- required Platform or device is unavailable
- risk path requires human approval

## Anti-patterns

- Endless compile-fix loop without changing the hypothesis
- Verifier receiving the full Maker conversation and inheriting its assumptions
- Retrying flaky tests until green without investigating the flake
- Increasing scope after each failure
- Rewriting Architecture to avoid a local acceptance criterion
- Declaring visual success without a comparable capture

## Readiness Levels

- L0 Draft: intent and workflow only
- L1 Report: inspect and update state; no source mutation
- L2 Assisted: small changes in a branch with independent verifier and human merge
- L3 Unattended: bounded automation with budgets, gates, logs, kill switch, and proven reliability

Unity Graph Engineering remains L1/L2 until real pilot runs show stable verification.
