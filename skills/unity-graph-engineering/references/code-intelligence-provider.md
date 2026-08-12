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

## Native adapter

Unity-Graph-Engineeringは `Tools/IxAdapter/ix_adapter.py` を唯一のIx CLI実行境界として使用する。

Adapterは任意のIx command passthroughを提供しない。許可する操作は以下だけ。

- `probe`
- `status`
- `map`
- `explain`
- `impact`
- `trace`
- `callers`
- `callees`

`ix reset`を含む破壊的Commandは公開しない。Subprocessはargument listで起動し、`shell=False`を固定する。Target symbolが`-`で始まる場合はoption injection防止のため拒否する。

### Example

```bash
python Tools/IxAdapter/ix_adapter.py probe --repo-root .
python Tools/IxAdapter/ix_adapter.py impact RenderPipeline --repo-root .
python Tools/IxAdapter/ix_adapter.py trace RenderPipeline --repo-root . --direction upstream
```

`trace`はIx本体が無制限Traversalを許容するため、Adapter側では既定で `--depth 3 --cap 100` を付与する。必要な場合のみ明示的に上限を変更する。

Adapterのstdoutは常にJSON envelopeとし、主な状態は次の通り。

```text
ok              → provider resultをNavigationに使用可能
unavailable     → Ix CLI / backend unavailable。targeted_source_readへFallback
error           → command/parse/timeout failure。確定Factには使用しない
invalid_request → Adapter contract違反
```

Exit codeは `0=ok / 2=unavailable / 3=error / 4=invalid_request`。

Low-confidence resultは`status=ok`のまま`low_confidence=true`とDiagnosticを付ける。確定Factへ昇格せず、Sourceを直接確認する。

## Use when

- unfamiliar subsystemの入口を探す
- caller / callee / import関係を絞る
- 変更前のblast radiusを見積もる
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
7. Adapter以外からIxへ任意Commandを中継しない。
8. `trace`は必ずbounded depth / node capで実行する。

## Integration boundary

Ix CLIやDocker環境の自動Installは行わない。既存Installを検出して利用するか、ユーザーがPackage/Tool導入を明示した場合のみ別Human Gateで扱う。
