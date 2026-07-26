# Unity Artifact Graph Scanner — Legacy Optional Tool

> This package is not the Unity Graph Engineering core workflow.

Unity Graph Engineering now governs how AI agents plan, implement, verify, and record Unity production work. This Editor package remains only as an optional dependency-inspection experiment.

Do not install it merely to use the AI workflow. Target Unity repositories only need the project context, state, workflow, and verifier files documented at the repository root.

## Artifact Graph Window

`Tools > Graph Engineering > Artifact Graph`

1. `Graphを走査`してAssetDatabase direct dependenciesを取得する
2. Scan ReportでNode / Edge、処理時間、Missing GUID、Skipped dependencyを確認する
3. 変更対象Assetから参照元を逆引きする
4. 必要に応じてSnapshot JSONを出力する

## Evidence Boundary

The scanner only proves dependencies returned by `AssetDatabase.GetDependencies`.

It does not prove:

- C# method calls
- dynamic Scene/Resource/Shader loads
- GUID + fileID or GlobalObjectId relationships
- Shader Pass or LightMode execution
- RenderGraph resource flow
- Addressables semantics

Never use this snapshot as the sole basis for an implementation or merge decision.

## Tests

When added to `testables`, `DarumaPPAP.UnityGraphEngineering.Editor.Tests` checks empty scans, Prefab/Material/Shader dependency chains, normalized output stability, reverse lookup, path traversal rejection, and committed `.meta` files.

## Future

The package should be archived or moved to a separate repository after the AI production framework is dogfooded successfully in FakeUnity7.
