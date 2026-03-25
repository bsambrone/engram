'use client';

import { useState } from 'react';
import { Group, TextInput, ActionIcon, Box } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';

interface ChatInputProps {
  onSend: (query: string, asOfDate?: string) => void;
  loading: boolean;
}

export function ChatInput({ onSend, loading }: ChatInputProps) {
  const [query, setQuery] = useState('');
  const [showDate, setShowDate] = useState(false);
  const [asOfDate, setAsOfDate] = useState<string | null>(null);

  function handleSend() {
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    onSend(trimmed, asOfDate ?? undefined);
    setQuery('');
  }

  return (
    <Box
      p="md"
      style={{
        borderTop: '1px solid var(--mantine-color-dark-4)',
      }}
    >
      {showDate && (
        <Box mb="xs" maw={250}>
          <DatePickerInput
            placeholder="As of date (optional)"
            value={asOfDate}
            onChange={setAsOfDate}
            clearable
            size="xs"
          />
        </Box>
      )}
      <Group gap="xs">
        <ActionIcon
          variant={showDate ? 'filled' : 'subtle'}
          size="lg"
          onClick={() => setShowDate((v) => !v)}
          aria-label="Toggle date filter"
          color={showDate ? 'blue' : 'gray'}
        >
          <span style={{ fontSize: 16 }}>&#x1F552;</span>
        </ActionIcon>
        <TextInput
          placeholder="Ask your engram..."
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSend();
          }}
          style={{ flex: 1 }}
          disabled={loading}
        />
        <ActionIcon
          variant="filled"
          size="lg"
          onClick={handleSend}
          loading={loading}
          aria-label="Send"
        >
          <span style={{ fontSize: 16 }}>&#x27A4;</span>
        </ActionIcon>
      </Group>
    </Box>
  );
}
