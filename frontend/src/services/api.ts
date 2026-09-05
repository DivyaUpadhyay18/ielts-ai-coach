import axios from 'axios';

// API base URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const API_V1_URL = `${API_URL.replace('/api', '')}/api/v1`;

// Token storage keys
const ACCESS_TOKEN_KEY = 'ielts_access_token';
const REFRESH_TOKEN_KEY = 'ielts_refresh_token';

// Access token cookie helpers.
//
// Next.js middleware (frontend/src/middleware.ts) runs server-side and can
// only see authentication state via cookies — localStorage is browser-only.
// Mirror the access token into a cookie here so middleware can route to
// /dashboard after a successful login instead of bouncing back to /login.
const ACCESS_TOKEN_MAX_AGE_FALLBACK = 15 * 60; // backend ACCESS_TOKEN_EXPIRE_MINUTES = 15

// Prefer the JWT's own `exp` claim (seconds) so the cookie doesn't outlive
// the token; fall back to the 15-minute backend default if it can't be read.
function getAccessTokenMaxAge(accessToken: string): number {
  try {
    const payloadPart = accessToken.split('.')[1];
    if (payloadPart) {
      const decoded = JSON.parse(
        atob(payloadPart.replace(/-/g, '+').replace(/_/g, '/'))
      );
      const exp = Number(decoded?.exp);
      if (Number.isFinite(exp) && exp > 0) {
        const remaining = Math.floor(exp - Date.now() / 1000);
        if (remaining > 0) return remaining;
      }
    }
  } catch {
    // malformed JWT - fall through to the default below
  }
  return ACCESS_TOKEN_MAX_AGE_FALLBACK;
}

function setAccessTokenCookie(accessToken: string): void {
  if (typeof document === 'undefined') return;
  const secure = location.protocol === 'https:' ? '; Secure' : '';
  document.cookie =
    `${ACCESS_TOKEN_KEY}=${accessToken}; path=/; max-age=${getAccessTokenMaxAge(accessToken)}; SameSite=Lax${secure}`;
}

function clearAccessTokenCookie(): void {
  if (typeof document === 'undefined') return;
  const secure = location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `${ACCESS_TOKEN_KEY}=; path=/; max-age=0; SameSite=Lax${secure}`;
}

// Token management
export const tokenManager = {
  getAccessToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },
  
  getRefreshToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },
  
  setTokens: (accessToken: string, refreshToken: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    setAccessTokenCookie(accessToken);
  },
  
  clearTokens: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    clearAccessTokenCookie();
  },
  
  isAuthenticated: (): boolean => {
    return !!tokenManager.getAccessToken();
  },
};

