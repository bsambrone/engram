/** TypeScript interfaces matching Engram API responses. */

export interface Topic {
  id: string;
  name: string;
}

export interface Person {
  id: string;
  name: string;
}

export interface Memory {
  id: string;
  content: string;
  intent: string | null;
  meaning: string | null;
  source: string | null;
  source_ref: string | null;
  authorship: string | null;
  importance_score: number | null;
  confidence: number | null;
  reinforcement_count: number;
  visibility: string;
  status: string;
  timestamp: string | null;
  created_at: string | null;
  topics: Topic[];
  people: Person[];
}

export interface Belief {
  id: string;
  topic: string;
  stance: string | null;
  nuance: string | null;
  confidence: number | null;
  source: string | null;
  valid_from: string | null;
  valid_until: string | null;
}

export interface BeliefVersion {
  id: string;
  topic: string;
  stance: string | null;
  nuance: string | null;
  confidence: number | null;
  source: string | null;
  valid_from: string | null;
  valid_until: string | null;
}

export interface Preference {
  id: string;
  category: string;
  value: string | null;
  strength: number | null;
  source: string | null;
}

export interface StyleProfile {
  tone: string | null;
  humor_level: number | null;
  verbosity: number | null;
  formality: number | null;
  vocabulary_notes: string | null;
  communication_patterns: string | null;
  source: string | null;
}

export interface Profile {
  id: string;
  name: string;
  description: string | null;
}

export interface EngramResponse {
  answer: string;
  confidence: number;
  memory_refs: string[] | null;
  belief_refs: string[] | null;
  caveats: string[];
}

export interface MemoryStats {
  total_memories: number;
  by_source: Record<string, number>;
  topic_count: number;
  person_count: number;
}

export interface TopicCount {
  name: string;
  memory_count: number;
}

export interface Snapshot {
  id: string;
  profile_id: string;
  snapshot_data: Record<string, unknown>;
  label: string | null;
  created_at: string | null;
}

/* ── Ingestion & Source Management ────────────────────────────────── */

export interface IngestJob {
  job_id: string;
  source: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  items_processed: number;
  errors: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface RegisteredExport {
  id: string;
  platform: string;
  export_path: string;
  status: string;
  created_at: string | null;
}

export interface ExportValidation {
  valid: boolean;
  platform: string;
  export_path: string;
  message: string;
  file_count?: number;
}

export interface SourceInfo {
  source: string;
  memory_count: number;
  visibility_breakdown: Record<string, number>;
}
