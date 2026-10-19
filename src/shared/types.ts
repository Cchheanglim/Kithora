/** Kethra API v1 response shapes (mirrors python_backend/app). */

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export type Scope = 'transcriptions:write' | 'stream:listen' | 'usage:read';
export const ALL_SCOPES: Scope[] = ['transcriptions:write', 'stream:listen', 'usage:read'];

export interface ApiKeyRecord {
  id: string;
  name: string;
  key_prefix: string;
  scopes: Scope[];
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  status: 'active' | 'revoked';
  request_count: number;
}

export interface EngineStatus {
  engine_id: string;
  display_name: string;
  is_mock: boolean;
  configured: boolean;
}

export interface Health {
  status: string;
  default_engine: string;
  engines: EngineStatus[];
}

export interface UsageLogRecord {
  id: number;
  timestamp: string;
  api_key_id: string | null;
  endpoint: string;
  engine_id: string;
  is_mock: boolean;
  status_code: number;
  audio_bytes: number;
  latency_ms: number;
  code_switched_detected: boolean;
}

export interface UsageSummary {
  total_requests: number;
  total_audio_bytes: number;
  error_count: number;
  code_switched_utterances: number;
  average_latency_ms: number | null;
  logs: UsageLogRecord[];
}

export interface NormalizationReport {
  raw_text: string;
  normalized_text: string;
  khmer_char_count: number;
  latin_word_count: number;
  switch_points: number;
  is_code_switched: boolean;
  applied_rules: string[];
}

export interface TranscriptionResult {
  id: string;
  engine_id: string;
  is_mock_engine: boolean;
  audio_metadata: { filename: string; mime_type: string; size_bytes: number };
  raw_transcript: string;
  normalized_transcript: string;
  normalization: NormalizationReport;
  processing_latency_ms: number;
  warnings: string[];
}

export interface WsStreamEvent {
  type: 'session.started' | 'transcript.partial' | 'transcript.final' | 'session.completed' | 'error';
  session_id: string;
  sequence?: number;
  text?: string;
  engine_id?: string;
  is_mock_engine?: boolean;
  latency_ms?: number;
  warnings?: string[];
  error?: { code: string; message: string; retryable: boolean };
  timestamp: string;
}
