# Unity Verification Evidence

Verifierは「良さそう」ではなく、Acceptance Criterionに対応するEvidenceを返す。

## Common Evidence

| Change | Required evidence |
|---|---|
| C# Runtime | Unity compile、EditMode/PlayMode Test、Runtime/Editor境界 |
| Editor Tool | Unity compile、EditMode Test、対象操作の再現 |
| Shader/HLSL | Shader compile、Pass/Keyword、同一Camera capture、対象Platform |
| RendererFeature | Pass timing、Resource read/write、Frame DebuggerまたはCapture |
| Scene/Lighting | Missing reference、Camera capture、設定Asset、Visual Contract |
| Optimization | 同条件Baseline/Result、CPU/GPU/Memory、画質・機能回帰 |
| Package change | Package resolve、lock file、compile/test、Human Gate |

## Verdict Format

```yaml
verdict: APPROVE | REJECT | ESCALATE_HUMAN
criteria:
  - name: criterion
    status: pass | fail | not_run
    evidence:
      - command: ""
        result: ""
        artifact: ""
risks: []
unverified: []
```

## Compile

記録するもの:

- Unity version
- exact command or Editor operation
- exit code
- error count
- warning count relevant to the change
- log path

Compileが通ってもRuntime behaviorはAPPROVEしない。

## Visual

Visual changeは同じ条件で比較する。

- Scene
- Camera
- Resolution
- Render Pipeline Asset
- Quality Level
- Platform
- Time / animation frame
- before / after capture

Visual verifierはComposition、Lighting、Material、Temporal stability、ArtifactをCriterionごとに判定する。

## Rendering

可能な範囲で記録する。

- RenderPassEvent
- ShaderTagId / LightMode
- RenderQueue
- LayerMask
- SortingCriteria
- Color / Depth / MotionVector / GBuffer read-write
- Active keywords and variants
- Frame Debugger event or RenderDoc marker

## Performance

BaselineとResultは同じ条件で測る。

```yaml
capture:
  platform: ""
  scene: ""
  camera: ""
  resolution: ""
  quality: ""
  frame_range: ""
baseline:
  cpu_ms: null
  gpu_ms: null
  memory_mb: null
result:
  cpu_ms: null
  gpu_ms: null
  memory_mb: null
```

誤差範囲の改善はAPPROVEしない。画質や機能を落とした場合はGoal Contract内のTrade-offと一致する必要がある。

## Not Run

実行できなかった検証は`not_run`として残し、理由を明記する。未実施を推測でPassへ変換しない。
