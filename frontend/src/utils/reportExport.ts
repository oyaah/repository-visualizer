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
    `- Git history: ${graph.git?.available ? `${graph.git.total_commits} commits read${graph.git.capped ? ' (capped)' : ''}` : 'unavailable'}`,
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
    '## Module Map',
    '',
    listOrFallback(
      (graph.package_edges ?? []).slice(0, 12).map((edge) => `- \`${edge.source}\` -> \`${edge.target}\` (${edge.count} ${edge.count === 1 ? 'dependency' : 'dependencies'})`),
      '- No cross-package dependencies found.'
    ),
    '',
    '## Routes',
    '',
    listOrFallback(
      (graph.routes ?? []).slice(0, 40).map((route) => `- \`${route.method} ${route.path}\` (${route.framework}) -> \`${route.file_path}\``),
      '- No framework routes detected.'
    ),
    '',
    '## Possibly Unused Files',
    '',
    listOrFallback(
      (graph.repo_report.orphans ?? []).map((finding) => `- \`${finding.file_path}\`: ${finding.detail}`),
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
    '## Top Packages',
    '',
    listOrFallback(
      (graph.package_summaries ?? []).slice(0, 8).map((summary) => {
        const owner = summary.primary_author ? `, owner @${summary.primary_author}` : '';
        const bus = summary.bus_factor != null ? `, bus factor ${summary.bus_factor}` : '';
        return `- \`${summary.name}\`: risk ${summary.average_risk}/100, ${summary.loc} LoC, ${summary.dependency_count} outgoing / ${summary.dependent_count} incoming package deps${owner}${bus}`;
      }),
      '- No package summaries found.'
    ),
    '',
    '## Highest Risk Files',
    '',
    listOrFallback(
      [...graph.nodes]
        .sort((a, b) => (b.metrics.risk_score ?? 0) - (a.metrics.risk_score ?? 0) || a.path.localeCompare(b.path))
        .slice(0, 8)
        .filter((node) => (node.metrics.risk_score ?? 0) > 0)
        .map((node) => `- \`${node.path}\`: risk ${node.metrics.risk_score}/100, maintainability ${node.metrics.maintainability ?? 'n/a'}, ${node.metrics.loc} LoC, Cx ${node.metrics.complexity}${node.git ? `, ${node.git.commits} commits, ${node.git.fix_commits} fixes` : ''}`),
      '- No risk signals found.'
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
  downloadText('repository-report.md', buildMarkdownReport(graph), 'text/markdown;charset=utf-8');
}

export function buildCsvReport(graph: GraphResponse): string {
  const rows = [
    ['path', 'folder', 'extension', 'loc', 'complexity', 'maintainability', 'risk_score', 'dependencies', 'dependents', 'commits', 'churn', 'fix_commits', 'primary_author', 'unresolved_imports', 'external_imports', 'symbols', 'hints'],
    ...graph.nodes.map((node) => [
      node.path,
      node.folder || 'root',
      node.extension,
      String(node.metrics.loc),
      String(node.metrics.complexity),
      String(node.metrics.maintainability ?? ''),
      String(node.metrics.risk_score ?? ''),
      String(node.metrics.dependency_count),
      String(node.metrics.dependent_count),
      String(node.git?.commits ?? ''),
      String(node.git?.churn ?? ''),
      String(node.git?.fix_commits ?? ''),
      node.git?.primary_author ?? '',
      node.unresolved_imports.join('; '),
      node.external_imports.join('; '),
      (node.symbols ?? []).map((symbol) => `${symbol.kind}:${symbol.name}:${symbol.line}`).join('; '),
      (node.hints ?? []).map((hint) => `${hint.kind}:${hint.title}`).join('; ')
    ])
  ];
  return rows.map((row) => row.map(csvCell).join(',')).join('\n') + '\n';
}

export function buildJsonReport(graph: GraphResponse): string {
  return JSON.stringify(graph, null, 2) + '\n';
}

export function downloadCsvReport(graph: GraphResponse): void {
  downloadText('repository-report.csv', buildCsvReport(graph), 'text/csv;charset=utf-8');
}

export function downloadJsonReport(graph: GraphResponse): void {
  downloadText('repository-report.json', buildJsonReport(graph), 'application/json;charset=utf-8');
}

function downloadText(filename: string, text: string, type: string): void {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function listOrFallback(items: string[], fallback: string): string {
  return items.length ? items.join('\n') : fallback;
}

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.split('"').join('""')}"` : value;
}
