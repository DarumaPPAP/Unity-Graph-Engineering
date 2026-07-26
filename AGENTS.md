# AGENTS.md

このRepositoryのSkillまたはWorkflowを使ってUnity制作を行うAgentは、次の契約を必ず守る。

## 1. 開始条件

実装前に対象Repositoryから次を読む。

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `STATE.md`
4. 対象コード・Scene・ProjectSettings
5. 使用するWorkflow

存在しない文書は勝手に補完せず、Repositoryから確定できる事実だけで初期Contextを作る。

## 2. Goal Contract

ユーザーの依頼を次へ変換する。

- Goal
- Deliverables
- Acceptance criteria
- Must
- Must not
- Unity version
- Render Pipeline
- Target platform
- Verification evidence
- Human gate

曖昧でも安全に進められる項目は仮定として明記する。結果を左右する不明点だけ確認する。

## 3. Task Graph

- Nodeは1つの担当へ渡せるJobにする
- Edgeは後段が前段の成果を読む場合だけ作る
- 独立していない作業を並列化しない
- 1 ArtifactにつきWriterは1人
- Merge Ownerを1人に固定する
- Agent数を成果指標にしない

## 4. Loop

各実装Nodeは次を持つ。

```text
Input → Action → Observe → Evaluate → Continue | Approve | Reject | Escalate
```

- 最大3回まで
- 同じ失敗を2回繰り返したら停止
- Testを無効化して通過させない
- Scopeを広げて問題を隠さない
- 実装者は自分の作業を完了判定しない

## 5. Unity実装規約

- Runtimeから`UnityEditor` APIを参照しない
- Editor機能はEditor FolderまたはEditor-only Assemblyへ隔離
- asmdefは境界が必要な場合だけ追加
- private Fieldは`_camelCase`
- Enumは`E_`、Structは`S_`
- Structは値型の利点が明確な場合だけ使う
- MonoBehaviourは1ファイル1型
- 不要なController、Setup関数、自動探索、static状態を追加しない
- ProjectSettings、URP Asset、Scene、Materialを暗黙変更しない
- Shader関数引数は可能な限り1行
- 本番Commentは意図・制約・危険箇所に限定する

## 6. Independent Verification

Verifierは実装者と別Contextで実行する。

Verifierの出力は次のいずれか。

```text
APPROVE
REJECT
ESCALATE_HUMAN
```

判定には実行したCommand、Test結果、Console、Screenshot、Profiler値などのEvidenceを添える。自己申告だけではAPPROVEしない。

## 7. Human Gate

次はユーザー承認なしに実行しない。

- PR merge
- mainへの直接Push
- Asset削除
- Sceneの大規模置換
- ProjectSettings変更
- Render Pipeline Asset差し替え
- Package追加・更新・削除
- Build配布

## 8. State Write-back

作業終了時に`STATE.md`へ次を残す。

- 完了したGoal
- 変更Artifact
- Verification Evidence
- 未検証事項
- 失敗した試行
- 次のAction
- Human override

Chat履歴だけを状態保存先にしない。

## 9. Completion Report

最終報告は次の順にする。

1. 何を達成したか
2. Task Graphの実行結果
3. 変更Artifact
4. Verification Evidence
5. 未検証事項
6. Human Gate
7. State / Knowledge Write-back
