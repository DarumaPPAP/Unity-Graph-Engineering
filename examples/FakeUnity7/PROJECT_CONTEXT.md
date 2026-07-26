# PROJECT_CONTEXT.md — FakeUnity7 Example

## Project Identity

- Repository: `DarumaPPAP/FakeUnity7`
- Unity version: `6000.7.0a2`
- Render Pipeline: URP
- URP package: `17.7.0`
- Purpose: Unity Preview技術、Rendering、AI制作Workflowの検証Project
- Priority: high-end visual experiments and Unity production validation

## Known Packages

- `com.unity.render-pipelines.universal`: `17.7.0`
- `com.unity.test-framework`: `1.8.0`
- `com.unity.ai.assistant`: `2.16.0-pre.1`
- `com.unity.ai.inference`: `2.6.1`

Package listはRun開始時に`Packages/manifest.json`から再確認する。

## Coding Constraints

- Runtimeから`UnityEditor`を参照しない
- Editor専用APIはEditor FolderまたはEditor-only Assemblyへ隔離
- asmdefは必要な境界がある場合のみ
- private Fieldは`_camelCase`
- Enumは`E_`、Structは`S_`
- MonoBehaviourは1ファイル1型
- 不要なController、Setup、自動探索、static状態を追加しない
- ProjectSettingsやURP Assetを暗黙変更しない

## Verification Seed

Run開始時に確定する項目:

- BatchMode compile command
- EditMode / PlayMode test command
- Validation Scene and Camera
- Screenshot output path
- Profiler capture conditions
- Target platform for the specific task

## Human Gates

- PR merge
- Package changes
- ProjectSettings changes
- Scene replacement
- Asset deletion
- Render Pipeline Asset replacement

## Known Risks

- Preview Unity/URP API can change
- Visual tasks require fixed-camera evidence
- Editor success does not prove device/platform success
- Existing project contains multiple experimental systems; write scope must remain explicit
