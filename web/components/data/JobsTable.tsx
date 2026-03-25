'use client';

import { useState } from 'react';
import {
  Table,
  Badge,
  Text,
  Modal,
  Alert,
  Loader,
  Center,
  Box,
} from '@mantine/core';
import useSWR from 'swr';
import { api } from '@/lib/api';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import type { IngestJob } from '@/lib/types';

dayjs.extend(relativeTime);

const STATUS_COLORS: Record<string, string> = {
  pending: 'yellow',
  running: 'blue',
  completed: 'green',
  failed: 'red',
};

function formatDuration(started: string | null, completed: string | null): string {
  if (!started) return '--';
  const start = dayjs(started);
  const end = completed ? dayjs(completed) : dayjs();
  const seconds = end.diff(start, 'second');
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

export function JobsTable() {
  const [errorModal, setErrorModal] = useState<string | null>(null);

  const { data: jobs, isLoading } = useSWR<IngestJob[]>(
    '/api/ingest/jobs?limit=20',
    (url: string) => api.get<IngestJob[]>(url),
    {
      refreshInterval: (latestData) => {
        if (!latestData) return 5000;
        const hasActive = latestData.some(
          (j) => j.status === 'pending' || j.status === 'running'
        );
        return hasActive ? 5000 : 0;
      },
    }
  );

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  if (!jobs || jobs.length === 0) {
    return (
      <Center py="xl">
        <Text c="dimmed">No ingestion jobs yet</Text>
      </Center>
    );
  }

  return (
    <Box>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Source</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Items Processed</Table.Th>
            <Table.Th>Errors</Table.Th>
            <Table.Th>Started</Table.Th>
            <Table.Th>Duration</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {jobs.map((job) => (
            <Table.Tr
              key={job.job_id}
              style={{
                cursor: job.status === 'failed' ? 'pointer' : undefined,
              }}
              onClick={() => {
                if (job.status === 'failed' && job.error_message) {
                  setErrorModal(job.error_message);
                }
              }}
            >
              <Table.Td>
                <Text size="sm" fw={500}>
                  {job.source}
                </Text>
              </Table.Td>
              <Table.Td>
                <Badge
                  color={STATUS_COLORS[job.status] ?? 'gray'}
                  variant="light"
                >
                  {job.status}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{job.items_processed}</Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c={job.errors > 0 ? 'red' : undefined}>
                  {job.errors}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {job.started_at ? dayjs(job.started_at).fromNow() : '--'}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {formatDuration(job.started_at, job.completed_at)}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Modal
        opened={!!errorModal}
        onClose={() => setErrorModal(null)}
        title="Job Error Details"
      >
        <Alert color="red" title="Error">
          {errorModal}
        </Alert>
      </Modal>
    </Box>
  );
}
