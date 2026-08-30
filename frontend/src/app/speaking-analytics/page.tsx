"use client";

import React, { useState, useEffect } from "react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Calendar, TrendingUp, Target, BarChart3, Clock, AlertCircle, CheckCircle2 } from "lucide-react";
import { speakingAnalyticsService } from "@/services/api";
import type { SpeakingAnalyticsDashboardResponse } from "@/types/speaking-test";

export default function SpeakingAnalyticsPage() {
  const [dashboard, setDashboard] = useState<SpeakingAnalyticsDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(90);
  const [part, setPart] = useState<string | undefined>(undefined);

  useEffect(() => {
    setLoading(true);
    setError(null);
    speakingAnalyticsService.getDashboard(days, part)
      .then((data) => {
        setDashboard(data);
        setLoading(false);
      })
      .catch((err: any) => {
        setError(err?.message || "Failed to load analytics");
        setLoading(false);
      });
  }, [days, part]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="p-6">
          <div className="text-center py-8 text-muted-foreground">Loading analytics...</div>
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="p-6">
          <div className="text-destructive">Error: {error}</div>
        </div>
      </DashboardLayout>
    );
  }

  if (!dashboard) {
    return (
      <DashboardLayout>
        <div className="p-6">
          <div className="text-center py-8 text-muted-foreground">No speaking data available yet.</div>
        </div>
      </DashboardLayout>
    );
  }

  const { metrics, band_history, common_errors, strongest_criterion, weakest_criterion,
    improvement_rate, attempt_history, total_evaluations } = dashboard;

  const getTrendColor = (trend: string) => {
    if (trend === "improving") return "text-green-500";
    if (trend === "declining") return "text-red-500";
    return "text-muted-foreground";
  };

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Speaking Progress Analytics</h1>
            <p className="text-sm text-muted-foreground">
              Track your IELTS Speaking improvement over time
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="border border-border rounded px-2 py-1 text-sm"
            >
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={180}>Last 180 days</option>
              <option value={365}>Last year</option>
            </select>
            <select
              value={part || "all"}
              onChange={(e) => setPart(e.target.value || undefined)}
              className="border border-border rounded px-2 py-1 text-sm"
            >
              <option value="all">All Parts</option>
              <option value="part_1">Part 1</option>
              <option value="part_2">Part 2</option>
              <option value="part_3">Part 3</option>
            </select>
          </div>
        </div>

        {/* Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Average Band</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{metrics.average_band ?? "N/A"}</div>
              <p className="text-xs text-muted-foreground">{total_evaluations} evaluations</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Strongest</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metrics.strongest_criterion_label || "N/A"}</div>
              <p className="text-xs text-muted-foreground">
                {metrics.strongest_criterion ? String((metrics as unknown as Record<string, unknown>)[`average_${metrics.strongest_criterion}_band`] ?? "") : ""}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Weakest</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-destructive">{metrics.weakest_criterion_label || "N/A"}</div>
              <p className="text-xs text-muted-foreground">
                Focus here to improve overall
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Trend</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${getTrendColor(improvement_rate.trend)}`}>
                {improvement_rate.trend === "improving" ? "↑ Improving" :
                 improvement_rate.trend === "declining" ? "↓ Declining" : "→ Stable"}
              </div>
              <p className="text-xs text-muted-foreground">
                {improvement_rate.improvement_rate > 0 ? "+" : ""}{improvement_rate.improvement_rate} per attempt
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Criterion Bands */}
        <Card>
          <CardHeader>
            <CardTitle>Average Criterion Bands</CardTitle>
            <CardDescription>Fluency & Coherence, Lexical Resource, Grammar, Pronunciation</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { name: "Fluency & Coherence", value: metrics.average_fluency_band },
              { name: "Lexical Resource", value: metrics.average_lexical_band },
              { name: "Grammatical Range", value: metrics.average_grammar_band },
              { name: "Pronunciation", value: metrics.average_pronunciation_band },
            ].map((c) => (
              <div key={c.name} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span>{c.name}</span>
                  <span className="font-medium">{c.value ?? "N/A"}</span>
                </div>
                {c.value && <Progress value={(c.value / 9) * 100} className="h-2" />}
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Duration + Fillers */}
        <Card>
          <CardHeader>
            <CardTitle>Performance Metrics</CardTitle>
            <CardDescription>Average speaking duration and filler word frequency</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Average Duration</span>
                </div>
                <div className="text-2xl font-bold">
                  {metrics.average_duration ? `${Math.round(metrics.average_duration)}s` : "N/A"}
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Average Filler Words</span>
                </div>
                <div className="text-2xl font-bold">
                  {metrics.average_filler_words !== null ? metrics.average_filler_words.toFixed(1) : "N/A"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Common Errors */}
        <Card>
          <CardHeader>
            <CardTitle>Common Errors</CardTitle>
            <CardDescription>Based on your error analysis</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-medium mb-2">Grammar Errors</h4>
                {common_errors.common_grammar_errors.length > 0 ? (
                  <div className="space-y-2">
                    {common_errors.common_grammar_errors.map((e) => (
                      <div key={e.error} className="flex justify-between text-sm">
                        <span className="text-muted-foreground">{e.error}</span>
                        <Badge variant="outline">{e.count}</Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No grammar errors recorded</p>
                )}
              </div>
              <div>
                <h4 className="font-medium mb-2">Vocabulary Errors</h4>
                {common_errors.common_vocabulary_errors.length > 0 ? (
                  <div className="space-y-2">
                    {common_errors.common_vocabulary_errors.map((e) => (
                      <div key={e.error} className="flex justify-between text-sm">
                        <span className="text-muted-foreground">{e.error}</span>
                        <Badge variant="outline">{e.count}</Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No vocabulary errors recorded</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Band History Chart Area */}
        <Card>
          <CardHeader>
            <CardTitle>Speaking Band History</CardTitle>
            <CardDescription>Your overall and per-criterion band trajectory over time</CardDescription>
          </CardHeader>
          <CardContent>
            {band_history.length > 0 ? (
              <div className="space-y-4">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2">Date</th>
                        <th className="text-right py-2">Overall</th>
                        <th className="text-right py-2">Fluency</th>
                        <th className="text-right py-2">Lexical</th>
                        <th className="text-right py-2">Grammar</th>
                        <th className="text-right py-2">Pronunciation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {band_history.slice().reverse().map((p) => (
                        <tr key={p.evaluation_id} className="border-b border-border/50">
                          <td className="py-2 text-xs">{p.date}</td>
                          <td className="text-right py-2">{p.overall_band ?? "-"}</td>
                          <td className="text-right py-2">{p.fluency_coherence_band ?? "-"}</td>
                          <td className="text-right py-2">{p.lexical_resource_band ?? "-"}</td>
                          <td className="text-right py-2">{p.grammatical_range_band ?? "-"}</td>
                          <td className="text-right py-2">{p.pronunciation_band ?? "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No band history available yet.</p>
            )}
          </CardContent>
        </Card>

        {/* Attempt History */}
        <Card>
          <CardHeader>
            <CardTitle>Attempt History</CardTitle>
            <CardDescription>All your speaking attempts with scores and stats</CardDescription>
          </CardHeader>
          <CardContent>
            {attempt_history.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2">Date</th>
                      <th className="text-right py-2">Band</th>
                      <th className="text-left py-2">Part</th>
                      <th className="text-right py-2">Errors</th>
                      <th className="text-right py-2">Fillers</th>
                      <th className="text-right py-2">Duration</th>
                      <th className="text-left py-2">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attempt_history.map((a) => (
                      <tr key={a.evaluation_id} className="border-b border-border/50">
                        <td className="py-2 text-xs">{a.date}</td>
                        <td className="text-right py-2 font-medium">{a.overall_band ?? "-"}</td>
                        <td className="py-2 text-xs">{a.part}</td>
                        <td className="text-right py-2">{a.error_count}</td>
                        <td className="text-right py-2">{a.filler_words}</td>
                        <td className="text-right py-2">{a.duration_seconds}s</td>
                        <td className="py-2 text-xs">{a.source || "unknown"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No attempts recorded yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
