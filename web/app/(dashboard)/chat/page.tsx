'use client';

import { useState, useEffect, useCallback } from 'react';
import { Box, Title, Group, ActionIcon, Paper, Text, Stack, Skeleton } from '@mantine/core';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { MessageList } from '@/components/chat/MessageList';
import { ChatInput } from '@/components/chat/ChatInput';
import type { ChatMessage } from '@/components/chat/MessageList';
import type { EngramResponse, TopicCount } from '@/lib/types';

const STORAGE_KEY = 'engram_chat_history';

function loadMessages(): ChatMessage[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // ignore corrupt data
  }
  return [];
}

function saveMessages(messages: ChatMessage[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  } catch {
    // storage full or unavailable
  }
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  const { data: topics, isLoading: topicsLoading } = useApi<TopicCount[]>('/api/engram/topics');

  // Restore from localStorage on mount
  useEffect(() => {
    setMessages(loadMessages());
    setMounted(true);
  }, []);

  // Persist whenever messages change (but not on initial mount)
  useEffect(() => {
    if (mounted) {
      saveMessages(messages);
    }
  }, [messages, mounted]);

  const handleSend = useCallback(
    async (query: string, asOfDate?: string) => {
      const userMsg: ChatMessage = { role: 'user', content: query };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);

      try {
        const body: { query: string; as_of_date?: string } = { query };
        if (asOfDate) body.as_of_date = asOfDate;

        const res = await api.post<EngramResponse>('/api/engram/ask', body);
        const engramMsg: ChatMessage = {
          role: 'engram',
          content: res.answer,
          confidence: res.confidence,
          caveats: res.caveats,
          memory_refs: res.memory_refs,
          belief_refs: res.belief_refs,
        };
        setMessages((prev) => [...prev, engramMsg]);
      } catch {
        const errorMsg: ChatMessage = {
          role: 'engram',
          content: 'Something went wrong. Please try again.',
          confidence: 0,
          caveats: [],
          memory_refs: null,
          belief_refs: null,
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  function handleClear() {
    setMessages([]);
  }

  function handleSuggestedClick(topic: string) {
    handleSend(`What do you think about ${topic}?`);
  }

  const suggestedTopics = topics?.slice(0, 5) ?? [];
  const showSuggestions = messages.length === 0 && suggestedTopics.length > 0;
  const showSuggestionsLoading = messages.length === 0 && topicsLoading;

  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 60px)',
      }}
    >
      {/* Header */}
      <Group justify="space-between" p="md" pb={0}>
        <Title order={3}>Chat</Title>
        {messages.length > 0 && (
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={handleClear}
            aria-label="Clear conversation"
            title="Clear conversation"
          >
            <span style={{ fontSize: 16 }}>&#x1F5D1;</span>
          </ActionIcon>
        )}
      </Group>

      {/* Suggested questions when empty */}
      {showSuggestionsLoading && (
        <Box p="md" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Stack gap="sm" align="center" maw={500} w="100%">
            <Text c="dimmed" mb="sm">Loading suggestions...</Text>
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} height={48} radius="md" />
            ))}
          </Stack>
        </Box>
      )}

      {showSuggestions && !topicsLoading && (
        <Box p="md" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Stack gap="sm" align="center" maw={500} w="100%">
            <Text c="dimmed" size="lg" mb="sm">
              Ask your engram anything
            </Text>
            <Text c="dimmed" size="sm" mb="md">
              Try one of these suggested questions:
            </Text>
            {suggestedTopics.map((t) => (
              <Paper
                key={t.name}
                p="sm"
                radius="md"
                withBorder
                w="100%"
                style={{ cursor: 'pointer' }}
                onClick={() => handleSuggestedClick(t.name)}
              >
                <Text size="sm">
                  What do you think about {t.name}?
                </Text>
              </Paper>
            ))}
          </Stack>
        </Box>
      )}

      {/* Empty state with no topics */}
      {messages.length === 0 && !topicsLoading && suggestedTopics.length === 0 && (
        <Box p="md" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Text c="dimmed" size="lg">
            Ask your engram anything
          </Text>
        </Box>
      )}

      {/* Message list */}
      {messages.length > 0 && <MessageList messages={messages} />}

      {/* Input bar */}
      <ChatInput onSend={handleSend} loading={loading} />
    </Box>
  );
}
