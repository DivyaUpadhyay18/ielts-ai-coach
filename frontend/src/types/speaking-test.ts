// ─────────────────────────────────────────────────────────────
// Speaking Test Workspace types
// Mirrors GET/POST /api/v1/speaking-test/*
// ─────────────────────────────────────────────────────────────

export type SpeakingTestPart = 'part_1' | 'part_2' | 'part_3';

export type SpeakingTestSessionStatus = 'in_progress' | 'completed' | 'abandoned';

export interface SpeakingTestPrompt {
  id: string;
  part: SpeakingTestPart;
  title: string;
  prompt_text: string;
  prep_time_seconds: number;
  speak_time_seconds: number;
  difficulty: number;
  topics?: string[] | null;
  follow_up?: string | null;
}

export interface SpeakingTestPromptsResponse {
  part: string;
  prompts: SpeakingTestPrompt[];
  total: number;
}

export interface SpeakingTestResponse {
  id: string;
  session_id: string;
  user_id: string;
  prompt_id?: string | null;
  part: SpeakingTestPart;
  title: string;
  prompt_text: string;
  prep_time_seconds: number;
  speak_time_seconds: number;
  audio_url: string;
  duration_seconds: number;
  transcript: string;
  is_saved: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SpeakingTestSession {
  id: string;
  user_id: string;
  current_part: SpeakingTestPart;
  status: SpeakingTestSessionStatus;
  started_at?: string | null;
  updated_at?: string | null;
  completed_at?: string | null;
  responses: SpeakingTestResponse[];
}

export interface SpeakingTestProgress {
  session: SpeakingTestSession;
  parts: Record<string, {
    total_prompts: number;
    completed: number;
    responses: SpeakingTestResponse[];
  }>;
  total_responses: number;
  completed_parts: SpeakingTestPart[];
}

export interface SpeakingTestResponseSaveRequest {
  audio_url?: string;
  duration_seconds?: number;
  transcript?: string;
  is_saved?: boolean;
}

export interface ResponseStartRequest {
  session_id: string;
  prompt_id: string;
  part: SpeakingTestPart;
}

export interface AudioUploadResponse {
  audio_url: string;
  filename: string;
  size: number;
}

export const SPEAKING_TEST_PART_LABELS: Record<SpeakingTestPart, string> = {
  part_1: 'Part 1 — Introduction & Interview',
  part_2: 'Part 2 — Individual Long Turn',
  part_3: 'Part 3 — Two-way Discussion',
};

export const PART_ORDER: SpeakingTestPart[] = ['part_1', 'part_2', 'part_3'];

// ─────────────────────────────────────────────────────────────
// Speaking Error Analysis types
// ─────────────────────────────────────────────────────────────

export type SpeakingIssueType =
  | 'Grammar'
  | 'Repeated Vocabulary'
  | 'Weak Vocabulary'
  | 'Unnatural Expression'
  | 'Filler Words'
  | 'Repetition'
  | 'Incomplete Sentence'
  | 'Hesitation Indicator'
  | 'Coherence Problem'
  | 'Pronunciation';

export type SpeakingSeverity = 'critical' | 'major' | 'minor';

export type SpeakingCriterion =
  | 'fluency_coherence'
  | 'lexical_resource'
  | 'grammatical_range'
  | 'pronunciation';

export interface SpeakingErrorIssue {
  original_phrase: string;
  issue_type: SpeakingIssueType;
  explanation: string;
  why_problem: string;
  suggested_improvement: string;
  criterion_affected: SpeakingCriterion;
  severity: SpeakingSeverity;
  context?: string;
}

export interface SpeakingErrorAnalysis {
  id: string;
  response_id: string;
  part: string;
  topic: string;
  issues: SpeakingErrorIssue[];
  overall_band: number;
  fluency_coherence_band: number;
  lexical_resource_band: number;
  grammatical_range_band: number;
  pronunciation_band: number;
  feedback: string;
  issue_count: number;
  high_severity_count: number;
  medium_severity_count: number;
  low_severity_count: number;
  is_estimate: boolean;
  source: string;
  created_at: string | null;
}

// ─────────────────────────────────────────────────────────────
// Speaking Improvement Plan types ("Improve My Speaking Band")
// ─────────────────────────────────────────────────────────────

export type SpeakingPriority = "high" | "medium" | "low";

export interface SpeakingSpecificChange {
  area: string;
  change: string;
  priority: SpeakingPriority;
}

export interface SpeakingPracticeExercise {
  title: string;
  description: string;
  skill_focus: string;
  estimated_minutes: number;
}

export interface SpeakingResource {
  title: string;
  url: string;
  why: string;
}

export interface SpeakingMission {
  title: string;
  skill: string;
  sub_skill: string;
  duration_minutes: number;
  description: string;
}

export interface SpeakingImprovementPlan {
  id: string;
  response_id: string;
  current_band: number;
  target_band: number;
  band_gap: number;
  strongest_criterion: string;
  weakest_criterion: string;
  criterion_priorities: Record<string, SpeakingPriority>;
  current_level_description: string;
  target_level_description: string;
  specific_changes: SpeakingSpecificChange[];
  practice_exercises: SpeakingPracticeExercise[];
  practice_topics: string[];
  recommended_resources: SpeakingResource[];
  suggested_daily_minutes: number;
  next_speaking_task: string;
  suggested_mission: SpeakingMission;
  is_estimate: boolean;
  source: string;
  created_at: string | null;
}

export interface SpeakingImprovementPlanListResponse {
  results: SpeakingImprovementPlan[];
  total: number;
}

// ─────────────────────────────────────────────────────────────
// Speaking Practice Mode types
// ─────────────────────────────────────────────────────────────

export type SpeakingPracticeMode =
  | "quick_practice"
  | "part_1_practice"
  | "part_2_practice"
  | "part_3_practice"
  | "vocabulary_practice"
  | "fluency_practice"
  | "random_question"
  | "weak_area_practice";

export interface SpeakingPracticeSession {
  id: string;
  user_id: string;
  practice_mode: SpeakingPracticeMode;
  prompt_id: string | null;
  part: string;
  title: string;
  prompt_text: string;
  prep_time_seconds: number;
  speak_time_seconds: number;
  audio_url: string;
  duration_seconds: number;
  transcript: string;
  overall_band: number | null;
  fluency_coherence_band: number | null;
  lexical_resource_band: number | null;
  grammatical_range_band: number | null;
  pronunciation_band: number | null;
  error_count: number;
  filler_words_count: number;
  feedback: string | null;
  next_recommendation: string | null;
  status: string;
  mission_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
}

export interface SpeakingPracticeSessionListResponse {
  results: SpeakingPracticeSession[];
  total: number;
}

// ─────────────────────────────────────────────────────────────
// Speaking Interactive Coach types
// ─────────────────────────────────────────────────────────────

export interface SpeakingCoachReply {
  answer: string;
  key_points: string[];
  example: string;
  action_step: string;
  tone: string;
  source: string;
}

export interface SpeakingCoachMessage {
  role: string;
  content: string;
  metadata?: {
    key_points: string[];
    example: string;
    action_step: string;
    tone: string;
    source: string;
  };
}

export interface SpeakingCoachConversation {
  id: string;
  user_id: string;
  context_type: string;
  context_id: string;
  practice_mode: string | null;
  part: string | null;
  target_band: number | null;
  current_weaknesses: string[];
  messages: SpeakingCoachMessage[];
  summary: string | null;
  created_at: string | null;
  updated_at: string | null;
  context?: {
    transcript: string;
    question: string;
    evaluation: Record<string, any>;
    weaknesses: string[];
    previous_attempts: any[];
    target_band: number | null;
  };
}

export interface SpeakingCoachChatResult {
  conversation_id: string;
  reply: SpeakingCoachReply;
  updated_messages: SpeakingCoachMessage[];
}

// ─────────────────────────────────────────────────────────────
// Speaking Progress Analytics types
// ─────────────────────────────────────────────────────────────

export interface SpeakingAnalyticsBandHistoryPoint {
  evaluation_id: string;
  date: string;
  overall_band: number | null;
  fluency_coherence_band: number | null;
  lexical_resource_band: number | null;
  grammatical_range_band: number | null;
  pronunciation_band: number | null;
  part: string;
  title: string | null;
  confidence: number | null;
}

export interface SpeakingAnalyticsBandHistoryResponse {
  results: SpeakingAnalyticsBandHistoryPoint[];
  total: number;
}

export interface SpeakingAnalyticsCriterionHistoryPoint {
  evaluation_id: string;
  date: string;
  band: number | null;
  part: string;
  title: string | null;
}

export interface SpeakingAnalyticsCriterionHistoryResponse {
  criterion: string;
  label: string;
  results: SpeakingAnalyticsCriterionHistoryPoint[];
  total: number;
}

export interface SpeakingAnalyticsMetrics {
  total_evaluations: number;
  average_band: number | null;
  average_fluency_band: number | null;
  average_lexical_band: number | null;
  average_grammar_band: number | null;
  average_pronunciation_band: number | null;
  average_duration: number | null;
  average_filler_words: number | null;
  strongest_criterion: string | null;
  strongest_criterion_label: string | null;
  weakest_criterion: string | null;
  weakest_criterion_label: string | null;
}

export interface SpeakingAnalyticsCommonError {
  error: string;
  count: number;
}

export interface SpeakingAnalyticsCommonErrors {
  common_grammar_errors: SpeakingAnalyticsCommonError[];
  common_vocabulary_errors: SpeakingAnalyticsCommonError[];
  total_grammar_errors: number;
  total_vocabulary_errors: number;
}

export interface SpeakingAnalyticsImprovementRate {
  criterion: string;
  label: string;
  improvement_rate: number;
  total_points: number;
  first_band: number | null;
  latest_band: number | null;
  trend: string;
}

export interface SpeakingAnalyticsAttemptHistoryItem {
  evaluation_id: string;
  date: string;
  overall_band: number | null;
  part: string;
  title: string | null;
  error_count: number;
  filler_words: number;
  duration_seconds: number;
  confidence: number | null;
  source: string | null;
}

export interface SpeakingAnalyticsDashboardResponse {
  band_history: SpeakingAnalyticsBandHistoryPoint[];
  metrics: SpeakingAnalyticsMetrics;
  common_errors: SpeakingAnalyticsCommonErrors;
  strongest_criterion: string | null;
  weakest_criterion: string | null;
  improvement_rate: SpeakingAnalyticsImprovementRate;
  attempt_history: SpeakingAnalyticsAttemptHistoryItem[];
  total_evaluations: number;
}
