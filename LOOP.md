# Graph / Loop Runtime Contract

このFileはGraph / Loop Engineeringで使用するLoop境界だけを説明します。Budget数値、Mode選択、State Schemaは各機械可読正本を参照します。

- Mode: `policies/execution-mode.yaml`
- Budget: `policies/graph-loop-budget.yaml`
- State: `schemas/execution-state.schema.yaml`
- Evidence: `schemas/evidence.schema.yaml`

## Loop placement

LoopはGraph全体を無条件に回す仕組みではなく、一つのAction Node内部へ閉じ込めます。

```text
Typed Input
   ↓
Action
   ↓
Observe Evidence
   ↓
Independent Evaluate
   ├─ APPROVE
   ├─ LOCAL_RETRY
   ├─ LOCAL_PATCH
   ├─ REPLAN
   └─ ESCALATE_HUMAN
```

## Required node contract

各Action Nodeは次を持ちます。

- Input schema
- Owned artifacts
- Single writer
- Action
- Observable evidence
- Acceptance criteria
- Attempt budget
- Failure signature
- Recovery destination
- Output schema

## Retry rules

- 同じFailure Signatureを新しい仮説なしで繰り返さない。
- TestやValidationを無効化して通過させない。
- Scopeを広げて失敗を隠さない。
- Makerは自分のNodeをAPPROVEしない。
- Node Budgetを超える前に停止する。

## Replan boundary

局所Retryで解決できない場合だけGraphをReplanします。

Replan理由:

- 前提がEvidenceで否定された
- 必須Dependencyが新たに判明した
- Goal Contract内でNode分割が不適切だった

Goal、互換性、破壊的Scopeの変更はAgentだけでReplanせず、Human Decisionへ送ります。

## State write-back

AttemptごとにTranscript全文を保存しません。次を追記します。

- Node ID
- Attempt
- Hypothesis
- Action summary
- Evidence reference
- Verdict
- Budget delta
- Next transition

完了項目はHistoryへ移し、`current.yaml`には現在の実行に必要な情報だけを残します。

## Readiness

- Assisted execution
- Auto-merge disabled
- Unattended mutation disabled
- Human Gate enabled
- Prompt is the default mode
