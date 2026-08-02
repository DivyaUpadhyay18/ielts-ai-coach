export type IELTSBandScore = 0 | 1 | 1.5 | 2 | 2.5 | 3 | 3.5 | 4 | 4.5 | 5 | 5.5 | 6 | 6.5 | 7 | 7.5 | 8 | 8.5 | 9;

export interface Assessment {
  id: string;
  user_id: string;
  task_type: 'Writing Task 1' | 'Writing Task 2' | 'Speaking';
  user_input: string;
  band_score: number;
  feedback: string;
  corrections: string[];
  created_at: string;
}

export interface UserProfile {
  id: string;
  full_name?: string;
  email?: string;
  avatar_url?: string;
  target_band?: number;
  joined_at: string;
}

export interface AIResponse {
  score: number;
  analysis: string;
  suggestions: string[];
}

// ─────────────────────────────────────────────────────────────
// Dashboard types (mirrors GET /api/v1/dashboard/overview)
// ─────────────────────────────────────────────────────────────

export interface DashboardUser {
  id: string;
  full_name: string;
  first_name: string;
}

export interface DashboardCountdown {
  exam_date: string | null;
  days_left: number | null;
  intensity: 'normal' | 'focused' | 'intensive' | 'final' | null;
  exam_set: boolean;
}

export interface PredictedBand {
  band: number | null;
  trend: number | null;
  confidence: number | null;
  note: string;
}

export interface MissionTask {
  id: string;
  title: string;
  skill: string;
  duration_minutes: number;
  status: string;
  completed: boolean;
}

export interface MissionSummary {
  has_plan: boolean;
  phase_title: string;
  phase_status: string;
  total_tasks: number;
  completed_tasks: number;
  total_minutes: number;
  tasks: MissionTask[];
}

export interface ProgressCounters {
  tasks_completed: number;
  tasks_target: number;
  percent: number;
}

export interface ProgressData {
  daily: ProgressCounters;
  weekly: ProgressCounters;
}

export interface StudyTimeData {
  today_minutes: number;
  week_minutes: number;
  budget_minutes: number;
  tracking_note: string;
}

export interface XPData {
  today: number;
  daily_target: number;
  level: number;
  level_progress: number;
  total: number;
  note: string;
}

export interface StreakData {
  current: number;
  longest: number;
  at_risk: boolean;
  note: string;
}

export interface DailyGoalData {
  target_minutes: number;
  completed_minutes: number;
  percent: number;
}

export interface WeeklyGoalData {
  target_minutes: number;
  completed_minutes: number;
  target_tasks: number;
  completed_tasks: number;
  percent: number;
}

export interface ContinueLearningData {
  has_item: boolean;
  title?: string;
  type?: string;
  duration_minutes?: number;
  progress?: number | null;
}

export interface UpcomingMockData {
  has_mock: boolean;
  note: string;
}

export interface RecentActivityItem {
  type: string;
  title: string;
  meta: string;
  created_at: string | null;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string | null;
}

export interface DashboardNotifications {
  unread_count: number;
  items: NotificationItem[];
}

// ─────────────────────────────────────────────────────────────
// Daily Mission types (mirrors GET /api/v1/daily-missions/*)
// ─────────────────────────────────────────────────────────────

export type MissionSkill =
  | 'reading'
  | 'listening'
  | 'writing'
  | 'speaking'
  | 'vocabulary'
  | 'grammar';

export type MissionStatus = 'pending' | 'completed' | 'skipped';

export interface DailyMission {
  id: string;
  user_id: string;
  mission_date: string;
  skill: MissionSkill;
  title: string;
  estimated_minutes: number;
  xp_reward: number;
  completion_percent: number;
  status: MissionStatus;
  created_at: string | null;
  updated_at: string | null;
}

export interface DailyMissionSummary {
  mission_date: string;
  total_missions: number;
  completed_missions: number;
  skipped_missions: number;
  pending_missions: number;
  total_estimated_minutes: number;
  total_xp_reward: number;
  earned_xp: number;
  completion_percent: number;
}

export interface DailyMissionListResponse {
  missions: DailyMission[];
  summary: DailyMissionSummary;
}

export interface DailyMissionGenerateResponse {
  generated: number;
  skipped: number;
  date_range: string;
}

