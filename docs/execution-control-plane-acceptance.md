# Execution Control Plane Acceptance Gates

この文書はPR #8を「実装済み」と「Merge可能」に分けて判定するためのGateです。

## P0 — Runtime safety

- [x] Graph / Loop以外をExecution Orchestratorへ入れない
- [x] Safety-relevant State欠落をFail Closed
- [x] Profile mismatchをFail Closed
- [x] Health / Human / Evidence / Focus / Budget / Quotaを最初に評価
- [x] Gate停止中はMemory/Ixを起動しない
- [x] Concrete Selected TodoなしではTicketを発行しない
- [x] Multi-worker Claim/LeaseはStateへdurable writebackするまで作業開始しない
- [x] Arbitrary subprocess command passthroughなし
- [x] `shell=False`
- [x] Controller identity / timeout / malformed JSONをFail Closed

## P0 — Personal / Generic / Team Safe isolation

- [x] Ixは`personal_full_control`のみ
- [x] `generic_planning`は`mutation`禁止
- [x] `team_safe_import`は一般`mutation`禁止
- [x] Team Safeの変更経路を`portable_import`へ分離
- [x] `portable_import`は`portable_artifact` scopeのみ
- [x] Non-personal ProfileはLocal Source Path禁止
- [x] Mutation Source VerificationはEvidence Ref必須
- [x] Ticket内Source PathはWorkspace-relative
- [x] Path escape禁止

## P0 — Layered Memory isolation

- [x] L0 Raw Evidenceを要約で置換しない
- [x] Raw EvidenceへSHA-256付与
- [x] same ID / different digestをBlock
- [x] Secret分類・高確度Credential patternをCapture拒否
- [x] Capture ScopeをSource File Readより前に検査
- [x] L0→L1→L2→L3で最も厳しいScopeを継承
- [x] Scope downgrade禁止
- [x] Non-personal RetrievalはSafe Indexだけを入口にする
- [x] `project_internal`をSafe Indexへ登録しない
- [x] Unindexed/Legacy RecordをNon-personal Profileで開かない
- [x] Corrupt Safe IndexをFail Closed
- [x] Normal Retrieval/ProjectionへRaw Contentを載せない
- [x] User Policy / UnityAgent KnowledgeをControllerが直接変更しない

## P0 — Ticket / accounting

- [x] TicketをGoal/Todo/Worker/Profile/Work Kind/State/Source Verificationへ束縛
- [x] Ticket digestをFinalizeで検査
- [x] Digestが再計算されてもSemantic BoundaryをFinalizeで再検査
- [x] Ticket digestをAuthentication Tokenとして扱わない
- [x] State fingerprint mismatch時はEvidenceを保持しAccounting停止
- [x] Raw Evidence保存前にQuota Spendしない
- [x] Quota Spend failure時もEvidenceを保持
- [x] 同一Slice再FinalizeはQuota delta 0
- [x] 別Sliceが既にAccounting済みなら新しいAccountingを停止
- [x] Orchestratorは`STATE/current.yaml`を直接編集しない

## P0 — Evidence Admission authority

- [x] Orchestrator自身をVerifierにしない
- [x] `validated=true`欠落/falseではFinalize成功不可
- [x] `validated=true`をWorker自己申告ではなくAdmission AuthorityのTrusted Inputとして定義
- [x] Raw Evidence保存とSuccess Admissionを分離
- [x] Human Gate / Verifier authorityをOrchestratorへ移譲しない

## Regression suite

CIの`python -m unittest discover -s Tests/ExternalProviders -p "test_*.py" -v`で以下をまとめて実行します。

- Ix Adapter
- Continuation Controller
- Layered Memory Controller
- Safe Index actual-file-access isolation
- Execution Orchestrator transitions
- Stale Ticket / Source Evidence regressions
- Fail-closed State Guard
- Profile / portable_import boundary
- Recomputed-digest Ticket semantic validation
- Execution Ticket JSON Schema examples

## Static validation

CIで以下を実行します。

```text
python -m compileall -q Tools Tests
YAML syntax validation
Draft 2020-12 JSON Schema validation
ExecutionPolicyValidator
Unit Tests
.gitignore runtime-state assertions
required-contract-file assertions
```

## Merge blockers

PR #8は以下がすべて成立するまでMergeしません。

- [ ] GitHub Actionsが**実際にJobを開始**し、最新HEADで全Gate PASS
- [ ] GitHub Billing / Spending limit問題が解消
- [ ] Runtime Result Schemaを`execution-orchestration-result.schema.yaml`へ一本化し、旧重複Envelope Schemaを整理
- [ ] PR最新HEADがSelf-review後に動いていないことを確認
- [ ] Mergeabilityを再確認
- [ ] 未解決Review Threadが0

現状Actionsのfailure表示はRepository code failureではなく、Billing / Spending limitによりJobが開始されない既知の外部Blockerです。

## Not a security sandbox

このControl Planeは事故・順序ドリフト・Context leakを防ぐFail-closed execution contractです。

同一OS権限を持つ悪意あるProcessからSecretを防御するSandboxやOS-level MACではありません。Ticket digestも認証Secretではありません。

必要なSecurity BoundaryはProfile、Source Path禁止、Safe Index、Secret Capture Guard、Human Gate、Repository/OS権限で多層化します。
