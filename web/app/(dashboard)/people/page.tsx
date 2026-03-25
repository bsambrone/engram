'use client';

import { Title, Container, Tabs, Stack } from '@mantine/core';
import { PeopleTable } from '@/components/people/PeopleTable';
import { RelationshipGraph } from '@/components/people/RelationshipGraph';

export default function PeoplePage() {
  return (
    <Container size="lg" py="md">
      <Stack gap="md">
        <Title order={2}>People</Title>

        <Tabs defaultValue="list">
          <Tabs.List>
            <Tabs.Tab value="list">List View</Tabs.Tab>
            <Tabs.Tab value="graph">Graph View</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="list" pt="md">
            <PeopleTable />
          </Tabs.Panel>

          <Tabs.Panel value="graph" pt="md">
            <RelationshipGraph />
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Container>
  );
}
