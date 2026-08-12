# Unity AI Execution Bootstrap

このRepositoryはUnity制作AIの実行方式、予算、状態、検証、回復を管理する正本です。Unity固有の実装知識、Knowledge Contract、Task Contractは`DarumaPPAP/UnityAgent`へ委譲します。

## 1. Default execution mode

- モード指定がない依頼は`prompt`で開始する。
- `graph_loop`へ無断で切り替えない。
- Promptでは安全に完遂できないと判断した場合、理由、利点、追加コスト、限定継続案を提示してユーザー確認を得る。
- `auto`はユーザーが明示的に指定した場合だけ使用する。
- Prompt Engineeringは既存Project、既存Repository、既存Package、既存設定を前提に、依頼されたSource変更を直接実装する。
- ユーザーが明示していない環境構築、Project生成、Package導入、初期設定、雛形生成、Setup Tool作成を前提条件または既定Taskへ追加しない。
- 必要な依存が欠けていても、推測不要なSource実装を先に進め、不足項目を未解決Bindingまたは未検証Gateとして残す。

正本:

- `policies/execution-mode.yaml`
- `policies/mode-escalation.yaml`
- `skills/unity-execution-router/SKILL.md`

## 2. Execution profile

Execution Modeとは別にProject接続形態をProfileとして管理する。

### `generic_planning`

Projectへアクセスしない標準Profile。最小手動要件だけで計画とPortable成果物を生成する。

- Project Context / Capability Manifestは必須ではない。
- Path、Scene、Renderer Data、Layer、ShaderTagを推測しない。
- 未解決Bindingを記録して計画を継続する。
- `project_internal` MemoryやSourceへアクセスしない。

### `personal_full_control`

個人Projectで明示的に許可された場合だけProject Source、Unity Tool、Screenshot、Profiler、Gitを利用する。

- Project Context GeneratorはOptional。
- Generator/Unity Toolが利用不能でも手動要件とSourceから継続する。
- SecretはContextへ収集しない。

### `team_safe_import`

会社Project向け。一方向のPortable Package Importだけを行う。

- Project Context Generatorを使用しない。
- Personal Toolへ依存しない。
- Project Scanner、Source Export、Screenshot、Hierarchy、Unity Project ID、Git、Issue、Cloud、Environment Variable、組織情報、顧客情報へのアクセス機能を持たない。
- 禁止情報は`redacted`としてもSchemaへ追加しない。
- `project_internal` Memoryを読まない。

正本: `policies/contract-routing.yaml`

## 3. Prompt execution

局所修正、説明、原因確定済みのエラー、明確な小規模実装は`unity-prompt-execution`を使用する。

- 一つのPrimary Task Contract
- 一つのPrimary Domain Route
- Zero or One Primary Knowledge
- 一つのMutation scope
- 一つのWriter
- 必要最小Context
- 決定的なValidator、Compile、Testを優先
- 大規模Task Graph、永続Checkpoint、複数Workerを作らない
- 既存Sourceを直接編集し、コード実装とその最小検証へ集中する
- ユーザーが求めていない環境構築やPackage導入を混ぜない

Budgetは`policies/prompt-budget.yaml`を正本とする。

## 4. Graph / Loop execution

複数Subsystem、原因不明、性能・Visual反復、Platform差、Migration、Rollback、独立Branch、Human Gateが必要な場合だけ`unity-graph-engineering`を使用する。

- GraphはNode間の依存とFailure Domainを所有する。
- Loopは一つのNode内部へ閉じ込める。
- 一つのArtifactにWriterを一人だけ割り当てる。
- MakerとVerifierを分離する。
- Nodeごとに一つのTask Contractを割り当てる。
- Execution ProfileはGoal単位でLockし、変更には承認を要求する。
- Node、Attempt、Tool、Token、外部副作用へ上限を設定する。
- StateとEvidenceを会話履歴から分離する。

### Canonical runtime control plane

通常の`graph_loop`実行は`Tools/ExecutionOrchestrator/execution_orchestrator.py`を標準入口にする。Ix / Continuation / Layered Memoryを通常フローで任意順序に直接合成しない。

順序は固定する。

```text
Continuation Gate
→ Claim durable writeback
→ bounded Memory Projection
→ optional Ix Navigation (personal_full_control only)
→ Direct Source Read
→ integrity-bound Execution Ticket
→ ONE bounded slice
→ Raw Evidence
→ optional Atom
→ Quota Spend Projection
→ STATE/current.yaml writeback
```

- `should_run=false`の時はIx/Memoryを起動しない。
- 複数Workerの新規Claim/LeaseはStateへ永続化してからProject Navigationへ進む。
- Mutation TicketはDirect Source Read完了前に発行しない。
- Evidence保存前にQuotaをSpendしない。
- 同一SliceのFinalizeを再実行してもQuotaを二重消費しない。
- OrchestratorはSource Mutation、State、Human Gate、Quota PolicyのAuthorityを持たない。

正本:

- `policies/execution-orchestration.yaml`
- `schemas/execution-orchestration.schema.yaml`
- `skills/unity-graph-engineering/SKILL.md`

Budgetは`policies/graph-loop-budget.yaml`を正本とする。

