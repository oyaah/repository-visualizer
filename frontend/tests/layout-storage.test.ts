import type { Node as FlowNode } from '@xyflow/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { applyLayout, clearSavedLayout, readSavedLayout, saveNodeLayout, storageKey } from '../src/utils/layoutStorage';
import type { GraphNode } from '../src/types/graph';

const graphNodes: GraphNode[] = [
  node('src/main.py'),
  node('src/utils.py')
];

const flowNodes: FlowNode[] = [
  { id: 'src/main.py', position: { x: 0, y: 0 }, data: {}, type: 'repoNode' },
  { id: 'src/utils.py', position: { x: 100, y: 50 }, data: {}, type: 'repoNode' }
];

beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    clear: () => values.clear()
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('layoutStorage', () => {
  it('saves and reapplies a node position', () => {
    saveNodeLayout('/tmp/repo', graphNodes, 'src/main.py', { x: 42, y: 84 });

    const restored = applyLayout(flowNodes, readSavedLayout('/tmp/repo', graphNodes));

    expect(restored[0].position).toEqual({ x: 42, y: 84 });
    expect(restored[1].position).toEqual({ x: 100, y: 50 });
  });

  it('clears a saved layout', () => {
    saveNodeLayout('/tmp/repo', graphNodes, 'src/main.py', { x: 42, y: 84 });
    clearSavedLayout('/tmp/repo', graphNodes);

    expect(applyLayout(flowNodes, readSavedLayout('/tmp/repo', graphNodes))[0].position).toEqual({ x: 0, y: 0 });
  });

  it('keys layouts by repository and graph shape', () => {
    expect(storageKey('/tmp/repo', graphNodes)).not.toEqual(storageKey('/tmp/other', graphNodes));
    expect(storageKey('/tmp/repo', graphNodes)).not.toEqual(storageKey('/tmp/repo', [...graphNodes, node('src/new.py')]));
  });
});

function node(path: string): GraphNode {
  return {
    id: path,
    path,
    label: path.split('/').slice(-1)[0] ?? path,
    folder: path.includes('/') ? path.split('/').slice(0, -1).join('/') : '',
    extension: path.slice(path.lastIndexOf('.')),
    kind: 'file',
    metrics: {
      loc: 1,
      total_lines: 1,
      size_bytes: 1,
      complexity: 0,
      dependency_count: 0,
      dependent_count: 0
    },
    imports: [],
    imported_by: [],
    unresolved_imports: [],
    external_imports: []
  };
}
