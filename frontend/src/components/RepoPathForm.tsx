import { FormEvent, useState } from 'react';
import { Search } from 'lucide-react';

type Props = {
  loading: boolean;
  onAnalyze: (rootPath: string) => void;
};

export function RepoPathForm({ loading, onAnalyze }: Props) {
  const [rootPath, setRootPath] = useState('');

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (rootPath.trim()) {
      onAnalyze(rootPath.trim());
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
    </form>
  );
}

