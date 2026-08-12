# Orchestrator Evidence Admission Boundary

Execution OrchestratorはVerifierではありません。

`slice_result.validated=true`はWorkerが自分で付ける成功フラグではなく、**Orchestratorより上流のEvidence Admission Authorityが確定したTrusted Input**として扱います。

## Authority separation

```text
Worker / Maker
   ↓ produces result + raw evidence
Deterministic Validator / Independent Verifier / Human Gate
   ↓ admission decision
Evidence Admission Authority
   ↓ validated=true only when admitted
Execution Orchestrator.finalize
   ↓ preserve L0 evidence
   ↓ quota spend projection
STATE writeback
```

Orchestratorは次を行いません。

- Workerの自己申告だけでEvidenceをAPPROVEする
- Compile/Test/Visual/Performanceの意味を自分で判定する
- Human Gateを代行する
- MakerとVerifierを同一Contextへ統合する

## Required semantics

`validated=true`を設定できるのは、Task Contractが要求するEvidence Gateを満たしたAdmission経路だけです。

例:

- deterministic compile/test validatorがPASS
- independent Verifierが`APPROVE`
- visual/performance gateで要求された実測EvidenceがAdmission済み
- Human Gate対象なら明示承認済み

`validated`が欠落または`false`の場合、OrchestratorはFinalizeを拒否しQuota Spendへ進みません。

## Raw evidence versus admitted evidence

Raw Evidenceの保存と、成功AccountingへのAdmissionは別です。

```text
Raw Evidence
  = 実際に観測したArtifactを失わないための保存

Admitted Evidence
  = Acceptance Criteria / Evidence Policyを満たしたと外部Authorityが判定したEvidence
```

Stale StateやQuota Accounting failureの場合でもRaw Evidenceは保持できますが、それだけでGoal成功やQuota Spendを意味しません。

## Trust boundary

Execution TicketのSHA-256 digestも、`validated=true`も暗号学的な外部認証Tokenではありません。

このControl Planeはローカル実行契約を壊れにくくするためのもので、悪意ある同一権限ProcessからState/Ticketを防御するSecurity Sandboxではありません。

そのため:

- TicketはFinalizeでSemantic Validationを再実施する
- `validated=true`はEvidence Admission Authorityからのみ受け取る
- Project Secret / Team Safe境界はProfile/Path/Memory/Ixの実装Gateで別途Fail Closedにする

## Admission failure

| State | L0 Evidence | Quota Spend | Goal success |
|---|---:|---:|---:|
| `validated=false` | 任意で保存可能 | No | No |
| Verifier `REJECT` | Keep | No | No |
| `ESCALATE_HUMAN` | Keep | No | No |
| Validator unavailable | Keep if safe | No | No |
| `APPROVE` + all required gates | Keep | Eligible | Acceptance Criteria次第 |

`validated=true`そのものをGoal completionと同一視しないことも重要です。
