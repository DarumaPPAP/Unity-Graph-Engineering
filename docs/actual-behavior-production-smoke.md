# Actual Behavior Production Smoke

Phase 1 connects UnityAgent Golden Tasks to a real Production Agent through Unity-Graph-Engineering.

## Goal

Run exactly one real Agent attempt for four representative behaviors:

- architecture
- type naming
- mutation scope
- evidence honesty

The Production Agent is external to this repository. Unity-Graph-Engineering owns invocation, sandboxing, timeout, evidence transport, and execution identity validation. UnityAgent owns the tasks, policy/context/harness contracts, normalization, and grading.

## Production Agent command contract

Set the command as a JSON argument array. Credentials must stay in the runtime environment and must not be embedded in Behavior Eval requests or evidence.

```bash
export UNITYAGENT_ROOT=/path/to/UnityAgent
export UNITYAGENT_PRODUCTION_COMMAND_JSON='["your-agent-command","behavior-eval"]'
python Tools/BehaviorEvalAdapter/run_production_smoke.py
```

The launcher always selects `production_smoke`, enables `--require-production-identity`, and keeps `max_agent_attempts=1`.

The Agent command receives:

```text
--request <production-request.json>
--output <temporary-evidence-directory>
```

The request contains only execution inputs, never Golden expectations:

```json
{
  "schema_version": "1.0",
  "task": {},
  "execution": {
    "mode": "prompt|graph_loop",
    "profile": "...",
    "work_kind": "...",
    "max_agent_attempts": 1
  },
  "workspace_root": "/temporary/sandbox",
  "mutation_scope": {
    "allowed_paths": [],
    "prohibited_paths": []
  },
  "evidence_contract": {
    "require": [],
    "optional": []
  },
  "evidence_output": "/temporary/evidence",
  "unityagent_revision": "...",
  "golden_task_id": "..."
}
```

`golden_task_id` is provenance only. The Golden expectation is never transferred to the Agent.

## Required evidence

Every attempt must emit:

- `response.md`
- `context-manifest.yaml`
- `artifact-index.yaml`
- `execution-metadata.yaml`

Cases may additionally require `diff.patch`. Optional evidence includes `gate-evidence.yaml`, `metrics.json`, and `generated/` artifacts.

For Phase 1 production execution, `execution-metadata.yaml` must include a real identity:

```yaml
status: completed
execution_class: production
agent_id: your-production-agent
provider: your-provider
model: your-model
model_revision: unavailable
infrastructure_attempts: 1
tool_manifest_hash: your-stable-tool-manifest-hash
```

`execution_class` must be `production`; provider, model, and agent_id may not be fixture/fake/unavailable identities.

## Integrity behavior

- one Agent attempt only
- sandbox workspace only
- mutation scope is transferred before execution and still graded from the resulting diff
- non-zero Agent exit is authoritative over self-reported `completed`
- timeout produces no partial published bundle
- stale output is rejected
- the repository fake Production Agent fixture is rejected by the production launcher
- no retry is performed to hide first-pass quality

## Result

UnityAgent writes the immutable run under `Artifacts/BehaviorEval/<run-id>/` and reports:

- Actual Behavior Pass Rate
- Actual First Pass Rate
- Routing / Context accuracy
- Policy / Mutation violation rate
- Evidence overclaim rate
- Naming / Architecture regression rate
- Artifact evidence coverage

Phase 1 remains manual and non-blocking. Promotion to a required PR gate belongs to a later phase after enough real-run evidence is collected.
