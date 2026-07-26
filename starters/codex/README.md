# Codex Starter

CodexでUnity Graph Engineeringを使うための最小構成。

## Copy to a Unity Repository

```text
PROJECT_CONTEXT.md                ← templates/PROJECT_CONTEXT.md
STATE.md                          ← templates/STATE.md
KNOWLEDGE.md                      ← templates/KNOWLEDGE.md
LOOP.md                           ← project-specific loop configuration
AGENTS.md                         ← project rules
.codex/agents/unity-verifier.toml
.codex/agents/unity-visual-verifier.toml
```

Skillは`skills/unity-graph-engineering/`をCodexが参照できるSkill Directoryへ追加する。

## First Run

最初の1回はL1 Reportとして実行し、Sourceを変更しない。

```text
$unity-graph-engineering を使ってこのUnity Repositoryを調査してください。
PROJECT_CONTEXT.mdとSTATE.mdを読み、実装はせず、次の依頼に使うContext不足・検証Command・Human Gateだけを報告してください。
```

調査品質が安定した後、L2 Assistedで実装する。

```text
$unity-graph-engineering を使って依頼をGoal Contractへ変換し、適切なWorkflowで実装してください。
Makerは自分で完了判定せず、unity-verifierへEvidence付きで渡してください。
Mergeは行わずHuman Gateで停止してください。
```

## Maker / Checker

- Maker: SourceやAssetを変更し、Expected ResultとEvidenceを提出
- `unity-verifier`: Compile、Test、Scope、Assembly境界を確認
- `unity-visual-verifier`: Referenceと同一条件Captureを比較
- Merge Owner: 両VerifierのVerdictを統合

## Operating Limits

- 最大3 Attempt
- 最大4 Worker
- 同じFailure Signatureが2回続いたら停止
- 自動Mergeなし
- ProjectSettings、Package、Scene、Asset削除はHuman Gate

## Automation

定期Automationを追加する場合、最初の1〜2週間はReport-onlyにする。無人のSource変更は、実行履歴・予算・Kill Switch・独立Verifierが揃うまで有効化しない。
