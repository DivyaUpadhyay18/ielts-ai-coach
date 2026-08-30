"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  Headphones,
  Keyboard,
  Mic,
  PenTool,
  Play,
  RotateCcw,
  Save,
  X,
} from "lucide-react";
import { diagnosticService } from "@/services/diagnostic";
import type {
  DiagnosticAttempt,
  DiagnosticQuestion,
  DiagnosticReport,
  DiagnosticSection,
  QuestionBankResponse,
} from "@/types/diagnostic";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";

const SECTION_META: Record<
  DiagnosticSection,
  { label: string; icon: React.ElementType; color: string; hint: string }
> = {
  reading: { label: "Reading", icon: BookOpen, color: "text-blue-500", hint: "Read carefully and choose the best answer." },
  listening: { label: "Listening", icon: Headphones, color: "text-teal-500", hint: "In the real test audio plays once. Focus on key details." },
  writing: { label: "Writing", icon: PenTool, color: "text-purple-500", hint: "Select the best answer based on IELTS writing criteria." },
  speaking: { label: "Speaking", icon: Mic, color: "text-orange-500", hint: "Choose the answer that best demonstrates fluency and range." },
  vocabulary: { label: "Vocabulary", icon: Keyboard, color: "text-emerald-500", hint: "Choose the most precise and appropriate word." },
  grammar: { label: "Grammar", icon: CheckCircle2, color: "text-rose-500", hint: "Select the grammatically correct option." },
};

const SECTION_ORDER: DiagnosticSection[] = [
  "reading",
  "listening",
  "writing",
  "speaking",
  "vocabulary",
  "grammar",
];

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
  if (band >= 3.5) return "A1";
  return "A1-";
}

