# Layered Memory — Evidence-first Compression

TencentDB-Agent-MemoryのL0→L3 Layeringを、Unity-Graph-EngineeringのEvidence-first実行Memoryとして再構成する。

実働入口は `Tools/LayeredMemoryController/layered_memory_controller.py`。
外部TencentDB Runtimeは必須ではなく、正本はGraph Engineering側の`Evidence/`と`STATE/memory/`に置く。

## Layers

```text
L3 Reusable Candidate
        ↑ scenario_refs
L2 Scenario
        ↑ atom_refs
L1 Atom
        ↑ raw_refs
L0 Raw Evidence
```

### L0 Raw Evidence

Compiler log、Tool output、Diff、Test、Profiler等のSource-faithful Evidence。

- Raw: `Evidence/raw/<id>.txt`
- Metadata: `STATE/memory/L0/<id>.json`
- SHA-256を保持する。
- 同じID + 同じdigestは冪等。
- 同じID + 異なるdigestは上書きせずBlockする。
- Secret分類または高確度Credential patternは保存しない。
- `team_safe_import`ではScope Gateを**source file read前**に評価する。

### L1 Atom

一つの観測・Factへ圧縮する。`raw_refs`が必須で、L0以外を参照できない。

### L2 Scenario

Atomから再利用可能なExecution Pattern / Failure Contextを作る。
`atom_refs`、`applicability`、`limits`が必須。

### L3 Reusable Candidate

UnityAgent KnowledgeやExecution Referenceへ昇格できる候補。
`scenario_refs`、`provenance`、`promotion_target`、Review状態を持つ。

## Native Controller operations

RequestはUTF-8 JSON fileで渡す。

- `capture_raw`
- `create_atom`
- `create_scenario`
- `create_candidate`
- `retrieve`
- `drilldown`
- `project`
- `promote`

ControllerはPython stdlibのみで動作する。

## Retrieval / Context compression

通常はRaw Tool LogをPromptへ戻さない。

```text
Query
  ↓
L3 / L2 / L1 / L0 metadataをbounded retrieval
  ↓
Compact Projection
  ↓ 必要な場合だけ
Drill-down by memory_id
  ↓ 明示指定された場合だけ
Raw Evidence content
```

既定値:

- max items: 8
- hard max items: 20
- max characters: 6000
- hard max characters: 12000
- Raw content: default OFF

Repository / Unity version / Platformが一致するMemoryはretrievalで優先できる。
MemoryはRuntime/Visual/Performanceの証明にはならず、必要なら元Evidenceへdrill downする。

## Short-term projection

ProjectionはContext圧縮用でありSource of Truthではない。

正本:

- `STATE/current.yaml`
- `Evidence/raw/`
- `STATE/memory/`

`project`はRaw contentを含めない。

## Promotion boundary

```text
Raw Evidence
  ↓ verified/scoped
Atom
  ↓ generalizable
Scenario
  ↓ provenance + review
Reusable Candidate
  ├─ Execution Reference
  ├─ UnityAgent Knowledge → verified required
  └─ User Policy Candidate → verified + Human Gate required
```

`promote`は**Projectionを返すだけ**で、UnityAgentやUser Policyを直接変更しない。
User Policyへの自動昇格は禁止する。

## Conflict handling

新旧Memoryが競合した場合は古いRecordをsilent overwriteしない。

- `supersedes`: 新Recordが旧Recordを置き換える関係
- `conflicts_with`: 解決していない競合関係

旧Recordは残し、Evidence差・Version差・Platform差を後から追跡できる状態を維持する。

## Example

```bash
python Tools/LayeredMemoryController/layered_memory_controller.py \
  --workspace-root . \
  --request examples/layered-memory-capture.json
```

次のTurnでは必要な上位Memoryだけを`retrieve` / `project`し、詳細が必要になった時だけ`drilldown`する。
