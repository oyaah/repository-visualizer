import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RepoPathForm } from '../src/components/RepoPathForm';

describe('RepoPathForm', () => {
  it('submits repository path with scan options', () => {
    const onAnalyze = vi.fn();
    render(<RepoPathForm loading={false} onAnalyze={onAnalyze} />);

    fireEvent.change(screen.getByLabelText('Local repository path'), { target: { value: '/tmp/repo' } });
    fireEvent.change(screen.getByLabelText('Max files'), { target: { value: '250' } });
    fireEvent.click(screen.getByLabelText('Tests'));
    fireEvent.click(screen.getByLabelText('Vendor'));
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    expect(onAnalyze).toHaveBeenCalledWith('/tmp/repo', {
      max_files: 250,
      include_tests: false,
      include_vendor: true
    });
  });
});
