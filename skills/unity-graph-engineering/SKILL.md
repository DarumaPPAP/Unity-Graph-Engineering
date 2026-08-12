---
name: unity-graph-engineering
description: Use only after explicit user selection or approved escalation when Unity work requires multiple subsystems, independent branches, bounded iteration, runtime or visual evidence, migration, rollback, or separate verification. Owns the typed task graph, continuation control, optional code intelligence, layered execution memory, and bounded node loops. Do not use for bounded work suitable for unity-prompt-execution.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
metadata:
  version: "2.3.0"
---

# Unity Graph / Loop Engineering

複雑なUnity作業を、型付きTask Graphと上限付きNode Loopで制御する実行Skillです。

このSkillは無指定依頼の既定入口ではありません。`unity-execution-router`で明示指定またはユーザー承認された場合だけ使用します。

## Required inputs

1. Mode decision
2. Goal Contract
3. Project Context
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

```text
Goal Contract
    ↓
Context / Baseline
    ↓
Plan Version
    ↓
Independent Nodes
    ↓
Join / Evidence Review
    ↓
Human Gate
```

## Optional code intelligence

`personal_full_control`でIxが利用可能な場合、構造探索・Trace・Impact Analysisへ使用できます。

- IxはNavigation LayerでありSource of Truthではありません。
- Provider unavailableでもTaskを止めません。
- Mutation前には対象Sourceを直接読みます。
- Source変更後は可能ならMapをrefreshします。
- Graph結果だけでRuntime / Visual / Performance GateをPASSにしません。

詳細: `references/code-intelligence-provider.md`、`policies/external-providers.yaml`

## Continuation control

Graph / Loopの継続は、LoopXから取り入れたObjective / Typed Todo / Claim / Lease / Quota / Evidence Writeback思想をNative Controllerとして実行します。

```text
Health Gate → Human Gate → Evidence Wait → Focus Wait → Budget → Quota
                                                               ↓
                                                       Todo / Capability
                                                               ↓
                                                       One bounded slice
                                                               ↓
                                               Evidence + Durable Writeback
                                                               ↓
                                                          Quota Spend
```

実装は`Tools/ContinuationController/continuation_controller.py`です。

- `evaluate`: `should_run`と次Laneを決定
- `claim`: 選択TodoのClaim/Lease Projectionを生成
- `spend`: 検証済みWriteback後だけQuota Spend Projectionを生成
- Controllerは`STATE/current.yaml`を直接編集しない
- Activeな他Worker Leaseは飛ばし、Expired Leaseは再取得可能
- `advancement_task`だけが通常Deliveryを開始できる
- `continuous_monitor`だけならMaterial Transitionがない限りquiet skip
- Todo Projectionがtruncatedなら隠れたOpen Todoを保守的にAdvancement扱いする
- Todo単位の`required_capabilities`を実行前に確認する

**QuotaはPermissionでもBudgetでもありません。** Human GateやSafety Gateを上書きできません。WritebackとEvidenceなしではQuotaをSpendせず、次のsliceへ進みません。

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
- L1/L2/L3は`STATE/memory/`へ保存し、下位Layerへの参照を必須にする
- 通常の`retrieve` / `project`ではRaw contentをContextへ載せない
- 既定8件/6000文字、最大20件/12000文字でContext投入量を制限する
- 詳細が必要な時だけ`drilldown`し、Raw content展開は明示指定時だけ行う
- `team_safe_import`では禁止Scopeをsource read前にBlockする
- Secret分類や高確度Credential patternはRaw Evidenceへ保存しない
- 新旧Memoryの競合は`supersedes` / `conflicts_with`で残し、silent overwriteしない
- `promote`はProjectionだけを返し、UnityAgent KnowledgeやUser Policyを直接変更しない
- User Policy candidateはverified + Human Gateが必須

Symbolic ProjectionはContext圧縮用でありState authorityではありません。Runtime / Visual / Performance Factが必要なら元Evidenceへdrill downします。

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

Mode変更時は確認済み事実、棄却仮説、対象Artifact、残Budgetだけを型付きStateとして引き継ぎます。

ContinuationとMemory Projectionも`schemas/execution-state.schema.yaml`のOptional fieldとして保持できます。外部Runtime stateを正本にしません。

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
- Memory projection broken: Raw Evidenceから再構築
- Memory ID conflict: 既存Recordを上書きせず新ID + supersedes/conflicts_withへ送る
- Memory promotion blocked: Review / Verification / Human Gateを解決するまで外部Authorityへ送らない
- Continuation writeback missing: 次のsliceを開始しない
- Continuation capability missing: Local repairまたはOwner-held capabilityならHuman Gateへ送る
- Continuation quota exhausted: Goalを消さず次Windowまで自動継続を停止する

失敗理由に関係なく同じ実装Nodeへ戻しません。

## Knowledge Graph

Knowledge Graphは候補Artifactの絞り込みに使用します。実装変更前に対象Sourceを直接読み、推論Edgeだけで原因や互換性を確定しません。

## Completion output

- Execution Mode: Graph / Loop
- Goal達成状態
- Graph versionとNode結果
- AttemptとBudget
- Continuation decision / Quota state
- 使用したOptional ProviderとFallback
- Memory Projection / Raw Evidence refs
- 変更Artifact
- Verifier verdictとEvidence
- 未検証事項
- Recovery / Revert条件
- Human Gate
- State write-back

## Common mistakes

- 無指定TaskをGraphへ入れる
- 一つのNodeへ調査、実装、性能、Visual修正を混ぜる
- Agent数を成果指標にする
- 全Nodeへ巨大な同一Contextを渡す
- 同じFailure Signatureを仮説変更なしで反復する
- AIの自己申告でAPPROVEする
- Ixを必須Project Scannerにする
- QuotaでHuman Gateを迂回する
- Writeback前にQuotaをSpendする
- Monitor-only Pollへ毎回Computeを使う
- 圧縮Memoryだけ残してRaw Evidenceを捨てる
- Retrieval時にRaw Tool Logを毎回Contextへ戻す
- Memory conflictを既存Record上書きで解消する
- MemoryからUser Policyを自動生成する