## 5. Unity domain delegation

Unityの命名、C#、URP、RenderGraph、Shader、Variant、Runtime Evidence、Visual DirectionはUnityAgentのContext Indexから必要なTask Contract、Context Pack、Knowledge Contractだけを取得する。

- UnityAgent全体を一括で読まない。
- Primary Task Contractは一つ。
- Primary Knowledgeは最大一つ。
- Related Knowledgeは条件成立時だけ読む。
- Knowledge Graphは候補ファイル選定にだけ使う。
- 実装変更前に対象Sourceを直接読む。
- Graph Report全体をPromptへ投入しない。

## 6. Project Context and capabilities

Project ContextやCapability Manifestがなくても計画を止めない。

```text
最小手動要件 → 計画可能
Project Sourceあり → 直接実装可能
Unity Toolあり → 自動検証可能
```

Capabilityは`available`、`unavailable`、`unknown`、`prohibited`として扱う。Team Safe Importでは禁止Capabilityを検出対象としても公開しない。

Schema: `schemas/capability-manifest.schema.yaml`

### External intelligence providers

- IxはOptional Code Intelligenceであり`personal_full_control`でのみProject構造探索へ使用する。
- Ixが無くてもSource read / repository searchへFallbackする。
- Ix結果はNavigationであり、Direct Source ReadやRuntime Evidenceを置き換えない。
- LoopX Runtimeを必須依存にせず、Todo / Claim / Lease / Quota / WritebackをNative Continuation Contractとして利用する。
- QuotaはPermissionではない。Human Gate、Safety Gate、Budgetを上書きしない。
- TencentDB-Agent-MemoryのLayering思想を使い、Raw Evidence → Atom → Scenario → Reusable Candidateとして圧縮する。
- Symbolic MemoryはProjectionでありState Source of Truthではない。
- MemoryのScopeはL0→L3へ最も厳しい親Scopeを継承し、downgradeしない。
- `project_internal` Memoryは`personal_full_control`だけが読める。
- Scopeの無いLegacy Memoryは`project_internal`としてFail Closedする。
- MemoryからUnityAgent User Policyへ自動昇格しない。User Policy候補の採用にはHuman Gateを要求する。
- 外部Package/Runtimeの自動Installは禁止し、Package Human Gateとして別扱いにする。
- `generic_planning` / `team_safe_import`ではIxをprobeしない。

正本:

- `policies/external-providers.yaml`
- `policies/continuation-control.yaml`
- `policies/memory-layering.yaml`
- `policies/execution-orchestration.yaml`
- `docs/external-intelligence-control-plane.md`

## 7. State and evidence

Graph / Loopでは次を分離する。

- Graph definition
- `STATE/current.yaml`
- append-only event / checkpoint
- `Evidence/raw/`
- `STATE/memory/`
- Source / patch artifact

Execution Stateには次を記録できる。

- Execution Mode / Profile / Task Contract
- Goal / Goal ID / Current Node
- Health / Human Gate / Evidence Wait / Focus Wait
- Budget / Quota
- Worker / Todo / Claim / Lease
- Previous Slice / Quota accounting marker
- Continuation Decision
- Orchestration state
- Memory Projection / Raw Evidence refs
- Optional External Provider state

`schemas/execution-state.schema.yaml`はControl Planeの実Writebackを表現できなければならない。Orchestratorは`required_state_writeback`を返すだけで、`STATE/current.yaml`を直接編集しない。

Quality Gateは`passed`、`failed`、`unavailable`のいずれか。

- `unavailable`を成功として報告しない。
- 実行していない検証をPASSにしない。
- AIの自己申告だけをEvidenceにしない。
- 圧縮Memoryだけ残してRaw Evidenceを破棄しない。
- Evidenceが保存できなければQuota Spendしない。

正本:

- `schemas/execution-state.schema.yaml`
- `schemas/evidence.schema.yaml`
- `schemas/continuation-state.schema.yaml`
- `schemas/memory-layer.schema.yaml`
- `schemas/execution-orchestration.schema.yaml`
- `policies/evidence-admission.yaml`

## 8. Human gates

次はユーザー承認なしに実行しない。

- PR merge
- mainへの直接Push
- AssetまたはFile削除
- Package追加・更新・削除
- ProjectSettings変更
- Render Pipeline Asset差し替え
- Scene / Prefabの大規模置換
- 品質と性能のTrade-off確定
- 実機品質の最終承認
- Execution Profile変更

ユーザーが今回の依頼で明示的に承認した操作は、同一Goal内で再確認しない。

## 9. Completion

最終報告には次を含める。

- Execution Modeと選択理由
- Execution Profile
- Task Contract
- Goal達成状態
- 変更Artifact
- Orchestrator prepare/finalize結果
- Execution Ticket / State fingerprint
- Optional Provider利用/Fallback
- Continuation Decision / Quota
- Memory Projection / Raw Evidence refs
- Quality Gate / unavailable Gate
- Evidence / 未検証事項
- 消費Budget / 停止理由
- Revert条件
- Human Gate
- State write-back

成功だけでなく、そこへ到達した経路と消費量を記録する。
