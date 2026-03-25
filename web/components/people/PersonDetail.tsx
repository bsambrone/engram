'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  TextInput,
  Select,
  Badge,
  Group,
  Stack,
  Text,
  Title,
  Button,
  Paper,
  SimpleGrid,
  Box,
  Image,
  Loader,
  Center,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { TopicTag } from '@/components/common';
import { MemoryCard } from '@/components/memories/MemoryCard';
import type { Memory } from '@/lib/types';

interface PersonDetailData {
  id: string;
  name: string;
  relationship_type: string | null;
  relationships: string[];
  memory_count: number;
  top_topics: { name: string; count: number }[];
  platforms?: string[];
  interaction_score?: number;
  message_count?: number;
}

interface Photo {
  id: string;
  url: string;
  thumbnail_url?: string;
  caption?: string;
}

const PLATFORM_COLORS: Record<string, string> = {
  gmail: 'red',
  facebook: 'blue',
  instagram: 'grape',
  reddit: 'orange',
};

const RELATIONSHIP_OPTIONS = [
  { value: 'friend', label: 'Friend' },
  { value: 'family', label: 'Family' },
  { value: 'colleague', label: 'Colleague' },
  { value: 'acquaintance', label: 'Acquaintance' },
  { value: 'partner', label: 'Partner' },
  { value: 'other', label: 'Other' },
];

export function PersonDetail({ personId }: { personId: string }) {
  const { data: person, isLoading, mutate } = useApi<PersonDetailData>(
    `/api/people/${personId}`
  );
  const { data: memories, mutate: mutateMemories } = useApi<Memory[]>(
    `/api/people/${personId}/memories?limit=20&offset=0`
  );
  const { data: photos } = useApi<Photo[]>(
    `/api/photos?person_id=${personId}`
  );

  const [editName, setEditName] = useState('');
  const [editRelationship, setEditRelationship] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (person) {
      setEditName(person.name);
      setEditRelationship(person.relationship_type);
    }
  }, [person]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await api.put(`/api/people/${personId}`, {
        name: editName,
        relationship_type: editRelationship,
      });
      mutate();
      notifications.show({
        title: 'Saved',
        message: 'Person updated successfully',
        color: 'green',
      });
    } catch {
      notifications.show({
        title: 'Error',
        message: 'Failed to save changes',
        color: 'red',
      });
    } finally {
      setSaving(false);
    }
  }, [personId, editName, editRelationship, mutate]);

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  if (!person) {
    return (
      <Center py="xl">
        <Text c="dimmed">Person not found</Text>
      </Center>
    );
  }

  const hasChanges =
    editName !== person.name || editRelationship !== person.relationship_type;

  return (
    <Stack gap="lg">
      {/* Editable fields */}
      <Paper p="md" radius="md" withBorder>
        <Stack gap="sm">
          <TextInput
            label="Name"
            value={editName}
            onChange={(e) => setEditName(e.currentTarget.value)}
          />
          <Select
            label="Relationship Type"
            data={RELATIONSHIP_OPTIONS}
            value={editRelationship}
            onChange={setEditRelationship}
            clearable
          />
          {person.platforms && person.platforms.length > 0 && (
            <Box>
              <Text size="sm" fw={500} mb={4}>
                Platforms
              </Text>
              <Group gap={4}>
                {person.platforms.map((p) => (
                  <Badge
                    key={p}
                    variant="light"
                    color={PLATFORM_COLORS[p.toLowerCase()] ?? 'gray'}
                  >
                    {p}
                  </Badge>
                ))}
              </Group>
            </Box>
          )}
          {hasChanges && (
            <Group>
              <Button onClick={handleSave} loading={saving}>
                Save Changes
              </Button>
            </Group>
          )}
        </Stack>
      </Paper>

      {/* Stats */}
      <Paper p="md" radius="md" withBorder>
        <SimpleGrid cols={3} spacing="md">
          <Box>
            <Text size="xs" c="dimmed">
              Message Count
            </Text>
            <Text size="lg" fw={600}>
              {person.message_count ?? 0}
            </Text>
          </Box>
          <Box>
            <Text size="xs" c="dimmed">
              Interaction Score
            </Text>
            <Text size="lg" fw={600}>
              {person.interaction_score != null
                ? `${Math.round(person.interaction_score * 100)}%`
                : '--'}
            </Text>
          </Box>
          <Box>
            <Text size="xs" c="dimmed">
              Memory Count
            </Text>
            <Text size="lg" fw={600}>
              {person.memory_count}
            </Text>
          </Box>
        </SimpleGrid>
      </Paper>

      {/* Top topics */}
      {person.top_topics.length > 0 && (
        <Paper p="md" radius="md" withBorder>
          <Text size="sm" fw={500} mb="sm">
            Top Topics
          </Text>
          <Group gap={6}>
            {person.top_topics.map((t) => (
              <TopicTag key={t.name} name={t.name} />
            ))}
          </Group>
        </Paper>
      )}

      {/* Memories */}
      <Box>
        <Title order={4} mb="sm">
          Memories
        </Title>
        {memories && memories.length > 0 ? (
          <Stack gap="sm">
            {memories.map((m) => (
              <MemoryCard
                key={m.id}
                memory={m}
                onUpdate={() => mutateMemories()}
              />
            ))}
          </Stack>
        ) : (
          <Text c="dimmed" size="sm">
            No memories found for this person.
          </Text>
        )}
      </Box>

      {/* Photos */}
      {photos && photos.length > 0 && (
        <Box>
          <Title order={4} mb="sm">
            Photos
          </Title>
          <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }} spacing="sm">
            {photos.map((photo) => (
              <Paper key={photo.id} radius="md" withBorder p={4}>
                <Image
                  src={photo.thumbnail_url ?? photo.url}
                  alt={photo.caption ?? 'Photo'}
                  radius="sm"
                  fit="cover"
                  h={160}
                />
                {photo.caption && (
                  <Text size="xs" c="dimmed" mt={4} lineClamp={2}>
                    {photo.caption}
                  </Text>
                )}
              </Paper>
            ))}
          </SimpleGrid>
        </Box>
      )}
    </Stack>
  );
}
