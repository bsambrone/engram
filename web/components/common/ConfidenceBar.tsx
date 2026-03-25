'use client';

import { Progress, Text, Group } from '@mantine/core';

interface ConfidenceBarProps {
  value: number;
  label?: string;
}

function getColor(value: number): string {
  if (value < 0.3) return 'red';
  if (value < 0.7) return 'yellow';
  return 'green';
}

export function ConfidenceBar({ value, label }: ConfidenceBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const percent = clamped * 100;
  const color = getColor(clamped);

  return (
    <div>
      {label && (
        <Group justify="space-between" mb={4}>
          <Text size="xs" c="dimmed">
            {label}
          </Text>
          <Text size="xs" c="dimmed">
            {Math.round(percent)}%
          </Text>
        </Group>
      )}
      <Progress value={percent} color={color} size="sm" radius="xl" />
    </div>
  );
}
