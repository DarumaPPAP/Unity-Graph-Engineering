---
name: unity-prompt-execution
description: Use for bounded Unity explanation, review, generation, or local fixes that can be completed by one owner with minimal context and deterministic verification. Applies Prompt Engineering budgets and stops for an approved Graph / Loop mode change when scope or uncertainty exceeds those limits.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
metadata:
  version: "1.0.0"
---

# Unity Prompt Execution

小規模・局所的なUnity作業を、Task Graphを展開せず最小Contextで完遂する実行Skillです。

## Inputs

- User request
- 対象RepositoryのProject Context
- UnityAgent Context Index
- 選択されたContext Pack
- 対象Sourceと直接依存

## Flow

1. Minimal Contractを確定する。
2. UnityAgentからPrimary Domain Skillを一つ選ぶ。
3. Context Packと対象Sourceだけを読む。
4. 一つのMutation scopeを一人のWriterが処理する。
5. Validator、Compile、Testなど決定的な検証を行う。
6. 結果と未検証事項を報告する。

## Minimal Contract

```yaml
goal: ""
scope:
  allowed: []
  forbidden: []
primary_skill: ""
context_pack: ""
validation: []
revert_condition: ""
```

局所TaskへSpec、Plan、Tasksの一式を強制しません。

## Budget

`policies/prompt-budget.yaml`を適用します。

- 初期Readを限定する
- Context拡張は1 Hopまで
- Primary Artifactは最大3
- 主要仮説は最大2
- Mutation Attemptは最大2
- 並列Workerは使用しない

## Escalation gate

Budget超過、2番目のSubsystem Mutation、決定的Evidence不足、Runtime / Visual / Performance反復が必要になった場合はMutationを停止します。

`policies/mode-escalation.yaml`に従い、Graph / Loopへの変更確認を出します。ユーザーがPrompt継続を選んだ場合は、一つの仮説、一つのScope、実行可能な検証だけに限定します。

## Verification

Prompt Modeでも自己申告だけで完了にしません。

優先順位:

1. Static validator
2. Compile
3. EditMode / PlayMode Test
4. 再現可能なRuntime check
5. 未実施項目の明記

## Output contract

- Execution Mode: Prompt
- Minimal Contract
- 読んだContext Pack
- 変更Artifact
- 実施した検証
- Budget使用状況
- 未検証事項
- Graph / Loop推奨の有無
- Revert条件

## Scope

このSkillはTask Graph、複数Worker、永続Checkpoint、長期Knowledge Write-backを作りません。必要になった場合はMode変更を提案します。
