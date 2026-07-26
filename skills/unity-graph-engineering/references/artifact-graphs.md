# Unity Artifact Dependency Graph

## Initial Node Types

- Scene
- Prefab
- Material
- Shader
- HlslInclude
- Script
- ScriptableObjectAsset
- RenderPipelineAsset
- RendererData
- Texture / Mesh / Audio
- Package / Assembly / ProjectSetting

## Initial Relations

- `DEPENDS_ON`
- `REFERENCES`
- `CONTAINS`
- `USES_SHADER`
- `INCLUDES`
- `COMPILES_INTO`
- `CONFIGURES`
- `EXECUTES_BEFORE` / `EXECUTES_AFTER`
- `READS_RESOURCE` / `WRITES_RESOURCE`

## Phase 0 Extraction

`AssetDatabase.GetDependencies(assetPath, false)`を直接依存Edgeとして保存する。自己参照を除外し、GUIDをNode IDへ使用する。Package依存を含めるかはScan設定で切り替える。

このAPIだけでは次を表現できない。

- C# method call
- SerializedObject内の意味的なRole
- Shader PassとLightMode
- RenderGraph Resource
- Addressables group / label
- 動的な`Resources.Load`、`Shader.Find`、文字列Scene load

したがってPhase 0のEdgeを完全な依存関係と呼ばず、`AssetDatabase direct dependency`というEvidenceを必ず付ける。
