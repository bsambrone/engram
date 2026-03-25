'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Table,
  TextInput,
  Badge,
  Progress,
  Text,
  Group,
  Loader,
  Center,
  Box,
  UnstyledButton,
} from '@mantine/core';
import { useApi } from '@/hooks/useApi';
import dayjs from 'dayjs';

interface PersonRow {
  id: string;
  name: string;
  relationship_type: string | null;
  platforms: string[];
  message_count: number;
  interaction_score: number;
  connected_since: string | null;
}

const PLATFORM_COLORS: Record<string, string> = {
  gmail: 'red',
  facebook: 'blue',
  instagram: 'grape',
  reddit: 'orange',
};

type SortField = 'name' | 'message_count' | 'interaction_score' | 'connected_since';
type SortDir = 'asc' | 'desc';

function SortHeader({
  label,
  field,
  currentField,
  currentDir,
  onSort,
}: {
  label: string;
  field: SortField;
  currentField: SortField;
  currentDir: SortDir;
  onSort: (f: SortField) => void;
}) {
  const active = currentField === field;
  const arrow = active ? (currentDir === 'asc' ? ' \u25B2' : ' \u25BC') : '';
  return (
    <UnstyledButton onClick={() => onSort(field)} style={{ fontWeight: 600 }}>
      {label}
      {arrow}
    </UnstyledButton>
  );
}

export function PeopleTable() {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const apiPath = `/api/people?q=${encodeURIComponent(search)}&sort=${sortField}&limit=50&offset=0`;
  const { data, isLoading } = useApi<PersonRow[]>(apiPath);

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  }

  const sorted = useMemo(() => {
    if (!data) return [];
    const list = [...data];
    list.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'name':
          cmp = a.name.localeCompare(b.name);
          break;
        case 'message_count':
          cmp = a.message_count - b.message_count;
          break;
        case 'interaction_score':
          cmp = a.interaction_score - b.interaction_score;
          break;
        case 'connected_since':
          cmp = (a.connected_since ?? '').localeCompare(b.connected_since ?? '');
          break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [data, sortField, sortDir]);

  return (
    <Box>
      <TextInput
        placeholder="Search people..."
        value={search}
        onChange={(e) => setSearch(e.currentTarget.value)}
        mb="md"
      />

      {isLoading ? (
        <Center py="xl">
          <Loader />
        </Center>
      ) : sorted.length === 0 ? (
        <Center py="xl">
          <Text c="dimmed">No people found</Text>
        </Center>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>
                <SortHeader
                  label="Name"
                  field="name"
                  currentField={sortField}
                  currentDir={sortDir}
                  onSort={handleSort}
                />
              </Table.Th>
              <Table.Th>Relationship</Table.Th>
              <Table.Th>Platforms</Table.Th>
              <Table.Th>
                <SortHeader
                  label="Messages"
                  field="message_count"
                  currentField={sortField}
                  currentDir={sortDir}
                  onSort={handleSort}
                />
              </Table.Th>
              <Table.Th>
                <SortHeader
                  label="Interaction Score"
                  field="interaction_score"
                  currentField={sortField}
                  currentDir={sortDir}
                  onSort={handleSort}
                />
              </Table.Th>
              <Table.Th>
                <SortHeader
                  label="Connected Since"
                  field="connected_since"
                  currentField={sortField}
                  currentDir={sortDir}
                  onSort={handleSort}
                />
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sorted.map((person) => (
              <Table.Tr
                key={person.id}
                style={{ cursor: 'pointer' }}
                onClick={() => router.push(`/people/${person.id}`)}
              >
                <Table.Td>
                  <Text fw={500}>{person.name}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {person.relationship_type ?? '--'}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {person.platforms.map((p) => (
                      <Badge
                        key={p}
                        variant="light"
                        color={PLATFORM_COLORS[p.toLowerCase()] ?? 'gray'}
                        size="sm"
                      >
                        {p}
                      </Badge>
                    ))}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{person.message_count}</Text>
                </Table.Td>
                <Table.Td>
                  <Progress
                    value={person.interaction_score * 100}
                    color={
                      person.interaction_score < 0.3
                        ? 'red'
                        : person.interaction_score < 0.7
                          ? 'yellow'
                          : 'green'
                    }
                    size="sm"
                    radius="xl"
                    style={{ minWidth: 80 }}
                  />
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {person.connected_since
                      ? dayjs(person.connected_since).format('MMM D, YYYY')
                      : '--'}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Box>
  );
}
