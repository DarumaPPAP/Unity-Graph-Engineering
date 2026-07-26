# Unity Graph Engineering

UnityをAIで制作するときの**作業構造・反復・検証・状態管理**を設計するためのリポジトリです。

このプロジェクトの主役はUnity Editor拡張ではありません。ChatGPT、Codex、Claude Code、CursorなどのエージェントがUnityリポジトリへ変更を加える際に、単発Promptではなく次の制御系で仕事を進めます。

```text
User Goal
   ↓
Goal Contract
   ↓
Context Acquisition
   ↓
Task Graph
   ↓
Implementation Loop(s)
   ↓
Independent Verification
   ↓
Merge Owner
   ↓
Human Gate
   ↓
State / Knowledge Write-back
```

## 中心となる3つの考え方

### Graph Engineering

作業をNode、実行依存をEdgeとして定義します。後段が前段の成果を本当に読む場合だけEdgeを作り、独立作業だけを並列化します。

### Loop Engineering

各Nodeの内部を、入力・行動・観測・評価・停止条件を持つ反復として設計します。実装者は自分で完了判定を行わず、最大試行回数と予算を超えたら人間へEscalateします。

### Unity Skills

Unity固有の規約、公式API確認、実装手順、検証方法を再利用可能なSkillへ分離します。Orchestrator Skillは作業フローを所有し、個別の実装知識を重複して抱えません。

## これは何ではないか

- Unity内でノードグラフを表示するための製品ではない
- Agent数を増やすこと自体を目的にしない
- すべてを自動化・自動マージする仕組みではない
- AIの自己申告をVerification Evidenceとして扱わない
- Repositoryの既存規約より一般論を優先しない

## Repository構成

```text
AGENTS.md                         AIが必ず守る運用契約
LOOP.md                           このRepositoryで有効なLoop
STATE.md                          会話外に残る現在状態
loop-budget.md                    試行回数・並列数・停止条件
gate.yaml                         Human Gateと危険Path

skills/unity-graph-engineering/   Cross-agent Orchestrator Skill
workflows/                        Unity制作タスク別Task Graph
schemas/                          Goal・State・Evidenceの機械可読Schema
templates/                        対象Unity Repositoryへ配置する雛形
starters/codex/                   Codex用Maker/Checker構成
examples/FakeUnity7/              FakeUnity7を対象とした実行例
docs/                             設計・運用・Pilot手順

packages/                         旧Artifact Scanner。補助実験でありCoreではない
```

`packages/`のUnity Editor拡張は初期の誤解から生まれた補助実験です。Core Workflowからは参照せず、後続PRでArchiveまたは別Repositoryへ分離します。

## 使い方

### 1. 対象Unity RepositoryへProject Contextを置く

`templates/PROJECT_CONTEXT.md`と`templates/STATE.md`を対象Repositoryへコピーし、Unity Version、Render Pipeline、Platform、Build/Test手順、禁止事項を記入します。

### 2. SkillをAgentへ導入する

Skill互換Agentでは、`skills/unity-graph-engineering/`をSkill Directoryへ追加します。

Codexでは`starters/codex/README.md`を参照し、Verifier Agentも配置します。

### 3. 普通にUnity制作を依頼する

例:

```text
FakeUnity7にURP向けの高品質なライブステージLightingを実装して。
既存のProject Contextを読み、Unity Graph Engineeringで進めて。
```

Agentは以下を行います。

1. GoalをAcceptance Contractへ変換
2. Repositoryと公式SourceからContextを確定
3. Task Graphを作成し、Fake Edgeを削除
4. 各Nodeを上限付きLoopで実行
5. 別ContextのVerifierがCompile/Test/Visual/Performanceを判定
6. Merge前にHuman Gateを提示
7. STATEとKnowledgeへ結果を書き戻す

## Workflow Registry

| Workflow | 用途 |
|---|---|
| `unity-feature-implementation.yaml` | Runtime / Editor機能の追加 |
| `rendering-bug-investigation.yaml` | Editor/実機差、描画破綻、回帰調査 |
| `shader-development.yaml` | Shader/HLSL/RendererFeature開発 |
| `scene-generation.yaml` | AIによるScene・Lighting・Project設定生成 |
| `performance-optimization.yaml` | CPU/GPU/Memory最適化 |

## Readiness

現在は**L1 Report / L2 Assistedの境界**です。

- Task Graph、Loop、State、Gate、Evidence Contractを定義済み
- Small fixはVerifier付きで実施可能
- 自動マージは禁止
- 無人実行、定期実行、Knowledge Fusionは未導入

詳細は`docs/roadmap.md`を参照してください。

## 参考Repository

- `cobusgreyling/loop-engineering` — Loop、State、Budget、Maker/Checker、Readiness Level
- `codejunkie99/graph-engineering` — Task Graph、Fake Edge、Diamond Pattern、Stop Rule、Human Gate
- `Unity-Technologies/skills` — Skill構造、具体的なTrigger、Skill間Delegation、Reference分離

利用方針とLicenseについては`THIRD_PARTY_NOTICES.md`を参照してください。
