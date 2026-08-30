"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  RotateCcw,
  SpellCheck,
  Languages,
  X,
} from "lucide-react";
import { vocabGrammarDiagnosticService } from "@/services/vocab-grammar-diagnostic";
import { diagnosticService } from "@/services/diagnostic";
import type {
  VGBankResponse,
  VGQuestion,
  VGQuestionType,
  VGReport,
  VGTypeBreakdown,
} from "@/types/vocab-grammar-diagnostic";
import { VG_QUESTION_TYPE_LABELS, VG_VOCABULARY_TYPES } from "@/types/vocab-grammar-diagnostic";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";

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

const TYPE_COLORS: Record<string, string> = {
  fill_in_the_blanks: "text-blue-500",
  synonyms: "text-teal-500",
  antonyms: "text-rose-500",
  sentence_correction: "text-purple-500",
  grammar_correction: "text-orange-500",
  tenses: "text-emerald-500",
  articles: "text-amber-500",
  prepositions: "text-cyan-500",
};

export function VocabGrammarDiagnosticTest() {
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Attempt + bank
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [bank, setBank] = useState<VGBankResponse | null>(null);

  // Question navigation
  const [questionIds, setQuestionIds] = useState<string[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0);

  // Answers storage: questionId -> selected answer
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  // Time tracking
  const [elapsed, setElapsed] = useState(0);
  const [questionStartSec, setQuestionStartSec] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Report
  const [report, setReport] = useState<VGReport | null>(null);

  const currentQuestion = useMemo<VGQuestion | undefined>(() => {
    if (!bank || questionIndex < 0 || questionIndex >= questionIds.length) return undefined;
    const qid = questionIds[questionIndex];
    return bank.questions.find((q) => q.id === qid);
  }, [bank, questionIndex, questionIds]);

  // Timer
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

  // Load bank + start attempt
  const loadBank = useCallback(async () => {
    try {
      const b = await vocabGrammarDiagnosticService.getBank();
      setBank(b);
      setQuestionIds(b.questions.map((q) => q.id));
      setQuestionIndex(0);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load questions.");
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
      await loadBank();
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to start vocabulary & grammar diagnostic.");
    } finally {
      setStarting(false);
      setLoading(false);
    }
  }, [loadBank]);

  useEffect(() => {
    startOrResume();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Answer submission (auto-grade)
  const submitCurrentAnswer = useCallback(
    async (questionId: string, answer: string) => {
      if (!attemptId) return;
      setSubmitting(questionId);
      try {
        const timeTaken = Math.max(1, elapsed - questionStartSec);
        await vocabGrammarDiagnosticService.submitAnswer({
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

  const handleSelect = async (question: VGQuestion, option: string) => {
    setAnswers((prev) => ({ ...prev, [question.id]: option }));
    await submitCurrentAnswer(question.id, option);
  };

  const handleNext = () => {
    if (questionIndex < questionIds.length - 1) {
      setQuestionIndex((i) => i + 1);
    } else {
      finishTest();
    }
  };

  const handlePrev = () => {
    if (questionIndex > 0) setQuestionIndex((i) => i - 1);
  };

  // Complete + report
  const finishTest = useCallback(async () => {
    if (!attemptId) return;
    setSubmitting("__finish__");
    try {
      const rep = await vocabGrammarDiagnosticService.completeAttempt(attemptId);
      setReport(rep);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to compute report.");
    } finally {
      setSubmitting(null);
    }
  }, [attemptId]);

  // Renderers
  if (loading || starting) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4">
        <Spinner size="lg" />
        <p className="text-muted-foreground">Preparing your vocabulary &amp; grammar assessment...</p>
      </div>
    );
  }

  // Report view
  if (report) {
    const cefr = cefrFromBand(Number(report.band) || 0);
    const breakdown = report.type_breakdown || [];
    return (
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        <div className="text-center space-y-3">
          <Badge variant="success" className="px-4 py-1">Vocabulary &amp; Grammar Assessment Complete</Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">Your Report</h1>
          <p className="text-muted-foreground">Estimated current IELTS Vocabulary &amp; Grammar level based on your performance.</p>
        </div>

        <Card className="bg-gradient-to-br from-primary to-purple-700 text-white border-none shadow-xl">
          <CardContent className="py-10 flex flex-col items-center text-center">
            <div className="flex items-center gap-8">
              <div className="flex flex-col items-center">
                <span className="text-6xl font-black">{Number(report.band).toFixed(1)}</span>
                <span className="mt-2 text-sm uppercase tracking-widest text-white/70">Est. Band</span>
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
            <div className="mt-6 grid grid-cols-2 gap-6">
              <div className="flex flex-col items-center">
                <span className="text-3xl font-bold">{Math.round(report.grammar_accuracy)}%</span>
                <span className="mt-1 text-sm uppercase tracking-widest text-white/70">Grammar</span>
              </div>
              <div className="flex flex-col items-center">
                <span className="text-3xl font-bold">{Math.round(report.vocabulary_accuracy)}%</span>
                <span className="mt-1 text-sm uppercase tracking-widest text-white/70">Vocabulary</span>
              </div>
            </div>
            <p className="mt-4 text-sm text-white/80">
              {report.correct_answers} of {report.total_questions} correct
            </p>
          </CardContent>
        </Card>

        {/* Per-question-type breakdown */}
        <Card>
          <CardContent className="pt-6 space-y-6">
            <h3 className="font-bold text-lg">Topic Breakdown</h3>
            {breakdown.length === 0 && (
              <p className="text-sm text-muted-foreground">No topic data available.</p>
            )}
            {breakdown.map((td: VGTypeBreakdown) => (
              <div key={td.question_type} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">
                    {VG_QUESTION_TYPE_LABELS[td.question_type] || td.question_type}
                    <span className="ml-2 text-xs text-muted-foreground uppercase">
                      {td.section}
                    </span>
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
              <h3 className="font-semibold text-success mb-3">Strong Topics</h3>
              <ul className="space-y-2">
                {(report.strong_types?.length
                  ? report.strong_types
                  : ["Complete more questions to see your strengths."]
                ).map((w, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-success" />
                    {VG_QUESTION_TYPE_LABELS[w as VGQuestionType] || w}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-error mb-3">Weak Grammar Topics</h3>
                <ul className="space-y-2">
                  {(report.weak_grammar_topics?.length
                    ? report.weak_grammar_topics
                    : ["No weak grammar topics detected. Great job!"]
                  ).map((w, i) => (
                    <li key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                      <X className="h-4 w-4 text-error" />
                      {VG_QUESTION_TYPE_LABELS[w as VGQuestionType] || w}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-error mb-3">Weak Vocabulary Categories</h3>
                <ul className="space-y-2">
                  {(report.weak_vocab_categories?.length
                    ? report.weak_vocab_categories
                    : ["No weak vocabulary categories detected. Great job!"]
                  ).map((w, i) => (
                    <li key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                      <X className="h-4 w-4 text-error" />
                      {VG_QUESTION_TYPE_LABELS[w as VGQuestionType] || w}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="flex flex-col items-center gap-4 pt-4 border-t border-border">
          <p className="text-sm text-muted-foreground">Use this baseline to focus your vocabulary and grammar practice.</p>
          <div className="flex gap-4">
            <Button variant="outline" onClick={() => { setReport(null); setAttemptId(null); setBank(null); setAnswers({}); setQuestionIndex(0); startOrResume(); }}>
              <RotateCcw className="mr-2 h-4 w-4" /> Retake Assessment
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
    const vocabCount = (bank?.questions || []).filter((q) => q.section === "vocabulary").length;
    const grammarCount = (bank?.questions || []).filter((q) => q.section === "grammar").length;
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-6">
        <div className="mx-auto p-4 rounded-2xl bg-secondary w-fit text-purple-500">
          <SpellCheck className="h-12 w-12" />
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight">Vocabulary &amp; Grammar Diagnostic</h1>
        <p className="text-muted-foreground">
          Answer questions covering fill-in-the-blanks, synonyms, antonyms, sentence correction,
          tenses, articles, and prepositions. Get instant accuracy, weak-topic analysis, and an
          estimated band.
        </p>
        <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <Languages className="h-4 w-4" />
          {bank?.questions?.length
            ? `${bank.questions.length} questions · ${vocabCount} vocabulary · ${grammarCount} grammar`
            : "Loading questions..."}
        </div>
        <Button size="lg" onClick={() => bank && setQuestionIndex(0)} disabled={!bank || !!submitting}>
          Start Assessment
        </Button>
      </div>
    );
  }

  // Question view
  const selected = answers[currentQuestion.id] || "";
  const progressVal = questionIds.length ? ((questionIndex + 1) / questionIds.length) * 100 : 0;
  const typeLabel = VG_QUESTION_TYPE_LABELS[currentQuestion.question_type] || currentQuestion.question_type;
  const isVocab = VG_VOCABULARY_TYPES.includes(currentQuestion.question_type);

  return (
    <div className="max-w-4xl mx-auto space-y-6 py-4">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          {isVocab ? (
            <BookOpen className={`h-5 w-5 ${TYPE_COLORS[currentQuestion.question_type]}`} />
          ) : (
            <Languages className={`h-5 w-5 ${TYPE_COLORS[currentQuestion.question_type]}`} />
          )}
          <span className="font-semibold">{typeLabel}</span>
          <Badge variant="secondary" className="uppercase text-xs">{currentQuestion.section}</Badge>
        </div>
        <Badge variant="accent" className="flex items-center gap-1">
          <Clock className="h-3 w-3" /> {formatTime(elapsed)}
        </Badge>
      </div>

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

      <Card className="border-primary/20">
        <CardContent className="pt-6 space-y-5">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={TYPE_COLORS[currentQuestion.question_type]}>
              {typeLabel}
            </Badge>
            <Badge variant="secondary">Difficulty {currentQuestion.difficulty}</Badge>
          </div>
          <p className="text-lg font-medium leading-relaxed">{currentQuestion.prompt}</p>

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
        <button onClick={finishTest} className="mx-auto block text-sm text-muted-foreground underline hover:text-primary">
          Finish and get my report
        </button>
      )}
    </div>
  );
}
