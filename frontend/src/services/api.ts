import axios from 'axios';

// API base URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const API_V1_URL = `${API_URL.replace('/api', '')}/api/v1`;

// Token storage keys
const ACCESS_TOKEN_KEY = 'ielts_access_token';
const REFRESH_TOKEN_KEY = 'ielts_refresh_token';

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
  },
  
  clearTokens: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
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
} from '@/types';

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

export { authApi, api };
export default api;
