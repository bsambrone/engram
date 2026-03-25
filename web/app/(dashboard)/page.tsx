'use client';

import { Title, Text, Container } from '@mantine/core';

export default function DashboardPage() {
  return (
    <Container>
      <Title order={2}>Dashboard</Title>
      <Text c="dimmed" mt="sm">Your digital engram overview.</Text>
    </Container>
  );
}
