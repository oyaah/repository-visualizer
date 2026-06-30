import { describe, expect, it } from 'vitest';
import { buildMarkdownReport } from '../src/utils/reportExport';
import type { GraphResponse } from '../src/types/graph';

const graph: GraphResponse = {
  root_path: '/tmp/repo',
  ignored_directories: [],
  stats: {
    total_files_found: 3,
    analyzed_files: 2,
    skipped_files: 1,
    skipped_reasons: { max_files: 1 },
    truncated: true,
    warnings: ['Analysis limited to 2 files out of 3 eligible files.']
  },
  nodes: [],
  edges: [{ id: 'a.py->b.py:import', source: 'a.py', target: 'b.py', kind: 'import', label: 'import' }],
  folder_summaries: [{ name: 'src', files: 2, loc: 120 }],
  cycles: [{ files: ['a.py', 'b.py'], edge_count: 2 }],
  repo_report: {
    start_here: [
      {
        kind: 'cycle',
        title: 'Dependency cycle',
        file_path: 'a.py',
        detail: '2 files import each other; change these carefully.',
        severity: 'high',
        confidence: 'high',
        related_files: ['a.py', 'b.py']
      }
    ],
    entry_points: [
      {
        kind: 'python_cli',
        file_path: 'main.py',
        label: 'Likely Python CLI',
        detail: 'Contains a Python main guard.'
      }
    ],
    reading_order: ['main.py', 'a.py']
  }
};

describe('buildMarkdownReport', () => {
  it('exports scan stats and actionable report sections', () => {
    const markdown = buildMarkdownReport(graph);

    expect(markdown).toContain('# Repository Report');
    expect(markdown).toContain('Root: `/tmp/repo`');
    expect(markdown).toContain('- Files analyzed: 2 / 3');
    expect(markdown).toContain('**Dependency cycle**');
    expect(markdown).toContain('high confidence');
    expect(markdown).toContain('**Likely Python CLI**');
    expect(markdown).toContain('1. `main.py`');
    expect(markdown).toContain('`src`: 120 LoC across 2 files');
    expect(markdown).toContain('`a.py` -> `b.py`');
    expect(markdown).toContain('Analysis limited to 2 files');
  });

  it('uses readable fallback text for empty sections', () => {
    const markdown = buildMarkdownReport({
      ...graph,
      edges: [],
      folder_summaries: [],
      cycles: [],
      repo_report: { start_here: [], entry_points: [], reading_order: [] },
      stats: { ...graph.stats, warnings: [] }
    });

    expect(markdown).toContain('No obvious hotspots');
    expect(markdown).toContain('No likely entry points');
    expect(markdown).toContain('Static dependency parsing only');
  });
});
