# Continuation Control — LoopX-inspired Contract

Long-running Graph / Loopの継続可否を、会話の勢いではなく型付きStateで決める。

## Separation

- **Gate**: 実行してよいか
- **Budget**: 最大どこまで消費してよいか
- **Quota**: eligibleなTaskへ次の実行枠を割り当てるか

QuotaはPermissionではない。Quotaが残っていてもHuman GateやEvidence Waitを越えてはいけない。

## Decision order

```text
Health Gate
  ↓
Human Gate
  ↓
Evidence Wait
  ↓
Focus Wait
  ↓
Compute Quota
  ↓
One bounded slice
  ↓
Evidence + Writeback
  ↓
Next decision
```

## Typed todo

Graph Nodeを再開可能にするため、次の仕事を`todo`として持つ。

- id
- owner
- status
- optional lease
- blocking gate
- evidence refs

複数Workerが同じTodoを選べる場合だけClaim/Leaseを使う。Single Workerでは過剰な分散制御を追加しない。

## Bounded slice

1回の継続は1 Nodeまたは1 Verification sliceまで。

終了時に必ず次をwrite backする。

- result summary
- evidence refs
- next todo or completion
- budget delta
- blocker if failed

Writebackなしで次のsliceへ進まない。

## Native authority

LoopX Runtimeを必須依存にしない。正本は`STATE/current.yaml`、`STATE/events.jsonl`、`Evidence/`、本RepositoryのPolicyである。外部LoopXを将来Adapterとして接続しても、Human GateとBudgetのauthorityは移譲しない。
