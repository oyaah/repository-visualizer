import { useEffect, useMemo, useState } from 'react';
import { Brain, FileCode2, Loader2 } from 'lucide-react';
import { summarizeFile } from '../api/client';
import type { GraphNode, GraphResponse, SummaryResponse } from '../types/graph';

type Props = {
  rootPath: string;
  node: GraphNode | null;
  graph: GraphResponse | null;
};

export function NodePanel({ rootPath, node, graph }: Props) {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const impact = useMemo(() => (node && graph ? buildImpact(graph, node) : null), [graph, node]);

  useEffect(() => {
    if (!node || !rootPath) {
      setSummary(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setSummary(null);
    summarizeFile(rootPath, node.path, true)
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
  }, [node, rootPath]);

  async function handleSummarize() {
    if (!node || !rootPath) return;
    setLoading(true);
    setSummary(null);
    try {
      setSummary(await summarizeFile(rootPath, node.path, false));
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
        <Metric label="Risk" value={node.metrics.risk_score ?? 0} />
        <Metric label="Used by" value={node.metrics.dependent_count} />
      </dl>

      {node.git ? (
        <section className="panel-section git-section">
          <h3>History</h3>
          <dl className="git-grid">
            <Metric label="Commits" value={node.git.commits} />
            <Metric label="Churn" value={node.git.churn} />
            <Metric label="Bug fixes" value={node.git.fix_commits} />
            <Metric label="Authors" value={node.git.distinct_authors} />
          </dl>
          <p className="git-meta">
            {node.git.primary_author ? <>Owner <strong>@{node.git.primary_author}</strong> ({Math.round(node.git.primary_author_share * 100)}%). </> : null}
            {node.git.recency_days != null ? <>Last touched {node.git.recency_days} {node.git.recency_days === 1 ? 'day' : 'days'} ago.</> : null}
          </p>
        </section>
      ) : null}

      <Section title="Dependencies" items={node.imports} fallback="No local dependencies." />
      <Section title="Dependents" items={node.imported_by} fallback="No local dependents." />
      <SymbolSection symbols={node.symbols ?? []} />
      <HintSection hints={node.hints ?? []} />
      {impact ? (
        <section className="panel-section impact-section">
          <h3>Change impact</h3>
          <ImpactRow label="Direct" items={impact.directDependents} fallback="No direct dependents." />
          <ImpactRow label="Second order" items={impact.secondOrderDependents} fallback="No second-order dependents." />
          <ImpactRow label="Likely tests" items={impact.likelyTests} fallback="No affected tests found in the graph." />
        </section>
      ) : null}
      <Section title="External / unresolved" items={[...node.external_imports, ...node.unresolved_imports]} fallback="No unresolved imports." />

      <div className="summary-box">
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

function buildImpact(graph: GraphResponse, node: GraphNode) {
  const nodeById = new Map(graph.nodes.map((item) => [item.id, item]));
  const directDependents = unique(node.imported_by);
  const directSet = new Set(directDependents);
  const secondOrderDependents = unique(
    directDependents.flatMap((path) => nodeById.get(path)?.imported_by ?? [])
  ).filter((path) => path !== node.id && !directSet.has(path));
  const likelyTests = unique([...directDependents, ...secondOrderDependents].filter(isTestPath));

  return {
    directDependents,
    secondOrderDependents,
    likelyTests
  };
}

function unique(items: string[]): string[] {
  return [...new Set(items)].sort();
}

function isTestPath(path: string): boolean {
  const lower = path.toLowerCase();
  return /(^|\/)(__tests__|tests?|specs?)(\/|$)/.test(lower) || /(^|[._-])(test|spec)\.[jt]sx?$/.test(lower) || lower.startsWith('test_');
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

function SymbolSection({ symbols }: { symbols: NonNullable<GraphNode['symbols']> }) {
  return (
    <section className="panel-section">
      <h3>Symbol hotspots</h3>
      {symbols.length ? (
        <ul>
          {symbols.slice(0, 5).map((symbol) => (
            <li key={`${symbol.kind}:${symbol.name}:${symbol.line}`}>
              {symbol.kind} {symbol.name} <span>line {symbol.line}, Cx {symbol.complexity}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p>No symbol hotspots found.</p>
      )}
    </section>
  );
}

function HintSection({ hints }: { hints: NonNullable<GraphNode['hints']> }) {
  return (
    <section className="panel-section">
      <h3>Static hints</h3>
      {hints.length ? (
        <ul>
          {hints.map((hint) => (
            <li key={`${hint.kind}:${hint.title}:${hint.line ?? 0}`}>
              {hint.title} <span>{hint.severity}{hint.line ? `, line ${hint.line}` : ''}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p>No static hints found.</p>
      )}
    </section>
  );
}

function ImpactRow({ label, items, fallback }: { label: string; items: string[]; fallback: string }) {
  return (
    <div className="impact-row">
      <strong>{label}</strong>
      {items.length ? (
        <ul>
          {items.slice(0, 5).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>{fallback}</p>
      )}
    </div>
  );
}
