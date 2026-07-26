# Unity Task Graphs

## Node

Nodeは単一担当へ渡せるJobにする。`URPを直す`ではなく、`RendererFeatureのResource read/writeを調査する`、`Shader Passを変更する`、`Switch Buildを検証する`まで分解する。

## Edge

後段が前段のOutputを読む場合だけ接続する。

- API調査 → 実装: 実Edge
- Repository構造調査 → 実装: 実Edge
- Shader調査 → 無関係なCalendar確認: Fake Edge

## Parallelism

Unityで安全に並列化しやすいもの:

- 公式API調査
- Repository既存実装調査
- Platform制約調査
- 別ファイル・別責務の読み取り専用分析

並列化しにくいもの:

- 同じSceneやPrefabの編集
- ShaderとMaterial設定を往復しながら調整する作業
- Compile errorを1つずつ解消する作業
- 1枚の最終画を見ながら行うLighting調整

## Verifier Separation

実装担当は変更理由を知りすぎているため、自分の仮定を見落としやすい。Verifierには差分、Acceptance Contract、実行方法だけを渡し、実装会話全体は渡さない。

## Stop Rule

- 最大Loop回数
- 最大並列Worker数
- Time / Token / CI budget
- 同じErrorが再発したらHumanへEscalate

をTask Graphに明記する。
