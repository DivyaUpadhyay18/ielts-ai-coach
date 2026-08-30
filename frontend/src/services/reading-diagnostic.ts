import { authApi } from './api';
import type {
  ReadingBankResponse,
  ReadingAnswerSubmit,
  ReadingAnswerResult,
  ReadingReport,
  ReadingResultsListResponse,
} from '@/types/reading-diagnostic';

/**
 * Frontend service for the Reading Diagnostic Module.
 *
 * All methods call the authenticated /api/v1/reading/* endpoints.
 * The backend is the source of truth for grading, metrics, and storage.
 */
export const readingDiagnosticService = {
  /** Fetch all reading passages and their questions. */
  getBank: async (): Promise<ReadingBankResponse> => {
    const response = await authApi.get('/reading/bank');
    return response.data;
  },

  /** Submit and grade a single reading answer. */
  submitAnswer: async (data: ReadingAnswerSubmit): Promise<ReadingAnswerResult> => {
    const response = await authApi.post('/reading/answers', data);
    return response.data;
  },

  /** Complete the reading diagnostic and compute/store results. */
  completeReading: async (attemptId: string): Promise<ReadingReport> => {
    const response = await authApi.post(`/reading/attempts/${attemptId}/complete`);
    return response.data;
  },

  /** Fetch the stored reading diagnostic report. */
  getReport: async (attemptId: string): Promise<ReadingReport> => {
    const response = await authApi.get(`/reading/attempts/${attemptId}/report`);
    return response.data;
  },

  /** List the user's stored reading diagnostic results. */
  listResults: async (limit = 20): Promise<ReadingResultsListResponse> => {
    const response = await authApi.get('/reading/results', { params: { limit } });
    return response.data;
  },
};

export { readingDiagnosticService as default };
