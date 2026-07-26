using UnityEditor;
using UnityEngine;

namespace UnityGraphEngineering
{
    public sealed class UnityGraphEngineeringWindow : EditorWindow
    {
        private DefaultAsset _rootFolder;
        private bool _includePackageDependencies = true;
        private string _outputPath = "GraphData/artifact-graph.json";
        private Vector2 _scrollPosition;
        private UnityArtifactGraph _graph;
        private UnityArtifactGraphScanner _scanner;
        private UnityArtifactGraphExporter _exporter;

        [MenuItem("Tools/Graph Engineering/Artifact Graph")]
        private static void Open()
        {
            GetWindow<UnityGraphEngineeringWindow>("Artifact Graph");
        }

        private void OnEnable()
        {
            _scanner = new UnityArtifactGraphScanner();
            _exporter = new UnityArtifactGraphExporter();
            _rootFolder = AssetDatabase.LoadAssetAtPath<DefaultAsset>("Assets");
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Unity Artifact Dependency Graph", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox("指定フォルダ以下のAssetと直接依存を走査します。C#呼び出しや動的ロードはPhase 0の対象外です。", MessageType.Info);

            _rootFolder = (DefaultAsset)EditorGUILayout.ObjectField("走査対象フォルダ", _rootFolder, typeof(DefaultAsset), false);
            _includePackageDependencies = EditorGUILayout.Toggle("Package依存を含める", _includePackageDependencies);
            _outputPath = EditorGUILayout.TextField("JSON出力先", _outputPath);

            var rootPath = _rootFolder == null ? string.Empty : AssetDatabase.GetAssetPath(_rootFolder);
            var canScan = !string.IsNullOrEmpty(rootPath) && AssetDatabase.IsValidFolder(rootPath);

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

            DrawResult();
        }

        private void Scan(string rootPath)
        {
            try
            {
                _graph = _scanner.Scan(rootPath, _includePackageDependencies);
                Repaint();
            }
            catch (System.Exception exception)
            {
                Debug.LogException(exception);
                EditorUtility.DisplayDialog("Graph走査失敗", exception.Message, "閉じる");
            }
        }

        private void Export()
        {
            try
            {
                var outputPath = _exporter.Export(_graph, _outputPath);
                EditorUtility.RevealInFinder(outputPath);
            }
            catch (System.Exception exception)
            {
                Debug.LogException(exception);
                EditorUtility.DisplayDialog("Graph出力失敗", exception.Message, "閉じる");
            }
        }

        private void DrawResult()
        {
            if (_graph == null)
                return;

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Node", _graph.Nodes.Count.ToString());
            EditorGUILayout.LabelField("Edge", _graph.Edges.Count.ToString());
            EditorGUILayout.LabelField("Unity", _graph.UnityVersion);

            _scrollPosition = EditorGUILayout.BeginScrollView(_scrollPosition);
            var displayCount = Mathf.Min(_graph.Nodes.Count, 100);
            for (var index = 0; index < displayCount; index++)
            {
                var node = _graph.Nodes[index];
                EditorGUILayout.LabelField(node.Kind, node.Path);
            }
            if (_graph.Nodes.Count > displayCount)
                EditorGUILayout.LabelField($"ほか {_graph.Nodes.Count - displayCount} Node");
            EditorGUILayout.EndScrollView();
        }
    }
}
