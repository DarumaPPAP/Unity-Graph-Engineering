# Execution Budget Compatibility Guide

Budgetの機械可読正本は次です。

- Prompt Engineering: `policies/prompt-budget.yaml`
- Graph / Loop Engineering: `policies/graph-loop-budget.yaml`
- Mode変更判定: `policies/mode-escalation.yaml`

このFileへ数値を重複定義しません。

## Prompt

- 一つのPrimary Skill
- 一つのWriter
- 最大3 Primary Artifact
- 最大2 Hypothesis
- 最大2 Mutation Attempt
- Context拡張は1 Hop
- 上限超過前にGraph / Loop変更確認

## Graph / Loop

- 最大3 Parallel Node
- Nodeあたり最大2 Attempt
- 同一Failureの無仮説反復は禁止
- Graph Replanは最大1回
- Verifier Retryは最大1回
- 新しいNode開始前に残Budgetを確認

## Accounting

次をRunとNodeの両方で記録します。

- input / output / cached tokens
- tool calls
- file reads
- attempts
- wall clock
- external side effects

正確なProvider Token Usageを取得できない場合は推定値と明記し、実測値と混同しません。

## Stop

Budget上限、観測不能なAcceptance、必要なDevice・Asset・Credential不足、Goal Contract変更、未承認Human Gateでは停止します。停止時はEvidence、棄却仮説、残Budget、最小の人間判断を保存します。
