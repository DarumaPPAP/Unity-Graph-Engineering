# Continuation Control — Native LoopX-inspired Controller

Long-running Graph / Loopの継続可否を、会話の勢いではなく型付きStateと決定的なControllerで決める。

## Separation

- **Gate**: 実行してよいか
- **Budget**: 最大どこまで消費してよいか
- **Quota**: eligibleなTaskへ次の実行枠を割り当てるか

QuotaはPermissionではない。Quotaが残っていてもHuman GateやEvidence Waitを越えてはいけない。

## Decision order

```text
Goal complete?
  ↓ no
Health Gate
  ↓
Human Gate
  ↓
Previous Slice Writeback / Validation
  ↓
Evidence Wait
  ↓
Focus Wait
  ↓
Budget Guard
  ↓
Compute Quota
  ↓
Todo / Lease / Capability Preflight
  ↓
One bounded slice
  ↓
Evidence + Durable Writeback
  ↓
Quota Spend
  ↓
Next decision
```

## Native controller

実装:

```text
Tools/ContinuationController/continuation_controller.py
```

外部LoopX Runtimeは不要。Python標準ライブラリだけで動作する。

Controllerは`STATE/current.yaml`を直接編集しない。正本から必要な状態だけをJSON Projectionとして入力し、Decision / Claim / Spend ProjectionをJSONで返す。呼び出し側がEvidenceと一緒に正本へwrite backする。

### Evaluate

```bash
python Tools/ContinuationController/continuation_controller.py evaluate \
  --input continuation-input.json
```

主要出力:

- `decision`: `run | ask_human | wait | blocked | complete`
- `should_run`
- `lane`
- `reason_code`
- `effective_action`
- `must_attempt_work`
- `normal_delivery_allowed`
- `selected_todo`
- `runnable_candidates`
- `blocked_candidates`
- `capability_gate`
- `quota`

`should_run=true`でも、1回で実行してよいのは1 Nodeまたは1 Verification sliceだけ。

### Claim / Lease

複数Workerが同じTodoを取得できる場合は、実行直前にClaim Projectionを生成する。

```bash
python Tools/ContinuationController/continuation_controller.py claim \
  --input continuation-input.json \
  --lease-seconds 900
```

- Activeな他Worker Leaseは候補から除外する。
- Expired Leaseは再取得可能として扱う。
- Single WorkerではClaimを必須にしない。
- LeaseはHuman Gateを上書きしない。

### Quota Spend

Quotaは**実行前に消費しない**。Slice完了後、次の条件を満たした場合だけSpend Projectionを作る。

1. `writeback_complete=true`
2. `validated=true`
3. `evidence_refs`が1件以上ある
4. Spend後に`allowed_slots`を超えない

```bash
python Tools/ContinuationController/continuation_controller.py spend \
  --input continuation-input.json \
  --slots 1
```

## Typed todo

Todoは最低限次を持つ。

- `id`
- `status`
- `task_class`
- optional `lease`
- optional `required_capabilities`

`task_class`:

- `advancement_task`: Goalを進める実行候補
- `continuous_monitor`: 状態変化待ちの観測。変化がなければquiet skip

Todo Projectionがtruncatedの場合、隠れたopen todoをadvancementとして保守的に扱い、通常Deliveryを直接再開せず`materialize_advancement_todo_or_blocker`を要求する。

## Capability preflight

Todo単位で`required_capabilities`を宣言できる。

既定利用可能Capability:

- `shell`
- `filesystem_read`
- `filesystem_write`

Local bridge不足は`capability_repair`へ送る。`credentials`、`production_access`、`human_review`などOwner保持Capabilityは`ask_human`へ送る。

CapabilityはQuotaでもPermissionでもない。単に「このTodoを今の実行環境で実行可能か」を判定するPreflightである。

## Quota model

既定:

- `compute_share=1.0`
- `window_hours=24`
- `slot_minutes=1`

`allowed_slots`未指定時:

```text
floor(window_hours * 60 / slot_minutes * compute_share)
```

`compute_share=0`はGoal削除ではなく自動継続Pause。`spent_slots >= allowed_slots`はThrottle。

## Bounded slice writeback

1回の継続終了時に必ず次をwrite backする。

- result summary
- evidence refs
- next todo or completion
- budget delta
- blocker if failed

Writebackなしで次のsliceへ進まない。

## Native authority

正本は`STATE/current.yaml`、`STATE/events.jsonl`、`Evidence/`、本RepositoryのPolicyである。外部LoopXを将来Adapterとして接続しても、Human Gate、Budget、Evidence Admissionのauthorityは移譲しない。

Schema:

- `schemas/continuation-state.schema.yaml`
- `schemas/execution-state.schema.yaml`

Policy:

- `policies/continuation-control.yaml`
