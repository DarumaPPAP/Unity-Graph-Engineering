# KNOWLEDGE.md

長期的に再利用でき、SourceとContextを持つFactだけを保存する。

## Fact Template

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
  commit: ""
observed_at: ISO-8601
confidence: verified | probable | unverified
supersedes: []
```

## Verified Facts

- 

## Probable Facts

- 

## Conflicts / Superseded

- 
