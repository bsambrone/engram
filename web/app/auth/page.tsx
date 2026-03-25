'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Container,
  Paper,
  Title,
  Text,
  TextInput,
  Button,
  Alert,
  Code,
  Stack,
} from '@mantine/core';
import { setToken, clearToken } from '@/lib/auth';
import { api } from '@/lib/api';
import type { Profile } from '@/lib/types';

export default function AuthPage() {
  const router = useRouter();
  const [token, setTokenValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleConnect() {
    setError(null);
    if (!token.trim()) {
      setError('Please enter a token.');
      return;
    }

    setLoading(true);
    setToken(token.trim());

    try {
      await api.get<Profile>('/api/identity/profile');
      router.replace('/');
    } catch {
      clearToken();
      setError('Invalid token. Could not connect to Engram.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Container size={420} py={80}>
      <Title ta="center" mb="md">
        Engram
      </Title>
      <Text c="dimmed" size="sm" ta="center" mb="xl">
        Connect to your digital engram
      </Text>

      <Paper withBorder shadow="md" p="xl" radius="md">
        <Stack gap="md">
          <TextInput
            label="API Token"
            placeholder="eng_..."
            value={token}
            onChange={(e) => setTokenValue(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleConnect();
            }}
          />

          {error && (
            <Alert color="red" variant="light">
              {error}
            </Alert>
          )}

          <Button fullWidth loading={loading} onClick={handleConnect}>
            Connect
          </Button>

          <Text size="xs" c="dimmed" ta="center">
            Generate a token with: <Code>uv run engram init</Code>
          </Text>
        </Stack>
      </Paper>
    </Container>
  );
}
