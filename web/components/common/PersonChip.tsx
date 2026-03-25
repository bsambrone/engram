'use client';

import { Badge } from '@mantine/core';
import { useRouter } from 'next/navigation';

interface PersonChipProps {
  name: string;
  id?: string;
}

export function PersonChip({ name, id }: PersonChipProps) {
  const router = useRouter();

  function handleClick() {
    if (id) {
      router.push(`/people/${encodeURIComponent(id)}`);
    } else {
      router.push(`/memories?person=${encodeURIComponent(name)}`);
    }
  }

  return (
    <Badge
      variant="light"
      color="grape"
      style={{ cursor: 'pointer' }}
      onClick={handleClick}
    >
      {name}
    </Badge>
  );
}
