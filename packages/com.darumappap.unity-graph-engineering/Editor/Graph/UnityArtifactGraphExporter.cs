using System;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace UnityGraphEngineering
{
    public sealed class UnityArtifactGraphExporter
    {
        public string Export(UnityArtifactGraph graph, string projectRelativePath)
        {
            if (graph == null)
                throw new ArgumentNullException(nameof(graph));
            if (string.IsNullOrWhiteSpace(projectRelativePath))
                throw new ArgumentException("出力先を指定してください。", nameof(projectRelativePath));

            var projectRoot = Path.GetFullPath(Directory.GetCurrentDirectory());
            var outputPath = Path.GetFullPath(Path.Combine(projectRoot, projectRelativePath));
            if (!outputPath.StartsWith(projectRoot, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("出力先はUnity Project配下に限定されています。");

            var directoryPath = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(directoryPath))
                Directory.CreateDirectory(directoryPath);

            var json = JsonUtility.ToJson(graph, true);
            File.WriteAllText(outputPath, json, new UTF8Encoding(false));

            var normalizedRelativePath = projectRelativePath.Replace('\\', '/');
            if (normalizedRelativePath.StartsWith("Assets/", StringComparison.Ordinal))
                AssetDatabase.Refresh();

            return outputPath;
        }
    }
}
