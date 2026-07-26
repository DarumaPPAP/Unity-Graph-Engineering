# Authoring Unity Workflows

新しいWorkflowは「Agentを何人使うか」ではなく「何を判定可能にするか」から設計する。

## 1. Single Goal

1文で完了条件を説明できない場合、Workflowを分ける。

Good:

```text
Switch向けに対象透明EffectのGPU時間を20%削減し、固定Camera Captureで見た目を維持する。
```

Bad:

```text
Renderingを全部良くする。
```

## 2. Explicit Non-goals

Workflowが触らない範囲を定義する。

- Package更新なし
- ProjectSettings変更なし
- Scene構造変更なし
- Architecture rewriteなし

## 3. Node Design

Nodeは次の条件を満たす。

- one owner
- one purpose
- explicit inputs
- explicit outputs
- verifiable result
- bounded write scope

## 4. Edge Audit

各`depends_on`について質問する。

> 後段は前段Outputを実際に読むか。

NoならEdgeを削除する。並列化できる可能性がある。

## 5. Loop Design

Action Nodeには以下を定義する。

- Action
- Observation
- Evaluator
- Success condition
- Failure condition
- Maximum attempts
- Escalation

## 6. Verification

Acceptance CriterionごとにEvidenceを指定する。

```yaml
acceptance:
  - criterion: Unity compile error 0
    evidence: batchmode log
  - criterion: visual target maintained
    evidence: fixed-camera before/after capture
  - criterion: GPU improvement >= 20%
    evidence: same-condition profiler capture
```

## 7. Human Handoff

Human Gateは高Cost Actionへ配置する。

- merge
- delete
- package
- project settings
- scene replacement
- visual trade-off

曖昧な入力、最大Attempt到達、Evidence取得不可もEscalation対象。

## 8. Readiness

最初はL1 ReportとしてSourceを変更せずに試す。RoutingとStateが安定した後、L2 Assistedで小規模変更を許可する。

L3へ上げる条件:

- 複数回の実Run
- Verifierの誤承認率が低い
- BudgetとKill Switchが機械的に適用される
- StateとRun Logで監査可能
- Path Allowlistがある

## 9. Review Checklist

- [ ] Goalが1つ
- [ ] Non-goalsが明示
- [ ] NodeにOwnerとOutputがある
- [ ] Fake Edgeがない
- [ ] 1 Artifact 1 Writer
- [ ] Loopに最大Attemptがある
- [ ] MakerとCheckerが分離
- [ ] Evidenceが機械判定または再確認可能
- [ ] Human Gateが定義
- [ ] State write-backがある
