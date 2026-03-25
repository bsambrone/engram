'use client';

import { TextInput, MultiSelect, SegmentedControl, Select, Group, Box } from '@mantine/core';
import { DatePickerInput, type DatePickerType } from '@mantine/dates';

export interface MemoryFilterValues {
  q: string;
  sources: string[];
  visibility: string;
  sort: string;
  dateRange: [Date | null, Date | null];
}

interface MemoryFiltersProps {
  value: MemoryFilterValues;
  onChange: (filters: MemoryFilterValues) => void;
}

const SOURCE_OPTIONS = [
  { value: 'gmail', label: 'Gmail' },
  { value: 'reddit', label: 'Reddit' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'instagram', label: 'Instagram' },
];

const VISIBILITY_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'private', label: 'Private' },
  { value: 'excluded', label: 'Excluded' },
];

const SORT_OPTIONS = [
  { value: 'date', label: 'Date' },
  { value: 'importance', label: 'Importance' },
  { value: 'reinforcement', label: 'Reinforcement' },
];

export function MemoryFilters({ value, onChange }: MemoryFiltersProps) {
  function update(patch: Partial<MemoryFilterValues>) {
    onChange({ ...value, ...patch });
  }

  return (
    <Box>
      <Group gap="sm" wrap="wrap">
        <TextInput
          placeholder="Search memories..."
          value={value.q}
          onChange={(e) => update({ q: e.currentTarget.value })}
          style={{ minWidth: 200, flex: 1 }}
        />
        <MultiSelect
          data={SOURCE_OPTIONS}
          placeholder="Sources"
          value={value.sources}
          onChange={(sources) => update({ sources })}
          clearable
          style={{ minWidth: 200 }}
        />
        <SegmentedControl
          data={VISIBILITY_OPTIONS}
          value={value.visibility}
          onChange={(visibility) => update({ visibility })}
          size="sm"
        />
        <Select
          data={SORT_OPTIONS}
          value={value.sort}
          onChange={(sort) => update({ sort: sort ?? 'date' })}
          style={{ minWidth: 140 }}
          allowDeselect={false}
        />
        <DatePickerInput<'range'>
          type="range"
          placeholder="Date range"
          value={value.dateRange}
          onChange={(dateRange) => update({ dateRange: dateRange as [Date | null, Date | null] })}
          clearable
          style={{ minWidth: 220 }}
        />
      </Group>
    </Box>
  );
}
