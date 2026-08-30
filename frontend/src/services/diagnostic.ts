import { authApi } from './api';
import type {
  DiagnosticStartResponse,
  DiagnosticAttempt,
  QuestionBankResponse,
  DiagnosticQuestion,
  AnswerSubmit,
  ResumeResponse,
  SectionComplete,
  DiagnosticReport,
  DiagnosticSection,
} from '@/types/diagnostic';

/**
 * Frontend service for the Diagnostic Test Framework.
 *
 * All methods call the authenticated /api/v1/diagnostic/* endpoints.
 * The backend is the source of truth for progress, resume, and scoring.
 */
export const diagnosticService = {
  /** Start a new attempt, or resume any in-progress attempt. */
  startAttempt: async (): Promise<DiagnosticStartResponse> => {
    const response = await authApi.post('/diagnostic/attempts', {});
    return response.data;
  },

  /** Resume a specific in-progress attempt. */
  getAttempt: async (attemptId: string): Promise<ResumeResponse> => {
    const response = await authApi.get(`/diagnostic/attempts/${attemptId}`);
    return response.data;
  },

  /** Fetch a randomized question bank for a section. */
  getQuestions: async (section: DiagnosticSection): Promise<QuestionBankResponse> => {
    const response = await authApi.get(`/diagnostic/questions/${section}`);
    return response.data;
  },

  /** Submit and grade a single answer. */
  submitAnswer: async (
    attemptId: string,
    data: AnswerSubmit
  ): Promise<{ question_id: string; is_correct: boolean; correct_answer: string }> => {
    const response = await authApi.post(`/diagnostic/attempts/${attemptId}/answers`, data);
    return response.data;
  },

  /** Mark a section as completed. */
  completeSection: async (
    attemptId: string,
    data: SectionComplete
  ): Promise<{ completed_sections: string[]; current_section: DiagnosticSection | null; attempt_completed: boolean }> => {
    const response = await authApi.post(
      `/diagnostic/attempts/${attemptId}/sections/${data.section}/complete`,
      data
    );
    return response.data;
  },

  /** Finalize the attempt and compute the report. */
  completeAttempt: async (attemptId: string): Promise<DiagnosticReport> => {
    const response = await authApi.post(`/diagnostic/attempts/${attemptId}/complete`);
    return response.data;
  },

  /** Fetch the diagnostic report. */
  getReport: async (attemptId: string): Promise<DiagnosticReport> => {
    const response = await authApi.get(`/diagnostic/attempts/${attemptId}/report`);
    return response.data;
  },
};

export type { DiagnosticQuestion, DiagnosticAttempt };
