import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { NodePanel } from '../src/components/NodePanel';
import type { GraphNode } from '../src/types/graph';

const node: GraphNode = {
  id: 'src/main.py',
  path: 'src/main.py',
  label: 'main.py',
  folder: 'src',
  extension: '.py',
  kind: 'file',
  metrics: { loc: 12, total_lines: 15, size_bytes: 100, complexity: 4, dependency_count: 1, dependent_count: 2 },
  imports: ['src/utils.py'],
  imported_by: ['tests/test_main.py'],
  unresolved_imports: ['.missing'],
  external_imports: ['os']
};

describe('NodePanel', () => {
  it('shows metrics and dependency lists for selected node', () => {
    render(<NodePanel rootPath="/tmp/repo" node={node} />);
    expect(screen.getByText('main.py')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('src/utils.py')).toBeInTheDocument();
    expect(screen.getByText('tests/test_main.py')).toBeInTheDocument();
    expect(screen.getByText('os')).toBeInTheDocument();
    expect(screen.getByLabelText('AI provider')).toBeInTheDocument();
  });

  it('shows empty state without a node', () => {
    render(<NodePanel rootPath="" node={null} />);
    expect(screen.getByText('Select a file node to inspect metrics and summarize code.')).toBeInTheDocument();
  });
});
