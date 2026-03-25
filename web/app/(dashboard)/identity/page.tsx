'use client';

import { useState, useCallback, useEffect } from 'react';
import {
  Title,
  Container,
  Stack,
  Tabs,
  Group,
  Button,
  Select,
  Modal,
  TextInput,
  Textarea,
  NumberInput,
  Text,
  Table,
  Loader,
  Center,
  Code,
  ScrollArea,
  Box,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { api } from '@/lib/api';
import { useApi } from '@/hooks/useApi';
import type { Belief, Preference, Snapshot } from '@/lib/types';
import { BeliefCard, BeliefTimeline, PreferenceCard, StyleGauges } from '@/components/identity';
import dayjs from 'dayjs';

export default function IdentityPage() {
  // --- Beliefs state ---
  const [beliefs, setBeliefs] = useState<Belief[]>([]);
  const [beliefsLoading, setBeliefsLoading] = useState(true);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [addBeliefOpen, setAddBeliefOpen] = useState(false);
  const [inferring, setInferring] = useState(false);

  // Add belief form
  const [newTopic, setNewTopic] = useState('');
  const [newStance, setNewStance] = useState('');
  const [newNuance, setNewNuance] = useState('');
  const [newConfidence, setNewConfidence] = useState<number | string>(0.5);
  const [addBeliefLoading, setAddBeliefLoading] = useState(false);

  const fetchBeliefs = useCallback(async () => {
    setBeliefsLoading(true);
    try {
      const data = await api.get<Belief[]>('/api/identity/beliefs');
      setBeliefs(data);
    } catch {
      // handled by api client
    } finally {
      setBeliefsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBeliefs();
  }, [fetchBeliefs]);

  const uniqueTopics = Array.from(new Set(beliefs.map((b) => b.topic))).sort();

  async function handleAddBelief() {
    setAddBeliefLoading(true);
    try {
      await api.post('/api/identity/beliefs', {
        topic: newTopic,
        stance: newStance || null,
        nuance: newNuance || null,
        confidence: Number(newConfidence),
      });
      notifications.show({ title: 'Created', message: 'Belief created', color: 'green' });
      setAddBeliefOpen(false);
      setNewTopic('');
      setNewStance('');
      setNewNuance('');
      setNewConfidence(0.5);
      fetchBeliefs();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to create belief', color: 'red' });
    } finally {
      setAddBeliefLoading(false);
    }
  }

  async function handleRunInference() {
    setInferring(true);
    try {
      await api.post('/api/identity/infer');
      notifications.show({ title: 'Inference complete', message: 'Beliefs updated from memory analysis', color: 'green' });
      fetchBeliefs();
    } catch {
      notifications.show({ title: 'Error', message: 'Inference failed', color: 'red' });
    } finally {
      setInferring(false);
    }
  }

  // --- Preferences state ---
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [prefsLoading, setPrefsLoading] = useState(true);
  const [addPrefOpen, setAddPrefOpen] = useState(false);

  // Add preference form
  const [newPrefCategory, setNewPrefCategory] = useState('');
  const [newPrefValue, setNewPrefValue] = useState('');
  const [newPrefStrength, setNewPrefStrength] = useState<number | string>(0.5);
  const [addPrefLoading, setAddPrefLoading] = useState(false);

  const fetchPreferences = useCallback(async () => {
    setPrefsLoading(true);
    try {
      const data = await api.get<Preference[]>('/api/identity/preferences');
      setPreferences(data);
    } catch {
      // handled by api client
    } finally {
      setPrefsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPreferences();
  }, [fetchPreferences]);

  // Group preferences by category
  const prefsByCategory = preferences.reduce<Record<string, Preference[]>>((acc, p) => {
    const cat = p.category || 'Uncategorized';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(p);
    return acc;
  }, {});

  async function handleAddPreference() {
    setAddPrefLoading(true);
    try {
      await api.post('/api/identity/preferences', {
        category: newPrefCategory,
        value: newPrefValue || null,
        strength: Number(newPrefStrength),
      });
      notifications.show({ title: 'Created', message: 'Preference created', color: 'green' });
      setAddPrefOpen(false);
      setNewPrefCategory('');
      setNewPrefValue('');
      setNewPrefStrength(0.5);
      fetchPreferences();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to create preference', color: 'red' });
    } finally {
      setAddPrefLoading(false);
    }
  }

  // --- Snapshots state ---
  const { data: snapshots, isLoading: snapshotsLoading, mutate: mutateSnapshots } = useApi<Snapshot[]>('/api/identity/snapshots');
  const [takingSnapshot, setTakingSnapshot] = useState(false);
  const [snapshotLabel, setSnapshotLabel] = useState('');
  const [snapshotModalOpen, setSnapshotModalOpen] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState<Snapshot | null>(null);
  const [snapshotDetailLoading, setSnapshotDetailLoading] = useState(false);
  const [snapshotDetail, setSnapshotDetail] = useState<Snapshot | null>(null);

  async function handleTakeSnapshot() {
    setTakingSnapshot(true);
    try {
      await api.post('/api/identity/snapshot', {
        label: snapshotLabel || null,
      });
      notifications.show({ title: 'Snapshot taken', message: 'Identity snapshot saved', color: 'green' });
      setSnapshotModalOpen(false);
      setSnapshotLabel('');
      mutateSnapshots();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to take snapshot', color: 'red' });
    } finally {
      setTakingSnapshot(false);
    }
  }

  async function handleViewSnapshot(snapshot: Snapshot) {
    setSelectedSnapshot(snapshot);
    setSnapshotDetailLoading(true);
    try {
      const detail = await api.get<Snapshot>(`/api/identity/snapshot/${snapshot.id}`);
      setSnapshotDetail(detail);
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to load snapshot', color: 'red' });
    } finally {
      setSnapshotDetailLoading(false);
    }
  }

  return (
    <Container size="lg" py="md">
      <Stack gap="md">
        <Title order={2}>Identity</Title>

        <Tabs defaultValue="beliefs">
          <Tabs.List>
            <Tabs.Tab value="beliefs">Beliefs</Tabs.Tab>
            <Tabs.Tab value="preferences">Preferences</Tabs.Tab>
            <Tabs.Tab value="style">Style</Tabs.Tab>
            <Tabs.Tab value="snapshots">Snapshots</Tabs.Tab>
          </Tabs.List>

          {/* ===== BELIEFS TAB ===== */}
          <Tabs.Panel value="beliefs" pt="md">
            <Stack gap="md">
              {/* Topic selector + timeline */}
              <Group gap="md" align="flex-end">
                <Select
                  label="Topic"
                  placeholder="Select topic for timeline"
                  data={uniqueTopics}
                  value={selectedTopic}
                  onChange={setSelectedTopic}
                  clearable
                  searchable
                  style={{ minWidth: 200 }}
                />
                <Button
                  variant="light"
                  color="violet"
                  onClick={handleRunInference}
                  loading={inferring}
                >
                  Run Inference
                </Button>
                <Button variant="light" onClick={() => setAddBeliefOpen(true)}>
                  Add Belief
                </Button>
              </Group>

              <BeliefTimeline topic={selectedTopic} />

              {/* Beliefs list */}
              {beliefsLoading ? (
                <Center py="xl">
                  <Loader />
                </Center>
              ) : beliefs.length === 0 ? (
                <Center py="xl">
                  <Text c="dimmed">No beliefs yet. Add one or run inference.</Text>
                </Center>
              ) : (
                <Stack gap="sm">
                  {beliefs.map((b) => (
                    <BeliefCard key={b.id} belief={b} onUpdate={fetchBeliefs} />
                  ))}
                </Stack>
              )}
            </Stack>
          </Tabs.Panel>

          {/* ===== PREFERENCES TAB ===== */}
          <Tabs.Panel value="preferences" pt="md">
            <Stack gap="md">
              <Group>
                <Button variant="light" onClick={() => setAddPrefOpen(true)}>
                  Add Preference
                </Button>
              </Group>

              {prefsLoading ? (
                <Center py="xl">
                  <Loader />
                </Center>
              ) : preferences.length === 0 ? (
                <Center py="xl">
                  <Text c="dimmed">No preferences yet.</Text>
                </Center>
              ) : (
                <Stack gap="lg">
                  {Object.entries(prefsByCategory).sort(([a], [b]) => a.localeCompare(b)).map(([category, prefs]) => (
                    <Box key={category}>
                      <Text fw={700} size="sm" mb="xs" tt="uppercase" c="dimmed">
                        {category}
                      </Text>
                      <Stack gap="sm">
                        {prefs.map((p) => (
                          <PreferenceCard key={p.id} preference={p} onUpdate={fetchPreferences} />
                        ))}
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}
            </Stack>
          </Tabs.Panel>

          {/* ===== STYLE TAB ===== */}
          <Tabs.Panel value="style" pt="md">
            <StyleGauges />
          </Tabs.Panel>

          {/* ===== SNAPSHOTS TAB ===== */}
          <Tabs.Panel value="snapshots" pt="md">
            <Stack gap="md">
              <Group>
                <Button variant="light" onClick={() => setSnapshotModalOpen(true)}>
                  Take Snapshot
                </Button>
              </Group>

              {snapshotsLoading ? (
                <Center py="xl">
                  <Loader />
                </Center>
              ) : !snapshots || snapshots.length === 0 ? (
                <Center py="xl">
                  <Text c="dimmed">No snapshots yet.</Text>
                </Center>
              ) : (
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Label</Table.Th>
                      <Table.Th>Created</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {snapshots.map((s) => (
                      <Table.Tr
                        key={s.id}
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleViewSnapshot(s)}
                      >
                        <Table.Td>{s.label || 'Untitled'}</Table.Td>
                        <Table.Td>
                          {s.created_at ? dayjs(s.created_at).format('YYYY-MM-DD HH:mm') : 'Unknown'}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Stack>

      {/* ===== ADD BELIEF MODAL ===== */}
      <Modal opened={addBeliefOpen} onClose={() => setAddBeliefOpen(false)} title="Add Belief" size="md">
        <Stack gap="md">
          <TextInput
            label="Topic"
            value={newTopic}
            onChange={(e) => setNewTopic(e.currentTarget.value)}
            required
          />
          <TextInput
            label="Stance"
            value={newStance}
            onChange={(e) => setNewStance(e.currentTarget.value)}
          />
          <Textarea
            label="Nuance"
            value={newNuance}
            onChange={(e) => setNewNuance(e.currentTarget.value)}
            minRows={2}
            autosize
          />
          <NumberInput
            label="Confidence"
            value={newConfidence}
            onChange={setNewConfidence}
            min={0}
            max={1}
            step={0.05}
            decimalScale={2}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setAddBeliefOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddBelief} loading={addBeliefLoading} disabled={!newTopic.trim()}>
              Create
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* ===== ADD PREFERENCE MODAL ===== */}
      <Modal opened={addPrefOpen} onClose={() => setAddPrefOpen(false)} title="Add Preference" size="md">
        <Stack gap="md">
          <TextInput
            label="Category"
            value={newPrefCategory}
            onChange={(e) => setNewPrefCategory(e.currentTarget.value)}
            required
          />
          <TextInput
            label="Value"
            value={newPrefValue}
            onChange={(e) => setNewPrefValue(e.currentTarget.value)}
          />
          <NumberInput
            label="Strength"
            value={newPrefStrength}
            onChange={setNewPrefStrength}
            min={0}
            max={1}
            step={0.05}
            decimalScale={2}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setAddPrefOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddPreference} loading={addPrefLoading} disabled={!newPrefCategory.trim()}>
              Create
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* ===== TAKE SNAPSHOT MODAL ===== */}
      <Modal opened={snapshotModalOpen} onClose={() => setSnapshotModalOpen(false)} title="Take Snapshot" size="sm">
        <Stack gap="md">
          <TextInput
            label="Label (optional)"
            value={snapshotLabel}
            onChange={(e) => setSnapshotLabel(e.currentTarget.value)}
            placeholder="e.g. Before experiment"
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setSnapshotModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleTakeSnapshot} loading={takingSnapshot}>
              Take Snapshot
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* ===== SNAPSHOT DETAIL MODAL ===== */}
      <Modal
        opened={selectedSnapshot !== null}
        onClose={() => { setSelectedSnapshot(null); setSnapshotDetail(null); }}
        title={selectedSnapshot?.label || 'Snapshot Detail'}
        size="lg"
      >
        {snapshotDetailLoading ? (
          <Center py="xl">
            <Loader />
          </Center>
        ) : snapshotDetail ? (
          <Stack gap="md">
            <Text size="xs" c="dimmed">
              Created: {snapshotDetail.created_at ? dayjs(snapshotDetail.created_at).format('YYYY-MM-DD HH:mm:ss') : 'Unknown'}
            </Text>
            <ScrollArea h={400}>
              <Code block style={{ whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(snapshotDetail.snapshot_data, null, 2)}
              </Code>
            </ScrollArea>
          </Stack>
        ) : (
          <Text c="dimmed">No data</Text>
        )}
      </Modal>
    </Container>
  );
}
