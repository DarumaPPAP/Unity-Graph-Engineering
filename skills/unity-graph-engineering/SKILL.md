---
name: unity-graph-engineering
description: Use when planning, implementing, reviewing, or teaching graph-engineered Unity development: task graphs for agent orchestration, knowledge graphs for durable Unity facts, and artifact dependency graphs for Scenes, Prefabs, Materials, Shaders, Scripts, Packages, ProjectSettings, and render-pipeline resources.
---

# Unity Graph Engineering

Unity開発をPromptの列ではなく、明示的なNode・Edge・State・Evidenceとして設計する。

## Three Graphs

1. **Task Graph** — 今回の作業。NodeはJob、Edgeは実行依存。
2. **Knowledge Graph** — 長期知識。Bug、Cause、Fix、Constraint、Decision、Benchmark、Sourceを保存。
3. **Artifact Dependency Graph** — Unity Project構造。Scene、Prefab、Material、Shader、HLSL、Script、Assembly、Package、ProjectSettingsを接続。

3つを論理的に接続してよいが、同じStoreや同じSchemaへ無理に統合しない。

## Mandatory Workflow

### 1. Goal Compiler

実装前に次を機械判定可能なAcceptance Contractへ変換する。

- Unity version
- Render Pipeline
- Target platforms
- Deliverables
- Must / Must not
- Visual acceptance
- Performance budget
- Verification method

不明な値は勝手に埋めず、Repositoryから確定できない重要項目だけ確認する。

### 2. Artifact Scan

変更対象と依存先を列挙する。最低限、対象ファイル、参照元、参照先、Assembly境界、Editor/Runtime境界を確認する。

変更影響をGraphで表現できない場合は、単純なファイル一覧と検索で済ませる。Graphを作ることを目的化しない。

### 3. Plan Graph

Edgeは後段Nodeが前段成果物を読む場合だけ作る。Fake Edgeを削除し、独立調査だけを並列化する。

推奨形:

```text
                         ┌─ worker A ─┐
plan ─ artifact/context ─┼─ worker B ─┼─ verifier ─ merge ─ human gate
                         └─ worker C ─┘
```

逐次依存が強い作業は1つのWorkerに残す。Agent数を増やすことを最適化指標にしない。

### 4. Ownership

1 ArtifactにつきWriterは1つ。複数Workerが同じ`.cs`、`.shader`、`.unity`、`.asset`、ProjectSettingsを変更してはならない。

### 5. Implementation

Unity固有ルール:

- Runtimeから`UnityEditor` APIを呼ばない
- Editor機能はEditor folderまたはEditor-only asmdefへ隔離
- asmdefは依存境界として必要な場合だけ追加
- private fieldは`_camelCase`
- Enumは`E_`、Structは`S_`。Structは値型の利点が明確な場合だけ使用
- MonoBehaviourは1ファイル1型
- 不要なController、Setup関数、自動探索、static状態を追加しない
- ProjectSettingsやURP Assetの変更を暗黙に行わない
- Shader / RendererFeature変更ではPass、LightMode、RenderQueue、Layer、Sorting、Resource read/writeを記録

### 6. Independent Verification

Verifierは実装者と別Contextで実行する。自己評価のみで完了扱いにしない。

Evidence例:

- Unity compile result
- EditMode / PlayMode test result
- Build result per platform
- Runtime/Editor assembly boundary
- Missing GUID / reference
- Screenshot or captured frame
- Frame Debugger / RenderDoc event
- CPU / GPU / memory measurement
- Shader variant and keyword evidence

### 7. Merge Owner

Verifierが通した変更だけを1つのOwnerが統合する。衝突時にWorker同士で暗黙解決させない。

### 8. Human Gate

merge、release、deploy、delete、ProjectSettingsの大規模置換など、失敗時に戻すコストが高い操作は明示承認を通す。

### 9. Knowledge Write-back

完了後、次を保存する。

```text
(Bug)-[CAUSED_BY]->(Artifact)
(Bug)-[FIXED_BY]->(Fix)
(Fix)-[VERIFIED_BY]->(Benchmark)
(Fact)-[DOCUMENTED_BY]->(Source)
```

FactとEdgeにはUnityVersion、Platform、PackageVersion、source、observed_at、confidenceを付ける。

## Source Policy

- Unity APIは公式DocumentationまたはUnityCsReferenceで確認する
- UnityCsReferenceはReference Onlyのためコードを複製しない
- Repositoryの既存規約と実装を一般論より優先する
- 外部記事の主張はversionと検証条件を記録する

## Completion Contract

最終報告には以下を含める。

1. Task Graphの実行結果
2. 変更Artifactと依存影響
3. Verifier Evidence
4. 未検証事項
5. Human Gateが必要な操作
6. Knowledge Graphへ書き戻すFact
