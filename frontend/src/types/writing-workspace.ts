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

export type ErrorType =
  | 'Grammar'
  | 'Vocabulary'
  | 'Spelling'
  | 'Punctuation'
  | 'Sentence Structure'
  | 'Cohesion'
  | 'Repetition'
  | 'Word Choice'
  | 'Task Response';

export type ErrorSeverity = 'critical' | 'major' | 'minor';

export interface WritingError {
  id: string;
  original: string;
  error_type: ErrorType;
  explanation: string;
  correction: string;
  severity: ErrorSeverity;
  criterion: string;
  start: number;
  end: number;
  sentence?: string;
}

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
  error_analysis?: WritingError[];
  mission_sync?: WritingMissionSync | null;
}

export interface WritingMissionSync {
  xp_earned: number;
  mission_completed: boolean;
  streak_bonus: number;
  predicted_band?: number | null;
  readiness_score?: number | null;
  weakest_skill?: string | null;
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

// ─────────────────────────────────────────────────────────────
// Writing Improvement Plan types ("Improve My Band")
// ─────────────────────────────────────────────────────────────

export type PlanPriority = "high" | "medium" | "low";

export type PlanSkillFocus =
  | "task_1"
  | "task_2"
  | "grammar"
  | "vocabulary"
  | "cohesion";

export interface ImprovementPlanChange {
  area: string;
  change: string;
  priority: PlanPriority;
}

export interface ImprovementPlanExercise {
  title: string;
  description: string;
  skill_focus: PlanSkillFocus;
  estimated_minutes: number;
}

export interface ImprovementPlanResource {
  title: string;
  url: string;
  why: string;
}

export interface ImprovementPlanMission {
  title: string;
  skill: string;
  sub_skill: string;
  duration_minutes: number;
  description: string;
}

export interface WritingImprovementPlan {
  id: string;
  evaluation_id: string;
  submission_id: string;
  task_type: WritingTaskType;
  current_band: number;
  target_band: number;
  band_gap: number;
  weaknesses: string[];
  current_level_description: string;
  target_level_description: string;
  specific_changes: ImprovementPlanChange[];
  practice_exercises: ImprovementPlanExercise[];
  recommended_resources: ImprovementPlanResource[];
  suggested_mission: ImprovementPlanMission;
  is_estimate: boolean;
  source: string;
  created_at: string | null;
}

export interface WritingImprovementPlanListResponse {
  results: WritingImprovementPlan[];
  total: number;
}

// ─────────────────────────────────────────────────────────────
// Writing Band Examples types ("Improve My Band — Examples")
// ─────────────────────────────────────────────────────────────

export interface ImprovedSentence {
  original: string;
  improved: string;
  explanation: string;
}

export interface VocabularyAlternative {
  from: string;
  to: string;
  why: string;
}

export interface BandExample {
  id: string;
  evaluation_id: string;
  submission_id: string;
  task_type: WritingTaskType;
  target_band: number;
  current_band: number;
  focus_areas: string[];
  key_weaknesses: string;
  improved_sentences: ImprovedSentence[];
  vocabulary_alternatives: VocabularyAlternative[];
  paragraph_structure: string;
  example_introduction: string;
  example_body_paragraph: string;
  example_conclusion: string;
  sample_answer: string | null;
  is_sample_answer: boolean;
  is_estimate: boolean;
  source: string;
  created_at: string | null;
}

export interface BandExampleListResponse {
  results: BandExample[];
  total: number;
}

// ─────────────────────────────────────────────────────────────
// Writing Reattempt Mode types
// ─────────────────────────────────────────────────────────────

export interface WritingAttempt {
  submission_id: string;
  attempt_number: number;
  overall_band: number | null;
  evaluated_at: string | null;
  bonus_xp: number;
}

export interface WritingAttemptGroup {
  attempt_group: string;
  title: string;
  task_type: WritingTaskType;
  attempts: WritingAttempt[];
  total_attempts: number;
}

export interface WritingAttemptListResponse {
  results: WritingAttemptGroup[];
  total: number;
}

export interface CriterionComparison {
  criterion: string;
  label: string;
  attempt_1_band: number;
  attempt_2_band: number;
  delta: number;
  improved: boolean;
}

export interface BandComparison {
  attempt_1: number;
  attempt_2: number;
  delta: number;
  improved: boolean;
}

export interface WordCountComparison {
  attempt_1: number;
  attempt_2: number;
  delta: number;
}

export interface TimeComparison {
  attempt_1: number;
  attempt_2: number;
  delta: number;
}

export interface WritingComparison {
  compared: boolean;
  reason?: string;
  original_submission_id: string;
  new_submission_id: string;
  overall_band: BandComparison;
  criteria: CriterionComparison[];
  word_count: WordCountComparison;
  time_seconds: TimeComparison;
  improvement: boolean;
}

export interface WritingReattemptEvaluateResponse {
  evaluation: WritingEvaluation;
  comparison: WritingComparison;
  attempt_number: number;
  bonus_xp: number;
  bonus_reason: string | null;
}

export interface WritingReattemptStartResponse {
  submission: WritingWorkspaceSubmission;
  original_submission_id: string;
  attempt_number: number;
  attempt_group: string;
  original_evaluation: WritingEvaluation;
}

// ─────────────────────────────────────────────────────────────
// Writing Coach Q&A types
// ─────────────────────────────────────────────────────────────

export interface WritingCoachMessage {
  id: string;
  conversation_id: string;
  role: "user" | "coach";
  content: string;
  structured: WritingCoachMessageStructured;
  created_at: string | null;
}

export interface WritingCoachMessageStructured {
  focus?: string;
  referenced_text?: string[];
  referenced_feedback?: string[];
  essay_text?: string;
  evaluation_id?: string;
  [key: string]: unknown;
}

export interface WritingCoachAnswer {
  conversation_id: string;
  answer: string;
  focus: string;
  referenced_text: string[];
  referenced_feedback: string[];
}

export interface WritingCoachConversation {
  id: string;
  user_id: string;
  evaluation_id: string;
  submission_id: string;
  title: string;
  status: "active" | "archived";
  messages: WritingCoachMessage[];
  created_at: string | null;
  updated_at: string | null;
}

export interface WritingCoachConversationListItem {
  id: string;
  evaluation_id: string;
  submission_id: string;
  title: string;
  status: "active" | "archived";
  message_count: number;
  last_message_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface WritingCoachConversationListResponse {
  items: WritingCoachConversationListItem[];
  total: number;
  limit: number;
  offset: number;
}

// ─────────────────────────────────────────────────────────────
// Speaking Error Analysis types
// ─────────────────────────────────────────────────────────────

export type SpeakingIssueType =
  | "Grammar"
  | "Repeated Vocabulary"
  | "Weak Vocabulary"
  | "Unnatural Expression"
  | "Filler Words"
  | "Repetition"
  | "Incomplete Sentence"
  | "Hesitation Indicator"
  | "Coherence Problem"
  | "Pronunciation";

export type SpeakingSeverity = "critical" | "major" | "minor";

export type SpeakingCriterion =
  | "fluency_coherence"
  | "lexical_resource"
  | "grammatical_range"
  | "pronunciation";

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

export interface SpeakingErrorAnalysisListResponse {
  results: SpeakingErrorAnalysis[];
  total: number;
}
