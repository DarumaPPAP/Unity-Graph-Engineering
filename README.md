# Unity AI Execution Engineering

Unity制作AIの**実行方式・接続Profile・Task Contract・予算・状態・検証・回復**を管理するRepositoryです。

すべてのTaskをGraph化しません。普段はPrompt Engineering、複雑案件だけGraph / Loop Engineeringを使用します。

```text
User Request
    ↓
Execution Mode
    ├─ Prompt【既定】
    └─ Graph / Loop【明示指定または承認後】
    ↓
Execution Profile
    ├─ Generic Planning
    ├─ Personal Full-Control
    └─ Team Safe Import
    ↓
UnityAgent Task Contract / Domain Route / Knowledge Contract
    ↓
Mutation and Quality Gates
```

Unity固有のC#、URP、RenderGraph、Shader、Variant、Performance、Visual Direction、Knowledge YAML、Task Contractは`DarumaPPAP/UnityAgent`へ委譲します。

## Execution modes

### Prompt Engineering

モード指定がない場合の既定です。説明、単一ファイル修正、原因確定済みエラー、明確な小規模実装、Portable設計をTask Graphなしで処理します。

### Graph / Loop Engineering

複数Subsystem、複数仮説、Runtime/Visual/Performance反復、Platform差、Migration/Rollback、独立Branch、Separate Verifierが必要な場合だけ使用します。無指定Taskから無断で切り替えません。

## Execution profiles

| Profile | 用途 | Project Context |
|---|---|---|
| `generic_planning` | Project非参照の設計、Portable成果物 | 不要 |
| `personal_full_control` | 個人Projectの直接実装、Unity検証、Git | Optional |
| `team_safe_import` | 会社Projectへの一方向Staging Import | 禁止 |

`team_safe_import`はProject Scanner、Source Export、Screenshot、Hierarchy、Unity Project ID、Git、Issue、Cloud、Environment Variable、組織情報、顧客情報へアクセスしません。禁止情報はReport Schemaにも追加しません。

## External intelligence / control plane

Graph / Loop向けにIx、LoopX、TencentDB-Agent-Memoryの有効な設計をNative Control Planeへ統合しています。**外部Runtimeは必須依存にしません。**

| Reference | Local implementation | 役割 |
|---|---|---|
| `ix-infrastructure/Ix` | `Tools/IxAdapter/ix_adapter.py` | Optional Code Intelligence |
| `huangruiteng/loopx` | `Tools/ContinuationController/continuation_controller.py` | Continuation / Claim / Lease / Quota |
| `TencentCloud/TencentDB-Agent-Memory` | `Tools/LayeredMemoryController/layered_memory_controller.py` | Evidence-first Layered Memory |
| Native integration | `Tools/ExecutionOrchestrator/execution_orchestrator.py` | 全Controllerの安全な順序制御 |

### Canonical Graph runtime flow

通常のGraph / Loop実行は各Controllerを個別に好きな順序で呼ばず、Execution Orchestratorの`prepare → bounded slice → finalize`を通します。

```text
Continuation Gate
  ├─ Health / Human / Evidence / Focus / Budget / Quota block → STOP
  ↓
Claim / Lease durable writeback
  ↓
Bounded Memory Projection
  ↓
Optional Ix Navigation [personal_full_control only]
  ↓
Direct Source Read
  ↓
Integrity-bound Execution Ticket
  ↓
ONE bounded slice
  ↓
L0 Raw Evidence
  ↓
Optional L1 Atom
  ↓
Quota Spend Projection
  ↓
STATE/current.yaml writeback
```

重要な境界:

- Continuationが止めた時はIx/Memoryを起動しません。
- 新規ClaimはStateへ永続化してからProject Navigationへ進みます。
- IxはNavigationでありDirect Source Readの代替ではありません。
- MutationのSource ReadにはEvidence Refを要求します。
- TicketはGoal/Todo/Worker/Profile/State fingerprint/Source verificationへ拘束します。
- Ticket発行後にStateが変わった場合、得られたEvidenceは保全しますがQuota/State Accountingは拒否します。
- Evidence保存前にQuotaをSpendしません。
- 同一Sliceを再FinalizeしてもQuotaを二重消費しません。
- OrchestratorはSource Mutation、`STATE/current.yaml`、Human Gate、Quota PolicyのAuthorityを持ちません。

詳細: `docs/external-intelligence-control-plane.md`

## Code intelligence

