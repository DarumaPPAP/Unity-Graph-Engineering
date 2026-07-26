using System;
using UnityEditor;
using UnityEngine;

namespace UnityGraphEngineering
{
    public sealed class UnityGraphEngineeringWindow : EditorWindow
    {
        private DefaultAsset _rootFolder;
        private bool _includePackageDependencies = true;
        private string _outputPath = "GraphData/artifact-graph.json";
        private Vector2 _nodeScrollPosition;
        private Vector2 _impactScrollPosition;
        private UnityEngine.Object _impactTarget;
        private int _impactMaxDepth = 8;
        private UnityArtifactGraph _graph;
        private UnityArtifactImpactResult _impactResult;
        private UnityArtifactGraphScanner _scanner;
        private UnityArtifactGraphExporter _exporter;
        private UnityArtifactImpactAnalyzer _impactAnalyzer;

        [MenuItem("Tools/Graph Engineering/Artifact Graph")]
        private static void Open()
        {
            GetWindow<UnityGraphEngineeringWindow>("Artifact Graph");
        }

        private void OnEnable()
        {
            _scanner = new UnityArtifactGraphScanner();
            _exporter = new UnityArtifactGraphExporter();
            _impactAnalyzer = new UnityArtifactImpactAnalyzer();
            _rootFolder = AssetDatabase.LoadAssetAtPath<DefaultAsset>("Assets");
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Unity Artifact Dependency Graph", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox("指定フォルダ以下のAsset依存を走査し、変更対象から逆方向へ影響範囲を検索します。C#呼び出しや動的ロードはPhase 0の対象外です。", MessageType.Info);

            DrawScanControls();
            DrawScanReport();
            DrawImpactQuery();
            DrawNodePreview();
        }

        private void DrawScanControls()
        {
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Scan", EditorStyles.boldLabel);
            _rootFolder = (DefaultAsset)EditorGUILayout.ObjectField("走査対象フォルダ", _rootFolder, typeof(DefaultAsset), false);
            _includePackageDependencies = EditorGUILayout.Toggle("Package依存を含める", _includePackageDependencies);
            _outputPath = EditorGUILayout.TextField("JSON出力先", _outputPath);

            var rootPath = _rootFolder == null ? string.Empty : AssetDatabase.GetAssetPath(_rootFolder);
            var canScan = !string.IsNullOrEmpty(rootPath) && AssetDatabase.IsValidFolder(rootPath);

            using (new EditorGUILayout.HorizontalScope())
            {
                using (new EditorGUI.DisabledScope(!canScan))
                {
                    if (GUILayout.Button("Graphを走査"))
                        Scan(rootPath);
                }

                using (new EditorGUI.DisabledScope(_graph == null))
                {
                    if (GUILayout.Button("JSONへ出力"))
                        Export();
                }
            }
        }

        private void DrawScanReport()
        {
            if (_graph == null || _graph.Report == null)
                return;

            var report = _graph.Report;
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Scan Report", EditorStyles.boldLabel);
            EditorGUILayout.LabelField("Unity", _graph.UnityVersion);
            EditorGUILayout.LabelField("Root Asset", report.RootAssetCount.ToString());
            EditorGUILayout.LabelField("Processed Asset", report.ProcessedAssetCount.ToString());
            EditorGUILayout.LabelField("Node / Edge", report.NodeCount + " / " + report.EdgeCount);
            EditorGUILayout.LabelField("Duration", report.DurationMilliseconds + " ms");
            EditorGUILayout.LabelField("Missing GUID", report.MissingGuidCount.ToString());
            EditorGUILayout.LabelField("Unknown Kind", report.UnknownAssetKindCount.ToString());
            EditorGUILayout.LabelField("Skipped Package", report.PackageDependencySkippedCount.ToString());
            EditorGUILayout.LabelField("Skipped Unsupported", report.UnsupportedDependencySkippedCount.ToString());

            var displayCount = Mathf.Min(report.Diagnostics.Count, 10);
            for (var index = 0; index < displayCount; index++)
            {
                var diagnostic = report.Diagnostics[index];
                var messageType = diagnostic.Severity == E_UnityArtifactDiagnosticSeverity.Error.ToString()
                    ? MessageType.Error
                    : diagnostic.Severity == E_UnityArtifactDiagnosticSeverity.Warning.ToString()
                        ? MessageType.Warning
                        : MessageType.Info;
                EditorGUILayout.HelpBox(diagnostic.Code + "\n" + diagnostic.Path + "\n" + diagnostic.Message, messageType);
            }
            if (report.Diagnostics.Count > displayCount || report.DiagnosticLimitReached)
                EditorGUILayout.LabelField("診断の一部のみ表示しています。JSON出力を確認してください。");
        }

        private void DrawImpactQuery()
        {
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Impact Query", EditorStyles.boldLabel);
            _impactTarget = EditorGUILayout.ObjectField("変更対象Asset", _impactTarget, typeof(UnityEngine.Object), false);
            _impactMaxDepth = EditorGUILayout.IntSlider("最大Hop数", _impactMaxDepth, 1, 32);

            var targetPath = _impactTarget == null ? string.Empty : AssetDatabase.GetAssetPath(_impactTarget);
            using (new EditorGUI.DisabledScope(_graph == null || string.IsNullOrEmpty(targetPath)))
            {
                if (GUILayout.Button("影響範囲を逆引き"))
                    QueryImpact(targetPath);
            }

            if (_impactResult == null)
                return;

            EditorGUILayout.LabelField("対象", _impactResult.Target.Path);
            EditorGUILayout.LabelField("影響Artifact", _impactResult.Items.Count.ToString());
            _impactScrollPosition = EditorGUILayout.BeginScrollView(_impactScrollPosition, GUILayout.MinHeight(100), GUILayout.MaxHeight(260));
            foreach (var item in _impactResult.Items)
                EditorGUILayout.LabelField(item.Distance + " hop / " + item.Node.Kind, item.Node.Path);
            EditorGUILayout.EndScrollView();
        }

        private void DrawNodePreview()
        {
            if (_graph == null)
                return;

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Node Preview", EditorStyles.boldLabel);
            _nodeScrollPosition = EditorGUILayout.BeginScrollView(_nodeScrollPosition, GUILayout.MinHeight(100));
            var displayCount = Mathf.Min(_graph.Nodes.Count, 100);
            for (var index = 0; index < displayCount; index++)
            {
                var node = _graph.Nodes[index];
                EditorGUILayout.LabelField(node.Kind, node.Path);
            }
            if (_graph.Nodes.Count > displayCount)
                EditorGUILayout.LabelField("ほか " + (_graph.Nodes.Count - displayCount) + " Node");
            EditorGUILayout.EndScrollView();
        }

        private void Scan(string rootPath)
        {
            try
            {
                _graph = _scanner.Scan(rootPath, _includePackageDependencies);
                _impactResult = null;
                Repaint();
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
                EditorUtility.DisplayDialog("Graph走査失敗", exception.Message, "閉じる");
            }
        }

        private void QueryImpact(string targetPath)
        {
            try
            {
                _impactResult = _impactAnalyzer.FindImpactedArtifacts(_graph, targetPath, _impactMaxDepth);
                Repaint();
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
                EditorUtility.DisplayDialog("影響範囲検索失敗", exception.Message, "閉じる");
            }
        }

        private void Export()
        {
            try
            {
                var outputPath = _exporter.Export(_graph, _outputPath);
                EditorUtility.RevealInFinder(outputPath);
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
                EditorUtility.DisplayDialog("Graph出力失敗", exception.Message, "閉じる");
            }
        }
    }
}
