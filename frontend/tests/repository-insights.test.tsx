import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RepositoryInsights } from '../src/components/RepositoryInsights';
import type { GraphNode, GraphResponse } from '../src/types/graph';

function node(path: string, metrics: Partial<GraphNode['metrics']>, extra: Partial<GraphNode> = {}): GraphNode {
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
      complexity: 1,
      dependency_count: 0,
      dependent_count: 0,
      ...metrics
    },
    imports: [],
    imported_by: [],
    unresolved_imports: [],
    external_imports: [],
    ...extra
  };
}

const graph: GraphResponse = {
  root_path: '/tmp/repo',
  ignored_directories: [],
  stats: {
    total_files_found: 3,
    analyzed_files: 3,
    skipped_files: 2,
    skipped_reasons: { scan_policy: 2 },
    truncated: false,
    warnings: []
  },
  nodes: [
    node('src/main.py', { loc: 50, complexity: 4, dependent_count: 3 }),
    node('src/complex.py', { loc: 20, complexity: 12, dependent_count: 1 }, { unresolved_imports: ['.missing'] }),
    node('src/large.py', { loc: 120, complexity: 2, dependent_count: 0 }),
    node('tests/test_large.py', { loc: 200, complexity: 1, dependent_count: 0 })
  ],
  edges: [
    { id: 'e1', source: 'src/main.py', target: 'src/complex.py', kind: 'import', label: 'import / top level', scope: 'top_level' },
    { id: 'e2', source: 'src/large.py', target: 'src/main.py', kind: 'import', label: 'import / top level', scope: 'top_level' }
  ],
  folder_summaries: [
    { name: 'tests', files: 1, loc: 200 },
    { name: 'src', files: 3, loc: 190 }
  ],
  cycles: [{ files: ['src/complex.py', 'src/main.py'], edge_count: 2 }],
  repo_report: {
    start_here: [
      {
        kind: 'cycle',
        title: 'Dependency cycle',
        file_path: 'src/complex.py',
        detail: '2 files import each other; change these carefully.',
        severity: 'high',
        confidence: 'high',
        related_files: ['src/complex.py', 'src/main.py']
      },
      {
        kind: 'unresolved_import',
        title: 'Unresolved local import',
        file_path: 'src/complex.py',
        detail: '1 relative imports could not be mapped.',
        severity: 'medium',
        confidence: 'high',
        related_files: ['.missing']
      },
      {
        kind: 'large_file',
        title: 'Large file',
        file_path: 'tests/test_large.py',
        detail: '200 lines of code; read this early before changing nearby modules.',
        severity: 'medium',
        confidence: 'high',
        related_files: []
      }
    ],
    entry_points: [
      {
        kind: 'python_web',
        file_path: 'src/main.py',
        label: 'Likely FastAPI app',
        detail: 'Defines a FastAPI app or route.'
      }
    ],
    reading_order: ['src/main.py', 'src/complex.py', 'tests/test_large.py']
  }
};

describe('RepositoryInsights', () => {
  it('ranks repository hotspots and scan stats', () => {
    render(<RepositoryInsights graph={graph} onSelectNode={() => undefined} />);

    expect(screen.getByText('3/3 source files')).toBeInTheDocument();
    expect(screen.getByLabelText('Export Markdown report')).toBeInTheDocument();
    expect(screen.getByLabelText('Export CSV report')).toBeInTheDocument();
    expect(screen.getByLabelText('Export JSON report')).toBeInTheDocument();
    expect(screen.getByText('Edges')).toBeInTheDocument();
    expect(screen.getByText('Skipped')).toBeInTheDocument();
    expect(screen.getByText('Start here')).toBeInTheDocument();
    expect(screen.getByText('Dependency cycle')).toBeInTheDocument();
    expect(screen.getByText('Unresolved local import')).toBeInTheDocument();
    expect(screen.getByText('Large file')).toBeInTheDocument();
    expect(screen.getAllByText('high confidence').length).toBeGreaterThan(0);
    expect(screen.getByText('Likely entry points')).toBeInTheDocument();
    expect(screen.getByText('Likely FastAPI app')).toBeInTheDocument();
    expect(screen.getByText('Reading order')).toBeInTheDocument();
    expect(screen.getByText('Top folders')).toBeInTheDocument();
    expect(screen.getByText('src')).toBeInTheDocument();
    expect(screen.getByText('190 LoC / 3 files')).toBeInTheDocument();
    expect(screen.getByText('tests')).toBeInTheDocument();
    expect(screen.getByText('200 LoC / 1 file')).toBeInTheDocument();
    expect(screen.getByText('Cycles')).toBeInTheDocument();
    expect(screen.getByText('src/complex.py -> src/main.py')).toBeInTheDocument();
    expect(screen.getAllByText('2 files / 2 edges').length).toBeGreaterThan(0);
    expect(screen.getAllByText('tests/test_large.py').length).toBeGreaterThan(0);
    expect(screen.getByText('200 LoC')).toBeInTheDocument();
    expect(screen.getAllByText('src/large.py').length).toBeGreaterThan(0);
    expect(screen.getByText('120 LoC')).toBeInTheDocument();
    expect(screen.getAllByText('src/complex.py').length).toBeGreaterThan(0);
    expect(screen.getByText('Cx 12')).toBeInTheDocument();
    expect(screen.getAllByText('src/main.py').length).toBeGreaterThan(0);
    expect(screen.getByText('3 uses')).toBeInTheDocument();
  });

  it('selects a node from an insight row', () => {
    const onSelectNode = vi.fn();
    render(<RepositoryInsights graph={graph} onSelectNode={onSelectNode} />);

    fireEvent.click(screen.getByRole('button', { name: 'src/large.py 120 LoC' }));

    expect(onSelectNode).toHaveBeenCalledWith(graph.nodes[2]);
  });

  it('selects a node from the start-here queue', () => {
    const onSelectNode = vi.fn();
    render(<RepositoryInsights graph={graph} onSelectNode={onSelectNode} />);

    fireEvent.click(screen.getByRole('button', { name: 'Unresolved local import src/complex.py high confidence 1 relative imports could not be mapped.' }));

    expect(onSelectNode).toHaveBeenCalledWith(graph.nodes[1]);
  });

  it('selects the first file from a cycle row', () => {
    const onSelectNode = vi.fn();
    render(<RepositoryInsights graph={graph} onSelectNode={onSelectNode} />);

    fireEvent.click(screen.getByRole('button', { name: 'src/complex.py -> src/main.py 2 files / 2 edges' }));

    expect(onSelectNode).toHaveBeenCalledWith(graph.nodes[1]);
  });

  it('renders an empty state before analysis', () => {
    render(<RepositoryInsights graph={null} onSelectNode={() => undefined} />);

    expect(screen.getByText('Analyze a repository to see hotspots, hubs, and unresolved imports.')).toBeInTheDocument();
  });
});
