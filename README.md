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

モード指定がない場合の既定です。

対象:

- 説明、レビュー
- 単一ファイルまたは局所修正
- 原因確定済みエラー
- 明確な小規模実装
- Project非参照のPortable設計

Task Graph、複数Worker、永続Checkpointを作らず、一つのTask Contract、必要なContext Pack、対象Sourceだけを読みます。

### Graph / Loop Engineering

次の場合だけ使用します。

- 複数Subsystem
- 原因不明、複数仮説
- Runtime / Visual / Performance反復
- Platform固有差
- Migration / Rollback
- 独立BranchとJoin
- Separate Verifier

無指定のPrompt Taskから無断で切り替えません。変更理由、利点、追加コスト、Prompt限定継続案を提示し、ユーザー承認を得ます。

## Execution profiles

Execution Modeとは別に、Projectとの接続形態を管理します。

| Profile | 用途 | Project Context |
|---|---|---|
| `generic_planning` | Project非参照の設計、Portable成果物 | 不要 |
| `personal_full_control` | 個人Projectの直接実装、Unity検証、Git | Optional |
| `team_safe_import` | 会社Projectへの一方向Staging Import | 禁止 |

### Generic Planning

Unity Version、Render Pipeline、Platform、Goal、Constraints、禁止事項、期待結果の最小手動入力だけで計画します。Project固有Path、Scene、Renderer Data、Layer、ShaderTagは未解決Bindingとして残し、推測しません。

### Personal Full-Control

Project Context GeneratorとUnity Command SurfaceはOptionalな加速装置です。利用不能でもTaskを中止せず、手動要件とSourceから継続します。

### Team Safe Import

Personal Toolとは別製品とし、Project Scanner、Source Export、Screenshot、Hierarchy、Unity Project ID、Git、Issue、Cloud、Environment Variable、組織情報、顧客情報へのアクセス機能を持ちません。禁止情報はReport Schemaにも追加しません。

## External intelligence / control plane

Graph / Loop向けに3つの公開Projectから設計を取り込みました。**外部Runtimeは必須依存にしません。**

| Reference | 統合役割 | 既定 |
|---|---|---|
| `ix-infrastructure/Ix` | Optional Code Intelligence / Impact / Trace | `personal_full_control`のみ |
| `huangruiteng/loopx` | Continuation / Todo / Claim / Lease / Quota思想 | Native Contract |
| `TencentCloud/TencentDB-Agent-Memory` | Layered Memory / Raw Evidence Offload / Symbolic Projection | Native Contract |

```text
Ix structural map ───────┐
                         ▼
Goal → Graph → Continuation Decision → Bounded Node Slice
                         │                    │
                         │                    ▼
                         │             Raw Evidence (L0)
                         │                    ↓
                         └──────────── Atom → Scenario → Reusable Candidate
```

- Ixは読むSourceを絞るNavigation Layerであり、Mutation前のSource確認やRuntime Evidenceを置き換えません。
- LoopX由来のQuotaはPermissionやBudgetと分離し、Human Gateを迂回できません。
- TencentDB-Agent-Memory由来の圧縮Memoryは必ずRaw Evidenceへdrill down可能にします。
- MemoryからUnityAgent User Policyへ自動昇格しません。
- 外部Package/Runtimeは自動Installせず、導入はHuman Gateです。

詳細: `docs/external-intelligence-control-plane.md`

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
└─ memory-layering.yaml

skills/
├─ unity-execution-router/
├─ unity-prompt-execution/
└─ unity-graph-engineering/

schemas/
├─ execution-state.schema.yaml
├─ evidence.schema.yaml
├─ capability-manifest.schema.yaml
├─ continuation-state.schema.yaml
└─ memory-layer.schema.yaml

workflow-templates/
└─ verified-mutation.yaml

tests/
└─ contract-routing-cases.yaml
```

## Contract routing

```text
Request
  ↓
Execution Profile
  ↓
One Primary Task Contract
  ↓
One Primary Domain Route
  ↓
Zero or One Primary Knowledge
  ↓
Conditional Related Knowledge
```

UnityAgent全体を一括読込しません。Related Knowledgeは依存条件が成立した場合だけ追加します。人間向けHTML Knowledge Productは、設計理由、実験、比較、Visual Reference、Decision履歴が必要な場合だけ参照します。

正本:

- `policies/contract-routing.yaml`
- `DarumaPPAP/UnityAgent/.ai/context-index.yaml`

## Project Context and capabilities

Project ContextやCapability Manifestは計画の必須条件ではありません。

```text
Minimal Manual Requirements
→ Planning

Project Source
→ Direct Implementation

Unity Tool
→ Automated Validation
```

Capability Manifestは存在する場合だけ利用し、`available`、`unavailable`、`unknown`、`prohibited`を区別します。Ix等のExternal Providerも同じManifestでOptional Capabilityとして表現できます。

## Budget, gate, and quota

PromptとGraph / Loopで別のBudget上限を持ちます。

- file reads
- context expansion hops
- hypotheses
- mutation attempts
- parallel nodes
- tool calls
- input / output / cached tokens
- external side effects

新しいNodeまたはAttempt開始前に残Budgetを確認します。

Graph / LoopではさらにContinuation Quotaを分離します。

```text
Gate  = 実行してよいか
Budget = 最大どこまで消費してよいか
Quota = eligibleなGoal/Nodeへ次の実行枠を与えるか
```

Quotaが残っていてもHuman GateやEvidence Waitを越えません。

## State, evidence, and memory

Transcriptを実行Stateとして引き継ぎません。

```text
STATE/current.yaml
STATE/events.jsonl
STATE/checkpoints/
Evidence/
```

Execution StateにはExecution Profile、Task Contract ID、Primary Knowledge、未解決Project Binding、Quality Gateに加え、必要な場合のみContinuationとMemory Projectionを保存します。

Quality Gateの状態:

- `passed`
- `failed`
- `unavailable`

`unavailable`は計画を止めませんが、成功とは扱いません。理由、Claim Scope縮小、残検証を必ず記録します。

Layered Memoryは `L0 Raw Evidence → L1 Atom → L2 Scenario → L3 Reusable Candidate`。上位層だけを残してEvidenceを破棄しません。

正本:

- `schemas/execution-state.schema.yaml`
- `schemas/continuation-state.schema.yaml`
- `schemas/memory-layer.schema.yaml`
- `policies/evidence-admission.yaml`

## Team Safe Import evidence

外部へ出せるReportはPackage ID、Version、結果Code、手動手順数などに限定します。

含めないもの:

- Project名とPath
- Scene名
- Source Path
- Screenshot
- Organization
- Customer
- Issue ID
- Unity Project ID

External ProviderのprobeやProject scanningも行いません。

## Human gates

PR Merge、main直接Push、File削除、Package、ProjectSettings、Render Pipeline、Scene大規模変更、品質と性能のTrade-off、実機品質の最終承認、Execution Profile変更はHuman Gateです。

## Validation

```bash
python Tools/ExecutionPolicyValidator/validate_execution_policies.py
```

Provider / Continuation / Memory regression contract:

```text
Tests/ExternalProviders/cases.yaml
```

## Pilot KPI

初期目標:

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

公開事例の最大値をそのまま目標にせず、同一Unity Task、同一Source Revision、同一Acceptance CriteriaのA/B比較で採用判断します。
