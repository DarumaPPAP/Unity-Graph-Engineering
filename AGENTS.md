# Unity AI Execution Bootstrap

このRepositoryはUnity制作AIの実行方式、予算、状態、検証、回復を管理する正本です。Unity固有の実装知識は`DarumaPPAP/UnityAgent`へ委譲します。

## 1. Default execution mode

- モード指定がない依頼は`prompt`で開始する。
- `graph_loop`へ無断で切り替えない。
- Promptでは安全に完遂できないと判断した場合、理由、利点、追加コスト、限定継続案を提示してユーザー確認を得る。
- `auto`はユーザーが明示的に指定した場合だけ使用する。

正本:

- `policies/execution-mode.yaml`
- `policies/mode-escalation.yaml`
- `skills/unity-execution-router/SKILL.md`

## 2. Prompt execution

局所修正、説明、原因確定済みのエラー、明確な小規模実装は`unity-prompt-execution`を使用する。

- 一つのPrimary Skill
- 一つのMutation scope
- 一つのWriter
- 必要最小Context
- 決定的なValidator、Compile、Testを優先
- 大規模Task Graph、永続Checkpoint、複数Workerを作らない

Budgetは`policies/prompt-budget.yaml`を正本とする。

## 3. Graph / Loop execution

複数Subsystem、原因不明、性能・Visual反復、Platform差、Migration、Rollback、独立Branch、Human Gateが必要な場合だけ`unity-graph-engineering`を使用する。

- GraphはNode間の依存とFailure Domainを所有する。
- Loopは一つのNode内部へ閉じ込める。
- 一つのArtifactにWriterを一人だけ割り当てる。
- MakerとVerifierを分離する。
- Node、Attempt、Tool、Token、外部副作用へ上限を設定する。
- StateとEvidenceを会話履歴から分離する。

Budgetは`policies/graph-loop-budget.yaml`を正本とする。

## 4. Unity domain delegation

Unityの命名、C#、URP、RenderGraph、Shader、Variant、Runtime Evidence、Visual DirectionはUnityAgentのContext Indexから必要なContext Packだけを取得する。

- UnityAgent全体を一括で読まない。
- Knowledge Graphは候補ファイル選定にだけ使う。
- 実装変更前に対象Sourceを直接読む。
- Graph Report全体をPromptへ投入しない。

## 5. State and evidence

Graph / Loopでは次を分離する。

- Graph definition
- `STATE/current.yaml`
- append-only event / checkpoint
- Evidence artifact
- Source / patch artifact

Schema:

- `schemas/execution-state.schema.yaml`
- `schemas/evidence.schema.yaml`

実行していない検証をPASSにしない。AIの自己申告だけをEvidenceにしない。

## 6. Human gates

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

ユーザーが今回の依頼で明示的に承認した操作は、同一Goal内で再確認しない。

## 7. Completion

最終報告には次を含める。

- Execution Modeと選択理由
- Goal達成状態
- 変更Artifact
- 実施した検証
- Evidenceまたは未検証事項
- 消費Budgetと停止理由
- Revert条件
- Human Gate

成功だけでなく、そこへ到達した経路と消費量を記録する。
