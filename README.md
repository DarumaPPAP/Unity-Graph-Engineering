# Unity Graph Engineering

Unity 6000.7系のプロジェクトを対象に、AIエージェントの作業とUnityプロジェクトの依存関係を「グラフ」として扱うための実験・実装リポジトリです。

## 目標

本リポジトリでは、次の3層を分離して設計します。

1. **Task Graph** — エージェントが今回どの順番で作業するか
2. **Knowledge Graph** — 過去に判明した事実・判断・不具合・検証結果をどう記憶するか
3. **Artifact Dependency Graph** — Scene、Prefab、Material、Shader、Script、Packageなどが何に依存しているか

Graph Engineeringを「エージェント数を増やす仕組み」にはしません。独立している仕事だけを並列化し、逐次依存する仕事は1つの担当に残します。実装担当と検証担当は分離し、不可逆な操作はHuman Gateを通します。

## 現在のMVP

`packages/com.darumappap.unity-graph-engineering`には、Unity Editor上で指定フォルダ以下のAsset依存関係を走査し、JSONへ出力する最小ツールを配置しています。

- `AssetDatabase.GetDependencies`による直接依存の抽出
- Scene / Prefab / Material / Shader / HLSL / Scriptなどの分類
- GUIDをNode IDとしたArtifact Graph生成
- Unityバージョン・生成時刻・依存根拠を含むJSON出力
- Editor専用Assemblyに隔離し、Runtimeから`UnityEditor`を参照しない構成

### 導入

Unity Package ManagerのGit URLに次を指定します。

```text
https://github.com/DarumaPPAP/Unity-Graph-Engineering.git?path=/packages/com.darumappap.unity-graph-engineering
```

導入後、Unityメニューから次を開きます。

```text
Tools > Graph Engineering > Artifact Graph
```

## リポジトリ構成

```text
.github/                         PR時のGraph Engineeringチェック
skills/unity-graph-engineering/ エージェント向けSkill
schemas/                        Ontology・Task Graph・Artifact Graph Schema
packages/                       Unity Package実装
docs/                           アーキテクチャとロードマップ
```

## 参考リポジトリとの役割分担

- `Unity-Technologies/skills` — Skillの配置・frontmatter・責務分割の参考
- `codejunkie99/graph-engineering` — Knowledge Graph / Task Graphという基本整理の参考
- `Unity-Technologies/UnityCsReference` — Unity Editor APIの挙動確認専用。Reference Only Licenseのためコードは転載しない
- `Unity-Technologies/ml-agents` — UPM Package、Editor/Runtime境界、ドキュメント構成の参考

詳細は[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を参照してください。

## 設計方針

- Schema first
- すべてのFactとEdgeにprovenanceを付ける
- 1 ArtifactにつきWriterは1つ
- 実装者とVerifierを別Contextにする
- Graphが単純な表や逐次処理より有利でない場合はGraphを使わない
- 小規模なPilotを最後まで通してから対象範囲を増やす

## Status

Phase 0: 基盤・Skill・Ontology・Artifact Graph Scannerの初版。次段階ではC#、ShaderLab/HLSL、Scene Objectの意味的依存を追加します。
