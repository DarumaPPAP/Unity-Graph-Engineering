using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace UnityGraphEngineering
{
    public sealed class UnityArtifactGraphScanner
    {
        public UnityArtifactGraph Scan(string rootAssetPath, bool includePackageDependencies)
        {
            if (string.IsNullOrWhiteSpace(rootAssetPath) || !AssetDatabase.IsValidFolder(rootAssetPath))
                throw new ArgumentException("有効なUnity Assetフォルダを指定してください。", nameof(rootAssetPath));

            var graph = new UnityArtifactGraph
            {
                UnityVersion = Application.unityVersion,
                GeneratedAtUtc = DateTime.UtcNow.ToString("O"),
                RootAssetPath = rootAssetPath
            };

            var nodesByPath = new Dictionary<string, UnityArtifactNode>(StringComparer.Ordinal);
            var edgeKeys = new HashSet<string>(StringComparer.Ordinal);
            var scheduledPaths = new HashSet<string>(StringComparer.Ordinal);
            var pendingPaths = new Queue<string>();

            foreach (var guid in AssetDatabase.FindAssets(string.Empty, new[] { rootAssetPath }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                if (!string.IsNullOrEmpty(path) && !AssetDatabase.IsValidFolder(path) && scheduledPaths.Add(path))
                    pendingPaths.Enqueue(path);
            }

            while (pendingPaths.Count > 0)
            {
                var sourcePath = pendingPaths.Dequeue();
                if (!IsSupportedPath(sourcePath, includePackageDependencies))
                    continue;

                var sourceNode = GetOrCreateNode(sourcePath, nodesByPath);
                var dependencies = AssetDatabase.GetDependencies(sourcePath, false);

                foreach (var dependencyPath in dependencies)
                {
                    if (string.Equals(sourcePath, dependencyPath, StringComparison.Ordinal))
                        continue;
                    if (!IsSupportedPath(dependencyPath, includePackageDependencies))
                        continue;
                    if (AssetDatabase.IsValidFolder(dependencyPath))
                        continue;

                    var targetNode = GetOrCreateNode(dependencyPath, nodesByPath);
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

                    if (scheduledPaths.Add(dependencyPath))
                        pendingPaths.Enqueue(dependencyPath);
                }
            }

            graph.Nodes = nodesByPath.Values.OrderBy(node => node.Path, StringComparer.Ordinal).ToList();
            graph.Edges = graph.Edges
                .OrderBy(edge => edge.SourceId, StringComparer.Ordinal)
                .ThenBy(edge => edge.TargetId, StringComparer.Ordinal)
                .ToList();
            return graph;
        }

        private UnityArtifactNode GetOrCreateNode(string assetPath, IDictionary<string, UnityArtifactNode> nodesByPath)
        {
            if (nodesByPath.TryGetValue(assetPath, out var existingNode))
                return existingNode;

            var guid = AssetDatabase.AssetPathToGUID(assetPath);
            var node = new UnityArtifactNode
            {
                Id = string.IsNullOrEmpty(guid) ? assetPath : guid,
                Guid = guid,
                Path = assetPath,
                Name = Path.GetFileNameWithoutExtension(assetPath),
                Kind = ClassifyAsset(assetPath).ToString()
            };
            nodesByPath.Add(assetPath, node);
            return node;
        }

        private bool IsSupportedPath(string assetPath, bool includePackageDependencies)
        {
            if (assetPath.StartsWith("Assets/", StringComparison.Ordinal) || string.Equals(assetPath, "Assets", StringComparison.Ordinal))
                return true;
            return includePackageDependencies && assetPath.StartsWith("Packages/", StringComparison.Ordinal);
        }

        private E_UnityArtifactKind ClassifyAsset(string assetPath)
        {
            var extension = Path.GetExtension(assetPath).ToLowerInvariant();
            switch (extension)
            {
                case ".unity": return E_UnityArtifactKind.Scene;
                case ".prefab": return E_UnityArtifactKind.Prefab;
                case ".mat": return E_UnityArtifactKind.Material;
                case ".shader": return E_UnityArtifactKind.Shader;
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
