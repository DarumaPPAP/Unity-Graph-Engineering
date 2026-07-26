# LOOP.md — Unity AI Production Loops

このFileは、Unity制作でAIが使用するLoopとHuman Handoffを定義する。

## Readiness

- Current level: **L1 Report / L2 Assisted**
- Auto-merge: disabled
- Scheduled unattended execution: disabled
- Maximum implementation attempts per item: 3
- Maximum parallel workers: 4

## Active Loops

### Unity Feature Delivery

- Trigger: Runtime機能、Editor Tool、Pipeline設定などの実装依頼
- Workflow: `workflows/unity-feature-implementation.yaml`
- Mode: L2 Assisted
- State: target repository `STATE.md`
- Stop condition: Acceptance criteriaをVerifierが全項目APPROVE
- Escalation: 3回失敗、設計変更、Package/ProjectSettings変更

### Rendering Bug Investigation

- Trigger: Editor/実機差、黒化、描画順、MotionVector、Transparent、RendererFeatureなどの不具合
- Workflow: `workflows/rendering-bug-investigation.yaml`
- Mode: L2 Assisted
- State: symptom / reproduction / hypothesis / evidence / rejected hypotheses
- Stop condition: 再現可能なCauseとFixを独立Verifierが確認
- Escalation: 実機専用で再現Evidenceがない、Render Pipeline全体の変更が必要

### Shader Development

- Trigger: ShaderLab、HLSL、Shader Graph、RendererFeature連携の追加・修正
- Workflow: `workflows/shader-development.yaml`
- Mode: L2 Assisted
- Stop condition: Compile、対象Pass、見た目、Variant、性能Evidenceを確認
- Escalation: 見た目のAcceptanceが定義できない、Platform Shader Compilerでのみ失敗

### Scene Generation

- Trigger: AIによるScene、Lighting、Material、URP Asset、Project設定の生成
- Workflow: `workflows/scene-generation.yaml`
- Mode: L2 Assisted
- Stop condition: Sceneが開く、Missingなし、Visual Contract合格、必要設定が揃う
- Escalation: Reference不足、Asset license不明、ProjectSettings大規模変更

### Performance Optimization

- Trigger: CPU/GPU/Memory/Build Sizeの改善
- Workflow: `workflows/performance-optimization.yaml`
- Mode: L2 Assisted
- Stop condition: 同じCapture条件でBaselineより改善し、画質・機能回帰なし
- Escalation: Baselineがない、計測環境が変わった、改善が誤差範囲

## Loop Anatomy

全Loopは次の形を使う。

```text
Intake
  ↓
Baseline / Context
  ↓
Plan
  ↓
Implement Attempt
  ↓
Observe Evidence
  ↓
Independent Evaluate
  ├─ APPROVE → Merge Owner → Human Gate
  ├─ REJECT  → State更新 → 次のAttempt
  └─ ESCALATE_HUMAN → 停止
```

## Multi-loop Coordination

優先順位:

1. Compile / CI Failure
2. Rendering Regression
3. Feature Delivery
4. Performance Optimization
5. Scene Quality Improvement

同一Artifactを変更するLoopは同時に走らせない。別Loopが必要な場合でも、Writer ownershipを1つへ統合する。

## State and Memory

- 全Runは開始時に`STATE.md`を読む
- 終了時にOutcome、Evidence、Last action、Next actionを更新
- 完了項目はCurrent WorkからHistoryへ移す
- 人間のOverrideを必ず記録
- 長期知識は`KNOWLEDGE.md`または接続されたKnowledge Storeへ書く

## Safety

- `gate.yaml`のdenylistを常に適用
- Merge、Delete、Package、ProjectSettings、Scene大規模変更はHuman Gate
- Test失敗をRetryだけで隠さない
- 同じFailure Signatureが2回続いたら仮説を変更する
- 3回のAttemptで進展がなければ停止する

## Observability

各Run Reportに次を残す。

- started_at / finished_at
- selected workflow
- task graph nodes and status
- attempts per node
- files changed
- commands and tests executed
- verifier verdict
- escalations
- estimated remaining risk
