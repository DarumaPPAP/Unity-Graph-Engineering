# Optional Unity Artifact Context

Artifact dependency information can help an AI plan Unity changes, but it is not the product and is not mandatory for every run.

## Use It When

- a change has multi-hop impact across Scene, Prefab, Material, Shader, or Package
- Writer ownership cannot be decided from scoped search
- a verifier needs a concrete impacted-asset list
- dynamic rendering or assembly relationships are being investigated

## Do Not Use It When

- a file search or direct reference lookup answers the question
- the graph would cost more to build than the change itself
- the available extractor cannot represent the relationship being relied on
- the user asked for AI production workflow rather than dependency tooling

## Possible Node Types

- Scene
- Prefab
- Material
- Shader / HLSL
- Script / Assembly
- RenderPipelineAsset / RendererData / RendererFeature
- Package / ProjectSetting

## Possible Relations

- `DEPENDS_ON`
- `REFERENCES`
- `USES_SHADER`
- `INCLUDES`
- `COMPILES_INTO`
- `CONFIGURES`
- `EXECUTES_BEFORE` / `EXECUTES_AFTER`
- `READS_RESOURCE` / `WRITES_RESOURCE`

## Evidence Boundary

`AssetDatabase.GetDependencies` only proves an AssetDatabase direct dependency. It does not prove:

- C# method calls
- semantic SerializedObject roles
- Shader Pass / LightMode execution
- RenderGraph resource flow
- Addressables semantics
- dynamic `Resources.Load`, `Shader.Find`, or string Scene load

Never treat an incomplete extractor as a complete project model. Attach the extraction method as evidence and keep unknown relationships explicit.

## Core Rule

Task Graph planning must work without the Artifact Scanner. Use dependency tooling as optional context only when it materially improves impact analysis or verification.
