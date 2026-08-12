# Execution Control Plane Threat Model

## Security objective

Unity-Graph-EngineeringのControl Planeは、AI実行で起きやすい**事故・権限境界逸脱・State競合・Context leak**をFail Closed contractで減らします。

OS-level Sandboxや悪意ある同一権限Processへの完全防御は目的に含めません。

## Protected assets

- User Policy / Human Gate authority
- Company / Team SafeのProject内部情報
- Project Source
- Raw Evidence
- Authoritative Execution State
- Quota / Accounting
- Selected Todo / Claim / Lease
- Source Mutation scope
- UnityAgent Knowledge promotion boundary

## Threats and mitigations

### T1 — Gate bypass by omitted State fields

**Threat:** `human_gate`や`budget.remaining`をStateから削除し、Controllerのdefaultへ落として実行する。

**Mitigation:** Execution Orchestrator入口でSafety-relevant fieldを必須化。欠落は`incomplete_control_state`。

### T2 — Controller-order drift

**Threat:** Ix/Memoryを先に呼び、Human Gate待ちでもProject/Memoryへ触れる。

**Mitigation:** `State Guard → Continuation → Claim → Memory → Ix → Verification → Ticket`をCanonical Orderとして固定。

### T3 — Team Safe Project Source leak

**Threat:** `scope_class=portable_artifact`を付けてCompany Project Pathを渡す。

**Mitigation:** Non-personal ProfileではLocal Source Pathを内容に関係なく禁止。Team Safeは一般`mutation`も禁止し`portable_import`へ分離。

### T4 — Memory read leak

**Threat:** Team Safe RetrievalがPersonal Runで保存された`project_internal` Memory fileを一度読んでからFilterする。

**Mitigation:** Non-personal Retrievalは`safe-index.jsonl`だけを入口にし、Indexへ存在しないRecord fileを開かない。`project_internal`はIndexへ登録しない。

### T5 — Legacy Memory ambiguity

**Threat:** Scope fieldを持たない旧Memoryをsafe扱いする。

**Mitigation:** Unindexed/Legacy Recordは`project_internal`相当としてFail Closed。Non-personalでは開かない。

### T6 — Secret copied into Raw Evidence

**Threat:** Tool outputやLogへCredential/Private Keyが含まれ、そのままMemory化される。

**Mitigation:** explicit `sensitivity=secret`拒否 + high-confidence Credential pattern guard。Raw EvidenceはRuntime directoryでGit ignore。

### T7 — Command injection

**Threat:** Symbol/targetからShell metacharacterを注入する。

**Mitigation:** Ix Adapterはoperation whitelist、target validation、`shell=False`。Orchestrator child processも固定Python path + `shell=False`。

### T8 — Destructive Ix operation

**Threat:** `ix reset`等をExecution Graphから呼ぶ。

**Mitigation:** Safe Adapter surfaceに destructive commandを公開しない。

### T9 — Concurrent worker duplicate execution

**Threat:** 複数Workerが同じTodoを同時に実行する。

**Mitigation:** Claim/Lease ProjectionをAuthoritative Stateへdurable writebackするまでOrchestratorがNavigation/Ticket発行へ進まない。

### T10 — Stale Ticket accounting

**Threat:** Human/別WorkerがStateを更新した後、古いTicketで成功Accountingする。

**Mitigation:** TicketへAuthoritative State SHA-256 fingerprintをbind。Finalizeで差分があればEvidenceのみ保全しQuota/State Accountingを拒否。

### T11 — Ticket digest treated as authentication

**Threat:** CallerがTicketを改変しdigestを再計算して安全境界を変更する。

**Mitigation:** digest検査に加えFinalizeでProfile / Work Kind / Source semanticsを再検証。digest自体はAuthentication Secretではないと明示。

### T12 — Duplicate quota spend

**Threat:** Network/retryで同じFinalizeを再送しQuotaを二重消費する。

**Mitigation:** `previous_slice.slice_id + quota_spent + quota_spend_id`をAccounting Markerにし、同一Slice再送はdelta 0。

### T13 — Evidence lost on stale/accounting failure

**Threat:** 実測結果は得られたがState競合で失われ、次Runが同じ検証を繰り返す。

**Mitigation:** Raw Evidenceを先にdurable保存。その後Stale/Quotaを判定。失敗してもEvidenceは保持する。

### T14 — Worker self-approval

**Threat:** Makerが`validated=true`を自己申告し成功Accountingする。

**Mitigation:** `validated`はIndependent Verifier / deterministic validator / Human Gateを経たEvidence Admission AuthorityからのTrusted Inputとして定義。Orchestrator自身をVerifierにしない。

### T15 — Memory promotion changes User Policy

**Threat:** 過去会話の頻度や推論からUser Policyを自動更新する。

**Mitigation:** Layered Memory ControllerはPromotion Projectionだけ返し、外部Authorityへ直接Writeしない。User Policy CandidateはVerified + Human Gate。

## Out of scope

以下はControl Plane単体では防御しません。

- 同一OSユーザー権限を持つ悪意あるProcess
- Kernel / filesystem permission bypass
- GitHub credential compromise
- Unity Editor自体の任意Native Plugin挙動
- Humanが意図的にSecretを`public_reference`へ再分類する行為

必要ならOS Sandbox、ACL、Container、Credential isolation等を別レイヤーで適用します。

## Review rule

Profile / Ticket / Memory Scope / Evidence / State Accountingに新しい例外を追加する変更は、便利さだけを理由にMergeしません。

最低限:

1. Threat Model上の影響
2. Policy更新
3. Schema更新
4. Positive Test
5. Negative / bypass Test
6. Recovery semantics

を同じPRで要求します。