export interface DashboardDailyMissions {
  mission_date: string;
  missions: DailyMission[];
  summary: DailyMissionSummary;
  generated: boolean;
  note: string;
}

export interface DashboardMessage {
  greeting: string;
  text: string;
  type: 'info' | 'success' | 'motivation';
}

// ─────────────────────────────────────────────────────────────
// Progress Tracking types (mirrors GET /api/v1/progress-tracking/*)
// ─────────────────────────────────────────────────────────────

export interface StudySession {
  id: string;
  user_id: string;
  activity_date: string;
  skill: MissionSkill | null;
  session_type: string;
  minutes: number;
  xp_earned: number;
  source_type: string;
  source_id: string | null;
  meta: Record<string, unknown> | null;
  created_at: string | null;
}

export interface StudySessionInput {
  activity_date?: string;
  skill?: MissionSkill | null;
  session_type?: string;
  minutes: number;
  xp_earned?: number;
  source_type?: string;
  source_id?: string | null;
  meta?: Record<string, unknown>;
}

export interface StreakInfoData {
  current: number;
  longest: number;
  at_risk: boolean;
  last_active_date: string | null;
  note: string;
}

export interface PeriodProgressData {
  period_start: string;
  period_end: string;
  minutes: number;
  tasks_completed: number;
  xp_earned: number;
  target_minutes: number;
  target_tasks: number;
  percent: number;
}

export interface ChartPointData {
  date: string | null;
  label: string;
  minutes: number;
  tasks: number;
  xp: number;
}

export interface ChartsData {
  daily_series: ChartPointData[];
  monthly_series: ChartPointData[];
  skill_totals: Record<string, { minutes: number; tasks: number }>;
}

export interface RecentHistoryItem {
  id: string;
  date: string;
  title: string;
  skill: MissionSkill | null;
  session_type: string;
  minutes: number;
  xp: number;
}

export interface ProgressOverviewResponse {
  xp: XPData;
  streak: StreakInfoData;
  study_time: StudyTimeData;
  daily: PeriodProgressData;
  weekly: PeriodProgressData;
  monthly: PeriodProgressData;
  total_minutes: number;
  total_tasks: number;
  total_xp: number;
}

export interface ChartsResponse extends ChartsData {}

export interface HistoryResponse {
  items: RecentHistoryItem[];
}

// ─────────────────────────────────────────────────────────────
// Streak System types (mirrors GET /api/v1/streaks/*)
// ─────────────────────────────────────────────────────────────

export interface StreakLevelInfo {
  kind: 'daily' | 'weekly' | 'monthly';
  current: number;
  longest: number;
  at_risk: boolean;
  last_active: string | null;
  target: number;
}

export interface StreakBonusInfo {
  total_bonus_xp: number;
  perfect_day_xp: number;
  milestone_xp: number;
  perfect_day_count: number;
}

export interface PerfectDayInfo {
  achieved: boolean;
  bonus_xp: number;
  last_perfect_date: string | null;
  perfect_day_count: number;
  remaining_missions: number;
}

export interface CarryForwardInfo {
  bank_minutes: number;
  cap_minutes: number;
  next_miss_covered: boolean;
}

export interface FreezeInfo {
  available: number;
  used: number;
  can_use: boolean;
  note: string;
}

export interface NextMilestone {
  label: string;
  target: number;
  current: number;
  remaining: number;
  xp_bonus: number;
}

export interface StreakEventItem {
  id: string;
  event_type: string;
  label: string;
  period_key: string;
  xp_awarded: number;
  created_at: string | null;
}

export interface StreakFreeze {
  id: string;
  user_id: string;
  period_type: 'day' | 'week' | 'month';
  status: 'available' | 'used';
  granted_at: string | null;
  used_at: string | null;
  expires_at: string | null;
  source: string;
}

export interface StreakLinePoint {
  date: string;
  label: string;
  value: number;
  note: string;
}

export interface StreakOverviewResponse {
  daily: StreakLevelInfo;
  weekly: StreakLevelInfo;
  monthly: StreakLevelInfo;
  perfect_day: PerfectDayInfo;
  carry_forward: CarryForwardInfo;
  freezes: FreezeInfo;
  bonuses: StreakBonusInfo;
  next_milestones: NextMilestone[];
  history: StreakLinePoint[];
  last_streak_update: string | null;
}

