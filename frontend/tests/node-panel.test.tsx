import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NodePanel } from '../src/components/NodePanel';
import type { GraphNode, GraphResponse } from '../src/types/graph';
import { summarizeFile } from '../src/api/client';

vi.mock('../src/api/client', () => ({
  summarizeFile: vi.fn()
}));

const summarizeMock = vi.mocked(summarizeFile);

const node: GraphNode = {
  id: 'src/main.py',
  path: 'src/main.py',
  label: 'main.py',
  folder: 'src',
  extension: '.py',
  kind: 'file',
  risk: 0,
  git: null,
  metrics: { loc: 12, total_lines: 15, size_bytes: 100, complexity: 4, dependency_count: 1, dependent_count: 2 },
  imports: ['src/utils.py'],
  imported_by: ['tests/test_main.py'],
  unresolved_imports: ['.missing'],
  external_imports: ['os']
};

const graph: GraphResponse = {
  root_path: '/tmp/repo',
  packages: [],
  package_edges: [],
  git: { available: false, total_commits: 0, capped: false, note: null },
  ignored_directories: [],
  stats: {
    total_files_found: 4,
    analyzed_files: 4,
    skipped_files: 0,
    skipped_reasons: {},
    truncated: false,
    warnings: []
  },
  nodes: [
    node,
    {
      ...node,
      id: 'tests/test_main.py',
      path: 'tests/test_main.py',
      label: 'test_main.py',
      folder: 'tests',
      imports: ['src/main.py'],
      imported_by: ['tests/test_flow.py']
    },
    {
      ...node,
      id: 'tests/test_flow.py',
      path: 'tests/test_flow.py',
      label: 'test_flow.py',
      folder: 'tests',
      imports: ['tests/test_main.py'],
      imported_by: []
    },
    {
      ...node,
      id: 'src/utils.py',
      path: 'src/utils.py',
      label: 'utils.py',
      imports: [],
      imported_by: ['src/main.py']
    }
  ],
  edges: [
    { id: 'src/main.py->src/utils.py:import', source: 'src/main.py', target: 'src/utils.py', kind: 'import', label: 'import' },
    { id: 'tests/test_main.py->src/main.py:import', source: 'tests/test_main.py', target: 'src/main.py', kind: 'import', label: 'import' },
    { id: 'tests/test_flow.py->tests/test_main.py:import', source: 'tests/test_flow.py', target: 'tests/test_main.py', kind: 'import', label: 'import' }
  ],
  folder_summaries: [],
  cycles: [],
  repo_report: {
    start_here: [],
    entry_points: [],
    reading_order: []
  }
};

describe('NodePanel', () => {
  beforeEach(() => {
    summarizeMock.mockReset();
    summarizeMock.mockResolvedValue({
      file_path: node.path,
      summary: null,
      cached: false,
      disabled: true,
      requires_generation: false,
      error: 'Set OPENAI_API_KEY to enable OpenAI summaries.',
      content_hash: 'hash',
      model: 'gpt-4.1-mini'
    });
  });

  it('shows metrics and dependency lists for selected node', () => {
    render(<NodePanel rootPath="/tmp/repo" node={node} graph={graph} />);
    expect(screen.getByText('main.py')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('src/utils.py')).toBeInTheDocument();
    expect(screen.getAllByText('tests/test_main.py').length).toBeGreaterThan(0);
    expect(screen.getByText('os')).toBeInTheDocument();
  });

  it('loads summary state when a node is selected', async () => {
    render(<NodePanel rootPath="/tmp/repo" node={node} graph={graph} />);

    await waitFor(() => expect(summarizeMock).toHaveBeenCalledWith('/tmp/repo', 'src/main.py', true));
    expect(await screen.findByText('AI disabled')).toBeInTheDocument();
    expect(screen.getByText('Set OPENAI_API_KEY to enable OpenAI summaries.')).toBeInTheDocument();
  });

  it('shows cached summaries without a manual click', async () => {
    summarizeMock.mockResolvedValue({
      file_path: node.path,
      summary: 'Reads command line input and starts the app.',
      cached: true,
      disabled: false,
      requires_generation: false,
      error: null,
      content_hash: 'hash',
      model: 'gpt-4.1-mini'
    });

    render(<NodePanel rootPath="/tmp/repo" node={node} graph={graph} />);

    expect(await screen.findByText('Cached summary')).toBeInTheDocument();
    expect(screen.getByText('Reads command line input and starts the app.')).toBeInTheDocument();
  });

  it('generates a fresh summary from the button when needed', async () => {
    summarizeMock
      .mockResolvedValueOnce({
        file_path: node.path,
        summary: null,
        cached: false,
        disabled: false,
        requires_generation: true,
        error: 'No cached summary yet. Generate one to analyze this file.',
        content_hash: 'hash',
        model: 'gpt-4.1-mini'
      })
      .mockResolvedValueOnce({
        file_path: node.path,
        summary: 'Fresh summary text.',
        cached: false,
        disabled: false,
        requires_generation: false,
        error: null,
        content_hash: 'hash',
        model: 'gpt-4.1-mini'
      });

    render(<NodePanel rootPath="/tmp/repo" node={node} graph={graph} />);

    const button = await screen.findByRole('button', { name: 'Generate summary' });
    fireEvent.click(button);

    await waitFor(() => expect(summarizeMock).toHaveBeenLastCalledWith('/tmp/repo', 'src/main.py', false));
    expect(await screen.findByText('Fresh summary')).toBeInTheDocument();
    expect(screen.getByText('Fresh summary text.')).toBeInTheDocument();
  });

  it('shows empty state without a node', () => {
    render(<NodePanel rootPath="" node={null} graph={null} />);
    expect(screen.getByText('Select a file node to inspect metrics and summarize code.')).toBeInTheDocument();
  });

  it('shows direct and second-order change impact', () => {
    render(<NodePanel rootPath="/tmp/repo" node={node} graph={graph} />);

    expect(screen.getByText('Change impact')).toBeInTheDocument();
    expect(screen.getByText('Direct')).toBeInTheDocument();
    expect(screen.getByText('Second order')).toBeInTheDocument();
    expect(screen.getAllByText('tests/test_main.py').length).toBeGreaterThan(0);
    expect(screen.getAllByText('tests/test_flow.py').length).toBeGreaterThan(0);
    expect(screen.getByText('Likely tests')).toBeInTheDocument();
  });
});
