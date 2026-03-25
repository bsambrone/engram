'use client';

import { useState } from 'react';
import {
  Paper,
  Group,
  Text,
  Stack,
  Badge,
  Box,
  Button,
  Modal,
  TextInput,
  Textarea,
  NumberInput,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { ConfidenceBar } from '@/components/common';
import { api } from '@/lib/api';
import type { Belief } from '@/lib/types';
import dayjs from 'dayjs';

interface BeliefCardProps {
  belief: Belief;
  onUpdate?: () => void;
}

export function BeliefCard({ belief, onUpdate }: BeliefCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // Edit form state
  const [editTopic, setEditTopic] = useState(belief.topic);
  const [editStance, setEditStance] = useState(belief.stance ?? '');
  const [editNuance, setEditNuance] = useState(belief.nuance ?? '');
  const [editConfidence, setEditConfidence] = useState<number | string>(
    belief.confidence ?? 0.5
  );

  async function handleEdit() {
    setLoading(true);
    try {
      await api.put(`/api/identity/beliefs/${belief.id}`, {
        topic: editTopic,
        stance: editStance || null,
        nuance: editNuance || null,
        confidence: Number(editConfidence),
      });
      notifications.show({ title: 'Updated', message: 'Belief updated successfully', color: 'green' });
      setEditOpen(false);
      onUpdate?.();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to update belief', color: 'red' });
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setLoading(true);
    try {
      await api.delete(`/api/identity/beliefs/${belief.id}`);
      notifications.show({ title: 'Deleted', message: 'Belief deleted', color: 'red' });
      setDeleteOpen(false);
      onUpdate?.();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to delete belief', color: 'red' });
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
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
        <Stack gap="xs">
          <Group justify="space-between" align="flex-start">
            <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
              <Text fw={700} size="sm">{belief.topic}</Text>
              {belief.stance && <Text size="sm">{belief.stance}</Text>}
              {belief.nuance && (
                <Text size="sm" fs="italic" c="dimmed">
                  {belief.nuance}
                </Text>
              )}
            </Stack>
            <Group gap="xs">
              {belief.source && (
                <Badge
                  variant="light"
                  color={belief.source === 'inferred' ? 'violet' : 'blue'}
                  size="sm"
                >
                  {belief.source}
                </Badge>
              )}
            </Group>
          </Group>

          {belief.confidence != null && (
            <Box w={160}>
              <ConfidenceBar value={belief.confidence} label="Confidence" />
            </Box>
          )}

          {/* Expanded timeline info */}
          {expanded && (
            <Box mt="xs" pt="xs" style={{ borderTop: '1px solid var(--mantine-color-dark-4)' }}>
              <Group gap="lg">
                <Box>
                  <Text size="xs" c="dimmed">Valid from</Text>
                  <Text size="sm">
                    {belief.valid_from ? dayjs(belief.valid_from).format('YYYY-MM-DD') : 'N/A'}
                  </Text>
                </Box>
                <Box>
                  <Text size="xs" c="dimmed">Valid until</Text>
                  <Text size="sm">
                    {belief.valid_until ? dayjs(belief.valid_until).format('YYYY-MM-DD') : 'Present'}
                  </Text>
                </Box>
              </Group>
              <Group gap="xs" mt="sm" onClick={(e) => e.stopPropagation()}>
                <Button size="xs" variant="light" onClick={() => setEditOpen(true)}>
                  Edit
                </Button>
                <Button size="xs" variant="light" color="red" onClick={() => setDeleteOpen(true)}>
                  Delete
                </Button>
              </Group>
            </Box>
          )}
        </Stack>
      </Paper>

      {/* Edit Modal */}
      <Modal opened={editOpen} onClose={() => setEditOpen(false)} title="Edit Belief" size="md">
        <Stack gap="md">
          <TextInput
            label="Topic"
            value={editTopic}
            onChange={(e) => setEditTopic(e.currentTarget.value)}
          />
          <TextInput
            label="Stance"
            value={editStance}
            onChange={(e) => setEditStance(e.currentTarget.value)}
          />
          <Textarea
            label="Nuance"
            value={editNuance}
            onChange={(e) => setEditNuance(e.currentTarget.value)}
            minRows={2}
            autosize
          />
          <NumberInput
            label="Confidence"
            value={editConfidence}
            onChange={setEditConfidence}
            min={0}
            max={1}
            step={0.05}
            decimalScale={2}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEdit} loading={loading}>
              Save
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal opened={deleteOpen} onClose={() => setDeleteOpen(false)} title="Delete Belief" size="sm">
        <Stack gap="md">
          <Text size="sm">
            Are you sure you want to delete this belief? This action cannot be undone.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button color="red" onClick={handleDelete} loading={loading}>
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
