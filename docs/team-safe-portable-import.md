# Team Safe Portable Import Boundary

`team_safe_import`は会社ProjectをAIへ接続するProfileではありません。

**外部で作成・検証したPortable Artifactを、一方向にImportするための境界**です。

## Allowed execution

`team_safe_import`で変更を伴うWork Kindは`portable_import`だけです。

```text
Portable Artifact
      ↓
External / Portable Verification Evidence
      ↓
ExecutionOrchestrator.prepare(work_kind=portable_import)
      ↓
No Ix
No Project Source Path
No project_internal Memory
      ↓
ONE bounded portable import slice
      ↓
Portable-safe Evidence
      ↓
Quota / State accounting
```

## Forbidden

`team_safe_import`では以下を禁止します。

- `work_kind=mutation`
- Ix probe / map / impact / trace
- Local Project Source Path
- Project Scanner
- Source Export
- Screenshot / Hierarchy
- Git / Issue / Cloud / Environment Variable
- Unity Project ID / Organization / Customer information
- `project_internal` Layered Memory
- ScopeなしLegacy Memory
- Portable ArtifactのふりをしたProject internal path

`scope_class=portable_artifact`というラベルだけでは許可されません。

Execution Orchestratorは非Personal Profileで`source_verification.paths`が1件でも存在した時点で`non_personal_source_path_forbidden`として停止します。

## Evidence-only source/import verification

`portable_import`のPrepareには次を要求します。

```json
{
  "work_kind": "portable_import",
  "execution_profile": "team_safe_import",
  "source_verification": {
    "completed": true,
    "scope_class": "portable_artifact",
    "paths": [],
    "evidence_refs": ["portable-package-verification-001"]
  }
}
```

必要条件:

- `scope_class == portable_artifact`
- `paths == []`
- `evidence_refs`が1件以上
- Continuation GateがPASS
- Concrete Selected Todoあり
- 複数WorkerならClaim/LeaseがStateへ永続化済み

## Memory boundary

Non-personal Profileは`STATE/memory/L*`を直接全件Scanしません。

```text
STATE/memory/safe-index.jsonl
        ↓
portable_artifact / public_reference のIDだけ取得
        ↓
許可済みRecordだけOpen
```

`project_internal`はSafe Indexへ登録されません。

Scopeなし、またはSafe Indexへ登録されていないLegacy Recordは内容を開かず`project_internal`相当としてFail Closedします。

## Finalize

`portable_import`のFinalize Evidenceも`portable_artifact`または明示的に許可されたPortable-safe情報だけを扱います。

- EvidenceはWorkspace内へ限定
- L0 Raw Evidence保存後にQuota Spend Projection
- Evidence保存失敗時はQuota Spend禁止
- Ticket発行後にStateが変化していた場合はEvidenceだけ保全しAccounting停止
- 同一SliceのFinalize再送はQuota delta 0

## Important distinction

```text
personal_full_control / mutation
  → Project Sourceを直接読む
  → 必要ならIxでNavigation
  → Source Mutation

team_safe_import / portable_import
  → Project Sourceを読まない
  → Ixを使わない
  → Portable EvidenceだけでImport境界を確認
```

この2経路を同じ`mutation`として扱わないことがSafety Modelの前提です。
