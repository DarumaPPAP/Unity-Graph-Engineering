# Roadmap

## Phase 0 — Foundation

- [x] Unity固有Graph Engineering Skill
- [x] 3 Graph Architecture
- [x] Unity Ontology初版
- [x] Artifact Graph JSON Schema
- [x] AssetDatabaseベースの依存ScannerとExporter

## Phase 1 — Artifact Graph Quality

- [x] Node / Edgeの決定的な順序付け
- [x] Scan ReportとDiagnostics
- [x] Graphの逆引き「このAssetを変更すると何が影響を受けるか」
- [x] EditMode Testの基礎Fixture
- [ ] FakeUnity7 / Unity 6000.7.0a2でCompile・EditMode Testを実行
- [ ] GUID・fileID単位の参照
- [ ] Scene / Prefab階層とComponent Node
- [ ] Material → Shader → Shader Pass → HLSL Include
- [ ] Renderer Data → Renderer Feature → Render Pass
- [ ] URP Asset / QualitySettings / GraphicsSettings
- [ ] 差分ScanとCache

## Phase 2 — Code Graph

- Unity CompilationPipelineからAssembly情報を取得
- RoslynまたはMono.Cecilによる型・メソッド依存
- Runtime → UnityEditor参照違反
- static濫用、循環依存、巨大責務の診断
- MonoBehaviour / ScriptableObject / Editor Toolの分類

## Phase 3 — Rendering Graph

- ShaderLab PassとLightMode
- RenderQueue / SortingCriteria / LayerMask / ShaderTagId
- RenderGraph Resource read/write
- MotionVector / Depth / GBuffer / Colorの生成・消費関係
- Shader Variant / Keyword / PSOの関係

## Phase 4 — Task Graph Runner

- YAMLからTask Graphを読み込む
- Nodeの入力・出力Schema
- 並列fan-outとjoin
- One Writer per Artifact
- VerifierとHuman Gate
- Loopの最大回数とToken/Cost Budget

## Phase 5 — Knowledge Write-back

- Bug → Cause → Fix → Verificationの保存
- UnityVersion・Platform・PackageVersionをFactへ付与
- PR・Commit・ログ・スクリーンショットのprovenance
- GraphRAGで過去の修正経路を検索

## Phase 6 — Visual Graph Editor

データモデルと検証が安定した後に可視化を追加します。先にGraphViewを作り込まず、JSON/YAMLとQueryが実用になることを優先します。
