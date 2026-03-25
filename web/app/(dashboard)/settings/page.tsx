'use client';

import { useState, useCallback, useEffect } from 'react';
import {
  Title,
  Container,
  Stack,
  Group,
  Button,
  Select,
  Modal,
  TextInput,
  PasswordInput,
  Text,
  Table,
  Loader,
  Center,
  Code,
  Paper,
  Badge,
  CopyButton,
  Alert,
} from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { notifications } from '@mantine/notifications';
import { api } from '@/lib/api';
import dayjs from 'dayjs';

/* ── Types ──────────────────────────────────────────────────────── */

interface EngramConfig {
  anthropic_api_key?: string;
  openai_api_key?: string;
  generation_provider?: string;
  generation_model?: string;
  embedding_model?: string;
  [key: string]: unknown;
}

interface AccessToken {
  id: string;
  name: string;
  access_level: string;
  created_at: string | null;
}

interface CreatedToken extends AccessToken {
  token: string;
}

interface ImportResult {
  [key: string]: unknown;
}

/* ── Page Component ─────────────────────────────────────────────── */

export default function SettingsPage() {
  // ── Config state ───────────────────────────────────────────────
  const [config, setConfig] = useState<EngramConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(true);

  const fetchConfig = useCallback(async () => {
    setConfigLoading(true);
    try {
      const data = await api.get<EngramConfig>('/api/config');
      setConfig(data);
    } catch {
      // handled by api client
    } finally {
      setConfigLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // ── API Keys form state ────────────────────────────────────────
  const [anthropicKey, setAnthropicKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [keysSubmitting, setKeysSubmitting] = useState(false);

  async function handleUpdateKeys() {
    setKeysSubmitting(true);
    try {
      const body: Record<string, string> = {};
      if (anthropicKey) body.anthropic_api_key = anthropicKey;
      if (openaiKey) body.openai_api_key = openaiKey;
      await api.put('/api/config/keys', body);
      notifications.show({ title: 'Updated', message: 'API keys updated successfully', color: 'green' });
      setAnthropicKey('');
      setOpenaiKey('');
      fetchConfig();
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to update keys',
        color: 'red',
      });
    } finally {
      setKeysSubmitting(false);
    }
  }

  // ── Tokens state ───────────────────────────────────────────────
  const [tokens, setTokens] = useState<AccessToken[]>([]);
  const [tokensLoading, setTokensLoading] = useState(true);

  const fetchTokens = useCallback(async () => {
    setTokensLoading(true);
    try {
      const data = await api.get<AccessToken[]>('/api/tokens');
      setTokens(data);
    } catch {
      // handled by api client
    } finally {
      setTokensLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTokens();
  }, [fetchTokens]);

  // Create token modal
  const [createTokenOpen, setCreateTokenOpen] = useState(false);
  const [newTokenName, setNewTokenName] = useState('');
  const [newTokenAccess, setNewTokenAccess] = useState<string | null>('owner');
  const [createTokenLoading, setCreateTokenLoading] = useState(false);
  const [createdToken, setCreatedToken] = useState<string | null>(null);

  async function handleCreateToken() {
    setCreateTokenLoading(true);
    try {
      const result = await api.post<CreatedToken>('/api/tokens', {
        name: newTokenName,
        access_level: newTokenAccess || 'owner',
      });
      setCreatedToken(result.token);
      fetchTokens();
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to create token',
        color: 'red',
      });
    } finally {
      setCreateTokenLoading(false);
    }
  }

  function handleCloseCreateToken() {
    setCreateTokenOpen(false);
    setNewTokenName('');
    setNewTokenAccess('owner');
    setCreatedToken(null);
  }

  // Revoke token
  const [revokeId, setRevokeId] = useState<string | null>(null);
  const [revoking, setRevoking] = useState(false);

  async function handleRevokeToken() {
    if (!revokeId) return;
    setRevoking(true);
    try {
      await api.delete(`/api/tokens/${revokeId}`);
      notifications.show({ title: 'Revoked', message: 'Token revoked', color: 'green' });
      setRevokeId(null);
      fetchTokens();
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to revoke token',
        color: 'red',
      });
    } finally {
      setRevoking(false);
    }
  }

  // ── Export / Import state ──────────────────────────────────────
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  async function handleExport() {
    setExporting(true);
    try {
      const data = await api.post<Record<string, unknown>>('/api/engram/export');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `engram-export-${dayjs().format('YYYY-MM-DD')}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      notifications.show({ title: 'Exported', message: 'Engram data downloaded', color: 'green' });
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Export failed',
        color: 'red',
      });
    } finally {
      setExporting(false);
    }
  }

  async function handleImportDrop(files: File[]) {
    if (files.length === 0) return;
    const file = files[0];
    setImporting(true);
    setImportResult(null);
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const result = await api.post<ImportResult>('/api/engram/import', payload);
      setImportResult(result);
      notifications.show({ title: 'Imported', message: 'Engram data imported successfully', color: 'green' });
    } catch (err) {
      notifications.show({
        title: 'Import Failed',
        message: err instanceof Error ? err.message : 'Failed to import data',
        color: 'red',
      });
    } finally {
      setImporting(false);
    }
  }

  // ── Disconnect ─────────────────────────────────────────────────
  function handleDisconnect() {
    localStorage.removeItem('engram_token');
    window.location.href = '/auth';
  }

  // ── Render ─────────────────────────────────────────────────────

  return (
    <Container size="lg" py="md">
      <Stack gap="xl">
        <Title order={2}>Settings</Title>

        {/* ═══ API Keys ═══════════════════════════════════════════ */}
        <Paper withBorder radius="md" p="lg">
          <Title order={4} mb="md">API Keys</Title>

          {configLoading ? (
            <Center py="md"><Loader /></Center>
          ) : (
            <Stack gap="md">
              <Group gap="lg">
                <Text size="sm" fw={500}>Anthropic API Key:</Text>
                <Code>{config?.anthropic_api_key || 'Not set'}</Code>
              </Group>
              <Group gap="lg">
                <Text size="sm" fw={500}>OpenAI API Key:</Text>
                <Code>{config?.openai_api_key || 'Not set'}</Code>
              </Group>

              <Title order={5} mt="sm">Update Keys</Title>
              <PasswordInput
                label="Anthropic API Key"
                placeholder="sk-ant-..."
                value={anthropicKey}
                onChange={(e) => setAnthropicKey(e.currentTarget.value)}
              />
              <PasswordInput
                label="OpenAI API Key"
                placeholder="sk-..."
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.currentTarget.value)}
              />
              <Group>
                <Button
                  onClick={handleUpdateKeys}
                  loading={keysSubmitting}
                  disabled={!anthropicKey && !openaiKey}
                >
                  Update Keys
                </Button>
              </Group>
            </Stack>
          )}
        </Paper>

        {/* ═══ Access Tokens ══════════════════════════════════════ */}
        <Paper withBorder radius="md" p="lg">
          <Group justify="space-between" mb="md">
            <Title order={4}>Access Tokens</Title>
            <Button variant="light" onClick={() => setCreateTokenOpen(true)}>
              Create Token
            </Button>
          </Group>

          {tokensLoading ? (
            <Center py="md"><Loader /></Center>
          ) : tokens.length === 0 ? (
            <Center py="md">
              <Text c="dimmed">No active tokens.</Text>
            </Center>
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Access Level</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {tokens.map((t) => (
                  <Table.Tr key={t.id}>
                    <Table.Td>{t.name}</Table.Td>
                    <Table.Td>
                      <Badge
                        color={t.access_level === 'owner' ? 'blue' : 'gray'}
                        variant="light"
                      >
                        {t.access_level}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      {t.created_at ? dayjs(t.created_at).format('YYYY-MM-DD HH:mm') : 'Unknown'}
                    </Table.Td>
                    <Table.Td>
                      <Button
                        variant="subtle"
                        color="red"
                        size="xs"
                        onClick={() => setRevokeId(t.id)}
                      >
                        Revoke
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Paper>

        {/* ═══ Model Configuration ════════════════════════════════ */}
        <Paper withBorder radius="md" p="lg">
          <Title order={4} mb="md">Model Configuration</Title>
          <Text size="xs" c="dimmed" mb="md">
            Read-only. Model changes require re-running <Code>engram init</Code>.
          </Text>

          {configLoading ? (
            <Center py="md"><Loader /></Center>
          ) : (
            <Stack gap="sm">
              <Group gap="lg">
                <Text size="sm" fw={500} w={160}>Generation Provider:</Text>
                <Text size="sm">{config?.generation_provider || 'N/A'}</Text>
              </Group>
              <Group gap="lg">
                <Text size="sm" fw={500} w={160}>Generation Model:</Text>
                <Text size="sm">{config?.generation_model || 'N/A'}</Text>
              </Group>
              <Group gap="lg">
                <Text size="sm" fw={500} w={160}>Embedding Model:</Text>
                <Text size="sm">{config?.embedding_model || 'N/A'}</Text>
              </Group>
            </Stack>
          )}
        </Paper>

        {/* ═══ Export / Import ════════════════════════════════════ */}
        <Paper withBorder radius="md" p="lg">
          <Title order={4} mb="md">Export / Import</Title>

          <Stack gap="md">
            <Group>
              <Button onClick={handleExport} loading={exporting} variant="light">
                Export Engram
              </Button>
            </Group>

            <Text size="sm" fw={500}>Import Engram</Text>
            <Dropzone
              onDrop={handleImportDrop}
              loading={importing}
              accept={['application/json']}
              maxFiles={1}
            >
              <Group justify="center" gap="xl" mih={100} style={{ pointerEvents: 'none' }}>
                <Stack align="center" gap={4}>
                  <Text size="lg" inline>
                    Drag a JSON export file here or click to browse
                  </Text>
                  <Text size="sm" c="dimmed" inline>
                    Only .json files accepted
                  </Text>
                </Stack>
              </Group>
            </Dropzone>

            {importResult && (
              <Alert color="green" title="Import Complete">
                <Code block style={{ whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(importResult, null, 2)}
                </Code>
              </Alert>
            )}
          </Stack>
        </Paper>

        {/* ═══ Danger Zone ════════════════════════════════════════ */}
        <Paper withBorder radius="md" p="lg" style={{ borderColor: 'var(--mantine-color-red-6)' }}>
          <Title order={4} mb="md" c="red">Danger Zone</Title>
          <Text size="sm" mb="md">
            Disconnect this browser from Engram. This clears your authentication token.
          </Text>
          <Button color="red" variant="outline" onClick={handleDisconnect}>
            Disconnect
          </Button>
        </Paper>
      </Stack>

      {/* ═══ Create Token Modal ══════════════════════════════════ */}
      <Modal
        opened={createTokenOpen}
        onClose={handleCloseCreateToken}
        title="Create Access Token"
        size="md"
      >
        {createdToken ? (
          <Stack gap="md">
            <Alert color="yellow" title="Save this token — it's only shown once!" />
            <Code block style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {createdToken}
            </Code>
            <CopyButton value={createdToken}>
              {({ copied, copy }) => (
                <Button
                  color={copied ? 'teal' : 'blue'}
                  variant="light"
                  onClick={copy}
                  fullWidth
                >
                  {copied ? 'Copied!' : 'Copy Token'}
                </Button>
              )}
            </CopyButton>
            <Group justify="flex-end">
              <Button variant="default" onClick={handleCloseCreateToken}>
                Done
              </Button>
            </Group>
          </Stack>
        ) : (
          <Stack gap="md">
            <TextInput
              label="Name"
              placeholder="e.g. CLI access"
              value={newTokenName}
              onChange={(e) => setNewTokenName(e.currentTarget.value)}
              required
            />
            <Select
              label="Access Level"
              data={[
                { value: 'owner', label: 'Owner' },
                { value: 'shared', label: 'Shared' },
              ]}
              value={newTokenAccess}
              onChange={setNewTokenAccess}
            />
            <Group justify="flex-end">
              <Button variant="default" onClick={handleCloseCreateToken}>
                Cancel
              </Button>
              <Button
                onClick={handleCreateToken}
                loading={createTokenLoading}
                disabled={!newTokenName.trim()}
              >
                Create
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      {/* ═══ Revoke Token Confirmation Modal ═════════════════════ */}
      <Modal
        opened={revokeId !== null}
        onClose={() => setRevokeId(null)}
        title="Revoke Token"
        size="sm"
      >
        <Stack gap="md">
          <Text>
            Are you sure you want to revoke this token? Any applications using it will lose access.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setRevokeId(null)}>
              Cancel
            </Button>
            <Button color="red" onClick={handleRevokeToken} loading={revoking}>
              Revoke
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}
