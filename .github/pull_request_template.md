## Goal Contract

<!-- Goal / Deliverables / Acceptance Criteria / Must / Must Not / Unity / Pipeline / Platform -->

## Selected Workflow

<!-- workflows/*.yaml -->

## Task Graph

<!-- Node、Owner、実Edge、並列化した作業、逐次に残した作業 -->

## Loop Results

| Node | Attempts | Result | Failure signature / Evidence |
|---|---:|---|---|

## Writer Ownership

<!-- 変更Artifactごとの単一Writer。複数Workerが同じFileを書いていないこと。 -->

## Changed Artifacts

<!-- Path / Reason / Expected Result / Dependents considered -->

## Independent Verification

- Verdict: `APPROVE | REJECT | ESCALATE_HUMAN`

- [ ] Unity compile
- [ ] Editor / Runtime assembly boundary
- [ ] EditMode / PlayMode tests
- [ ] Missing GUID / reference
- [ ] Visual verification
- [ ] Performance measurement
- [ ] Platform build / device verification

未実施項目は`not_run`として理由を記載してください。Makerの自己評価だけで完了扱いにしないでください。

## Risks / Unverified

<!-- 残っているRiskと未検証事項 -->

## State / Knowledge Write-back

<!-- STATE.md、Run Log、Bug / Cause / Fix / Verification / UnityVersion / Platform / Source -->

## Human Gate

- [ ] Merge承認が必要
- [ ] ProjectSettings変更の有無を確認した
- [ ] Package変更の有無を確認した
- [ ] Scene大規模変更の有無を確認した
- [ ] Asset削除の有無を確認した
- [ ] Visual / Performance trade-offを確認した
