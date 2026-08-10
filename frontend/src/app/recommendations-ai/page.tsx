"use client";

import React, {useCallback, useEffect, useState} from "react";
import {
  Calendar,
  RefreshCw,
  TrendingUp,
  Trophy,
  Clock,
  Target,
  BookOpen,
  CheckCircle2,
  PauseCircle,
  Zap,
  AlertCircle,
  Loader2,
  Brain,
  BarChart3,
  PlayCircle,
  ExternalLink,
} from "lucide-react";
import {DashboardLayout} from "@/components/layouts/dashboard-layout";
import {Card, CardContent, CardHeader, CardTitle, CardDescription} from "@/components/ui/card";
import {Button} from "@/components/ui/button";
import {Badge} from "@/components/ui/badge";
import {Progress} from "@/components/ui/progress";
import {Skeleton} from "@/components/ui/skeleton";
import Link from "next/link";
import {aiRecommendationsService} from "@/services/api";
import type {AiRecommendationsResponse} from "@/types";

function PriorityBadge({priority}: { priority: string }) {
  const styles = {
    high: "bg-red-100 text-red-800 dark:bg-red-900/30",
    medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/30",
    low: "bg-green-100 text-green-800 dark:bg-green-900/30",
  };
  return (
    <Badge className={styles[priority as keyof typeof styles] || styles.medium}>
      {priority} priority
    </Badge>
  );
}

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
  3: "text-red-500",
  4: "text-orange-500",
  5: "text-amber-500",
  6: "text-yellow-500",
  7: "text-green-500",
  8: "text-blue-500",
  9: "text-purple-600",
};

function getBandColor(band: number): string {
  const rounded = Math.round(band * 2) / 2;
  return BAND_COLORS[rounded] || "text-gray-400";
}

function BandBadge({band}: { band: number }) {
  const colorClass = getBandColor(band);
  return (
    <Badge variant="outline" className={`text-sm font-semibold ${colorClass} border-current`}>
      {band.toFixed(1)}
    </Badge>
  );
}

