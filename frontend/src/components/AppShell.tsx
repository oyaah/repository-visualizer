import type { PropsWithChildren } from 'react';

export function AppShell({ children }: PropsWithChildren) {
  return <div className="app-shell">{children}</div>;
}

