// ─────────────────────────────────────────────────────────────
// Writing Diagnostic Module types
// Mirrors GET/POST /api/v1/writing/*
// ─────────────────────────────────────────────────────────────

export type WritingTaskType = 'task_1' | 'task_2';

export type WritingEssayStatus = 'in_progress' | 'completed';

export type WritingCriterion =
  | 'task_response'
  | 'coherence_cohesion'
  | 'lexical_resource'
  | 'grammatical_range';

export interface WritingPrompt {
  id: string;
  task_type: WritingTaskType;
  title: string;
  prompt_text: string;
  word_limit: number;
  time_limit_seconds: number;
  difficulty: number;
  topics?: string[] | null;
}

export interface WritingPromptsResponse {
  task_type: string;
  prompts: WritingPrompt[];
  total: number;
}

export interface WritingEssayStart {
  prompt_id: string;
  attempt_id?: string | null;
}

export interface WritingEssaySave {
  essay_text: string;
  time_seconds_spent?: number;
}

export interface WritingEssayComplete {
  time_seconds_spent?: number;
}

export interface ManualScoreSubmit {
  task_response: number;
  coherence_cohesion: number;
  lexical_resource: number;
  grammatical_range: number;
}

export interface WritingEssay {
  id: string;
  attempt_id: string;
  user_id: string;
  prompt_id?: string | null;
  task_type: WritingTaskType;
  title: string;
  essay_text: string;
  word_count: number;
  time_seconds_spent: number;
  status: WritingEssayStatus;
  // prompt snapshot
  prompt_text?: string | null;
  word_limit?: number | null;
  time_limit_seconds?: number | null;
  // manual scores
  task_response?: number | null;
  coherence_cohesion?: number | null;
  lexical_resource?: number | null;
  grammatical_range?: number | null;
  overall_band?: number | null;
  // AI placeholders (future)
  grammar_feedback: Record<string, unknown>;
  vocabulary_feedback: Record<string, unknown>;
  ai_evaluation: Record<string, unknown>;
  saved_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
}

export interface WritingReportResponse {
  essay: WritingEssay;
  is_scored: boolean;
  completed: boolean;
}

export interface WritingResultsListResponse {
  results: WritingEssay[];
  total: number;
}

export const WRITING_TASK_LABELS: Record<WritingTaskType, string> = {
  task_1: 'Academic Task 1',
  task_2: 'Task 2 Essay',
};

export const WRITING_CRITERIA_LABELS: Record<WritingCriterion, string> = {
  task_response: 'Task Response',
  coherence_cohesion: 'Coherence & Cohesion',
  lexical_resource: 'Lexical Resource',
  grammatical_range: 'Grammar & Accuracy',
};
