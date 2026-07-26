---
name: unity-graph-engineering
description: Use when an AI coding agent must plan, implement, debug, optimize, or generate content in a Unity repository. Orchestrates Unity work as a goal contract, task graph, bounded implementation loops, independent verification, human gates, and durable state. Do not use it to build a graph UI unless the user explicitly requests one.
---

# Unity Graph Engineering

AIがUnity Repositoryへ変更を加えるときのOrchestrator Skill。

Graphは作業のTopology、Loopは各Node内部の反復、SkillはUnity固有知識、Stateは会話外の記憶として扱う。

## Start Here

対象Repositoryで次を順に読む。

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `STATE.md`
4. 関連するSource / Scene / ProjectSettings
5. このSkillのWorkflow Registry

存在しないFileは`templates/`を参考に提案するが、実装を止める必要がない場合は現在確定できるContextで進める。

## Select One Workflow

依頼に最も近いWorkflowを1つ選ぶ。

- Runtime / Editor機能追加 → `workflows/unity-feature-implementation.yaml`
- 描画不具合調査 → `workflows/rendering-bug-investigation.yaml`
- Shader / HLSL / RendererFeature → `workflows/shader-development.yaml`
- Scene / Lighting / Material生成 → `workflows/scene-generation.yaml`
- CPU / GPU / Memory最適化 → `workflows/performance-optimization.yaml`

複数Workflowを同時に始めない。主WorkflowのNodeとして必要な検証だけ取り込む。

## 1. Compile the Goal

実装前にGoal Contractを作る。

```yaml
goal: ""
deliverables: []
acceptance_criteria: []
must: []
must_not: []
unity:
  version: ""
  render_pipeline: ""
  target_platforms: []
verification_required: []
human_gate: []
assumptions: []
```

Repositoryから確定できる情報は質問しない。結果を左右する不明点だけユーザーへ確認する。

## 2. Build the Task Graph

Nodeは1担当へ渡せるJobにする。Edgeは後段が前段の成果を読む場合だけ作る。

```text
Goal Contract
     ↓
Context / Baseline
     ↓
Plan Owner
  ┌──┼──────────┐
  ↓  ↓          ↓
Worker A   Worker B   Worker C
  └──┼──────────┘
     ↓
Independent Verifier
     ↓
Merge Owner
     ↓
Human Gate
```

Rules:

- Fake Edgeを削除する
- 逐次依存は1 Workerに残す
- 1 ArtifactにつきWriterは1人
- 最大4 Worker
- Merge Ownerを1人に固定
- Artifact Graph Toolを必須にしない。通常の検索やファイル一覧で十分ならそれを使う

詳細: `references/task-graphs.md`

## 3. Run Bounded Loops

Action Nodeは次のLoopで進める。

```text
Input → Action → Observe → Evaluate → Continue | Approve | Reject | Escalate
```

- 最大3 Attempt
- 同じFailure Signatureを2回繰り返したら仮説を変更するか停止
- Scopeを広げて失敗を隠さない
- Testを無効化しない
- Implementerは自分の完了を判定しない

詳細: `references/loop-design.md`

## 4. Apply Unity Constraints

- Runtimeから`UnityEditor`を参照しない
- Editor機能はEditor FolderまたはEditor-only Assemblyへ隔離
- asmdefは境界が必要な場合だけ追加
- private Fieldは`_camelCase`
- Enumは`E_`、Structは`S_`
- MonoBehaviourは1ファイル1型
- 不要なController、Setup、自動探索、static状態を追加しない
- ProjectSettings、URP Asset、Scene、Materialを暗黙変更しない
- Shader / RendererFeatureではPass、LightMode、RenderQueue、Layer、Sorting、Resource read/writeを記録
- Unity APIは公式DocumentationまたはUnityCsReferenceで確認する
- UnityCsReferenceのSourceを転載しない

## 5. Verify in a Separate Context

VerifierはMakerと別Contextで動き、次のどれかを返す。

```text
APPROVE | REJECT | ESCALATE_HUMAN
```

Evidenceは依頼に応じて選ぶ。

- Unity Compile
- EditMode / PlayMode Test
- Build
- Missing GUID / Reference
- Runtime / Editor Assembly Boundary
- Screenshot / Game View Capture
- Frame Debugger / RenderDoc
- CPU / GPU / Memory Capture
- Shader Variant / Keyword / Pass Evidence

実行していない検証を推測でPASSにしない。

詳細: `references/unity-verification.md`

## 6. Human Gate

`gate.yaml`を読み、Merge、Delete、ProjectSettings、Package、Scene大規模変更などを承認待ちにする。

ユーザーが明示的にMergeを依頼した場合のみMergeする。

## 7. Write State Back

作業後に対象Repositoryの`STATE.md`へOutcome、Evidence、Failure、Next Action、Human Overrideを記録する。

長期的に再利用できるFactだけを`KNOWLEDGE.md`またはKnowledge Storeへ追加する。Source、UnityVersion、Platform、PackageVersion、observed_at、confidenceを付ける。

詳細: `references/knowledge-writeback.md`

## Completion Output

1. Goalの達成状況
2. 実行したTask Graph
3. Attemptと変更Artifact
4. Verifier VerdictとEvidence
5. 未検証事項
6. Human Gate
7. State / Knowledge Write-back