Ixは`personal_full_control`だけで利用できるOptional Navigation Layerです。`impact / trace / callers / callees`等で読む範囲を狭めますが、結果だけでRuntime FactやMutation対象を確定しません。Ix unavailable時は`targeted_source_read`へFallbackします。

## Continuation

Gate / Budget / Quotaを分離します。

```text
Gate   = 実行してよいか
Budget = 最大どこまで消費してよいか
Quota  = eligibleなGoal/Nodeへ次の実行枠を与えるか
```

Quotaが残っていてもHuman GateやEvidence Waitを越えません。複数WorkerではClaim/Leaseを用い、validated durable writeback + Evidence後だけQuota SpendをProjectionします。

## Layered Memory

```text
Evidence/raw/        L0 Raw Evidence
      ↓ raw_refs
STATE/memory/L1/     Atom
      ↓ atom_refs
STATE/memory/L2/     Scenario
      ↓ scenario_refs
STATE/memory/L3/     Reusable Candidate
```

- Raw EvidenceはSHA-256付きで保持し、要約で置換しません。
- 通常RetrievalにRaw contentを載せません。
- 既定8件/6000文字、最大20件/12000文字です。
- `project_internal`は`personal_full_control`だけが読めます。
- `generic_planning` / `team_safe_import`は`portable_artifact` / `public_reference`だけです。
- L1→L3は最も厳しい親Scopeを継承し、Scope downgradeを禁止します。
- Scope無しLegacy Memoryは`project_internal`としてFail Closedします。
- User Policyへ自動昇格しません。

## Core files

```text
AGENTS.md
policies/
├─ execution-mode.yaml
├─ prompt-budget.yaml
├─ graph-loop-budget.yaml
├─ mode-escalation.yaml
├─ contract-routing.yaml
├─ evidence-admission.yaml
├─ external-providers.yaml
├─ continuation-control.yaml
├─ memory-layering.yaml
└─ execution-orchestration.yaml

Tools/
├─ IxAdapter/
├─ ContinuationController/
├─ LayeredMemoryController/
├─ ExecutionOrchestrator/
└─ ExecutionPolicyValidator/

schemas/
├─ execution-state.schema.yaml
├─ evidence.schema.yaml
├─ capability-manifest.schema.yaml
├─ continuation-state.schema.yaml
├─ memory-layer.schema.yaml
└─ execution-orchestration.schema.yaml

skills/
├─ unity-execution-router/
├─ unity-prompt-execution/
└─ unity-graph-engineering/
```

## State, evidence, and accounting

Transcriptを実行Stateとして引き継ぎません。

```text
STATE/current.yaml
STATE/events.jsonl
STATE/checkpoints/
STATE/memory/
Evidence/raw/
```

`STATE/current.yaml`はExecution Mode/Profile/Task Contractに加え、Goal ID、Health/Human Gate、Budget/Quota、Worker/Todo/Lease、Previous Slice、Orchestration accounting、Memory Projectionを保持できます。

OrchestratorはStateを直接編集せず、`required_state_writeback`を返します。Callerが正本へ適用した後に次の`prepare`へ進みます。

## Team Safe Import evidence

外部へ出せるReportはPackage ID、Version、結果Code、手動手順数などに限定します。Project名/Path、Scene、Source Path、Screenshot、Organization、Customer、Issue ID、Unity Project IDを含めません。Ix probeやProject scanningも行いません。

## Human gates

PR Merge、main直接Push、File削除、Package、ProjectSettings、Render Pipeline、Scene大規模変更、品質と性能のTrade-off、実機品質の最終承認、Execution Profile変更はHuman Gateです。

## Validation

```bash
python -m compileall -q Tools Tests
python Tools/ExecutionPolicyValidator/validate_execution_policies.py
python -m unittest discover -s Tests/ExternalProviders -p "test_*.py" -v
```

CIではさらに全YAML構文とDraft 2020-12 JSON Schema自体の妥当性を検証します。

## Pilot KPI

- Framework Token: 50%以上削減
- Accepted Taskあたり総Token: 30%以上削減
- Context File Read: 30%以上削減
- Verifier品質低下: 0
- Silent Mode Switch: 0
- Unbounded Retry: 0
- Unavailable Gateの成功誤報: 0
- External Provider必須化: 0
- Raw Evidence喪失: 0
- User Policy自動昇格: 0
- Human/Quota Block中のProvider Probe: 0
- Duplicate Quota Spend: 0
- Non-personal `project_internal` Memory leak: 0

公開事例の最大値をそのまま目標にせず、同一Unity Task、同一Source Revision、同一Acceptance CriteriaのA/B比較で採用判断します。
