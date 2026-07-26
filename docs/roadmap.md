# Roadmap

## Phase 0 — Direction Correction

- [x] Clarify that the product is AI-side Unity production control
- [x] Separate Task Graph from per-node Loop
- [x] Define Maker / Checker and Human Gate
- [x] Add durable STATE, run log, budget, and gate policy
- [x] Demote Artifact Scanner from Core Product to optional context experiment

## Phase 1 — L1 Report Ready

- [x] Goal Contract Schema
- [x] Task Graph Schema
- [x] Run State Schema
- [x] Verification Evidence Schema
- [x] Knowledge Write-back Schema
- [x] Unity Project Context template
- [x] Workflow Registry for feature, rendering bug, shader, scene, and optimization
- [x] Codex verifier starter
- [ ] Validate all YAML/JSON files in CI
- [ ] Add Loop Readiness audit specific to Unity production

## Phase 2 — FakeUnity7 Dogfood

- [ ] Remove the Artifact Scanner package from FakeUnity7
- [ ] Add PROJECT_CONTEXT.md, AGENTS.md, LOOP.md, STATE.md, and KNOWLEDGE.md
- [ ] Run one L1 report-only repository intake
- [ ] Run one L2 assisted Unity feature task
- [ ] Use separate compile and visual verifiers
- [ ] Record attempts and evidence in the run log
- [ ] Review whether the Workflow had fake edges or missing gates

## Phase 3 — Executable Verification

- [ ] Standardize Unity batchmode compile/test commands
- [ ] Add EditMode / PlayMode result parser
- [ ] Add log artifact capture
- [ ] Add screenshot/camera capture contract
- [ ] Add performance baseline/result contract
- [ ] Produce machine-readable verifier verdicts

## Phase 4 — Agent Harness Integration

- [ ] Codex starter with isolated worktree guidance
- [ ] Claude Code starter
- [ ] Cursor / generic skills.sh starter
- [ ] Connector permission profiles
- [ ] Worktree ownership and cleanup policy
- [ ] Kill switch and daily budget enforcement

## Phase 5 — Knowledge and Retrieval

- [ ] Store Bug → Cause → Fix → Verification facts
- [ ] Attach UnityVersion, Platform, Pipeline, PackageVersion, Source, and time
- [ ] Preserve conflicts and superseded facts
- [ ] Retrieve scoped facts at run start
- [ ] Evaluate whether Graph retrieval beats repository search for multi-hop Unity questions

## Phase 6 — L2 Reliability

- [ ] Complete at least 10 real Unity runs
- [ ] Measure success, rejection, escalation, and regression rates
- [ ] Tune maximum attempts and worker count from observed data
- [ ] Define safe low-risk action allowlist
- [ ] Keep auto-merge disabled until verifier precision is demonstrated

## Phase 7 — Optional Supporting Tools

Only after the AI production loop is proven:

- Artifact dependency extraction
- C# call and assembly graph
- Shader Pass / LightMode / RenderGraph resource context
- Impact query for planning and verification selection
- Visualization for debugging the workflow itself

Supporting tools must earn their maintenance cost and must not become the project goal.
