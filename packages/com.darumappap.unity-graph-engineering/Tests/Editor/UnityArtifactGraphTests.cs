using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

namespace UnityGraphEngineering.Tests
{
    public sealed class UnityArtifactGraphTests
    {
        private const string RootPath = "Assets/__UnityGraphEngineeringTests";
        private const string EmptyFolderPath = RootPath + "/Empty";
        private const string ShaderPath = RootPath + "/Validation.shader";
        private const string MaterialPath = RootPath + "/Validation.mat";
        private const string PrefabPath = RootPath + "/Validation.prefab";

        [SetUp]
        public void SetUp()
        {
            DeleteFixture();
            EnsureFolder(RootPath);
            EnsureFolder(EmptyFolderPath);
        }

        [TearDown]
        public void TearDown()
        {
            DeleteFixture();
        }

        [Test]
        public void Scan_EmptyFolder_ReturnsEmptyGraph()
        {
            var graph = new UnityArtifactGraphScanner().Scan(EmptyFolderPath, false);

            Assert.That(graph.Nodes, Is.Empty);
            Assert.That(graph.Edges, Is.Empty);
            Assert.That(graph.Report.RootAssetCount, Is.Zero);
            Assert.That(graph.Report.NodeCount, Is.Zero);
            Assert.That(graph.Report.EdgeCount, Is.Zero);
        }

        [Test]
        public void Scan_PrefabMaterialShader_CreatesDependencyChain()
        {
            CreateFixtureAssets();

            var graph = new UnityArtifactGraphScanner().Scan(RootPath, false);
            var prefab = graph.Nodes.Single(node => node.Path == PrefabPath);
            var material = graph.Nodes.Single(node => node.Path == MaterialPath);
            var shader = graph.Nodes.Single(node => node.Path == ShaderPath);

            Assert.That(graph.Edges.Any(edge => edge.SourceId == prefab.Id && edge.TargetId == material.Id), Is.True);
            Assert.That(graph.Edges.Any(edge => edge.SourceId == material.Id && edge.TargetId == shader.Id), Is.True);
            Assert.That(graph.Report.NodeCount, Is.EqualTo(graph.Nodes.Count));
            Assert.That(graph.Report.EdgeCount, Is.EqualTo(graph.Edges.Count));
        }

        [Test]
        public void Scan_SameFixture_ProducesStableNormalizedJson()
        {
            CreateFixtureAssets();
            var scanner = new UnityArtifactGraphScanner();
            var exporter = new UnityArtifactGraphExporter();

            var first = scanner.Scan(RootPath, false);
            var second = scanner.Scan(RootPath, false);
            NormalizeVolatileFields(first);
            NormalizeVolatileFields(second);

            Assert.That(exporter.Serialize(first, false), Is.EqualTo(exporter.Serialize(second, false)));
        }

        [Test]
        public void ImpactQuery_Shader_ReturnsMaterialThenPrefab()
        {
            CreateFixtureAssets();
            var graph = new UnityArtifactGraphScanner().Scan(RootPath, false);

            var result = new UnityArtifactImpactAnalyzer().FindImpactedArtifacts(graph, ShaderPath, 8);

            Assert.That(result.Items.Any(item => item.Node.Path == MaterialPath && item.Distance == 1), Is.True);
            Assert.That(result.Items.Any(item => item.Node.Path == PrefabPath && item.Distance == 2), Is.True);
        }

        [Test]
        public void Export_ProjectTraversal_Throws()
        {
            var graph = new UnityArtifactGraph();

            Assert.Throws<System.InvalidOperationException>(() => new UnityArtifactGraphExporter().Export(graph, "../unity-graph-engineering-outside.json"));
        }

        [Test]
        public void Package_VisibleAssetsHaveMetaFiles()
        {
            var packageInfo = UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(UnityArtifactGraphScanner).Assembly);
            Assert.That(packageInfo, Is.Not.Null);

            var missingMetaPaths = Directory
                .EnumerateFileSystemEntries(packageInfo.resolvedPath, "*", SearchOption.AllDirectories)
                .Where(path => !path.EndsWith(".meta", System.StringComparison.OrdinalIgnoreCase))
                .Where(path => !IsHiddenFromUnity(packageInfo.resolvedPath, path))
                .Where(path => !File.Exists(path + ".meta"))
                .Select(path => path.Substring(packageInfo.resolvedPath.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
                .OrderBy(path => path, System.StringComparer.Ordinal)
                .ToArray();

            Assert.That(
                missingMetaPaths,
                Is.Empty,
                "Every visible package asset must have a committed .meta file:\n" + string.Join("\n", missingMetaPaths));
        }

        private static void CreateFixtureAssets()
        {
            var shaderSource = @"Shader ""Hidden/UnityGraphEngineering/Validation""
{
    SubShader
    {
        Pass
        {
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            float4 Vert(float4 positionOS : POSITION) : SV_POSITION { return positionOS; }
            float4 Frag() : SV_Target { return float4(1, 1, 1, 1); }
            ENDHLSL
        }
    }
}";
            File.WriteAllText(ToAbsolutePath(ShaderPath), shaderSource);
            AssetDatabase.ImportAsset(ShaderPath, ImportAssetOptions.ForceSynchronousImport);

            var shader = AssetDatabase.LoadAssetAtPath<Shader>(ShaderPath);
            Assert.That(shader, Is.Not.Null);
            var material = new Material(shader);
            AssetDatabase.CreateAsset(material, MaterialPath);

            var gameObject = new GameObject("ValidationPrefab");
            try
            {
                var renderer = gameObject.AddComponent<MeshRenderer>();
                renderer.sharedMaterial = material;
                gameObject.AddComponent<MeshFilter>();
                PrefabUtility.SaveAsPrefabAsset(gameObject, PrefabPath);
            }
            finally
            {
                Object.DestroyImmediate(gameObject);
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        }

        private static void NormalizeVolatileFields(UnityArtifactGraph graph)
        {
            graph.GeneratedAtUtc = string.Empty;
            graph.Report.DurationMilliseconds = 0;
        }

        private static string ToAbsolutePath(string projectRelativePath)
        {
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", projectRelativePath));
        }

        private static bool IsHiddenFromUnity(string packageRoot, string path)
        {
            return path
                .Substring(packageRoot.Length)
                .Split(new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar }, System.StringSplitOptions.RemoveEmptyEntries)
                .Any(segment => segment.EndsWith("~", System.StringComparison.Ordinal));
        }

        private static void EnsureFolder(string path)
        {
            var segments = path.Split('/');
            var current = segments[0];
            for (var index = 1; index < segments.Length; index++)
            {
                var next = current + "/" + segments[index];
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(current, segments[index]);
                current = next;
            }
        }

        private static void DeleteFixture()
        {
            if (AssetDatabase.IsValidFolder(RootPath))
                AssetDatabase.DeleteAsset(RootPath);
        }
    }
}
