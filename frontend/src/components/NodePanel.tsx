import { useEffect, useState } from 'react';
import { Brain, FileCode2, Loader2 } from 'lucide-react';
import { summarizeFile } from '../api/client';
import type { GraphNode, SummaryResponse } from '../types/graph';

type Props = {
  rootPath: string;
  node: GraphNode | null;
};

export function NodePanel({ rootPath, node }: Props) {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [provider, setProvider] = useState('openai');

  useEffect(() => {
    if (!node || !rootPath) {
      setSummary(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setSummary(null);
    summarizeFile(rootPath, node.path, provider, true)
      .then((response) => {
        if (!cancelled) {
          setSummary(response);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setSummary(errorSummary(node.path, err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [node, provider, rootPath]);

  async function handleSummarize() {
    if (!node || !rootPath) return;
    setLoading(true);
    setSummary(null);
    try {
      setSummary(await summarizeFile(rootPath, node.path, provider, false));
    } catch (err) {
      setSummary(errorSummary(node.path, err));
    } finally {
      setLoading(false);
    }
  }

  if (!node) {
    return (
      <aside className="node-panel empty">
        <FileCode2 size={28} />
        <p>Select a file node to inspect metrics and summarize code.</p>
      </aside>
    );
  }

  return (
    <aside className="node-panel" aria-label="Selected file details">
      <div className="panel-header">
        <div>
          <span className="path-label">{node.folder || 'root'}</span>
          <h2>{node.label}</h2>
        </div>
        <span className="extension">{node.extension}</span>
      </div>

      <dl className="metrics-grid">
        <Metric label="LoC" value={node.metrics.loc} />
        <Metric label="Complexity" value={node.metrics.complexity} />
        <Metric label="Imports" value={node.metrics.dependency_count} />
        <Metric label="Used by" value={node.metrics.dependent_count} />
      </dl>

      <Section title="Dependencies" items={node.imports} fallback="No local dependencies." />
      <Section title="Dependents" items={node.imported_by} fallback="No local dependents." />
      <Section title="External / unresolved" items={[...node.external_imports, ...node.unresolved_imports]} fallback="No unresolved imports." />

      <div className="summary-box">
        <label className="provider-select">
          AI provider
          <select value={provider} onChange={(event) => setProvider(event.target.value)} disabled={loading}>
            <option value="openai">OpenAI</option>
            <option value="gemini">Gemini</option>
          </select>
        </label>
        <button className="summary-button" onClick={handleSummarize} disabled={loading}>
          {loading ? <Loader2 className="spin" size={17} /> : <Brain size={17} />}
          {loading ? 'Checking summary' : summary?.requires_generation ? 'Generate summary' : 'Refresh summary'}
        </button>
        {summary ? (
          <div className="summary-result">
            <span>{summary.cached ? 'Cached summary' : summary.disabled ? 'AI disabled' : summary.requires_generation ? 'Ready to generate' : 'Fresh summary'}</span>
            <p>{summary.summary ?? summary.error}</p>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function errorSummary(filePath: string, err: unknown): SummaryResponse {
  return {
    file_path: filePath,
    summary: null,
    cached: false,
    disabled: false,
    requires_generation: false,
    error: err instanceof Error ? err.message : 'Summary failed',
    content_hash: null,
    provider: null,
    model: null
  };
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Section({ title, items, fallback }: { title: string; items: string[]; fallback: string }) {
  return (
    <section className="panel-section">
      <h3>{title}</h3>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>{fallback}</p>
      )}
    </section>
  );
}
