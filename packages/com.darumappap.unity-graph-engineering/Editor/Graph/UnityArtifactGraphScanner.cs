using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace UnityGraphEngineering
{
    public sealed class UnityArtifactGraphScanner
    {
        private const int MaxDiagnosticCount = 100;

        public UnityArtifactGraph Scan(string rootAssetPath, bool includePackageDependencies)
        {
            var normalizedRootPath = NormalizePath(rootAssetPath);
            if (string.IsNullOrWhiteSpace(normalizedRootPath) || !AssetDatabase.IsValidFolder(normalizedRootPath))
                throw new ArgumentException("有効なUnity Assetフォルダを指定してください。", nameof(rootAssetPath));

            var stopwatch = Stopwatch.StartNew();
            var report = new UnityArtifactScanReport();
            var graph = new UnityArtifactGraph
            {
                UnityVersion = Application.unityVersion,
                GeneratedAtUtc = DateTime.UtcNow.ToString("O"),
                RootAssetPath = normalizedRootPath,
                Report = report
            };

            var nodesByPath = new Dictionary<string, UnityArtifactNode>(StringComparer.Ordinal);
            var edgeKeys = new HashSet<string>(StringComparer.Ordinal);
            var scheduledPaths = new HashSet<string>(StringComparer.Ordinal);
            var pendingPaths = new Queue<string>();

            var rootPaths = AssetDatabase.FindAssets(string.Empty, new[] { normalizedRootPath })
                .Select(AssetDatabase.GUIDToAssetPath)
                .Select(NormalizePath)
                .Where(path => !string.IsNullOrEmpty(path) && !AssetDatabase.IsValidFolder(path))
                .Distinct(StringComparer.Ordinal)
                .OrderBy(path => path, StringComparer.Ordinal)
                .ToArray();

            report.RootAssetCount = rootPaths.Length;
            foreach (var path in rootPaths)
            {
                if (scheduledPaths.Add(path))
                    pendingPaths.Enqueue(path);
            }

            while (pendingPaths.Count > 0)
            {
                var sourcePath = pendingPaths.Dequeue();
                if (!TryAcceptPath(sourcePath, includePackageDependencies, report))
                    continue;

                report.ProcessedAssetCount++;
                var sourceNode = GetOrCreateNode(sourcePath, nodesByPath, report);
                var dependencies = AssetDatabase.GetDependencies(sourcePath, false)
                    .Select(NormalizePath)
                    .Where(path => !string.IsNullOrEmpty(path))
                    .Distinct(StringComparer.Ordinal)
                    .OrderBy(path => path, StringComparer.Ordinal);

                foreach (var dependencyPath in dependencies)
                {
                    if (string.Equals(sourcePath, dependencyPath, StringComparison.Ordinal))
                        continue;
                    if (AssetDatabase.IsValidFolder(dependencyPath))
                        continue;
                    if (!TryAcceptPath(dependencyPath, includePackageDependencies, report))
                        continue;

                    var targetNode = GetOrCreateNode(dependencyPath, nodesByPath, report);
                    var edgeKey = sourceNode.Id + "|DEPENDS_ON|" + targetNode.Id;

                    if (edgeKeys.Add(edgeKey))
                    {
                        graph.Edges.Add(new UnityArtifactEdge
                        {
                            SourceId = sourceNode.Id,
                            TargetId = targetNode.Id,
                            Relation = "DEPENDS_ON",
                            Evidence = "AssetDatabase.GetDependencies(path, false)"
                        });
                    }
                    else
                    {
                        report.DuplicateEdgeCount++;
                    }

                    if (scheduledPaths.Add(dependencyPath))
                        pendingPaths.Enqueue(dependencyPath);
                }
            }

            graph.Nodes = nodesByPath.Values.OrderBy(node => node.Path, StringComparer.Ordinal).ToList();
            graph.Edges = graph.Edges
                .OrderBy(edge => edge.SourceId, StringComparer.Ordinal)
                .ThenBy(edge => edge.TargetId, StringComparer.Ordinal)
                .ThenBy(edge => edge.Relation, StringComparer.Ordinal)
                .ToList();

            stopwatch.Stop();
            report.DurationMilliseconds = stopwatch.ElapsedMilliseconds;
            report.NodeCount = graph.Nodes.Count;
            report.EdgeCount = graph.Edges.Count;
            return graph;
        }

        private UnityArtifactNode GetOrCreateNode(string assetPath, IDictionary<string, UnityArtifactNode> nodesByPath, UnityArtifactScanReport report)
        {
            if (nodesByPath.TryGetValue(assetPath, out var existingNode))
                return existingNode;

            var guid = AssetDatabase.AssetPathToGUID(assetPath);
            var kind = ClassifyAsset(assetPath);
            if (string.IsNullOrEmpty(guid))
            {
                report.MissingGuidCount++;
                AddDiagnostic(report, "MISSING_GUID", E_UnityArtifactDiagnosticSeverity.Warning, assetPath, "AssetDatabaseからGUIDを取得できませんでした。PathをNode IDとして使用します。");
            }
            if (kind == E_UnityArtifactKind.Unknown)
            {
                report.UnknownAssetKindCount++;
                AddDiagnostic(report, "UNKNOWN_ASSET_KIND", E_UnityArtifactDiagnosticSeverity.Info, assetPath, "拡張子に対応するArtifact種別が未定義です。");
            }

            var node = new UnityArtifactNode
            {
                Id = string.IsNullOrEmpty(guid) ? "path:" + assetPath : guid,
                Guid = guid,
                Path = assetPath,
                Name = Path.GetFileNameWithoutExtension(assetPath),
                Kind = kind.ToString()
            };
            nodesByPath.Add(assetPath, node);
            return node;
        }

        private bool TryAcceptPath(string assetPath, bool includePackageDependencies, UnityArtifactScanReport report)
        {
            if (assetPath.StartsWith("Assets/", StringComparison.Ordinal) || string.Equals(assetPath, "Assets", StringComparison.Ordinal))
                return true;

            if (assetPath.StartsWith("Packages/", StringComparison.Ordinal))
            {
                if (includePackageDependencies)
                    return true;
                report.PackageDependencySkippedCount++;
                return false;
            }

            report.UnsupportedDependencySkippedCount++;
            return false;
        }

        private void AddDiagnostic(UnityArtifactScanReport report, string code, E_UnityArtifactDiagnosticSeverity severity, string path, string message)
        {
            if (report.Diagnostics.Count >= MaxDiagnosticCount)
            {
                report.DiagnosticLimitReached = true;
                return;
            }

            report.Diagnostics.Add(new UnityArtifactScanDiagnostic
            {
                Code = code,
                Severity = severity.ToString(),
                Path = path,
                Message = message
            });
        }

        private string NormalizePath(string assetPath)
        {
            return string.IsNullOrEmpty(assetPath) ? string.Empty : assetPath.Replace('\\', '/').TrimEnd('/');
        }

        private E_UnityArtifactKind ClassifyAsset(string assetPath)
        {
            var extension = Path.GetExtension(assetPath).ToLowerInvariant();
            switch (extension)
            {
                case ".unity": return E_UnityArtifactKind.Scene;
                case ".prefab": return E_UnityArtifactKind.Prefab;
                case ".mat": return E_UnityArtifactKind.Material;
                case ".shader":
                case ".shadergraph":
                case ".shadersubgraph":
                case ".compute": return E_UnityArtifactKind.Shader;
                case ".hlsl":
                case ".cginc": return E_UnityArtifactKind.HlslInclude;
                case ".cs": return E_UnityArtifactKind.Script;
                case ".asmdef": return E_UnityArtifactKind.AssemblyDefinition;
                case ".asset": return E_UnityArtifactKind.ScriptableObjectAsset;
                case ".png":
                case ".jpg":
                case ".jpeg":
                case ".tga":
                case ".psd":
                case ".exr": return E_UnityArtifactKind.Texture;
                case ".fbx":
                case ".obj":
                case ".dae": return E_UnityArtifactKind.Model;
                case ".wav":
                case ".mp3":
                case ".ogg": return E_UnityArtifactKind.Audio;
                case ".anim":
                case ".controller": return E_UnityArtifactKind.Animation;
                default:
                    return assetPath.StartsWith("Packages/", StringComparison.Ordinal)
                        ? E_UnityArtifactKind.PackageAsset
                        : E_UnityArtifactKind.Unknown;
            }
        }
    }
}
