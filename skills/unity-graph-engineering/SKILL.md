---
name: unity-graph-engineering
description: Use only after explicit user selection or approved escalation when Unity work requires multiple subsystems, independent branches, bounded iteration, runtime or visual evidence, migration, rollback, or separate verification. Owns the typed task graph, execution orchestration, continuation control, optional code intelligence, layered execution memory, and bounded node loops. Do not use for bounded work suitable for unity-prompt-execution.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
metadata:
  version: "2.4.0"
---

# Unity Graph / Loop Engineering

複雑なUnity作業を、型付きTask Graphと上限付きNode Loopで制御する実行Skillです。

このSkillは無指定依頼の既定入口ではありません。`unity-execution-router`で明示指定またはユーザー承認された場合だけ使用します。Graph / Loopへ自動変更しません。

## Required inputs

1. Mode decision
2. Goal Contract
3. Project Contextまたは最小手動要件
4. UnityAgent Context Index
5. 選択したDomain Context Pack
6. `policies/graph-loop-budget.yaml`
7. Human Gate

全Skill、全Reference、全Toolを一括で公開しません。Ix / LoopX / TencentDB-Agent-Memoryの外部RuntimeはRequired inputではありません。

## Goal Contract

```yaml
goal: []
deliverables: []
acceptance_criteria: []
constraints:
  environment: {}
  allowed_mutation: []
  forbidden_mutation: []
compatibility: []
required_evidence: []
human_gates: []
recovery: {}
```

コード生成やCompile成功そのものをGoalにしません。

## Task Graph

- Nodeは一人のOwnerへ渡せる一責務Jobにする。
- Edgeは後段が前段の型付きOutputを読む場合だけ作る。
- Fake Edgeを削除する。
- 一つのArtifactにWriterを一人だけ割り当てる。
- 独立Branchがない場合は並列化しない。
- Merge Ownerを一人に固定する。

## Canonical execution path

通常の`graph_loop`実行では、Ix / Continuation / Memoryを個別に好きな順序で呼ばず、`Tools/ExecutionOrchestrator/execution_orchestrator.py`をControl Planeの標準入口にします。

```text
prepare
  ↓
Continuation Gate
  ├─ Health / Human / Evidence / Focus / Budget / Quota block → STOP
  ↓
Claim / Lease
  ├─ 新規Claim → STATEへdurable writeback → prepareを再実行
  ↓
Bounded Memory Projection
  ↓
Optional Ix Navigation (personal_full_control only)
  ↓
Direct Source Read
  ├─ Mutationで未完了 → Sourceを読む → prepareを再実行
  ↓
Execution Ticket
  ↓
ONE bounded Node / Verification slice
  ↓
finalize
  ↓
L0 Raw Evidence
  ↓
Optional L1 Atom
  ↓
Quota Spend Projection
  ↓
STATE/current.yaml durable writeback
  ↓
次のprepare
```

### Orchestrator authority

Orchestratorは順序と契約を調停しますが、次のAuthorityは持ちません。

- Project Source Mutation
- `STATE/current.yaml`
- Human Gate
- Quota Policy
- UnityAgent Knowledge / User Policy

つまりExecution Ticketは「任意変更の許可証」ではなく、**特定Goal / Todo / Worker / Profile / State fingerprint / Source verificationへ拘束された1 bounded sliceの実行契約**です。

### Prepare

`prepare`は最初にContinuationを評価します。`should_run=false`ならMemoryもIxも呼ばず終了します。

複数Workerで新しいClaim/Leaseが必要な場合、Projectionだけ返して停止します。CallerがClaimを`STATE/current.yaml`へ書き戻した後に`prepare`を再実行してください。Claimを永続化せずにProject NavigationやMutationへ進みません。

MutationではDirect Source Readが必須です。Ix結果はNavigation Layerであり、Source Read完了の代替にしません。

### Finalize

`finalize`は以下をすべて満たすまでQuotaをSpendしません。

1. Ticket integrity OK
2. Todo / Goal / Profile一致
3. `writeback_complete=true`
4. `validated=true`
5. Evidence fileがWorkspace内
6. L0 Raw Evidence保存成功
7. Optional Atom生成成功

Evidence保存後にQuota Spendが拒否された場合、Evidenceは捨てません。ただしQuota Patchは返さず、Accounting問題を解決するまで次のsliceへ進みません。

同じ`slice_id`がすでに`quota_spent=true`なら再Finalizeは冪等処理し、追加Spendしません。

正本: `policies/execution-orchestration.yaml`、`schemas/execution-orchestration.schema.yaml`

## Optional code intelligence

`personal_full_control`でIxが利用可能な場合だけ、構造探索・Trace・Impact Analysisへ使用できます。

- IxはNavigation LayerでありSource of Truthではありません。
- Provider unavailableでも`targeted_source_read`へFallbackします。
- Mutation前には対象Sourceを直接読みます。
- Graph結果だけでRuntime / Visual / Performance GateをPASSにしません。
- `generic_planning` / `team_safe_import`ではOrchestratorからIxを起動しません。

詳細: `references/code-intelligence-provider.md`、`policies/external-providers.yaml`

## Continuation control

LoopX由来のObjective / Typed Todo / Claim / Lease / Quota / Evidence Writeback思想をNative Controllerとして利用します。

実装: `Tools/ContinuationController/continuation_controller.py`

- `evaluate`: `should_run`とLaneを決定
- `claim`: Claim/Lease Projection
- `spend`: 検証済みWriteback + Evidence後だけQuota Spend Projection
- Controllerは`STATE/current.yaml`を直接編集しない
- `advancement_task`だけ通常Deliveryを開始可能
- `continuous_monitor`だけならMaterial Transitionがない限りquiet skip
- Activeな他Worker Leaseは飛ばし、Expired Leaseは再取得可能

