"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Mic,
  Square,
  Play,
  Pause,
  Volume2,
  Clock,
  Save,
  RefreshCw,
  CheckCircle2,
  ArrowLeft,
  ArrowRight,
  Headphones,
  Calendar,
  AlertCircle,
  Trash2,
  ChevronRight,
  PauseCircle,
   Send,
   MessageCircle,
   Search,
  Loader2,
  Target,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { Modal, ModalHeader, ModalTitle, ModalFooter } from "@/components/ui/modal";
import { speakingTestService, speakingErrorAnalysisService, speakingImprovementPlanService, speakingReattemptService, speakingCoachService } from "@/services/api";
import type {
  SpeakingTestPart,
  SpeakingTestPrompt,
  SpeakingTestSession,
  SpeakingTestResponse,
  SpeakingTestProgress,
  SpeakingErrorAnalysis,
  SpeakingImprovementPlan,
  SpeakingCoachConversation,
} from "@/types/speaking-test";
import { SPEAKING_TEST_PART_LABELS, PART_ORDER } from "@/types/speaking-test";

function formatTime(totalSeconds: number): string {
  const m = Math.floor(Math.max(0, totalSeconds) / 60);
  const s = Math.max(0, totalSeconds) % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

const AUTO_SAVE_DEBOUNCE_MS = 2000;

export default function SpeakingTestWorkspacePage() {
  // ── Auth ──────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Session state ─────────────────────────────────────
  const [session, setSession] = useState<SpeakingTestSession | null>(null);
  const [responses, setResponses] = useState<SpeakingTestResponse[]>([]);
  const [currentPart, setCurrentPart] = useState<SpeakingTestPart>("part_1");

  // ── Prompts ───────────────────────────────────────────
  const [promptsByPart, setPromptsByPart] = useState<Record<string, SpeakingTestPrompt[]>>({});
  const [promptsLoaded, setPromptsLoaded] = useState(false);

  // ── Current question flow ─────────────────────────────
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentPrompt, setCurrentPrompt] = useState<SpeakingTestPrompt | null>(null);
  const [currentResponse, setCurrentResponse] = useState<SpeakingTestResponse | null>(null);

  // ── UI phase ──────────────────────────────────────────
  type TestPhase = "welcome" | "select" | "prep" | "recording" | "review" | "completed";
  const [phase, setPhase] = useState<TestPhase>("welcome");

  // ── Recording state ───────────────────────────────────
  const [isRecording, setIsRecording] = useState(false);
  const [isMicRequesting, setIsMicRequesting] = useState(false);
  const [audioUrl, setAudioUrl] = useState("");
  const [durationSeconds, setDurationSeconds] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordStartRef = useRef<number>(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [audioPlaying, setAudioPlaying] = useState(false);

  // ── Speaking Error Analysis ─────────────────────────────
  const [errorAnalysis, setErrorAnalysis] = useState<SpeakingErrorAnalysis | null>(null);
  const [isAnalysisLoading, setIsAnalysisLoading] = useState(false);
  const [showAnalysisModal, setShowAnalysisModal] = useState(false);

  const [improvementPlan, setImprovementPlan] = useState<SpeakingImprovementPlan | null>(null);
  const [isPlanLoading, setIsPlanLoading] = useState(false);
  const [showPlanModal, setShowPlanModal] = useState(false);

  const [isReattemptLoading, setIsReattemptLoading] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<any>(null);
  const [showComparisonModal, setShowComparisonModal] = useState(false);

  // Speaking Coach state
  const [coachConversation, setCoachConversation] = useState<SpeakingCoachConversation | null>(null);
  const [showCoachModal, setShowCoachModal] = useState(false);
  const [coachInput, setCoachInput] = useState("");
  const [isCoachLoading, setIsCoachLoading] = useState(false);
  const [coachError, setCoachError] = useState<string | null>(null);

  const handleStartCoach = async (response: SpeakingTestResponse) => {
    if (!response.transcript) return;
    try {
      const result = await speakingCoachService.startSession(
        "test_response",
        response.id,
        {
          transcript: response.transcript,
          question: response.prompt_text,
          evaluation: {},
          targetBand: 7.0,
        },
      );
      setCoachConversation(result);
      setShowCoachModal(true);
      setCoachError(null);
    } catch (err: any) {
      setCoachError(err?.message || "Failed to start coach");
    }
  };

  const handleCoachChat = async () => {
    if (!coachInput.trim() || !coachConversation) return;
    setIsCoachLoading(true);
    setCoachError(null);
    try {
      const result = await speakingCoachService.chat(coachConversation.id, coachInput);
      setCoachConversation(prev => prev ? {
        ...prev,
        messages: result.updated_messages,
        updated_at: new Date().toISOString(),
      } : prev);
      setCoachInput("");
    } catch (err: any) {
      setCoachError(err?.message || "Failed to get coach response");
    } finally {
      setIsCoachLoading(false);
    }
  };

  const handleReattempt = async (response: SpeakingTestResponse) => {
    setIsReattemptLoading(true);
    try {
      const result = await speakingReattemptService.startReattempt(response.id);
      alert(`Reattempt #${result.attempt_number} started!`);
      window.location.reload();
    } catch (err: any) {
      setError(err?.message || "Failed to start reattempt");
    } finally {
      setIsReattemptLoading(false);
    }
  };

  const handleAnalyzeResponse = async (response: SpeakingTestResponse) => {
    if (!response.transcript || !response.is_saved) return;
    setIsAnalysisLoading(true);
    try {
      const result = await speakingErrorAnalysisService.analyzeTranscript(
        response.id,
        response.part,
        response.title || "",
      );
      setErrorAnalysis(result);
      setShowAnalysisModal(true);
    } catch (err: any) {
      setError(err?.message || "Failed to analyze speaking response");
    } finally {
      setIsAnalysisLoading(false);
    }
  };

  const handleGeneratePlan = async (responseId: string, targetBand?: number) => {
    setIsPlanLoading(true);
    try {
      const result = await speakingImprovementPlanService.generatePlan(
        responseId,
        targetBand,
      );
      setImprovementPlan(result);
      setShowPlanModal(true);
      setShowAnalysisModal(false);
    } catch (err: any) {
      setError(err?.message || "Failed to generate improvement plan");
    } finally {
      setIsPlanLoading(false);
    }
  };

  // ── Timers ────────────────────────────────────────────
  const [phaseLeft, setPhaseLeft] = useState(0);
  const [speakingLeft, setSpeakingLeft] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Modals ────────────────────────────────────────────
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);

  // ── Auto-save debounce ────────────────────────────────
  const autoSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ─────────────────────────────────────────────────────────────────
  // Load prompts (all parts at once). Returns the part→prompts map so
  // callers can use it immediately without waiting for a re-render.
  // ─────────────────────────────────────────────────────────────────
  const loadAllPrompts = useCallback(async (): Promise<Record<string, SpeakingTestPrompt[]> | null> => {
    if (promptsLoaded) return null;
    try {
      const byPart: Record<string, SpeakingTestPrompt[]> = {};
      for (const part of PART_ORDER) {
        const res = await speakingTestService.getPrompts(part);
        byPart[part] = res.prompts || [];
      }
      setPromptsByPart(byPart);
      setPromptsLoaded(true);
      return byPart;
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load prompts");
      return null;
    }
  }, [promptsLoaded]);

  // ─────────────────────────────────────────────────────────────────
  // Resume: load active session on mount
  // ─────────────────────────────────────────────────────────────────
  const loadSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const sess = await speakingTestService.getCurrentSession();
      if (sess) {
        setSession(sess);
        setResponses(sess.responses || []);
        const part = (sess.current_part || "part_1") as SpeakingTestPart;
        setCurrentPart(part);

        // Load the full question bank (all parts) so advancing works later.
        let byPart = await loadAllPrompts();
        if (!byPart) byPart = promptsByPart;

        const partPrompts = byPart[part] || [];

        // Restore the question that matches the latest recorded response so
        // the user resumes exactly where they left off.
        const latestResponse =
          sess.responses && sess.responses.length > 0
            ? sess.responses[sess.responses.length - 1]
            : null;

        if (partPrompts.length > 0) {
          let idx = 0;
          if (latestResponse?.prompt_id) {
            const matchIdx = partPrompts.findIndex(
              (p) => p.id === latestResponse.prompt_id,
            );
            if (matchIdx >= 0) idx = matchIdx;
          }
          setCurrentQuestionIndex(idx);
          setCurrentPrompt(partPrompts[idx]);
        }

        // If there's a response for the current question, load it
        if (latestResponse) {
          setCurrentResponse(latestResponse);
          // Restore transcript
          if (latestResponse.transcript) setTranscript(latestResponse.transcript);
          if (latestResponse.audio_url) setAudioUrl(latestResponse.audio_url);
          if (latestResponse.duration_seconds) setDurationSeconds(latestResponse.duration_seconds);
          if (latestResponse.is_saved) setPhase("review");
          else setPhase("select");
        } else {
          setPhase("select");
        }
      } else {
        setPhase("welcome");
      }
    } catch (e: any) {
      setPhase("welcome");
    } finally {
      setLoading(false);
    }
  }, [loadAllPrompts, promptsByPart]);

  // ─────────────────────────────────────────────────────────────────
  // Start test
  // ─────────────────────────────────────────────────────────────────
  const startTest = useCallback(async () => {
    setIsSaving(true);
    setError(null);
    try {
      const sess = await speakingTestService.startTest();
      setSession(sess);
      setResponses(sess.responses || []);
      setCurrentPart("part_1");
      setCurrentQuestionIndex(0);

      const byPart = (await loadAllPrompts()) || promptsByPart;
      const partPrompts = byPart["part_1"] || [];
      if (partPrompts.length > 0) setCurrentPrompt(partPrompts[0]);
      setPhase("select");
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to start test");
    } finally {
      setIsSaving(false);
    }
  }, [loadAllPrompts, promptsByPart]);

  // ─────────────────────────────────────────────────────────────────
  // Timer helpers
  // ─────────────────────────────────────────────────────────────────
  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startCountDown = useCallback(
    (secs: number, onExpire: () => void) => {
      stopTimer();
      setPhaseLeft(secs);
      setSpeakingLeft(secs);
      timerRef.current = setInterval(() => {
        setPhaseLeft((prev) => {
          if (prev <= 1) {
            stopTimer();
            onExpire();
            return 0;
          }
          return prev - 1;
        });
        setSpeakingLeft((prev) => Math.max(0, prev - 1));
      }, 1000);
    },
    [stopTimer],
  );

  // ─────────────────────────────────────────────────────────────────
  // Select a question → enter prep or recording
  // ─────────────────────────────────────────────────────────────────
  const selectQuestion = useCallback(
    async (prompt: SpeakingTestPrompt) => {
      setCurrentPrompt(prompt);
      setError(null);

      try {
        const res = await speakingTestService.startResponse({
          session_id: session!.id,
          prompt_id: prompt.id,
          part: prompt.part,
        });
        setCurrentResponse(res);
        setAudioUrl(res.audio_url || "");
        setTranscript(res.transcript || "");
        setDurationSeconds(res.duration_seconds || 0);
        setLastSaved(res.updated_at || null);
      } catch (e: any) {
        setError(e?.response?.data?.detail?.message || e?.message || "Failed to start question");
        return;
      }

      const prep = prompt.prep_time_seconds || 0;
      const stopIfRecording = () => {
        stopTimer();
        // Stop the recorder only if it is genuinely recording (avoids the
        // stale-closure problem of reading `isRecording` inside the timer).
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
          mediaRecorderRef.current.stop();
        }
        setIsRecording(false);
        setPhase("review");
      };

      if (prep > 0) {
        setPhase("prep");
        startCountDown(prep, () => {
          setPhase("recording");
          startCountDown(prompt.speak_time_seconds || 60, stopIfRecording);
        });
      } else {
        setPhase("recording");
        startCountDown(prompt.speak_time_seconds || 60, stopIfRecording);
      }
    },
    [session, startCountDown, stopTimer],
  );

  // ─────────────────────────────────────────────────────────────────
  // Auto-save: upload audio + save to backend
  // ─────────────────────────────────────────────────────────────────
  const autoSaveBlob = useCallback(
    async (blobUrl: string, blob: Blob) => {
      if (!currentResponse) return;

      // Try uploading to storage; if it fails, fall back to the blob URL
      let audioUrl = blobUrl;
      try {
        const file = new File([blob], `response_${Date.now()}.webm`, { type: blob.type });
        const uploadRes = await speakingTestService.uploadAudio(file);
        audioUrl = uploadRes.audio_url;
      } catch {
        // Storage unavailable — keep blob URL (only valid in this session)
      }

      // Debounced save
      if (autoSaveTimeoutRef.current) clearTimeout(autoSaveTimeoutRef.current);
      autoSaveTimeoutRef.current = setTimeout(async () => {
        setIsSaving(true);
        try {
          const updated = await speakingTestService.saveResponse(
            currentResponse.id,
            session!.id,
            {
              audio_url: audioUrl,
              duration_seconds: durationSeconds,
              transcript,
              is_saved: false,
            },
          );
          setCurrentResponse(updated);
          setResponses((prev) =>
            prev.map((r) => (r.id === updated.id ? updated : r)),
          );
          setLastSaved(updated.updated_at || new Date().toISOString());
        } catch (e: any) {
          setError(e?.response?.data?.detail?.message || e?.message || "Auto-save failed");
        } finally {
          setIsSaving(false);
        }
      }, AUTO_SAVE_DEBOUNCE_MS);
    },
    [currentResponse, session, durationSeconds, transcript],
  );

  // ─────────────────────────────────────────────────────────────────
  // Recording controls
  // ─────────────────────────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    if (!currentResponse) return;
    setIsMicRequesting(true);
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "";
      const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: mediaRecorder.mimeType || "audio/webm",
        });
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        setDurationSeconds(Math.round((Date.now() - recordStartRef.current) / 1000));

        // Release microphone
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;

        // Persist to localStorage for resume
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = reader.result as string;
          const key = `speaking_audio_${currentResponse.id}`;
          try {
            localStorage.setItem(key, dataUrl);
          } catch {
            // localStorage full — skip
          }
        };
        reader.readAsDataURL(blob);

        autoSaveBlob(url, blob);
      };

      mediaRecorder.start();
      recordStartRef.current = Date.now();
      setIsRecording(true);
    } catch {
      setError("Microphone access denied. Please allow microphone access to record.");
    } finally {
      setIsMicRequesting(false);
    }
  }, [currentResponse, autoSaveBlob]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    stopTimer();
  }, [stopTimer]);

  // ─────────────────────────────────────────────────────────────────
  // Playback
  // ─────────────────────────────────────────────────────────────────
  const togglePlayback = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => {});
    } else {
      audio.pause();
    }
  }, []);

  // ─────────────────────────────────────────────────────────────────
  // Transcript change (debounced save)
  // ─────────────────────────────────────────────────────────────────
  const handleTranscriptChange = useCallback(
    (value: string) => {
      setTranscript(value);
      if (!currentResponse) return;
      if (autoSaveTimeoutRef.current) clearTimeout(autoSaveTimeoutRef.current);
      autoSaveTimeoutRef.current = setTimeout(async () => {
        setIsSaving(true);
        try {
          const updated = await speakingTestService.saveResponse(
            currentResponse.id,
            session!.id,
            {
              audio_url: audioUrl,
              duration_seconds: durationSeconds,
              transcript: value,
              is_saved: false,
            },
          );
          setCurrentResponse(updated);
          setResponses((prev) =>
            prev.map((r) => (r.id === updated.id ? updated : r)),
          );
          setLastSaved(updated.updated_at || new Date().toISOString());
        } catch (e: any) {
          setError(e?.response?.data?.detail?.message || e?.message || "Auto-save failed");
        } finally {
          setIsSaving(false);
        }
      }, AUTO_SAVE_DEBOUNCE_MS);
    },
    [currentResponse, session, audioUrl, durationSeconds],
  );

  // ─────────────────────────────────────────────────────────────────
  // Save recording (explicit)
  // ─────────────────────────────────────────────────────────────────
  const saveRecording = useCallback(async () => {
    if (!currentResponse) return;
    setIsSaving(true);
    try {
      const updated = await speakingTestService.saveResponse(
        currentResponse.id,
        session!.id,
        {
          audio_url: audioUrl,
          duration_seconds: durationSeconds,
          transcript,
          is_saved: true,
        },
      );
      setCurrentResponse(updated);
      setResponses((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r)),
      );
      setLastSaved(updated.updated_at || new Date().toISOString());
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to save");
    } finally {
      setIsSaving(false);
    }
  }, [currentResponse, session, audioUrl, durationSeconds, transcript]);

  // ─────────────────────────────────────────────────────────────────
  // Delete and re-record
  // ─────────────────────────────────────────────────────────────────
  const deleteAndReRecord = useCallback(async () => {
    if (!currentResponse) return;
    try {
      await speakingTestService.deleteResponse(currentResponse.id, session!.id);
      // Clear localStorage for the old response
      localStorage.removeItem(`speaking_audio_${currentResponse.id}`);
      setAudioUrl("");
      setTranscript("");
      setDurationSeconds(0);
      setLastSaved(null);
      // Re-enter the prep/recording flow for the same question (this also
      // re-creates the response row for a fresh recording).
      await selectQuestion(currentPrompt!);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to delete recording");
    }
  }, [currentResponse, session, currentPrompt, selectQuestion]);

  // ─────────────────────────────────────────────────────────────────
  // Continue to next question or part
  // ─────────────────────────────────────────────────────────────────
  const handleContinue = useCallback(async () => {
    if (!session || !currentPrompt) return;

    stopTimer();
    setIsRecording(false);

    const partPrompts = promptsByPart[currentPart] || [];
    const nextIndex = currentQuestionIndex + 1;

    if (nextIndex < partPrompts.length) {
      // Next question in the same part
      setCurrentQuestionIndex(nextIndex);
      const nextPrompt = partPrompts[nextIndex];
      setCurrentPrompt(nextPrompt);
      setCurrentResponse(null);
      setAudioUrl("");
      setTranscript("");
      setDurationSeconds(0);
      setPhase("select");

      try {
        await speakingTestService.startResponse({
          session_id: session.id,
          prompt_id: nextPrompt.id,
          part: nextPrompt.part,
        });
      } catch (e: any) {
        setError(e?.response?.data?.detail?.message || e?.message || "Failed to load next question");
      }
    } else {
      // No more questions in this part — advance to next part
      try {
        if (currentPart === "part_3") {
          // Complete the test
          await speakingTestService.completeTest(session.id);
          const updated = await speakingTestService.getSession(session.id);
          setSession(updated);
          setResponses(updated.responses);
          setPhase("completed");
        } else {
          const updated = await speakingTestService.advancePart(session.id);
          setSession(updated);
          const nextPart = (updated.current_part || "part_1") as SpeakingTestPart;
          setCurrentPart(nextPart);
          setCurrentQuestionIndex(0);

          const nextPrompts = promptsByPart[nextPart] || [];
          if (nextPrompts.length > 0) {
            const nextPrompt = nextPrompts[0];
            setCurrentPrompt(nextPrompt);
          }
          setPhase("select");
        }
      } catch (e: any) {
        setError(e?.response?.data?.detail?.message || e?.message || "Failed to advance");
      }
    }
  }, [session, currentPrompt, currentPart, currentQuestionIndex, promptsByPart, stopTimer]);

  // ─────────────────────────────────────────────────────────────────
  // Complete test
  // ─────────────────────────────────────────────────────────────────
  const completeTest = useCallback(async () => {
    if (!session) return;
    setIsCompleting(true);
    try {
      await speakingTestService.completeTest(session.id);
      const updated = await speakingTestService.getSession(session.id);
      setSession(updated);
      setResponses(updated.responses);
      setShowCompleteModal(false);
      setPhase("completed");
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to complete test");
    } finally {
      setIsCompleting(false);
    }
  }, [session]);

  // ─────────────────────────────────────────────────────────────────
  // Restore audio from localStorage on mount/resume
  // ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (currentResponse?.id && !audioUrl) {
      const key = `speaking_audio_${currentResponse.id}`;
      const stored = localStorage.getItem(key);
      if (stored) {
        setAudioUrl(stored);
      }
    }
  }, [currentResponse, audioUrl]);

  // ─────────────────────────────────────────────────────────────────
  // Cleanup on unmount
  // ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      stopTimer();
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, [stopTimer]);

  // ─────────────────────────────────────────────────────────────────
  // Initial load (resume)
  // ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    void loadAllPrompts();
    void loadSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─────────────────────────────────────────────────────────────────
  // Render helpers
  // ─────────────────────────────────────────────────────────────────
  const partPrompts = promptsByPart[currentPart] || [];
  const progressPercent = (PART_ORDER.indexOf(currentPart) / (PART_ORDER.length - 1)) * 100;
  const responsesForCurrentPart = responses.filter((r) => r.part === currentPart);

  // ─────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center py-24 space-y-4">
          <Spinner size="lg" />
          <p className="text-muted-foreground">Loading your speaking test...</p>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-6xl mx-auto space-y-6 py-4">
        {/* Error banner */}
        {error && (
          <div className="rounded-lg border border-error/30 bg-error/5 p-3 text-sm text-error flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-error hover:text-error/80">
              ×
            </button>
          </div>
        )}

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Headphones className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">Speaking Test Workspace</h1>
          </div>
          {session && session.status !== "completed" && (
            <Badge variant="accent" className="px-3 py-1">
              {isSaving ? "Saving..." : lastSaved ? "Saved" : "Auto-saves as you go"}
            </Badge>
          )}
        </div>

        {/* Progress bar across parts */}
        {session && session.status !== "completed" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">
                {SPEAKING_TEST_PART_LABELS[currentPart]}
              </span>
              <span className="text-muted-foreground">
                Question {currentQuestionIndex + 1} of {partPrompts.length}
              </span>
            </div>
            <Progress value={progressPercent} className="h-3" />
            <div className="flex gap-2">
              {PART_ORDER.map((p) => (
                <Badge
                  key={p}
                  variant={currentPart === p ? "default" : responsesForCurrentPart.length > 0 && PART_ORDER.indexOf(p) < PART_ORDER.indexOf(currentPart) ? "success" : "secondary"}
                  className="text-xs"
                >
                  {p.replace("_", " ").toUpperCase()}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Welcome screen */}
        {phase === "welcome" && (
          <WelcomeScreen onStart={startTest} loading={isSaving} />
        )}

        {/* Question selection */}
        {phase === "select" && session && (
          currentPrompt ? (
            <div className="space-y-6">
              <QuestionCard prompt={currentPrompt} part={currentPart} />
              <div className="flex justify-center">
                <Button size="lg" onClick={() => selectQuestion(currentPrompt)} disabled={isSaving}>
                  {isSaving ? <Spinner size="sm" /> : <Mic className="mr-2 h-5 w-5" />}
                  Start Recording
                </Button>
              </div>
            </div>
          ) : partPrompts.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Select a question</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {partPrompts.map((p, i) => (
                  <button
                    key={p.id}
                    onClick={() => selectQuestion(p)}
                    className="w-full text-left rounded-lg border border-border p-3 hover:bg-secondary/40 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">
                        {i + 1}. {p.title}
                      </span>
                      <Mic className="h-4 w-4 text-primary" />
                    </div>
                  </button>
                ))}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                Questions for this part could not be loaded. Please refresh and try again.
              </CardContent>
            </Card>
          )
        )}

        {/* Preparation phase (Part 2 only) */}
        {phase === "prep" && currentPrompt && (
          <div className="space-y-6">
            <QuestionCard prompt={currentPrompt} part={currentPart} />
            <Card className="border-2 border-primary/20">
              <CardContent className="py-12 text-center space-y-6">
                <Badge variant="warning" className="px-4 py-1 text-lg">
                  Preparation Time
                </Badge>
                <div className="text-6xl font-mono font-bold text-primary">
                  {formatTime(phaseLeft)}
                </div>
                <p className="text-muted-foreground max-w-md mx-auto">
                  You have {formatTime(currentPrompt.prep_time_seconds || 60)} to prepare.
                  Think about your bullet points. You will speak for{" "}
                  {formatTime(currentPrompt.speak_time_seconds || 120)}.
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Recording phase */}
        {phase === "recording" && currentPrompt && (
          <div className="space-y-6">
            <QuestionCard prompt={currentPrompt} part={currentPart} />

            <Card className="border-2 border-primary/20">
              <CardContent className="py-8 space-y-6">
                {/* Timer */}
                <div className="flex justify-center">
                  <div
                    className={`flex items-center gap-2 px-4 py-2 bg-secondary rounded-full font-mono text-2xl font-bold ${
                      phaseLeft < 15 ? "text-error" : "text-primary"
                    }`}
                  >
                    <Clock className="h-6 w-6" />
                    Speak&nbsp;
                    {formatTime(phaseLeft)}
                  </div>
                </div>

                {/* Recording controls */}
                <div className="flex justify-center">
                  <button
                    onClick={isRecording ? stopRecording : startRecording}
                    disabled={isMicRequesting}
                    className={`group relative flex h-20 w-20 items-center justify-center rounded-full transition-all duration-300 shadow-xl ${
                      isRecording
                        ? "bg-error scale-110"
                        : "bg-primary hover:scale-105"
                    }`}
                  >
                    {isRecording ? (
                      <Square className="h-8 w-8 text-white fill-current" />
                    ) : (
                      <Mic className="h-10 w-10 text-white" />
                    )}
                    {isRecording && (
                      <span className="absolute -inset-2 rounded-full border-2 border-error animate-ping opacity-25" />
                    )}
                  </button>
                </div>

                <p className="text-center text-sm text-muted-foreground">
                  {isRecording
                    ? "Recording... Click to stop."
                    : isMicRequesting
                      ? "Requesting microphone..."
                      : "Click the microphone to start recording your response."}
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Review phase */}
        {phase === "review" && currentPrompt && currentResponse && (
          <div className="space-y-6">
            <QuestionCard prompt={currentPrompt} part={currentPart} />

            {/* Recording status */}
            <Card>
              <CardContent className="pt-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-lg flex items-center gap-2">
                    <Volume2 className="h-5 w-5 text-primary" />
                    Your Recording
                  </h3>
                  <Badge variant={currentResponse.is_saved ? "success" : "secondary"}>
                    {currentResponse.is_saved ? "Saved" : "Not saved"}
                  </Badge>
                </div>

                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                  <Clock className="h-4 w-4" />
                  <span>Duration: {formatTime(durationSeconds)}</span>
                </div>

                {/* Playback */}
                {audioUrl && (
                  <div className="rounded-xl border border-border bg-secondary/40 p-4 space-y-3">
                    <audio
                      ref={audioRef}
                      src={audioUrl}
                      onPlay={() => setAudioPlaying(true)}
                      onPause={() => setAudioPlaying(false)}
                      onEnded={() => setAudioPlaying(false)}
                      preload="metadata"
                    />
                    <div className="flex items-center gap-3">
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={togglePlayback}
                        aria-label="Play/pause recording"
                      >
                        {audioPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
                      </Button>
                      <span className="text-sm text-muted-foreground">{formatTime(durationSeconds)}</span>
                    </div>
                  </div>
                )}

                {/* Delete and re-record */}
                <Button
                  variant="outline"
                  onClick={deleteAndReRecord}
                  disabled={isSaving}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete &amp; Re-record
                </Button>
              </CardContent>
            </Card>

            {/* Transcript */}
            <Card>
              <CardContent className="pt-6 space-y-3">
                <label className="text-sm font-medium">Transcript</label>
                <textarea
                  className="min-h-[120px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary resize-y"
                  placeholder="Type or paste a transcript of your response..."
                  value={transcript}
                  onChange={(e) => handleTranscriptChange(e.target.value)}
                />
              </CardContent>
            </Card>

            {/* Action buttons */}
            <div className="flex items-center justify-between pt-4 border-t border-border">
              <Button variant="outline" onClick={() => setPhase("select")} disabled={isSaving}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <div className="flex items-center gap-3">
                <Button variant="ghost" onClick={saveRecording} disabled={isSaving || !audioUrl}>
                  {isSaving ? <Spinner size="sm" /> : <Save className="mr-2 h-4 w-4" />}
                  Save Recording
                </Button>
                <Button onClick={handleContinue} disabled={isSaving}>
                  Continue
                  <ChevronRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Completed screen */}
        {phase === "completed" && session && (
          <CompletedScreen
            session={session}
            responses={responses}
            onRestart={() => window.location.reload()}
            onAnalyzeResponse={handleAnalyzeResponse}
            isAnalyzing={isAnalysisLoading}
            onReattempt={handleReattempt}
            isReattemptLoading={isReattemptLoading}
          />
        )}

        {/* Speaking Error Analysis Modal */}
      {showAnalysisModal && errorAnalysis && (
        <SpeakingErrorAnalysisModal
            analysis={errorAnalysis}
            onClose={() => setShowAnalysisModal(false)}
            onGeneratePlan={(target) => handleGeneratePlan(errorAnalysis.response_id, target)}
            onStartCoach={handleStartCoach}
            response={responses.find(r => r.id === errorAnalysis.response_id) || responses[0]}
          />
      )}

      {/* Speaking Improvement Plan Modal */}
      {showPlanModal && improvementPlan && (
        <SpeakingImprovementPlanModal
          plan={improvementPlan}
          onClose={() => setShowPlanModal(false)}
        />
      )}

      {/* Speaking Interactive Coach Modal */}
      {showCoachModal && (
          <Modal
          isOpen={showCoachModal}
          onClose={() => setShowCoachModal(false)}
        >
          <ModalHeader>
            <ModalTitle>AI Speaking Coach</ModalTitle>
            <CardDescription>
              Ask questions about your speaking performance — e.g. &ldquo;Why did I get 6.5?&rdquo; or
              &ldquo;How can I improve fluency?&rdquo;
            </CardDescription>
          </ModalHeader>
          <div className="space-y-4 max-h-[500px] overflow-y-auto">
            {coachConversation && coachConversation.messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}>
                  {msg.content}
                  {msg.metadata && msg.role === "assistant" && (
                    <div className="mt-2 space-y-1">
                      {msg.metadata.action_step && (
                        <div className="text-xs font-medium">
                          Action: {msg.metadata.action_step}
                        </div>
                      )}
                      {msg.metadata.example && (
                        <div className="text-xs italic text-muted-foreground">
                          Example: {msg.metadata.example}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {coachError && (
              <div className="text-sm text-destructive">{coachError}</div>
            )}
          </div>
          <div className="flex gap-2 pt-4 border-t border-border">
            <input
              type="text"
              value={coachInput}
              onChange={(e) => setCoachInput(e.target.value)}
              placeholder="Ask the coach a question..."
              className="flex-1 rounded-lg border border-border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isCoachLoading) {
                  e.preventDefault();
                  void handleCoachChat();
                }
              }}
            />
            <Button
              size="sm"
              onClick={handleCoachChat}
              disabled={isCoachLoading || !coachInput.trim()}
            >
              {isCoachLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              Send
            </Button>
          </div>
          {coachConversation && coachConversation.messages.length === 0 && (
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
              {["Why did I get 6.5?", "How can I improve fluency?", "Was my answer too short?",
                "What vocabulary should I use?"].map((q) => (
                <Button
                  key={q}
                  size="sm"
                  variant="outline"
                  className="text-xs justify-start"
                  onClick={() => setCoachInput(q)}
                >
                  {q}
                </Button>
              ))}
            </div>
          )}
        </Modal>
      )}
      </div>

      {/* Complete test confirmation modal */}
      <Modal isOpen={showCompleteModal} onClose={() => setShowCompleteModal(false)}>
        <ModalHeader>
          <ModalTitle>Complete Speaking Test?</ModalTitle>
        </ModalHeader>
        <div className="py-4 text-sm text-muted-foreground">
          All three parts are complete. Once you confirm, your test will be marked as finished
          and can no longer be edited.
        </div>
        <ModalFooter>
          <Button variant="outline" onClick={() => setShowCompleteModal(false)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={completeTest} disabled={isCompleting}>
            {isCompleting ? <Spinner size="sm" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            Complete Test
          </Button>
        </ModalFooter>
      </Modal>
    </DashboardLayout>
  );
}

// ─── Sub-components ───────────────────────────────────────────────

function WelcomeScreen({ onStart, loading }: {
  onStart: () => void;
  loading: boolean;
}) {
  return (
    <div className="max-w-3xl mx-auto space-y-8 py-8">
      <div className="text-center space-y-4">
        <Badge variant="accent" className="px-4 py-1">
          Speaking Test Workspace
        </Badge>
        <h1 className="text-4xl font-extrabold tracking-tight">Full IELTS Speaking Mock</h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          Practice all three parts of the IELTS Speaking test with authentic prompts,
          preparation timers, and microphone recording.
        </p>
      </div>

      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="pt-6 space-y-4">
          <div className="flex items-center gap-3">
            <Calendar className="h-5 w-5 text-primary" />
            <span className="font-medium">Structure</span>
          </div>
          <ul className="space-y-2 text-sm text-muted-foreground ml-8">
            <li>• <strong>Part 1:</strong> Introduction &amp; Interview (11-14 questions, short answers)</li>
            <li>• <strong>Part 2:</strong> Individual Long Turn (1 question, 1-min prep, 2-min speak)</li>
            <li>• <strong>Part 3:</strong> Two-way Discussion (3-4 questions, deeper discussion)</li>
          </ul>
          <div className="flex items-center gap-3 pt-2">
            <Save className="h-5 w-5 text-primary" />
            <span className="font-medium">Progress is auto-saved as you go</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Your session will resume automatically if you leave and return.
          </p>
        </CardContent>
      </Card>

      <div className="text-center pt-4">
        <Button size="lg" onClick={onStart} disabled={loading}>
          {loading ? <Spinner size="sm" /> : <Mic className="mr-2 h-5 w-5" />}
          Start Full Speaking Test
        </Button>
      </div>
    </div>
  );
}

function QuestionCard({ prompt, part }: {
  prompt: SpeakingTestPrompt;
  part: SpeakingTestPart;
}) {
  return (
    <Card className="border-2 border-primary/10">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-xl">{prompt.title}</CardTitle>
          <Badge variant="accent">{SPEAKING_TEST_PART_LABELS[part]}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-lg leading-relaxed whitespace-pre-line">
          {prompt.prompt_text}
        </p>
        {prompt.follow_up && (
          <div className="mt-4 rounded-lg border border-border bg-secondary/30 p-3">
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">
              Follow-up
            </p>
            <p className="text-sm">{prompt.follow_up}</p>
          </div>
        )}
        <div className="flex items-center gap-4 mt-4 text-xs text-muted-foreground">
          {prompt.prep_time_seconds > 0 && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Prep: {formatTime(prompt.prep_time_seconds)}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Speak: {formatTime(prompt.speak_time_seconds)}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function CompletedScreen({
  session,
  responses,
  onRestart,
  onAnalyzeResponse,
  isAnalyzing,
  onReattempt,
  isReattemptLoading,
}: {
  session: SpeakingTestSession;
  responses: SpeakingTestResponse[];
  onRestart: () => void;
  onAnalyzeResponse: (response: SpeakingTestResponse) => void;
  isAnalyzing: boolean;
  onReattempt: (response: SpeakingTestResponse) => void;
  isReattemptLoading: boolean;
}) {
  const totalDuration = responses.reduce((sum, r) => sum + (r.duration_seconds || 0), 0);
  const completedParts = new Set(responses.map((r) => r.part));

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-8">
      <div className="text-center space-y-4">
        <Badge variant="success" className="px-4 py-1 text-lg">
          <CheckCircle2 className="h-5 w-5 mr-1" />
          Speaking Test Complete
        </Badge>
        <h1 className="text-3xl font-extrabold tracking-tight">Well done!</h1>
        <p className="text-muted-foreground">
          You completed all three parts of the IELTS Speaking test.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold text-primary">{responses.length}</div>
            <div className="text-sm text-muted-foreground">Responses recorded</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold text-primary">{formatTime(totalDuration)}</div>
            <div className="text-sm text-muted-foreground">Total speaking time</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold text-primary">
              {completedParts.has("part_1") && completedParts.has("part_2") && completedParts.has("part_3")
                ? "3/3"
                : `${completedParts.size}/3`}
            </div>
            <div className="text-sm text-muted-foreground">Parts completed</div>
          </CardContent>
        </Card>
      </div>

      {/* Response review */}
      <Card>
        <CardHeader>
          <CardTitle>Your Responses</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {responses.map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between rounded-lg border border-border p-3"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    {r.part.replace("_", " ")}
                  </Badge>
                  <span className="font-medium text-sm">{r.title}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  Duration: {formatTime(r.duration_seconds || 0)} &middot;
                  {r.is_saved ? " Saved" : " Draft"}
                </div>
              </div>
              {r.audio_url && (
                <audio
                  src={r.audio_url}
                  controls
                  style={{ width: "200px" }}
                  preload="none"
                />
              )}
              {r.transcript && r.is_saved && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onAnalyzeResponse(r)}
                  disabled={isAnalyzing}
                >
                  {isAnalyzing ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  Analyze
                </Button>
              )}
              {r.transcript && r.is_saved && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onReattempt(r)}
                  disabled={isReattemptLoading}
                >
                  {isReattemptLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                  Reattempt
                </Button>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="text-center pt-4">
        <Button onClick={onRestart} variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          Start a new test
        </Button>
      </div>
    </div>
  );
}

// ─── Speaking Error Analysis Modal ──────────────────────────────────
function SpeakingErrorAnalysisModal({
  analysis,
  onClose,
  onGeneratePlan,
  onStartCoach,
  response,
}: {
  analysis: SpeakingErrorAnalysis;
  onClose: () => void;
  onGeneratePlan: (targetBand?: number) => void;
  onStartCoach: (response: SpeakingTestResponse) => void;
  response: SpeakingTestResponse;
}) {
  const SEVERITY_COLOR: Record<string, string> = {
    critical: "bg-red-500/15 text-red-600 border-red-400/50",
    major: "bg-orange-500/15 text-orange-600 border-orange-400/50",
    minor: "bg-blue-500/15 text-blue-600 border-blue-400/50",
  };

  const CRITERION_LABEL: Record<string, string> = {
    fluency_coherence: "Fluency & Coherence",
    lexical_resource: "Lexical Resource",
    grammatical_range: "Grammatical Range",
    pronunciation: "Pronunciation",
  };

  const ISSUE_TYPE_ICON: Record<string, string> = {
    "Grammar": "🔧",
    "Repeated Vocabulary": "♻️",
    "Weak Vocabulary": "📔",
    "Unnatural Expression": "🗣️",
    "Filler Words": "…",
    "Repetition": "🔁",
    "Incomplete Sentence": "✂️",
    "Hesitation Indicator": "⏸️",
    "Coherence Problem": "🔗",
    "Pronunciation": "🔤",
  };

  return (
    <Modal isOpen={true} onClose={onClose} className="max-w-4xl">
      <ModalHeader>
        <ModalTitle className="flex items-center gap-2">
          <Search className="h-5 w-5 text-primary" />
          Speaking Error Analysis
        </ModalTitle>
      </ModalHeader>

      <div className="max-h-[70vh] overflow-y-auto py-4 space-y-6">
        {/* Band summary */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Overall</span>
              <p className="text-2xl font-bold text-primary">{analysis.overall_band.toFixed(1)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Fluency</span>
              <p className="text-xl font-medium">{analysis.fluency_coherence_band.toFixed(1)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Lexis</span>
              <p className="text-xl font-medium">{analysis.lexical_resource_band.toFixed(1)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Grammar</span>
              <p className="text-xl font-medium">{analysis.grammatical_range_band.toFixed(1)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Pronunciation</span>
              <p className="text-xl font-medium">{analysis.pronunciation_band.toFixed(1)}</p>
            </CardContent>
          </Card>
        </div>

        {/* Feedback */}
        {analysis.feedback && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Your Feedback</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{analysis.feedback}</p>
            </CardContent>
          </Card>
        )}

        {/* Issues list */}
        {analysis.issues.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">
                Specific Issues ({analysis.issues.length})
              </CardTitle>
              <CardDescription>
                Click any issue to expand the full explanation.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {analysis.issues.map((issue, i) => (
                <details key={`issue-${i}`} className="group">
                  <summary className="cursor-pointer list-none">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-lg">
                          {ISSUE_TYPE_ICON[issue.issue_type] || "•"}
                        </span>
                        <span className="font-medium text-sm">
                          {issue.issue_type}
                        </span>
                        <Badge
                          variant="outline"
                          className={`text-xs ${SEVERITY_COLOR[issue.severity] || ""}`}
                        >
                          {issue.severity}
                        </Badge>
                      </div>
                      <span className="text-xs text-muted-foreground group-open:hidden">
                        Tap to expand
                      </span>
                    </div>
                  </summary>
                  <div className="mt-3 pl-6 space-y-3 border-l-2 border-primary/10 pl-4">
                    {issue.original_phrase && (
                      <div>
                        <span className="text-xs font-medium text-muted-foreground">
                          What you said:
                        </span>
                        <blockquote className="mt-1 text-sm italic border-l-2 border-muted pl-3 ml-0">
                          {issue.original_phrase}
                        </blockquote>
                      </div>
                    )}
                    <div>
                      <span className="text-xs font-medium text-muted-foreground">
                        What happened?
                      </span>
                      <p className="text-sm mt-1">{issue.explanation}</p>
                    </div>
                    <div>
                      <span className="text-xs font-medium text-muted-foreground">
                        Why is this a problem?
                      </span>
                      <p className="text-sm mt-1">{issue.why_problem}</p>
                    </div>
                    <div>
                      <span className="text-xs font-medium text-muted-foreground">
                        How should I improve it?
                      </span>
                      <p className="text-sm mt-1 text-green-600 dark:text-green-300">{issue.suggested_improvement}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs">
                        {CRITERION_LABEL[issue.criterion_affected] || issue.criterion_affected}
                      </Badge>
                      {issue.context && (
                        <Badge variant="outline" className="text-xs">
                          {issue.context}
                        </Badge>
                      )}
                    </div>
                  </div>
                </details>
              ))}
            </CardContent>
          </Card>
        )}

        {analysis.is_estimate && (
          <p className="text-xs text-muted-foreground text-center">
            This analysis is AI-generated based on your transcript — not official IELTS advice.
          </p>
        )}
      </div>

      <ModalFooter>
        <Button size="sm" variant="outline" onClick={onClose}>
          Close
        </Button>
        <Button size="sm" variant="outline" onClick={() => onStartCoach(response)}>
          <MessageCircle className="h-4 w-4 mr-1" />
          Ask the Coach
        </Button>
        <Button size="sm" onClick={() => onGeneratePlan()}>
          <Target className="h-4 w-4 mr-1" />
          Improve My Speaking Band
        </Button>
      </ModalFooter>
    </Modal>
  );
}

// ─── Speaking Improvement Plan Modal ("Improve My Speaking Band") ─────
function SpeakingImprovementPlanModal({
  plan,
  onClose,
}: {
  plan: SpeakingImprovementPlan;
  onClose: () => void;
}) {
  const CRITERION_LABEL: Record<string, string> = {
    fluency_coherence: "Fluency & Coherence",
    lexical_resource: "Lexical Resource",
    grammatical_range: "Grammatical Range",
    pronunciation: "Pronunciation",
  };

  const PRIORITY_COLOR: Record<string, string> = {
    high: "text-red-600 dark:text-red-400",
    medium: "text-orange-600 dark:text-orange-400",
    low: "text-green-600 dark:text-green-400",
  };

  const gapColor = (plan.band_gap >= 2) ? "text-red-500" :
    (plan.band_gap >= 1) ? "text-orange-500" : "text-green-500";

  return (
    <Modal isOpen={true} onClose={onClose} className="max-w-4xl">
      <ModalHeader>
        <ModalTitle className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          Improve My Speaking Band
        </ModalTitle>
      </ModalHeader>

      <div className="max-h-[75vh] overflow-y-auto py-4">
        {/* Band Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Current Band</span>
              <p className="text-2xl font-bold text-primary">{plan.current_band.toFixed(1)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Target Band</span>
              <p className="text-2xl font-bold text-green-500">{plan.target_band.toFixed(1)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Band Gap</span>
              <p className={`text-2xl font-bold ${gapColor}`}>+{plan.band_gap.toFixed(1)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Daily Practice</span>
              <p className="text-2xl font-bold text-primary">{plan.suggested_daily_minutes} min</p>
            </CardContent>
          </Card>
        </div>

        {/* Strongest / Weakest */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <Card>
            <CardContent className="pt-4">
              <span className="text-xs text-muted-foreground">Strongest Criterion</span>
              <p className="font-medium">{CRITERION_LABEL[plan.strongest_criterion] || plan.strongest_criterion}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <span className="text-xs text-muted-foreground">Weakest Criterion</span>
              <p className="font-medium text-red-500">{CRITERION_LABEL[plan.weakest_criterion] || plan.weakest_criterion}</p>
            </CardContent>
          </Card>
        </div>

        {/* Criterion Priorities */}
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Priority by Criterion</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(plan.criterion_priorities).map(([criterion, priority]) => (
                <div key={criterion} className="text-center p-3 border rounded-lg">
                  <span className="text-xs text-muted-foreground block mb-1">
                    {CRITERION_LABEL[criterion] || criterion}
                  </span>
                  <span className={`font-bold text-sm ${PRIORITY_COLOR[priority] || ""}`}>
                    {priority.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Current Level */}
        <Card className="mb-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Where You Are Now</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{plan.current_level_description}</p>
          </CardContent>
        </Card>

        {/* Target Level */}
        <Card className="mb-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">What Band {plan.target_band.toFixed(1)} Requires</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{plan.target_level_description}</p>
          </CardContent>
        </Card>

        {/* Specific Changes */}
        <Card className="mb-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Specific Changes to Make</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {plan.specific_changes.map((change, i) => (
              <div key={`change-${i}`} className="border-l-3 border-primary/30 pl-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">{change.area}</span>
                  <Badge variant="secondary" className={PRIORITY_COLOR[change.priority] || ""}>
                    {change.priority}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{change.change}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Practice Exercises */}
        <Card className="mb-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Practice Exercises</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {plan.practice_exercises.map((ex, i) => (
              <div key={`ex-${i}`}>
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">{ex.title}</span>
                  <Badge variant="outline" className="text-xs">
                    {ex.estimated_minutes} min · {ex.skill_focus}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground mt-1">{ex.description}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Practice Topics */}
        {plan.practice_topics.length > 0 && (
          <Card className="mb-4">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Practice Topics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {plan.practice_topics.map((topic, i) => (
                  <Badge key={`topic-${i}`} variant="secondary">
                    {topic}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Recommended Resources */}
        {plan.recommended_resources.length > 0 && (
          <Card className="mb-4">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Recommended Resources</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {plan.recommended_resources.map((res, i) => (
                <div key={`res-${i}`}>
                  <a
                    href={res.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-sm text-primary hover:underline"
                  >
                    {res.title}
                  </a>
                  <p className="text-xs text-muted-foreground mt-1">{res.why}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Next Speaking Task */}
        <Card className="mb-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Next Speaking Task</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{plan.next_speaking_task}</p>
          </CardContent>
        </Card>

        {/* Suggested Mission */}
        {plan.suggested_mission && plan.suggested_mission.title && (
          <Card className="mb-4 bg-primary/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Target className="h-4 w-4" />
                Suggested Mission
              </CardTitle>
            </CardHeader>
            <CardContent>
              <h4 className="font-medium">{plan.suggested_mission.title}</h4>
              <p className="text-sm text-muted-foreground mt-1">
                {plan.suggested_mission.description}
              </p>
              <div className="mt-2">
                <Badge variant="outline">
                  {plan.suggested_mission.duration_minutes} min · {plan.suggested_mission.skill}
                </Badge>
              </div>
            </CardContent>
          </Card>
        )}

        {plan.is_estimate && (
          <p className="text-xs text-muted-foreground text-center">
            AI-generated improvement plan — not official IELTS advice.
          </p>
        )}
      </div>

      <ModalFooter>
        <Button size="sm" variant="outline" onClick={onClose}>
          Close
        </Button>
      </ModalFooter>
    </Modal>
  );
}
