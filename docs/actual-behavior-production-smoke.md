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

## Codex CLI Production Agent

`Tools/CodexProductionAgent/codex_production_agent.py` adapts the local Codex CLI to the Production Agent command contract. It does not edit the real UnityAgent checkout. For every case it receives the temporary fixture workspace created by `BehaviorEvalAdapter`, copies only runtime control sources (`AGENTS.md`, `.ai` excluding `.ai/eval`, `.agents`, and `SkillReferences`) into a reserved `.unityagent-control` snapshot, and runs Codex against that temporary workspace.

The bridge uses:

- one `codex exec` turn
- `--ephemeral`
- `--json`
- `--sandbox workspace-write`
- an explicit model identity
- a structured output schema for response/context/gate evidence
- post-run mutation-scope verification
- a protected hash for `.unityagent-control`

MCP is disabled for Phase 1 by default with a per-run config override. This keeps the smoke independent from Unity Editor/MyUnityMCP availability and avoids an unrelated MCP startup failure changing the result. Use `--keep-mcp` only when a later evaluation explicitly requires MCP.

The bridge resolves the model in this order:

1. `--model`
2. `CODEX_PRODUCTION_MODEL`
3. the top-level `model` in `%USERPROFILE%\.codex\config.toml`

The provider defaults to `openai`, or uses `CODEX_PRODUCTION_PROVIDER` / top-level `model_provider` when configured.

### Windows local run

Expected local checkouts:

```text
D:\UnityAgent
D:\Unity-Graph-Engineering
```

From PowerShell:

```powershell
cd D:\Unity-Graph-Engineering
python .\Tools\CodexProductionAgent\run_codex_production_smoke.py `
  --unityagent-root D:\UnityAgent
```

If the Codex config already contains `model = "..."`, no model argument is required. To pin one explicitly:

```powershell
python .\Tools\CodexProductionAgent\run_codex_production_smoke.py `
  --unityagent-root D:\UnityAgent `
  --model gpt-5.6-luna
```

The wrapper converts this into the existing generic launcher contract; users do not need to hand-write `UNITYAGENT_PRODUCTION_COMMAND_JSON`.

The real `D:\UnityAgent` checkout is used only as the source for the read-only control snapshot. Task mutations occur in the temporary Behavior Eval workspace. The bridge fails closed if an analysis/verification case mutates files, if a mutation escapes `allowed_paths`, if a prohibited path changes, or if Codex modifies `.unityagent-control`.

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

For the Codex bridge, the expected identity is `agent_id: codex-cli`, with the configured provider and explicitly resolved model.

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
- Codex control snapshot is hash-checked after execution
- `.ai/eval` is not copied into the Codex control snapshot

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