// ─────────────────────────────────────────────────────────────
// Adaptive Scheduler types (mirrors GET /api/v1/scheduler/*)
// ─────────────────────────────────────────────────────────────

export interface SchedulerMetrics {
  total_pending: number;
  completed_yesterday: number;
  missed_yesterday: number;
  carried_forward: number;
  rescheduled: number;
  deprioritized: number;
  days_remaining: number;
  completion_rate: number;
  previous_workload_minutes: number;
  new_workload_minutes: number;
  workload_percent: number;
  overload_factor: number;
  adjustment_count: number;
}

export type SchedulerAction =
  | 'rescheduled'
  | 'carried_forward'
  | 'deprioritized'
  | 'spread'
  | 'merged'
  | 'kept'
  | 'split';

export interface SchedulerAdjustment {
  id: string;
  run_id?: string | null;
  task_id?: string | null;
  task_title?: string | null;
  from_date?: string | null;
  to_date?: string | null;
  action: SchedulerAction;
  reason: string;
  priority_delta: number;
}

export interface SchedulerRun {
  id: string;
  user_id: string;
  study_plan_id?: string | null;
  trigger_type: 'midnight' | 'app_open' | 'manual';
  run_date: string;
  metrics: SchedulerMetrics;
  summary?: string | null;
  created_at?: string | null;
}

export interface SchedulerExplain {
  would_change: boolean;
  metrics: SchedulerMetrics;
  adjustments: SchedulerAdjustment[];
  note: string;
}

export interface SchedulerRunPayload {
  run: Record<string, unknown> | null;
  metrics: SchedulerMetrics;
  adjustments: SchedulerAdjustment[];
  summary?: string;
}

export interface SchedulerRunPayloadOptional {
  run?: Record<string, unknown> | null;
  metrics?: SchedulerMetrics;
  adjustments?: SchedulerAdjustment[];
  summary?: string;
}

// ─────────────────────────────────────────────────────────────
// Enriched Dashboard Overview
// ─────────────────────────────────────────────────────────────

export interface DashboardOverview {
  user: DashboardUser;
  countdown: DashboardCountdown;
  current_band: number | null;
  target_band: number | null;
  predicted_band: PredictedBand;
  mission: MissionSummary;
  progress: ProgressData;
  study_time: StudyTimeData;
  xp: XPData;
  streak: StreakData;
  streak_detail?: StreakOverviewResponse;
  daily_goal: DailyGoalData;
  weekly_goal: WeeklyGoalData;
  progress_monthly: PeriodProgressData;
  progress_charts: ChartsData;
  progress_history: RecentHistoryItem[];
  progress_totals: {
    total_minutes: number;
    total_tasks: number;
    total_xp: number;
  };
  continue_learning: ContinueLearningData;
  upcoming_mock: UpcomingMockData;
  recent_activity: RecentActivityItem[];
  notifications: DashboardNotifications;
  daily_missions: DashboardDailyMissions;
  message: DashboardMessage;
}

// ─────────────────────────────────────────────────────────────
// Exam Countdown types (mirrors GET /api/v1/countdown/*)
// ─────────────────────────────────────────────────────────────

export type IntensityLevel = 'normal' | 'focused' | 'intensive' | 'final';

export interface StudyHoursData {
  planned: number;
  completed: number;
  remaining: number;
}

export interface ExamCountdown {
  exam_date: string;
  today: string;
  days_remaining: number;
  weeks_remaining: number;
  study_hours: StudyHoursData;
  completion_percentage: number;
  intensity: IntensityLevel;
  has_active_plan: boolean;
  study_plan_id: string | null;
  study_plan_version: number;
}

export interface ExamDateUpdateRequest {
  exam_date: string;
  auto_regenerate?: boolean;
}

export interface ExamDateUpdateResponse {
  exam_date: string;
  previous_exam_date: string | null;
  regenerated: boolean;
  new_study_plan_id: string | null;
  new_study_plan_version: number | null;
  message: string;
}

// ─────────────────────────────────────────────────────────────
// Prediction Engine types (mirrors GET /api/v1/prediction/*)
// ─────────────────────────────────────────────────────────────

