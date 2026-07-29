---
name: unity-graph-engineering
description: Use only after explicit user selection or approved escalation when Unity work requires multiple subsystems, independent branches, bounded iteration, runtime or visual evidence, migration, rollback, or separate verification. Owns the typed task graph and node loops. Do not use for bounded work suitable for unity-prompt-execution.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
metadata:
  version: "2.0.0"
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

全Skill、全Reference、全Toolを一括で公開しません。

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
- Evidence artifact
- Source / patch artifact

Mode変更時は確認済み事実、棄却仮説、対象Artifact、残Budgetだけを型付きStateとして引き継ぎます。

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

失敗理由に関係なく同じ実装Nodeへ戻しません。

## Knowledge Graph

Knowledge Graphは候補Artifactの絞り込みに使用します。実装変更前に対象Sourceを直接読み、推論Edgeだけで原因や互換性を確定しません。

## Completion output

- Execution Mode: Graph / Loop
- Goal達成状態
- Graph versionとNode結果
- AttemptとBudget
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
