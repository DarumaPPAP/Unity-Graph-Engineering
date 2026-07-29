---
name: unity-execution-router
description: Use when selecting how a Unity AI task should execute. Defaults unspecified requests to Prompt Engineering, evaluates whether Graph / Loop Engineering is justified, and requests user confirmation before any heavier mode switch. Does not implement Unity domain work.
allowed-tools:
  - Read
metadata:
  version: "1.0.0"
---

# Unity Execution Router

Unity制作依頼を`prompt`または`graph_loop`へ割り当てる入口Skillです。

## Required policy

1. `policies/execution-mode.yaml`
2. `policies/mode-escalation.yaml`
3. 対象Repositoryの`PROJECT_CONTEXT`または同等情報

## Routing

### Explicit selection

ユーザーがPrompt、Graph、Loop、Graph / Loopを指定した場合は、その指定を優先します。`auto`は明示指定時だけ使用します。

### Unspecified selection

無指定時は必ず`prompt`です。

```text
Request -> Prompt suitability check -> Prompt execution
```

Graph / Loopへ自動変更しません。

## Suitability check

Hard TriggerまたはSuitability Scoreを評価します。ただし、提案前にRepositoryから解決できる事実を取得し、単なるファイル数だけでGraphを推奨しません。

Graph / Loop候補:

- 複数SubsystemのMutation
- 原因不明かつ複数仮説
- Runtime、Visual、Performanceの反復
- Platform固有再現
- Migration、Rollback
- 独立BranchとJoin
- Maker / Verifier分離

## Mode-change proposal

Promptで不適切と判断した場合は作業を停止し、次を提示します。

- 現在Mode
- 推奨Mode
- 根拠
- 期待できる利点
- 追加Token・工程
- Prompt継続時の限定Scope
- 引き継ぐ型付きState

選択肢:

1. Graph / Loopへ変更
2. Promptのまま限定継続
3. Read-only調査後に再判断

同一Goalで一度決定したModeをLockし、契約変更がない限り再確認しません。

## Output contract

```yaml
execution_mode: prompt | graph_loop
selection_source: explicit | default | approved_escalation
reason: []
mode_locked_for_goal: true
applicable_budget: ""
context_owner: ""
```

## Common mistakes

- 無指定依頼を`auto`にする
- 複雑そうという印象だけでGraphへ切り替える
- Token増加を説明せずGraphを提案する
- Promptで既に得たTranscript全文をGraphへ渡す
- 同一Goalで何度もMode確認する
