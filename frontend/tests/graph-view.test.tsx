import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
  stats: {
    total_files_found: 2,
    analyzed_files: 2,
    skipped_files: 0,
    skipped_reasons: {},
    truncated: false,
    warnings: []
  },
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
  edges: [{ id: 'e1', source: 'src/main.py', target: 'src/utils.py', kind: 'import', label: 'import / top level', scope: 'top_level' }],
  folder_summaries: [{ name: 'src', files: 2, loc: 7 }],
  cycles: [],
  repo_report: {
    start_here: [],
    entry_points: [],
    reading_order: []
  }
};

const graphWithOrphan: GraphResponse = {
  ...graph,
  stats: {
    total_files_found: 3,
    analyzed_files: 3,
    skipped_files: 0,
    skipped_reasons: {},
    truncated: false,
    warnings: []
  },
  nodes: [
    ...graph.nodes,
    {
      id: 'docs/readme.md',
      path: 'docs/readme.md',
      label: 'readme.md',
      folder: 'docs',
      extension: '.md',
      kind: 'file',
      metrics: { loc: 8, total_lines: 8, size_bytes: 80, complexity: 0, dependency_count: 0, dependent_count: 0 },
      imports: [],
      imported_by: [],
      unresolved_imports: [],
      external_imports: []
    }
  ]
};

const graphWithPresets: GraphResponse = {
  ...graph,
  stats: {
    total_files_found: 4,
    analyzed_files: 4,
    skipped_files: 0,
    skipped_reasons: {},
    truncated: false,
    warnings: []
  },
  nodes: [
    ...graph.nodes,
    {
      id: 'tests/test_main.py',
      path: 'tests/test_main.py',
      label: 'test_main.py',
      folder: 'tests',
      extension: '.py',
      kind: 'file',
      metrics: { loc: 12, total_lines: 12, size_bytes: 120, complexity: 1, dependency_count: 1, dependent_count: 0 },
      imports: ['src/main.py'],
      imported_by: [],
      unresolved_imports: [],
      external_imports: []
    },
    {
      id: 'src/large.py',
      path: 'src/large.py',
      label: 'large.py',
      folder: 'src',
      extension: '.py',
      kind: 'file',
      metrics: { loc: 100, total_lines: 100, size_bytes: 1000, complexity: 1, dependency_count: 0, dependent_count: 0 },
      imports: [],
      imported_by: [],
      unresolved_imports: [],
      external_imports: []
    }
  ],
  edges: [
    ...graph.edges,
    { id: 'e2', source: 'tests/test_main.py', target: 'src/main.py', kind: 'import', label: 'import / top level', scope: 'top_level' }
  ]
};

describe('GraphCanvas', () => {
  it('renders graph nodes and counts', () => {
    render(<GraphCanvas graph={graph} selectedNodeId={null} onSelectNode={() => undefined} />);
    expect(screen.getByText('2 of 2 files')).toBeInTheDocument();
    expect(screen.getByText('1 of 1 local edges')).toBeInTheDocument();
    expect(screen.getByText('2 analyzed / 2 found')).toBeInTheDocument();
    expect(screen.getByText('main.py')).toBeInTheDocument();
    expect(screen.getByText('utils.py')).toBeInTheDocument();
  });

  it('filters graph nodes by path query', () => {
    render(<GraphCanvas graph={graph} selectedNodeId={null} onSelectNode={() => undefined} />);

    fireEvent.change(screen.getByLabelText('Filter graph by path'), { target: { value: 'utils' } });

    expect(screen.getByText('1 of 2 files')).toBeInTheDocument();
    expect(screen.queryByText('main.py')).not.toBeInTheDocument();
    expect(screen.getByText('utils.py')).toBeInTheDocument();
  });

  it('filters graph nodes by top folder', () => {
    render(<GraphCanvas graph={graphWithOrphan} selectedNodeId={null} onSelectNode={() => undefined} />);

    fireEvent.change(screen.getByLabelText('Filter graph by folder'), { target: { value: 'docs' } });

    expect(screen.getByText('1 of 3 files')).toBeInTheDocument();
    expect(screen.queryByText('main.py')).not.toBeInTheDocument();
    expect(screen.queryByText('utils.py')).not.toBeInTheDocument();
    expect(screen.getByText('readme.md')).toBeInTheDocument();
  });

  it('filters graph nodes by preset', () => {
    render(<GraphCanvas graph={graphWithPresets} selectedNodeId={null} onSelectNode={() => undefined} />);

    fireEvent.change(screen.getByLabelText('Filter graph by preset'), { target: { value: 'hide-tests' } });

    expect(screen.getByText('3 of 4 files')).toBeInTheDocument();
    expect(screen.queryByText('test_main.py')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Filter graph by preset'), { target: { value: 'issues' } });

    expect(screen.getByText('1 of 4 files')).toBeInTheDocument();
    expect(screen.getByText('large.py')).toBeInTheDocument();
    expect(screen.queryByText('main.py')).not.toBeInTheDocument();
  });

  it('shows only one-hop related files in neighborhood mode', () => {
    render(<GraphCanvas graph={graphWithOrphan} selectedNodeId="src/main.py" onSelectNode={() => undefined} />);

    fireEvent.click(screen.getByRole('button', { name: 'Neighborhood' }));

    expect(screen.getByText('2 of 3 files')).toBeInTheDocument();
    expect(screen.getByText('main.py')).toBeInTheDocument();
    expect(screen.getByText('utils.py')).toBeInTheDocument();
    expect(screen.queryByText('readme.md')).not.toBeInTheDocument();
  });

  it('moves selection when the active node is filtered out', async () => {
    const onSelectNode = vi.fn();
    render(<GraphCanvas graph={graph} selectedNodeId="src/main.py" onSelectNode={onSelectNode} />);

    fireEvent.change(screen.getByLabelText('Filter graph by path'), { target: { value: 'utils' } });

    await waitFor(() => expect(onSelectNode).toHaveBeenCalledWith(graph.nodes[1]));
  });

  it('shows backend warnings for limited scans', () => {
    render(
      <GraphCanvas
        graph={{
          ...graph,
          stats: {
            total_files_found: 10,
            analyzed_files: 2,
            skipped_files: 8,
            skipped_reasons: { max_files: 8 },
            truncated: true,
            warnings: ['Analysis limited to 2 files out of 10 eligible files.']
          }
        }}
        selectedNodeId={null}
        onSelectNode={() => undefined}
      />
    );

    expect(screen.getByText('Limited scan')).toBeInTheDocument();
    expect(screen.getByText('Analysis limited to 2 files out of 10 eligible files.')).toBeInTheDocument();
    expect(screen.getByText('8 skipped')).toBeInTheDocument();
  });

  it('renders empty state before analysis', () => {
    render(<GraphCanvas graph={null} selectedNodeId={null} onSelectNode={() => undefined} />);
    expect(screen.getByText('No repository loaded')).toBeInTheDocument();
  });
});
