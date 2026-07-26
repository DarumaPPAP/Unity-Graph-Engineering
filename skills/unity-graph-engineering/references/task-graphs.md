# Unity Task Graphs

Task GraphはAIがUnity制作を進める外側の実行Topologyであり、Unity Editor内の表示機能ではない。

## Node Contract

各Nodeは次を持つ。

```yaml
id: unique-id
owner: one-agent-role
purpose: one verifiable job
inputs: []
outputs: []
depends_on: []
write_scope: []
verification: []
status: pending
```

`URPを直す`のような巨大Nodeは避ける。`RendererFeatureのResource使用を調査する`、`Shader Passを修正する`、`対象PlatformでBuildする`のように、単一Ownerと判定可能なOutputを持たせる。

## Real Edge

Edgeは、後段Nodeが前段NodeのOutputを必要とする場合だけ作る。

Real Edge:

```text
Reproduction Evidence → Root Cause Analysis
Shader Interface Design → HLSL Implementation
Implementation Diff → Independent Verification
```

Fake Edge:

```text
Unity API Research → Reference Image Analysis
Repository Scan → Unrelated Documentation Draft
```

Fake Edgeを削除すると並列化できる。ただし並列化のために依存を偽装してはならない。

## Diamond Pattern

```text
                  ┌─ official API research ─┐
Goal → Plan Owner ├─ repository inspection ─┼→ Merge Context → Implementation
                  └─ platform constraints ──┘

Implementation → Independent Verifier → Merge Owner → Human Gate
```

Fan-outは読み取り中心の独立作業に使う。実装後の結果を統合するOwnerは1人に固定する。

## Unityで安全に並列化しやすい作業

- Unity公式API調査
- Repository既存規約の確認
- 対象Platform制約の確認
- Reference Imageの独立分析
- 別Artifactに対する読み取り専用調査
- Compile、Visual、Performanceの独立Verifier

## Unityで逐次に残す作業

- 同じScene、Prefab、Materialへの編集
- Shader Interfaceとそれに依存するPass実装
- Compile Errorを順番に解消する作業
- 1枚の最終画を見ながら行うLighting調整
- Baseline計測後のOptimization
- Root Cause仮説に基づくTargeted Fix

## Writer Ownership

同じArtifactを複数Workerが変更しない。

```yaml
ownership:
  "Assets/Shaders/**": rendering-worker
  "Assets/Editor/**": tooling-worker
  "ProjectSettings/**": project-owner
  "Packages/manifest.json": package-owner
```

境界をまたぐ変更はPlan Ownerが1 Workerへ統合するか、Artifact単位で分ける。

## Stop Rule

- 最大Worker: 4
- 最大Implementation Attempt: 3
- 同じFailure Signature: 2回まで
- Merge Owner: 1人
- LoopごとにBudgetとHuman Escalationを定義

More agents is not the goal. Sequential work remains with one agent when it needs the full picture.

## Human as a Node

Human GateはすべてのEdgeへ置かない。失敗時の巻き戻しCostが高い場所へ置く。

- merge
- delete
- ProjectSettings
- Package
- Scene大規模置換
- Build配布

CompileやStatic Analysisなど機械判定可能なEdgeはVerifierへ任せる。
