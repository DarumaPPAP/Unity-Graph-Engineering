# Loop Run Log

Append one entry per completed or escalated run. Do not rewrite old verdicts; add corrections as new entries.

## Entry Template

```yaml
run_id: YYYYMMDD-HHMM-short-name
started_at: ISO-8601
finished_at: ISO-8601
repository: owner/name
workflow: workflows/example.yaml
goal: one sentence
status: approved | rejected | escalated | cancelled
task_graph:
  - id: node-id
    status: pending | running | approved | rejected | skipped
    attempts: 0
changed_artifacts: []
verification:
  verdict: APPROVE | REJECT | ESCALATE_HUMAN
  evidence: []
failed_attempts: []
human_gate:
  required: true
  reason: merge
state_updates: []
knowledge_updates: []
```

## Runs

No production Unity run has been completed with the rebuilt framework yet.
