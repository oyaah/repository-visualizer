import { memo, useEffect, useMemo, useState } from 'react';
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Node as FlowNode,
  type NodeProps
} from '@xyflow/react';
import type { GraphNode, GraphResponse, PackageSummary } from '../types/graph';
import { applyLayout, clearSavedLayout, readSavedLayout, saveNodeLayout } from '../utils/layoutStorage';
import { buildFileFlow, buildPackageFlow, type ExternalFlowNode } from './layout';

type GraphMode = 'all' | 'neighborhood';
type ViewMode = 'files' | 'packages';
type GraphPreset = 'all' | 'hide-tests' | 'connected' | 'hubs' | 'issues';

type Props = {
  graph: GraphResponse | null;
  selectedNodeId: string | null;
  onSelectNode: (node: GraphNode | null) => void;
};

export function GraphCanvas({ graph, selectedNodeId, onSelectNode }: Props) {
  const [query, setQuery] = useState('');
  const [extension, setExtension] = useState('all');
  const [folder, setFolder] = useState('all');
  const [preset, setPreset] = useState<GraphPreset>('all');
  const [graphMode, setGraphMode] = useState<GraphMode>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('files');
  const [showExternal, setShowExternal] = useState(false);
  const [layoutVersion, setLayoutVersion] = useState(0);
  const extensions = useMemo(() => {
    const values = new Set((graph?.nodes ?? []).map((node) => node.extension || 'file'));
    return Array.from(values).sort();
  }, [graph]);
  const folders = useMemo(() => {
    const values = new Set((graph?.nodes ?? []).map((node) => topFolder(node.path)));
    return Array.from(values).sort();
  }, [graph]);
  const visibleGraph = useMemo(() => {
    const candidateNodes = nodesForMode(graph, graphMode, selectedNodeId);
    const normalizedQuery = query.trim().toLowerCase();
    const nodes = candidateNodes.filter((node) => {
      const matchesQuery =
        !normalizedQuery ||
        node.path.toLowerCase().includes(normalizedQuery) ||
        node.label.toLowerCase().includes(normalizedQuery) ||
        node.folder.toLowerCase().includes(normalizedQuery);
      const matchesExtension = extension === 'all' || node.extension === extension;
      const matchesFolder = folder === 'all' || topFolder(node.path) === folder;
      return matchesQuery && matchesExtension && matchesFolder && matchesPreset(node, preset);
    });
    const visibleIds = new Set(nodes.map((node) => node.id));
    const edges = (graph?.edges ?? []).filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
    return { nodes, edges };
  }, [extension, folder, graph, graphMode, preset, query, selectedNodeId]);
  const savedLayout = useMemo(() => readSavedLayout(graph?.root_path ?? '', graph?.nodes ?? []), [graph?.nodes, graph?.root_path, layoutVersion]);
  const fileFlow = useMemo(() => buildFileFlow(visibleGraph.nodes, visibleGraph.edges, showExternal), [showExternal, visibleGraph]);
  const flowNodes = useMemo(() => applyLayout(fileFlow.flowNodes, savedLayout), [fileFlow.flowNodes, savedLayout]);
  const flowEdges = fileFlow.flowEdges;
  const flowKey = `${graph?.root_path ?? ''}:${graphMode}:${preset}:${extension}:${folder}:${query}:${showExternal}:${selectedNodeId ?? ''}:${layoutVersion}`;
  useEffect(() => {
    if (!graph) {
      return;
    }
    if (!selectedNodeId) {
      return;
    }
    if (visibleGraph.nodes.some((node) => node.id === selectedNodeId)) {
      return;
    }
    onSelectNode(visibleGraph.nodes[0] ?? null);
  }, [graph, onSelectNode, selectedNodeId, visibleGraph.nodes]);

  if (!graph) {
    return (
      <section className="graph-empty">
        <h2>No repository loaded</h2>
        <p>Analyze a local path to see file relationships and metrics.</p>
      </section>
    );
  }

  const packages = graph.package_summaries ?? [];
  const packageEdges = graph.package_edges ?? [];
  const packageFlow = buildPackageFlow(packages, packageEdges);

  function openPackage(name: string) {
    setViewMode('files');
    setGraphMode('all');
    setFolder(folders.includes(name) ? name : 'all');
    setQuery('');
  }

  return (
    <section className="graph-panel" aria-label="Repository dependency graph">
      <div className="graph-toolbar">
        <div className="view-toggle" aria-label="Graph view">
          <button type="button" className={viewMode === 'files' ? 'active' : ''} onClick={() => setViewMode('files')}>
            Files
          </button>
          <button type="button" className={viewMode === 'packages' ? 'active' : ''} onClick={() => setViewMode('packages')}>
            Packages
          </button>
        </div>
        {viewMode === 'packages' ? (
          <>
            <strong>{packages.length} packages</strong>
            <span>{packageEdges.length} cross-package links</span>
            <span className="hint">Click a package to drill into its files</span>
          </>
        ) : (
          <>
            <strong>{visibleGraph.nodes.length} of {graph.nodes.length} files</strong>
            <span>{visibleGraph.edges.length} of {graph.edges.length} local edges</span>
            <span>{graph.stats.analyzed_files} analyzed / {graph.stats.total_files_found} found</span>
            {graph.stats.skipped_files ? <span>{graph.stats.skipped_files} skipped</span> : null}
            {graph.ignored_directories.length ? <span>Ignored: {graph.ignored_directories.join(', ')}</span> : null}
            <div className="graph-mode" aria-label="Graph display mode">
              <button type="button" className={graphMode === 'all' ? 'active' : ''} onClick={() => setGraphMode('all')}>
                Full
              </button>
              <button type="button" className={graphMode === 'neighborhood' ? 'active' : ''} onClick={() => setGraphMode('neighborhood')}>
                Neighborhood
              </button>
            </div>
            <button
              type="button"
              className="graph-reset"
              onClick={() => {
                clearSavedLayout(graph.root_path, graph.nodes);
                setLayoutVersion((version) => version + 1);
              }}
            >
              Reset layout
            </button>
            <label className="graph-filter">
              Search
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="path or folder"
                aria-label="Filter graph by path"
              />
            </label>
            <label className="graph-filter compact">
              Preset
              <select value={preset} onChange={(event) => setPreset(event.target.value as GraphPreset)} aria-label="Filter graph by preset">
                <option value="all">All files</option>
                <option value="hide-tests">Hide tests</option>
                <option value="connected">Connected only</option>
                <option value="hubs">Hubs</option>
                <option value="issues">Issues</option>
              </select>
            </label>
            <label className="graph-filter compact">
              Type
              <select value={extension} onChange={(event) => setExtension(event.target.value)} aria-label="Filter graph by extension">
                <option value="all">All</option>
                {extensions.map((value) => (
                  <option key={value} value={value}>{value || 'file'}</option>
                ))}
              </select>
            </label>
            <label className="graph-filter compact">
              Folder
              <select value={folder} onChange={(event) => setFolder(event.target.value)} aria-label="Filter graph by folder">
                <option value="all">All</option>
                {folders.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="graph-toggle">
              <input type="checkbox" checked={showExternal} onChange={(event) => setShowExternal(event.target.checked)} />
              External deps
            </label>
          </>
        )}
        {graph.stats.truncated ? <span className="warning-pill">Limited scan</span> : null}
      </div>
      {graph.stats.truncated ? (
        <div className="graph-warning" role="status">
          {graph.stats.warnings.join(' ')}
        </div>
      ) : null}
      {viewMode === 'packages' ? (
        <PackageGraph
          key={`pkg:${graph.root_path}`}
          flowNodes={packageFlow.flowNodes}
          flowEdges={packageFlow.flowEdges}
          onOpenPackage={openPackage}
        />
      ) : (
        <FlowGraph
          key={flowKey}
          graph={graph}
          flowNodes={flowNodes}
          flowEdges={flowEdges}
          selectedNodeId={selectedNodeId}
          onSelectNode={onSelectNode}
        />
      )}
    </section>
  );
}

function FlowGraph({
  graph,
  flowNodes,
  flowEdges,
  selectedNodeId,
  onSelectNode
}: {
  graph: GraphResponse;
  flowNodes: FlowNode[];
  flowEdges: ReturnType<typeof buildFileFlow>['flowEdges'];
  selectedNodeId: string | null;
  onSelectNode: (node: GraphNode | null) => void;
}) {
  const [nodes, , onNodesChange] = useNodesState(flowNodes);
  const [edges, , onEdgesChange] = useEdgesState(flowEdges);

  return (
    <ReactFlow
      nodes={nodes.map((node) => ({ ...node, selected: node.id === selectedNodeId }))}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeDragStop={(_, node: FlowNode) => {
        if (!String(node.id).startsWith('external::')) {
          saveNodeLayout(graph.root_path, graph.nodes, node.id, node.position);
        }
      }}
      onNodeClick={(_, node) => {
        if (!String(node.id).startsWith('external::')) {
          onSelectNode(node.data as GraphNode);
        }
      }}
      fitView
    >
      <Background />
      <MiniMap pannable zoomable />
      <Controls />
    </ReactFlow>
  );
}

function PackageGraph({
  flowNodes,
  flowEdges,
  onOpenPackage
}: {
  flowNodes: FlowNode[];
  flowEdges: ReturnType<typeof buildPackageFlow>['flowEdges'];
  onOpenPackage: (name: string) => void;
}) {
  const [nodes, , onNodesChange] = useNodesState(flowNodes);
  const [edges, , onEdgesChange] = useEdgesState(flowEdges);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={(_, node) => onOpenPackage(String(node.id))}
      fitView
    >
      <Background />
      <MiniMap pannable zoomable />
      <Controls />
    </ReactFlow>
  );
}

