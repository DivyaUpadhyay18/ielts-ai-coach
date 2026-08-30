// ─────────────────────────────────────────────────────────────
// Speaking Diagnostic Module types
// Mirrors GET/POST /api/v1/speaking/*
// ─────────────────────────────────────────────────────────────

export type SpeakingPart = 'part_1' | 'part_2' | 'part_3';

export type SpeakingRecordingStatus = 'in_progress' | 'completed';

export type SpeakingCriterion =
  | 'fluency_coherence'
  | 'lexical_resource'
  | 'grammatical_range'
  | 'pronunciation';

export interface SpeakingPrompt {
  id: string;
  part: SpeakingPart;
  title: string;
  prompt_text: string;
  prep_time_seconds: number;
  speak_time_seconds: number;
  difficulty: number;
  topics?: string[] | null;
  follow_up?: string | null;
}

export interface SpeakingPromptsResponse {
  part: string;
  prompts: SpeakingPrompt[];
  total: number;
}

export interface SpeakingRecordingStart {
  prompt_id: string;
  attempt_id?: string | null;
}

export interface SpeakingRecordingSave {
  audio_url: string;
  duration_seconds?: number;
  transcript?: string;
}

export interface SpeakingRecordingComplete {
  duration_seconds?: number;
}

export interface SpeakingManualScoreSubmit {
  fluency_coherence: number;
  lexical_resource: number;
  grammatical_range: number;
  pronunciation: number;
}

export interface SpeakingRecording {
  id: string;
  attempt_id: string;
  user_id: string;
  prompt_id?: string | null;
  part: SpeakingPart;
  title: string;
  audio_url: string;
  duration_seconds: number;
  transcript: string;
  status: SpeakingRecordingStatus;
  // prompt snapshot
  prompt_text?: string | null;
  prep_time_seconds?: number | null;
  speak_time_seconds?: number | null;
  follow_up?: string | null;
  // manual scores
  fluency_coherence?: number | null;
  lexical_resource?: number | null;
  grammatical_range?: number | null;
  pronunciation?: number | null;
  overall_band?: number | null;
  // AI placeholder (future)
  ai_evaluation: Record<string, unknown>;
  saved_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
}

export interface SpeakingReportResponse {
  recording: SpeakingRecording;
  is_scored: boolean;
  completed: boolean;
}

export interface SpeakingResultsListResponse {
  results: SpeakingRecording[];
  total: number;
}

export const SPEAKING_PART_LABELS: Record<SpeakingPart, string> = {
  part_1: 'Part 1 — Introduction',
  part_2: 'Part 2 — Long Turn',
  part_3: 'Part 3 — Discussion',
};

export const SPEAKING_CRITERIA_LABELS: Record<SpeakingCriterion, string> = {
  fluency_coherence: 'Fluency & Coherence',
  lexical_resource: 'Lexical Resource',
  grammatical_range: 'Grammatical Range',
  pronunciation: 'Pronunciation',
};
