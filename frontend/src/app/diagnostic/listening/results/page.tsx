"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Clock, Headphones, History, TrendingUp, Award } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { listeningDiagnosticService } from "@/services/listening-diagnostic";
import type { ListeningResultItem, ListeningQuestionType } from "@/types/listening-diagnostic";
import { LISTENING_QUESTION_TYPE_LABELS } from "@/types/listening-diagnostic";

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function ListeningResultsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ListeningResultItem[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listeningDiagnosticService.listResults(50);
      setResults(res.results || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load listening results.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6 py-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <Link href="/diagnostic/listening" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Listening Overview
          </Link>
          <Badge variant="accent" className="px-4 py-1">History</Badge>
        </div>

        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-bold">Listening Diagnostic Results</h1>
        </div>

        {error && (
          <div className="rounded-lg border border-error/30 bg-error/5 p-3 text-sm text-error">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <Spinner size="lg" />
            <p className="text-muted-foreground">Loading your listening results...</p>
          </div>
        ) : results.length === 0 ? (
          <Card>
            <CardContent className="py-16 flex flex-col items-center text-center gap-4">
              <div className="p-4 rounded-2xl bg-secondary w-fit text-teal-500">
                <Headphones className="h-12 w-12" />
              </div>
              <h2 className="text-xl font-bold">No listening results yet</h2>
              <p className="text-sm text-muted-foreground max-w-md">
                Complete a listening diagnostic to see your accuracy, weak question types, and estimated IELTS band.
              </p>
              <Link href="/diagnostic/listening/test">
                <Button className="mt-2">Start Listening Diagnostic</Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {results.map((r) => (
              <Card key={r.attempt_id} className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="flex flex-col md:flex-row md:items-center gap-4 md:justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <Award className="h-8 w-8 text-teal-500" />
                        <div>
                          <p className="text-2xl font-black">{Number(r.listening_band).toFixed(1)}</p>
                          <p className="text-xs uppercase tracking-widest text-muted-foreground">Band</p>
                        </div>
                      </div>
                      <div className="h-10 w-px bg-border" />
                      <div>
                        <p className="text-2xl font-black">{Math.round(r.accuracy)}%</p>
                        <p className="text-xs uppercase tracking-widest text-muted-foreground">Accuracy</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="secondary">{r.difficulty_level} difficulty</Badge>
                      <Badge variant="secondary" className="flex items-center gap-1">
                        <Clock className="h-3 w-3" /> {formatTime(r.total_time_seconds || 0)}
                      </Badge>
                      <Badge variant="outline">{formatDate(r.completed_at)}</Badge>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                    <TrendingUp className="h-3 w-3" />
                    <span>{r.correct_answers} of {r.total_questions} correct</span>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2 mt-2">
                    <div>
                      <p className="text-xs font-semibold text-error mb-1">Weak question types</p>
                      {r.weak_types?.length ? (
                        <div className="flex flex-wrap gap-1">
                          {r.weak_types.map((t) => (
                            <Badge key={t} variant="outline" className="text-error border-error/30">
                              {LISTENING_QUESTION_TYPE_LABELS[t as ListeningQuestionType] || t}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground">None detected 🎉</p>
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-success mb-1">Strong question types</p>
                      {r.strong_types?.length ? (
                        <div className="flex flex-wrap gap-1">
                          {r.strong_types.map((t) => (
                            <Badge key={t} variant="outline" className="text-success border-success/30">
                              {LISTENING_QUESTION_TYPE_LABELS[t as ListeningQuestionType] || t}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground">No strong types recorded</p>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-border">
                    <Link href={`/diagnostic/listening/report?attempt_id=${r.attempt_id}`} className="text-sm text-primary hover:underline">
                      View detailed report →
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
