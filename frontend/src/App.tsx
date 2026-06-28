import { useState } from 'react';
import { AlertCircle, GitBranch } from 'lucide-react';
import { analyzeRepository } from './api/client';
import { AppShell } from './components/AppShell';
import { NodePanel } from './components/NodePanel';
import { RepoPathForm } from './components/RepoPathForm';
import { GraphCanvas } from './graph/GraphCanvas';
import type { GraphNode, GraphResponse } from './types/graph';

export function App() {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze(rootPath: string) {
    setLoading(true);
    setError(null);
    try {
      const response = await analyzeRepository(rootPath);
      setGraph(response);
      setSelectedNode(response.nodes[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <header className="topbar">
        <div>
          <div className="eyebrow"><GitBranch size={16} /> Repository Visualizer</div>
          <h1>Map code structure before reading every file.</h1>
        </div>
        <RepoPathForm onAnalyze={handleAnalyze} loading={loading} />
      </header>

      {error ? (
        <div className="error-banner" role="alert">
          <AlertCircle size={18} />
          {error}
        </div>
      ) : null}

      <main className="workspace">
        <GraphCanvas graph={graph} selectedNodeId={selectedNode?.id ?? null} onSelectNode={setSelectedNode} />
        <NodePanel rootPath={graph?.root_path ?? ''} node={selectedNode} />
      </main>
    </AppShell>
  );
}

