'use client';

import { useState, useEffect } from 'react';
import {
  Stack,
  Text,
  Slider,
  Textarea,
  TextInput,
  Button,
  Group,
  Box,
  Paper,
  Loader,
  Center,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { StyleProfile } from '@/lib/types';

export function StyleGauges() {
  const { data, isLoading, mutate } = useApi<StyleProfile>('/api/identity/style');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state
  const [tone, setTone] = useState('');
  const [humorLevel, setHumorLevel] = useState(0.5);
  const [verbosity, setVerbosity] = useState(0.5);
  const [formality, setFormality] = useState(0.5);
  const [vocabNotes, setVocabNotes] = useState('');
  const [commPatterns, setCommPatterns] = useState('');

  // Sync form state when data loads
  useEffect(() => {
    if (data) {
      setTone(data.tone ?? '');
      setHumorLevel(data.humor_level ?? 0.5);
      setVerbosity(data.verbosity ?? 0.5);
      setFormality(data.formality ?? 0.5);
      setVocabNotes(data.vocabulary_notes ?? '');
      setCommPatterns(data.communication_patterns ?? '');
    }
  }, [data]);

  async function handleSave() {
    setSaving(true);
    try {
      await api.put('/api/identity/style', {
        tone: tone || null,
        humor_level: humorLevel,
        verbosity,
        formality,
        vocabulary_notes: vocabNotes || null,
        communication_patterns: commPatterns || null,
      });
      notifications.show({ title: 'Saved', message: 'Style profile updated', color: 'green' });
      setEditing(false);
      mutate();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to update style profile', color: 'red' });
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    if (data) {
      setTone(data.tone ?? '');
      setHumorLevel(data.humor_level ?? 0.5);
      setVerbosity(data.verbosity ?? 0.5);
      setFormality(data.formality ?? 0.5);
      setVocabNotes(data.vocabulary_notes ?? '');
      setCommPatterns(data.communication_patterns ?? '');
    }
    setEditing(false);
  }

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  return (
    <Paper p="lg" radius="md" withBorder>
      <Stack gap="lg">
        <Group justify="space-between">
          <Text fw={700} size="lg">Communication Style</Text>
          {!editing ? (
            <Button variant="light" size="xs" onClick={() => setEditing(true)}>
              Edit
            </Button>
          ) : (
            <Group gap="xs">
              <Button variant="default" size="xs" onClick={handleCancel}>
                Cancel
              </Button>
              <Button size="xs" onClick={handleSave} loading={saving}>
                Save
              </Button>
            </Group>
          )}
        </Group>

        {/* Tone */}
        <Box>
          <Text size="sm" fw={600} mb={4}>Tone</Text>
          {editing ? (
            <TextInput
              value={tone}
              onChange={(e) => setTone(e.currentTarget.value)}
              placeholder="e.g. friendly, professional, casual"
            />
          ) : (
            <Text size="sm" c={tone ? undefined : 'dimmed'}>
              {tone || 'Not set'}
            </Text>
          )}
        </Box>

        {/* Humor Level */}
        <Box>
          <Group justify="space-between" mb={4}>
            <Text size="sm" fw={600}>Humor Level</Text>
            <Text size="xs" c="dimmed">{Math.round(humorLevel * 100)}%</Text>
          </Group>
          <Slider
            value={humorLevel * 100}
            onChange={(v) => editing && setHumorLevel(v / 100)}
            min={0}
            max={100}
            disabled={!editing}
            marks={[
              { value: 0, label: 'Serious' },
              { value: 50, label: 'Balanced' },
              { value: 100, label: 'Humorous' },
            ]}
          />
        </Box>

        {/* Verbosity */}
        <Box>
          <Group justify="space-between" mb={4}>
            <Text size="sm" fw={600}>Verbosity</Text>
            <Text size="xs" c="dimmed">{Math.round(verbosity * 100)}%</Text>
          </Group>
          <Slider
            value={verbosity * 100}
            onChange={(v) => editing && setVerbosity(v / 100)}
            min={0}
            max={100}
            disabled={!editing}
            marks={[
              { value: 0, label: 'Concise' },
              { value: 50, label: 'Moderate' },
              { value: 100, label: 'Verbose' },
            ]}
          />
        </Box>

        {/* Formality */}
        <Box>
          <Group justify="space-between" mb={4}>
            <Text size="sm" fw={600}>Formality</Text>
            <Text size="xs" c="dimmed">{Math.round(formality * 100)}%</Text>
          </Group>
          <Slider
            value={formality * 100}
            onChange={(v) => editing && setFormality(v / 100)}
            min={0}
            max={100}
            disabled={!editing}
            marks={[
              { value: 0, label: 'Casual' },
              { value: 50, label: 'Neutral' },
              { value: 100, label: 'Formal' },
            ]}
          />
        </Box>

        {/* Vocabulary Notes */}
        <Box>
          <Text size="sm" fw={600} mb={4}>Vocabulary Notes</Text>
          {editing ? (
            <Textarea
              value={vocabNotes}
              onChange={(e) => setVocabNotes(e.currentTarget.value)}
              placeholder="Notes about vocabulary preferences..."
              minRows={2}
              autosize
            />
          ) : (
            <Text size="sm" c={vocabNotes ? undefined : 'dimmed'} style={{ whiteSpace: 'pre-wrap' }}>
              {vocabNotes || 'Not set'}
            </Text>
          )}
        </Box>

        {/* Communication Patterns */}
        <Box>
          <Text size="sm" fw={600} mb={4}>Communication Patterns</Text>
          {editing ? (
            <Textarea
              value={commPatterns}
              onChange={(e) => setCommPatterns(e.currentTarget.value)}
              placeholder="Notes about communication patterns..."
              minRows={2}
              autosize
            />
          ) : (
            <Text size="sm" c={commPatterns ? undefined : 'dimmed'} style={{ whiteSpace: 'pre-wrap' }}>
              {commPatterns || 'Not set'}
            </Text>
          )}
        </Box>
      </Stack>
    </Paper>
  );
}
