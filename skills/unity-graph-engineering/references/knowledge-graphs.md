# Unity Knowledge Graphs

## Competency Questions

Ontologyは先に、実際に答えたい質問から設計する。

- このShaderを変更すると、どのMaterial・Prefab・Scene・Platformが影響を受けるか
- Switch実機だけで発生したRenderQueue変更の原因と修正は何か
- Unity 6000.7で利用できるAPIと、過去versionの代替実装は何か
- このRendererFeatureが読む・書くRenderGraph Resourceは何か
- 同じ不具合を再発させたCommitはあるか

## Provenance

Factだけを保存せず、次を保存する。

```yaml
fact: MaterialのrawRenderQueueが-1へ戻った
unity_version: 6000.3
platform: Nintendo Switch
source: Player log and source file
observed_at: 2026-07-16
confidence: verified
```

## Fusion

同じArtifactがPath変更、別名、Package埋め込みによって複数Nodeになることがある。GUID、GlobalObjectId、assembly-qualified type、repository+commitなど、Entityごとのcanonical identityを定義する。

誤MergeはEdge全体を汚染するため、高信頼だけ自動Mergeし、中間帯はHuman Reviewへ送る。Merge履歴を残してUndo可能にする。

## GraphRAG

単純なキーワード検索で答えられる質問はVector/全文検索を使う。Graphはmulti-hop質問、影響範囲、原因経路、version/platform横断に限定して維持費を正当化する。
