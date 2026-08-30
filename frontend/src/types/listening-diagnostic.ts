// ─────────────────────────────────────────────────────────────
// Listening Diagnostic Module types
// Mirrors GET/POST /api/v1/listening/*
// ─────────────────────────────────────────────────────────────

export type ListeningQuestionType =
  | 'multiple_choice'
  | 'map'
  | 'form_completion'
  | 'sentence_completion'
  | 'matching';

export type ListeningDifficultyLevel = 'Easy' | 'Moderate' | 'Hard';

export interface ListeningTrack {
  id: string;
  title: string;
  description?: string | null;
  audio_url: string;
  section_number: number;
  difficulty: number;
  topics?: string[] | null;
  transcript?: string | null;
}

export interface ListeningQuestion {
  id: string;
  track_id: string;
  question_type: ListeningQuestionType;
  prompt: string;
  options?: string[] | null;
  difficulty: number;
  time_limit_seconds: number;
  skill_tag?: string | null;
}

export interface ListeningBankResponse {
  tracks: ListeningTrack[];
  questions: ListeningQuestion[];
  total: number;
}

export interface ListeningAnswerSubmit {
  attempt_id: string;
  question_id: string;
  answer: string;
  time_taken_seconds?: number;
}

export interface ListeningAnswerResult {
  question_id: string;
  is_correct: boolean;
  correct_answer?: string | null;
  question_type: ListeningQuestionType;
  time_taken_seconds: number;
}

export interface ListeningTypeBreakdown {
  question_type: ListeningQuestionType;
  total: number;
  correct: number;
  accuracy: number;
  avg_time_seconds: number;
}

export interface ListeningReport {
  attempt_id: string;
  user_id: string;
  total_questions: number;
  correct_answers: number;
  accuracy: number;
  total_time_seconds: number;
  listening_band: number;
  difficulty_level: ListeningDifficultyLevel;
  type_breakdown: ListeningTypeBreakdown[];
  weak_types: ListeningQuestionType[];
  strong_types: ListeningQuestionType[];
  completed_at?: string | null;
}

export interface ListeningResultItem {
  attempt_id: string;
  total_questions: number;
  correct_answers: number;
  accuracy: number;
  listening_band: number;
  difficulty_level: ListeningDifficultyLevel;
  weak_types: ListeningQuestionType[];
  strong_types: ListeningQuestionType[];
  total_time_seconds: number;
  completed_at?: string | null;
}

export interface ListeningResultsListResponse {
  results: ListeningResultItem[];
  total: number;
}

export const LISTENING_QUESTION_TYPE_LABELS: Record<ListeningQuestionType, string> = {
  multiple_choice: 'Multiple Choice',
  map: 'Map',
  form_completion: 'Form Completion',
  sentence_completion: 'Sentence Completion',
  matching: 'Matching',
};
