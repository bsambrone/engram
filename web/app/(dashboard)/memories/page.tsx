'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  Title,
  Container,
  Stack,
  Group,
  Text,
  Badge,
  Button,
  Loader,
  Center,
  Box,
} from '@mantine/core';
import { api } from '@/lib/api';
import { useApi } from '@/hooks/useApi';
import type { Memory, MemoryStats } from '@/lib/types';
import { MemoryFilters, type MemoryFilterValues } from '@/components/memories/MemoryFilters';
import { MemoryCard } from '@/components/memories/MemoryCard';

const PAGE_SIZE = 20;

function formatDate(d: Date | null): string {
  if (!d) return '';
  return d.toISOString().split('T')[0];
}

function buildQueryString(filters: MemoryFilterValues, offset: number): string {
  const params = new URLSearchParams();
  if (filters.q) params.set('q', filters.q);
  if (filters.sources.length > 0) params.set('sources', filters.sources.join(','));
  if (filters.visibility) params.set('visibility', filters.visibility);
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.dateRange[0]) params.set('date_from', formatDate(filters.dateRange[0]));
  if (filters.dateRange[1]) params.set('date_to', formatDate(filters.dateRange[1]));
  params.set('limit', String(PAGE_SIZE));
  params.set('offset', String(offset));
  return params.toString();
}

export default function MemoriesPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // Initialize filters from URL search params
  const [filters, setFilters] = useState<MemoryFilterValues>(() => ({
    q: searchParams.get('q') ?? searchParams.get('topic') ?? searchParams.get('person') ?? '',
    sources: searchParams.get('sources')?.split(',').filter(Boolean) ?? [],
    visibility: searchParams.get('visibility') ?? '',
    sort: searchParams.get('sort') ?? 'date',
    dateRange: [null, null],
  }));

  const [memories, setMemories] = useState<Memory[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [initialLoad, setInitialLoad] = useState(true);

  const { data: stats } = useApi<MemoryStats>('/api/memories/stats');

  const fetchMemories = useCallback(
    async (currentFilters: MemoryFilterValues, currentOffset: number, append: boolean) => {
      setLoading(true);
      try {
        const qs = buildQueryString(currentFilters, currentOffset);
        const data = await api.get<Memory[]>(`/api/memories?${qs}`);
        if (append) {
          setMemories((prev) => [...prev, ...data]);
        } else {
          setMemories(data);
        }
        setHasMore(data.length >= PAGE_SIZE);
      } catch {
        // Error is handled by api client (401 redirect etc.)
      } finally {
        setLoading(false);
        setInitialLoad(false);
      }
    },
    []
  );

  // Fetch on mount and when filters change
  useEffect(() => {
    setOffset(0);
    fetchMemories(filters, 0, false);

    // Sync filters to URL
    const params = new URLSearchParams();
    if (filters.q) params.set('q', filters.q);
    if (filters.sources.length > 0) params.set('sources', filters.sources.join(','));
    if (filters.visibility) params.set('visibility', filters.visibility);
    if (filters.sort && filters.sort !== 'date') params.set('sort', filters.sort);
    const qs = params.toString();
    router.replace(qs ? `/memories?${qs}` : '/memories', { scroll: false });
  }, [filters, fetchMemories, router]);

  function handleLoadMore() {
    const nextOffset = offset + PAGE_SIZE;
    setOffset(nextOffset);
    fetchMemories(filters, nextOffset, true);
  }

  function handleUpdate() {
    // Re-fetch current page from scratch
    setOffset(0);
    fetchMemories(filters, 0, false);
  }

  return (
    <Container size="lg" py="md">
      <Stack gap="md">
        <Title order={2}>Memories</Title>

        <MemoryFilters value={filters} onChange={setFilters} />

        {/* Stats bar */}
        {stats && (
          <Group gap="md">
            <Text size="sm" c="dimmed">
              {stats.total_memories} total memories
            </Text>
            {Object.entries(stats.by_source).map(([source, count]) => (
              <Badge key={source} variant="light" color="gray" size="sm">
                {source}: {count}
              </Badge>
            ))}
          </Group>
        )}

        {/* Memory list */}
        {initialLoad ? (
          <Center py="xl">
            <Loader />
          </Center>
        ) : memories.length === 0 ? (
          <Center py="xl">
            <Text c="dimmed">No memories found</Text>
          </Center>
        ) : (
          <Stack gap="sm">
            {memories.map((m) => (
              <MemoryCard key={m.id} memory={m} onUpdate={handleUpdate} />
            ))}
          </Stack>
        )}

        {/* Load more */}
        {hasMore && memories.length > 0 && (
          <Center>
            <Button variant="light" onClick={handleLoadMore} loading={loading}>
              Load more
            </Button>
          </Center>
        )}
      </Stack>
    </Container>
  );
}
