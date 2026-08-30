"use client";

import React, { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Award, CheckCircle2, Clock, Headphones, X } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { listeningDiagnosticService } from "@/services/listening-diagnostic";
import type { ListeningReport, ListeningQuestionType, ListeningTypeBreakdown } from "@/types/listening-diagnostic";
import { LISTENING_QUESTION_TYPE_LABELS } from "@/types/listening-diagnostic";

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

export default function ListeningReportPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center text-muted-foreground">Loading...</div>}>
      <ListeningReportContent />
    </Suspense>
  );
}

function ListeningReportContent() {
  const searchParams = useSearchParams();
  const attemptId = searchParams.get("attempt_id");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ListeningReport | null>(null);

  const load = useCallback(async () => {
    if (!attemptId) {
      setError("Missing attempt_id parameter.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rep = await listeningDiagnosticService.getReport(attemptId);
      setReport(rep);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load listening report.");
    } finally {
      setLoading(false);
    }
  }, [attemptId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6 py-4">
        <div className="flex items-center justify-between">
          <Link href="/diagnostic/listening/results" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Results
          </Link>
          <Badge variant="accent" className="px-4 py-1">Stored Report</Badge>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <Spinner size="lg" />
            <p className="text-muted-foreground">Loading your listening report...</p>
          </div>
        ) : error ? (
          <Card>
            <CardContent className="py-16 text-center space-y-4">
              <Headphones className="h-12 w-12 mx-auto text-muted-foreground/40" />
              <p className="text-sm text-error">{error}</p>
              <Link href="/diagnostic/listening">
                <Button variant="outline">Back to Listening Overview</Button>
              </Link>
            </CardContent>
          </Card>
        ) : report ? (
          <div className="space-y-6">
            <div className="text-center space-y-3">
              <Badge variant="success" className="px-4 py-1">Listening Assessment Complete</Badge>
              <h1 className="text-3xl font-extrabold tracking-tight">Your Listening Report</h1>
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
                  <Badge className="bg-white/20 text-white border-white/30">{cefrFromBand(Number(report.listening_band) || 0)}</Badge>
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

            <Card>
              <CardContent className="pt-6 space-y-6">
                <h3 className="font-bold text-lg">Question Type Breakdown</h3>
                {(report.type_breakdown || []).length === 0 && (
                  <p className="text-sm text-muted-foreground">No question-type data available.</p>
                )}
                {(report.type_breakdown || []).map((td: ListeningTypeBreakdown) => (
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
          </div>
        ) : null}
      </div>
    </DashboardLayout>
  );
}
