// ─────────────────────────────────────────────────────────────
// Vocabulary & Grammar Diagnostic Module types
// Mirrors GET/POST /api/v1/vocab-grammar/*
// ─────────────────────────────────────────────────────────────

export type VGQuestionType =
  // Vocabulary
  | 'fill_in_the_blanks'
  | 'synonyms'
  | 'antonyms'
  // Grammar
  | 'sentence_correction'
  | 'grammar_correction'
  | 'tenses'
  | 'articles'
  | 'prepositions';

export type VGSection = 'vocabulary' | 'grammar';

export type VGDifficultyLevel = 'Easy' | 'Moderate' | 'Hard';

export interface VGQuestion {
  id: string;
  section: VGSection;
  question_type: VGQuestionType;
  prompt: string;
  options?: string[] | null;
  difficulty: number;
  time_limit_seconds: number;
  skill_tag?: string | null;
}

export interface VGBankResponse {
  questions: VGQuestion[];
  total: number;
}

export interface VGAnswerSubmit {
  attempt_id: string;
  question_id: string;
  answer: string;
  time_taken_seconds?: number;
}

export interface VGAnswerResult {
  question_id: string;
  is_correct: boolean;
  correct_answer?: string | null;
  section: VGSection;
  question_type: VGQuestionType;
  time_taken_seconds: number;
}

export interface VGTypeBreakdown {
  question_type: VGQuestionType;
  section: VGSection;
  total: number;
  correct: number;
  accuracy: number;
  avg_time_seconds: number;
}

export interface VGReport {
  attempt_id: string;
  user_id: string;
  total_questions: number;
  correct_answers: number;
  accuracy: number;
  grammar_accuracy: number;
  vocabulary_accuracy: number;
  total_time_seconds: number;
  band: number;
  difficulty_level: VGDifficultyLevel;
  type_breakdown: VGTypeBreakdown[];
  weak_grammar_topics: VGQuestionType[];
  weak_vocab_categories: VGQuestionType[];
  strong_types: VGQuestionType[];
  completed_at?: string | null;
}

export interface VGResultItem {
  attempt_id: string;
  total_questions: number;
  correct_answers: number;
  accuracy: number;
  grammar_accuracy: number;
  vocabulary_accuracy: number;
  band: number;
  difficulty_level: VGDifficultyLevel;
  weak_grammar_topics: VGQuestionType[];
  weak_vocab_categories: VGQuestionType[];
  strong_types: VGQuestionType[];
  total_time_seconds: number;
  completed_at?: string | null;
}

export interface VGResultsListResponse {
  results: VGResultItem[];
  total: number;
}

export const VG_QUESTION_TYPE_LABELS: Record<VGQuestionType, string> = {
  fill_in_the_blanks: 'Fill in the Blanks',
  synonyms: 'Synonyms',
  antonyms: 'Antonyms',
  sentence_correction: 'Sentence Correction',
  grammar_correction: 'Grammar Correction',
  tenses: 'Tenses',
  articles: 'Articles',
  prepositions: 'Prepositions',
};

export const VG_VOCABULARY_TYPES: VGQuestionType[] = [
  'fill_in_the_blanks',
  'synonyms',
  'antonyms',
];

export const VG_GRAMMAR_TYPES: VGQuestionType[] = [
  'sentence_correction',
  'grammar_correction',
  'tenses',
  'articles',
  'prepositions',
];
