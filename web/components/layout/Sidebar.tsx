'use client';

import { NavLink, Stack, Text, Divider } from '@mantine/core';
import { usePathname, useRouter } from 'next/navigation';

const navItems = [
  { label: 'Dashboard', emoji: '\uD83D\uDCCA', href: '/' },
  { label: 'Chat', emoji: '\uD83D\uDCAC', href: '/chat' },
  { label: 'Memories', emoji: '\uD83E\uDDE0', href: '/memories' },
  { label: 'Identity', emoji: '\uD83E\uDEAA', href: '/identity' },
  { label: 'People', emoji: '\uD83D\uDC65', href: '/people' },
  { label: 'Data', emoji: '\uD83D\uDCC2', href: '/data' },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  function isActive(href: string) {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  }

  return (
    <Stack justify="space-between" h="100%" p="sm">
      <div>
        <Text fw={700} size="lg" mb="md" pl="sm">
          Engram
        </Text>
        {navItems.map((item) => (
          <NavLink
            key={item.href}
            label={item.label}
            leftSection={<span>{item.emoji}</span>}
            active={isActive(item.href)}
            onClick={() => router.push(item.href)}
            style={{ borderRadius: 'var(--mantine-radius-md)' }}
          />
        ))}
      </div>
      <div>
        <Divider mb="sm" />
        <NavLink
          label="Settings"
          leftSection={<span>{'\u2699\uFE0F'}</span>}
          active={pathname.startsWith('/settings')}
          onClick={() => router.push('/settings')}
          style={{ borderRadius: 'var(--mantine-radius-md)' }}
        />
      </div>
    </Stack>
  );
}
