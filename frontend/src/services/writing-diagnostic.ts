import { authApi } from './api';
import type {
  WritingPromptsResponse,
  WritingEssayStart,
  WritingEssaySave,
  WritingEssayComplete,
  ManualScoreSubmit,
  WritingReportResponse,
  WritingEssay,
  WritingResultsListResponse,
  WritingTaskType,
} from '@/types/writing-diagnostic';

/**
 * Frontend service for the Writing Diagnostic Module.
 *
 * All methods call the authenticated /api/v1/writing/* endpoints.
 * The backend is the source of truth for auto-save, word count, timing,
 * manual scoring, and storage.
 */
export const writingDiagnosticService = {
  /** Fetch writing prompts, optionally filtered by task type. */
  getPrompts: async (taskType?: WritingTaskType): Promise<WritingPromptsResponse> => {
    const response = await authApi.get('/writing/prompts', {
      params: taskType ? { task_type: taskType } : undefined,
    });
    return response.data;
  },

  /** Start a new writing essay for a prompt (resume-aware). */
  startEssay: async (data: WritingEssayStart): Promise<WritingEssay> => {
    const response = await authApi.post('/writing/essays', data);
    return response.data;
  },

  /** Auto-save the essay body (debounced on the client). */
  autoSave: async (essayId: string, data: WritingEssaySave): Promise<WritingEssay> => {
    const response = await authApi.post(`/writing/essays/${essayId}/save`, data);
    return response.data;
  },

  /** Complete the essay (submit for scoring). */
  completeEssay: async (essayId: string, data?: WritingEssayComplete): Promise<WritingEssay> => {
    const response = await authApi.post(`/writing/essays/${essayId}/complete`, data || {});
    return response.data;
  },

  /** Apply manual IELTS scoring across the four criteria. */
  submitManualScore: async (essayId: string, data: ManualScoreSubmit): Promise<WritingEssay> => {
    const response = await authApi.post(`/writing/essays/${essayId}/score`, data);
    return response.data;
  },

  /** Run (or scaffold) AI evaluation of the essay. */
  aiEvaluate: async (essayId: string): Promise<WritingEssay> => {
    const response = await authApi.post(`/writing/essays/${essayId}/ai`);
    return response.data;
  },

  /** Fetch the stored writing essay report. */
  getReport: async (essayId: string): Promise<WritingReportResponse> => {
    const response = await authApi.get(`/writing/essays/${essayId}`);
    return response.data;
  },

  /** List the user's stored writing essays/results. */
  listEssays: async (limit = 20): Promise<WritingResultsListResponse> => {
    const response = await authApi.get('/writing/essays', { params: { limit } });
    return response.data;
  },
};

export { writingDiagnosticService as default };
