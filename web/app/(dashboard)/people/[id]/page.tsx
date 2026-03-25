'use client';

import { use } from 'react';
import { Container, Anchor, Group, Text, Stack } from '@mantine/core';
import Link from 'next/link';
import { PersonDetail } from '@/components/people/PersonDetail';

export default function PersonDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  return (
    <Container size="lg" py="md">
      <Stack gap="md">
        <Group>
          <Anchor component={Link} href="/people" size="sm">
            <Text size="sm">&larr; Back to People</Text>
          </Anchor>
        </Group>
        <PersonDetail personId={id} />
      </Stack>
    </Container>
  );
}
