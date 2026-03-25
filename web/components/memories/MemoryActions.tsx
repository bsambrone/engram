'use client';

import { useState } from 'react';
import {
  Group,
  Button,
  Modal,
  TextInput,
  Textarea,
  Select,
  NumberInput,
  Stack,
  Text,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { api } from '@/lib/api';
import type { Memory } from '@/lib/types';

interface MemoryActionsProps {
  memory: Memory;
  onUpdate?: () => void;
}

export function MemoryActions({ memory, onUpdate }: MemoryActionsProps) {
  const [editOpen, setEditOpen] = useState(false);
  const [evolveOpen, setEvolveOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // Edit form state
  const [editContent, setEditContent] = useState(memory.content);
  const [editVisibility, setEditVisibility] = useState(memory.visibility);
  const [editImportance, setEditImportance] = useState<number | string>(
    memory.importance_score ?? 0.5
  );

  // Evolve form state
  const [evolveContent, setEvolveContent] = useState('');

  async function handleEdit() {
    setLoading(true);
    try {
      await api.put(`/api/memories/${memory.id}`, {
        content: editContent,
        visibility: editVisibility,
        importance_score: Number(editImportance),
      });
      notifications.show({ title: 'Updated', message: 'Memory updated successfully', color: 'green' });
      setEditOpen(false);
      onUpdate?.();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to update memory', color: 'red' });
    } finally {
      setLoading(false);
    }
  }

  async function handleReinforce() {
    setLoading(true);
    try {
      await api.post(`/api/memories/${memory.id}/reinforce`);
      notifications.show({ title: 'Reinforced', message: 'Memory reinforced', color: 'green' });
      onUpdate?.();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to reinforce memory', color: 'red' });
    } finally {
      setLoading(false);
    }
  }

  async function handleDegrade() {
    setLoading(true);
    try {
      await api.post(`/api/memories/${memory.id}/degrade`);
      notifications.show({ title: 'Degraded', message: 'Memory degraded', color: 'yellow' });
      onUpdate?.();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to degrade memory', color: 'red' });
    } finally {
      setLoading(false);
    }
  }

  async function handleEvolve() {
    setLoading(true);
    try {
      await api.post(`/api/memories/${memory.id}/evolve`, { content: evolveContent });
      notifications.show({ title: 'Evolved', message: 'Memory evolved with new nuance', color: 'green' });
      setEvolveOpen(false);
      setEvolveContent('');
      onUpdate?.();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to evolve memory', color: 'red' });
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setLoading(true);
    try {
      await api.delete(`/api/memories/${memory.id}`);
      notifications.show({ title: 'Deleted', message: 'Memory deleted', color: 'red' });
      setDeleteOpen(false);
      onUpdate?.();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to delete memory', color: 'red' });
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Group gap="xs" mt="xs">
        <Button size="xs" variant="light" onClick={() => setEditOpen(true)}>
          Edit
        </Button>
        <Button size="xs" variant="light" color="green" onClick={handleReinforce} loading={loading}>
          Reinforce
        </Button>
        <Button size="xs" variant="light" color="yellow" onClick={handleDegrade} loading={loading}>
          Degrade
        </Button>
        <Button size="xs" variant="light" color="cyan" onClick={() => setEvolveOpen(true)}>
          Evolve
        </Button>
        <Button size="xs" variant="light" color="red" onClick={() => setDeleteOpen(true)}>
          Delete
        </Button>
      </Group>

      {/* Edit Modal */}
      <Modal opened={editOpen} onClose={() => setEditOpen(false)} title="Edit Memory" size="lg">
        <Stack gap="md">
          <TextInput
            label="Content"
            value={editContent}
            onChange={(e) => setEditContent(e.currentTarget.value)}
          />
          <Select
            label="Visibility"
            data={[
              { value: 'active', label: 'Active' },
              { value: 'private', label: 'Private' },
              { value: 'excluded', label: 'Excluded' },
            ]}
            value={editVisibility}
            onChange={(v) => setEditVisibility(v ?? 'active')}
            allowDeselect={false}
          />
          <NumberInput
            label="Importance"
            value={editImportance}
            onChange={setEditImportance}
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

      {/* Evolve Modal */}
      <Modal opened={evolveOpen} onClose={() => setEvolveOpen(false)} title="Evolve Memory" size="lg">
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Add new nuance or updated content to evolve this memory.
          </Text>
          <Textarea
            label="New content / nuance"
            value={evolveContent}
            onChange={(e) => setEvolveContent(e.currentTarget.value)}
            minRows={3}
            autosize
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setEvolveOpen(false)}>
              Cancel
            </Button>
            <Button color="cyan" onClick={handleEvolve} loading={loading} disabled={!evolveContent.trim()}>
              Evolve
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal opened={deleteOpen} onClose={() => setDeleteOpen(false)} title="Delete Memory" size="sm">
        <Stack gap="md">
          <Text size="sm">
            Are you sure you want to delete this memory? This action cannot be undone.
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
