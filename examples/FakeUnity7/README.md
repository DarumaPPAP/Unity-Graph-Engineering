# FakeUnity7 Example

FakeUnity7 is the first target repository for dogfooding Unity Graph Engineering.

The goal is not to install a graph Editor tool. The goal is to make an AI agent operate FakeUnity7 through:

```text
Goal Contract
→ Task Graph
→ Bounded Implementation Loop
→ Independent Unity / Visual Verification
→ Human Merge Gate
→ State and Knowledge Write-back
```

## Files

- `PROJECT_CONTEXT.md` — known project facts and required unknowns
- `l1-repository-intake.yaml` — first report-only run

## Recommended Order

1. Copy the project context and state templates into FakeUnity7.
2. Run the L1 repository intake without source changes.
3. Fill actual compile, test, capture, and build commands.
4. Select one bounded L2 Unity task.
5. Use separate Maker, Unity Verifier, and Visual Verifier roles.
6. Stop before merge and request human approval.
7. Record the run and update reusable knowledge.

See `docs/fakeunity7-pilot.md`.
