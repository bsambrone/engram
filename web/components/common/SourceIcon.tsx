'use client';

import { ThemeIcon } from '@mantine/core';

const SOURCE_ICONS: Record<string, string> = {
  gmail: '\u{1F4E7}',
  reddit: '\u{1F4AC}',
  facebook: '\u{1F4D8}',
  instagram: '\u{1F4F8}',
  file: '\u{1F4C4}',
  generated: '\u{1F3A8}',
};

const DEFAULT_ICON = '\u{1F4DD}';

interface SourceIconProps {
  source: string;
  size?: number | 'xs' | 'sm' | 'md' | 'lg' | 'xl';
}

export function SourceIcon({ source, size = 'md' }: SourceIconProps) {
  const emoji = SOURCE_ICONS[source.toLowerCase()] ?? DEFAULT_ICON;

  return (
    <ThemeIcon variant="light" size={size} radius="xl" color="gray">
      <span style={{ fontSize: typeof size === 'number' ? size * 0.6 : undefined }}>
        {emoji}
      </span>
    </ThemeIcon>
  );
}
