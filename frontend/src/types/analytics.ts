// Analytics types (mirrors GET /api/v1/analytics/*)

export interface AnalyticsEvent {
  id: string;
  user_id: string | null;
  event: string;
  entity_type: string | null;
  entity_id: string | null;
  properties: Record<string, any>;
  session_id: string | null;
  timestamp: string | null;
  created_at: string | null;
}

export interface AnalyticsEventCreate {
  event: string;
  entity_type?: string;
  entity_id?: string;
  properties?: Record<string, any>;
  session_id?: string;
  timestamp?: string;
}

export interface ResourceAnalytics {
  resource_id: string;
  view_count: number;
  bookmark_count: number;
  like_count: number;
  rating_sum: number;
  rating_count: number;
  completion_count: number;
  avg_rating: number;
  updated_at: string | null;
}

export interface UserAnalytics {
  user_id: string;
  total_views: number;
  total_completions: number;
  total_bookmarks: number;
  total_likes: number;
  total_ratings: number;
  total_study_minutes: number;
  total_tasks_completed: number;
  total_sessions: number;
  last_active_at: string | null;
  updated_at: string | null;
}

export interface AnalyticsTrendPoint {
  date: string;
  label: string;
  views: number;
  completions: number;
  bookmarks: number;
  likes: number;
  ratings: number;
  study_minutes: number;
}

export interface SkillBreakdown {
  skill: string;
  views: number;
  completions: number;
  bookmarks: number;
  likes: number;
  ratings: number;
  study_minutes: number;
}

export interface ResourcePerformanceItem {
  resource_id: string;
  title: string;
  type: string;
  skill: string;
  views: number;
  bookmarks: number;
  likes: number;
  completions: number;
  avg_rating: number;
  rating_count: number;
  completion_rate: number;
}

export interface AnalyticsSummary {
  total_views: number;
  total_completions: number;
  total_bookmarks: number;
  total_likes: number;
  total_ratings: number;
  total_study_minutes: number;
  total_tasks_completed: number;
  total_sessions: number;
  avg_study_time_per_session: number;
  completion_rate: number;
  success_rate: number;
  drop_off_rate: number;
  active_days: number;
  last_active_at: string | null;
}

export interface AnalyticsDashboardResponse {
  summary: AnalyticsSummary;
  trends: AnalyticsTrendPoint[];
  skill_breakdown: SkillBreakdown[];
  top_resources: ResourcePerformanceItem[];
  recent_events: AnalyticsEvent[];
}

export interface ResourceRatingCreate {
  resource_id: string;
  rating: number;
}