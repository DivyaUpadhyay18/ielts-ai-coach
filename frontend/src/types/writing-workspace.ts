// ─────────────────────────────────────────────────────────────
// Writing Workspace types
// Mirrors GET/POST /api/v1/writing-workspace/*
// ─────────────────────────────────────────────────────────────

export type WritingTaskType = 'task_1' | 'task_2';

export type WritingSubmissionStatus = 'draft' | 'submitted';

export interface WritingWorkspacePrompt {
  id: string;
  task_type: WritingTaskType;
  title: string;
  prompt_text: string;
  word_limit: number;
  time_limit_seconds: number;
  difficulty: number;
  topics?: string[] | null;
}

export interface WritingWorkspacePromptsResponse {
  task_type: string;
  prompts: WritingWorkspacePrompt[];
  total: number;
}

export interface WritingWorkspacePromptResponse {
  id: string;
  task_type: WritingTaskType;
  title: string;
  prompt_text: string;
  word_limit: number;
  time_limit_seconds: number;
  difficulty: number;
  topics: string[];
}

export interface WritingWorkspaceSubmission {
  id: string;
  user_id: string;
  prompt_id: string | null;
  task_type: WritingTaskType;
  title: string;
  prompt_text: string | null;
  word_limit: number;
  time_limit_seconds: number;
  essay_text: string;
  word_count: number;
  time_seconds_spent: number;
  status: WritingSubmissionStatus;
  is_locked: boolean;
  evaluation_status?: string | null;
  submission_summary: WritingSubmissionSummary;
  created_at: string | null;
  updated_at: string | null;
  submitted_at: string | null;
}

export interface WritingSubmissionSummary {
  word_count: number;
  word_limit: number;
  time_seconds_spent: number;
  time_limit_seconds: number;
  meets_word_requirement: boolean;
  within_time_limit: boolean;
  warnings: string[];
  submitted_at: string | null;
}

export interface WritingWorkspaceSubmissionStart {
  prompt_id: string;
}

export interface WritingWorkspaceSubmissionSave {
  essay_text: string;
  time_seconds_spent?: number;
}

export interface WritingWorkspaceSubmissionSubmit {
  time_seconds_spent?: number;
}

export interface WritingWorkspaceSubmissionListResponse {
  results: WritingWorkspaceSubmission[];
  total: number;
}

export const WRITING_WORKSPACE_TASK_LABELS: Record<WritingTaskType, string> = {
  task_1: 'Academic Task 1',
  task_2: 'Task 2 Essay',
};

export const WRITING_WORKSPACE_TASK_DESCRIPTIONS: Record<WritingTaskType, string> = {
  task_1: 'Report / Letter (150 words, 20 minutes)',
  task_2: 'Essay (250 words, 40 minutes)',
};

// ─────────────────────────────────────────────────────────────
// Writing Evaluation types (mirrors /api/v1/writing-evaluations/*)
// ─────────────────────────────────────────────────────────────

export type EvaluationStatus = 'pending' | 'evaluated';

export interface CriterionEvaluation {
  band: number;
  label: string;
  strength: string;
  weakness: string;
  errors: string[];
  suggestions: string[];
}

export interface WritingEvaluationCriteria {
  task_response: CriterionEvaluation;
  coherence_cohesion: CriterionEvaluation;
  lexical_resource: CriterionEvaluation;
  grammatical_range_accuracy: CriterionEvaluation;
}

export interface WritingEvaluation {
  id?: string;
  submission_id: string;
  task_type: WritingTaskType;
  criteria: WritingEvaluationCriteria;
  criteria_bands: Record<string, number>;
  overall_band: number | null;
  confidence: number | null;
  is_estimate: boolean;
  word_count: number;
  source: string;
  strengths: string[];
  weaknesses: string[];
  errors: string[];
  suggestions: string[];
  evaluated_at: string | null;
  evaluation_status: EvaluationStatus;
  is_official: boolean;
}

export interface WritingEvaluationSummary {
  submission_id: string;
  overall_band: number | null;
  confidence: number | null;
  word_count: number;
  task_type: WritingTaskType;
  evaluation_status: EvaluationStatus;
  created_at: string | null;
}

export interface WritingEvaluationListResponse {
  results: WritingEvaluationSummary[];
  total: number;
}
