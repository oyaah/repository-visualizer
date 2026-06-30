export type FileMetrics = {
  loc: number;
  total_lines: number;
  size_bytes: number;
  complexity: number;
  maintainability?: number;
  risk_score?: number;
  dependency_count: number;
  dependent_count: number;
};

export type CodeSymbol = {
  name: string;
  kind: string;
  line: number;
  complexity: number;
};

export type CodeHint = {
  kind: string;
  title: string;
  detail: string;
  severity: string;
  line: number | null;
};

export type GraphNode = {
  id: string;
  path: string;
  label: string;
  folder: string;
  extension: string;
  kind: 'file';
  metrics: FileMetrics;
  imports: string[];
  imported_by: string[];
  unresolved_imports: string[];
  external_imports: string[];
  symbols?: CodeSymbol[];
  hints?: CodeHint[];
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  kind: 'import' | 'include' | 'dynamic_import';
  label: string;
  scope: 'top_level' | 'lazy' | 'conditional' | 'type_checking' | 're_export' | 'dynamic';
};

export type AnalyzeOptions = {
  max_files: number;
  include_tests: boolean;
  include_vendor: boolean;
};

export type GraphStats = {
  total_files_found: number;
  analyzed_files: number;
  skipped_files: number;
  skipped_reasons: Record<string, number>;
  truncated: boolean;
  warnings: string[];
};

export type FolderSummary = {
  name: string;
  files: number;
  loc: number;
};

export type PackageSummary = {
  name: string;
  files: number;
  loc: number;
  average_complexity: number;
  average_risk: number;
  dependency_count: number;
  dependent_count: number;
  highest_risk_files: string[];
};

export type CycleSummary = {
  files: string[];
  edge_count: number;
};

export type ReportFinding = {
  kind: string;
  title: string;
  file_path: string;
  detail: string;
  severity: string;
  confidence: string;
  related_files: string[];
};

export type EntryPointSummary = {
  kind: string;
  file_path: string;
  label: string;
  detail: string;
};

export type RepoReport = {
  start_here: ReportFinding[];
  entry_points: EntryPointSummary[];
  reading_order: string[];
};

export type GraphResponse = {
  root_path: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  folder_summaries: FolderSummary[];
  package_summaries?: PackageSummary[];
  cycles: CycleSummary[];
  repo_report: RepoReport;
  ignored_directories: string[];
  stats: GraphStats;
};

export type SummaryResponse = {
  file_path: string;
  summary: string | null;
  cached: boolean;
  disabled: boolean;
  requires_generation: boolean;
  error: string | null;
  content_hash: string | null;
  model: string | null;
};
