# External Intelligence / Control Plane Integration

Unity-Graph-EngineeringへIx、LoopX、TencentDB-Agent-Memoryから有効な設計を取り込みつつ、外部Runtimeを必須化しないための統合仕様。

## Responsibility map

| Reference | Local role | Local implementation | Required? | Authority |
|---|---|---|---:|---|
| `ix-infrastructure/Ix` | Code Intelligence Provider | `Tools/IxAdapter/ix_adapter.py` | No | Source code / tests remain authoritative |
| `huangruiteng/loopx` | Continuation Control | `Tools/ContinuationController/continuation_controller.py` | No | Unity-Graph-Engineering state/policy |
| `TencentCloud/TencentDB-Agent-Memory` | Layered Memory | `Tools/LayeredMemoryController/layered_memory_controller.py` | No | Raw Evidence + local state |

## Why native adapters/controllers instead of embedding

Unity-Graph-EngineeringはUnity AI実行方式の正本であり、特定Vendor/RuntimeへExecution authorityを移さない。

- Providerが無くてもPlanning/Mutationを継続できる
- Package追加を暗黙に起こさない
- `team_safe_import`のProject情報境界を維持する
- Human Gate、Budget、Evidence Admissionを一箇所へ固定する
- 将来Providerを交換してもTask Contractを維持できる

## Ix path

`personal_full_control`で利用可能な場合のみ、構造質問・影響解析・依存Traceへ使用する。

```text
Ix Adapter → map / explain / impact / trace / callers / callees
           → candidate scope
           → direct Source verification
```

任意Command passthroughや`ix reset`等の破壊操作は公開しない。Ix unavailable時はTargeted Source ReadへFallbackする。

## LoopX path

LoopXのObjective/Todo/Claim/Lease/Quota/Evidence WritebackをNative Continuation Controllerへ再設計した。

```text
Health → Human → Writeback → Evidence → Focus → Budget → Quota
                                                     ↓
                                              Todo / Capability
                                                     ↓
                                                bounded slice
                                                     ↓
                                           Evidence + Writeback
                                                     ↓
                                                Quota Spend
```

- QuotaはPermissionでもBudgetでもない
- `compute_share=0`はGoalを削除せず自動継続だけPause
- Monitor-only laneはMaterial Transitionがなければquiet skip
- Spendはvalidated durable writeback + Evidenceがある場合だけProjectionする

## TencentDB-Agent-Memory path

Raw Tool LogをL0 Evidenceへ保存し、L1 Atom、L2 Scenario、L3 Reusable Candidateへ段階的に圧縮するNative Layered Memory Controllerを実装した。

```text
Evidence/raw/<id>.txt
        ↓
STATE/memory/L0/<id>.json
        ↓ raw_refs
STATE/memory/L1/<id>.json
        ↓ atom_refs
STATE/memory/L2/<id>.json
        ↓ scenario_refs
STATE/memory/L3/<id>.json
```

主なOperation:

- `capture_raw`
- `create_atom`
- `create_scenario`
- `create_candidate`
- `retrieve`
- `drilldown`
- `project`
- `promote`

通常Retrievalは上位Layerを優先し、Raw contentを含めない。既定8件/6000文字、最大20件/12000文字でContext投入量を制限する。Raw contentが必要な場合だけ明示的に`drilldown`する。

L0 CaptureではSHA-256を保持し、同IDの異なる内容をsilent overwriteしない。`team_safe_import`では禁止Scopeをsource read前に遮断し、Secret分類・高確度Credential patternは保存しない。

`promote`はProjectionを返すだけでUnityAgent Knowledge/User Policyを直接変更しない。User Policy candidateはVerified + Human Gateが必須。

## External runtime activation

本統合はIx以外の外部Runtimeを必須にしない。既存のIx/Tencent Runtime等を将来Providerとして接続する場合は、`policies/external-providers.yaml`のSupply Chain Gateに従い、Version/Revision固定とCapability Probeを行う。

## Validation

```bash
python Tools/ExecutionPolicyValidator/validate_execution_policies.py
python -m unittest discover -s Tests/ExternalProviders -p "test_*.py" -v
```

対象:

- Ix Adapter contract
- Continuation Controller contract
- Layered Memory Controller contract
- External Provider regression cases
