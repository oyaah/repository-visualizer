import { AlertTriangle, BarChart3, GitMerge, ListTree } from 'lucide-react';
import type { ReactNode } from 'react';
import type { GraphNode, GraphResponse } from '../types/graph';

type Props = {
  graph: GraphResponse | null;
  onSelectNode: (node: GraphNode) => void;
};

export function RepositoryInsights({ graph, onSelectNode }: Props) {
  if (!graph) {
    return (
      <aside className="insights-panel empty" aria-label="Repository insights">
        <BarChart3 size={22} />
        <p>Analyze a repository to see hotspots, hubs, and unresolved imports.</p>
      </aside>
    );
  }

  const largest = topBy(graph.nodes, (node) => node.metrics.loc);
  const complex = topBy(graph.nodes, (node) => node.metrics.complexity);
  const hubs = topBy(graph.nodes, (node) => node.metrics.dependent_count);
  const unresolved = graph.nodes
    .filter((node) => node.unresolved_imports.length || node.external_imports.length)
    .sort((a, b) => b.unresolved_imports.length + b.external_imports.length - (a.unresolved_imports.length + a.external_imports.length))
    .slice(0, 3);

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
      <InsightList title="Largest files" icon={<ListTree size={15} />} items={largest} valueFor={(node) => `${node.metrics.loc} LoC`} onSelectNode={onSelectNode} />
      <InsightList title="Complexity" icon={<BarChart3 size={15} />} items={complex} valueFor={(node) => `Cx ${node.metrics.complexity}`} onSelectNode={onSelectNode} />
      <InsightList title="Dependency hubs" icon={<GitMerge size={15} />} items={hubs} valueFor={(node) => `${node.metrics.dependent_count} uses`} onSelectNode={onSelectNode} />
      <InsightList
        title="External / unresolved"
        icon={<AlertTriangle size={15} />}
        items={unresolved}
        valueFor={(node) => `${node.unresolved_imports.length + node.external_imports.length} refs`}
        onSelectNode={onSelectNode}
        fallback="No unresolved references in analyzed files."
      />
    </aside>
  );
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
