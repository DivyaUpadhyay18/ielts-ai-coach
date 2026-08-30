"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  Headphones,
  LayoutGrid,
  MapPin,
  Pause,
  Play,
  Rewind,
  RotateCcw,
  X,
} from "lucide-react";
import { listeningDiagnosticService } from "@/services/listening-diagnostic";
import { diagnosticService } from "@/services/diagnostic";
import type {
  ListeningBankResponse,
  ListeningQuestion,
  ListeningQuestionType,
  ListeningReport,
  ListeningTrack,
  ListeningTypeBreakdown,
} from "@/types/listening-diagnostic";
import { LISTENING_QUESTION_TYPE_LABELS } from "@/types/listening-diagnostic";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { Input } from "@/components/ui/input";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function cefrFromBand(band: number): string {
  if (band >= 8.5) return "C2";
  if (band >= 7.5) return "C1";
  if (band >= 6.5) return "B2";
  if (band >= 5.5) return "B1";
  if (band >= 4.5) return "A2";
  return "A1-";
}

const TYPE_COLORS: Record<ListeningQuestionType, string> = {
  multiple_choice: "text-teal-500",
  map: "text-blue-500",
  form_completion: "text-orange-500",
  sentence_completion: "text-rose-500",
  matching: "text-purple-500",
};

