'use client';

import { Badge } from '@mantine/core';
import { useRouter } from 'next/navigation';

interface TopicTagProps {
  name: string;
}

export function TopicTag({ name }: TopicTagProps) {
  const router = useRouter();

  return (
    <Badge
      variant="light"
      color="blue"
      style={{ cursor: 'pointer' }}
      onClick={() => router.push(`/memories?topic=${encodeURIComponent(name)}`)}
    >
      {name}
    </Badge>
  );
}
