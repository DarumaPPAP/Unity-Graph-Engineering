# External Intelligence / Execution Control Plane

Unity-Graph-EngineeringへIx、LoopX、TencentDB-Agent-Memoryの有効な設計を取り込みつつ、外部RuntimeへExecution Authorityを移さないNative Control Plane仕様です。

## Responsibility map

| Reference | Local implementation | Local role | Authority |
|---|---|---|---|
| `ix-infrastructure/Ix` | `Tools/IxAdapter/ix_adapter.py` | Optional Code Intelligence | Source / Testが正本 |
| `huangruiteng/loopx` | `Tools/ContinuationController/continuation_controller.py` | Continuation / Claim / Lease / Quota | `STATE/current.yaml` + Policy |
| `TencentCloud/TencentDB-Agent-Memory` | `Tools/LayeredMemoryController/layered_memory_controller.py` | Evidence-first Layered Memory | Raw Evidence + local state |
| Native integration | `Tools/ExecutionOrchestrator/execution_orchestrator.py` | Ordering / handshake / accounting coordination | Authorityを持たない |

## Why an Orchestrator

3 Controllerを個別に実装しただけでは、Callerが順序を間違える余地が残ります。

危険例:

- Human Gate待ちなのにIxでProject Scanを始める
- ClaimをStateへ書かず複数Workerが同じTodoを実行する
- Ix結果だけでMutationしDirect Source Readを省略する
- Evidence保存前にQuotaをSpendする
- RetryされたFinalizeでQuotaを二重消費する
- personalで保存したproject_internal Memoryをteam_safeで読む

そのため通常のGraph / Loop RuntimeはExecution Orchestratorの2 Phase Contractへ固定します。

## Canonical execution sequence

```text
PREPARE
  ↓
1. Validate graph_loop / Profile / Goal
  ↓
2. Continuation Evaluate
  ├─ Health / Human / Evidence / Focus / Budget / Quota block
  │      └─ STOP: Ix / Memoryも呼ばない
  ↓
3. Selected Todo確認
  ├─ Todo未materialize
  │      └─ STOP: Todo/Blockerを明示化
  ↓
4. Claim / Lease [multi-worker]
  ├─ 新規またはExpired Claim
  │      └─ STATEへdurable writeback → PREPAREを再実行
  ↓
5. Bounded Memory Projection
  ↓
6. Optional Ix Navigation [personal_full_control only]
  ↓
7. Direct Source Verification
  ├─ Mutationで未完了
  │      └─ Sourceを直接読む → PREPAREを再実行
  ↓
8. Integrity-bound Execution Ticket
  ↓
9. ONE bounded slice
  ↓
FINALIZE
  ↓
10. Ticket / Goal / Todo / Profile確認
  ↓
11. validated + writeback_complete確認
  ↓
12. Evidence file confinement / Scope確認
  ↓
13. L0 Raw Evidence保存
  ↓
14. Optional L1 Atom生成
  ↓
15. Stale State / Duplicate Accounting確認
  ↓
16. Quota Spend Projection
  ↓
17. required_state_writeback返却
  ↓
18. CallerがSTATE/current.yamlへ永続化
  ↓
Next PREPARE
```

## Execution Ticket

Ticketは任意Mutation権限ではありません。1回のbounded sliceを次へ拘束します。

- Goal ID
- Selected Todo ID
- Worker ID
- Execution Profile
- Work Kind
- Authoritative State fingerprint
- Direct Source Verification paths / Evidence refs

Canonical JSONをSHA-256でfingerprintし、Ticket自体にもdigestを付与します。

### Source verification

MutationではDirect Source Readが必須です。

- 明示Pathのみ
- Workspace外escape禁止
- TicketにはWorkspace-relative pathだけ保存
- MutationではSource Read Evidence Refも必須
- Ix impact/traceはSource Readの代替にならない

## Stale State semantics

Ticket発行後に正本Stateが変化した場合、Finalizeでstaleと判定します。

この時、すでにbounded sliceで得たEvidenceは捨てません。

```text
valid Ticket + valid Evidence
        ↓
L0 Evidenceを保全
        ↓
State fingerprint mismatch
        ↓
Quota Spend = NO
State Accounting Patch = NO
        ↓
reprepare_from_authoritative_state
```

