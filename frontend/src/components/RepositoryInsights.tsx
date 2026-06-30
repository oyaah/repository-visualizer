import { AlertTriangle, BarChart3, Download, GitMerge, ListTree, Play } from 'lucide-react';
import { useMemo } from 'react';
import type { ReactNode } from 'react';
import type { CycleSummary, EntryPointSummary, FolderSummary, GraphNode, GraphResponse, ReportFinding } from '../types/graph';
import { downloadMarkdownReport } from '../utils/reportExport';

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
        <div className="insights-actions">
          <button type="button" onClick={() => downloadMarkdownReport(graph)} aria-label="Export Markdown report">
            <Download size={15} />
          </button>
          <span>{graph.stats.analyzed_files}/{graph.stats.total_files_found} source files</span>
        </div>
      </div>
      <div className="insights-stats">
        <Stat label="Edges" value={graph.edges.length} />
        <Stat label="Skipped" value={graph.stats.skipped_files} />
      </div>
      <StartHere items={insights?.startHere ?? []} nodeById={insights?.nodeById ?? new Map()} onSelectNode={onSelectNode} />
      <EntryPointList entries={insights?.entryPoints ?? []} nodeById={insights?.nodeById ?? new Map()} onSelectNode={onSelectNode} />
      <ReadingOrder paths={insights?.readingOrder ?? []} nodeById={insights?.nodeById ?? new Map()} onSelectNode={onSelectNode} />
      <FolderList folders={insights?.folders ?? []} />
      <CycleList cycles={insights?.cycles ?? []} nodeById={insights?.nodeById ?? new Map()} onSelectNode={onSelectNode} />
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
  const largest = topBy(graph.nodes, (node) => node.metrics.loc);
  const complex = topBy(graph.nodes, (node) => node.metrics.complexity);
  const hubs = topBy(graph.nodes, (node) => node.metrics.dependent_count);
  const unresolved = topBy(graph.nodes, (node) => node.unresolved_imports.length);
  const cycles = graph.cycles.slice(0, 3);
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));

  return {
    nodeById,
    startHere: graph.repo_report.start_here.slice(0, 4),
    entryPoints: graph.repo_report.entry_points.slice(0, 4),
    readingOrder: graph.repo_report.reading_order.slice(0, 6),
    folders: graph.folder_summaries.slice(0, 3),
    cycles,
    largest,
    complex,
    hubs,
    unresolved,
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

function StartHere({
  items,
  nodeById,
  onSelectNode
}: {
  items: ReportFinding[];
  nodeById: Map<string, GraphNode>;
  onSelectNode: (node: GraphNode) => void;
}) {
  return (
    <section className="insight-section start-here">
      <h3><AlertTriangle size={15} />Start here</h3>
      {items.length ? (
        <ol>
          {items.map((item) => {
            const node = nodeById.get(item.file_path);
            return (
              <li key={`${item.kind}:${item.file_path}`}>
                <button type="button" onClick={() => node && onSelectNode(node)}>
                  <span>
                    <b>{item.title}</b>
                    <em>{item.file_path}</em>
                    <small>{item.confidence} confidence</small>
                    {item.detail}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      ) : (
        <p>No obvious hotspots in analyzed files.</p>
      )}
    </section>
  );
}

function EntryPointList({
  entries,
  nodeById,
  onSelectNode
}: {
  entries: EntryPointSummary[];
  nodeById: Map<string, GraphNode>;
  onSelectNode: (node: GraphNode) => void;
}) {
  return (
    <section className="insight-section">
      <h3><Play size={15} />Likely entry points</h3>
      {entries.length ? (
        <ol>
          {entries.map((entry) => {
            const node = nodeById.get(entry.file_path);
            return (
              <li key={`${entry.kind}:${entry.file_path}`}>
                <button type="button" onClick={() => node && onSelectNode(node)}>
                  <span>{entry.file_path}</span>
                  <strong>{entry.label}</strong>
                </button>
              </li>
            );
          })}
        </ol>
      ) : (
        <p>No likely source entry points found in analyzed files.</p>
      )}
    </section>
  );
}

function ReadingOrder({
  paths,
  nodeById,
  onSelectNode
}: {
  paths: string[];
  nodeById: Map<string, GraphNode>;
  onSelectNode: (node: GraphNode) => void;
}) {
  return (
    <section className="insight-section">
      <h3><ListTree size={15} />Reading order</h3>
      {paths.length ? (
        <ol>
          {paths.map((path, index) => {
            const node = nodeById.get(path);
            return (
              <li key={path}>
                <button type="button" onClick={() => node && onSelectNode(node)}>
                  <span>{path}</span>
                  <strong>{index + 1}</strong>
                </button>
              </li>
            );
          })}
        </ol>
      ) : (
        <p>No reading order generated.</p>
      )}
    </section>
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
  nodeById,
  onSelectNode
}: {
  cycles: CycleSummary[];
  nodeById: Map<string, GraphNode>;
  onSelectNode: (node: GraphNode) => void;
}) {
  return (
    <section className="insight-section">
      <h3><GitMerge size={15} />Cycles</h3>
      {cycles.length ? (
        <ol>
          {cycles.map((cycle) => {
            const firstNode = nodeById.get(cycle.files[0]);
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
