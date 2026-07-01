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
    expect(edges.filter((edge) => edge.target === 'external::react')).toHaveLength(2);
  });
});

describe('buildPackageFlow', () => {
  it('produces package nodes and weighted edges', () => {
    const packages: PackageSummary[] = [
      { name: 'app', files: 3, loc: 100, average_complexity: 3, average_risk: 50, dependency_count: 0, dependent_count: 1, highest_risk_files: [], bus_factor: 1, primary_author: 'a', churn: 10 },
      { name: 'tests', files: 1, loc: 20, average_complexity: 1, average_risk: 5, dependency_count: 1, dependent_count: 0, highest_risk_files: [], bus_factor: 1, primary_author: 'a', churn: 2 }
    ];
    const edges: PackageEdge[] = [{ source: 'tests', target: 'app', count: 3 }];

    const { flowNodes, flowEdges } = buildPackageFlow(packages, edges);

    expect(flowNodes.map((flowNode) => flowNode.id).sort()).toEqual(['app', 'tests']);
    expect(flowNodes.every((flowNode) => flowNode.type === 'packageNode')).toBe(true);
    expect(flowEdges[0].label).toBe('3');
  });
});
