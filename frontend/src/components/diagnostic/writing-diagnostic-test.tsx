"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  FileText,
  PenTool,
  Save,
  Sparkles,
  Type,
  X,
} from "lucide-react";
import { writingDiagnosticService } from "@/services/writing-diagnostic";
import type {
  WritingCriterion,
  WritingEssay,
  WritingPrompt,
  WritingTaskType,
} from "@/types/writing-diagnostic";
import {
  WRITING_CRITERIA_LABELS,
  WRITING_TASK_LABELS,
} from "@/types/writing-diagnostic";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

function formatTime(totalSeconds: number): string {
  const m = Math.floor(Math.max(0, totalSeconds) / 60);
  const s = Math.max(0, totalSeconds) % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function countWords(text: string): number {
  if (!text.trim()) return 0;
  return text.trim().split(/\s+/).length;
}

const CRITERIA_KEYS: WritingCriterion[] = [
  "task_response",
  "coherence_cohesion",
  "lexical_resource",
  "grammatical_range",
];

export function WritingDiagnosticTest() {
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Prompt selection
  const [taskType, setTaskType] = useState<WritingTaskType>("task_2");
  const [prompts, setPrompts] = useState<WritingPrompt[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState<WritingPrompt | null>(null);

  // Essay state
  const [essay, setEssay] = useState<WritingEssay | null>(null);
  const [essayText, setEssayText] = useState("");
  const [wordCount, setWordCount] = useState(0);

  // Timer
  const [elapsed, setElapsed] = useState(0);
  const [timeLimit, setTimeLimit] = useState(2400);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-save
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [saving, setSaving] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);

  // Manual scoring
  const [scores, setScores] = useState<Record<WritingCriterion, string>>({
    task_response: "",
    coherence_cohesion: "",
    lexical_resource: "",
    grammatical_range: "",
  });
  const [scoring, setScoring] = useState(false);

  // AI scaffold
  const [aiResult, setAiResult] = useState<Record<string, unknown> | null>(null);
  const [aiRunning, setAiRunning] = useState(false);

  // ------------------------------------------------------------------
  // Load prompts
  // ------------------------------------------------------------------
  const loadPrompts = useCallback(async (tt: WritingTaskType) => {
    try {
      const res = await writingDiagnosticService.getPrompts(tt);
      setPrompts(res.prompts || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load writing prompts.");
    }
  }, []);

  useEffect(() => {
    loadPrompts(taskType);
  }, [taskType, loadPrompts]);

  useEffect(() => {
    setLoading(false);
  }, []);

  // ------------------------------------------------------------------
  // Start essay + resume
  // ------------------------------------------------------------------
  const startEssay = useCallback(async (prompt: WritingPrompt) => {
    setStarting(true);
    setError(null);
    try {
      const res = await writingDiagnosticService.startEssay({ prompt_id: prompt.id });
      setEssay(res);
      setEssayText(res.essay_text || "");
      setWordCount(Number(res.word_count) || countWords(res.essay_text || ""));
      setElapsed(Number(res.time_seconds_spent) || 0);
      setTimeLimit(Number(prompt.time_limit_seconds) || 2400);
      setSelectedPrompt(prompt);
      setLastSavedAt(res.saved_at || null);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to start writing essay.");
    } finally {
      setStarting(false);
    }
  }, []);

  // ------------------------------------------------------------------
  // Timer
  // ------------------------------------------------------------------
  useEffect(() => {
    if (essay && essay.status === "in_progress") {
      timerRef.current = setInterval(() => {
        setElapsed((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [essay]);

  const remaining = Math.max(0, timeLimit - elapsed);

  // ------------------------------------------------------------------
  // Auto-save (debounced)
  // ------------------------------------------------------------------
  const persistSave = useCallback(
    async (text: string, seconds: number) => {
      if (!essay) return;
      setSaving(true);
      try {
        const updated = await writingDiagnosticService.autoSave(essay.id, {
          essay_text: text,
          time_seconds_spent: seconds,
        });
        setLastSavedAt(updated.saved_at || new Date().toISOString());
      } catch (e: any) {
        setError(e?.response?.data?.detail?.message || e?.message || "Auto-save failed.");
      } finally {
        setSaving(false);
      }
    },
    [essay]
  );

  const handleTextChange = (value: string) => {
    setEssayText(value);
    setWordCount(countWords(value));
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      persistSave(value, elapsed);
    }, 1200);
  };

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  // ------------------------------------------------------------------
  // Complete essay
  // ------------------------------------------------------------------
  const completeEssay = useCallback(async () => {
    if (!essay) return;
    setSaving(true);
    try {
      // Final save before completing.
      await writingDiagnosticService.autoSave(essay.id, {
        essay_text: essayText,
        time_seconds_spent: elapsed,
      });
      const updated = await writingDiagnosticService.completeEssay(essay.id, {
        time_seconds_spent: elapsed,
      });
      setEssay(updated);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to complete essay.");
    } finally {
      setSaving(false);
    }
  }, [essay, essayText, elapsed]);

  // ------------------------------------------------------------------
  // Manual scoring
  // ------------------------------------------------------------------
  const canScore = CRITERIA_KEYS.every((k) => {
    const v = Number(scores[k]);
    return v >= 0 && v <= 9;
  });

  const submitManualScore = useCallback(async () => {
    if (!essay || !canScore) return;
    setScoring(true);
    try {
      const updated = await writingDiagnosticService.submitManualScore(essay.id, {
        task_response: Number(scores.task_response),
        coherence_cohesion: Number(scores.coherence_cohesion),
        lexical_resource: Number(scores.lexical_resource),
        grammatical_range: Number(scores.grammatical_range),
      });
      setEssay(updated);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to save scores.");
    } finally {
      setScoring(false);
    }
  }, [essay, scores, canScore]);

  // ------------------------------------------------------------------
  // AI evaluation scaffold
  // ------------------------------------------------------------------
  const runAiEvaluate = useCallback(async () => {
    if (!essay) return;
    setAiRunning(true);
    setError(null);
    try {
      const updated = await writingDiagnosticService.aiEvaluate(essay.id);
      setEssay(updated);
      setAiResult(updated.ai_evaluation || {});
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "AI evaluation unavailable.");
    } finally {
      setAiRunning(false);
    }
  }, [essay]);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  if (loading || starting) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4">
        <Spinner size="lg" />
        <p className="text-muted-foreground">Preparing your writing assessment...</p>
      </div>
    );
  }

  // Report / completed view
  if (essay && essay.status === "completed") {
    const overall = essay.overall_band != null ? Number(essay.overall_band) : null;
    return (
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        <div className="text-center space-y-3">
          <Badge variant="success" className="px-4 py-1">Writing Assessment Complete</Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">Your Writing Report</h1>
          <p className="text-muted-foreground">
            {WRITING_TASK_LABELS[essay.task_type]} — {essay.word_count} words · {formatTime(essay.time_seconds_spent)} spent
          </p>
        </div>

        <Card className="bg-gradient-to-br from-blue-600 to-indigo-700 text-white border-none shadow-xl">
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
                <span className="text-6xl font-black">{essay.word_count}</span>
                <span className="mt-2 text-sm uppercase tracking-widest text-white/70">Words</span>
              </div>
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              <Badge className="bg-white/20 text-white border-white/30">
                <Type className="mr-1 h-3 w-3" /> {WRITING_TASK_LABELS[essay.task_type]}
              </Badge>
              <Badge className="bg-white/20 text-white border-white/30">
                <Clock className="mr-1 h-3 w-3" /> {formatTime(essay.time_seconds_spent)}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* Criteria breakdown */}
        <Card>
          <CardContent className="pt-6 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-lg">IELTS Marking Criteria</h3>
              {overall != null && (
                <Badge variant="accent">Manually scored</Badge>
              )}
            </div>
            {!essay.overall_band && (
              <p className="text-sm text-muted-foreground">
                This essay has not been manually scored yet. Use the scoring panel below.
              </p>
            )}
            {CRITERIA_KEYS.map((key) => {
              const val = essay[key] != null ? Number(essay[key]) : null;
              return (
                <div key={key} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{WRITING_CRITERIA_LABELS[key]}</span>
                    <span className="font-bold">{val != null ? val.toFixed(1) : "—"}</span>
                  </div>
                  <Progress value={val != null ? (val / 9) * 100 : 0} className="h-3" />
                </div>
              );
            })}
          </CardContent>
        </Card>

        {/* Essay body */}
        <Card>
          <CardContent className="pt-6">
            <h3 className="font-bold text-lg mb-3">{essay.title || "Your Essay"}</h3>
            <p className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground">
              {essay.essay_text}
            </p>
          </CardContent>
        </Card>

        {/* Grammar / Vocabulary placeholders */}
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardContent className="pt-6">
              <h3 className="font-semibold text-primary mb-3">Grammar Feedback</h3>
              <p className="text-sm text-muted-foreground">
                {essay.grammar_feedback && (essay.grammar_feedback as any).summary
                  ? (essay.grammar_feedback as any).summary
                  : "Grammar feedback placeholder — connect an AI provider to enable analysis."}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <h3 className="font-semibold text-accent-foreground mb-3">Vocabulary Feedback</h3>
              <p className="text-sm text-muted-foreground">
                {essay.vocabulary_feedback && (essay.vocabulary_feedback as any).summary
                  ? (essay.vocabulary_feedback as any).summary
                  : "Vocabulary feedback placeholder — connect an AI provider to enable analysis."}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Manual scoring panel (always available for completed unscored essays) */}
        {!essay.overall_band && (
          <Card className="border-primary/30">
            <CardContent className="pt-6 space-y-5">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <PenTool className="h-5 w-5 text-primary" /> Manual Scoring
              </h3>
              <p className="text-sm text-muted-foreground">
                Score each criterion 0–9 (in 0.5 steps). The overall band is averaged automatically.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                {CRITERIA_KEYS.map((key) => (
                  <div key={key} className="space-y-1">
                    <label className="text-sm font-medium">{WRITING_CRITERIA_LABELS[key]}</label>
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
          <p className="text-sm text-muted-foreground">Your essay is saved. Use this baseline to focus your writing practice.</p>
          <div className="flex gap-4">
            <Link href="/diagnostic/writing">
              <Button className="bg-accent hover:bg-accent/90">
                Back to Writing Diagnostics <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Prompt selection view
  if (!essay) {
    return (
      <div className="max-w-3xl mx-auto space-y-6 py-4">
        <div className="text-center space-y-3">
          <Badge variant="accent" className="px-4 py-1">Writing Diagnostic</Badge>
          <h1 className="text-3xl font-extrabold tracking-tight">Choose a Writing Task</h1>
          <p className="text-muted-foreground">
            Select a task type, then pick a prompt to begin. Your essay is auto-saved as you type.
          </p>
        </div>

        {/* Task type selector */}
        <div className="flex items-center justify-center gap-3">
          <Button
            variant={taskType === "task_1" ? "default" : "outline"}
            onClick={() => setTaskType("task_1")}
          >
            Task 1 — Report
          </Button>
          <Button
            variant={taskType === "task_2" ? "default" : "outline"}
            onClick={() => setTaskType("task_2")}
          >
            Task 2 — Essay
          </Button>
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
                No prompts available for this task type yet.
              </CardContent>
            </Card>
          )}
          {prompts.map((p) => (
            <Card key={p.id} className="border-primary/20 hover:shadow-md transition-shadow">
              <CardContent className="pt-6 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="accent">{WRITING_TASK_LABELS[p.task_type]}</Badge>
                  <Badge variant="secondary">≥ {p.word_limit} words</Badge>
                  <Badge variant="secondary">{formatTime(p.time_limit_seconds)}</Badge>
                  <Badge variant="outline">Difficulty {p.difficulty}</Badge>
                </div>
                <h3 className="font-bold text-lg">{p.title}</h3>
                <p className="text-sm text-muted-foreground whitespace-pre-line">{p.prompt_text}</p>
                <Button onClick={() => startEssay(p)} disabled={starting}>
                  {starting ? <Spinner size="sm" /> : <PenTool className="mr-2 h-4 w-4" />}
                  Start Writing
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Editor view
  const wordTarget = Number(selectedPrompt?.word_limit) || (essay.task_type === "task_1" ? 150 : 250);
  const metWordCount = wordCount >= wordTarget;
  const progressPct = Math.min(100, (wordCount / Math.max(1, wordTarget)) * 100);

  return (
    <div className="flex flex-col gap-6">
      {/* Top control bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg text-primary">
            <FileText className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{selectedPrompt?.title || essay.title}</h1>
            <p className="text-sm text-muted-foreground">{WRITING_TASK_LABELS[essay.task_type]}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 px-4 py-2 bg-secondary rounded-full font-mono text-lg font-bold ${remaining < 300 ? "text-error" : ""}`}>
            <Clock className="h-5 w-5 text-primary" /> {formatTime(remaining)}
          </div>
          <Button onClick={completeEssay} disabled={saving}>
            {saving ? <Spinner size="sm" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            Submit Essay
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-error/30 bg-error/5 p-3 text-sm text-error flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6 flex-1 overflow-hidden">
        {/* Prompt panel */}
        <Card className="flex flex-col overflow-hidden">
          <CardContent className="flex-1 overflow-y-auto pt-6 space-y-4">
            <div className="flex items-center justify-between">
              <Badge variant="accent">{WRITING_TASK_LABELS[essay.task_type]}</Badge>
              <Badge variant="secondary">{formatTime(essay.time_seconds_spent)} elapsed</Badge>
            </div>
            <div className="prose prose-slate dark:prose-invert">
              <p className="text-lg font-medium leading-relaxed whitespace-pre-line">
                {selectedPrompt?.prompt_text}
              </p>
            </div>
            <div className="space-y-2 pt-4 border-t border-border">
              <h4 className="text-sm font-bold flex items-center gap-2">
                <PenTool className="h-4 w-4 text-primary" /> Instructions
              </h4>
              <ul className="text-sm text-muted-foreground space-y-1.5">
                <li>• Write at least {wordTarget} words.</li>
                <li>• Use a formal academic style.</li>
                <li>• Support your arguments with examples.</li>
                <li>• {"Timer: "}{formatTime(timeLimit)} recommended.</li>
              </ul>
            </div>
          </CardContent>
        </Card>

        {/* Editor panel */}
        <Card className="flex flex-col overflow-hidden border-2 border-primary/20">
          <div className="border-b border-border px-4 py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Type className="h-4 w-4 text-muted-foreground" />
              <span className={metWordCount ? "text-success" : "text-warning"}>
                {wordCount} / {wordTarget} words
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Save className="h-3 w-3" />
              <span>{saving ? "Saving..." : lastSavedAt ? "Saved" : "Not saved"}</span>
            </div>
          </div>
          <div className="px-4 pt-3">
            <Progress value={progressPct} className="h-2" />
          </div>
          <CardContent className="p-0 flex-1 relative">
            <Textarea
              className="h-full w-full border-none rounded-none p-6 text-lg leading-relaxed focus-visible:ring-0 resize-none bg-transparent"
              placeholder="Type your essay here. It is saved automatically..."
              value={essayText}
              onChange={(e) => handleTextChange(e.target.value)}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