const RepoNode = memo(function RepoNode({ data, selected }: NodeProps) {
  const node = data as unknown as GraphNode;
  const risk = node.metrics.risk_score ?? 0;
  const tone = riskTone(risk);
  return (
    <div className={`repo-node ${tone} ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      <div className="repo-node-top">
        <span>{node.extension.replace('.', '') || 'file'}</span>
        <strong>{node.label}</strong>
      </div>
      <div className="repo-node-metrics">
        <span>{node.metrics.loc} LoC</span>
        <span>Cx {node.metrics.complexity}</span>
        <span className={`risk-pill ${tone}`}>Risk {risk}</span>
      </div>
      {node.git ? (
        <div className="repo-node-git">
          <span>{node.git.commits} commits</span>
          {node.git.fix_commits ? <span>{node.git.fix_commits} fixes</span> : null}
          {node.git.primary_author ? <span>@{node.git.primary_author}</span> : null}
        </div>
      ) : null}
      <Handle type="source" position={Position.Right} />
    </div>
  );
});

const PackageNode = memo(function PackageNode({ data }: NodeProps) {
  const pkg = data as unknown as PackageSummary;
  const tone = riskTone(pkg.average_risk);
  const segments = pkg.name.split('/');
  const leaf = segments[segments.length - 1];
  const parent = segments.slice(0, -1).join('/');
  return (
    <div className={`package-node ${tone}`} title={pkg.name}>
      <Handle type="target" position={Position.Left} />
      <div className="package-node-top">
        <strong>{leaf}</strong>
        <span className={`risk-pill ${tone}`}>risk {Math.round(pkg.average_risk)}</span>
      </div>
      {parent ? <div className="package-node-path">{parent}/</div> : null}
      <div className="package-node-metrics">
        <span>{pkg.files} files</span>
        <span>{pkg.loc} LoC</span>
        {pkg.bus_factor != null ? <span>bus {pkg.bus_factor}</span> : null}
      </div>
      {pkg.primary_author ? <div className="package-node-owner">@{pkg.primary_author}</div> : null}
      <Handle type="source" position={Position.Right} />
    </div>
  );
});

const ExternalNode = memo(function ExternalNode({ data }: NodeProps) {
  const node = data as unknown as ExternalFlowNode;
  return (
    <div className="external-node">
      <Handle type="target" position={Position.Left} />
      <strong>{node.label}</strong>
      <span>{node.count} importers</span>
    </div>
  );
});

const nodeTypes = { repoNode: RepoNode, packageNode: PackageNode, externalNode: ExternalNode };

function riskTone(risk: number): 'hot' | 'busy' | 'calm' {
  if (risk >= 70) {
    return 'hot';
  }
  if (risk >= 40) {
    return 'busy';
  }
  return 'calm';
}

function nodesForMode(graph: GraphResponse | null, graphMode: GraphMode, selectedNodeId: string | null): GraphNode[] {
  if (!graph) {
    return [];
  }
  if (graphMode === 'all' || !selectedNodeId) {
    return graph.nodes;
  }

  if (!graph.nodes.some((node) => node.id === selectedNodeId)) {
    return graph.nodes;
  }

  const ids = new Set<string>([selectedNodeId]);
  graph.edges.forEach((edge) => {
    if (edge.source === selectedNodeId) {
      ids.add(edge.target);
    }
    if (edge.target === selectedNodeId) {
      ids.add(edge.source);
    }
  });

  return graph.nodes.filter((node) => ids.has(node.id));
}

function topFolder(path: string): string {
  return path.includes('/') ? path.split('/')[0] : 'root';
}

function matchesPreset(node: GraphNode, preset: GraphPreset): boolean {
  if (preset === 'hide-tests') {
    return !isTestPath(node.path);
  }
  if (preset === 'connected') {
    return node.metrics.dependency_count > 0 || node.metrics.dependent_count > 0;
  }
  if (preset === 'hubs') {
    return node.metrics.dependent_count >= 2;
  }
  if (preset === 'issues') {
    return node.unresolved_imports.length > 0 || node.metrics.complexity >= 8 || node.metrics.loc >= 80 || (node.metrics.risk_score ?? 0) >= 70;
  }
  return true;
}

function isTestPath(path: string): boolean {
  const lower = path.toLowerCase();
  return /(^|\/)(__tests__|tests?|specs?)(\/|$)/.test(lower) || /(^|[._-])(test|spec)\.[jt]sx?$/.test(lower) || lower.startsWith('test_');
}