// Create axios instance for v1 API (auth)
const authApi = axios.create({
  baseURL: API_V1_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Create axios instance for legacy API
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token to all requests
const addAuthInterceptor = (instance: ReturnType<typeof axios.create>) => {
  instance.interceptors.request.use(
    (config: any) => {
      const token = tokenManager.getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error: any) => Promise.reject(error)
  );
};

// Response interceptor for token refresh
const addRefreshInterceptor = (instance: ReturnType<typeof axios.create>) => {
  instance.interceptors.response.use(
    (response: any) => response,
    async (error: any) => {
      const originalRequest = error.config;
      
      // If 401 and not already retrying, try to refresh token
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;
        
        try {
          const refreshToken = tokenManager.getRefreshToken();
          if (!refreshToken) {
            tokenManager.clearTokens();
            if (typeof window !== 'undefined') {
              window.location.href = '/login';
            }
            return Promise.reject(error);
          }
          
          const response = await axios.post(`${API_V1_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });
          
          const { access_token, refresh_token } = response.data;
          tokenManager.setTokens(access_token, refresh_token);
          
          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return instance(originalRequest);
        } catch (refreshError) {
          tokenManager.clearTokens();
          if (typeof window !== 'undefined') {
            window.location.href = '/login';
          }
          return Promise.reject(refreshError);
        }
      }
      
      return Promise.reject(error);
    }
  );
};

// Add interceptors to both instances
addAuthInterceptor(api);
addRefreshInterceptor(api);
addAuthInterceptor(authApi);
addRefreshInterceptor(authApi);

// Auth service
export const authService = {
  register: async (email: string, password: string, fullName: string) => {
    const response = await authApi.post('/auth/register', {
      email,
      password,
      full_name: fullName,
    });
    return response.data;
  },

  login: async (email: string, password: string) => {
    const response = await authApi.post('/auth/login', {
      email,
      password,
    });
    return response.data;
  },

  refreshToken: async (refreshToken: string) => {
    const response = await authApi.post('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return response.data;
  },

  logout: async () => {
    try {
      await authApi.post('/auth/logout');
    } finally {
      tokenManager.clearTokens();
    }
  },

  getMe: async () => {
    const response = await authApi.get('/auth/me');
    return response.data;
  },

  forgotPassword: async (email: string) => {
    const response = await authApi.post('/auth/forgot-password', { email });
    return response.data;
  },

  resetPassword: async (token: string, newPassword: string) => {
    const response = await authApi.post('/auth/reset-password', {
      token,
      new_password: newPassword,
    });
    return response.data;
  },

  changePassword: async (currentPassword: string, newPassword: string) => {
    const response = await authApi.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  },
};

// Onboarding service
export interface OnboardingData {
  full_name?: string;
  country?: string;
  timezone?: string;
  module: 'academic' | 'general';
  current_band: number;
  target_band: number;
  exam_date: string;
  daily_minutes_budget: number;
  preferred_study_time?: string;
  weakest_skill: string[];
  strongest_skill: string[];
  previous_ielts_attempt: boolean;
}

export interface RoadmapTask {
  id: string;
  title: string;
  skill: string;
  duration_minutes: number;
  status: string;
}

export interface RoadmapPhase {
  id: string;
  order_index: number;
  title: string;
  description: string;
  status: string;
  duration_days: number;
  start_date: string | null;
  end_date: string | null;
  tasks: RoadmapTask[];
}

export interface RoadmapResponse {
  id: string;
  version: number;
  title: string;
  target_band: number;
  start_band: number;
  total_weeks: number;
  estimated_achievement_date: string | null;
  confidence_score: number;
  phases: RoadmapPhase[];
}

export interface OnboardingStatus {
  is_onboarding_complete: boolean;
  onboarded_at: string | null;
  has_roadmap: boolean;
}

export const onboardingService = {
  submit: async (data: OnboardingData) => {
    const response = await authApi.post('/onboarding/submit', data);
    return response.data;
  },

  getStatus: async (): Promise<OnboardingStatus> => {
    const response = await authApi.get('/onboarding/status');
    return response.data;
  },

  generateRoadmap: async (): Promise<RoadmapResponse> => {
    const response = await authApi.post('/onboarding/roadmap/generate');
    return response.data;
  },

  getRoadmap: async (): Promise<RoadmapResponse> => {
    const response = await authApi.get('/onboarding/roadmap');
    return response.data;
  },
};

// ─────────────────────────────────────────────────────────────
// Study Plan service (mirrors /api/v1/study-plans/*)
// ─────────────────────────────────────────────────────────────
import type {
  StudyPlanGenerateRequest,
  DiagnosticStudyPlanRequest,
  StudyPlanGenerateResponse,
} from '@/types';

export const studyPlanService = {
  generate: async (data: StudyPlanGenerateRequest): Promise<StudyPlanGenerateResponse> => {
    const response = await authApi.post('/study-plans/generate', data);
    return response.data;
  },

  generateFromDiagnostic: async (
    data: DiagnosticStudyPlanRequest
  ): Promise<StudyPlanGenerateResponse> => {
    const response = await authApi.post('/study-plans/generate-from-diagnostic', data);
    return response.data;
  },

  getPlanDays: async (
    planId: string,
    params?: { fromDate?: string; toDate?: string }
  ): Promise<any> => {
    const response = await authApi.get(`/study-plans/${planId}/days`, { params });
    return response.data;
  },

  getActivePlan: async (): Promise<any> => {
    const response = await authApi.get('/study-plans/active');
    return response.data;
  },

  listPlans: async (): Promise<any[]> => {
    const response = await authApi.get('/study-plans');
    return response.data;
  },
};

// ─────────────────────────────────────────────────────────────
// Recommendation Engine service (mirrors /api/v1/recommendations/*)
// ─────────────────────────────────────────────────────────────
import type {
  RecommendationResponse,
  RecommendationItem,
} from '@/types';

export const recommendationService = {
  getRecommendations: async (params?: {
    skill?: string;
    sub_skill?: string;
    resource_type?: string;
    limit?: number;
    include_completed?: boolean;
    only_verified?: boolean;
  }): Promise<RecommendationResponse> => {
    const response = await authApi.get('/recommendations', { params });
    return response.data;
  },

  getHistory: async (params?: {
    limit?: number;
    offset?: number;
  }): Promise<any[]> => {
    const response = await authApi.get('/recommendations/history', { params });
    return response.data;
  },

  track: async (data: {
    resource_id: string;
    recommendation_log_id?: string;
    action: 'viewed' | 'clicked' | 'completed';
    session_id?: string;
  }): Promise<any> => {
    const response = await authApi.post('/recommendations/track', data);
    return response.data;
  },

  getStats: async (): Promise<any> => {
    const response = await authApi.get('/recommendations/stats');
    return response.data;
  },
};

// Dashboard service
import type { DashboardOverview } from '@/types';

export const dashboardService = {
  getOverview: async (): Promise<DashboardOverview> => {
    const response = await authApi.get('/dashboard/overview');
    return response.data;
  },
};

// Daily Missions service
import type {
  DailyMission,
  DailyMissionGenerateResponse,
  DailyMissionListResponse,
  MissionStatus,
} from '@/types';

export const dailyMissionService = {
  list: async (params?: {
    mission_date?: string;
    from?: string;
    to?: string;
  }): Promise<DailyMission[]> => {
    const response = await authApi.get('/daily-missions', { params });
    return response.data;
  },

  getToday: async (): Promise<DailyMissionListResponse> => {
    const response = await authApi.get('/daily-missions/today');
    return response.data;
  },

  get: async (missionId: string): Promise<DailyMission> => {
    const response = await authApi.get(`/daily-missions/${missionId}`);
    return response.data;
  },

  generate: async (params?: {
    mission_date?: string;
    from?: string;
    to?: string;
    days?: number;
  }): Promise<DailyMissionGenerateResponse> => {
    const response = await authApi.post('/daily-missions/generate', null, { params });
    return response.data;
  },

  update: async (
    missionId: string,
    data: { status?: MissionStatus; completion_percent?: number }
  ): Promise<DailyMission> => {
    const response = await authApi.patch(`/daily-missions/${missionId}`, data);
    return response.data;
  },

  complete: async (missionId: string): Promise<DailyMission> => {
    const response = await authApi.post(`/daily-missions/${missionId}/complete`);
    return response.data;
  },

  skip: async (missionId: string): Promise<DailyMission> => {
    const response = await authApi.post(`/daily-missions/${missionId}/skip`);
    return response.data;
  },
};

// Adaptive Scheduler service
import type {
  SchedulerRun,
  SchedulerMetrics,
  SchedulerAdjustment,
  SchedulerExplain,
  SchedulerAction,
  TimelineResponse,
  TimelineDay,
} from '@/types';

export interface SchedulerRunPayload {
  run: Record<string, unknown> | null;
  metrics: SchedulerMetrics;
  adjustments: SchedulerAdjustment[];
  summary?: string;
}

export type SchedulerTriggerType = 'midnight' | 'app_open' | 'manual';

export const schedulerService = {
  run: async (
    triggerType: SchedulerTriggerType = 'app_open',
    runDate?: string
  ): Promise<SchedulerRunPayload> => {
    const response = await authApi.post('/scheduler/run', null, {
      params: { trigger_type: triggerType, ...(runDate ? { run_date: runDate } : {}) },
    });
    return response.data;
  },

  getLatest: async (): Promise<SchedulerRunPayload> => {
    const response = await authApi.get('/scheduler/latest');
    return response.data;
  },

  listRuns: async (limit = 10): Promise<SchedulerRun[]> => {
    const response = await authApi.get('/scheduler/runs', { params: { limit } });
    return response.data;
  },

  getRun: async (runId: string): Promise<SchedulerRunPayload> => {
    const response = await authApi.get(`/scheduler/runs/${runId}`);
    return response.data;
  },

  explain: async (runDate?: string): Promise<SchedulerExplain> => {
    const response = await authApi.get('/scheduler/explain', {
      params: runDate ? { run_date: runDate } : {},
    });
    return response.data;
  },
};

// Scheduler change log component helpers
export const getSchedulerActionIcon = (action: SchedulerAction): string => {
  switch (action) {
    case 'carried_forward':
      return '→';
    case 'rescheduled':
      return '↕';
    case 'deprioritized':
      return '↓';
    case 'spread':
      return '⇢';
    case 'merged':
      return '⊕';
    case 'kept':
      return '•';
    case 'split':
      return '÷';
    default:
      return '•';
  }
};

export const getSchedulerActionColor = (action: SchedulerAction): string => {
  switch (action) {
    case 'carried_forward':
      return 'text-blue-600';
    case 'rescheduled':
      return 'text-amber-600';
    case 'deprioritized':
      return 'text-gray-600';
    case 'spread':
      return 'text-purple-600';
    case 'merged':
      return 'text-emerald-600';
    case 'kept':
      return 'text-slate-600';
    case 'split':
      return 'text-rose-600';
    default:
      return 'text-slate-600';
  }
};

// PLACEHOLDER: Extended types to avoid cross-import errors
type MissionSkill = 'reading' | 'listening' | 'writing' | 'speaking' | 'vocabulary' | 'grammar';

// Progress Tracking service
import type {
  ProgressOverviewResponse,
  ChartsResponse,
  HistoryResponse,
  StudySession,
  StudySessionInput,
} from '@/types';

export const progressTrackingService = {
  addSession: async (input: StudySessionInput): Promise<StudySession> => {
    const response = await authApi.post('/progress-tracking/log', input);
    return response.data;
  },

  getOverview: async (): Promise<ProgressOverviewResponse> => {
    const response = await authApi.get('/progress-tracking/overview');
    return response.data;
  },

  getCharts: async (): Promise<ChartsResponse> => {
    const response = await authApi.get('/progress-tracking/charts');
    return response.data;
  },

  getHistory: async (limit = 50): Promise<HistoryResponse> => {
    const response = await authApi.get('/progress-tracking/history', {
      params: { limit },
    });
    return response.data;
  },
};

// Streak System service
import type {
  StreakOverviewResponse,
  StreakEventItem,
  StreakFreeze,
} from '@/types';

export const streakService = {
  getOverview: async (): Promise<StreakOverviewResponse> => {
    const response = await authApi.get('/streaks/overview');
    return response.data;
  },

  listEvents: async (limit = 50): Promise<StreakEventItem[]> => {
    const response = await authApi.get('/streaks/events', { params: { limit } });
    return response.data;
  },

  listFreezes: async (): Promise<StreakFreeze[]> => {
    const response = await authApi.get('/streaks/freezes');
    return response.data;
  },

  grantFreeze: async (
    periodType: 'day' | 'week' | 'month' = 'day',
    source: 'placeholder' | 'purchase' | 'reward' | 'system' = 'placeholder'
  ): Promise<StreakFreeze> => {
    const response = await authApi.post('/streaks/freezes/grant', null, {
      params: { period_type: periodType, source },
    });
    return response.data;
  },

  useFreeze: async (freezeId: string): Promise<StreakFreeze> => {
    const response = await authApi.post('/streaks/freezes/use', { freeze_id: freezeId });
    return response.data;
  },

  recompute: async (day?: string): Promise<Record<string, unknown>> => {
    const response = await authApi.post('/streaks/recompute', null, {
      params: day ? { day } : undefined,
    });
    return response.data;
  },

  getMilestones: async (): Promise<Record<string, unknown>> => {
    const response = await authApi.get('/streaks/milestones');
    return response.data;
  },
};

// IELTS service (existing)
export const ieltsService = {
  checkHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },

  submitAssessment: async (data: {
    task_type: string;
    user_input: string;
    user_id: string;
  }) => {
    const response = await api.post('/assess', data);
    return response.data;
  },

  getUserResults: async (userId: string) => {
    const response = await api.get(`/results/${userId}`);
    return response.data;
  }
};

// Exam Countdown service
import type {
  ExamCountdown,
  ExamDateUpdateRequest,
  ExamDateUpdateResponse,
} from '@/types';

export const countdownService = {
  getCountdown: async (): Promise<ExamCountdown> => {
    const response = await authApi.get('/countdown');
    return response.data;
  },

  updateExamDate: async (
    data: ExamDateUpdateRequest
  ): Promise<ExamDateUpdateResponse> => {
    const response = await authApi.post('/countdown/exam-date', data);
    return response.data;
  },
};

// Prediction Engine service
import type {
  PredictionResponse,
  PredictionHistoryItem,
  PredictionHistoryResponse,
} from '@/types';

export const predictionService = {
  getPrediction: async (): Promise<PredictionResponse> => {
    const response = await authApi.get('/prediction');
    return response.data;
  },

  getHistory: async (limit = 20, offset = 0): Promise<PredictionHistoryResponse> => {
    const response = await authApi.get('/prediction/history', {
      params: { limit, offset },
    });
    return response.data;
  },
};

// Timeline service
export const timelineService = {
  getTimeline: async (): Promise<TimelineResponse> => {
    const response = await authApi.get('/tasks/timeline');
    return response.data;
  },
};

// Schedule History service
import type {
  ScheduleHistoryEntry,
  ScheduleHistoryListResponse,
  ScheduleComparisonResponse,
  ScheduleHistoryStats,
  ScheduleChangeType,
  UserAction,
} from '@/types';

export const scheduleHistoryService = {
  list: async (params?: {
    change_type?: ScheduleChangeType;
    user_action?: UserAction;
    study_plan_id?: string;
    from_date?: string;
    to_date?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScheduleHistoryListResponse> => {
    const response = await authApi.get('/schedule-history', { params });
    return response.data;
  },

  get: async (historyId: string): Promise<ScheduleHistoryEntry> => {
    const response = await authApi.get(`/schedule-history/${historyId}`);
    return response.data;
  },

  getLatest: async (): Promise<ScheduleHistoryEntry | null> => {
    const response = await authApi.get('/schedule-history/latest');
    return response.data;
  },

  compare: async (
    historyId1: string,
    historyId2: string
  ): Promise<ScheduleComparisonResponse> => {
    const response = await authApi.get(`/schedule-history/compare/${historyId1}/${historyId2}`);
    return response.data;
  },

  updateAction: async (
    historyId: string,
    action: UserAction,
    notes?: string
  ): Promise<ScheduleHistoryEntry> => {
    const response = await authApi.patch(`/schedule-history/${historyId}/action`, {
      user_action: action,
      user_action_notes: notes,
    });
    return response.data;
  },

  getStats: async (days: number = 30): Promise<ScheduleHistoryStats> => {
    const response = await authApi.get('/schedule-history/stats/summary', {
      params: { days },
    });
    return response.data;
  },
};

// Resource Management service
import type {
  ResourceItem,
  ResourceCreatePayload,
  ResourceUpdatePayload,
  ResourceStats,
  ResourceFilters,
  ResourceSortBy,
  SortOrder,
  BandEstimationInput,
  BandEstimationResponse,
  BandEstimationHistoryItem,
  BandEstimationHistoryResponse,
} from '@/types';
import type {
  ResourceSuggestion,
  ResourceSuggestionCreatePayload,
} from '@/types/admin';

// Learning Session service
import type {
  SessionStartResponse,
  SessionProgressUpdate,
  SessionNoteInput,
  SessionNote,
  SessionBookmarkInput,
  SessionBookmark,
  SessionCompleteResponse,
  SessionHistoryResponse,
  TodaySessionOverview,
} from '@/types';

export const resourcesService = {
  list: async (params?: {
    skill?: string;
    type?: string;
    difficulty?: string;
    minimum_band?: number;
    maximum_band?: number;
    is_free?: boolean;
    verified?: boolean;
    official?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<ResourceItem[]> => {
    const response = await authApi.get('/resource-management', { params });
    return response.data;
  },

  listAdvanced: async (filters?: ResourceFilters): Promise<ResourceItem[]> => {
    const response = await authApi.get('/resource-management', { params: filters as Record<string, unknown> });
    return response.data;
  },

  get: async (resourceId: string): Promise<ResourceItem> => {
    const response = await authApi.get(`/resource-management/${resourceId}`);
    return response.data;
  },

  create: async (data: ResourceCreatePayload): Promise<ResourceItem> => {
    const response = await authApi.post('/resource-management', data);
    return response.data;
  },

  update: async (resourceId: string, data: ResourceUpdatePayload): Promise<ResourceItem> => {
    const response = await authApi.patch(`/resource-management/${resourceId}`, data);
    return response.data;
  },

  delete: async (resourceId: string): Promise<void> => {
    await authApi.delete(`/resource-management/${resourceId}`);
  },

  search: async (params?: {
    skill?: string;
    type?: string;
    difficulty?: string;
    minimum_band?: number;
    maximum_band?: number;
    is_free?: boolean;
    verified?: boolean;
    official?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<ResourceItem[]> => {
    const response = await authApi.get('/resource-management/search', { params });
    return response.data;
  },

  getStats: async (): Promise<ResourceStats> => {
    const response = await authApi.get('/resource-management/stats');
    return response.data;
  },

  getBySkill: async (skill: string, limit?: number): Promise<ResourceItem[]> => {
    const response = await authApi.get(`/resource-management/by-skill/${skill}`, {
      params: { limit },
    });
    return response.data;
  },

  getByType: async (type: string, limit?: number): Promise<ResourceItem[]> => {
    const response = await authApi.get(`/resource-management/by-type/${type}`, {
      params: { limit },
    });
    return response.data;
  },

  getVerified: async (limit?: number): Promise<ResourceItem[]> => {
    const response = await authApi.get('/resource-management/verified', {
      params: { limit },
    });
    return response.data;
  },

  getOfficial: async (limit?: number): Promise<ResourceItem[]> => {
    const response = await authApi.get('/resource-management/official', {
      params: { limit },
    });
    return response.data;
  },

  getFree: async (limit?: number): Promise<ResourceItem[]> => {
    const response = await authApi.get('/resource-management/free', {
      params: { limit },
    });
    return response.data;
  },

  incrementPopularity: async (resourceId: string): Promise<ResourceItem> => {
    const response = await authApi.post(`/resource-management/${resourceId}/popularity`);
    return response.data;
  },

  updateRating: async (resourceId: string, rating: number): Promise<ResourceItem> => {
    const response = await authApi.post(`/resource-management/${resourceId}/rating`, null, {
      params: { rating },
    });
    return response.data;
  },

  getSubSkills: async (skill: string): Promise<string[]> => {
    const response = await authApi.get(`/resource-management/sub-skills/${skill}`);
    return response.data;
  },

  getSources: async (): Promise<string[]> => {
    const response = await authApi.get('/resource-management/sources');
    return response.data;
  },

  getBookmarked: async (limit?: number): Promise<ResourceItem[]> => {
    const response = await authApi.get('/resource-management/bookmarks', {
      params: { limit },
    });
    return response.data;
  },

  getCompleted: async (limit?: number): Promise<ResourceItem[]> => {
    const response = await authApi.get('/resource-management/completed', {
      params: { limit },
    });
    return response.data;
  },

  getRecentlyViewed: async (limit?: number): Promise<ResourceItem[]> => {
    const response = await authApi.get('/resource-management/recently-viewed', {
      params: { limit },
    });
    return response.data;
  },

  recordView: async (resourceId: string): Promise<void> => {
    await authApi.post(`/resource-management/${resourceId}/view`);
  },

  recordComplete: async (resourceId: string): Promise<void> => {
    await authApi.post(`/resource-management/${resourceId}/complete`);
  },

  checkBookmark: async (resourceId: string): Promise<boolean> => {
    const response = await authApi.get(`/resource-management/${resourceId}/bookmark-status`);
    return response.data.is_bookmarked;
  },

  toggleBookmark: async (resourceId: string, isBookmarked: boolean): Promise<void> => {
    if (isBookmarked) {
      await authApi.delete('/resource-bookmarks', { params: { resource_id: resourceId } });
    } else {
      await authApi.post('/resource-management/bookmark', { resource_id: resourceId });
    }
  },

// ─── Community Suggestions ─────────────────────────────────
  submitSuggestion: async (data: ResourceSuggestionCreatePayload): Promise<ResourceSuggestion> => {
    const response = await authApi.post('/resource-management/suggestions', data);
    return response.data;
  },

  getMySuggestions: async (params?: { limit?: number; offset?: number }): Promise<ResourceSuggestion[]> => {
    const response = await authApi.get('/resource-management/suggestions/mine', { params });
    return response.data;
  },

  getCommunitySuggestions: async (params?: {
    category?: string;
    skill?: string;
    limit?: number;
    offset?: number;
  }): Promise<ResourceSuggestion[]> => {
    const response = await authApi.get('/resource-management/suggestions/community', { params });
    return response.data;
  },

  voteSuggestion: async (suggestionId: string): Promise<{ suggestion_id: string; votes: number; voted: boolean }> => {
    const response = await authApi.post(`/resource-management/suggestions/${suggestionId}/vote`);
    return response.data;
  },

  unvoteSuggestion: async (suggestionId: string): Promise<{ suggestion_id: string; votes: number; voted: boolean }> => {
    const response = await authApi.delete(`/resource-management/suggestions/${suggestionId}/vote`);
    return response.data;
  },

  // Favorites (client-side persistence via localStorage)
  // In production, this would be backed by a resource_favorites table
  getFavoriteIds: (): string[] => {
    if (typeof window === 'undefined') return [];
    try {
      const stored = localStorage.getItem('ielts_resource_favorites');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  },

  isFavorited: (resourceId: string): boolean => {
    return resourcesService.getFavoriteIds().includes(resourceId);
  },

  toggleFavorite: (resourceId: string, isFavorited: boolean): void => {
    if (typeof window === 'undefined') return;
    try {
      const favorites = resourcesService.getFavoriteIds();
      if (isFavorited) {
        const updated = favorites.filter((id) => id !== resourceId);
        localStorage.setItem('ielts_resource_favorites', JSON.stringify(updated));
      } else {
        if (!favorites.includes(resourceId)) {
          favorites.push(resourceId);
          localStorage.setItem('ielts_resource_favorites', JSON.stringify(favorites));
        }
      }
    } catch {
      // Silently fail - localStorage might be unavailable
    }
  },
};

export const learningSessionsService = {
  startSession: async (params?: {
    mission_id?: string;
    skill?: string;
  }): Promise<SessionStartResponse> => {
    const response = await authApi.post('/learning-sessions/start', {}, { params });
    return response.data;
  },

  updateProgress: async (
    missionId: string,
    data: SessionProgressUpdate
  ): Promise<any> => {
    const response = await authApi.post(`/learning-sessions/${missionId}/progress`, data);
    return response.data;
  },

  addNote: async (
    missionId: string,
    data: SessionNoteInput
  ): Promise<SessionNote> => {
    const response = await authApi.post(`/learning-sessions/${missionId}/notes`, data);
    return response.data;
  },

  addBookmark: async (
    missionId: string,
    data: SessionBookmarkInput
  ): Promise<SessionBookmark> => {
    const response = await authApi.post(`/learning-sessions/${missionId}/bookmarks`, data);
    return response.data;
  },

  completeSession: async (
    missionId: string,
    data?: {
      notes?: string[];
      progress?: number;
      actual_duration_minutes?: number;
    }
  ): Promise<SessionCompleteResponse> => {
    const response = await authApi.post(`/learning-sessions/${missionId}/complete`, data || {});
    return response.data;
  },

  getTodayOverview: async (): Promise<TodaySessionOverview> => {
    const response = await authApi.get('/learning-sessions/today');
    return response.data;
  },

  getHistory: async (params?: {
    limit?: number;
    offset?: number;
  }): Promise<SessionHistoryResponse> => {
    const response = await authApi.get('/learning-sessions/history', { params });
    return response.data;
  },
};

// Band Estimation service
export const bandEstimationService = {
  estimate: async (data: BandEstimationInput): Promise<BandEstimationResponse> => {
    const response = await authApi.post('/band-estimation', data);
    return response.data;
  },

  getLatest: async (): Promise<BandEstimationResponse> => {
    const response = await authApi.get('/band-estimation/latest');
    return response.data;
  },

  getHistory: async (params?: {
    limit?: number;
    offset?: number;
  }): Promise<BandEstimationHistoryResponse> => {
    const response = await authApi.get('/band-estimation/history', { params });
    return response.data;
  },
};

// Analytics service
import type {
  AnalyticsDashboardResponse,
  AnalyticsEvent,
  AnalyticsEventCreate,
  AnalyticsSummary,
  AnalyticsTrendPoint,
  SkillBreakdown,
  ResourcePerformanceItem,
  ResourceAnalytics,
  UserAnalytics,
  ResourceRatingCreate,
} from '@/types/analytics';

export const analyticsService = {
  // Event tracking
  trackEvent: async (data: AnalyticsEventCreate): Promise<AnalyticsEvent> => {
    const response = await authApi.post('/analytics/events', data);
    return response.data;
  },

  trackEventsBatch: async (events: AnalyticsEventCreate[]): Promise<AnalyticsEvent[]> => {
    const response = await authApi.post('/analytics/events/batch', { events });
    return response.data;
  },

  // Resource interactions
  recordView: async (resourceId: string): Promise<void> => {
    await authApi.post(`/analytics/resources/${resourceId}/view`);
  },

  recordComplete: async (resourceId: string): Promise<void> => {
    await authApi.post(`/analytics/resources/${resourceId}/complete`);
  },

  recordBookmark: async (resourceId: string): Promise<void> => {
    await authApi.post(`/analytics/resources/${resourceId}/bookmark`);
  },

  removeBookmark: async (resourceId: string): Promise<void> => {
    await authApi.delete(`/analytics/resources/${resourceId}/bookmark`);
  },

  toggleLike: async (resourceId: string): Promise<{ liked: boolean; resource_id: string }> => {
    const response = await authApi.post(`/analytics/resources/${resourceId}/like`);
    return response.data;
  },

  rateResource: async (resourceId: string, rating: number): Promise<any> => {
    const response = await authApi.post(`/analytics/resources/${resourceId}/rate`, {
      resource_id: resourceId,
      rating,
    });
    return response.data;
  },

  recordStudySession: async (params: {
    minutes: number;
    skill?: string;
    source_type?: string;
    source_id?: string;
  }): Promise<void> => {
    await authApi.post('/analytics/study-sessions', null, { params });
  },

  // Dashboard reads
  getDashboard: async (days = 30): Promise<AnalyticsDashboardResponse> => {
    const response = await authApi.get('/analytics/dashboard', { params: { days } });
    return response.data;
  },

  getSummary: async (): Promise<AnalyticsSummary> => {
    const response = await authApi.get('/analytics/summary');
    return response.data;
  },

  getTrends: async (days = 30): Promise<AnalyticsTrendPoint[]> => {
    const response = await authApi.get('/analytics/trends', { params: { days } });
    return response.data;
  },

  getSkills: async (): Promise<SkillBreakdown[]> => {
    const response = await authApi.get('/analytics/skills');
    return response.data;
  },

  getTopResources: async (limit = 10): Promise<ResourcePerformanceItem[]> => {
    const response = await authApi.get('/analytics/resources/top', { params: { limit } });
    return response.data;
  },

  getResourceAnalytics: async (resourceId: string): Promise<ResourceAnalytics> => {
    const response = await authApi.get(`/analytics/resources/${resourceId}`);
    return response.data;
  },

  getEvents: async (params?: {
    limit?: number;
    event?: string;
    entity_type?: string;
  }): Promise<AnalyticsEvent[]> => {
    const response = await authApi.get('/analytics/events', { params });
    return response.data;
  },

  getMyAnalytics: async (): Promise<UserAnalytics> => {
    const response = await authApi.get('/analytics/me');
    return response.data;
  },
};

// Resource Notes service
import type {
  ResourceNote,
  ResourceNoteCreate,
  ResourceNoteUpdate,
  ResourceNoteListResponse,
  ResourceHighlight,
  ResourceHighlightCreate,
  ResourceHighlightListResponse,
  RevisionReminder,
  RevisionReminderCreate,
  RevisionReminderUpdate,
  RevisionReminderListResponse,
  ResourceNoteStats,
} from '@/types/resource-notes';

export const resourceNotesService = {
  // Notes
  createNote: async (data: ResourceNoteCreate): Promise<ResourceNote> => {
    const response = await authApi.post('/resource-notes/notes', data);
    return response.data;
  },

  listNotes: async (params?: { resource_id?: string; search?: string }): Promise<ResourceNoteListResponse> => {
    const response = await authApi.get('/resource-notes/notes', { params });
    return response.data;
  },

  getNote: async (noteId: string): Promise<ResourceNote> => {
    const response = await authApi.get(`/resource-notes/notes/${noteId}`);
    return response.data;
  },

  updateNote: async (noteId: string, data: ResourceNoteUpdate): Promise<ResourceNote> => {
    const response = await authApi.patch(`/resource-notes/notes/${noteId}`, data);
    return response.data;
  },

  deleteNote: async (noteId: string): Promise<void> => {
    await authApi.delete(`/resource-notes/notes/${noteId}`);
  },

  // Highlights
  createHighlight: async (data: ResourceHighlightCreate): Promise<ResourceHighlight> => {
    const response = await authApi.post('/resource-notes/highlights', data);
    return response.data;
  },

  listHighlights: async (params?: { resource_id?: string }): Promise<ResourceHighlightListResponse> => {
    const response = await authApi.get('/resource-notes/highlights', { params });
    return response.data;
  },

  deleteHighlight: async (highlightId: string): Promise<void> => {
    await authApi.delete(`/resource-notes/highlights/${highlightId}`);
  },

  // Revision Reminders
  createReminder: async (data: RevisionReminderCreate): Promise<RevisionReminder> => {
    const response = await authApi.post('/resource-notes/reminders', data);
    return response.data;
  },

  listReminders: async (params?: { upcoming_only?: boolean }): Promise<RevisionReminderListResponse> => {
    const response = await authApi.get('/resource-notes/reminders', { params });
    return response.data;
  },

  updateReminder: async (reminderId: string, data: RevisionReminderUpdate): Promise<RevisionReminder> => {
    const response = await authApi.patch(`/resource-notes/reminders/${reminderId}`, data);
    return response.data;
  },

  deleteReminder: async (reminderId: string): Promise<void> => {
    await authApi.delete(`/resource-notes/reminders/${reminderId}`);
  },

  // Stats
  getStats: async (): Promise<ResourceNoteStats> => {
    const response = await authApi.get('/resource-notes/stats');
    return response.data;
  },
};

// Resource Quality service
import type {
  ResourceFeedback,
  ResourceFeedbackCreate,
  ResourceFeedbackListResponse,
  ModerationAction,
  ModerationLog,
  ModerationQueue,
  ResourceQualityScores,
  ResourceQualityLeaderboard,
  QualityScoreBreakdown,
  ResourceQualityStats,
  RecomputeAllResult,
} from '@/types/resource-quality';

export const resourceQualityService = {
  // ─── User Feedback ────────────────────────────────────────────
  submitFeedback: async (data: ResourceFeedbackCreate): Promise<ResourceFeedback> => {
    const response = await authApi.post('/resource-quality/feedback', data);
    return response.data;
  },

  listFeedback: async (params?: {
    resource_id?: string;
    feedback_type?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<ResourceFeedbackListResponse> => {
    const response = await authApi.get('/resource-quality/feedback', { params });
    return response.data;
  },

  getFeedback: async (feedbackId: string): Promise<ResourceFeedback> => {
    const response = await authApi.get(`/resource-quality/feedback/${feedbackId}`);
    return response.data;
  },

  deleteFeedback: async (feedbackId: string): Promise<void> => {
    await authApi.delete(`/resource-quality/feedback/${feedbackId}`);
  },

  // ─── Quality Scores ───────────────────────────────────────────
  getScores: async (resourceId: string): Promise<ResourceQualityScores> => {
    const response = await authApi.get(`/resource-quality/resources/${resourceId}/scores`);
    return response.data;
  },

  getBreakdown: async (resourceId: string): Promise<QualityScoreBreakdown> => {
    const response = await authApi.get(`/resource-quality/resources/${resourceId}/breakdown`);
    return response.data;
  },

  recomputeScores: async (resourceId: string): Promise<ResourceQualityScores> => {
    const response = await authApi.post(`/resource-quality/resources/${resourceId}/recompute`);
    return response.data;
  },

  getLeaderboard: async (params?: {
    sort_by?: string;
    limit?: number;
    skill?: string;
  }): Promise<ResourceQualityLeaderboard> => {
    const response = await authApi.get('/resource-quality/leaderboard', { params });
    return response.data;
  },

  recomputeAll: async (limit?: number): Promise<RecomputeAllResult> => {
    const response = await authApi.post('/resource-quality/recompute-all', null, {
      params: { limit },
    });
    return response.data;
  },

  // ─── Admin Moderation ────────────────────────────────────────
  getModerationQueue: async (params?: {
    status?: string;
    feedback_type?: string;
    priority?: string;
    limit?: number;
    offset?: number;
  }): Promise<ModerationQueue> => {
    const response = await authApi.get('/resource-quality/admin/queue', { params });
    return response.data;
  },

  getModerationLog: async (feedbackId: string): Promise<ModerationLog[]> => {
    const response = await authApi.get(`/resource-quality/admin/feedback/${feedbackId}/log`);
    return response.data;
  },

  moderateFeedback: async (
    feedbackId: string,
    data: ModerationAction
  ): Promise<ResourceFeedback> => {
    const response = await authApi.post(
      `/resource-quality/admin/feedback/${feedbackId}/moderate`,
      data
    );
    return response.data;
  },

  // ─── Stats ────────────────────────────────────────────────────
  getStats: async (): Promise<ResourceQualityStats> => {
    const response = await authApi.get('/resource-quality/stats');
    return response.data;
  },
};

// Admin service
import type {
  AdminUser,
  AdminStats,
  AuditLogEntry,
  AdminAnalytics,
  AdminResourceAnalytics,
BulkUploadResult,
  BulkEditResult,
  BulkDeleteResult,
  VerificationLogEntry,
  UserRole,
  ResourceSuggestionUpdatePayload,
} from '@/types/admin';
export const adminService = {
  // ─── User Management ────────────────────────────────────────
  listUsers: async (params?: {
    role?: UserRole;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<AdminUser[]> => {
    const response = await authApi.get('/admin/users', { params });
    return response.data;
  },

  updateUserRole: async (userId: string, role: UserRole): Promise<{ user_id: string; role: UserRole }> => {
    const response = await authApi.patch(`/admin/users/${userId}/role`, null, { params: { role } });
    return response.data;
  },

  updateUserStatus: async (userId: string, isActive: boolean): Promise<{ user_id: string; is_active: boolean }> => {
    const response = await authApi.patch(`/admin/users/${userId}/status`, null, { params: { is_active: isActive } });
    return response.data;
  },

  // ─── Audit Log ──────────────────────────────────────────────
  getAuditLog: async (params?: {
    admin_id?: string;
    entity_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditLogEntry[]> => {
    const response = await authApi.get('/admin/audit-log', { params });
    return response.data;
  },

  // ─── Stats ──────────────────────────────────────────────────
  getStats: async (): Promise<AdminStats> => {
    const response = await authApi.get('/admin/stats');
    return response.data;
  },

  // ─── Resource Management Admin ──────────────────────────────
  getAdminAnalytics: async (): Promise<AdminAnalytics> => {
    const response = await authApi.get('/resource-management/admin/analytics');
    return response.data;
  },

  getResourceAnalytics: async (resourceId: string): Promise<AdminResourceAnalytics> => {
    const response = await authApi.get(`/resource-management/${resourceId}/analytics`);
    return response.data;
  },

  // ─── Community Suggestions ──────────────────────────────────
  getSuggestions: async (params?: {
    status?: 'pending' | 'approved' | 'rejected';
    limit?: number;
    offset?: number;
  }): Promise<ResourceSuggestion[]> => {
    const response = await authApi.get('/resource-management/suggestions', { params });
    return response.data;
  },

  approveSuggestion: async (suggestionId: string, notes?: string): Promise<ResourceItem> => {
    const response = await authApi.post(`/resource-management/suggestions/${suggestionId}/approve`, null, {
      params: notes ? { notes } : {},
    });
    return response.data;
  },

rejectSuggestion: async (suggestionId: string, notes?: string): Promise<ResourceSuggestion> => {
    const response = await authApi.post(`/resource-management/suggestions/${suggestionId}/reject`, null, {
      params: notes ? { notes } : {},
    });
    return response.data;
  },

  editSuggestion: async (
    suggestionId: string,
    data: ResourceSuggestionUpdatePayload
  ): Promise<ResourceSuggestion> => {
    const response = await authApi.patch(`/resource-management/suggestions/${suggestionId}`, data);
    return response.data;
  },

  // ─── Verification ───────────────────────────────────────────
  verifyResource: async (resourceId: string, notes?: string): Promise<ResourceItem> => {
    const response = await authApi.post(`/resource-management/${resourceId}/verify`, null, {
      params: notes ? { notes } : {},
    });
    return response.data;
  },

  unverifyResource: async (resourceId: string, notes?: string): Promise<ResourceItem> => {
    const response = await authApi.post(`/resource-management/${resourceId}/unverify`, null, {
      params: notes ? { notes } : {},
    });
    return response.data;
  },

  getVerificationLog: async (resourceId: string): Promise<VerificationLogEntry[]> => {
    const response = await authApi.get(`/resource-management/${resourceId}/verification-log`);
    return response.data;
  },

  // ─── Bulk Operations ────────────────────────────────────────
  bulkUpload: async (resources: ResourceCreatePayload[]): Promise<BulkUploadResult> => {
    const response = await authApi.post('/resource-management/bulk', resources);
    return response.data;
  },

  bulkEdit: async (updates: Array<ResourceUpdatePayload & { id: string }>): Promise<BulkEditResult> => {
    const response = await authApi.patch('/resource-management/bulk', updates);
    return response.data;
  },

  bulkDelete: async (resourceIds: string[]): Promise<BulkDeleteResult> => {
    const response = await authApi.delete('/resource-management/bulk', { data: resourceIds });
    return response.data;
  },
};

// AI Mentor service
import type {
  CoachRequest,
  CoachResponse,
  MentorContextResponse,
  MentorConversationListResponse,
  MentorConversationResponse,
} from '@/types';

export const mentorService = {
  getContext: async (): Promise<MentorContextResponse> => {
    const response = await authApi.get('/mentor/context');
    return response.data;
  },

  coach: async (data: CoachRequest): Promise<CoachResponse> => {
    const response = await authApi.post('/mentor/coach', data);
    return response.data;
  },

  ask: async (question: string): Promise<CoachResponse> => {
    const response = await authApi.post('/mentor/ask', { question });
    return response.data;
  },

  listConversations: async (params?: {
    mode?: string;
    limit?: number;
    offset?: number;
  }): Promise<MentorConversationListResponse> => {
    const response = await authApi.get('/mentor/conversations', { params });
    return response.data;
  },

  getConversation: async (conversationId: string): Promise<MentorConversationResponse> => {
    const response = await authApi.get(`/mentor/conversations/${conversationId}`);
    return response.data;
  },
};

// ─────────────────────────────────────────────────────────────
// Weekly AI Reports service (mirrors /api/v1/weekly-reports/*)
// ─────────────────────────────────────────────────────────────
import type {
  WeeklyReportResponse,
  WeeklyReportHistoryResponse,
} from '@/types';

export const weeklyReportService = {
  getLatest: async (forceRegenerate = false): Promise<WeeklyReportResponse> => {
    const response = await authApi.get('/weekly-reports', {
      params: { force_regenerate: forceRegenerate },
    });
    return response.data;
  },

  getHistory: async (limit = 20, offset = 0): Promise<WeeklyReportHistoryResponse> => {
    const response = await authApi.get('/weekly-reports/history', {
      params: { limit, offset },
    });
    return response.data;
  },

  getByWeek: async (weekStart: string, forceRegenerate = false): Promise<WeeklyReportResponse> => {
    const response = await authApi.get(`/weekly-reports/${weekStart}`, {
      params: { force_regenerate: forceRegenerate },
    });
    return response.data;
  },
};

// ─────────────────────────────────────────────────────────────
// AI Recommendations service (mirrors /api/v1/ai-recommendations/*)
// ─────────────────────────────────────────────────────────────
import type { AiRecommendationsResponse } from '@/types';

export const aiRecommendationsService = {
  getRecommendations: async (forceRegenerate = false): Promise<AiRecommendationsResponse> => {
    const response = await authApi.get('/ai-recommendations', {
      params: { force_regenerate: forceRegenerate },
    });
    return response.data;
  },

  getHistory: async (limit = 20, offset = 0): Promise<WeeklyReportHistoryResponse> => {
    const response = await authApi.get('/ai-recommendations/history', {
      params: { limit, offset },
    });
    return response.data;
  },

  getByWeek: async (weekStart: string, forceRegenerate = false): Promise<AiRecommendationsResponse> => {
    const response = await authApi.get(`/ai-recommendations/${weekStart}`, {
      params: { force_regenerate: forceRegenerate },
    });
    return response.data;
  },
};

// ─────────────────────────────────────────────────────────────
// AI Mentor Memory service (mirrors /api/v1/mentor-memory/*)
// ─────────────────────────────────────────────────────────────
import type {
  MentorMemoryProfile,
  MentorMemoryEntry,
  MemoryTypeSchema,
  ExtractionResult,
} from '@/types';

export const mentorMemoryService = {
  getProfile: async (): Promise<MentorMemoryProfile> => {
    const response = await authApi.get('/mentor-memory');
    return response.data;
  },

  extractMemories: async (force = false): Promise<ExtractionResult> => {
    const response = await authApi.post('/mentor-memory/extract', {}, {
      params: { force },
    });
    return response.data;
  },

  getMemoryTypes: async (): Promise<MemoryTypeSchema[]> => {
    const response = await authApi.get('/mentor-memory/types');
    return response.data;
  },

  listMemories: async (params?: {
    memory_type?: string;
    category?: string;
    limit?: number;
  }): Promise<MentorMemoryEntry[]> => {
    const response = await authApi.get('/mentor-memory/list', { params });
    return response.data;
  },

  addMemory: async (data: {
    memory_type: string;
    content: string;
    category?: string;
    subcategory?: string;
    structured_data?: Record<string, any>;
    confidence?: number;
  }): Promise<MentorMemoryEntry> => {
    const response = await authApi.post('/mentor-memory', data);
    return response.data;
  },

  updateMemory: async (
    memoryId: string,
    data: Partial<{
      content: string;
      category: string;
      subcategory: string;
      structured_data: Record<string, any>;
      confidence: number;
      is_active: boolean;
      expires_at: string;
    }>
  ): Promise<MentorMemoryEntry> => {
    const response = await authApi.patch(`/mentor-memory/${memoryId}`, data);
    return response.data;
  },

  deleteMemory: async (memoryId: string): Promise<void> => {
    await authApi.delete(`/mentor-memory/${memoryId}`);
  },
};

// ─────────────────────────────────────────────────────────────
// Writing Workspace service (mirrors /api/v1/writing-workspace/*)
// ─────────────────────────────────────────────────────────────
import type {
  WritingWorkspacePrompt,
  WritingWorkspacePromptsResponse,
  WritingWorkspacePromptResponse,
  WritingWorkspaceSubmission,
  WritingWorkspaceSubmissionStart,
  WritingWorkspaceSubmissionSave,
  WritingWorkspaceSubmissionSubmit,
  WritingWorkspaceSubmissionListResponse,
  WritingImprovementPlan,
  WritingImprovementPlanListResponse,
  BandExample,
  BandExampleListResponse,
  SpeakingErrorAnalysis,
  SpeakingErrorAnalysisListResponse,
} from '@/types/writing-workspace';
import type {
  SpeakingImprovementPlan,
  SpeakingImprovementPlanListResponse,
} from '@/types/speaking-test';
import type {
  SpeakingPracticeSession,
  SpeakingPracticeSessionListResponse,
  SpeakingCoachConversation,
  SpeakingCoachChatResult,
  SpeakingAnalyticsDashboardResponse,
} from '@/types/speaking-test';

export const writingWorkspaceService = {
  getPrompts: async (taskType?: string): Promise<WritingWorkspacePromptsResponse> => {
    const response = await authApi.get('/writing-workspace/prompts', {
      params: taskType ? { task_type: taskType } : undefined,
    });
    return response.data;
  },

  getPrompt: async (promptId: string): Promise<WritingWorkspacePromptResponse> => {
    const response = await authApi.get(`/writing-workspace/prompts/${promptId}`);
    return response.data;
  },

  startSubmission: async (data: WritingWorkspaceSubmissionStart): Promise<WritingWorkspaceSubmission> => {
    const response = await authApi.post('/writing-workspace/start', data);
    return response.data;
  },

  autoSave: async (
    submissionId: string,
    data: WritingWorkspaceSubmissionSave
  ): Promise<WritingWorkspaceSubmission> => {
    const response = await authApi.post(`/writing-workspace/${submissionId}/save`, data);
    return response.data;
  },

  submit: async (
    submissionId: string,
    data?: WritingWorkspaceSubmissionSubmit
  ): Promise<WritingWorkspaceSubmission> => {
    const response = await authApi.post(`/writing-workspace/${submissionId}/submit`, data || {});
    return response.data;
  },

  getSubmission: async (submissionId: string): Promise<WritingWorkspaceSubmission> => {
    const response = await authApi.get(`/writing-workspace/${submissionId}`);
    return response.data;
  },

   listSubmissions: async (limit = 50): Promise<WritingWorkspaceSubmissionListResponse> => {
     const response = await authApi.get('/writing-workspace', { params: { limit } });
     return response.data;
   },
};

// Writing Evaluation service (mirrors /api/v1/writing-evaluations/*)
// ─────────────────────────────────────────────────────────────
import type {
  WritingEvaluation,
  WritingEvaluationListResponse,
  CriterionEvaluation,
} from '@/types/writing-workspace';

export const writingEvaluationService = {
  evaluateSubmission: async (
    submissionId: string,
    taskType: 'task_1' | 'task_2' = 'task_2'
  ): Promise<WritingEvaluation> => {
    const response = await authApi.post(
      `/writing-evaluations/${submissionId}?task_type=${taskType}`
    );
    return response.data;
  },

  getEvaluation: async (submissionId: string): Promise<WritingEvaluation> => {
    const response = await authApi.get(`/writing-evaluations/${submissionId}`);
    return response.data;
  },

  listEvaluations: async (limit = 20): Promise<WritingEvaluationListResponse> => {
    const response = await authApi.get('/writing-evaluations', { params: { limit } });
    return response.data;
  },
};

// Writing Reattempt service (mirrors /api/v1/writing-reattempts/*)
// ─────────────────────────────────────────────────────────────
import type {
  WritingAttemptListResponse,
  WritingReattemptStartResponse,
  WritingReattemptEvaluateResponse,
  WritingComparison,
} from '@/types/writing-workspace';

export const writingReattemptService = {
  startReattempt: async (
    submissionId: string,
  ): Promise<WritingReattemptStartResponse> => {
    const response = await authApi.post(
      `/writing-reattempts/${submissionId}/start`
    );
    return response.data;
  },

  evaluateReattempt: async (
    submissionId: string,
  ): Promise<WritingReattemptEvaluateResponse> => {
    const response = await authApi.post(
      `/writing-reattempts/${submissionId}/evaluate`
    );
    return response.data;
  },

  compareAttempts: async (
    submissionId: string,
  ): Promise<WritingComparison> => {
    const response = await authApi.get(
      `/writing-reattempts/${submissionId}/compare`
    );
    return response.data;
  },

  listAttempts: async (limit = 20): Promise<WritingAttemptListResponse> => {
    const response = await authApi.get('/writing-reattempts', {
      params: { limit },
    });
    return response.data;
  },
};

// Writing Coach service (mirrors /api/v1/writing-coach/*)
// ─────────────────────────────────────────────────────────────
import type {
  WritingCoachAnswer,
  WritingCoachConversation,
  WritingCoachConversationListResponse,
} from '@/types/writing-workspace';

export const writingCoachService = {
  ask: async (
    submissionId: string,
    question: string,
  ): Promise<WritingCoachAnswer> => {
    const response = await authApi.post(
      `/writing-coach/${submissionId}/ask?question=${encodeURIComponent(question)}`
    );
    return response.data;
  },

  askQuick: async (
    submissionId: string,
    question: string,
  ): Promise<Omit<WritingCoachAnswer, 'conversation_id'>> => {
    const response = await authApi.post(
      `/writing-coach/${submissionId}/ask-quick?question=${encodeURIComponent(question)}`
    );
    return response.data;
  },

  getConversation: async (
    conversationId: string,
  ): Promise<WritingCoachConversation> => {
    const response = await authApi.get(`/writing-coach/conversations/${conversationId}`);
    return response.data;
  },

  listConversations: async (
    limit = 50,
    offset = 0,
  ): Promise<WritingCoachConversationListResponse> => {
    const response = await authApi.get('/writing-coach/conversations', {
      params: { limit, offset },
    });
    return response.data;
  },
};

// Writing Improvement Plans service (mirrors /api/v1/writing-improvement-plans/*)
// ─────────────────────────────────────────────────────────────
export const writingImprovementPlanService = {
  generatePlan: async (
    submissionId: string,
    targetBand?: number,
  ): Promise<WritingImprovementPlan> => {
    const params = targetBand !== undefined ? { target_band: targetBand } : undefined;
    const response = await authApi.post(`/writing-improvement-plans/${submissionId}`, null, { params });
    return response.data;
  },

  getPlan: async (evaluationId: string): Promise<WritingImprovementPlan> => {
    const response = await authApi.get(`/writing-improvement-plans/${evaluationId}`);
    return response.data;
  },

  listPlans: async (limit = 20): Promise<WritingImprovementPlanListResponse> => {
    const response = await authApi.get('/writing-improvement-plans', { params: { limit } });
    return response.data;
  },
};

// Writing Band Examples service (mirrors /api/v1/writing-band-examples/*)
// ─────────────────────────────────────────────────────────────
export const writingBandExamplesService = {
  generateExamples: async (
    submissionId: string,
    targetBand: number = 7.5,
    generateSample: boolean = false,
  ): Promise<BandExample> => {
    const response = await authApi.post(`/writing-band-examples/${submissionId}`, null, {
      params: { target_band: targetBand, generate_sample: generateSample },
    });
    return response.data;
  },

  getExamples: async (evaluationId: string): Promise<BandExample> => {
    const response = await authApi.get(`/writing-band-examples/${evaluationId}`);
    return response.data;
  },

  listExamples: async (limit = 20): Promise<BandExampleListResponse> => {
    const response = await authApi.get('/writing-band-examples', { params: { limit } });
    return response.data;
  },
};

// ─────────────────────────────────────────────────────────────
// Speaking Test Workspace service (mirrors /api/v1/speaking-test/*)
// ─────────────────────────────────────────────────────────────
import type {
  SpeakingTestPrompt,
  SpeakingTestPromptsResponse,
  SpeakingTestSession,
  SpeakingTestProgress,
  SpeakingTestResponse,
  SpeakingTestResponseSaveRequest,
  ResponseStartRequest,
  AudioUploadResponse,
} from '@/types/speaking-test';

export const speakingTestService = {
  /** Fetch speaking prompts, optionally filtered by part. */
  getPrompts: async (part?: string): Promise<SpeakingTestPromptsResponse> => {
    const response = await authApi.get('/speaking-test/prompts', {
      params: part ? { part } : undefined,
    });
    return response.data;
  },

  /** Get a single prompt by ID. */
  getPrompt: async (promptId: string): Promise<SpeakingTestPrompt> => {
    const response = await authApi.get(`/speaking-test/prompts/${promptId}`);
    return response.data;
  },

  /** Start a new test session or resume the existing in-progress one. */
  startTest: async (): Promise<SpeakingTestSession> => {
    const response = await authApi.post('/speaking-test/start');
    return response.data;
  },

  /** Get the current in-progress session with responses (resume). */
  getCurrentSession: async (): Promise<SpeakingTestSession | null> => {
    try {
      const response = await authApi.get('/speaking-test/session');
      return response.data;
    } catch {
      return null;
    }
  },

  /** List all test sessions. */
  listSessions: async (limit = 20): Promise<{ results: SpeakingTestSession[]; total: number }> => {
    const response = await authApi.get('/speaking-test/sessions', { params: { limit } });
    return response.data;
  },

  /** Get a specific session with all responses. */
  getSession: async (sessionId: string): Promise<SpeakingTestSession> => {
    const response = await authApi.get(`/speaking-test/sessions/${sessionId}`);
    return response.data;
  },

  /** Start a response for a specific prompt within a session. */
  startResponse: async (data: ResponseStartRequest): Promise<SpeakingTestResponse> => {
    const response = await authApi.post('/speaking-test/responses', data);
    return response.data;
  },

  /** List all responses for a session. */
  listResponses: async (sessionId: string): Promise<{ results: SpeakingTestResponse[]; total: number }> => {
    const response = await authApi.get(`/speaking-test/sessions/${sessionId}/responses`);
    return response.data;
  },

  /** Save recording metadata (auto-save). */
  saveResponse: async (
    responseId: string,
    sessionId: string,
    data: SpeakingTestResponseSaveRequest
  ): Promise<SpeakingTestResponse> => {
    const response = await authApi.post(
      `/speaking-test/responses/${responseId}/save?session_id=${sessionId}`,
      data
    );
    return response.data;
  },

  /** Complete a response (mark as done). */
  completeResponse: async (
    responseId: string,
    sessionId: string,
    data?: SpeakingTestResponseSaveRequest
  ): Promise<SpeakingTestResponse> => {
    const response = await authApi.post(
      `/speaking-test/responses/${responseId}/complete?session_id=${sessionId}`,
      data || {}
    );
    return response.data;
  },

  /** Delete a response so it can be re-recorded. */
  deleteResponse: async (responseId: string, sessionId: string): Promise<void> => {
    await authApi.delete(`/speaking-test/responses/${responseId}?session_id=${sessionId}`);
  },

  /** Get a single response. */
  getResponse: async (responseId: string, sessionId: string): Promise<SpeakingTestResponse> => {
    const response = await authApi.get(
      `/speaking-test/responses/${responseId}?session_id=${sessionId}`
    );
    return response.data;
  },

  /** Advance to the next part. */
  advancePart: async (sessionId: string): Promise<SpeakingTestSession> => {
    const response = await authApi.post(`/speaking-test/sessions/${sessionId}/advance`);
    return response.data;
  },

  /** Complete the test (logs progress). */
  completeTest: async (sessionId: string): Promise<SpeakingTestSession> => {
    const response = await authApi.post(`/speaking-test/sessions/${sessionId}/complete`);
    return response.data;
  },

  /** Abandon the test (save for later). */
  abandonTest: async (sessionId: string): Promise<SpeakingTestSession> => {
    const response = await authApi.post(`/speaking-test/sessions/${sessionId}/abandon`);
    return response.data;
  },

  /** Upload an audio blob to storage; returns the public URL. */
  uploadAudio: async (file: File): Promise<AudioUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await authApi.post('/speaking-test/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  /** Get current test progress (resume helper). */
  getProgress: async (): Promise<SpeakingTestProgress> => {
    const response = await authApi.get('/speaking-test/progress');
    return response.data;
  },
};

// Speaking Error Analysis service (mirrors /api/v1/speaking-error-analysis/*)
// ─────────────────────────────────────────────────────────────
export const speakingErrorAnalysisService = {
  analyzeTranscript: async (
    responseId: string,
    part: string = "part_1",
    topic: string = "",
  ): Promise<SpeakingErrorAnalysis> => {
    const response = await authApi.post(`/speaking-error-analysis/${responseId}`, null, {
      params: { part, topic },
    });
    return response.data;
  },

  getAnalysis: async (responseId: string): Promise<SpeakingErrorAnalysis> => {
    const response = await authApi.get(`/speaking-error-analysis/${responseId}`);
    return response.data;
  },

  listAnalyses: async (limit = 50): Promise<SpeakingErrorAnalysisListResponse> => {
    const response = await authApi.get('/speaking-error-analysis', { params: { limit } });
    return response.data;
  },
};

// Speaking Improvement Plan service ("Improve My Speaking Band")
// ─────────────────────────────────────────────────────────────
export const speakingImprovementPlanService = {
  generatePlan: async (
    responseId: string,
    targetBand?: number,
  ): Promise<SpeakingImprovementPlan> => {
    const params: Record<string, any> = {};
    if (targetBand !== undefined) params.target_band = targetBand;
    const response = await authApi.post(`/speaking-improvement-plan/${responseId}`, null, {
      params,
    });
    return response.data;
  },

  getPlan: async (responseId: string): Promise<SpeakingImprovementPlan> => {
    const response = await authApi.get(`/speaking-improvement-plan/${responseId}`);
    return response.data;
  },

  listPlans: async (limit = 50): Promise<SpeakingImprovementPlanListResponse> => {
    const response = await authApi.get('/speaking-improvement-plan', { params: { limit } });
    return response.data;
  },
};

// Speaking Reattempt Mode service
// ─────────────────────────────────────────────────────────────
export interface SpeakingReattemptStartResponse {
  original_response_id: string;
  response_id: string;
  attempt_number: number;
  part: string;
  topic: string;
}

export interface SpeakingCriterionComparison {
  criterion: string;
  label: string;
  attempt_1_band: number;
  attempt_2_band: number;
  delta: number;
  improved: boolean;
}

export interface SpeakingAttemptComparison {
  compared: boolean;
  reason?: string;
  original_response_id: string;
  latest_response_id: string;
  latest_attempt_number: number;
  overall_band: { attempt_1: number; attempt_2: number; delta: number; improved: boolean };
  criteria: SpeakingCriterionComparison[];
  duration_seconds: { attempt_1: number; attempt_2: number; delta: number };
  filler_words: { attempt_1: number; attempt_2: number; delta: number };
  error_count: { attempt_1: number; attempt_2: number; delta: number };
  what_improved: string[];
  what_stayed_the_same: string[];
  what_became_worse: string[];
  focus_next: string[];
  bonus_xp: number;
  bonus_reason?: string;
}

export const speakingReattemptService = {
  startReattempt: async (responseId: string): Promise<SpeakingReattemptStartResponse> => {
    const response = await authApi.post(`/speaking-reattempts/${responseId}/start`);
    return response.data;
  },

  evaluateReattempt: async (responseId: string): Promise<any> => {
    const response = await authApi.post(`/speaking-reattempts/${responseId}/evaluate`);
    return response.data;
  },

  getComparison: async (responseId: string): Promise<SpeakingAttemptComparison> => {
    const response = await authApi.get(`/speaking-reattempts/${responseId}/compare`);
    return response.data;
  },

  listReattempts: async (limit = 50): Promise<{ results: any[]; total: number }> => {
    const response = await authApi.get('/speaking-reattempts', { params: { limit } });
    return response.data;
  },
};

// Speaking Practice Mode service
// ─────────────────────────────────────────────────────────────
export const speakingPracticeService = {
  startSession: async (
    practiceMode: string,
    targetBand?: number,
  ): Promise<SpeakingPracticeSession> => {
    const params: Record<string, any> = { practice_mode: practiceMode };
    if (targetBand !== undefined) params.target_band = targetBand;
    const response = await authApi.post('/speaking-practice/sessions', null, { params });
    return response.data;
  },

  saveResponse: async (
    sessionId: string,
    transcript: string,
    durationSeconds: number = 0,
    audioUrl: string = "",
  ): Promise<SpeakingPracticeSession> => {
    const response = await authApi.patch(`/speaking-practice/sessions/${sessionId}`, {
      transcript, duration_seconds: durationSeconds, audio_url: audioUrl,
    });
    return response.data;
  },

  evaluateSession: async (
    sessionId: string,
    targetBand?: number,
  ): Promise<any> => {
    const params: Record<string, any> = {};
    if (targetBand !== undefined) params.target_band = targetBand;
    const response = await authApi.post(`/speaking-practice/sessions/${sessionId}/evaluate`, null, { params });
    return response.data;
  },

  getSession: async (sessionId: string): Promise<SpeakingPracticeSession> => {
    const response = await authApi.get(`/speaking-practice/sessions/${sessionId}`);
    return response.data;
  },

  listSessions: async (limit = 50): Promise<SpeakingPracticeSessionListResponse> => {
    const response = await authApi.get('/speaking-practice/sessions', { params: { limit } });
    return response.data;
  },
};

// Speaking Interactive Coach service
// ─────────────────────────────────────────────────────────────
export const speakingCoachService = {
  startSession: async (
    contextType: string,
    contextId: string,
    options?: {
      practiceMode?: string;
      part?: string;
      targetBand?: number;
      transcript?: string;
      question?: string;
      evaluation?: Record<string, any>;
      errorAnalysis?: Record<string, any>;
    },
  ): Promise<any> => {
    const params: Record<string, any> = { context_type: contextType, context_id: contextId };
    if (options) {
      if (options.practiceMode !== undefined) params.practice_mode = options.practiceMode;
      if (options.part !== undefined) params.part = options.part;
      if (options.targetBand !== undefined) params.target_band = options.targetBand;
    }
    const data: Record<string, any> = {};
    if (options) {
      if (options.transcript !== undefined) data.transcript = options.transcript;
      if (options.question !== undefined) data.question = options.question;
      if (options.evaluation !== undefined) data.evaluation = options.evaluation;
      if (options.errorAnalysis !== undefined) data.error_analysis = options.errorAnalysis;
    }
    const response = await authApi.post('/speaking-coach/sessions', data, { params });
    return response.data;
  },

  chat: async (sessionId: string, question: string): Promise<SpeakingCoachChatResult> => {
    const response = await authApi.post(`/speaking-coach/sessions/${sessionId}/chat`, { question });
    return response.data;
  },

  getSession: async (sessionId: string): Promise<SpeakingCoachConversation> => {
    const response = await authApi.get(`/speaking-coach/sessions/${sessionId}`);
    return response.data;
  },

  listSessions: async (limit = 50, contextId?: string): Promise<{ results: SpeakingCoachConversation[]; total: number }> => {
    const params: Record<string, any> = { limit };
    if (contextId) params.context_id = contextId;
    const response = await authApi.get('/speaking-coach/sessions', { params });
    return response.data;
  },
};

// Speaking Progress Analytics service
// ─────────────────────────────────────────────────────────────
export const speakingAnalyticsService = {
  getDashboard: async (
    days: number = 90,
    part?: string,
  ): Promise<SpeakingAnalyticsDashboardResponse> => {
    const params: Record<string, any> = { days };
    if (part) params.part = part;
    const response = await authApi.get('/speaking-analytics/dashboard', { params });
    return response.data;
  },

  getBandHistory: async (
    days: number = 90,
    part?: string,
  ): Promise<any> => {
    const params: Record<string, any> = { days };
    if (part) params.part = part;
    const response = await authApi.get('/speaking-analytics/band-history', { params });
    return response.data;
  },

  getMetrics: async (days: number = 90, part?: string): Promise<any> => {
    const params: Record<string, any> = { days };
    if (part) params.part = part;
    const response = await authApi.get('/speaking-analytics/metrics', { params });
    return response.data;
  },

  getCommonErrors: async (days: number = 90): Promise<any> => {
    const response = await authApi.get('/speaking-analytics/common-errors', { params: { days } });
    return response.data;
  },

  getImprovementRate: async (
    criterion: string = "overall",
    days: number = 90,
    part?: string,
  ): Promise<any> => {
    const params: Record<string, any> = { criterion, days };
    if (part) params.part = part;
    const response = await authApi.get('/speaking-analytics/improvement-rate', { params });
    return response.data;
  },

  getAttemptHistory: async (days: number = 90): Promise<any> => {
    const response = await authApi.get('/speaking-analytics/attempt-history', { params: { days } });
    return response.data;
  },
};

export { authApi, api };
export default api;