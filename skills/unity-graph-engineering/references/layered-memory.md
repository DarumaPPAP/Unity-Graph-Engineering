# Layered Memory — Evidence-first Compression

TencentDB-Agent-MemoryのLayering / Symbolic Memory思想を、Evidence-firstなUnity実行Memoryへ再構成する。

## Layers

```text
L3 Reusable Candidate
        ↑
L2 Scenario
        ↑
L1 Atom
        ↑
L0 Raw Evidence
```

### L0 Raw Evidence

Compiler log、Tool output、Diff、Test、Profiler等。上位Memoryの根拠として保持する。

### L1 Atom

一つの観測・確定Factへ圧縮する。必ずRaw Evidenceへdrill downできるようにする。

### L2 Scenario

複数Atomから、再利用可能なFailure ContextやExecution Patternを作る。

### L3 Reusable Candidate

UnityAgent KnowledgeやSkillへ昇格できる候補。自動的にKnowledgeやUser Policyへ書き込まない。

## Short-term projection

巨大Tool Logを毎Turn読み直さず、`STATE/current.yaml`またはcompact Markdown/Mermaid projectionだけをContextへ載せる。

Projectionは表示用であり正本ではない。詳細が必要になった時だけIDからRaw Evidenceへdrill downする。

## Promotion boundary

```text
Raw Evidence
  ↓ verified/scoped
Atom
  ↓ generalizable
Scenario
  ↓ provenance review
Reusable Candidate
  ├─ UnityAgent Knowledge → verified evidence required
  └─ User Policy         → Human Gate required
```

ユーザー固有Policyは推測で更新しない。会話頻度やMemory統計だけで`.ai/user-policy.yaml`へ昇格させない。

## Conflict handling

新旧Memoryが競合した場合は古い側をsilent overwriteしない。Version、Platform、Package、Evidence差を保持し、`supersedes`または`conflicts_with`で追跡する。
