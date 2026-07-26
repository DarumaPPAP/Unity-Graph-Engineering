# Loop Budget

## Default Limits

| Limit | Value |
|---|---:|
| Parallel workers | 4 |
| Implementation attempts per node | 3 |
| Identical failure repetitions | 2 |
| Verifier retries | 1 |
| Auto-created PRs per run | 1 |
| Auto-merge | 0 |

## Time and Context Budget

- Context acquisition must stop when the Goal Contract can be evaluated.
- Do not scan the entire Repository when scoped search answers the question.
- Large logs are summarized with exact error excerpts and source paths.
- Each Worker receives only the context needed for its owned artifacts.
- A Worker may request more context, but must state which decision depends on it.

## Attempt Budget

An attempt counts when source files or project assets are changed and verification is run.

Stop immediately when:

- the same failure signature appears twice without a changed hypothesis
- the requested outcome cannot be measured
- required device, license, package, asset, or credential is unavailable
- a denylisted path must change without human approval
- the fix requires changing the Goal Contract

## Parallelism Budget

Parallelize only work that does not consume another Worker's output and does not write the same artifact.

Good candidates:

- Unity official API research
- Repository convention inspection
- independent visual reference analysis
- independent performance evidence review

Keep sequential:

- Shader interface design followed by dependent HLSL implementation
- Scene generation followed by visual correction
- Root cause hypothesis followed by targeted fix
- ProjectSettings change followed by build verification

## Escalation

Use `ESCALATE_HUMAN` when limits are reached. Include:

- attempts made
- evidence collected
- rejected hypotheses
- remaining uncertainty
- smallest decision needed from the user
