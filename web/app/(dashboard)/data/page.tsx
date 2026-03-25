'use client';

import { useState, useCallback } from 'react';
import {
  Title,
  Container,
  Stack,
  SimpleGrid,
  Text,
  Paper,
  Group,
  Alert,
  Loader,
  Center,
} from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { notifications } from '@mantine/notifications';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { PlatformCard } from '@/components/data/PlatformCard';
import { JobsTable } from '@/components/data/JobsTable';
import { SourceManager } from '@/components/data/SourceManager';
import type { RegisteredExport, MemoryStats, IngestJob } from '@/lib/types';

const PLATFORMS = [
  { key: 'gmail', label: 'Gmail' },
  { key: 'reddit', label: 'Reddit' },
  { key: 'facebook', label: 'Facebook' },
  { key: 'instagram', label: 'Instagram' },
];

export default function DataPage() {
  const { data: exports, mutate: mutateExports } = useApi<RegisteredExport[]>('/api/ingest/exports');
  const { data: stats } = useApi<MemoryStats>('/api/memories/stats');
  const [uploading, setUploading] = useState(false);

  const handleImportStarted = useCallback(() => {
    mutateExports();
  }, [mutateExports]);

  async function handleFileDrop(files: File[]) {
    if (files.length === 0) return;
    setUploading(true);
    try {
      for (const file of files) {
        await api.upload<IngestJob>('/api/ingest/file', file);
      }
      notifications.show({
        title: 'Upload Complete',
        message: `${files.length} file(s) uploaded and queued for processing`,
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Upload Failed',
        message: err instanceof Error ? err.message : 'File upload failed',
        color: 'red',
      });
    } finally {
      setUploading(false);
    }
  }

  function getExportForPlatform(platform: string): RegisteredExport | undefined {
    return exports?.find((e) => e.platform === platform);
  }

  function getMemoryCount(platform: string): number {
    return stats?.by_source?.[platform] ?? 0;
  }

  return (
    <Container size="lg" py="md">
      <Stack gap="xl">
        {/* ── Import Section ────────────────────────────────────── */}
        <section>
          <Title order={2} mb="md">
            Import Data
          </Title>

          <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} mb="lg">
            {PLATFORMS.map((p) => (
              <PlatformCard
                key={p.key}
                platform={p.key}
                label={p.label}
                exportEntry={getExportForPlatform(p.key)}
                memoryCount={getMemoryCount(p.key)}
                onImportStarted={handleImportStarted}
              />
            ))}
          </SimpleGrid>

          <Paper withBorder radius="md" p="md">
            <Text fw={500} mb="sm">
              Upload Files
            </Text>
            <Dropzone
              onDrop={handleFileDrop}
              loading={uploading}
              accept={[
                'text/plain',
                'application/json',
                'text/csv',
                'application/pdf',
                'message/rfc822',
                'application/mbox',
              ]}
            >
              <Group justify="center" gap="xl" mih={120} style={{ pointerEvents: 'none' }}>
                <Stack align="center" gap={4}>
                  <Text size="xl" inline>
                    Drag files here or click to browse
                  </Text>
                  <Text size="sm" c="dimmed" inline>
                    Supported: TXT, JSON, CSV, PDF, EML, MBOX
                  </Text>
                </Stack>
              </Group>
            </Dropzone>
          </Paper>
        </section>

        {/* ── Jobs Section ──────────────────────────────────────── */}
        <section>
          <Title order={2} mb="md">
            Ingestion Jobs
          </Title>
          <JobsTable />
        </section>

        {/* ── Sources Section ───────────────────────────────────── */}
        <section>
          <Title order={2} mb="md">
            Source Management
          </Title>
          <SourceManager />
        </section>
      </Stack>
    </Container>
  );
}
