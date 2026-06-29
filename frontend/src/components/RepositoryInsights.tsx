import { AlertTriangle, BarChart3, GitMerge, ListTree } from 'lucide-react';
import { useMemo } from 'react';
import type { ReactNode } from 'react';
import type { CycleSummary, FolderSummary, GraphNode, GraphResponse } from '../types/graph';

type Props = {
  graph: GraphResponse | null;
  onSelectNode: (node: GraphNode) => void;
};

export function RepositoryInsights({ graph, onSelectNode }: Props) {
  const insights = useMemo(() => (graph ? buildInsights(graph) : null), [graph]);

  if (!graph) {
    return (
      <aside className="insights-panel empty" aria-label="Repository insights">
        <BarChart3 size={22} />
        <p>Analyze a repository to see hotspots, hubs, and unresolved imports.</p>
      </aside>
    );
  }

  return (
    <aside className="insights-panel" aria-label="Repository insights">
      <div className="insights-header">
        <div>
          <span className="path-label">repository</span>
          <h2>Insights</h2>
        </div>
        <span>{graph.nodes.length} files</span>
      </div>
      <div className="insights-stats">
        <Stat label="Edges" value={graph.edges.length} />
        <Stat label="Skipped" value={graph.stats.skipped_files} />
      </div>
      <FolderList folders={insights?.folders ?? []} />
      <CycleList cycles={insights?.cycles ?? []} nodes={graph.nodes} onSelectNode={onSelectNode} />
      <InsightList title="Largest files" icon={<ListTree size={15} />} items={insights?.largest ?? []} valueFor={(node) => `${node.metrics.loc} LoC`} onSelectNode={onSelectNode} />
      <InsightList title="Complexity" icon={<BarChart3 size={15} />} items={insights?.complex ?? []} valueFor={(node) => `Cx ${node.metrics.complexity}`} onSelectNode={onSelectNode} />
      <InsightList title="Dependency hubs" icon={<GitMerge size={15} />} items={insights?.hubs ?? []} valueFor={(node) => `${node.metrics.dependent_count} uses`} onSelectNode={onSelectNode} />
      <InsightList
        title="Unresolved imports"
        icon={<AlertTriangle size={15} />}
        items={insights?.unresolved ?? []}
        valueFor={(node) => `${node.unresolved_imports.length} refs`}
        onSelectNode={onSelectNode}
        fallback="No unresolved references in analyzed files."
      />
      <InsightList
        title="External imports"
        icon={<AlertTriangle size={15} />}
        items={insights?.external ?? []}
        valueFor={(node) => `${node.external_imports.length} refs`}
        onSelectNode={onSelectNode}
        fallback="No external package references in analyzed files."
      />
    </aside>
  );
}

function buildInsights(graph: GraphResponse) {
  return {
    folders: graph.folder_summaries.slice(0, 3),
    cycles: graph.cycles.slice(0, 3),
    largest: topBy(graph.nodes, (node) => node.metrics.loc),
    complex: topBy(graph.nodes, (node) => node.metrics.complexity),
    hubs: topBy(graph.nodes, (node) => node.metrics.dependent_count),
    unresolved: topBy(graph.nodes, (node) => node.unresolved_imports.length),
    external: topBy(graph.nodes, (node) => node.external_imports.length)
  };
}

function topBy(nodes: GraphNode[], score: (node: GraphNode) => number): GraphNode[] {
  return [...nodes]
    .filter((node) => score(node) > 0)
    .sort((a, b) => score(b) - score(a) || a.path.localeCompare(b.path))
    .slice(0, 3);
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function InsightList({
  title,
  icon,
  items,
  valueFor,
  onSelectNode,
  fallback = 'No matching files.'
}: {
  title: string;
  icon: ReactNode;
  items: GraphNode[];
  valueFor: (node: GraphNode) => string;
  onSelectNode: (node: GraphNode) => void;
  fallback?: string;
}) {
  return (
    <section className="insight-section">
      <h3>{icon}{title}</h3>
      {items.length ? (
        <ol>
          {items.map((node) => (
            <li key={node.id}>
              <button type="button" onClick={() => onSelectNode(node)}>
                <span>{node.path}</span>
                <strong>{valueFor(node)}</strong>
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p>{fallback}</p>
      )}
    </section>
  );
}

function FolderList({ folders }: { folders: FolderSummary[] }) {
  return (
    <section className="insight-section">
      <h3><ListTree size={15} />Top folders</h3>
      {folders.length ? (
        <ol>
          {folders.map((folder) => (
            <li key={folder.name}>
              <div className="folder-insight-row">
                <span>{folder.name}</span>
                <strong>{folder.loc} LoC / {folder.files} {folder.files === 1 ? 'file' : 'files'}</strong>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p>No folders found.</p>
      )}
    </section>
  );
}

function CycleList({
  cycles,
  nodes,
  onSelectNode
}: {
  cycles: CycleSummary[];
  nodes: GraphNode[];
  onSelectNode: (node: GraphNode) => void;
}) {
  return (
    <section className="insight-section">
      <h3><GitMerge size={15} />Cycles</h3>
      {cycles.length ? (
        <ol>
          {cycles.map((cycle) => {
            const firstNode = nodes.find((node) => node.id === cycle.files[0]);
            return (
              <li key={cycle.files.join('|')}>
                <button type="button" onClick={() => firstNode && onSelectNode(firstNode)}>
                  <span>{cycle.files.join(' -> ')}</span>
                  <strong>{cycle.files.length} files / {cycle.edge_count} edges</strong>
                </button>
              </li>
            );
          })}
        </ol>
      ) : (
        <p>No dependency cycles in analyzed files.</p>
      )}
    </section>
  );
}