**QuotaはPermissionでもBudgetでもありません。** Human GateやSafety Gateを上書きできません。

詳細: `references/continuation-control.md`、`policies/continuation-control.yaml`

## Layered memory

長いTool Outputや過去Turnは、`Tools/LayeredMemoryController/layered_memory_controller.py`でEvidence-firstなLayered Memoryへ落とします。

```text
L0 Raw Evidence
    ↓ raw_refs
L1 Atom
    ↓ atom_refs
L2 Scenario
    ↓ scenario_refs
L3 Reusable Candidate
```

- L0 Rawは`Evidence/raw/`へSource-faithfulに保持しSHA-256を記録する
- 通常の`retrieve` / `project`ではRaw contentをContextへ載せない
- 既定8件/6000文字、最大20件/12000文字
- Raw content展開は明示`drilldown`時だけ
- `project_internal`は`personal_full_control`だけが読める
- `generic_planning` / `team_safe_import`は`portable_artifact` / `public_reference`だけを読める
- ScopeはL0→L1→L2→L3へ最も厳しい親Scopeを継承し、downgrade禁止
- Scopeの無いLegacy Recordは`project_internal`としてFail Closed
- Secret分類や高確度Credential patternは保存しない
- Conflictは`supersedes` / `conflicts_with`で保持しsilent overwriteしない
- `promote`はProjectionだけで、UnityAgent KnowledgeやUser Policyを直接変更しない

Symbolic ProjectionはContext圧縮用でありState authorityではありません。

詳細: `references/layered-memory.md`、`policies/memory-layering.yaml`

## Node loop

LoopはNode内部だけで実行します。

```text
Input -> Action -> Observe -> Evaluate
                         ├─ Approve
                         ├─ Local Retry
                         ├─ Local Patch
                         ├─ Replan
                         └─ Escalate
```

`policies/graph-loop-budget.yaml`のAttempt、Failure repetition、Tool、Token、外部副作用上限を適用します。

## State and checkpoint

会話履歴をStateとして渡しません。

- Graph definition
- `STATE/current.yaml`
- append-only event / checkpoint
- `Evidence/raw/`
- `STATE/memory/`
- Source / patch artifact

`STATE/current.yaml`は`schemas/execution-state.schema.yaml`に従い、Control Planeが必要とする`goal_id / health / human_gate / quota / worker / todos / previous_slice / orchestration / memory_projection`を保持できます。

Orchestratorが返す`required_state_writeback`をCallerが正本Stateへ適用した後に、次の`prepare`へ進みます。

## Independent verification

Makerとは別ContextのVerifierが次を返します。

```text
APPROVE | REJECT | ESCALATE_HUMAN
```

VerifierへMakerの思考履歴全体を渡しません。Goal、Diff、対象Source、Acceptance Criteria、実行結果、Evidence、未検証事項だけを渡します。

## Failure routing

- Compile failure: 対象Nodeの実装または依存調査
- Runtime failure: Incident investigation
- Visual failure: Rendering / Shader / Visual evidence
- Performance failure: Baselineと主要仮説を再設定
- Scope violation: Patch除去またはRevert
- Contract conflict: Human decisionまで停止
- Code intelligence unavailable: targeted Source readへFallback
- Memory projection unavailable: Memoryなしで継続可能、Raw Evidenceは維持
- Memory scope leak / raw-content contract breach: Block
- Memory ID conflict: 新ID + supersedes/conflicts_with
- Continuation writeback missing: 次のsliceを開始しない
- Claim未永続化: ClaimをStateへWritebackしてprepareを再実行
- Source verification missing: Direct Source Read後にprepareを再実行
- Ticket integrity failure: BlockしTicketを再発行
- Evidence capture failure: Quota Spend禁止
- Quota accounting failure: Evidenceを保持してAccounting解決まで停止
- Continuation quota exhausted: Goalを消さず次Windowまで自動継続停止

失敗理由に関係なく同じ実装Nodeへ無条件で戻しません。

## Knowledge Graph

Knowledge Graphは候補Artifactの絞り込みに使用します。実装変更前に対象Sourceを直接読み、推論Edgeだけで原因や互換性を確定しません。

## Completion output

- Execution Mode: Graph / Loop
- Goal達成状態
- Graph versionとNode結果
- AttemptとBudget
- Orchestrator prepare/finalize結果
- Execution Ticket / State fingerprint
- Continuation decision / Quota state
- 使用したOptional ProviderとFallback
- Memory Projection / Raw Evidence refs
- Verifier verdictとEvidence
- 未検証事項
- Recovery / Revert条件
- Human Gate
- State write-back

## Common mistakes

- 無指定TaskをGraphへ入れる
- Ix / Memory / Continuationを通常フローで勝手な順序に直接呼ぶ
- Human GateやQuota停止中にProject Scannerを起動する
- ClaimをProjectionだけで済ませて複数Worker作業へ進む
- Ix結果だけでMutation対象を確定する
- Direct Source Read前にMutation Ticketを発行する
- Writeback前にQuotaをSpendする
- Evidence保存前にQuotaをSpendする
- 同一Sliceを再FinalizeしてQuotaを二重消費する
- 圧縮Memoryだけ残してRaw Evidenceを捨てる
- Team Safeへproject_internal Memoryを流す
- Scope無しLegacy Memoryをpublic扱いする
- MemoryからUser Policyを自動生成する
