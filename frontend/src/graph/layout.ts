import dagre from 'dagre';
import type { Edge, Node } from '@xyflow/react';
import type { GraphEdge, GraphNode, PackageEdge, PackageSummary } from '../types/graph';

const NODE_WIDTH = 210;
const NODE_HEIGHT = 84;

type LayoutItem = { id: string; type: string; data: unknown; width?: number; height?: number };
type SimpleEdge = { source: string; target: string };

function layoutItems(items: LayoutItem[], edges: SimpleEdge[]): Node[] {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: 'LR', nodesep: 50, ranksep: 90 });

  items.forEach((item) => graph.setNode(item.id, { width: item.width ?? NODE_WIDTH, height: item.height ?? NODE_HEIGHT }));
  edges.forEach((edge) => {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
      graph.setEdge(edge.source, edge.target);
    }
  });
  dagre.layout(graph);

  return items.map((item) => {
    const position = graph.node(item.id) ?? { x: 0, y: 0 };
    return { id: item.id, type: item.type, position: { x: position.x, y: position.y }, data: item.data as Record<string, unknown> };
  });
}

export function toFlowNodes(nodes: GraphNode[], edges: GraphEdge[] = []): Node[] {
  const items = nodes.map((node) => ({ id: node.id, type: 'repoNode', data: node }));
  return layoutItems(items, edges);
}

export function toFlowEdges(edges: GraphEdge[]): Edge[] {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    animated: edge.kind === 'dynamic_import',
    label: edge.scope === 'top_level' ? undefined : edge.scope.replace('_', ' ')
  }));
}

export type ExternalFlowNode = { id: string; label: string; count: number; external: true };

export const EXTERNAL_PREFIX = 'external::';

export function buildExternalAdditions(nodes: GraphNode[], limit = 12): { items: LayoutItem[]; edges: Edge[] } {
  const counts = new Map<string, number>();
  nodes.forEach((node) => {
    node.external_imports.forEach((raw) => {
      const name = externalName(raw);
      counts.set(name, (counts.get(name) ?? 0) + 1);
    });
  });
  const top = new Set(
    [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, limit)
      .map(([name]) => name)
  );

  const items: LayoutItem[] = [...top].map((name) => ({
    id: EXTERNAL_PREFIX + name,
    type: 'externalNode',
    width: 150,
    height: 56,
    data: { id: EXTERNAL_PREFIX + name, label: name, count: counts.get(name) ?? 0, external: true } satisfies ExternalFlowNode
  }));

  const edges: Edge[] = [];
  nodes.forEach((node) => {
    const seen = new Set<string>();
    node.external_imports.forEach((raw) => {
      const name = externalName(raw);
      if (!top.has(name) || seen.has(name)) {
        return;
      }
      seen.add(name);
      edges.push({
        id: `ext:${node.id}->${name}`,
        source: node.id,
        target: EXTERNAL_PREFIX + name,
        className: 'external-edge'
      });
    });
  });

  return { items, edges };
}

export function buildFileFlow(nodes: GraphNode[], edges: GraphEdge[], showExternal: boolean): { flowNodes: Node[]; flowEdges: Edge[] } {
  const items: LayoutItem[] = nodes.map((node) => ({ id: node.id, type: 'repoNode', data: node }));
  const layoutEdges: SimpleEdge[] = edges.map((edge) => ({ source: edge.source, target: edge.target }));
  const flowEdges = toFlowEdges(edges);

  if (showExternal) {
    const additions = buildExternalAdditions(nodes);
    items.push(...additions.items);
    flowEdges.push(...additions.edges);
    layoutEdges.push(...additions.edges.map((edge) => ({ source: edge.source, target: edge.target })));
  }

  return { flowNodes: layoutItems(items, layoutEdges), flowEdges };
}

export function buildPackageFlow(packages: PackageSummary[], packageEdges: PackageEdge[]): { flowNodes: Node[]; flowEdges: Edge[] } {
  const items: LayoutItem[] = packages.map((pkg) => ({
    id: pkg.name,
    type: 'packageNode',
    width: 200,
    height: 96,
    data: pkg
  }));
  const flowEdges: Edge[] = packageEdges.map((edge) => ({
    id: `pkg:${edge.source}->${edge.target}`,
    source: edge.source,
    target: edge.target,
    label: String(edge.count),
    animated: false
  }));
  return { flowNodes: layoutItems(items, packageEdges), flowEdges };
}

function externalName(raw: string): string {
  const cleaned = raw.replace(/^[./]+/, '');
  if (cleaned.startsWith('@')) {
    return cleaned.split('/').slice(0, 2).join('/');
  }
  return cleaned.split('/')[0];
}
