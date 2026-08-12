# Code Intelligence Provider — Ix

`ix-infrastructure/Ix`のCode Graph設計を、`personal_full_control`向けOptional Code Intelligence Providerとして利用する。

## Position

IxはSource of Truthではない。構造探索を高速化するNavigation Layerである。

```text
Request
  ↓
Ix available?
  ├─ no  → targeted Source read / repository search
  └─ yes → map / explain / trace / impact
                    ↓
             candidate scope
                    ↓
          direct Source verification
                    ↓
               mutation / test
```

## Use when

- unfamiliar subsystemの入口を探す
- caller / callee / import関係を絞る
-変更前のblast radiusを見積もる
- data flowや依存経路を追う
- 大規模Repositoryで読むFileを減らす

## Do not use as

- Runtime挙動の証明
- Unity serializationの完全な意味解析
- Scene / Prefab / Material状態の代替
- Compile/Test/Profiler Evidenceの代替
- `team_safe_import`でのProject Scanner

## Required behavior

1. Provider availabilityはCapability Manifestで`available | unavailable | unknown | prohibited`として扱う。
2. unavailableでもTaskを停止しない。
3. `impact`や`trace`で候補範囲を絞った後、Mutation前に対象Sourceを直接読む。
4. Source変更後、Ixが利用可能ならMapをrefreshする。
5. Low-confidence/ambiguous resultを確定Factとして扱わない。
6. Graph結果はEvidence IDへ紐付けてもよいが、Runtime/Visual/Performance GateのPASSには単独で使用しない。

## Integration boundary

Ix CLIやDocker環境の自動Installは行わない。既存Installを検出して利用するか、ユーザーがPackage/Tool導入を明示した場合のみ別Human Gateで扱う。
