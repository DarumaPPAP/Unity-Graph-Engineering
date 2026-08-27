# UnityAgent Compatibility Boundary

Unity-Graph-EngineeringはUnity固有Policy、Task Fingerprint、Context Selection、Context Budget、Harness、Golden Behaviorを再定義しません。これらは`DarumaPPAP/UnityAgent`が正本です。

## Handoff v2

UnityAgentからExecution Ownerへ渡すHandoffは`2.0`です。

```text
UnityAgent Task Fingerprint
+ Context Manifest v3.1
+ Context Budget decision
+ Task Contract / Risk / Mutation / Quality Gates
        ↓
UnityAgent Handoff v2
        ↓
Tools/UnityAgentCompatibility/handoff_adapter.py
        ↓
Execution State
```

Execution側はPrimary RouteやContext Budgetを再計算しません。

Mutationは`context_budget_decision.decision == within_budget`の場合だけ許可されます。`compression_required`、`blocked`、`unmeasured`はRead-only分析で保持できますがMutationを開始できません。

## Actual Behavior Eval

UnityAgentがBehavior TruthとGraderを所有し、Unity-Graph-EngineeringがProduction Execution Evidenceを返します。

```text
UnityAgent run_behavior_eval.py
        ↓ external command
Tools/BehaviorEvalAdapter/behavior_eval_adapter.py
        ↓ shell=False / sandbox
Production Agent command
        ↓
response.md
context-manifest.yaml
artifact-index.yaml
optional diff / gate evidence / metrics
        ↓
execution-envelope.yaml
        ↓
UnityAgent Normalizer / Golden Runner
```

### Adapter invocation

UnityAgent Runnerからは通常、次のようなbase commandとして利用します。

```text
python Tools/BehaviorEvalAdapter/behavior_eval_adapter.py \
  --unityagent-root <UnityAgent checkout> \
  --agent-command-json '["<production-agent-command>", "<arg>"]'
```

UnityAgent Runnerが末尾へ`--request <path> --output <case-dir>`を追加します。

Production Agent commandはAdapterから次を受け取ります。

```text
--request <temporary production-request.json>
--output <temporary evidence directory>
```

最低限のEvidence:

- `response.md`
- `context-manifest.yaml`
- `artifact-index.yaml`

任意:

- `diff.patch`
- `gate-evidence.yaml`
- `metrics.json`
- `generated/`
- `execution-metadata.yaml`

Provider認証、Model selection、Retry PolicyはBehavior Eval Requestに含めません。

## Vocabulary

Production Execution vocabularyへ統一します。

```text
Behavior mode prompt      -> prompt
Behavior mode graph_loop  -> graph_loop

work_kind implementation  -> mutation
work_kind mutation        -> mutation
work_kind analysis        -> analysis
work_kind verification    -> verification
work_kind portable_import -> portable_import
```

Legacy `graph` aliasを黙って`graph_loop`へ変換しません。Contract driftとして失敗させます。

## Validation

Local:

```text
python Tools/UnityAgentCompatibility/validate_local_compatibility.py
python -m unittest discover -s Tests/UnityAgentCompatibility -p "test_*.py" -v
python -m unittest discover -s Tests/BehaviorEvalAdapter -p "test_*.py" -v
```

Cross-repository:

```text
python Tools/UnityAgentCompatibility/validate_against_unityagent.py \
  --unityagent-root <UnityAgent checkout>
```

`.github/workflows/validate-unityagent-compatibility.yml`はUnityAgent `main`とのdriftを定期検証します。

## Merge order

Handoff contractを同時変更する場合は、ProducerであるUnityAgent側のHandoff v2変更を先に統合し、その後Unity-Graph-Engineering側を統合します。Cross-repository scheduled validationは両Repositoryの`main`が同じContract versionへ到達した時点でGreenになります。
