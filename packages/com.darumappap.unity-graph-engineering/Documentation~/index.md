# Unity Graph Engineering Package

## Artifact Graph

`Tools > Graph Engineering > Artifact Graph`を開き、走査対象Folderを指定します。

1. `Graphを走査`してAsset依存を取得します。
2. Scan ReportでNode / Edge数、処理時間、Missing GUID、未知種別、Skipped dependencyを確認します。
3. 変更対象Assetと最大Hop数を指定し、`影響範囲を逆引き`して参照元を直接・間接に辿ります。
4. 必要に応じてGraph JSONをUnity Project内へ出力します。

出力JSONは`schemas/artifact-graph.schema.json`で検証できます。NodeとEdgeはPath / ID順に整列されますが、`GeneratedAtUtc`と`DurationMilliseconds`は走査ごとに変化します。

## EditMode Tests

Packageを`testables`へ追加すると、`DarumaPPAP.UnityGraphEngineering.Editor.Tests`をTest Runnerから実行できます。

- 空FolderのScan
- Prefab → Material → Shader依存
- 揮発Fieldを除いたJSONの安定性
- ShaderからMaterial / Prefabへの逆引き
- Project外へのPath Traversal拒否

## Limitations

- 文字列によるScene Load、Resources Load、Shader.Findは検出しません
- GUID + fileID / GlobalObjectIdは未対応です
- C# method call graphは未対応です
- Shader Pass、LightMode、RenderGraph Resourceは未対応です
- JSON出力はSnapshotであり、差分更新やFusionは未対応です
