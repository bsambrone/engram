'use client';

import { useState } from 'react';
import {
  Title,
  Text,
  Container,
  SimpleGrid,
  Paper,
  Skeleton,
  Stack,
  Group,
  TextInput,
  ActionIcon,
  Anchor,
  Grid,
} from '@mantine/core';
import { DonutChart } from '@mantine/charts';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { SourceIcon } from '@/components/common/SourceIcon';
import type { MemoryStats, Memory, Belief, EngramResponse } from '@/lib/types';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

const SOURCE_COLORS: Record<string, string> = {
  gmail: 'red',
  facebook: 'blue',
  reddit: 'orange',
  instagram: 'grape',
};

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useApi<MemoryStats>('/api/memories/stats');
  const { data: memories, isLoading: memoriesLoading } = useApi<Memory[]>('/api/memories?limit=10');
  const { data: beliefs, isLoading: beliefsLoading } = useApi<Belief[]>('/api/identity/beliefs');

  const [query, setQuery] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [lastAnswer, setLastAnswer] = useState<EngramResponse | null>(null);

  const donutData = stats
    ? Object.entries(stats.by_source).map(([name, value]) => ({
        name: capitalize(name),
        value,
        color: SOURCE_COLORS[name.toLowerCase()] ?? 'gray',
      }))
    : [];

  async function handleAsk() {
    const trimmed = query.trim();
    if (!trimmed || chatLoading) return;
    setChatLoading(true);
    try {
      const res = await api.post<EngramResponse>('/api/engram/ask', { query: trimmed });
      setLastAnswer(res);
    } catch {
      setLastAnswer({
        answer: 'Something went wrong. Please try again.',
        confidence: 0,
        memory_refs: null,
        belief_refs: null,
        caveats: [],
      });
    } finally {
      setChatLoading(false);
      setQuery('');
    }
  }

  return (
    <Container size="lg" py="xl">
      <Title order={2} mb="xs">Dashboard</Title>
      <Text c="dimmed" mb="lg">Your digital engram overview.</Text>

      {/* Stats Cards Row */}
      <SimpleGrid cols={{ base: 2, sm: 4 }} mb="xl">
        <Paper p="md" radius="md" withBorder>
          {statsLoading ? (
            <Skeleton height={48} />
          ) : (
            <>
              <Text c="dimmed" size="sm">Memories</Text>
              <Title order={3}>{stats?.total_memories?.toLocaleString() ?? 0}</Title>
            </>
          )}
        </Paper>
        <Paper p="md" radius="md" withBorder>
          {statsLoading ? (
            <Skeleton height={48} />
          ) : (
            <>
              <Text c="dimmed" size="sm">People</Text>
              <Title order={3}>{stats?.person_count?.toLocaleString() ?? 0}</Title>
            </>
          )}
        </Paper>
        <Paper p="md" radius="md" withBorder>
          {beliefsLoading ? (
            <Skeleton height={48} />
          ) : (
            <>
              <Text c="dimmed" size="sm">Beliefs</Text>
              <Title order={3}>{beliefs?.length?.toLocaleString() ?? 0}</Title>
            </>
          )}
        </Paper>
        <Paper p="md" radius="md" withBorder>
          {statsLoading ? (
            <Skeleton height={48} />
          ) : (
            <>
              <Text c="dimmed" size="sm">Topics</Text>
              <Title order={3}>{stats?.topic_count?.toLocaleString() ?? 0}</Title>
            </>
          )}
        </Paper>
      </SimpleGrid>

      {/* Donut Chart */}
      <Paper p="md" radius="md" withBorder mb="xl">
        <Title order={4} mb="md">Source Breakdown</Title>
        {statsLoading ? (
          <Skeleton height={200} />
        ) : donutData.length > 0 ? (
          <DonutChart data={donutData} tooltipDataSource="segment" mx="auto" />
        ) : (
          <Text c="dimmed" ta="center" py="xl">No source data available.</Text>
        )}
      </Paper>

      {/* Two column layout: Recent Memories | Quick Chat */}
      <Grid gutter="xl">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Title order={4} mb="md">Recent Memories</Title>
          {memoriesLoading ? (
            <Stack gap="sm">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} height={72} radius="md" />
              ))}
            </Stack>
          ) : memories && memories.length > 0 ? (
            <Stack gap="sm">
              {memories.map((memory) => (
                <Paper
                  key={memory.id}
                  p="sm"
                  radius="md"
                  withBorder
                  component="a"
                  href={`/memories/${memory.id}`}
                  style={{ textDecoration: 'none', cursor: 'pointer' }}
                >
                  <Group gap="sm" mb={4}>
                    <SourceIcon source={memory.source ?? 'unknown'} size="sm" />
                    <Text size="xs" c="dimmed">
                      {memory.timestamp
                        ? dayjs(memory.timestamp).fromNow()
                        : 'Unknown date'}
                    </Text>
                  </Group>
                  <Text size="sm" lineClamp={2}>
                    {memory.content.length > 100
                      ? memory.content.slice(0, 100) + '...'
                      : memory.content}
                  </Text>
                </Paper>
              ))}
            </Stack>
          ) : (
            <Text c="dimmed">No memories yet.</Text>
          )}
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 5 }}>
          <Title order={4} mb="md">Quick Chat</Title>
          <Paper p="md" radius="md" withBorder>
            <Group gap="xs" mb="md">
              <TextInput
                placeholder="Ask your engram..."
                value={query}
                onChange={(e) => setQuery(e.currentTarget.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleAsk();
                }}
                style={{ flex: 1 }}
                disabled={chatLoading}
              />
              <ActionIcon
                variant="filled"
                size="lg"
                onClick={handleAsk}
                loading={chatLoading}
                aria-label="Send"
              >
                <span style={{ fontSize: 16 }}>&#x27A4;</span>
              </ActionIcon>
            </Group>

            {lastAnswer && (
              <Paper p="sm" radius="sm" bg="dark.6" mb="md">
                <Text size="sm">{lastAnswer.answer}</Text>
                {lastAnswer.caveats.length > 0 && (
                  <Text size="xs" c="dimmed" mt="xs">
                    Caveats: {lastAnswer.caveats.join(', ')}
                  </Text>
                )}
              </Paper>
            )}

            <Anchor href="/chat" size="sm">
              Open full chat &rarr;
            </Anchor>
          </Paper>
        </Grid.Col>
      </Grid>
    </Container>
  );
}
