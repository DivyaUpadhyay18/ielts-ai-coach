"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Calendar,
  Trophy,
  Target,
  TrendingUp,
  Clock,
  CheckCircle2,
  Zap,
  Award,
  Star,
  BarChart3,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Flame,
  BookOpen,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { weeklyReportService } from "@/services/api";
import type { WeeklyReportResponse, WeeklyReportHistoryResponse } from "@/types";

const SKILL_LABELS: Record<string, string> = {
  reading: "Reading",
  listening: "Listening",
  writing: "Writing",
  speaking: "Speaking",
  vocabulary: "Lexical Resource",
  grammar: "Grammatical Range",
};

const BAND_COLORS: Record<number, string> = {
  0: "text-gray-400",
  1: "text-gray-400",
  2: "text-gray-400",
  3: "text-red-500",
  4: "text-orange-500",
  5: "text-amber-500",
  6: "text-yellow-500",
  7: "text-green-500",
  8: "text-blue-500",
  9: "text-purple-600",
};

function BandBadge({ band }: { band: number }) {
  const bandRounded = Math.round(band * 2) / 2;
  const colorClass = BAND_COLORS[bandRounded] || "text-gray-400";
  return (
    <Badge variant="outline" className={`text-sm font-semibold ${colorClass} border-current`}>
      {bandRounded.toFixed(1)}
    </Badge>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  color = "text-primary",
  unit = "",
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  color?: string;
  unit?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {title}
            </p>
            <p className={`text-3xl font-black ${color}`}>
              {value}
              {unit}
            </p>
            {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          <div className={`p-3 rounded-xl bg-primary/10 ${color}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SectionHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2 className="text-xl font-bold text-foreground">{title}</h2>
        {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export default function WeeklyReportsPage() {
  const [report, setReport] = useState<WeeklyReportResponse | null>(null);
  const [history, setHistory] = useState<WeeklyReportHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await weeklyReportService.getLatest();
      setReport(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to load weekly report");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRegenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const data = await weeklyReportService.getLatest(true);
      setReport(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to regenerate report");
    } finally {
      setGenerating(false);
    }
  };

  const fetchHistory = useCallback(async () => {
    setShowHistory(true);
    try {
      const data = await weeklyReportService.getHistory();
      setHistory(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load history");
    }
  }, []);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6 pb-12">
          <Skeleton className="h-12 w-64" />
          <Skeleton className="h-6 w-80" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-32 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="flex items-center gap-3 rounded-xl border border-error/30 bg-error/5 p-4 text-error">
          <AlertCircle className="h-5 w-5" />
          <p className="text-sm font-medium flex-1">{error}</p>
          <Button variant="ghost" size="sm" onClick={fetchReport}>
            Retry
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  if (!report) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <Calendar className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">No weekly report available yet.</p>
        </div>
      </DashboardLayout>
    );
  }

  const weekStart = new Date(report.week_start);
  const weekEnd = new Date(report.week_end);
  const formattedRange = `${weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" })} – ${weekEnd.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Calendar className="h-8 w-8 text-primary" />
              Weekly AI Report
            </h1>
            <p className="text-muted-foreground">
              {formattedRange} · Generated {new Date(report.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleRegenerate} disabled={generating}>
              {generating ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              {generating ? "Regenerating..." : "Regenerate"}
            </Button>
            <Button variant="outline" size="sm" onClick={fetchHistory}>
              <Clock className="h-4 w-4 mr-2" />
              History
            </Button>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg flex items-center gap-3">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {/* Top Stats Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Estimated Band"
            value={report.estimated_band.toFixed(1)}
            subtitle={
              report.previous_week_band
                ? `${report.previous_week_band.toFixed(1)} last week • ${report.estimated_band >= report.previous_week_band ? "↗" : "↘"} ${Math.abs(report.estimated_band - report.previous_week_band).toFixed(1)}`
                : "vs last week"
            }
            icon={Trophy}
            color={BAND_COLORS[Math.round(report.estimated_band * 2) / 2] || "text-yellow-400"}
          />
          <StatCard
            title="Hours Studied"
            value={report.hours_studied.toFixed(1)}
            subtitle={`${report.metrics.task_target} tasks target`}
            unit="h"
            icon={Clock}
            color="text-blue-600"
          />
          <StatCard
            title="Tasks Completed"
            value={report.tasks_completed}
            subtitle={`/${report.metrics.task_target} this week`}
            icon={CheckCircle2}
            color="text-green-600"
          />
          <StatCard
            title="Current Streak"
            value={report.streak}
            subtitle={`Longest: ${report.metrics.longest_streak} days`}
            unit="d"
            icon={Flame}
            color="text-orange-600"
          />
        </div>

        {/* Second Stats Row */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard
            title="Consistency"
            value={report.consistency.toFixed(0)}
            subtitle={`${report.metrics.active_days_in_week}/${report.metrics.total_days_in_week} active days`}
            unit="%"
            icon={BarChart3}
            color="text-indigo-600"
          />
          <StatCard
            title="Weakest Skill"
            value={report.weakest_skill || "N/A"}
            subtitle={
              report.weakest_skill_key && report.metrics.skill_bands[report.weakest_skill_key]
                ? `Band ${report.metrics.skill_bands[report.weakest_skill_key].toFixed(1)}`
                : ""
            }
            icon={TrendingUp}
            color="text-red-600"
          />
          <StatCard
            title="Strongest Skill"
            value={report.strongest_skill || "N/A"}
            subtitle={
              report.strongest_skill_key && report.metrics.skill_bands[report.strongest_skill_key]
                ? `Band ${report.metrics.skill_bands[report.strongest_skill_key].toFixed(1)}`
                : ""
            }
            icon={Award}
            color="text-emerald-600"
          />
        </div>

        {/* Summary Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <BookOpen className="h-5 w-5 text-primary" />
              Weekly Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-base text-foreground leading-relaxed">
              {report.summary}
            </p>
          </CardContent>
        </Card>

        {/* Achievements */}
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Star className="h-5 w-5 text-yellow-400" />
                Achievements Unlocked
              </CardTitle>
              <CardDescription>
                {report.achievements.length} achievement(s) this week
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {report.achievements.map((achievement, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-3 p-2 bg-gradient-to-r from-yellow-50 to-amber-50 rounded-lg border border-yellow-200"
                  >
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-yellow-400 flex items-center justify-center text-xs font-bold text-yellow-900">
                      {idx + 1}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-yellow-900">
                        {achievement}
                      </p>
                    </div>
                    <Star className="h-4 w-4 text-yellow-400 mt-0.5" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Skill Bands */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Trophy className="h-5 w-5 text-purple-600" />
                Skill Bands
              </CardTitle>
              <CardDescription>
                Your estimated band per skill (diagnostic + band estimation)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {report.metrics.skill_bands && Object.keys(report.metrics.skill_bands).length > 0 ? (
                <div className="space-y-3">
                  {Object.entries(report.metrics.skill_bands).map(([skill, band]) => {
                    const label = SKILL_LABELS[skill] || skill;
                    const isWeakest = report.weakest_skill_key === skill;
                    const isStrongest = report.strongest_skill_key === skill;
                    const colorClass = BAND_COLORS[Math.round(band * 2) / 2] || "text-gray-400";

                    return (
                      <div key={skill} className="space-y-1">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className={`font-medium text-sm ${colorClass}`}>
                              {label}
                            </span>
                            {isWeakest && (
                              <Badge variant="destructive" className="text-xs">
                                Weakest
                              </Badge>
                            )}
                            {isStrongest && (
                              <Badge variant="default" className="text-xs">
                                Strongest
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-3">
                            <span className={`font-bold ${colorClass}`}>
                              {band.toFixed(1)}
                            </span>
                            <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${colorClass.includes("red") ? "bg-red-500" : colorClass.includes("orange") ? "bg-orange-500" : colorClass.includes("amber") ? "bg-amber-500" : colorClass.includes("yellow") ? "bg-yellow-500" : colorClass.includes("green") ? "bg-green-500" : colorClass.includes("blue") ? "bg-blue-500" : colorClass.includes("purple") ? "bg-purple-500" : "bg-gray-400"}`}
                                style={{ width: `${(band / 9) * 100}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-6 text-muted-foreground">
                  <Trophy className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p>Complete a diagnostic test to see skill bands</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Suggestions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Target className="h-5 w-5 text-primary" />
              This Week&apos;s Suggestions
            </CardTitle>
            <CardDescription>
              Actionable, deterministic recommendations based on your progress
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {report.suggestions.map((suggestion, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 bg-primary/5 rounded-lg border border-primary/10"
                >
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-xs font-bold text-primary">
                    {idx + 1}
                  </div>
                  <p className="text-sm text-foreground flex-1">
                    {suggestion}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Next Week's Focus */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Zap className="h-5 w-5 text-amber-500" />
              Next Week&apos;s Focus
            </CardTitle>
            <CardDescription>
              Prioritize these skills based on your weakest areas
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {report.next_week_focus.map((focus, idx) => (
                <div key={idx} className="flex items-center gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center text-xs font-bold text-amber-600">
                    {idx + 1}
                  </div>
                  <p className="text-sm font-medium">{focus}</p>
                </div>
              ))}
            </div>

            {/* Navigation */}
            <div className="mt-6 pt-4 border-t border-border flex items-center justify-between">
              <Button variant="ghost" size="sm" asChild>
                <Link href="/dashboard">
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Back to Dashboard
                </Link>
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/prediction">
                  <ChevronRight className="h-4 w-4 ml-1" />
                  Band Prediction
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Consistency Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <BarChart3 className="h-5 w-5 text-indigo-600" />
              Consistency Trend
            </CardTitle>
            <CardDescription>
              {report.consistency !== undefined && (
                <>Consistency: {report.consistency.toFixed(0)}%</>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Active days this week</span>
                <span className="font-medium">
                  {report.metrics.active_days_in_week}/{report.metrics.total_days_in_week}
                </span>
              </div>
              <Progress
                value={(report.metrics.active_days_in_week / report.metrics.total_days_in_week) * 100}
                className="h-3"
              />
              <div className="grid grid-cols-3 gap-4 text-center text-sm">
                <div>
                  <p className="text-2xl font-bold text-orange-600">
                    {report.metrics.daily_streak}
                  </p>
                  <p className="text-xs text-muted-foreground">Daily Streak</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-blue-600">
                    {report.metrics.weekly_streak}
                  </p>
                  <p className="text-xs text-muted-foreground">Weekly Streak</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-purple-600">
                    {report.metrics.monthly_streak}
                  </p>
                  <p className="text-xs text-muted-foreground">Monthly Streak</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Formula Reference (expandable) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <BookOpen className="h-5 w-5 text-slate-600" />
              Formula Reference
            </CardTitle>
            <CardDescription>
              All metrics are computed deterministically — no AI
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2">
              {Object.entries(report.formulas).map(([key, formula]) => (
                <div key={key}>
                  <code className="text-xs font-medium text-primary bg-primary/10 px-2 py-1 rounded">
                    {key}
                  </code>
                  <p className="text-xs text-muted-foreground mt-1">{formula}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
