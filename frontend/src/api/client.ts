import type { AnalyzeOptions, GraphResponse, SummaryResponse } from '../types/graph';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

export function analyzeRepository(rootPath: string, options: AnalyzeOptions): Promise<GraphResponse> {
  return postJson<GraphResponse>('/api/analyze', { root_path: rootPath, ...options });
}

export function summarizeFile(rootPath: string, filePath: string, provider = 'openai', cacheOnly = false): Promise<SummaryResponse> {
  return postJson<SummaryResponse>('/api/summarize', {
    root_path: rootPath,
    file_path: filePath,
    provider,
    cache_only: cacheOnly
  });
}
