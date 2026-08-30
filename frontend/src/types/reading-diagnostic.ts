// ─────────────────────────────────────────────────────────────
// Reading Diagnostic Module types
// Mirrors GET/POST /api/v1/reading/*
// ─────────────────────────────────────────────────────────────

export type ReadingQuestionType =
  | 'true_false_not_given'
  | 'matching_headings'
  | 'multiple_choice'
  | 'sentence_completion'
  | 'summary_completion'
  | 'short_answer';

export type ReadingDifficultyLevel = 'Easy' | 'Moderate' | 'Hard';

export interface ReadingPassage {
  id: string;
  title: string;
  content: string;
  difficulty: number;
  topics?: string[] | null;
  word_count: number;
}

export interface ReadingQuestion {
  id: string;
  passage_id: string;
  question_type: ReadingQuestionType;
  prompt: string;
  options?: string[] | null;
  difficulty: number;
  time_limit_seconds: number;
  skill_tag?: string | null;
}

export interface ReadingBankResponse {
  passages: ReadingPassage[];
  questions: ReadingQuestion[];
  total: number;
}

export interface ReadingAnswerSubmit {
  attempt_id: string;
  question_id: string;
  answer: string;
  time_taken_seconds?: number;
}

export interface ReadingAnswerResult {
  question_id: string;
  is_correct: boolean;
  correct_answer?: string | null;
  question_type: ReadingQuestionType;
  time_taken_seconds: number;
}

export interface ReadingTypeBreakdown {
  question_type: ReadingQuestionType;
  total: number;
  correct: number;
  accuracy: number;
  avg_time_seconds: number;
}

export interface ReadingReport {
  attempt_id: string;
  user_id: string;
  total_questions: number;
  correct_answers: number;
  accuracy: number;
  total_time_seconds: number;
  reading_band: number;
  difficulty_level: ReadingDifficultyLevel;
  type_breakdown: ReadingTypeBreakdown[];
  weak_types: ReadingQuestionType[];
  strong_types: ReadingQuestionType[];
  completed_at?: string | null;
}

export interface ReadingResultItem {
  attempt_id: string;
  total_questions: number;
  correct_answers: number;
  accuracy: number;
  reading_band: number;
  difficulty_level: ReadingDifficultyLevel;
  weak_types: ReadingQuestionType[];
  strong_types: ReadingQuestionType[];
  total_time_seconds: number;
  completed_at?: string | null;
}

export interface ReadingResultsListResponse {
  results: ReadingResultItem[];
  total: number;
}

export const READING_QUESTION_TYPE_LABELS: Record<ReadingQuestionType, string> = {
  true_false_not_given: 'True / False / Not Given',
  matching_headings: 'Matching Headings',
  multiple_choice: 'Multiple Choice',
  sentence_completion: 'Sentence Completion',
  summary_completion: 'Summary Completion',
  short_answer: 'Short Answer',
};
