# FakeUnity7 Pilot

FakeUnity7はUnity Graph EngineeringのEditor Tool検証先ではなく、**AI制作Workflowの対象Repository**として使う。

## Pilot Goal

最初のPilotは、実装品質よりもFrameworkの制御品質を検証する。

確認するもの:

- Goal Contractが曖昧さを減らしたか
- Task GraphにFake Edgeがないか
- Writer ownershipが守られたか
- Loopが上限内で停止したか
- VerifierがMakerと独立していたか
- EvidenceからVerdictを再現できるか
- STATEが次Sessionで役に立つか

## Phase A — Repository Intake（L1 Report）

Sourceを変更せず、次を確定する。

1. Unity / URP / Package version
2. Runtime、Editor、Shader、Scene、ProjectSettingsの主要Path
3. Compile、EditMode、PlayMode、Build Command
4. Coding conventions
5. Protected paths and human gates
6. Current known risks

Output:

- `PROJECT_CONTEXT.md`
- `STATE.md`
- missing context list
- first recommended L2 task

## Phase B — First L2 Task

小さく、機械判定とVisual判定を両方含むUnityタスクを選ぶ。

推奨条件:

- 変更Artifact 3〜8個
- Package変更なし
- ProjectSettings変更なし
- Scene削除なし
- Compile可能
- Fixed CameraでBefore/After比較可能
- 3 Attempt以内で終わる見込み

候補:

- 既存Rendering Debug表示の改善
- Shaderの限定的なVisual品質改善
- Editor-only検証Toolの小規模追加
- 既存SceneのLightingまたはPost Processの局所改善

## Execution

```text
Goal Contract
  ↓
Repository + Unity API Context
  ↓
Task Plan with ownership
  ↓
Implementation Loop
  ↓
Unity Verifier + Visual Verifier
  ↓
Merge Owner
  ↓
Human Gate
  ↓
STATE / KNOWLEDGE / Run Log
```

## Required Evidence

- exact commit/branch
- Unity version
- changed files
- compile/test result
- before/after capture when visual
- verifier verdict
- unverified items
- human gate reason

## Review Questions

Pilot後に次へ回答する。

1. 不要なNodeはあったか
2. 本当は逐次だったのに並列化した作業はあったか
3. MakerとVerifierが同じ仮定を共有しすぎていないか
4. Acceptance Criterionが後付けになっていないか
5. 失敗したAttemptは次のAttemptへ情報を残したか
6. Human Gateは早すぎる・遅すぎる位置にないか
7. 次回のContext取得量を減らせるKnowledgeは何か
