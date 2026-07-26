using System;
using System.Collections.Generic;

namespace UnityGraphEngineering
{
    public enum E_UnityArtifactKind
    {
        Unknown,
        Scene,
        Prefab,
        Material,
        Shader,
        HlslInclude,
        Script,
        AssemblyDefinition,
        ScriptableObjectAsset,
        Texture,
        Model,
        Audio,
        Animation,
        PackageAsset
    }

    [Serializable]
    public sealed class UnityArtifactNode
    {
        public string Id;
        public string Guid;
        public string Path;
        public string Name;
        public string Kind;
    }

    [Serializable]
    public sealed class UnityArtifactEdge
    {
        public string SourceId;
        public string TargetId;
        public string Relation;
        public string Evidence;
    }

    [Serializable]
    public sealed class UnityArtifactGraph
    {
        public string SchemaVersion = "0.1.0";
        public string UnityVersion;
        public string GeneratedAtUtc;
        public string RootAssetPath;
        public List<UnityArtifactNode> Nodes = new List<UnityArtifactNode>();
        public List<UnityArtifactEdge> Edges = new List<UnityArtifactEdge>();
    }
}
