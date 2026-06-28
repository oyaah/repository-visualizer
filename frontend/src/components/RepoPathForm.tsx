import { FormEvent, useState } from 'react';
import { Search } from 'lucide-react';
import type { AnalyzeOptions } from '../types/graph';

type Props = {
  loading: boolean;
  onAnalyze: (rootPath: string, options: AnalyzeOptions) => void;
};

export function RepoPathForm({ loading, onAnalyze }: Props) {
  const [rootPath, setRootPath] = useState('');
  const [maxFiles, setMaxFiles] = useState(1000);
  const [includeTests, setIncludeTests] = useState(true);
  const [includeVendor, setIncludeVendor] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (rootPath.trim()) {
      const boundedMaxFiles = Math.min(10000, Math.max(1, Number.isFinite(maxFiles) ? maxFiles : 1000));
      onAnalyze(rootPath.trim(), {
        max_files: boundedMaxFiles,
        include_tests: includeTests,
        include_vendor: includeVendor
      });
    }
  }

  return (
    <form className="repo-form" onSubmit={handleSubmit}>
      <label htmlFor="repo-path">Local repository path</label>
      <div className="repo-form-row">
        <input
          id="repo-path"
          value={rootPath}
          onChange={(event) => setRootPath(event.target.value)}
          placeholder="/Users/you/project"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !rootPath.trim()} title="Analyze repository">
          <Search size={18} />
          {loading ? 'Scanning' : 'Analyze'}
        </button>
      </div>
      <div className="scan-options" aria-label="Scan options">
        <label htmlFor="max-files">
          Max files
          <input
            id="max-files"
            type="number"
            min={1}
            max={10000}
            value={maxFiles}
            onChange={(event) => setMaxFiles(Number(event.target.value))}
            disabled={loading}
          />
        </label>
        <label className="check-option">
          <input
            type="checkbox"
            checked={includeTests}
            onChange={(event) => setIncludeTests(event.target.checked)}
            disabled={loading}
          />
          Tests
        </label>
        <label className="check-option">
          <input
            type="checkbox"
            checked={includeVendor}
            onChange={(event) => setIncludeVendor(event.target.checked)}
            disabled={loading}
          />
          Vendor
        </label>
      </div>
    </form>
  );
}
