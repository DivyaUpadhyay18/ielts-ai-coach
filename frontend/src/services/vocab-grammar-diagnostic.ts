import { authApi } from './api';
import type {
  VGBankResponse,
  VGAnswerSubmit,
  VGAnswerResult,
  VGReport,
  VGResultsListResponse,
} from '@/types/vocab-grammar-diagnostic';

/**
 * Frontend service for the Vocabulary & Grammar Diagnostic Module.
 *
 * All methods call the authenticated /api/v1/vocab-grammar/* endpoints.
 * The backend is the source of truth for grading, metrics, and storage.
 */
export const vocabGrammarDiagnosticService = {
  /** Fetch the vocabulary and grammar question bank. */
  getBank: async (): Promise<VGBankResponse> => {
    const response = await authApi.get('/vocab-grammar/bank');
    return response.data;
  },

  /** Submit and grade a single vocabulary/grammar answer. */
  submitAnswer: async (data: VGAnswerSubmit): Promise<VGAnswerResult> => {
    const response = await authApi.post('/vocab-grammar/answers', data);
    return response.data;
  },

  /** Complete the vocabulary/grammar diagnostic and compute/store results. */
  completeAttempt: async (attemptId: string): Promise<VGReport> => {
    const response = await authApi.post(`/vocab-grammar/attempts/${attemptId}/complete`);
    return response.data;
  },

  /** Fetch the stored vocabulary/grammar diagnostic report. */
  getReport: async (attemptId: string): Promise<VGReport> => {
    const response = await authApi.get(`/vocab-grammar/attempts/${attemptId}/report`);
    return response.data;
  },

  /** List the user's stored vocabulary/grammar diagnostic results. */
  listResults: async (limit = 20): Promise<VGResultsListResponse> => {
    const response = await authApi.get('/vocab-grammar/results', { params: { limit } });
    return response.data;
  },
};

export { vocabGrammarDiagnosticService as default };
