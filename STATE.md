# STATE.md

## Project

- Name: Unity Graph Engineering
- Purpose: AI-side operating model for Unity production
- Readiness: L1 Report / L2 Assisted
- Last updated: 2026-07-26

## Current Direction

Unity Editor内へGraph Engineering製品を作るのではなく、AIがUnity Repositoryを制作・修正するときのTask Graph、Loop、Verifier、State、Human Gateを提供する。

## Active Work

### Framework Rebuild

- Status: in_progress
- Goal: Loop Engineering、Graph Engineering、Unity Skillsを統合したAI制作Frameworkへ再構成
- Owner: merge-owner
- Human gate: PR merge
- Evidence required:
  - Skill triggerがUnity制作依頼を明確に対象とする
  - WorkflowがTask GraphとLoopを機械可読に表現する
  - VerifierがMakerと分離される
  - FakeUnity7がTool検証先ではなく制作Pilot対象になる

## Completed

- Initial Task Graph / Artifact Graph investigation
- Artifact Scanner prototype 0.2.1
- Misinterpretation identified: Unity Editor Tool was treated as the product

## Decisions

- Task Graph is the outer execution topology
- Loop is the bounded internal cycle of each actionable node
- State lives outside chat
- Implementer cannot approve its own work
- Auto-merge remains disabled
- Artifact dependency scanning is optional context, not the core product

## Known Risks

- Workflow documents can become ceremonial unless dogfooded on a real Unity task
- Verification may remain self-reported without executable commands and captured evidence
- Too many specialized agents can increase coordination cost
- Visual quality cannot be approved by compile tests alone

## Next Actions

1. Merge the framework rebuild after review
2. Apply templates to FakeUnity7
3. Run one real Unity feature or rendering task end-to-end
4. Record the first run in `loop-run-log.md`
5. Adjust schemas and stop rules from observed failures

## Human Overrides

- 2026-07-26: User clarified that Graph Engineering must govern AI Unity production, not become a Unity Editor graph product
