# Unity AI Execution Engineering

Unity制作AIの**実行方式・予算・状態・検証・回復**を管理するRepositoryです。

すべてのTaskをGraph化しません。普段はPrompt Engineering、複雑案件だけGraph / Loop Engineeringを使用します。

```text
User Request
    ↓
Execution Router
    ├─ Prompt Engineering【既定】
    │    ├─ Minimal Context
    │    ├─ One Mutation Scope
    │    └─ Deterministic Verification
    │
    └─ Graph / Loop【明示指定または承認後】
         ├─ Goal Contract
         ├─ Typed Task Graph
         ├─ Bounded Node Loops
         ├─ Independent Verifier
         ├─ Human Gate
         └─ State / Evidence Write-back
```

Unity固有のC#、URP、RenderGraph、Shader、Variant、Performance、Visual Directionは`DarumaPPAP/UnityAgent`へ委譲します。

## Execution modes

### Prompt Engineering

モード指定がない場合の既定です。

対象:

- 説明、レビュー
- 単一ファイルまたは局所修正
- 原因確定済みエラー
- 明確な小規模実装

Task Graph、複数Worker、永続Checkpointを作らず、必要なContext Packと対象Sourceだけを読みます。

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

## Core files

```text
AGENTS.md
policies/
├─ execution-mode.yaml
├─ prompt-budget.yaml
├─ graph-loop-budget.yaml
└─ mode-escalation.yaml

skills/
├─ unity-execution-router/
├─ unity-prompt-execution/
└─ unity-graph-engineering/

schemas/
├─ execution-state.schema.yaml
└─ evidence.schema.yaml

workflow-templates/
└─ verified-mutation.yaml
```

## Context ownership

Execution側はUnityAgent全体を一括読込しません。

```text
Request
  ↓
UnityAgent Context Index
  ↓
Domain Context Pack
  ↓
Knowledge Graph Query【必要時】
  ↓
対象Sourceを直接精読
```

Knowledge Graphは読む候補を絞る索引です。推論Edgeだけで原因や互換性を確定しません。

## Budget

PromptとGraph / Loopで別の上限を持ちます。

- file reads
- context expansion hops
- hypotheses
- mutation attempts
- parallel nodes
- tool calls
- input / output / cached tokens
- external side effects

新しいNodeまたはAttempt開始前に残Budgetを確認します。

## State and evidence

Transcriptを実行Stateとして引き継ぎません。

```text
STATE/current.yaml
STATE/events.jsonl
STATE/checkpoints/
Evidence/
```

Stateは現在位置、Evidenceは判断根拠です。AIの自己申告だけではAPPROVEしません。

## Human gates

PR Merge、main直接Push、File削除、Package、ProjectSettings、Render Pipeline、Scene大規模変更、品質と性能のTrade-off、実機品質の最終承認はHuman Gateです。

## Pilot KPI

初期目標:

- Framework Token: 50%以上削減
- Accepted Taskあたり総Token: 30%以上削減
- Context File Read: 30%以上削減
- Verifier品質低下: 0
- Silent Mode Switch: 0
- Unbounded Retry: 0

公開事例の最大値をそのまま目標にせず、Unity TaskのA/B比較で採用判断します。
