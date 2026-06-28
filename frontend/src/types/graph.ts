export type FileMetrics = {
  loc: number;
  total_lines: number;
  size_bytes: number;
  complexity: number;
  dependency_count: number;
  dependent_count: number;
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
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  kind: 'import' | 'include' | 'dynamic_import';
  label: string;
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
  truncated: boolean;
  warnings: string[];
};

export type GraphResponse = {
  root_path: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  ignored_directories: string[];
  stats: GraphStats;
};

export type SummaryResponse = {
  file_path: string;
  summary: string | null;
  cached: boolean;
  disabled: boolean;
  error: string | null;
  content_hash: string | null;
  provider: string | null;
  model: string | null;
};