function StatCard({
  title, value, subtitle, icon: Icon, color = "text-primary",
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  color?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {title}
            </p>
            <p className={`text-3xl font-black ${color}`}>{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
          </div>
          <div className={`p-3 rounded-xl bg-primary/10 ${color}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SectionHeader({
  title, subtitle, action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
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
export default function AiRecommendationsPage() {
  const [report, setReport] = useState<AiRecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const fetchRecommendations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await aiRecommendationsService.getRecommendations();
      setReport(data);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail?.message ||
        err?.message ||
        "Failed to load recommendations"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRegenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const data = await aiRecommendationsService.getRecommendations(true);
      setReport(data);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail?.message ||
        err?.message ||
        "Failed to regenerate"
      );
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6 pb-12">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-80" />
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
          <Button variant="ghost" size="sm" onClick={fetchRecommendations}>
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
          <Brain className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">No recommendations available yet.</p>
        </div>
      </DashboardLayout>
    );
  }

  const today = new Date(report.run_date);
  const formattedDate = today.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const bandColor = getBandColor(report.estimated_band);

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Brain className="h-8 w-8 text-primary" />
              AI Recommendations
            </h1>
            <p className="text-sm text-muted-foreground">
              {formattedDate} · v{report.version}
            </p>
          </div>
          <Button onClick={handleRegenerate} disabled={generating} variant="outline">
            {generating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Regenerating...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                Regenerate
              </>
            )}
          </Button>
        </div>

        {/* Overview stats */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Estimated Band"
            value={report.estimated_band.toFixed(1)}
            subtitle={
              report.previous_week_band
                ? `${report.previous_week_band.toFixed(1)} last week • ${
                    report.estimated_band >= report.previous_week_band ? "↗" : "↘"
                  } ${Math.abs(report.estimated_band - report.previous_week_band).toFixed(1)}`
                : "vs last week"
            }
            icon={Trophy}
            color={bandColor}
          />
          <StatCard
            title="Hours Studied"
            value={report.hours_studied.toFixed(1)}
            subtitle={`${report.tasks_completed} tasks completed`}
            icon={Clock}
            color="text-blue-600"
          />
          <StatCard
            title="Current Streak"
            value={report.streak}
            subtitle={`Longest: ${report.metrics.longest_streak} days`}
            icon={TrendingUp}
            color="text-orange-600"
          />
          <StatCard
            title="Consistency"
            value={`${report.consistency.toFixed(0)}%`}
            subtitle={`${report.metrics.active_days_in_week}/7 active days`}
            icon={BarChart3}
            color="text-indigo-600"
          />
        </div>

        {/* Summary */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Brain className="h-5 w-5 text-primary" />
              Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-base text-foreground leading-relaxed">
              {report.summary}
            </p>
          </CardContent>
        </Card>

        {/* Study Order */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <PlayCircle className="h-5 w-5 text-blue-600" />
              Study Order — This Week
            </CardTitle>
            <CardDescription>
              Skills ranked by priority (band gap + production skill bonus + time pressure)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {report.study_order.length === 0 ? (
              <p className="text-sm text-muted-foreground">No diagnostic data available. Complete a diagnostic test to unlock study order.</p>
            ) : (
            <div className="space-y-3">
              {report.study_order.map((entry) => {
                const colorClass = getBandColor(entry.band);
                return (
                  <div
                    key={entry.skill}
                    className="flex items-center gap-4 p-3 bg-secondary/30 rounded-lg border border-border"
                  >
                    <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary font-bold">
                      {entry.order}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{entry.label}</span>
                        <BandBadge band={entry.band} />
                        {entry.is_production && (
                          <Badge variant="outline" className="text-xs">
                            Production
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                        <span>Gap: +{entry.band_gap.toFixed(1)}</span>
                        <span>Score: {entry.priority_score.toFixed(1)}</span>
                      </div>
                    </div>
                    <div className={`font-bold ${colorClass}`}>
                      {entry.band.toFixed(1)}
                    </div>
                  </div>
                );
              })}
            </div>
            )}
          </CardContent>
        </Card>

        {/* Grid: Revision Priorities + Extra Practice */}
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Target className="h-5 w-5 text-red-600" />
                Revision Priorities
              </CardTitle>
              <CardDescription>
                Topics within weak skills that need review
              </CardDescription>
            </CardHeader>
            <CardContent>
              {report.revision_priorities.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4">No revision priorities — skills look balanced.</p>
              ) : (
              <div className="space-y-3">
                {report.revision_priorities.map((item) => (
                  <div key={item.skill} className="p-3 bg-red-50/30 rounded-lg border border-red-200/30">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium">{item.label}</span>
                      <Badge
                        className={
                          item.intensity === "critical"
                            ? "bg-red-100 text-red-800 dark:bg-red-900/30"
                            : item.intensity === "high"
                            ? "bg-orange-100 text-orange-800 dark:bg-orange-900/30"
                            : item.intensity === "medium"
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30"
                            : "bg-green-100 text-green-800 dark:bg-green-900/30"
                        }
                      >
                        {item.intensity}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mb-2">
                      Focus: {item.focus_area}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {item.topics.map((topic) => (
                        <Badge key={topic} variant="outline" className="text-xs">
                          {topic}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <BookOpen className="h-5 w-5 text-green-600" />
                Extra Practice
              </CardTitle>
              <CardDescription>
                Daily time allocation per skill
              </CardDescription>
            </CardHeader>
            <CardContent>
              {report.extra_practice.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4">No extra practice needed.</p>
              ) : (
              <div className="space-y-4">
                {report.extra_practice.map((item) => (
                  <div key={item.skill} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{item.label}</span>
                        <BandBadge band={item.band} />
                        <PriorityBadge priority={item.priority} />
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-xs">
                          {item.practice_type}
                        </Badge>
                        <span className="text-sm font-medium">
                          {item.recommended_minutes} min
                        </span>
                      </div>
                    </div>
                    <Progress
                      value={
                        (item.recommended_minutes / report.metrics.daily_budget_minutes) * 100
                      }
                      className="h-2"
                    />
                  </div>
                ))}
              </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Break Suggestions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <PauseCircle className="h-5 w-5 text-amber-500" />
              Break Suggestions
            </CardTitle>
            <CardDescription>
              Based on your study load this week
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2">
              {report.break_suggestions.map((breakItem, idx) => (
                <div key={idx} className="p-4 bg-amber-50/30 rounded-lg border border-amber-200/30">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 p-2 bg-amber-100 rounded-lg">
                      <PauseCircle className="h-5 w-5 text-amber-600" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium text-sm">{breakItem.title}</h4>
                      <p className="text-xs text-muted-foreground mt-1">
                        {breakItem.description}
                      </p>
                      <div className="flex items-center gap-2 mt-2 text-xs">
                        <Badge variant="outline" className="text-xs">
                          {breakItem.frequency}
                        </Badge>
                        {breakItem.duration_minutes > 0 && (
                          <span className="text-muted-foreground">
                            {breakItem.duration_minutes} min
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Time Management */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Clock className="h-5 w-5 text-indigo-600" />
              Time Management
            </CardTitle>
            <CardDescription>
              Daily budget allocation and scheduling tips
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">Focus Mode</span>
                <Badge
                  className={
                    report.time_management.focus_mode === "exam-cram"
                      ? "bg-red-100 text-red-800 dark:bg-red-900/30"
                      : report.time_management.focus_mode === "intensive"
                      ? "bg-orange-100 text-orange-800 dark:bg-orange-900/30"
                      : "bg-green-100 text-green-800 dark:bg-green-900/30"
                  }
                >
                  {report.time_management.focus_mode}
                </Badge>
              </div>

              <div className="space-y-3">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-red-600 font-medium">
                      Weak Skills ({report.time_management.time_split.weak_skills})
                    </span>
                    <span className="font-medium">
                      {report.time_management.time_split.weak_minutes} min
                    </span>
                  </div>
                  <Progress
                    value={
                      (report.time_management.time_split.weak_minutes /
                        report.time_management.daily_budget_minutes) *
                      100
                    }
                    className="h-2"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-blue-600 font-medium">
                      Strong Skills ({report.time_management.time_split.strong_skills})
                    </span>
                    <span className="font-medium">
                      {report.time_management.time_split.strong_minutes} min
                    </span>
                  </div>
                  <Progress
                    value={
                      (report.time_management.time_split.strong_minutes /
                        report.time_management.daily_budget_minutes) *
                      100
                    }
                    className="h-2"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-purple-600 font-medium">
                      Review ({report.time_management.time_split.review})
                    </span>
                    <span className="font-medium">
                      {report.time_management.time_split.review_minutes} min
                    </span>
                  </div>
                  <Progress
                    value={
                      (report.time_management.time_split.review_minutes /
                        report.time_management.daily_budget_minutes) *
                      100
                    }
                    className="h-2"
                  />
                </div>
              </div>

              <p className="text-sm text-muted-foreground bg-indigo-50/30 p-3 rounded-lg">
                {report.time_management.tip}
              </p>

              <div className="grid grid-cols-3 gap-4 text-center text-sm">
                <div>
                  <p className="text-2xl font-bold text-indigo-600">
                    {report.time_management.tasks_per_day}
                  </p>
                  <p className="text-xs text-muted-foreground">Tasks/Day</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-indigo-600">
                    {report.time_management.weekly_target_minutes}
                  </p>
                  <p className="text-xs text-muted-foreground">Weekly Target</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-indigo-600">
                    Level {report.time_management.level}
                  </p>
                  <p className="text-xs text-muted-foreground">Your Level</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Additional Resources */}
        {report.additional_resources.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <BookOpen className="h-5 w-5 text-teal-600" />
                Additional Resources
              </CardTitle>
              <CardDescription>
                Curated resources based on your weakest skills
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                {report.additional_resources.map((resource) => (
                  <div
                    key={resource.id}
                    className="flex flex-col p-3 bg-secondary/30 rounded-lg border border-border"
                  >
                    <div className="flex items-start justify-between">
                      <h4 className="font-medium text-sm">{resource.title}</h4>
                      <Badge variant="secondary" className="text-xs">
                        {resource.type}
                      </Badge>
                    </div>
                    {resource.description && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {resource.description}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-2">
                      {resource.minimum_band && <BandBadge band={resource.minimum_band} />}
                      {resource.official && (
                        <Badge variant="outline" className="text-xs">
                          Official
                        </Badge>
                      )}
                      {resource.is_free && (
                        <Badge variant="outline" className="text-xs">
                          Free
                        </Badge>
                      )}
                    </div>
                    {resource.url && (
                      <Button variant="link" size="sm" className="mt-2 justify-start" asChild>
                        <a href={resource.url} target="_blank" rel="noreferrer">
                          <ExternalLink className="h-3 w-3 mr-1" />
                          Open Resource
                        </a>
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Suggestions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Zap className="h-5 w-5 text-yellow-500" />
              Personalized Suggestions
            </CardTitle>
            <CardDescription>
              Actionable advice based on your progress
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {report.suggestions.map((suggestion, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 bg-yellow-50/30 rounded-lg border border-yellow-200/30"
                >
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-yellow-400 flex items-center justify-center text-xs font-bold text-yellow-900">
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
              <Trophy className="h-5 w-5 text-emerald-600" />
              Next Week&apos;s Focus
            </CardTitle>
            <CardDescription>
              Prioritize these skills in your next study week
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {report.next_week_focus.map((focus, idx) => (
                <div key={idx} className="flex items-center gap-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-sm font-bold text-emerald-600">
                    {idx + 1}
                  </div>
                  <p className="text-sm font-medium flex-1">{focus}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 pt-4 border-t border-border flex items-center justify-between">
              <Button variant="ghost" size="sm" asChild>
                <Link href="/dashboard">← Back to Dashboard</Link>
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/weekly-reports">Weekly Reports →</Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Formula Reference */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <BookOpen className="h-5 w-5 text-slate-600" />
              Formula Reference
            </CardTitle>
            <CardDescription>
              All recommendations are deterministic — no AI hallucinations
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