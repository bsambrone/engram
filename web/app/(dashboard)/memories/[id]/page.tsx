'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';
import {
  Container,
  Title,
  Text,
  Stack,
  Group,
  Paper,
  Badge,
  Anchor,
  Box,
  SimpleGrid,
  Loader,
  Center,
} from '@mantine/core';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useApi } from '@/hooks/useApi';
import { SourceIcon, ConfidenceBar, TopicTag, PersonChip } from '@/components/common';
import { MemoryActions } from '@/components/memories/MemoryActions';
import type { Memory } from '@/lib/types';

dayjs.extend(relativeTime);

interface MemoryDetailData extends Memory {
  parent_memory_id?: string | null;
  interaction_context?: string | null;
  children?: Memory[];
}

export default function MemoryDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: memory, isLoading, mutate } = useApi<MemoryDetailData>(
    `/api/memories/${id}`
  );

  if (isLoading) {
    return (
      <Container size="md" py="xl">
        <Center>
          <Loader />
        </Center>
      </Container>
    );
  }

  if (!memory) {
    return (
      <Container size="md" py="xl">
        <Text c="dimmed">Memory not found</Text>
      </Container>
    );
  }

  const relTime = memory.timestamp ? dayjs(memory.timestamp).fromNow() : 'Unknown date';
  const absTime = memory.timestamp
    ? dayjs(memory.timestamp).format('YYYY-MM-DD HH:mm')
    : null;

  return (
    <Container size="md" py="md">
      <Stack gap="md">
        <Anchor
          size="sm"
          c="dimmed"
          onClick={() => router.push('/memories')}
          style={{ cursor: 'pointer' }}
        >
          &larr; Back to memories
        </Anchor>

        <Paper p="lg" radius="md" withBorder>
          <Stack gap="md">
            {/* Header */}
            <Group justify="space-between" align="flex-start">
              <Group gap="sm">
                {memory.source && <SourceIcon source={memory.source} size="lg" />}
                <Box>
                  <Text size="sm" c="dimmed">
                    {relTime} {absTime && `(${absTime})`}
                  </Text>
                  {memory.source && (
                    <Text size="xs" c="dimmed">
                      Source: {memory.source}
                      {memory.source_ref && ` - ${memory.source_ref}`}
                    </Text>
                  )}
                  {memory.authorship && (
                    <Text size="xs" c="dimmed">
                      Authorship: {memory.authorship}
                    </Text>
                  )}
                </Box>
              </Group>
              <Group gap={4}>
                <Badge variant="light">{memory.status}</Badge>
                <Badge variant="light" color="gray">
                  {memory.visibility}
                </Badge>
              </Group>
            </Group>

            {/* Content */}
            <Box>
              <Text size="xs" fw={600} c="dimmed" mb={4}>
                Content
              </Text>
              <Text style={{ whiteSpace: 'pre-wrap' }}>{memory.content}</Text>
            </Box>

            {/* Intent & Meaning */}
            {memory.intent && (
              <Box>
                <Text size="xs" fw={600} c="dimmed" mb={4}>
                  Intent
                </Text>
                <Text size="sm">{memory.intent}</Text>
              </Box>
            )}
            {memory.meaning && (
              <Box>
                <Text size="xs" fw={600} c="dimmed" mb={4}>
                  Meaning
                </Text>
                <Text size="sm">{memory.meaning}</Text>
              </Box>
            )}
            {memory.interaction_context && (
              <Box>
                <Text size="xs" fw={600} c="dimmed" mb={4}>
                  Interaction Context
                </Text>
                <Text size="sm">{memory.interaction_context}</Text>
              </Box>
            )}

            {/* Metrics */}
            <SimpleGrid cols={4} spacing="sm">
              {memory.importance_score != null && (
                <Box>
                  <Text size="xs" c="dimmed" mb={4}>
                    Importance
                  </Text>
                  <ConfidenceBar value={memory.importance_score} />
                </Box>
              )}
              {memory.confidence != null && (
                <Box>
                  <Text size="xs" c="dimmed" mb={4}>
                    Confidence
                  </Text>
                  <ConfidenceBar value={memory.confidence} />
                </Box>
              )}
              <Box>
                <Text size="xs" c="dimmed">
                  Reinforcements
                </Text>
                <Text size="sm" fw={500}>
                  {memory.reinforcement_count}
                </Text>
              </Box>
              <Box>
                <Text size="xs" c="dimmed">
                  Created
                </Text>
                <Text size="sm">
                  {memory.created_at ? dayjs(memory.created_at).format('YYYY-MM-DD') : 'N/A'}
                </Text>
              </Box>
            </SimpleGrid>

            {/* Topics */}
            {memory.topics.length > 0 && (
              <Box>
                <Text size="xs" fw={600} c="dimmed" mb={4}>
                  Topics
                </Text>
                <Group gap={4} wrap="wrap">
                  {memory.topics.map((t) => (
                    <TopicTag key={t.id} name={t.name} />
                  ))}
                </Group>
              </Box>
            )}

            {/* People */}
            {memory.people.length > 0 && (
              <Box>
                <Text size="xs" fw={600} c="dimmed" mb={4}>
                  People
                </Text>
                <Group gap={4} wrap="wrap">
                  {memory.people.map((p) => (
                    <PersonChip key={p.id} name={p.name} id={p.id} />
                  ))}
                </Group>
              </Box>
            )}

            {/* Evolution chain */}
            {memory.parent_memory_id && (
              <Box>
                <Text size="xs" fw={600} c="dimmed" mb={4}>
                  Evolved from
                </Text>
                <Anchor
                  size="sm"
                  onClick={() => router.push(`/memories/${memory.parent_memory_id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  Parent memory: {memory.parent_memory_id}
                </Anchor>
              </Box>
            )}
            {memory.children && memory.children.length > 0 && (
              <Box>
                <Text size="xs" fw={600} c="dimmed" mb={4}>
                  Evolved into
                </Text>
                <Stack gap={4}>
                  {memory.children.map((child) => (
                    <Anchor
                      key={child.id}
                      size="sm"
                      onClick={() => router.push(`/memories/${child.id}`)}
                      style={{ cursor: 'pointer' }}
                    >
                      {child.content.slice(0, 100)}
                      {child.content.length > 100 ? '...' : ''}
                    </Anchor>
                  ))}
                </Stack>
              </Box>
            )}

            {/* Actions */}
            <MemoryActions memory={memory} onUpdate={() => mutate()} />
          </Stack>
        </Paper>
      </Stack>
    </Container>
  );
}
