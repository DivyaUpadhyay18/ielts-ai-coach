import { authApi } from './api';
import type {
  ListeningBankResponse,
  ListeningAnswerSubmit,
  ListeningAnswerResult,
  ListeningReport,
  ListeningResultsListResponse,
} from '@/types/listening-diagnostic';

/**
 * Frontend service for the Listening Diagnostic Module.
 *
 * All methods call the authenticated /api/v1/listening/* endpoints.
 * The backend is the source of truth for grading, metrics, and storage.
 */
export const listeningDiagnosticService = {
  /** Fetch all listening tracks and their questions. */
  getBank: async (): Promise<ListeningBankResponse> => {
    const response = await authApi.get('/listening/bank');
    return response.data;
  },

  /** Submit and grade a single listening answer. */
  submitAnswer: async (data: ListeningAnswerSubmit): Promise<ListeningAnswerResult> => {
    const response = await authApi.post('/listening/answers', data);
    return response.data;
  },

  /** Complete the listening diagnostic and compute/store results. */
  completeListening: async (attemptId: string): Promise<ListeningReport> => {
    const response = await authApi.post(`/listening/attempts/${attemptId}/complete`);
    return response.data;
  },

  /** Fetch the stored listening diagnostic report. */
  getReport: async (attemptId: string): Promise<ListeningReport> => {
    const response = await authApi.get(`/listening/attempts/${attemptId}/report`);
    return response.data;
  },

  /** List the user's stored listening diagnostic results. */
  listResults: async (limit = 20): Promise<ListeningResultsListResponse> => {
    const response = await authApi.get('/listening/results', { params: { limit } });
    return response.data;
  },
};

export { listeningDiagnosticService as default };
