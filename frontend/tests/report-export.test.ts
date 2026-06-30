import { describe, expect, it } from 'vitest';
import { buildCsvReport, buildJsonReport, buildMarkdownReport } from '../src/utils/reportExport';
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
  nodes: [
    {
      id: 'a.py',
      path: 'a.py',
      label: 'a.py',
      folder: '',
      extension: '.py',
      kind: 'file',
      metrics: { loc: 120, total_lines: 130, size_bytes: 1000, complexity: 12, maintainability: 54.2, risk_score: 75, dependency_count: 1, dependent_count: 2 },
      imports: ['b.py'],
      imported_by: ['tests/test_a.py'],
      unresolved_imports: ['.missing'],
      external_imports: ['os'],
      symbols: [{ name: 'run', kind: 'function', line: 10, complexity: 8 }],
      hints: [{ kind: 'security', title: 'Unsafe API pattern', detail: 'A risky API appears in source.', severity: 'medium', line: 12 }]
    }
  ],
  edges: [{ id: 'a.py->b.py:import:top_level', source: 'a.py', target: 'b.py', kind: 'import', label: 'import / top level', scope: 'top_level' }],
  folder_summaries: [{ name: 'src', files: 2, loc: 120 }],
  package_summaries: [{ name: 'src', files: 2, loc: 120, average_complexity: 4.5, average_risk: 52.5, dependency_count: 1, dependent_count: 0, highest_risk_files: ['a.py'] }],
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
    expect(markdown).toContain('risk 52.5/100');
    expect(markdown).toContain('risk 75/100');
    expect(markdown).toContain('`a.py` -> `b.py`');
    expect(markdown).toContain('Analysis limited to 2 files');
  });

  it('uses readable fallback text for empty sections', () => {
    const markdown = buildMarkdownReport({
      ...graph,
      edges: [],
      nodes: [],
      folder_summaries: [],
      package_summaries: [],
      cycles: [],
      repo_report: { start_here: [], entry_points: [], reading_order: [] },
      stats: { ...graph.stats, warnings: [] }
    });

    expect(markdown).toContain('No obvious hotspots');
    expect(markdown).toContain('No likely entry points');
    expect(markdown).toContain('Static dependency parsing only');
  });

  it('exports CSV file metrics with escaped cells', () => {
    const csv = buildCsvReport({
      ...graph,
      nodes: [{ ...graph.nodes[0], path: 'src/file,with-comma.py' }]
    });

    expect(csv).toContain('path,folder,extension,loc,complexity');
    expect(csv).toContain('"src/file,with-comma.py"');
    expect(csv).toContain('function:run:10');
    expect(csv).toContain('security:Unsafe API pattern');
  });

  it('exports full JSON graph data', () => {
    const parsed = JSON.parse(buildJsonReport(graph)) as GraphResponse;

    expect(parsed.stats.analyzed_files).toBe(2);
    expect(parsed.package_summaries?.[0].name).toBe('src');
    expect(parsed.nodes[0].symbols?.[0].name).toBe('run');
  });
});