export interface PredictionMetrics {
  total_tasks: number;
  completed_tasks: number;
  skipped_tasks: number;
  completion_rate: number;
  study_minutes: number;
  study_hours: number;
  daily_streak: number;
  longest_streak: number;
  missed_days: number;
  active_days: number;
  total_days_since_start: number;
  study_consistency: number;
  mock_test_count: number;
  latest_mock_band: number | null;
  average_mock_band: number | null;
  days_remaining: number;
}

export interface PredictionResponse {
  user_id: string;
  generated_at: string;
  run_date: string;
  preparation_percentage: number;
  estimated_band: number;
  study_consistency: number;
  completion_rate: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  readiness_score: number;
  current_band: number | null;
  target_band: number | null;
  days_remaining: number;
  intensity: string;
  metrics: PredictionMetrics;
  formulas: Record<string, string>;
  recommendations: string[];
}

export interface PredictionHistoryItem {
  id: string;
  user_id: string;
  run_date: string;
  generated_at: string;
  preparation_percentage: number;
  estimated_band: number;
  study_consistency: number;
  completion_rate: number;
  risk_level: string;
  readiness_score: number;
  metrics_json: Record<string, any>;
}

export interface PredictionHistoryResponse {
  items: PredictionHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

// ─────────────────────────────────────────────────────────────
// Timeline View types (mirrors GET /api/v1/tasks/timeline)
// ─────────────────────────────────────────────────────────────

export interface TimelineTask {
  id: string;
  title: string;
  skill: string;
  task_type: string;
  status: string;
  duration_minutes: number;
  priority: number;
  scheduled_date: string;
  created_at: string | null;
}

export interface TimelineDay {
  date: string;
  display_date: string;
  is_today: boolean;
  is_exam_day: boolean;
  total_tasks: number;
  completed_tasks: number;
  pending_tasks: number;
  missed_tasks: number;
  upcoming_tasks: number;
  revision_tasks: number;
  mock_tests: number;
  total_minutes: number;
  completed_minutes: number;
  completion_percent: number;
  tasks: TimelineTask[];
  resources: any[];
}

export interface TimelineResponse {
  exam_date: string;
  today: string;
  total_days: number;
  days: TimelineDay[];
}

// ─────────────────────────────────────────────────────────────
// Schedule History types (mirrors GET /api/v1/schedule-history/*)
// ─────────────────────────────────────────────────────────────

export type ScheduleChangeType =
  | 'scheduler_run'
  | 'exam_date_update'
  | 'manual_reschedule'
  | 'study_plan_regeneration'
  | 'task_modification'
  | 'user_override';

export type UserAction =
  | 'accepted'
  | 'rejected'
  | 'modified'
  | 'pending'
  | 'auto_applied';

export type ScheduleTriggerType =
  | 'midnight'
  | 'app_open'
  | 'manual'
  | 'system'
  | 'user';

export interface ScheduleHistoryEntry {
  id: string;
  user_id: string;
  study_plan_id?: string | null;
  run_id?: string | null;
  previous_schedule: Record<string, any>;
  new_schedule: Record<string, any>;
  change_reason: string;
  change_type: ScheduleChangeType;
  trigger_type?: ScheduleTriggerType | null;
  user_action?: UserAction | null;
  user_action_at?: string | null;
  user_action_notes?: string | null;
  metrics_before: Record<string, any>;
  metrics_after: Record<string, any>;
  summary?: string | null;
  adjustments_count: number;
  tasks_affected: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ScheduleHistoryListResponse {
  items: ScheduleHistoryEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface ScheduleComparisonResponse {
  history_1_id: string;
  history_2_id: string;
  history_1_date: string;
  history_2_date: string;
  history_1_change_type: ScheduleChangeType;
  history_2_change_type: ScheduleChangeType;
  tasks_added: number;
  tasks_removed: number;
  tasks_rescheduled: number;
  workload_change_minutes: number;
  completion_rate_change: number;
}

export interface ScheduleHistoryStats {
  total_changes: number;
  scheduler_runs: number;
  exam_date_updates: number;
  manual_reschedules: number;
  regenerations: number;
  accepted: number;
  rejected: number;
  modified: number;
  auto_applied: number;
  total_adjustments: number;
  total_tasks_affected: number;
}
