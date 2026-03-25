'use client';

import { useEffect, useRef } from 'react';
import { Paper, Text, Badge, Alert, Group, Stack, Box } from '@mantine/core';
import { SourceCitations } from './SourceCitations';

export interface ChatMessage {
  role: 'user' | 'engram';
  content: string;
  confidence?: number;
  caveats?: string[];
  memory_refs?: string[] | null;
  belief_refs?: string[] | null;
}

interface MessageListProps {
  messages: ChatMessage[];
}

function confidenceColor(value: number): string {
  if (value < 0.3) return 'red';
  if (value < 0.7) return 'yellow';
  return 'green';
}

export function MessageList({ messages }: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <Box
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: 'var(--mantine-spacing-md)',
      }}
    >
      <Stack gap="md">
        {messages.map((msg, i) =>
          msg.role === 'user' ? (
            <Group key={i} justify="flex-end">
              <Paper
                p="sm"
                radius="md"
                bg="blue.7"
                maw="70%"
              >
                <Text size="sm" c="white">
                  {msg.content}
                </Text>
              </Paper>
            </Group>
          ) : (
            <Group key={i} justify="flex-start" align="flex-start">
              <Paper
                p="sm"
                radius="md"
                bg="dark.6"
                maw="70%"
                withBorder
              >
                <Text size="sm" mb="xs">
                  {msg.content}
                </Text>

                {msg.confidence !== undefined && (
                  <Badge
                    size="sm"
                    color={confidenceColor(msg.confidence)}
                    variant="light"
                    mb="xs"
                  >
                    Confidence: {Math.round(msg.confidence * 100)}%
                  </Badge>
                )}

                {msg.caveats && msg.caveats.length > 0 && (
                  <Alert
                    variant="light"
                    color="yellow"
                    title="Caveats"
                    p="xs"
                    mb="xs"
                  >
                    {msg.caveats.map((caveat, ci) => (
                      <Text key={ci} size="xs">
                        {caveat}
                      </Text>
                    ))}
                  </Alert>
                )}

                <SourceCitations
                  memory_refs={msg.memory_refs}
                  belief_refs={msg.belief_refs}
                />
              </Paper>
            </Group>
          )
        )}
        <div ref={endRef} />
      </Stack>
    </Box>
  );
}
