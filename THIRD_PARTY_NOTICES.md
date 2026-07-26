# Third-Party References

本リポジトリは、以下の公開Repositoryを設計上の参考資料として利用する。Sourceをそのまま複製するのではなく、Unity AI制作向けに独自のWorkflow、Schema、Skillとして再構成している。

## cobusgreyling/loop-engineering

- Reference: Loop、State、Budget、Run Log、Maker/Checker、Human Handoff、Readiness Level
- License: MIT
- Adopted ideas:
  - AgentをPromptする単発操作ではなくLoopを設計する
  - `LOOP.md`と`STATE.md`を会話外のDurable Spineにする
  - 実装者とVerifierを分離する
  - Report-onlyからAssisted、Unattendedへ段階的に上げる
  - 最大Attempt、Budget、Kill/Stop条件を明示する

本RepositoryのUnity WorkflowとCodex Agent定義は独自に記述している。

## codejunkie99/graph-engineering

- Reference: Task Graph、Fake Edge、Diamond Pattern、Stop Rule、Human Gate、Knowledge provenance
- License: MIT
- Adopted ideas:
  - NodeはJob、EdgeはOutput依存
  - 独立作業だけをFan-outする
  - Separate Verifier Context
  - One Writer per Artifact
  - Merge Ownerを1人に固定する

Knowledge Graph教材の原文や資料は再配布しない。

## Unity-Technologies/skills

- Reference: Skill Directory、`SKILL.md` frontmatter、具体的なTrigger、Skill間Delegation、Reference分離
- Public Repository
- Adopted ideas:
  - `skills/<name>/SKILL.md`をEntry Pointにする
  - Descriptionを`Use when ...`で具体化する
  - Orchestratorが個別SkillのCommandや知識を重複して再記述しない
  - 長い説明を`references/`へ分離する

Unity内部情報、Credential、非公開Workflowは含めない。

## Unity-Technologies/UnityCsReference

Unity C# Reference SourceはUnity Reference Only Licenseで提供される。Unity APIの存在、Editor/Runtime境界、挙動を確認するためだけに使用し、Sourceを転載・改変・再配布しない。

## Unity-Technologies/ml-agents

初期Artifact Scanner PackageでUPM構造、Editor/Runtime Assembly、Documentation、Samples、Tests構成を参考にした。ML-AgentsをLLM Agent Orchestratorとして使用するものではない。
