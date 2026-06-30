import type { GraphResponse } from '../types/graph';

export function buildMarkdownReport(graph: GraphResponse): string {
  const lines = [
    '# Repository Report',
    '',
    `Root: \`${graph.root_path}\``,
    '',
    '## Scan',
    '',
    `- Files analyzed: ${graph.stats.analyzed_files} / ${graph.stats.total_files_found}`,
    `- Local edges: ${graph.edges.length}`,
    `- Skipped files: ${graph.stats.skipped_files}`,
    `- Truncated: ${graph.stats.truncated ? 'yes' : 'no'}`,
    '',
    '## Start Here',
    '',
    listOrFallback(
      graph.repo_report.start_here.map((finding) => `- **${finding.title}** (${finding.severity}, ${finding.confidence} confidence) - \`${finding.file_path}\`: ${finding.detail}`),
      '- No obvious hotspots in analyzed files.'
    ),
    '',
    '## Likely Entry Points',
    '',
    listOrFallback(
      graph.repo_report.entry_points.map((entry) => `- **${entry.label}** - \`${entry.file_path}\`: ${entry.detail}`),
      '- No likely entry points found.'
    ),
    '',
    '## Reading Order',
    '',
    listOrFallback(graph.repo_report.reading_order.map((path, index) => `${index + 1}. \`${path}\``), '- No reading order generated.'),
    '',
    '## Possibly Unused Files',
    '',
    listOrFallback(
      graph.repo_report.orphans.map((finding) => `- \`${finding.file_path}\`: ${finding.detail}`),
      '- No obviously unused files detected.'
    ),
    '',
    '## Top Folders',
    '',
    listOrFallback(
      graph.folder_summaries.slice(0, 8).map((folder) => `- \`${folder.name}\`: ${folder.loc} LoC across ${folder.files} ${folder.files === 1 ? 'file' : 'files'}`),
      '- No folders found.'
    ),
    '',
    '## Module Map',
    '',
    listOrFallback(
      graph.folder_dependencies.slice(0, 12).map((edge) => `- \`${edge.source}\` -> \`${edge.target}\` (${edge.edge_count} ${edge.edge_count === 1 ? 'dependency' : 'dependencies'})`),
      '- No cross-folder dependencies found.'
    ),
    '',
    '## Cycles',
    '',
    listOrFallback(
      graph.cycles.slice(0, 8).map((cycle) => `- ${cycle.files.map((file) => `\`${file}\``).join(' -> ')} (${cycle.edge_count} edges)`),
      '- No dependency cycles found.'
    ),
    '',
    '## Scan Notes',
    '',
    listOrFallback(graph.stats.warnings.map((warning) => `- ${warning}`), '- Static dependency parsing only; external packages are metadata, not graph nodes.')
  ];

  return lines.join('\n').trimEnd() + '\n';
}

export function downloadMarkdownReport(graph: GraphResponse): void {
  const blob = new Blob([buildMarkdownReport(graph)], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'repository-report.md';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function listOrFallback(items: string[], fallback: string): string {
  return items.length ? items.join('\n') : fallback;
}
