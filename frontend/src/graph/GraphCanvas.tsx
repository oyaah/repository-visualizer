import { memo, useEffect, useMemo } from 'react';
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

type Props = {
  graph: GraphResponse | null;
  selectedNodeId: string | null;
  onSelectNode: (node: GraphNode) => void;
};

export function GraphCanvas({ graph, selectedNodeId, onSelectNode }: Props) {
  const flowNodes = useMemo(() => toFlowNodes(graph?.nodes ?? []), [graph]);
  const flowEdges = useMemo(() => toFlowEdges(graph?.edges ?? []), [graph]);
  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => setNodes(flowNodes), [flowNodes, setNodes]);
  useEffect(() => setEdges(flowEdges), [flowEdges, setEdges]);

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
        <strong>{graph.nodes.length} files</strong>
        <span>{graph.edges.length} local edges</span>
        {graph.ignored_directories.length ? <span>Ignored: {graph.ignored_directories.join(', ')}</span> : null}
      </div>
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
