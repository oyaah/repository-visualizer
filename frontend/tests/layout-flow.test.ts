import { describe, expect, it } from 'vitest';
import { buildExternalAdditions, buildPackageFlow } from '../src/graph/layout';
import type { GraphNode, PackageEdge, PackageSummary } from '../src/types/graph';

function node(path: string, external: string[]): GraphNode {
  return {
    id: path,
    path,
    label: path.split('/').slice(-1)[0] ?? path,
    folder: path.includes('/') ? path.split('/').slice(0, -1).join('/') : '',
    extension: path.slice(path.lastIndexOf('.')),
    kind: 'file',
    risk: 0,
    git: null,
    metrics: { loc: 1, total_lines: 1, size_bytes: 1, complexity: 1, dependency_count: 0, dependent_count: 0 },
    imports: [],
    imported_by: [],
    unresolved_imports: [],
    external_imports: external
  };
}

describe('buildExternalAdditions', () => {
  it('aggregates external libraries and links importers', () => {
    const nodes = [node('a.ts', ['react', 'react-dom']), node('b.ts', ['react', '@scope/pkg/sub'])];

    const { items, edges } = buildExternalAdditions(nodes);

    const ids = items.map((item) => item.id).sort();
    expect(ids).toContain('external::react');
    expect(ids).toContain('external::@scope/pkg');
    // react imported by both files -> two edges to the react node
    expect(edges.filter((edge) => edge.target === 'external::react')).toHaveLength(2);
  });
});

describe('buildPackageFlow', () => {
  it('produces package nodes and weighted edges', () => {
    const packages: PackageSummary[] = [
      { name: 'app', files: 3, loc: 100, complexity: 10, risk: 50, internal_edges: 2, incoming_edges: 1, outgoing_edges: 0, bus_factor: 1, primary_author: 'a', churn: 10 },
      { name: 'tests', files: 1, loc: 20, complexity: 1, risk: 5, internal_edges: 0, incoming_edges: 0, outgoing_edges: 1, bus_factor: 1, primary_author: 'a', churn: 2 }
    ];
    const edges: PackageEdge[] = [{ source: 'tests', target: 'app', count: 3 }];

    const { flowNodes, flowEdges } = buildPackageFlow(packages, edges);

    expect(flowNodes.map((node) => node.id).sort()).toEqual(['app', 'tests']);
    expect(flowNodes.every((node) => node.type === 'packageNode')).toBe(true);
    expect(flowEdges[0].label).toBe('3');
  });
});
