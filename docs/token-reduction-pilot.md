# Unity AI Token Reduction Pilot

## Goal

品質と依存解決率を維持したまま、Accepted Taskあたりの総Tokenを削減できるか検証する。

## Target KPI

```yaml
minimum:
  accepted_task_token_reduction: 20
  framework_token_reduction: 45
  verifier_approval_regression: 0
  missed_dependency_regression: 0

target:
  accepted_task_token_reduction: 30
  framework_token_reduction: 50
  context_file_read_reduction: 30

stretch:
  accepted_task_token_reduction: 40
  cross_cutting_research_reduction: 60
```

単位はPercent。公開事例の最大値をUnity全体の目標にはしない。

## Scenarios

同じ入力、Repository revision、利用可能Tool、Acceptance Criteriaで旧方式と新方式を比較する。

1. 単一C#コンパイル修正
2. Shaderコンパイル修正
3. RenderGraph Incident
4. RendererFeatureとShaderの横断変更
5. TAA品質改善
6. CPU / GPU最適化
7. Scene生成

## Variants

### Baseline

- 現行AGENTS / Skill routing
- 現行Context読込
- 現行Loop / State

### Candidate

- Prompt既定
- Context Pack
- Mode escalation確認
- Graph / Loop Budget
- Typed State / Evidence
- Knowledge Graphは該当Scenarioだけ

## Metrics

`schemas/execution-metrics.schema.yaml`を使用する。

主要指標:

- Framework Token
- Retrieved Context Token
- Source Token
- Output Token
- Accepted Task Token
- File Read
- Tool Call
- Attempt
- Mode Escalation
- Human Override
- Verifier Verdict
- Missed Dependency

ProviderのUsage Eventを優先する。Tokenizer推定値は`measurement_source: tokenizer_estimate`として区別する。

## Comparison rules

- Cache条件を揃える。
- BaselineとCandidateで同じSource revisionを使う。
- CandidateだけAcceptanceを弱めない。
- 未実施検証をAPPROVEとして数えない。
- 失敗Runを除外せず、Goal単位の累積Tokenへ含める。
- Graph構築やContext Pack作成の導入費用は別Ledgerで管理する。

## Knowledge Graph pilot

FakeUnity7の次だけを対象にする。

- `Assets/Settings/RendererFeature/`
- `Assets/Rendering/`
- `Assets/Shaders/`
- `Packages/manifest.json`
- `ProjectSettings/GraphicsSettings.asset`
- `ProjectSettings/QualitySettings.asset`

初期対象は200ファイル以下。Knowledge Graphは候補Artifact選定にだけ使用し、最終判断前にSourceを直接読む。

## Adoption decision

採用:

- Accepted Task Tokenが20%以上削減
- Verifier Approvalと依存解決率が悪化しない
- Silent Mode Switchが0
- 無制限Retryが0

再設計:

- 削減20%未満
- Prompt継続によるMissed Escalation増加
- Context Packによる重要依存漏れ
- Graph / Loopの管理Tokenが削減分を上回る

## Rollout

1. 文書重複削減
2. Prompt既定Router
3. Context Pack
4. Graph / Loop BudgetとState
5. Knowledge Graph Pilot
6. A/B評価
7. 採用範囲の拡大
