---
name: unity-prompt-execution
description: Use for bounded Unity explanation, review, generation, or local fixes that can be completed by one owner with minimal context and deterministic verification. Applies Prompt Engineering budgets and stops for an approved Graph / Loop mode change when scope or uncertainty exceeds those limits.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
metadata:
  version: "1.1.0"
---

# Unity Prompt Execution

小規模・局所的なUnity作業を、Task Graphを展開せず最小Contextで完遂する実行Skillです。

## Inputs

- User request
- 対象Repositoryの既存Project Context
- UnityAgent Context Index
- 選択されたContext Pack
- 対象Sourceと直接依存

Project Context Generator、Package導入、Project初期化、Setup Scriptは既定Inputではありません。

## Code-first contract

Prompt Engineeringは、既存Projectと既存Repositoryへコードを実装するためのModeです。

- 依頼されたSource変更をPrimary Artifactとする。
- 環境構築、Project生成、Package導入、ProjectSettings変更、雛形生成、補助Setup Toolを自動でTaskへ追加しない。
- ユーザーが明示していない導入手順やセットアップ手順を成果物へ混ぜない。
- 既存コード、既存asmdef、既存Package、既存設定を優先して再利用する。
- Project情報が一部不足していても、推測不要なコード実装を先に完了する。
- 本当に欠けている依存は未解決Bindingまたは未検証Gateとして報告し、環境構築を勝手に開始しない。
- ユーザーが環境構築も明示的に依頼した場合だけ、コード実装とは別Mutation scopeとして扱う。

## Flow

1. Minimal Contractを確定する。
2. UnityAgentからPrimary Domain Skillを一つ選ぶ。
3. Context Pack、対象Source、直接依存だけを読む。
4. 既存環境を前提に、依頼されたコード変更を一つのMutation scopeとして実装する。
5. Validator、Compile、Testなど決定的な検証を行う。
6. 不足環境がある場合はコード実装を巻き戻さず、未解決Bindingまたは未検証事項として報告する。
7. 結果と未検証事項を報告する。

## Minimal Contract

```yaml
goal: ""
scope:
  allowed: []
  forbidden:
    - unrequested_environment_setup
    - unrequested_package_installation
    - unrequested_project_settings_change
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

環境構築が必要そうに見えること自体はGraph / LoopへのEscalation理由にしません。既存Sourceで実装可能な範囲を先に完了します。

## Verification

Prompt Modeでも自己申告だけで完了にしません。

優先順位:

1. Static validator
2. Compile
3. EditMode / PlayMode Test
4. 再現可能なRuntime check
5. 未実施項目の明記

検証Toolが利用不能でも、そのToolを導入するための環境構築を自動で始めません。利用可能な検証だけを実行し、残りを`unavailable`として報告します。

## Output contract

- Execution Mode: Prompt
- Minimal Contract
- 読んだContext Pack
- 変更Artifact
- 実施した検証
- Budget使用状況
- 未解決Binding
- 未検証事項
- Graph / Loop推奨の有無
- Revert条件

## Scope

このSkillはTask Graph、複数Worker、永続Checkpoint、長期Knowledge Write-backを作りません。必要になった場合はMode変更を提案します。

このSkillは、明示依頼のない環境構築、Project初期化、Package導入、ProjectSettings変更、Setup Tool生成も行いません。
