"use client";

import React, { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Award, CheckCircle2, Clock, FileText, PenTool, Sparkles } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { writingDiagnosticService } from "@/services/writing-diagnostic";
import type { WritingCriterion, WritingEssay } from "@/types/writing-diagnostic";
import { WRITING_CRITERIA_LABELS, WRITING_TASK_LABELS } from "@/types/writing-diagnostic";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

const CRITERIA_KEYS: WritingCriterion[] = [
  "task_response",
  "coherence_cohesion",
  "lexical_resource",
  "grammatical_range",
];

export default function WritingReportPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center text-muted-foreground">Loading...</div>}>
      <WritingReportContent />
    </Suspense>
  );
}

function WritingReportContent() {
  const searchParams = useSearchParams();
  const essayId = searchParams.get("essay_id");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [essay, setEssay] = useState<WritingEssay | null>(null);

  const load = useCallback(async () => {
    if (!essayId) {
      setError("Missing essay_id parameter.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rep = await writingDiagnosticService.getReport(essayId);
      setEssay(rep.essay);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load writing report.");
    } finally {
      setLoading(false);
    }
  }, [essayId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6 py-4">
        <div className="flex items-center justify-between">
          <Link href="/diagnostic/writing/results" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Results
          </Link>
          <Badge variant="accent" className="px-4 py-1">Stored Essay</Badge>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <Spinner size="lg" />
            <p className="text-muted-foreground">Loading your writing report...</p>
          </div>
        ) : error ? (
          <Card>
            <CardContent className="py-16 text-center space-y-4">
              <FileText className="h-12 w-12 mx-auto text-muted-foreground/40" />
              <p className="text-sm text-error">{error}</p>
              <Link href="/diagnostic/writing">
                <Button variant="outline">Back to Writing Overview</Button>
              </Link>
            </CardContent>
          </Card>
        ) : essay ? (
          <div className="space-y-6">
            <div className="text-center space-y-3">
              <Badge variant="success" className="px-4 py-1">Writing Assessment</Badge>
              <h1 className="text-3xl font-extrabold tracking-tight">Your Writing Report</h1>
              <p className="text-muted-foreground">
                {WRITING_TASK_LABELS[essay.task_type]} — {essay.word_count} words · {formatTime(essay.time_seconds_spent)} spent
              </p>
            </div>

            <Card className="bg-gradient-to-br from-blue-600 to-indigo-700 text-white border-none shadow-xl">
              <CardContent className="py-10 flex flex-col items-center text-center">
                <div className="flex items-center gap-8">
                  <div className="flex flex-col items-center">
                    <span className="text-6xl font-black">
                      {essay.overall_band != null ? Number(essay.overall_band).toFixed(1) : "—"}
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
                  <Badge className="bg-white/20 text-white border-white/30">{WRITING_TASK_LABELS[essay.task_type]}</Badge>
                  <Badge className="bg-white/20 text-white border-white/30">
                    <Clock className="mr-1 h-3 w-3" /> {formatTime(essay.time_seconds_spent || 0)}
                  </Badge>
                  <Badge className="bg-white/20 text-white border-white/30">
                    {essay.overall_band != null ? "Manual Score" : "Unscored"}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6 space-y-6">
                <h3 className="font-bold text-lg">IELTS Marking Criteria</h3>
                {essay.overall_band == null && (
                  <p className="text-sm text-muted-foreground">
                    This essay has not been manually scored yet.
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

            <Card>
              <CardContent className="pt-6">
                <h3 className="font-bold text-lg mb-3">{essay.title || "Your Essay"}</h3>
                <p className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground">
                  {essay.essay_text}
                </p>
              </CardContent>
            </Card>

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

            <Card className="border-accent/30 bg-accent/5">
              <CardContent className="pt-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-lg flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-accent" /> AI Evaluation
                  </h3>
                  <Badge variant="outline">Coming soon</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {essay.ai_evaluation && (essay.ai_evaluation as any).feedback
                    ? (essay.ai_evaluation as any).feedback
                    : "AI evaluation placeholder. Connect an AI provider to enable automatic band assessment."}
                </p>
              </CardContent>
            </Card>
          </div>
        ) : null}
      </div>
    </DashboardLayout>
  );
}
