'use client';

import { Box, Text, Center, Loader } from '@mantine/core';
import { LineChart } from '@mantine/charts';
import { useApi } from '@/hooks/useApi';
import type { BeliefVersion } from '@/lib/types';
import dayjs from 'dayjs';

interface BeliefTimelineProps {
  topic: string | null;
}

export function BeliefTimeline({ topic }: BeliefTimelineProps) {
  const { data, isLoading } = useApi<BeliefVersion[]>(
    topic ? `/api/identity/timeline?topic=${encodeURIComponent(topic)}` : null
  );

  if (!topic) {
    return (
      <Center py="md">
        <Text size="sm" c="dimmed">Select a topic to view its timeline</Text>
      </Center>
    );
  }

  if (isLoading) {
    return (
      <Center py="md">
        <Loader size="sm" />
      </Center>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Center py="md">
        <Text size="sm" c="dimmed">No timeline data for this topic</Text>
      </Center>
    );
  }

  const chartData = data.map((v) => ({
    date: v.valid_from ? dayjs(v.valid_from).format('YYYY-MM-DD') : 'Unknown',
    confidence: v.confidence ?? 0,
    stance: v.stance ?? '',
  }));

  return (
    <Box>
      <Text size="sm" fw={600} mb="xs">
        Belief confidence over time: {topic}
      </Text>
      <LineChart
        h={250}
        data={chartData}
        dataKey="date"
        series={[{ name: 'confidence', color: 'blue.6' }]}
        curveType="monotone"
        yAxisProps={{ domain: [0, 1] }}
        tooltipProps={{
          content: ({ payload }) => {
            if (!payload || payload.length === 0) return null;
            const item = payload[0]?.payload as { date: string; confidence: number; stance: string } | undefined;
            if (!item) return null;
            return (
              <Box
                p="xs"
                style={{
                  background: 'var(--mantine-color-dark-7)',
                  border: '1px solid var(--mantine-color-dark-4)',
                  borderRadius: 4,
                }}
              >
                <Text size="xs" fw={600}>{item.date}</Text>
                <Text size="xs">Confidence: {(item.confidence * 100).toFixed(0)}%</Text>
                {item.stance && <Text size="xs" c="dimmed">{item.stance}</Text>}
              </Box>
            );
          },
        }}
      />
    </Box>
  );
}
