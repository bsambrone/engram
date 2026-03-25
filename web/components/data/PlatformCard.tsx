'use client';

import { useState } from 'react';
import {
  Card,
  Group,
  Stack,
  Text,
  Badge,
  Button,
  Modal,
  TextInput,
  Accordion,
  Alert,
  Loader,
} from '@mantine/core';
import { SourceIcon } from '@/components/common';
import { api } from '@/lib/api';
import type { ExportValidation, IngestJob, RegisteredExport } from '@/lib/types';

interface PlatformCardProps {
  platform: string;
  label: string;
  exportEntry?: RegisteredExport;
  memoryCount: number;
  onImportStarted?: () => void;
}

const PLATFORM_INSTRUCTIONS: Record<string, string> = {
  gmail:
    'Go to takeout.google.com, select Mail, download MBOX format. Extract the archive and provide the path to the extracted directory.',
  reddit:
    'Go to reddit.com/settings/data-request and request your data. Once downloaded, extract the archive and provide the path to the extracted directory.',
  facebook:
    'Go to Facebook Settings, then "Download Your Information". Select JSON format, create the export, download and extract it, then provide the path to the extracted directory.',
  instagram:
    'Go to Instagram Settings, then "Download Your Data". Select JSON format, create the export, download and extract it, then provide the path to the extracted directory.',
};

export function PlatformCard({
  platform,
  label,
  exportEntry,
  memoryCount,
  onImportStarted,
}: PlatformCardProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [exportPath, setExportPath] = useState('');
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<ExportValidation | null>(null);
  const [registering, setRegistering] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);

  async function handleValidate() {
    setValidating(true);
    setValidation(null);
    try {
      const result = await api.post<ExportValidation>('/api/ingest/export/validate', {
        platform,
        export_path: exportPath,
      });
      setValidation(result);
    } catch (err) {
      setValidation({
        valid: false,
        platform,
        export_path: exportPath,
        message: err instanceof Error ? err.message : 'Validation failed',
      });
    } finally {
      setValidating(false);
    }
  }

  async function handleRegister() {
    setRegistering(true);
    setRegisterError(null);
    try {
      await api.post<IngestJob>('/api/ingest/export', {
        platform,
        export_path: exportPath,
      });
      setModalOpen(false);
      setExportPath('');
      setValidation(null);
      onImportStarted?.();
    } catch (err) {
      setRegisterError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setRegistering(false);
    }
  }

  function statusColor(status: string): string {
    switch (status) {
      case 'pending':
        return 'yellow';
      case 'running':
        return 'blue';
      case 'completed':
        return 'green';
      case 'failed':
        return 'red';
      default:
        return 'gray';
    }
  }

  return (
    <>
      <Card withBorder radius="md" p="lg">
        <Stack gap="sm">
          <Group justify="space-between">
            <Group gap="sm">
              <SourceIcon source={platform} size="lg" />
              <Text fw={600} size="lg">
                {label}
              </Text>
            </Group>
            {exportEntry && (
              <Badge color={statusColor(exportEntry.status)} variant="light">
                {exportEntry.status}
              </Badge>
            )}
          </Group>

          <Text size="sm" c="dimmed">
            {memoryCount} memories
          </Text>

          <Button variant="light" onClick={() => setModalOpen(true)}>
            Import
          </Button>
        </Stack>
      </Card>

      <Modal
        opened={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setValidation(null);
          setRegisterError(null);
        }}
        title={`Import ${label} Data`}
        size="lg"
      >
        <Stack gap="md">
          <TextInput
            label="Export directory path"
            placeholder={`/path/to/${platform}-export`}
            value={exportPath}
            onChange={(e) => setExportPath(e.currentTarget.value)}
          />

          <Group gap="sm">
            <Button
              variant="light"
              onClick={handleValidate}
              disabled={!exportPath.trim()}
              loading={validating}
            >
              Validate
            </Button>
            <Button
              onClick={handleRegister}
              disabled={!exportPath.trim()}
              loading={registering}
            >
              Register &amp; Process
            </Button>
          </Group>

          {validation && (
            <Alert
              color={validation.valid ? 'green' : 'red'}
              title={validation.valid ? 'Valid' : 'Invalid'}
            >
              {validation.message}
              {validation.file_count != null && (
                <Text size="sm" mt={4}>
                  {validation.file_count} file(s) found
                </Text>
              )}
            </Alert>
          )}

          {registerError && (
            <Alert color="red" title="Error">
              {registerError}
            </Alert>
          )}

          <Accordion variant="separated">
            <Accordion.Item value="instructions">
              <Accordion.Control>How to export your {label} data</Accordion.Control>
              <Accordion.Panel>
                <Text size="sm">{PLATFORM_INSTRUCTIONS[platform]}</Text>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        </Stack>
      </Modal>
    </>
  );
}