export function ListeningDiagnosticTest() {
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Attempt + bank
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [bank, setBank] = useState<ListeningBankResponse | null>(null);

  // Question navigation
  const [questionIds, setQuestionIds] = useState<string[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Answers storage: questionId -> selected answer
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  // Time tracking
  const [elapsed, setElapsed] = useState(0);
  const [questionStartSec, setQuestionStartSec] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Audio player
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [audioCurrent, setAudioCurrent] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Report
  const [report, setReport] = useState<ListeningReport | null>(null);

  const currentQuestion = useMemo<ListeningQuestion | undefined>(() => {
    if (!bank || questionIndex < 0 || questionIndex >= questionIds.length) return undefined;
    const qid = questionIds[questionIndex];
    return bank.questions.find((q) => q.id === qid);
  }, [bank, questionIndex, questionIds]);

  const currentTrack = useMemo<ListeningTrack | undefined>(() => {
    if (!bank || !currentQuestion) return undefined;
    return bank.tracks.find((t) => t.id === currentQuestion.track_id);
  }, [bank, currentQuestion]);

  // ------------------------------------------------------------------
  // Timer
  // ------------------------------------------------------------------
  useEffect(() => {
    if (attemptId && !report) {
      timerRef.current = setInterval(() => {
        setElapsed((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [attemptId, report]);

  // ------------------------------------------------------------------
  // Load bank + start attempt + resume answered state
  // ------------------------------------------------------------------
  const loadBank = useCallback(async () => {
    try {
      const b = await listeningDiagnosticService.getBank();
      setBank(b);
      setQuestionIds(b.questions.map((q) => q.id));
      setQuestionIndex(0);
      return b;
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load listening tracks.");
      return null;
    }
  }, []);

  const startOrResume = useCallback(async () => {
    setStarting(true);
    setError(null);
    try {
      const res = await diagnosticService.startAttempt();
      const a = res.attempt as any;
      setAttemptId(a.id);
      setElapsed(Number(a.total_seconds_spent) || 0);
      setQuestionStartSec(Number(a.total_seconds_spent) || 0);

      const b = await loadBank();
      // Restore already-answered answers from the shared diagnostic resume endpoint.
      try {
        const resume = await diagnosticService.getAttempt(a.id);
        const answered = (resume as any)?.answered || [];
        const restored: Record<string, string> = {};
        (answered as any[]).forEach((r: any) => {
          if (r?.section === "listening" && r?.question_id) {
            const val = r?.selected_answer ?? (r?.answer_json?.value ?? "");
            if (val !== undefined && val !== null && val !== "") {
              restored[String(r.question_id)] = String(val);
            }
          }
        });
        if (Object.keys(restored).length) {
          setAnswers((prev) => ({ ...prev, ...restored }));
        }
        // If any listening questions were answered, jump to the first unanswered.
        if (b && Object.keys(restored).length) {
          const idx = b.questions.findIndex((q) => !restored[q.id]);
          if (idx >= 0) setQuestionIndex(idx);
        }
      } catch (e: any) {
        // Resume is best-effort; ignore failures.
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to start listening diagnostic.");
    } finally {
      setStarting(false);
      setLoading(false);
    }
  }, [loadBank]);

  useEffect(() => {
    startOrResume();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------------
  // Audio player controls
  // ------------------------------------------------------------------
  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => {});
    } else {
      audio.pause();
    }
  }, []);

  const onTimeUpdate = useCallback(() => {
    if (audioRef.current) setAudioCurrent(audioRef.current.currentTime);
  }, []);

  const onLoadedMetadata = useCallback(() => {
    if (audioRef.current) setAudioDuration(audioRef.current.duration || 0);
  }, []);

  const onEnded = useCallback(() => {
    setAudioPlaying(false);
    setAudioCurrent(0);
  }, []);

  const rewind15 = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, audio.currentTime - 15);
    setAudioCurrent(audio.currentTime);
  }, []);

  const seekTo = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const audio = audioRef.current;
      if (!audio || !audioDuration) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      audio.currentTime = ratio * audioDuration;
      setAudioCurrent(audio.currentTime);
    },
    [audioDuration]
  );

  // ------------------------------------------------------------------
  // Answer submission (auto-grade)
  // ------------------------------------------------------------------
  const submitCurrentAnswer = useCallback(
    async (questionId: string, answer: string) => {
      if (!attemptId) return;
      setSubmitting(questionId);
      try {
        const timeTaken = Math.max(1, elapsed - questionStartSec);
        await listeningDiagnosticService.submitAnswer({
          attempt_id: attemptId,
          question_id: questionId,
          answer,
          time_taken_seconds: timeTaken,
        });
        setQuestionStartSec(elapsed);
      } catch (e: any) {
        setError(e?.response?.data?.detail?.message || e?.message || "Failed to save answer.");
      } finally {
        setSubmitting(null);
      }
    },
    [attemptId, elapsed, questionStartSec]
  );

  const handleSelect = async (question: ListeningQuestion, option: string) => {
    setAnswers((prev) => ({ ...prev, [question.id]: option }));
    await submitCurrentAnswer(question.id, option);
  };

  const handleTextAnswer = async (question: ListeningQuestion, value: string) => {
    setAnswers((prev) => ({ ...prev, [question.id]: value }));
    await submitCurrentAnswer(question.id, value);
  };

  const jumpTo = (idx: number) => {
    setQuestionIndex(idx);
    setPaletteOpen(false);
  };

  const handleNext = () => {
    if (questionIndex < questionIds.length - 1) {
      setQuestionIndex((i) => i + 1);
    } else {
      finishListening();
    }
  };

  const handlePrev = () => {
    if (questionIndex > 0) setQuestionIndex((i) => i - 1);
  };

  // ------------------------------------------------------------------
  // Complete + report
  // ------------------------------------------------------------------
  const finishListening = useCallback(async () => {
    if (!attemptId) return;
    setSubmitting("__finish__");
    try {
      const rep = await listeningDiagnosticService.completeListening(attemptId);
      setReport(rep);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to compute listening report.");
    } finally {
      setSubmitting(null);
    }
  }, [attemptId]);

  // ------------------------------------------------------------------
  // Renderers
  // ------------------------------------------------------------------
  if (loading || starting) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4">
        <Spinner size="lg" />
        <p className="text-muted-foreground">Preparing your listening assessment...</p>
      </div>
    );
  }

  // Report view
  if (report) {
    const cefr = cefrFromBand(Number(report.listening_band) || 0);
    const breakdown = report.type_breakdown || [];
    return (
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        <div className="text-center space-y-3">
          <Badge variant="success" className="px-4 py-1">Listening Assessment Complete</Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">Your Listening Report</h1>
          <p className="text-muted-foreground">Estimated current IELTS Listening level based on your performance.</p>
        </div>

        <Card className="bg-gradient-to-br from-teal-600 to-emerald-700 text-white border-none shadow-xl">
          <CardContent className="py-10 flex flex-col items-center text-center">
            <div className="flex items-center gap-8">
              <div className="flex flex-col items-center">
                <span className="text-6xl font-black">{Number(report.listening_band).toFixed(1)}</span>
                <span className="mt-2 text-sm uppercase tracking-widest text-white/70">Listening Band</span>
              </div>
              <div className="h-16 w-px bg-white/20" />
              <div className="flex flex-col items-center">
                <span className="text-6xl font-black">{Math.round(report.accuracy)}%</span>
                <span className="mt-2 text-sm uppercase tracking-widest text-white/70">Accuracy</span>
              </div>
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              <Badge className="bg-white/20 text-white border-white/30">{cefr}</Badge>
              <Badge className="bg-white/20 text-white border-white/30">{report.difficulty_level} difficulty</Badge>
              <Badge className="bg-white/20 text-white border-white/30">
                <Clock className="mr-1 h-3 w-3" /> {formatTime(report.total_time_seconds || 0)}
              </Badge>
            </div>
            <p className="mt-4 text-sm text-white/80">
              {report.correct_answers} of {report.total_questions} correct
            </p>
          </CardContent>
        </Card>

        {/* Per-question-type breakdown */}
        <Card>
          <CardContent className="pt-6 space-y-6">
            <h3 className="font-bold text-lg">Question Type Breakdown</h3>
            {breakdown.length === 0 && (
              <p className="text-sm text-muted-foreground">No question-type data available.</p>
            )}
            {breakdown.map((td: ListeningTypeBreakdown) => (
              <div key={td.question_type} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">
                    {LISTENING_QUESTION_TYPE_LABELS[td.question_type] || td.question_type}
                  </span>
                  <span className="font-bold">
                    {Math.round(td.accuracy)}% · avg {Math.round(td.avg_time_seconds)}s
                  </span>
                </div>
                <Progress value={td.accuracy} variant={td.accuracy >= 60 ? "success" : "default"} className="h-3" />
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardContent className="pt-6">
              <h3 className="font-semibold text-success mb-3">Strong Question Types</h3>
              <ul className="space-y-2">
                {(report.strong_types?.length
                  ? report.strong_types
                  : ["Complete more questions to see your strengths."]
                ).map((w, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-success" />
                    {LISTENING_QUESTION_TYPE_LABELS[w as ListeningQuestionType] || w}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <h3 className="font-semibold text-error mb-3">Weak Question Types</h3>
              <ul className="space-y-2">
                {(report.weak_types?.length
                  ? report.weak_types
                  : ["No weak question types detected. Great job!"]
                ).map((w, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                    <X className="h-4 w-4 text-error" />
                    {LISTENING_QUESTION_TYPE_LABELS[w as ListeningQuestionType] || w}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col items-center gap-4 pt-4 border-t border-border">
          <p className="text-sm text-muted-foreground">Use this baseline to focus your listening practice.</p>
          <div className="flex gap-4">
            <Button variant="outline" onClick={() => { setReport(null); setAttemptId(null); setBank(null); setQuestionIds([]); setAnswers({}); setQuestionIndex(0); setPaletteOpen(false); startOrResume(); }}>
              <RotateCcw className="mr-2 h-4 w-4" /> Retake Listening Diagnostic
            </Button>
            <Link href="/diagnostic">
              <Button className="bg-accent hover:bg-accent/90">
                Back to Diagnostics <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Intro view
  if (!bank || !currentQuestion) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-6">
        <div className="mx-auto p-4 rounded-2xl bg-secondary w-fit text-teal-500">
          <Headphones className="h-12 w-12" />
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight">Listening Diagnostic</h1>
        <p className="text-muted-foreground">
          Listen to each audio track and answer questions covering all five IELTS Listening question types.
        </p>
        <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <Headphones className="h-4 w-4" />
          {bank?.questions?.length ? `${bank.questions.length} questions across ${bank.tracks.length} tracks` : "Loading tracks..."}
        </div>
        <Button size="lg" onClick={() => bank && setQuestionIndex(0)} disabled={!bank || !!submitting}>
          Start Listening Assessment
        </Button>
      </div>
    );
  }

  // Question view
  const selected = answers[currentQuestion.id] || "";
  const progressVal = questionIds.length ? ((questionIndex + 1) / questionIds.length) * 100 : 0;
  const typeLabel = LISTENING_QUESTION_TYPE_LABELS[currentQuestion.question_type] || currentQuestion.question_type;
  const needsTextInput = ["form_completion", "sentence_completion"].includes(currentQuestion.question_type);
  const isMap = currentQuestion.question_type === "map";

  return (
    <div className="max-w-5xl mx-auto space-y-6 py-4">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Headphones className={`h-5 w-5 ${TYPE_COLORS[currentQuestion.question_type]}`} />
          <span className="font-semibold">{typeLabel}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setPaletteOpen((o) => !o)}>
            <LayoutGrid className="mr-1 h-4 w-4" /> Questions
          </Button>
          <Badge variant="accent" className="flex items-center gap-1">
            <Clock className="h-3 w-3" /> {formatTime(elapsed)}
          </Badge>
        </div>
      </div>

      {/* Question palette */}
      {paletteOpen && (
        <Card className="border-primary/30">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold">Jump to question</p>
              <span className="text-xs text-muted-foreground">{Object.keys(answers).length} answered</span>
            </div>
            <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(44px, 1fr))" }}>
              {questionIds.map((qid, idx) => {
                const answered = !!answers[qid];
                const active = idx === questionIndex;
                return (
                  <button
                    key={qid}
                    onClick={() => jumpTo(idx)}
                    className={`h-11 rounded-lg border text-sm font-semibold transition-all ${
                      active
                        ? "border-primary bg-primary text-primary-foreground"
                        : answered
                        ? "border-success/50 bg-success/10 text-success hover:bg-success/20"
                        : "border-border text-muted-foreground hover:bg-accent/40"
                    }`}
                  >
                    {idx + 1}
                  </button>
                );
              })}
            </div>
            <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1"><span className="h-3 w-3 rounded border border-success/50 bg-success/10" /> Answered</span>
              <span className="flex items-center gap-1"><span className="h-3 w-3 rounded border border-border" /> Unanswered</span>
              <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-primary" /> Current</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Question {questionIndex + 1} of {questionIds.length}</span>
          <span>{Object.keys(answers).length} answered</span>
        </div>
        <Progress value={progressVal} className="h-2" />
      </div>

      {error && (
        <div className="rounded-lg border border-error/30 bg-error/5 p-3 text-sm text-error flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Audio track */}
        <div className="space-y-3">
          <Card className="lg:sticky lg:top-4">
            <CardContent className="pt-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-lg">{currentTrack?.title}</h3>
                <Badge variant="secondary">Section {currentTrack?.section_number}</Badge>
              </div>
              {currentTrack?.description && (
                <p className="text-sm text-muted-foreground">{currentTrack.description}</p>
              )}

              {/* Audio player */}
              <div className="rounded-xl border border-border bg-secondary/40 p-4 space-y-3">
                <audio
                  ref={audioRef}
                  src={currentTrack?.audio_url}
                  onPlay={() => setAudioPlaying(true)}
                  onPause={() => setAudioPlaying(false)}
                  onTimeUpdate={onTimeUpdate}
                  onLoadedMetadata={onLoadedMetadata}
                  onEnded={onEnded}
                  preload="metadata"
                />
                <div className="flex items-center gap-3">
                  <Button variant="outline" size="icon" onClick={rewind15} aria-label="Rewind 15 seconds">
                    <Rewind className="h-5 w-5" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={togglePlay}
                    aria-label={audioPlaying ? "Pause audio" : "Play audio"}
                  >
                    {audioPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
                  </Button>
                  <div className="flex-1 cursor-pointer" onClick={seekTo}>
                    <Progress
                      value={audioDuration ? (audioCurrent / audioDuration) * 100 : 0}
                      className="h-2"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                      <span>{formatTime(Math.round(audioCurrent))}</span>
                      <span>{formatTime(Math.round(audioDuration))}</span>
                    </div>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Play the audio, scrub to any point, or rewind 15 seconds. You can replay as needed.
                </p>
              </div>

              {currentTrack?.transcript && (
                <details className="text-sm">
                  <summary className="cursor-pointer text-muted-foreground hover:text-primary">
                    View transcript (optional)
                  </summary>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground whitespace-pre-line">
                    {currentTrack.transcript}
                  </p>
                </details>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Question */}
        <div className="space-y-3">
          <Card className="border-primary/20">
            <CardContent className="pt-6 space-y-5">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={TYPE_COLORS[currentQuestion.question_type]}>
                  {typeLabel}
                </Badge>
                <Badge variant="secondary">Difficulty {currentQuestion.difficulty}</Badge>
              </div>
              <p className="text-lg font-medium leading-relaxed">{currentQuestion.prompt}</p>

              {needsTextInput ? (
                <div className="space-y-2">
                  <Input
                    placeholder="Type your answer here..."
                    value={selected}
                    onChange={(e) => handleTextAnswer(currentQuestion, e.target.value)}
                    disabled={!!submitting}
                    className="min-h-[48px]"
                  />
                  <p className="text-xs text-muted-foreground">
                    Enter your answer (for completion questions, use words you hear in the audio).
                  </p>
                </div>
              ) : isMap ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-4">
                    <div className="flex items-center gap-2 text-sm text-blue-600 mb-3">
                      <MapPin className="h-4 w-4" />
                      <span className="font-semibold">Map / Diagram</span>
                    </div>
                    <div className="relative h-40 rounded-lg border border-dashed border-blue-300 bg-background flex items-center justify-center">
                      <span className="text-xs text-muted-foreground">Map diagram — select the location from the options below based on the audio.</span>
                      <MapPin className="h-8 w-8 text-blue-400/40 absolute top-2 left-2" />
                      <MapPin className="h-8 w-8 text-blue-400/40 absolute bottom-2 right-2" />
                    </div>
                  </div>
                  <div className="space-y-3">
                    {(currentQuestion.options || []).map((opt, idx) => {
                      const isSelected = selected === opt;
                      return (
                        <button
                          key={idx}
                          disabled={!!submitting}
                          onClick={() => handleSelect(currentQuestion, opt)}
                          className={`w-full text-left rounded-lg border p-4 text-sm transition-all ${
                            isSelected
                              ? "border-blue-500 bg-blue-500/5 ring-2 ring-blue-500"
                              : "border-border hover:bg-accent/40"
                          }`}
                        >
                          <span className="inline-flex items-center gap-3">
                            <span className={`h-6 w-6 rounded-full border flex items-center justify-center text-xs font-bold ${isSelected ? "bg-blue-500 text-white border-blue-500" : "text-muted-foreground"}`}>
                              {String.fromCharCode(65 + idx)}
                            </span>
                            {opt}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {(currentQuestion.options || []).map((opt, idx) => {
                    const isSelected = selected === opt;
                    return (
                      <button
                        key={idx}
                        disabled={!!submitting}
                        onClick={() => handleSelect(currentQuestion, opt)}
                        className={`w-full text-left rounded-lg border p-4 text-sm transition-all ${
                          isSelected
                            ? "border-primary bg-primary/5 ring-2 ring-primary"
                            : "border-border hover:bg-accent/40"
                        }`}
                      >
                        <span className="inline-flex items-center gap-3">
                          <span className={`h-6 w-6 rounded-full border flex items-center justify-center text-xs font-bold ${isSelected ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground"}`}>
                            {String.fromCharCode(65 + idx)}
                          </span>
                          {opt}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}

              {submitting === currentQuestion.id && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Spinner size="sm" /> Grading answer...
                </div>
              )}
              {selected && submitting !== currentQuestion.id && (
                <p className="flex items-center gap-2 text-sm text-success">
                  <CheckCircle2 className="h-4 w-4" /> Answer saved.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Nav buttons */}
          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={handlePrev} disabled={questionIndex === 0}>
              <ArrowLeft className="mr-2 h-4 w-4" /> Previous
            </Button>
            <Button onClick={handleNext} disabled={!selected || !!submitting}>
              {questionIndex === questionIds.length - 1 ? "Get My Report" : "Next"}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>

          {questionIndex === questionIds.length - 1 && (
            <button onClick={finishListening} className="mx-auto block text-sm text-muted-foreground underline hover:text-primary">
              Finish and get my report
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
