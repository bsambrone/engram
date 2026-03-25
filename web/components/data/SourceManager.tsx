'use client';

import { useState } from 'react';
import {
  Table,
  Select,
  Button,
  Group,
  Text,
  Badge,
  Loader,
  Center,
  Box,
  Stack,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { SourceInfo } from '@/lib/types';

const VISIBILITY_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'private', label: 'Private' },
  { value: 'excluded', label: 'Excluded' },
];

const VISIBILITY_COLORS: Record<string, string> = {
  active: 'green',
  private: 'yellow',
  excluded: 'red',
};

export function SourceManager() {
  const { data: sources, isLoading, mutate } = useApi<SourceInfo[]>('/api/sources');
  const [updating, setUpdating] = useState<string | null>(null);

  async function handleVisibilityChange(source: string, visibility: string) {
    setUpdating(source);
    try {
      await api.put('/api/sources/visibility', {
        source_ref: source,
        visibility,
      });
      await mutate();
      notifications.show({
        title: 'Visibility Updated',
        message: `${source} set to ${visibility}`,
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to update visibility',
        color: 'red',
      });
    } finally {
      setUpdating(null);
    }
  }

  async function handleBulkAction(source: string, visibility: string) {
    setUpdating(source);
    try {
      await api.post('/api/sources/bulk', {
        source,
        visibility,
      });
      await mutate();
      notifications.show({
        title: 'Bulk Update Complete',
        message: `All ${source} memories set to ${visibility}`,
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Bulk update failed',
        color: 'red',
      });
    } finally {
      setUpdating(null);
    }
  }

  async function handleDeleteSource(source: string) {
    setUpdating(source);
    try {
      await api.delete('/api/sources', { source_ref: source });
      await mutate();
      notifications.show({
        title: 'Source Deleted',
        message: `${source} has been removed`,
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Delete failed',
        color: 'red',
      });
    } finally {
      setUpdating(null);
    }
  }

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  if (!sources || sources.length === 0) {
    return (
      <Center py="xl">
        <Text c="dimmed">No sources found</Text>
      </Center>
    );
  }

  return (
    <Box>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Source</Table.Th>
            <Table.Th>Memories</Table.Th>
            <Table.Th>Visibility Breakdown</Table.Th>
            <Table.Th>Set Visibility</Table.Th>
            <Table.Th>Bulk Actions</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {sources.map((src) => (
            <Table.Tr key={src.source}>
              <Table.Td>
                <Text size="sm" fw={500}>
                  {src.source}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{src.memory_count}</Text>
              </Table.Td>
              <Table.Td>
                <Group gap={4}>
                  {Object.entries(src.visibility_breakdown).map(([vis, count]) => (
                    <Badge
                      key={vis}
                      variant="light"
                      color={VISIBILITY_COLORS[vis] ?? 'gray'}
                      size="sm"
                    >
                      {vis}: {count}
                    </Badge>
                  ))}
                </Group>
              </Table.Td>
              <Table.Td>
                <Select
                  data={VISIBILITY_OPTIONS}
                  placeholder="Change..."
                  size="xs"
                  w={130}
                  disabled={updating === src.source}
                  onChange={(value) => {
                    if (value) handleVisibilityChange(src.source, value);
                  }}
                />
              </Table.Td>
              <Table.Td>
                <Group gap={4}>
                  <Button
                    variant="light"
                    size="xs"
                    color="yellow"
                    loading={updating === src.source}
                    onClick={() => handleBulkAction(src.source, 'private')}
                  >
                    All Private
                  </Button>
                  <Button
                    variant="light"
                    size="xs"
                    color="red"
                    loading={updating === src.source}
                    onClick={() => handleBulkAction(src.source, 'excluded')}
                  >
                    All Excluded
                  </Button>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Box>
  );
}
