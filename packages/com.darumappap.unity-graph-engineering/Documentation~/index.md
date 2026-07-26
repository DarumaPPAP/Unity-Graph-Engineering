# Unity Graph Engineering Package

## Artifact Graph

`Tools > Graph Engineering > Artifact Graph`を開き、走査対象Folderを指定します。

Phase 0ではUnityのAssetDatabaseが返す直接依存をGraph化します。出力JSONはRepository外のKnowledge Storeへ取り込む前に、`schemas/artifact-graph.schema.json`で検証できます。

## Limitations

- 文字列によるScene Load、Resources Load、Shader.Findは検出しません
- C# method call graphは未対応です
- Shader Pass、LightMode、RenderGraph Resourceは未対応です
- JSON出力はSnapshotであり、差分更新やFusionは未対応です
