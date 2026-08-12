# Runtime Control State

Graph / Loop Runtimeの正本は会話履歴ではなく`STATE/current.yaml`です。

`STATE/`と`Evidence/`はRuntime生成物であり`.gitignore`対象です。RepositoryへCommitしません。

## Required safety state for Graph / Loop

Execution Orchestratorは次が明示されていないStateをFail Closedします。

```yaml
execution_mode: graph_loop
execution_profile: personal_full_control | generic_planning | team_safe_import
goal_id: string
goal_complete: boolean

health:
  ok: boolean

human_gate:
  required: boolean
  satisfied: boolean

evidence_wait:
  waiting: boolean

focus_wait:
  waiting: boolean

budget:
  remaining: boolean

quota:
  compute_share: 0.0..1.0
  allowed_slots: integer
  spent_slots: integer

worker:
  id: string
  multiple_workers: boolean

available_capabilities: []
todos: []
todos_truncated: boolean
```

欠落値を`false/true`へ推測しません。

## Claim writeback

複数WorkerでContinuation Controllerが新しいClaim/LeaseをProjectionした場合、Execution Orchestratorはそこで停止します。

```text
prepare
  ↓
claim projection
  ↓
required_state_writeback
  ↓
CallerがSTATE/current.yamlへatomic write
  ↓
prepareを再実行
```

Stateへ保存されていないClaimを「取得済み」と見なしてProject Navigationへ進みません。

## Ticket state fingerprint

Execution Ticketは発行時のAuthoritative State全体をSHA-256 fingerprintへ束縛します。

Finalize時にStateが変わっていた場合:

- 実際に得たRaw Evidenceは保持
- Quota Spendしない
- Final State Accounting Patchを返さない
- `reprepare_from_authoritative_state`

これにより、別WorkerやHuman操作でStateが進んだ後に古いTicketが成功Accountingを上書きすることを防ぎます。

## Finalize writeback

成功Finalizeは直接`STATE/current.yaml`を書かず、`required_state_writeback`を返します。

主なPatch:

```yaml
previous_slice:
  slice_id: ...
  todo_id: ...
  writeback_complete: true
  validated: true
  evidence_refs: [...]
  quota_spent: true
  quota_spend_id: spend-...
  orchestrated: true

quota:
  spent_slots: ...

orchestration:
  active_ticket_id: null
  last_quota_spend_id: spend-...
  required_next_action: write_finalization_to_authoritative_state
  last_status: ok

memory_projection:
  memory_ids: [...]
  raw_evidence_refs: [...]
```

CallerはこのPatchをAuthoritative Stateへdurable/atomicに反映してから次の`prepare`へ進みます。

## Idempotency

`previous_slice.slice_id + quota_spent`をQuota AccountingのIdempotency Markerとして使用します。

同じSliceをFinalizeし直した場合:

- Raw Evidence IDは同内容なら冪等確認
- Quota Spend delta = 0
- 追加Accountingを発行しない

異なるSliceがすでに`quota_spent=true`なら新しいEvidenceは保持してAccountingを停止します。

## State authority

Execution OrchestratorはState Authorityではありません。

```text
Orchestrator
  = decision / ticket / patch projection

Caller / State Store
  = STATE/current.yaml durable write authority
```

State Storeを実装する場合もHuman Gate / Profile / Claim / Quotaの意味を書き換えてはいけません。
