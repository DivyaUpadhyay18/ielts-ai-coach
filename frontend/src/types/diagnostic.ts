// ─────────────────────────────────────────────────────────────
// Diagnostic Test Framework types
// Mirrors GET/POST /api/v1/diagnostic/*
// ─────────────────────────────────────────────────────────────

export type DiagnosticSection =
  | 'reading'
  | 'listening'
  | 'writing'
  | 'speaking'
  | 'vocabulary'
  | 'grammar';

export type DiagnosticQuestionType =
  | 'multiple_choice'
  | 'true_false'
  | 'fill_blank'
  | 'short_answer'
  | 'essay'
  | 'speaking_prompt';

export type AttemptStatus = 'in_progress' | 'completed' | 'abandoned';

export interface DiagnosticQuestion {
  id: string;
  section: DiagnosticSection;
  question_type: DiagnosticQuestionType;
  prompt: string;
  passage?: string | null;
  options?: string[] | null;
  correct_answer: string;
  explanation?: string | null;
  difficulty: number;
  time_limit_seconds: number;
  order_index: number;
}

export interface QuestionBankResponse {
  section: DiagnosticSection;
  total: number;
  time_limit_seconds: number;
  questions: DiagnosticQuestion[];
}

export interface DiagnosticAttempt {
  id: string;
  user_id: string;
  status: AttemptStatus;
  current_section: DiagnosticSection;
  sections_completed: string[];
  total_seconds_spent: number;
  section_seconds: Record<string, number>;
  last_activity_at?: string | null;
  overall_band?: number | null;
  skill_scores?: Record<string, number> | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AnswerSubmit {
  section: DiagnosticSection;
  question_id: string;
  answer: string;
  time_taken_seconds?: number;
}

export interface AnsweredQuestion {
  question_id: string;
  section: DiagnosticSection;
  selected_answer: string;
  is_correct: boolean;
  time_taken_seconds: number;
}

export interface ResumeResponse {
  attempt: DiagnosticAttempt;
  answered_question_ids: string[];
  answered: AnsweredQuestion[];
}

export interface SectionComplete {
  section: DiagnosticSection;
  time_taken_seconds?: number;
}

export interface SectionScore {
  section: DiagnosticSection;
  band: number;
  accuracy: number;
}

export interface DiagnosticReport {
  attempt_id: string;
  user_id: string;
  overall_band: number;
  target_note: string;
  skill_scores: SectionScore[];
  strengths: string[];
  weaknesses: string[];
  total_time_seconds: number;
  completed_at?: string | null;
  recommended_focus_areas?: string[];
  suggested_weekly_hours?: number;
  suggested_exam_timeline_weeks?: number;
  roadmap_preview?: Record<string, unknown> | null;
}

export interface DiagnosticStartResponse {
  attempt: DiagnosticAttempt;
  is_new: boolean;
  message: string;
}
