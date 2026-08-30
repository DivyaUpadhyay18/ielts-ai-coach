"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  Headphones,
  Mic,
  Pause,
  Play,
  RefreshCcw,
  RotateCcw,
  Save,
  Sparkles,
  Square,
  Volume2,
  X,
} from "lucide-react";
import { speakingDiagnosticService } from "@/services/speaking-diagnostic";
import type {
  SpeakingCriterion,
  SpeakingPart,
  SpeakingPrompt,
  SpeakingRecording,
} from "@/types/speaking-diagnostic";
import { SPEAKING_CRITERIA_LABELS, SPEAKING_PART_LABELS } from "@/types/speaking-diagnostic";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { Input } from "@/components/ui/input";

function formatTime(totalSeconds: number): string {
  const m = Math.floor(Math.max(0, totalSeconds) / 60);
  const s = Math.max(0, totalSeconds) % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

const CRITERIA_KEYS: SpeakingCriterion[] = [
  "fluency_coherence",
  "lexical_resource",
  "grammatical_range",
  "pronunciation",
];

const PART_ORDER: SpeakingPart[] = ["part_1", "part_2", "part_3"];

export function SpeakingDiagnosticTest() {
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Part + question rotation
  const [part, setPart] = useState<SpeakingPart>("part_1");
  const [prompts, setPrompts] = useState<SpeakingPrompt[]>([]);
  // Rotating queue of prompt ids (shuffled) for the selected part.
  const [rotation, setRotation] = useState<string[]>([]);
  const [rotationIndex, setRotationIndex] = useState(0);
  const [selectedPrompt, setSelectedPrompt] = useState<SpeakingPrompt | null>(null);

  // Recording state
  const [recording, setRecording] = useState<SpeakingRecording | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [transcript, setTranscript] = useState("");
  const [durationSeconds, setDurationSeconds] = useState(0);

  // Microphone / MediaRecorder
  const [isRecording, setIsRecording] = useState(false);
  const [isMicRequesting, setIsMicRequesting] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordStartRef = useRef<number>(0);

  // Playback
  const [audioPlaying, setAudioPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Timer
  const [phase, setPhase] = useState<"idle" | "prep" | "speaking">("idle");
  const [phaseLeft, setPhaseLeft] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Saving
  const [saving, setSaving] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);

  // Manual scoring
  const [scores, setScores] = useState<Record<SpeakingCriterion, string>>({
    fluency_coherence: "",
    lexical_resource: "",
    grammatical_range: "",
    pronunciation: "",
  });
  const [scoring, setScoring] = useState(false);

  // AI scaffold
  const [aiResult, setAiResult] = useState<Record<string, unknown> | null>(null);
  const [aiRunning, setAiRunning] = useState(false);

  // ------------------------------------------------------------------
  // Load prompts + begin rotation
  // ------------------------------------------------------------------
  const loadPrompts = useCallback(async (p: SpeakingPart) => {
    try {
      const res = await speakingDiagnosticService.getPrompts(p);
      setPrompts(res.prompts || []);
      // Shuffle the prompt ids to create a rotating queue.
      const ids = (res.prompts || []).map((q) => q.id);
      for (let i = ids.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [ids[i], ids[j]] = [ids[j], ids[i]];
      }
      setRotation(ids);
      setRotationIndex(0);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load speaking prompts.");
    }
  }, []);

  useEffect(() => {
    loadPrompts(part);
  }, [part, loadPrompts]);

  useEffect(() => {
    setLoading(false);
  }, []);

  // Pick the current prompt from the rotated queue.
  const currentPrompt = useMemo<SpeakingPrompt | null>(() => {
    if (!rotation.length) return null;
    const id = rotation[rotationIndex % rotation.length];
    return prompts.find((p) => p.id === id) || null;
  }, [rotation, rotationIndex, prompts]);

  // ------------------------------------------------------------------
  // Timer for prep + speaking phases
  // ------------------------------------------------------------------
  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startPhaseCountdown = useCallback(
    (secs: number) => {
      stopTimer();
      setPhaseLeft(secs);
      timerRef.current = setInterval(() => {
        setPhaseLeft((prev) => {
          if (prev <= 1) {
            // Time's up — auto advance to speaking phase (if in prep) or stop.
            if (phase === "prep") {
              setPhase("speaking");
              return selectedPrompt?.speak_time_seconds || 60;
            }
            stopTimer();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    },
    [phase, selectedPrompt, stopTimer]
  );

  useEffect(() => {
    return () => stopTimer();
  }, [stopTimer]);

  // When a new prompt is selected, set up the prep/speak phases.
  const resetForPrompt = useCallback(
    (p: SpeakingPrompt) => {
      stopTimer();
      setIsRecording(false);
      setAudioUrl("");
      setTranscript("");
      setDurationSeconds(0);
      setPhase("prep");
      const prep = Number(p.prep_time_seconds) || 0;
      if (prep > 0) {
        startPhaseCountdown(prep);
      } else {
        setPhaseLeft(Number(p.speak_time_seconds) || 60);
        setPhase("speaking");
      }
    },
    [startPhaseCountdown, stopTimer]
  );

  // ------------------------------------------------------------------
  // Start recording (resume-aware) + begin the rotation
  // ------------------------------------------------------------------
  const startPrompt = useCallback(
    async (prompt: SpeakingPrompt) => {
      setStarting(true);
      setError(null);
      try {
        const res = await speakingDiagnosticService.startRecording({ prompt_id: prompt.id });
        setRecording(res);
        setSelectedPrompt(prompt);
        setAudioUrl(res.audio_url || "");
        setTranscript(res.transcript || "");
        setDurationSeconds(Number(res.duration_seconds) || 0);
        setLastSavedAt(res.saved_at || null);
        resetForPrompt(prompt);
        if (res.status === "completed") {
          setPhase("idle");
        }
      } catch (e: any) {
        setError(e?.response?.data?.detail?.message || e?.message || "Failed to start speaking recording.");
      } finally {
        setStarting(false);
      }
    },
    [resetForPrompt]
  );

  // Rotate to the next question in the current part.
  const rotateNext = useCallback(() => {
    const nextIndex = rotationIndex + 1;
    setRotationIndex(nextIndex);
    const next = prompts.find((p) => p.id === rotation[nextIndex % rotation.length]);
    if (next) {
      startPrompt(next);
    }
  }, [rotationIndex, rotation, prompts, startPrompt]);

  const rotateRandom = useCallback(() => {
    if (!rotation.length) return;
    const next = Math.floor(Math.random() * rotation.length);
    setRotationIndex(next);
    const p = prompts.find((q) => q.id === rotation[next]);
    if (p) startPrompt(p);
  }, [rotation, prompts, startPrompt]);

  // ------------------------------------------------------------------
  // Microphone recording
  // ------------------------------------------------------------------
  const startRecording = useCallback(async () => {
    if (!recording || recording.status === "completed") return;
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
        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType || "audio/webm" });
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        // Stop all tracks to release the microphone.
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      };

      mediaRecorder.start();
      recordStartRef.current = Date.now();
      setIsRecording(true);
      setPhase("speaking");
      setPhaseLeft(Number(selectedPrompt?.speak_time_seconds) || 60);
    } catch (err) {
      setError("Microphone access denied. Please allow microphone access to record your response.");
    } finally {
      setIsMicRequesting(false);
    }
  }, [recording, selectedPrompt]);

// Need persistSave defined before stopRecording (which references it).
  // ------------------------------------------------------------------
  // Persist recording metadata + transcript
  // ------------------------------------------------------------------
  const persistSave = useCallback(
    async (url: string, seconds: number) => {
      if (!recording) return;
      setSaving(true);
      try {
        const updated = await speakingDiagnosticService.saveRecording(recording.id, {
          audio_url: url,
          duration_seconds: seconds,
          transcript,
        });
        setRecording(updated);
        setLastSavedAt(updated.saved_at || new Date().toISOString());
      } catch (e: any) {
        setError(e?.response?.data?.detail?.message || e?.message || "Failed to save recording.");
      } finally {
        setSaving(false);
      }
    },
    [recording, transcript]
  );

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    const elapsed = Math.round((Date.now() - recordStartRef.current) / 1000);
    setDurationSeconds(elapsed);
    setIsRecording(false);
    stopTimer();
    // Persist the recording metadata.
    persistSave(audioUrl, elapsed);
  }, [audioUrl, stopTimer, persistSave]);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // Save transcript edits (debounced).
  const handleTranscriptChange = (value: string) => {
    setTranscript(value);
    if (recording) {
      persistSave(audioUrl, durationSeconds);
    }
  };

  // ------------------------------------------------------------------
  // Playback
  // ------------------------------------------------------------------
  const togglePlayback = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => {});
    } else {
      audio.pause();
    }
  }, []);

  // ------------------------------------------------------------------
  // Complete recording
  // ------------------------------------------------------------------
  const completeRecording = useCallback(async () => {
    if (!recording) return;
    setSaving(true);
    try {
await speakingDiagnosticService.saveRecording(recording.id, {
        audio_url: audioUrl,
        duration_seconds: durationSeconds,
        transcript,
      });
      const updated = await speakingDiagnosticService.completeRecording(recording.id, {
        duration_seconds: durationSeconds,
      });
      setRecording(updated);
      setIsRecording(false);
      stopTimer();
      setPhase("idle");
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to complete recording.");
    } finally {
      setSaving(false);
    }
  }, [recording, audioUrl, durationSeconds, transcript, stopTimer]);

  // ------------------------------------------------------------------
  // Manual scoring
  // ------------------------------------------------------------------
  const canScore = CRITERIA_KEYS.every((k) => {
    const v = Number(scores[k]);
    return v >= 0 && v <= 9;
  });

  const submitManualScore = useCallback(async () => {
    if (!recording || !canScore) return;
    setScoring(true);
    try {
      const updated = await speakingDiagnosticService.submitManualScore(recording.id, {
        fluency_coherence: Number(scores.fluency_coherence),
        lexical_resource: Number(scores.lexical_resource),
        grammatical_range: Number(scores.grammatical_range),
        pronunciation: Number(scores.pronunciation),
      });
      setRecording(updated);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to save scores.");
    } finally {
      setScoring(false);
    }
  }, [recording, scores, canScore]);

  // ------------------------------------------------------------------
  // AI evaluation scaffold
  // ------------------------------------------------------------------
  const runAiEvaluate = useCallback(async () => {
    if (!recording) return;
    setAiRunning(true);
    setError(null);
    try {
      const updated = await speakingDiagnosticService.aiEvaluate(recording.id);
      setRecording(updated);
      setAiResult(updated.ai_evaluation || {});
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "AI evaluation unavailable.");
    } finally {
      setAiRunning(false);
    }
  }, [recording]);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  if (loading || starting) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4">
        <Spinner size="lg" />
        <p className="text-muted-foreground">Preparing your speaking assessment...</p>
      </div>
    );
  }

  // Report / completed view
  if (recording && recording.status === "completed") {
    const overall = recording.overall_band != null ? Number(recording.overall_band) : null;
    return (
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        <div className="text-center space-y-3">
          <Badge variant="success" className="px-4 py-1">Speaking Assessment Complete</Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">Your Speaking Report</h1>
          <p className="text-muted-foreground">
            {SPEAKING_PART_LABELS[recording.part]} — {formatTime(recording.duration_seconds)} recorded
          </p>
        </div>

        <Card className="bg-gradient-to-br from-teal-600 to-emerald-700 text-white border-none shadow-xl">
          <CardContent className="py-10 flex flex-col items-center text-center">
            <div className="flex items-center gap-8">
              <div className="flex flex-col items-center">
                <span className="text-6xl font-black">
                  {overall != null ? Number(overall).toFixed(1) : "—"}
                </span>
                <span className="mt-2 text-sm uppercase tracking-widest text-white/70">Overall Band</span>
              </div>
              <div className="h-16 w-px bg-white/20" />
              <div className="flex flex-col items-center">
                <span className="text-6xl font-black">{formatTime(recording.duration_seconds)}</span>
                <span className="mt-2 text-sm uppercase tracking-widest text-white/70">Duration</span>
              </div>
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              <Badge className="bg-white/20 text-white border-white/30">
                <Headphones className="mr-1 h-3 w-3" /> {SPEAKING_PART_LABELS[recording.part]}
              </Badge>
              <Badge className="bg-white/20 text-white border-white/30">
                <Clock className="mr-1 h-3 w-3" /> {formatTime(recording.duration_seconds)}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* Recorded audio playback */}
        {recording.audio_url && (
          <Card>
            <CardContent className="pt-6 space-y-4">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <Volume2 className="h-5 w-5 text-primary" /> Your Recording
              </h3>
              <div className="rounded-xl border border-border bg-secondary/40 p-4 space-y-3">
                <audio
                  ref={audioRef}
                  src={recording.audio_url}
                  onPlay={() => setAudioPlaying(true)}
                  onPause={() => setAudioPlaying(false)}
                  onEnded={() => setAudioPlaying(false)}
                  preload="metadata"
                />
                <div className="flex items-center gap-3">
                  <Button variant="outline" size="icon" onClick={togglePlayback} aria-label="Play/pause recording">
                    {audioPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
                  </Button>
                  <span className="text-sm text-muted-foreground">{formatTime(recording.duration_seconds)}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Criteria breakdown */}
        <Card>
          <CardContent className="pt-6 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-lg">IELTS Marking Criteria</h3>
              {overall != null && <Badge variant="accent">Manually scored</Badge>}
            </div>
            {!recording.overall_band && (
              <p className="text-sm text-muted-foreground">
                This recording has not been manually scored yet. Use the scoring panel below.
              </p>
            )}
            {CRITERIA_KEYS.map((key) => {
              const val = recording[key] != null ? Number(recording[key]) : null;
              return (
                <div key={key} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{SPEAKING_CRITERIA_LABELS[key]}</span>
                    <span className="font-bold">{val != null ? val.toFixed(1) : "—"}</span>
                  </div>
                  <Progress value={val != null ? (val / 9) * 100 : 0} className="h-3" />
                </div>
              );
            })}
          </CardContent>
        </Card>

        {/* Transcript */}
        <Card>
          <CardContent className="pt-6">
            <h3 className="font-bold text-lg mb-3">{recording.title || "Your Response"}</h3>
            <p className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground">
              {recording.transcript || "No transcript provided."}
            </p>
          </CardContent>
        </Card>

        {/* Manual scoring panel */}
        {!recording.overall_band && (
          <Card className="border-primary/30">
            <CardContent className="pt-6 space-y-5">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <Mic className="h-5 w-5 text-primary" /> Manual Scoring
              </h3>
              <p className="text-sm text-muted-foreground">
                Score each criterion 0–9 (in 0.5 steps). The overall band is averaged automatically.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                {CRITERIA_KEYS.map((key) => (
                  <div key={key} className="space-y-1">
                    <label className="text-sm font-medium">{SPEAKING_CRITERIA_LABELS[key]}</label>
                    <Input
                      type="number"
                      min={0}
                      max={9}
                      step={0.5}
                      placeholder="e.g. 6.5"
                      value={scores[key]}
                      onChange={(e) => setScores((prev) => ({ ...prev, [key]: e.target.value }))}
                    />
                  </div>
                ))}
              </div>
              <Button onClick={submitManualScore} disabled={!canScore || scoring} className="w-full">
                {scoring ? <Spinner size="sm" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                Save Manual Scores
              </Button>
            </CardContent>
          </Card>
        )}

        {/* AI evaluation scaffold */}
        <Card className="border-accent/30 bg-accent/5">
          <CardContent className="pt-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-accent" /> AI Evaluation
              </h3>
              <Badge variant="outline">Coming soon</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              {aiResult && (aiResult as any).feedback
                ? (aiResult as any).feedback
                : "AI evaluation placeholder. Connect an AI provider to enable automatic band assessment."}
            </p>
            <Button variant="outline" onClick={runAiEvaluate} disabled={aiRunning}>
              {aiRunning ? <Spinner size="sm" /> : <Sparkles className="mr-2 h-4 w-4" />}
              Run AI Evaluation (Scaffold)
            </Button>
          </CardContent>
        </Card>

        <div className="flex flex-col items-center gap-4 pt-4 border-t border-border">
          <p className="text-sm text-muted-foreground">Your recording is saved. Use this baseline to focus your speaking practice.</p>
          <div className="flex gap-4">
            <Link href="/diagnostic/speaking">
              <Button className="bg-accent hover:bg-accent/90">
                Back to Speaking Diagnostics <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Prompt selection view
  if (!recording) {
    return (
      <div className="max-w-3xl mx-auto space-y-6 py-4">
        <div className="text-center space-y-3">
          <Badge variant="accent" className="px-4 py-1">Speaking Diagnostic</Badge>
          <h1 className="text-3xl font-extrabold tracking-tight">Choose a Speaking Part</h1>
          <p className="text-muted-foreground">
            Select a part, then pick a prompt to begin. Record your spoken response, then score it
            across the four official IELTS criteria.
          </p>
        </div>

        {/* Part selector */}
        <div className="flex items-center justify-center gap-3 flex-wrap">
          {PART_ORDER.map((p) => (
            <Button
              key={p}
              variant={part === p ? "default" : "outline"}
              onClick={() => setPart(p)}
            >
              {SPEAKING_PART_LABELS[p]}
            </Button>
          ))}
        </div>

        {error && (
          <div className="rounded-lg border border-error/30 bg-error/5 p-3 text-sm text-error flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
          </div>
        )}

        <div className="space-y-4">
          {prompts.length === 0 && (
            <Card>
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                No prompts available for this part yet.
              </CardContent>
            </Card>
          )}
          {prompts.map((p) => (
            <Card key={p.id} className="border-primary/20 hover:shadow-md transition-shadow">
              <CardContent className="pt-6 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="accent">{SPEAKING_PART_LABELS[p.part]}</Badge>
                  <Badge variant="secondary">
                    <Clock className="mr-1 h-3 w-3" /> {formatTime(p.speak_time_seconds)}
                  </Badge>
                  {p.prep_time_seconds > 0 && (
                    <Badge variant="secondary">Prep {formatTime(p.prep_time_seconds)}</Badge>
                  )}
                  <Badge variant="outline">Difficulty {p.difficulty}</Badge>
                </div>
                <h3 className="font-bold text-lg">{p.title}</h3>
                <p className="text-sm text-muted-foreground whitespace-pre-line">{p.prompt_text}</p>
                <Button onClick={() => startPrompt(p)} disabled={starting}>
                  {starting ? <Spinner size="sm" /> : <Mic className="mr-2 h-4 w-4" />}
                  Start Recording
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Active recording view
  const prompt = selectedPrompt || currentPrompt;
  const metTime = phaseLeft <= 0 && phase === "speaking";

  return (
    <div className="flex flex-col gap-6">
      {/* Top control bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg text-primary">
            <Headphones className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{prompt?.title || recording.title}</h1>
            <p className="text-sm text-muted-foreground">{SPEAKING_PART_LABELS[recording.part]}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Timer */}
          {(phase === "prep" || phase === "speaking") && (
            <div className={`flex items-center gap-2 px-4 py-2 bg-secondary rounded-full font-mono text-lg font-bold ${phaseLeft < 15 ? "text-error" : ""}`}>
              <Clock className="h-5 w-5 text-primary" />
              {phase === "prep" ? "Prep " : "Speak "}
              {formatTime(phaseLeft)}
            </div>
          )}
          <Button onClick={completeRecording} disabled={saving}>
            {saving ? <Spinner size="sm" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            Submit Recording
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-error/30 bg-error/5 p-3 text-sm text-error flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Prompt panel */}
        <Card className="flex flex-col overflow-hidden">
          <CardContent className="flex-1 overflow-y-auto pt-6 space-y-4">
            <div className="flex items-center justify-between">
              <Badge variant="accent">{SPEAKING_PART_LABELS[recording.part]}</Badge>
              <Badge variant="secondary">{formatTime(durationSeconds)} recorded</Badge>
            </div>
            <div>
              <p className="text-lg font-medium leading-relaxed whitespace-pre-line">{prompt?.prompt_text}</p>
            </div>
            {prompt?.follow_up && (
              <div className="rounded-lg border border-border bg-secondary/40 p-3">
                <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">Follow-up question</p>
                <p className="text-sm">{prompt.follow_up}</p>
              </div>
            )}
            <div className="space-y-2 pt-4 border-t border-border">
              <h4 className="text-sm font-bold flex items-center gap-2">
                <Mic className="h-4 w-4 text-primary" /> Instructions
              </h4>
              <ul className="text-sm text-muted-foreground space-y-1.5">
                <li>• Press the mic to record your spoken response.</li>
                <li>• Speak at a natural pace; aim for {formatTime(prompt?.speak_time_seconds || 60)}.</li>
                <li>• Click the button again to stop and save the recording.</li>
                <li>• Add a transcript, then submit for scoring.</li>
              </ul>
            </div>
          </CardContent>
        </Card>

        {/* Recorder panel */}
        <Card className="flex flex-col overflow-hidden border-2 border-primary/20">
          <div className="border-b border-border px-4 py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Mic className="h-4 w-4 text-muted-foreground" />
              <span>{isRecording ? "Recording..." : "Ready to record"}</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Save className="h-3 w-3" />
              <span>{saving ? "Saving..." : lastSavedAt ? "Saved" : "Not saved"}</span>
            </div>
          </div>

          <CardContent className="flex-1 p-6 space-y-5">
            {/* Recording controls */}
            <div className="flex items-center justify-center gap-6 py-4">
              <button
                onClick={toggleRecording}
                disabled={isMicRequesting}
                className={`group relative flex h-20 w-20 items-center justify-center rounded-full transition-all duration-300 shadow-xl ${
                  isRecording ? "bg-error scale-110" : "bg-primary hover:scale-105"
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

            {/* Waveform (visual only) */}
            <div className="w-full h-12 flex items-center justify-center gap-1">
              {[...Array(24)].map((_, i) => (
                <div
                  key={i}
                  className={`w-1 rounded-full bg-primary/40 transition-all duration-300 ${isRecording ? "animate-bounce" : "h-2"}`}
                  style={{
                    height: isRecording ? `${20 + Math.random() * 60}%` : "8px",
                    animationDelay: `${i * 0.05}s`,
                  }}
                />
              ))}
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
                  <Button variant="outline" size="icon" onClick={togglePlayback} aria-label="Play/pause recording">
                    {audioPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
                  </Button>
                  <span className="text-sm text-muted-foreground">{formatTime(durationSeconds)}</span>
                </div>
                <p className="text-xs text-muted-foreground">Play back your recording to review it before submitting.</p>
              </div>
            )}

            {/* Transcript */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Transcript (optional)</label>
              <textarea
                className="min-h-[120px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary resize-y"
                placeholder="Paste or type a transcript of your response here. It is saved automatically..."
                value={transcript}
                onChange={(e) => handleTranscriptChange(e.target.value)}
              />
            </div>

            {/* Rotation controls */}
            <div className="flex items-center justify-between pt-2 border-t border-border">
              <Button variant="outline" size="sm" onClick={rotateRandom} disabled={starting}>
                <RefreshCcw className="mr-1 h-4 w-4" /> Random Question
              </Button>
              <Button size="sm" onClick={rotateNext} disabled={starting}>
                Next Question <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
