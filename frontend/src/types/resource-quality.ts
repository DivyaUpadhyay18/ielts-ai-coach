/**
 * Resource Quality Scoring - TypeScript Types
 *
 * Backs the /api/v1/resource-quality endpoints. Supports:
 *   - User feedback (broken links, better resources, corrections, ratings)
 *   - Admin moderation (approve/reject/resolve/dismiss)
 *   - Quality scoring (quality, popularity, completion, recommendation scores)
 */

// ─── Feedback Types ──────────────────────────────────────────────────────────

export type FeedbackType = 'broken_link' | 'better_resource' | 'correction' | 'rating';
export type FeedbackStatus = 'pending' | 'approved' | 'rejected' | 'resolved' | 'dismissed';
export type FeedbackPriority = 'low' | 'normal' | 'high' | 'urgent';
export type ModerationActionType =
  | 'approved'
  | 'rejected'
  | 'resolved'
  | 'dismissed'
  | 'escalated'
  | 'commented';

export const FEEDBACK_TYPES: FeedbackType[] = [
  'broken_link',
  'better_resource',
  'correction',
  'rating',
];

export const FEEDBACK_STATUSES: FeedbackStatus[] = [
  'pending',
  'approved',
  'rejected',
  'resolved',
  'dismissed',
];

export const FEEDBACK_PRIORITIES: FeedbackPriority[] = [
  'low',
  'normal',
  'high',
  'urgent',
];

export const MODERATION_ACTIONS: ModerationActionType[] = [
  'approved',
  'rejected',
  'resolved',
  'dismissed',
  'escalated',
  'commented',
];

// ─── Feedback ────────────────────────────────────────────────────────────────

export interface ResourceFeedbackCreate {
  resource_id: string;
  feedback_type: FeedbackType;
  title?: string;
  description?: string;
  suggested_url?: string;
  suggested_title?: string;
  field_name?: string;
  suggested_value?: string;
  reason?: string;
  rating?: number;
}

export interface ResourceFeedback {
  id: string;
  user_id: string;
  resource_id: string;
  feedback_type: FeedbackType;
  title?: string;
  description?: string;
  suggested_url?: string;
  suggested_title?: string;
  field_name?: string;
  suggested_value?: string;
  reason?: string;
  rating?: number;
  status: FeedbackStatus;
  priority: FeedbackPriority;
  admin_notes?: string;
  moderated_by?: string;
  moderated_at?: string;
  resolved_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ResourceFeedbackListResponse {
  items: ResourceFeedback[];
  total: number;
  limit: number;
  offset: number;
}

// ─── Moderation ──────────────────────────────────────────────────────────────

export interface ModerationAction {
  action: ModerationActionType;
  admin_notes?: string;
  new_priority?: FeedbackPriority;
}

export interface ModerationLog {
  id: string;
  feedback_id: string;
  admin_id: string;
  action: ModerationActionType;
  old_status?: string;
  new_status?: string;
  notes?: string;
  created_at?: string;
}

export interface ModerationQueue {
  items: ResourceFeedback[];
  total: number;
  pending_count: number;
  high_priority_count: number;
  broken_link_count: number;
  correction_count: number;
  suggestion_count: number;
}

// ─── Quality Scores ──────────────────────────────────────────────────────────

export interface ResourceQualityScores {
  resource_id: string;
  quality_score: number;
  popularity_score: number;
  completion_score: number;
  recommendation_score: number;
  avg_rating: number;
  rating_count: number;
  view_count: number;
  bookmark_count: number;
  like_count: number;
  completion_count: number;
  broken_link_count: number;
  correction_count: number;
  suggestion_count: number;
  computed_at?: string;
  updated_at?: string;
}

export interface ResourceQualityLeaderboardItem {
  resource_id: string;
  title: string;
  type: string;
  skill: string;
  quality_score: number;
  popularity_score: number;
  completion_score: number;
  recommendation_score: number;
  avg_rating: number;
  rating_count: number;
  view_count: number;
  like_count: number;
  completion_count: number;
}

export interface ResourceQualityLeaderboard {
  items: ResourceQualityLeaderboardItem[];
  total: number;
}

export interface QualityScoreBreakdown {
  resource_id: string;
  quality_score: number;
  popularity_score: number;
  completion_score: number;
  recommendation_score: number;
  components: Record<string, unknown>;
  weights: Record<string, number>;
  computed_at?: string;
}

// ─── Stats ───────────────────────────────────────────────────────────────────

export interface ResourceQualityStats {
  total_feedback: number;
  pending_feedback: number;
  approved_feedback: number;
  rejected_feedback: number;
  resolved_feedback: number;
  dismissed_feedback: number;
  broken_link_reports: number;
  correction_suggestions: number;
  better_resource_suggestions: number;
  rating_feedback: number;
  total_resources_scored: number;
  avg_quality_score: number;
  avg_popularity_score: number;
  avg_completion_score: number;
  avg_recommendation_score: number;
}

// ─── Recompute Result ────────────────────────────────────────────────────────

export interface RecomputeAllResult {
  total: number;
  computed: number;
  errors: number;
}