これにより実際の検証結果を失わず、古いStateを前提とした成功Accountingだけを拒否します。

## Idempotency

`previous_slice.slice_id`と`previous_slice.quota_spent`をAccounting Markerにします。

同じSliceがすでにAccounting済みなら:

- Evidence IDは同内容なら冪等確認
- Quota Spend delta = 0
- 新しいSpendは発行しない

異なるSliceがすでにAccounting済みならEvidenceだけ保持し、State競合として停止します。

## Ix path

Ixは`personal_full_control`限定のOptional Navigation Layerです。

許可するPreflight Operation:

- `explain`
- `impact`
- `trace`
- `callers`
- `callees`

Orchestrator側でもTraceを最大depth=5 / cap=200に制限します。Adapter自身の既定はdepth=3 / cap=100です。

Ix unavailable/low-confidenceでもTaskを即失敗させず、Targeted Source ReadへFallbackします。`generic_planning` / `team_safe_import`ではIxを起動しません。

## Continuation path

Native Continuation Controllerが最初のGateです。

```text
Health → Human → Previous Writeback → Evidence → Focus → Budget → Quota → Todo / Capability
```

QuotaはPermissionでもBudgetでもありません。

複数WorkerではClaim/Lease ProjectionをStateへ書き戻す前にNavigationや実作業へ進みません。

## Layered Memory path

```text
Evidence/raw/<id>.txt
        ↓
STATE/memory/L0/<id>.json
        ↓ raw_refs
STATE/memory/L1/<id>.json
        ↓ atom_refs
STATE/memory/L2/<id>.json
        ↓ scenario_refs
STATE/memory/L3/<id>.json
```

### Scope model

| Scope | generic | personal | team_safe |
|---|---:|---:|---:|
| `public_reference` | ✓ | ✓ | ✓ |
| `portable_artifact` | ✓ | ✓ | ✓ |
| `project_internal` | ✗ | ✓ | ✗ |

- L1/L2/L3は最も厳しいParent Scopeを継承
- Scope downgrade禁止
- Scope無しLegacy Recordは`project_internal`としてFail Closed
- RetrievalはScope filterをrankingより先に実施
- Drilldownも各Layerで再確認
- Normal retrieve/projectにRaw contentを含めない
- Raw contentは明示drilldownだけ

Secret分類・高確度Credential patternはL0 Captureを拒否します。`promote`はProjectionのみでUnityAgent Knowledge/User Policyを直接変更しません。

## Authority boundaries

Execution Orchestratorは以下を**所有しません**。

- Project Source Mutation Authority
- `STATE/current.yaml` Authority
- Human Gate Authority
- Quota Policy Authority
- UnityAgent Knowledge / User Policy Authority

Orchestratorが返すのは`required_state_writeback`です。Callerが正本Stateへ永続化して初めて次のPhaseへ進めます。

## Failure matrix

| Failure | Evidence | Quota Spend | Next |
|---|---|---:|---|
| Continuation block | なし | No | reported action |
| Claim未Writeback | なし | No | ClaimをStateへ保存 |
| Ix unavailable | なし | No impact | targeted source read |
| Memory projection unavailable | 既存Raw維持 | No impact | Memoryなしで継続可 |
| Memory scope/raw contract breach | なし | No | Block |
| Direct Source Read未完了 | なし | No | Source Read |
| Ticket tamper | なし | No | reprepare |
| Evidence capture failure | 保存失敗 | No | capture修復 |
| Atom failure | Raw保持 | No | Atom修復 |
| Stale State | Raw保持 | No | reprepare |
| Quota Spend rejection | Raw保持 | No | accounting修復 |
| Duplicate Finalize | Raw確認 | 0 delta | State維持 |

## Validation

```bash
python -m compileall -q Tools Tests
python Tools/ExecutionPolicyValidator/validate_execution_policies.py
python -m unittest discover -s Tests/ExternalProviders -p "test_*.py" -v
```

CIはさらに:

- YAML syntax
- Draft 2020-12 JSON Schema validity
- Policy/implementation ordering coherence
- Ix Adapter tests
- Continuation Controller tests
- Layered Memory scope/security tests
- Execution Orchestrator transition/idempotency tests

を検証します。
