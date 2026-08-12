# Control Plane Examples

このDirectoryのJSONはControl Planeの**呼び出し形状を説明するExample**です。

`execution_state`の永続正本を置き換えるものではありません。

実運用の`STATE/current.yaml`は`schemas/execution-state.schema.yaml`を満たし、Task Contract / Goal / Quality Gate / Budget / Control Stateを保持します。

## Execution Orchestrator

### Personal mutation

`execution-orchestrator-personal-prepare.json`

- `personal_full_control`
- `work_kind=mutation`
- Local Source Pathあり
- Direct Source Read Evidence Refあり
- Optional Memory / Ixあり

### Team Safe portable import

`execution-orchestrator-team-safe-portable-import.json`

- `team_safe_import`
- `work_kind=portable_import`
- Local Source Pathなし
- Ixなし
- `portable_artifact` scope
- Evidence-only Verification

Team Safe ExampleへCompany ProjectのPath、Hierarchy、Screenshot、Git、Issue、Unity Project ID、組織/顧客情報等を追加しないでください。

## Ticket

`prepare`成功時のTicketは手書きしません。

必ずExecution Orchestratorが返したTicketをそのまま`finalize`へ渡します。

Ticketの型契約:

- `schemas/execution-ticket.schema.yaml`

## Finalize

Finalizeは次の順序を前提にします。

1. One bounded slice完了
2. Task Contractが要求するValidator / Verifier完了
3. Evidence Admission AuthorityがAdmission
4. `validated=true`を設定
5. `finalize`
6. Raw Evidence保存
7. Quota Spend Projection
8. `required_state_writeback`をAuthoritative Stateへdurable write

Worker自身が`validated=true`を自己決定する運用は禁止です。
