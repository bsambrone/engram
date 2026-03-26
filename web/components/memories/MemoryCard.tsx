'use client';

import { useState } from 'react';
import { Paper, Group, Text, Stack, Spoiler, Box, Badge, SimpleGrid } from '@mantine/core';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { SourceIcon, ConfidenceBar, TopicTag, PersonChip } from '@/components/common';
import { MemoryActions } from './MemoryActions';
import type { Memory } from '@/lib/types';

dayjs.extend(relativeTime);

interface MemoryCardProps {
  memory: Memory;
  onUpdate?: () => void;
}

export function MemoryCard({ memory, onUpdate }: MemoryCardProps) {
  const [expanded, setExpanded] = useState(false);

  const relTime = memory.timestamp ? dayjs(memory.timestamp).fromNow() : 'Unknown date';
  const truncated =
    memory.content.length > 150 ? memory.content.slice(0, 150) + '...' : memory.content;

  return (
    <Paper
      p="md"
      radius="md"
      withBorder
      style={{ cursor: 'pointer', transition: 'background 150ms ease' }}
      onClick={() => setExpanded((prev) => !prev)}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.background = 'var(--mantine-color-dark-5)';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.background = '';
      }}
    >
      {/* Compact view */}
      <Group align="flex-start" gap="sm" wrap="nowrap">
        {memory.source && <SourceIcon source={memory.source} size="md" />}
        <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
          <Group justify="space-between" gap="xs">
            <Text size="xs" c="dimmed">
              {relTime}
            </Text>
            {memory.importance_score != null && (
              <Box w={80}>
                <ConfidenceBar value={memory.importance_score} />
              </Box>
            )}
          </Group>

          {expanded ? (
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
              {memory.content}
            </Text>
          ) : (
            <Text size="sm">{truncated}</Text>
          )}

          <Group gap={4} wrap="wrap">
            {(expanded ? (memory.topics || []) : (memory.topics || []).slice(0, 3)).map((t) => (
              <TopicTag key={typeof t === 'string' ? t : t.id} name={typeof t === 'string' ? t : t.name} />
            ))}
            {!expanded && (memory.topics || []).length > 3 && (
              <Badge variant="light" color="gray" size="sm">
                +{memory.topics.length - 3}
              </Badge>
            )}
          </Group>

          <Group gap={4} wrap="wrap">
            {(expanded ? (memory.people || []) : (memory.people || []).slice(0, 2)).map((p) => (
              <PersonChip key={typeof p === 'string' ? p : p.id} name={typeof p === 'string' ? p : p.name} id={typeof p === 'string' ? undefined : p.id} />
            ))}
            {!expanded && (memory.people || []).length > 2 && (
              <Badge variant="light" color="gray" size="sm">
                +{memory.people.length - 2}
              </Badge>
            )}
          </Group>
        </Stack>
      </Group>

      {/* Expanded view */}
      {expanded && (
        <Box mt="md" pt="md" style={{ borderTop: '1px solid var(--mantine-color-dark-4)' }}>
          <Stack gap="sm">
            {memory.intent && (
              <Box>
                <Text size="xs" fw={600} c="dimmed">
                  Intent
                </Text>
                <Text size="sm">{memory.intent}</Text>
              </Box>
            )}
            {memory.meaning && (
              <Box>
                <Text size="xs" fw={600} c="dimmed">
                  Meaning
                </Text>
                <Text size="sm">{memory.meaning}</Text>
              </Box>
            )}

            <SimpleGrid cols={3} spacing="sm">
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
                  Status / Visibility
                </Text>
                <Group gap={4}>
                  <Badge size="sm" variant="light">
                    {memory.status}
                  </Badge>
                  <Badge size="sm" variant="light" color="gray">
                    {memory.visibility}
                  </Badge>
                </Group>
              </Box>
            </SimpleGrid>

            <Box onClick={(e) => e.stopPropagation()}>
              <MemoryActions memory={memory} onUpdate={onUpdate} />
            </Box>
          </Stack>
        </Box>
      )}
    </Paper>
  );
}
