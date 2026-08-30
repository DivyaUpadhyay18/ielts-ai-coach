"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Clock, FileText, History, PenTool, Award } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { writingDiagnosticService } from "@/services/writing-diagnostic";
import type { WritingEssay, WritingTaskType } from "@/types/writing-diagnostic";
import { WRITING_TASK_LABELS } from "@/types/writing-diagnostic";

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

export default function WritingResultsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<WritingEssay[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await writingDiagnosticService.listEssays(50);
      setResults(res.results || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load writing essays.");
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
        <div className="flex items-center justify-between">
          <Link href="/diagnostic/writing" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Writing Overview
          </Link>
          <Badge variant="accent" className="px-4 py-1">History</Badge>
        </div>

        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-bold">Writing Diagnostic Results</h1>
        </div>

        {error && (
          <div className="rounded-lg border border-error/30 bg-error/5 p-3 text-sm text-error">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <Spinner size="lg" />
            <p className="text-muted-foreground">Loading your essays...</p>
          </div>
        ) : results.length === 0 ? (
          <Card>
            <CardContent className="py-16 flex flex-col items-center text-center gap-4">
              <div className="p-4 rounded-2xl bg-secondary w-fit text-blue-500">
                <PenTool className="h-12 w-12" />
              </div>
              <h2 className="text-xl font-bold">No writing essays yet</h2>
              <p className="text-sm text-muted-foreground max-w-md">
                Complete a writing diagnostic to see your saved essays, word counts, and manual scores.
              </p>
              <Link href="/diagnostic/writing/test">
                <Button className="mt-2">Start Writing Diagnostic</Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {results.map((r) => {
              const overall = r.overall_band != null ? Number(r.overall_band) : null;
              return (
                <Card key={r.id} className="hover:shadow-md transition-shadow">
                  <CardContent className="pt-6">
                    <div className="flex flex-col md:flex-row md:items-center gap-4 md:justify-between mb-4">
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          <Award className="h-8 w-8 text-blue-500" />
                          <div>
                            <p className="text-2xl font-black">
                              {overall != null ? Number(overall).toFixed(1) : "—"}
                            </p>
                            <p className="text-xs uppercase tracking-widest text-muted-foreground">Band</p>
                          </div>
                        </div>
                        <div className="h-10 w-px bg-border" />
                        <div>
                          <p className="text-2xl font-black">{r.word_count}</p>
                          <p className="text-xs uppercase tracking-widest text-muted-foreground">Words</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{WRITING_TASK_LABELS[r.task_type]}</Badge>
                        <Badge variant="secondary" className="flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {formatTime(r.time_seconds_spent || 0)}
                        </Badge>
                        <Badge variant={overall != null ? "success" : "outline"}>
                          {overall != null ? "Scored" : "Unscored"}
                        </Badge>
                        <Badge variant="outline">{formatDate(r.completed_at || r.created_at)}</Badge>
                      </div>
                    </div>

                    <p className="text-sm font-semibold mb-1">{r.title || "Untitled essay"}</p>
                    <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{r.essay_text}</p>

                    <div className="mt-4 pt-3 border-t border-border">
                      <Link href={`/diagnostic/writing/report?essay_id=${r.id}`} className="text-sm text-primary hover:underline">
                        View detailed report →
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
