# External Intelligence / Control Plane Integration

Unity-Graph-EngineeringへIx、LoopX、TencentDB-Agent-Memoryから有効な設計を取り込みつつ、外部Runtimeを必須化しないための統合仕様。

## Responsibility map

| Reference | Local role | Required? | Authority |
|---|---|---:|---|
| `ix-infrastructure/Ix` | Code Intelligence Provider | No | Source code / tests remain authoritative |
| `huangruiteng/loopx` | Continuation Control concepts | No | Unity-Graph-Engineering state/policy |
| `TencentCloud/TencentDB-Agent-Memory` | Layered Memory concepts | No | Raw Evidence + local state |

## Why adapters instead of embedding

Unity-Graph-EngineeringはUnity AI実行方式の正本であり、特定Vendor/RuntimeへExecution authorityを移さない。

- Providerが無くてもPlanning/Mutationを継続できる
- Package追加を暗黙に起こさない
- `team_safe_import`のProject情報境界を維持する
- Human Gate、Budget、Evidence Admissionを一箇所へ固定する
- 将来Providerを交換してもTask Contractを維持できる

## Ix path

`personal_full_control`で利用可能な場合のみ、構造質問・影響解析・依存Traceへ使用する。Graph結果で対象Sourceを絞り、Mutation前には必ずSourceを直接確認する。変更後は可能ならGraphをrefreshする。

## LoopX path

LoopXのObjective/Todo/Claim/Lease/Quota/Evidence Writebackを、native continuation contractへ再設計した。QuotaはPermissionでもBudgetでもない。

継続順序は `Health → Human → Evidence → Focus → Quota → Bounded Work`。1回の継続は1 Node/Verification sliceで止め、EvidenceとStateを書き戻してから次を判定する。

## TencentDB-Agent-Memory path

Raw Tool LogをL0 Evidenceへ退避し、L1 Atom、L2 Scenario、L3 Reusable Candidateへ段階的に圧縮する。上位層は必ず下位Evidenceへdrill downできること。

Mermaid等のSymbolic ProjectionはContext節約のために使用できるが、State authorityにはしない。

User PolicyへのMemory自動昇格は禁止。UnityAgent Knowledgeへの昇格もVerified Evidenceを要求する。

## Activation

本変更だけでは外部PackageをInstallしない。既存のIx/LoopX/Tencent Runtimeを接続する場合は、`policies/external-providers.yaml`のSupply Chain Gateに従い、Version/Revision固定とCapability Probeを行う。

## Validation

```bash
python Tools/ExecutionPolicyValidator/validate_execution_policies.py
```

External Provider regression cases:

```text
Tests/ExternalProviders/cases.yaml
```