export function DiagnosticTest() {
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Attempt state
  const [attempt, setAttempt] = useState<DiagnosticAttempt | null>(null);
  const [answeredIds, setAnsweredIds] = useState<string[]>([]);

  // Current section + questions
  const [section, setSection] = useState<DiagnosticSection>("reading");
  const [bank, setBank] = useState<QuestionBankResponse | null>(null);
  const [questionIndex, setQuestionIndex] = useState(0);

  // Answers storage: questionId -> selected answer
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  // Time tracking
  const [elapsed, setElapsed] = useState(0);
  const [sectionStartSec, setSectionStartSec] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Report
  const [report, setReport] = useState<DiagnosticReport | null>(null);

  const currentQuestion: DiagnosticQuestion | undefined = bank?.questions?.[questionIndex];

  // ------------------------------------------------------------------
  // Timer
  // ------------------------------------------------------------------
  useEffect(() => {
    if (attempt && attempt.status === "in_progress" && !report) {
      timerRef.current = setInterval(() => {
        setElapsed((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
}, [attempt, report]);

// ------------------------------------------------------------------
  // Load section questions
  // ------------------------------------------------------------------
  const loadSection = useCallback(async (sec: DiagnosticSection) => {
    try {
      const b = await diagnosticService.getQuestions(sec);
      setBank(b);
      setQuestionIndex(0);
      setSection(sec);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load questions.");
    }
  }, []);

  // ------------------------------------------------------------------
  // Start / resume
  // ------------------------------------------------------------------
  const startOrResume = useCallback(async () => {
    setStarting(true);
    setError(null);
    try {
      const res = await diagnosticService.startAttempt();
      const a = res.attempt as DiagnosticAttempt;
      setAttempt(a);
      setSection((a.current_section as DiagnosticSection) || "reading");
      setElapsed(Number(a.total_seconds_spent) || 0);
      setSectionStartSec(Number(a.total_seconds_spent) || 0);
      // Load resumed answered ids
      if (a.id) {
        try {
          const resume = await diagnosticService.getAttempt(a.id);
          setAnsweredIds(resume.answered_question_ids || []);
        } catch {
          setAnsweredIds([]);
        }
      }
      await loadSection((a.current_section as DiagnosticSection) || "reading");
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to start diagnostic.");
    } finally {
      setStarting(false);
      setLoading(false);
    }
  }, [loadSection]);

  useEffect(() => {
    if (typeof startOrResume === "function") {
      startOrResume();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------------
  // Answer submission
  // ------------------------------------------------------------------
  const submitCurrentAnswer = useCallback(
    async (questionId: string, answer: string, sec: DiagnosticSection) => {
      if (!attempt) return;
      setSubmitting(questionId);
      try {
        const timeTaken = Math.max(1, sectionStartSec > 0 ? elapsed - sectionStartSec : elapsed);
        await diagnosticService.submitAnswer(attempt.id, {
          section: sec,
          question_id: questionId,
          answer,
          time_taken_seconds: timeTaken,
        });
        setSectionStartSec(elapsed);
        setAnsweredIds((prev) => (prev.includes(questionId) ? prev : [...prev, questionId]));
      } catch (e: any) {
        setError(e?.response?.data?.detail?.message || e?.message || "Failed to save answer.");
      } finally {
        setSubmitting(null);
      }
    },
    [attempt, elapsed, sectionStartSec]
  );

  const handleSelectOption = async (question: DiagnosticQuestion, option: string) => {
    setAnswers((prev) => ({ ...prev, [question.id]: option }));
    await submitCurrentAnswer(question.id, option, question.section as DiagnosticSection);
  };

  const handleNext = () => {
    if (!bank) return;
    if (questionIndex < bank.questions.length - 1) {
      setQuestionIndex((i) => i + 1);
    } else {
      completeSection();
    }
  };

  const handlePrev = () => {
    if (questionIndex > 0) setQuestionIndex((i) => i - 1);
  };

  // ------------------------------------------------------------------
  // Section completion
  // ------------------------------------------------------------------
  const completeSection = useCallback(async () => {
    if (!attempt) return;
    setSubmitting("__section__");
    try {
      const sectionTime = Math.max(0, elapsed - sectionStartSec);
      const res = await diagnosticService.completeSection(attempt.id, {
        section,
        time_taken_seconds: sectionTime,
      });
      const next = (res.current_section as DiagnosticSection) || null;
      if (res.attempt_completed || !next) {
        // All sections done -> complete attempt
        const rep = await diagnosticService.completeAttempt(attempt.id);
        setReport(rep);
        setBank(null);
      } else {
        setSectionStartSec(elapsed);
        await loadSection(next);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to complete section.");
    } finally {
      setSubmitting(null);
    }
  }, [attempt, elapsed, section, sectionStartSec, loadSection]);

  const finishAttempt = useCallback(async () => {
    if (!attempt) return;
    setSubmitting("__finish__");
    try {
      const rep = await diagnosticService.completeAttempt(attempt.id);
      setReport(rep);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to compute report.");
    } finally {
      setSubmitting(null);
    }
  }, [attempt]);

  // ------------------------------------------------------------------
  // Renderers
  // ------------------------------------------------------------------
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4">
        <Spinner size="lg" />
        <p className="text-muted-foreground">Preparing your diagnostic...</p>
      </div>
    );
  }

// Report view
  if (report) {
    const cefr = cefrFromBand(Number(report.overall_band) || 0);
    return (
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        <div className="text-center space-y-3">
          <Badge variant="success" className="px-4 py-1">Assessment Complete</Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">Your Diagnostic Report</h1>
          <p className="text-muted-foreground">Estimated current IELTS level based on your performance.</p>
        </div>

        <Card className="bg-gradient-to-br from-primary to-blue-700 text-white border-none shadow-xl">
          <CardContent className="py-10 flex flex-col items-center text-center">
            <div className="flex items-center gap-8">
              <div className="flex flex-col items-center">
                <span className="text-6xl font-black">{Number(report.overall_band).toFixed(1)}</span>
                <span className="mt-2 text-sm uppercase tracking-widest text-white/70">Overall Band</span>
              </div>
              <div className="h-16 w-px bg-white/20" />
              <div className="flex flex-col items-center">
                <span className="text-6xl font-black">{cefr}</span>
                <span className="mt-2 text-sm uppercase tracking-widest text-white/70">CEFR Level</span>
              </div>
            </div>
            <p className="mt-6 text-sm text-white/80 max-w-md">
              Total time spent: {formatTime(report.total_time_seconds || 0)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6 space-y-6">
            <h3 className="font-bold text-lg">Skill Breakdown</h3>
            {report.skill_scores?.map((s) => (
              <div key={s.section} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="capitalize font-medium">{s.section}</span>
                  <span className="font-bold">Band {Number(s.band).toFixed(1)}</span>
                </div>
                <Progress value={(Number(s.band) / 9) * 100} variant="accent" className="h-3" />
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardContent className="pt-6">
              <h3 className="font-semibold text-success mb-3">Strengths</h3>
              <ul className="space-y-2">
                {(report.strengths?.length ? report.strengths : ["Complete more sections to see strengths."]).map((s, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-success" /> {s}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <h3 className="font-semibold text-error mb-3">Areas for Growth</h3>
              <ul className="space-y-2">
                {(report.weaknesses?.length ? report.weaknesses : ["No weaknesses detected yet."]).map((w, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-error" /> {w}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col items-center gap-4 pt-4 border-t border-border">
          <p className="text-sm text-muted-foreground">Use this baseline to generate your personalized study plan.</p>
          <div className="flex gap-4">
            <Button variant="outline" onClick={() => { setReport(null); setAttempt(null); setBank(null); setAnswers({}); setAnsweredIds([]); startOrResume(); }}>
              <RotateCcw className="mr-2 h-4 w-4" /> Retake Diagnostic
            </Button>
            <Link href="/roadmap">
              <Button className="bg-accent hover:bg-accent/90">
                Generate My Study Roadmap <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Section intro / between sections
  if (!bank || !currentQuestion) {
    const meta = SECTION_META[section];
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-6">
        <div className={`mx-auto p-4 rounded-2xl bg-secondary w-fit ${meta.color}`}>
          <meta.icon className="h-12 w-12" />
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight">{meta.label} Section</h1>
        <p className="text-muted-foreground">{meta.hint}</p>
        <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <Clock className="h-4 w-4" /> 
          {bank?.questions?.length ? `${bank.questions.length} questions` : "Loading questions..."}
        </div>
        <Button size="lg" onClick={() => bank && setQuestionIndex(0)} disabled={!bank || !!submitting}>
          <Play className="mr-2 h-5 w-5" /> Start Section
        </Button>
      </div>
    );
  }

  // Question view
  const meta = SECTION_META[section];
  const progressVal = bank.questions.length
    ? ((questionIndex + (answers[currentQuestion.id] ? 1 : 0)) / bank.questions.length) * 100
    : 0;
  const selected = answers[currentQuestion.id];

  return (
    <div className="max-w-3xl mx-auto space-y-6 py-4">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <meta.icon className={`h-5 w-5 ${meta.color}`} />
          <span className="font-semibold">{meta.label}</span>
        </div>
        <Badge variant="accent" className="flex items-center gap-1">
          <Clock className="h-3 w-3" /> {formatTime(elapsed)}
        </Badge>
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Question {questionIndex + 1} of {bank.questions.length}</span>
          <span>{answeredIds.length} saved</span>
        </div>
        <Progress value={progressVal} className="h-2" />
      </div>

      {error && (
        <div className="rounded-lg border border-error/30 bg-error/5 p-3 text-sm text-error flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Question card */}
      <Card className="border-primary/20">
        <CardContent className="pt-6 space-y-6">
          <p className="text-lg font-medium leading-relaxed">{currentQuestion.prompt}</p>

          {currentQuestion.options?.length ? (
            <div className="space-y-3">
              {currentQuestion.options.map((opt, idx) => {
                const isSelected = selected === opt;
                return (
                  <button
                    key={idx}
                    disabled={!!submitting}
                    onClick={() => handleSelectOption(currentQuestion, opt)}
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
          ) : (
            <p className="text-sm text-muted-foreground">Write your answer below.</p>
          )}

          {submitting === currentQuestion.id && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner size="sm" /> Saving answer...
            </div>
          )}
          {selected && submitting !== currentQuestion.id && (
            <p className="flex items-center gap-2 text-sm text-success">
              <CheckCircle2 className="h-4 w-4" /> Answer saved. Your progress is auto-saved.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Nav buttons */}
      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={handlePrev} disabled={questionIndex === 0}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Previous
        </Button>
        <Button variant="outline" onClick={() => { setError(null); startOrResume(); }}>
          <Save className="mr-2 h-4 w-4" /> Save & Exit
        </Button>
        <Button onClick={handleNext} disabled={!selected || !!submitting}>
          {questionIndex === bank.questions.length - 1 ? "Finish Section" : "Next"}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>

      {questionIndex === bank.questions.length - 1 && (
        <button onClick={finishAttempt} className="mx-auto block text-sm text-muted-foreground underline hover:text-primary">
          Skip remaining sections and get my report
        </button>
      )}
    </div>
  );
}
