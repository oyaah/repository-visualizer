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
  type NodeProps
} from '@xyflow/react';
import type { GraphNode, GraphResponse } from '../types/graph';
import { toFlowEdges, toFlowNodes } from './layout';

type GraphMode = 'all' | 'neighborhood';

type Props = {
  graph: GraphResponse | null;
  selectedNodeId: string | null;
  onSelectNode: (node: GraphNode | null) => void;
};

export function GraphCanvas({ graph, selectedNodeId, onSelectNode }: Props) {
  const [query, setQuery] = useState('');
  const [extension, setExtension] = useState('all');
  const [graphMode, setGraphMode] = useState<GraphMode>('all');
  const extensions = useMemo(() => {
    const values = new Set((graph?.nodes ?? []).map((node) => node.extension || 'file'));
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
      return matchesQuery && matchesExtension;
    });
    const visibleIds = new Set(nodes.map((node) => node.id));
    const edges = (graph?.edges ?? []).filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
    return { nodes, edges };
  }, [extension, graph, graphMode, query, selectedNodeId]);
  const flowNodes = useMemo(() => toFlowNodes(visibleGraph.nodes, visibleGraph.edges), [visibleGraph]);
  const flowEdges = useMemo(() => toFlowEdges(visibleGraph.edges), [visibleGraph]);
  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => setNodes(flowNodes), [flowNodes, setNodes]);
  useEffect(() => setEdges(flowEdges), [flowEdges, setEdges]);
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

  return (
    <section className="graph-panel" aria-label="Repository dependency graph">
      <div className="graph-toolbar">
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
          Type
          <select value={extension} onChange={(event) => setExtension(event.target.value)} aria-label="Filter graph by extension">
            <option value="all">All</option>
            {extensions.map((value) => (
              <option key={value} value={value}>{value || 'file'}</option>
            ))}
          </select>
        </label>
        {graph.stats.truncated ? <span className="warning-pill">Limited scan</span> : null}
      </div>
      {graph.stats.warnings.length ? (
        <div className="graph-warning" role="status">
          {graph.stats.warnings.join(' ')}
        </div>
      ) : null}
      <ReactFlow
        nodes={nodes.map((node) => ({ ...node, selected: node.id === selectedNodeId }))}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => onSelectNode(node.data as GraphNode)}
        fitView
      >
        <Background />
        <MiniMap pannable zoomable />
        <Controls />
      </ReactFlow>
    </section>
  );
}

const RepoNode = memo(function RepoNode({ data, selected }: NodeProps) {
  const node = data as unknown as GraphNode;
  const tone = node.metrics.complexity >= 8 || node.metrics.loc >= 80 ? 'hot' : node.metrics.dependency_count > 2 ? 'busy' : 'calm';
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
        <span>{node.metrics.dependency_count} deps</span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});

const nodeTypes = { repoNode: RepoNode };

function nodesForMode(graph: GraphResponse | null, graphMode: GraphMode, selectedNodeId: string | null): GraphNode[] {
  if (!graph) {
    return [];
  }
  if (graphMode === 'all' || !selectedNodeId) {
    return graph.nodes;
  }

  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId);
  if (!selectedNode) {
    return graph.nodes;
  }

  const ids = new Set<string>([selectedNode.id, ...selectedNode.imports, ...selectedNode.imported_by]);
  graph.edges.forEach((edge) => {
    if (edge.source === selectedNode.id) {
      ids.add(edge.target);
    }
    if (edge.target === selectedNode.id) {
      ids.add(edge.source);
    }
  });

  return graph.nodes.filter((node) => ids.has(node.id));
}
