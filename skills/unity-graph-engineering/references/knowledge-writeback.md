# Unity Knowledge Write-back

Stateは現在進行中の作業、Knowledgeは次回も再利用できる技術Factを保存する。

## Stateへ書くもの

- current goal
- node status
- attempts
- current hypothesis
- last action
- pending verification
- human override
- next action

## Knowledgeへ書くもの

- reproduced bug and conditions
- confirmed cause
- accepted fix
- platform/version constraint
- stable project convention
- measured benchmark
- official source that resolved an ambiguity

一時的な進捗、未確認仮説、会話上の感想はKnowledgeへ入れない。

## Fact Contract

```yaml
id: stable-id
type: Bug | Cause | Fix | Constraint | Decision | Benchmark | Source
statement: ""
context:
  unity_version: ""
  render_pipeline: ""
  package_versions: {}
  platforms: []
source:
  kind: repository | test | profiler | screenshot | official_documentation | user_override
  location: ""
observed_at: ISO-8601
confidence: verified | probable | unverified
supersedes: []
```

## Relationship Examples

```text
(Bug)-[CAUSED_BY]->(Cause)
(Bug)-[FIXED_BY]->(Fix)
(Fix)-[VERIFIED_BY]->(Benchmark)
(Fix)-[VALID_ON]->(UnityVersion)
(Constraint)-[APPLIES_TO]->(Platform)
(Decision)-[SUPPORTED_BY]->(Source)
```

## Contradictions

新しいFactが既存Factと競合する場合、古いFactを消さない。

- sourceとtimeを保持する
- `supersedes`または`conflicts_with`を記録する
- Platform、UnityVersion、PackageVersion差を確認する
- 未解決なら両方を残してretrieval時に警告する

## Provenance

Repository SourceはPathとCommit、TestはCommandとResult、ProfilerはCapture条件、ScreenshotはScene/Camera/Resolutionを残す。

AIが生成した説明だけをSourceにしない。

## Retrieval

作業開始時はGoalに関連するFactだけを取得する。Knowledge全体をContextへ流し込まない。

優先順位:

1. same repository + same Unity version + same platform
2. same package/pipeline version
3. verified facts
4. newer observations
5. probable or cross-project facts
