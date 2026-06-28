import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { GraphCanvas } from '../src/graph/GraphCanvas';
import type { GraphResponse } from '../src/types/graph';

vi.mock('@xyflow/react', async () => {
  const actual = await vi.importActual<typeof import('@xyflow/react')>('@xyflow/react');
  return {
    ...actual,
    ReactFlow: ({ nodes }: { nodes: Array<{ id: string; data: { label: string } }> }) => (
      <div>{nodes.map((node) => <div key={node.id}>{node.data.label}</div>)}</div>
    ),
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    Handle: () => null
  };
});

const graph: GraphResponse = {
  root_path: '/tmp/repo',
  ignored_directories: [],
  nodes: [
    {
      id: 'src/main.py',
      path: 'src/main.py',
      label: 'main.py',
      folder: 'src',
      extension: '.py',
      kind: 'file',
      metrics: { loc: 5, total_lines: 5, size_bytes: 20, complexity: 1, dependency_count: 1, dependent_count: 0 },
      imports: ['src/utils.py'],
      imported_by: [],
      unresolved_imports: [],
      external_imports: []
    },
    {
      id: 'src/utils.py',
      path: 'src/utils.py',
      label: 'utils.py',
      folder: 'src',
      extension: '.py',
      kind: 'file',
      metrics: { loc: 2, total_lines: 2, size_bytes: 10, complexity: 1, dependency_count: 0, dependent_count: 1 },
      imports: [],
      imported_by: ['src/main.py'],
      unresolved_imports: [],
      external_imports: []
    }
  ],
  edges: [{ id: 'e1', source: 'src/main.py', target: 'src/utils.py', kind: 'import', label: 'import' }]
};

describe('GraphCanvas', () => {
  it('renders graph nodes and counts', () => {
    render(<GraphCanvas graph={graph} selectedNodeId={null} onSelectNode={() => undefined} />);
    expect(screen.getByText('2 files')).toBeInTheDocument();
    expect(screen.getByText('1 local edges')).toBeInTheDocument();
    expect(screen.getByText('main.py')).toBeInTheDocument();
    expect(screen.getByText('utils.py')).toBeInTheDocument();
  });

  it('renders empty state before analysis', () => {
    render(<GraphCanvas graph={null} selectedNodeId={null} onSelectNode={() => undefined} />);
    expect(screen.getByText('No repository loaded')).toBeInTheDocument();
  });
});

