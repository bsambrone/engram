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
  NumberInput,
  Progress,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { api } from '@/lib/api';
import type { Preference } from '@/lib/types';

interface PreferenceCardProps {
  preference: Preference;
  onUpdate?: () => void;
}

function getStrengthColor(value: number): string {
  if (value < 0.3) return 'red';
  if (value < 0.7) return 'yellow';
  return 'green';
}

export function PreferenceCard({ preference, onUpdate }: PreferenceCardProps) {
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // Edit form state
  const [editCategory, setEditCategory] = useState(preference.category);
  const [editValue, setEditValue] = useState(preference.value ?? '');
  const [editStrength, setEditStrength] = useState<number | string>(
    preference.strength ?? 0.5
  );

  async function handleEdit() {
    setLoading(true);
    try {
      await api.put(`/api/identity/preferences/${preference.id}`, {
        category: editCategory,
        value: editValue || null,
        strength: Number(editStrength),
      });
      notifications.show({ title: 'Updated', message: 'Preference updated successfully', color: 'green' });
      setEditOpen(false);
      onUpdate?.();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to update preference', color: 'red' });
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setLoading(true);
    try {
      await api.delete(`/api/identity/preferences/${preference.id}`);
      notifications.show({ title: 'Deleted', message: 'Preference deleted', color: 'red' });
      setDeleteOpen(false);
      onUpdate?.();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to delete preference', color: 'red' });
    } finally {
      setLoading(false);
    }
  }

  const strengthValue = preference.strength ?? 0;
  const strengthPercent = Math.max(0, Math.min(1, strengthValue)) * 100;

  return (
    <>
      <Paper p="md" radius="md" withBorder>
        <Stack gap="xs">
          <Group justify="space-between" align="flex-start">
            <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
              <Badge variant="light" color="teal" size="sm" style={{ alignSelf: 'flex-start' }}>
                {preference.category}
              </Badge>
              {preference.value && <Text size="sm">{preference.value}</Text>}
            </Stack>
            {preference.source && (
              <Badge
                variant="light"
                color={preference.source === 'inferred' ? 'violet' : 'blue'}
                size="sm"
              >
                {preference.source}
              </Badge>
            )}
          </Group>

          {preference.strength != null && (
            <Box>
              <Group justify="space-between" mb={4}>
                <Text size="xs" c="dimmed">Strength</Text>
                <Text size="xs" c="dimmed">{Math.round(strengthPercent)}%</Text>
              </Group>
              <Progress
                value={strengthPercent}
                color={getStrengthColor(strengthValue)}
                size="sm"
                radius="xl"
              />
            </Box>
          )}

          <Group gap="xs" mt={4}>
            <Button size="xs" variant="light" onClick={() => setEditOpen(true)}>
              Edit
            </Button>
            <Button size="xs" variant="light" color="red" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          </Group>
        </Stack>
      </Paper>

      {/* Edit Modal */}
      <Modal opened={editOpen} onClose={() => setEditOpen(false)} title="Edit Preference" size="md">
        <Stack gap="md">
          <TextInput
            label="Category"
            value={editCategory}
            onChange={(e) => setEditCategory(e.currentTarget.value)}
          />
          <TextInput
            label="Value"
            value={editValue}
            onChange={(e) => setEditValue(e.currentTarget.value)}
          />
          <NumberInput
            label="Strength"
            value={editStrength}
            onChange={setEditStrength}
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
      <Modal opened={deleteOpen} onClose={() => setDeleteOpen(false)} title="Delete Preference" size="sm">
        <Stack gap="md">
          <Text size="sm">
            Are you sure you want to delete this preference? This action cannot be undone.
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
