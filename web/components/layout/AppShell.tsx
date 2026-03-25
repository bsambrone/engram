'use client';

import { AppShell } from '@mantine/core';
import { useAuth } from '@/hooks/useAuth';
import { Sidebar } from './Sidebar';

export function AppShellLayout({ children }: { children: React.ReactNode }) {
  const { ready } = useAuth();
  if (!ready) return null;

  return (
    <AppShell navbar={{ width: 220, breakpoint: 'sm' }} padding="md">
      <AppShell.Navbar>
        <Sidebar />
      </AppShell.Navbar>
      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
}
