import dagre from 'dagre';
import type { Edge, Node } from '@xyflow/react';
import type { GraphEdge, GraphNode } from '../types/graph';

const NODE_WIDTH = 210;
const NODE_HEIGHT = 84;

export function toFlowNodes(nodes: GraphNode[]): Node[] {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: 'LR', nodesep: 50, ranksep: 90 });

  nodes.forEach((node) => graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));

  return nodes.map((node) => {
    const position = graph.node(node.id) ?? { x: 0, y: 0 };
    return {
      id: node.id,
      type: 'repoNode',
      position: { x: position.x, y: position.y },
      data: node
    };
  });
}

export function toFlowEdges(edges: GraphEdge[]): Edge[] {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    animated: edge.kind === 'dynamic_import',
    label: edge.kind === 'include' ? 'include' : undefined
  }));
}

