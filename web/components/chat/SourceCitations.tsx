'use client';

import { Accordion, Anchor, Text, Stack, Group } from '@mantine/core';

interface SourceCitationsProps {
  memory_refs?: string[] | null;
  belief_refs?: string[] | null;
}

export function SourceCitations({ memory_refs, belief_refs }: SourceCitationsProps) {
  // Only show for owner access (memory_refs is not null)
  if (memory_refs === null || memory_refs === undefined) return null;

  const totalSources = memory_refs.length + (belief_refs?.length ?? 0);
  if (totalSources === 0) return null;

  return (
    <Accordion variant="subtle" chevronPosition="left">
      <Accordion.Item value="sources">
        <Accordion.Control>
          <Text size="xs" c="dimmed">
            Sources ({totalSources})
          </Text>
        </Accordion.Control>
        <Accordion.Panel>
          <Stack gap={4}>
            {memory_refs.map((ref) => (
              <Group key={ref} gap="xs">
                <Text size="xs" c="dimmed">Memory:</Text>
                <Anchor size="xs" href={`/memories/${ref}`}>
                  {ref}
                </Anchor>
              </Group>
            ))}
            {belief_refs?.map((ref) => (
              <Group key={ref} gap="xs">
                <Text size="xs" c="dimmed">Belief:</Text>
                <Anchor size="xs" href="/identity">
                  {ref}
                </Anchor>
              </Group>
            ))}
          </Stack>
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
