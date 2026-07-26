# Third-Party References

本リポジトリは、以下の公開リポジトリを設計上の参考資料として利用します。

## Unity-Technologies/skills

AI Agent Skillのフォルダ構成、`SKILL.md`のYAML frontmatter、長い資料を`references/`へ分離する方針を参考にしています。ソースコードの複製は行いません。

## codejunkie99/graph-engineering

Knowledge GraphとTask Graphを分ける基本モデル、Schema First、provenance、fusion、diamond pattern、human gateの考え方を参考にしています。元リポジトリはMIT Licenseです。本リポジトリのUnity固有Skillと実装は独自に記述しています。

## Unity-Technologies/UnityCsReference

Unity C# Reference SourceはUnity Reference Only Licenseで提供されています。APIの存在・境界・挙動を確認するためだけに使用し、ソースコードを転載・改変・再配布しません。

## Unity-Technologies/ml-agents

UPM packageの分離、Editor/Runtime assembly、Documentation、Samples、Testsというプロジェクト構造を参考にしています。ML-AgentsをLLM Agent Orchestratorとして使用するものではありません。
