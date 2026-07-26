using System;
using System.Collections.Generic;
using System.Linq;

namespace UnityGraphEngineering
{
    public sealed class UnityArtifactImpactAnalyzer
    {
        public UnityArtifactImpactResult FindImpactedArtifacts(UnityArtifactGraph graph, string targetAssetPath, int maxDepth)
        {
            if (graph == null)
                throw new ArgumentNullException(nameof(graph));
            if (string.IsNullOrWhiteSpace(targetAssetPath))
                throw new ArgumentException("変更対象Assetを指定してください。", nameof(targetAssetPath));
            if (maxDepth < 1)
                throw new ArgumentOutOfRangeException(nameof(maxDepth), "最大Hop数は1以上で指定してください。");

            var normalizedTargetPath = targetAssetPath.Replace('\\', '/').TrimEnd('/');
            var nodesById = graph.Nodes
                .Where(node => node != null && !string.IsNullOrEmpty(node.Id))
                .GroupBy(node => node.Id, StringComparer.Ordinal)
                .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);
            var target = graph.Nodes.FirstOrDefault(node => string.Equals(node.Path, normalizedTargetPath, StringComparison.Ordinal));
            if (target == null)
                throw new InvalidOperationException("走査済みGraphに変更対象Assetが存在しません。先に対象範囲を含めて再走査してください。");

            var reverseEdges = new Dictionary<string, List<string>>(StringComparer.Ordinal);
            foreach (var edge in graph.Edges)
            {
                if (edge == null || string.IsNullOrEmpty(edge.SourceId) || string.IsNullOrEmpty(edge.TargetId))
                    continue;
                if (!string.Equals(edge.Relation, "DEPENDS_ON", StringComparison.Ordinal))
                    continue;

                if (!reverseEdges.TryGetValue(edge.TargetId, out var sourceIds))
                {
                    sourceIds = new List<string>();
                    reverseEdges.Add(edge.TargetId, sourceIds);
                }
                sourceIds.Add(edge.SourceId);
            }

            foreach (var sourceIds in reverseEdges.Values)
                sourceIds.Sort(StringComparer.Ordinal);

            var result = new UnityArtifactImpactResult
            {
                Target = target,
                MaxDepth = maxDepth
            };
            var visited = new HashSet<string>(StringComparer.Ordinal) { target.Id };
            var pending = new Queue<ImpactQueueItem>();
            pending.Enqueue(new ImpactQueueItem(target.Id, 0));

            while (pending.Count > 0)
            {
                var current = pending.Dequeue();
                if (current.Distance >= maxDepth)
                    continue;
                if (!reverseEdges.TryGetValue(current.NodeId, out var sourceIds))
                    continue;

                foreach (var sourceId in sourceIds)
                {
                    if (!visited.Add(sourceId))
                        continue;
                    if (!nodesById.TryGetValue(sourceId, out var sourceNode))
                        continue;

                    var distance = current.Distance + 1;
                    result.Items.Add(new UnityArtifactImpactItem
                    {
                        Node = sourceNode,
                        Distance = distance
                    });
                    pending.Enqueue(new ImpactQueueItem(sourceId, distance));
                }
            }

            result.Items = result.Items
                .OrderBy(item => item.Distance)
                .ThenBy(item => item.Node.Path, StringComparer.Ordinal)
                .ToList();
            return result;
        }

        private sealed class ImpactQueueItem
        {
            public string NodeId { get; }
            public int Distance { get; }

            public ImpactQueueItem(string nodeId, int distance)
            {
                NodeId = nodeId;
                Distance = distance;
            }
        }
    }
}
