import { authApi } from './api';
import type {
  SpeakingPromptsResponse,
  SpeakingRecordingStart,
  SpeakingRecordingSave,
  SpeakingRecordingComplete,
  SpeakingManualScoreSubmit,
  SpeakingReportResponse,
  SpeakingRecording,
  SpeakingResultsListResponse,
  SpeakingPart,
} from '@/types/speaking-diagnostic';

/**
 * Frontend service for the Speaking Diagnostic Module.
 *
 * All methods call the authenticated /api/v1/speaking/* endpoints.
 * The backend is the source of truth for recording storage, duration,
 * manual scoring, and AI evaluation scaffolding.
 */
export const speakingDiagnosticService = {
  /** Fetch speaking prompts, optionally filtered by part. */
  getPrompts: async (part?: SpeakingPart): Promise<SpeakingPromptsResponse> => {
    const response = await authApi.get('/speaking/prompts', {
      params: part ? { part } : undefined,
    });
    return response.data;
  },

  /** Start a new speaking recording for a prompt (resume-aware). */
  startRecording: async (data: SpeakingRecordingStart): Promise<SpeakingRecording> => {
    const response = await authApi.post('/speaking/recordings', data);
    return response.data;
  },

  /** Save the recorded audio metadata + transcript. */
  saveRecording: async (
    recordingId: string,
    data: SpeakingRecordingSave
  ): Promise<SpeakingRecording> => {
    const response = await authApi.post(`/speaking/recordings/${recordingId}/save`, data);
    return response.data;
  },

  /** Complete the recording (submit for scoring). */
  completeRecording: async (
    recordingId: string,
    data?: SpeakingRecordingComplete
  ): Promise<SpeakingRecording> => {
    const response = await authApi.post(
      `/speaking/recordings/${recordingId}/complete`,
      data || {}
    );
    return response.data;
  },

  /** Apply manual IELTS scoring across the four speaking criteria. */
  submitManualScore: async (
    recordingId: string,
    data: SpeakingManualScoreSubmit
  ): Promise<SpeakingRecording> => {
    const response = await authApi.post(`/speaking/recordings/${recordingId}/score`, data);
    return response.data;
  },

  /** Run (or scaffold) AI evaluation of the speaking transcript. */
  aiEvaluate: async (recordingId: string): Promise<SpeakingRecording> => {
    const response = await authApi.post(`/speaking/recordings/${recordingId}/ai`);
    return response.data;
  },

  /** Fetch the stored speaking recording report. */
  getReport: async (recordingId: string): Promise<SpeakingReportResponse> => {
    const response = await authApi.get(`/speaking/recordings/${recordingId}`);
    return response.data;
  },

  /** List the user's stored speaking recordings/results. */
  listRecordings: async (limit = 20): Promise<SpeakingResultsListResponse> => {
    const response = await authApi.get('/speaking/recordings', { params: { limit } });
    return response.data;
  },
};

export { speakingDiagnosticService as default };
