# Changelog

## [0.2.1]

- Added committed Unity `.meta` files for every visible package asset so Git-based UPM installs import the Editor assemblies
- Added an EditMode regression test that fails when a visible package asset is missing its `.meta` file

## [0.2.0]

- Added reverse dependency impact query with configurable hop depth
- Added scan duration, counts, skipped dependency metrics, and diagnostics
- Added deterministic node and edge ordering
- Added EditMode tests for empty scans, dependency chains, stable serialization, impact traversal, and export path safety
- Added Shader Graph, Compute Shader, and HLSL-related artifact classification

## [0.1.0]

- Initial Unity Artifact Graph scanner
- JSON exporter with Unity version and provenance
- Editor window under `Tools/Graph Engineering/Artifact Graph`
