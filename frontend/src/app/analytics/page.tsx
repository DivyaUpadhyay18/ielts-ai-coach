"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Download,
  Filter,
  Info,
  Clock,
  Zap,
  Flame,
  TrendingUp,
  Activity,
  PenTool,
  Mic,
  BookOpen,
  Bell,
  Sparkles,
  GraduationCap,
  AlertCircle,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { progressTrackingService } from "@/services/api";
import type {
  ProgressOverviewResponse,
  ChartsResponse,
  HistoryResponse,
  RecentHistoryItem,
  ChartPointData,
  MissionSkill,
} from "@/types";

// ─────────────────────────────────────────────────────────────
// Skill → icon/color mapping
// ─────────────────────────────────────────────────────────────
const SKILL_STYLES: Record<string, { color: string; bg: string; icon: any; label: string }> = {
  reading: { color: "text-purple-600", bg: "bg-purple-100", icon: BookOpen, label: "Reading" },
  listening: { color: "text-amber-600", bg: "bg-amber-100", icon: Bell, label: "Listening" },
  writing: { color: "text-blue-600", bg: "bg-blue-100", icon: PenTool, label: "Writing" },
  speaking: { color: "text-teal-600", bg: "bg-teal-100", icon: Mic, label: "Speaking" },
  vocabulary: { color: "text-emerald-600", bg: "bg-emerald-100", icon: Sparkles, label: "Vocabulary" },
  grammar: { color: "text-rose-600", bg: "bg-rose-100", icon: GraduationCap, label: "Grammar" },
  general: { color: "text-slate-600", bg: "bg-slate-100", icon: Activity, label: "General" },
};

function skillStyle(skill: string | null) {
  return SKILL_STYLES[skill || "general"] || SKILL_STYLES.general;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso || "—";
  }
}

// ─────────────────────────────────────────────────────────────
// Loading skeleton
// ─────────────────────────────────────────────────────────────
function AnalyticsSkeleton() {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-8 lg:grid-cols-3">
        <Skeleton className="lg:col-span-2 h-[360px] rounded-xl" />
        <Skeleton className="h-[360px] rounded-xl" />
      </div>
      <Skeleton className="h-72 rounded-xl" />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Pure bar chart (no external chart lib needed)
// ─────────────────────────────────────────────────────────────
function BarChart({ series }: { series: ChartPointData[] }) {
  const max = Math.max(...series.map((s) => s.minutes || s.xp), 1);
  return (
    <div className="h-[280px] w-full bg-slate-50 dark:bg-slate-900 rounded-xl border border-dashed border-border flex items-end justify-around gap-2 p-6 relative">
      {series.map((point, i) => {
        const h = Math.max(4, Math.round(((point.minutes || point.xp || 0) / max) * 100));
        return (
          <div key={i} className="w-full max-w-[48px] group relative flex flex-col items-center justify-end h-full">
            <div className="relative flex items-end w-full justify-center" style={{ height: `${h}%` }}>
              <div className="w-full bg-primary/20 group-hover:bg-primary transition-all rounded-t-sm" style={{ height: "100%" }} />
              <div className="absolute inset-x-0 -bottom-0 h-full flex items-end justify-center">
                <span className="text-[9px] font-bold text-muted-foreground bg-background/90 rounded px-1 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap mb-1">
                  {point.minutes} min • {point.xp} XP
                </span>
              </div>
            </div>
            <span className="mt-2 text-[10px] text-muted-foreground">{point.label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────
export default function ProgressAnalytics() {
  const [overview, setOverview] = useState<ProgressOverviewResponse | null>(null);
  const [charts, setCharts] = useState<ChartsResponse | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, ch, hist] = await Promise.all([
        progressTrackingService.getOverview(),
        progressTrackingService.getCharts(),
        progressTrackingService.getHistory(50),
      ]);
      setOverview(ov);
      setCharts(ch);
      setHistory(hist);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (loading) {
    return (
      <DashboardLayout>
        <AnalyticsSkeleton />
      </DashboardLayout>
    );
  }

  if (error && !overview) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center py-32 text-center space-y-4">
          <div className="p-4 rounded-full bg-error/10 text-error">
            <AlertCircle className="h-10 w-10" />
          </div>
          <h2 className="text-2xl font-bold">Unable to load analytics</h2>
          <p className="text-muted-foreground max-w-md">{error}</p>
          <Button onClick={fetchAll}>Retry</Button>
        </div>
      </DashboardLayout>
    );
  }

  // Quick stats — real progress data
  const daily = overview?.daily;
  const weekly = overview?.weekly;
  const monthly = overview?.monthly;
  const xp = overview?.xp;
  const streak = overview?.streak;

  const stats = [
    {
      label: "XP Today",
      value: String(xp?.today ?? 0),
      sub: `${xp?.total ?? 0} lifetime • Level ${xp?.level ?? 1}`,
      icon: Zap,
      iconBg: "bg-amber-100",
      iconColor: "text-amber-600",
      trend: null,
    },
    {
      label: "Study Streak",
      value: `${streak?.current ?? 0} days`,
      sub: streak?.at_risk ? "Complete a mission to protect it" : `Longest: ${streak?.longest ?? 0} days`,
      icon: Flame,
      iconBg: "bg-orange-100",
      iconColor: "text-orange-600",
      trend: null,
    },
    {
      label: "Study Time",
      value: `${overview?.study_time.today_minutes ?? 0}`,
      sub: `${overview?.study_time.week_minutes ?? 0} min this week`,
      icon: Clock,
      iconBg: "bg-blue-100",
      iconColor: "text-blue-600",
      trend: null,
    },
    {
      label: "Total Tasks",
      value: String(overview?.total_tasks ?? 0),
      sub: `${overview?.total_minutes ?? 0} total minutes logged`,
      icon: TrendingUp,
      iconBg: "bg-emerald-100",
      iconColor: "text-emerald-600",
      trend: null,
    },
  ];

  const skillTotals = charts?.skill_totals ?? {};
  const skillRows = Object.entries(skillTotals).map(([skill, totals]) => ({
    name: skillStyle(skill).label,
    skill,
    minutes: totals.minutes,
    tasks: totals.tasks,
    icon: skillStyle(skill).icon,
    color: skillStyle(skill).color,
    bg: skillStyle(skill).bg,
  }));
  skillRows.sort((a, b) => b.minutes - a.minutes);
  const maxSkillMinutes = Math.max(...skillRows.map((r) => r.minutes), 1);

  const dailySeries = charts?.daily_series ?? [];
  const historyItems = history?.items ?? [];

  return (
    <DashboardLayout>
      <div className="space-y-8 pb-12">

        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Performance Analytics</h1>
            <p className="text-muted-foreground">Real insights from your logged study activity.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Download className="mr-2 h-4 w-4" /> Export Data
            </Button>
            <Badge variant="secondary" className="h-8 px-3">
              <Filter className="mr-1 h-3.5 w-3.5" /> Last 7 Days
            </Badge>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-3 rounded-xl border border-error/30 bg-error/5 p-4 text-error">
            <AlertCircle className="h-5 w-5" />
            <p className="text-sm font-medium flex-1">{error}</p>
            <Button variant="ghost" size="sm" onClick={fetchAll}>Retry</Button>
          </div>
        )}

        {/* 1. Quick Stats Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => (
            <Card key={stat.label}>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
                  <div className={`p-2 rounded-lg ${stat.iconBg} ${stat.iconColor}`}>
                    <stat.icon className="h-4 w-4" />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <h3 className="text-3xl font-bold">{stat.value}</h3>
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">{stat.sub}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid gap-8 lg:grid-cols-3">

          {/* 2. Main Chart: Minutes + XP over last 7 days */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Weekly Study Activity</CardTitle>
                <CardDescription>Minutes studied and XP earned over the last 7 days.</CardDescription>
              </div>
              <BarChart3 className="h-5 w-5 text-muted-foreground" />
            </CardHeader>
            <CardContent className="pt-4">
              {dailySeries.length === 0 ? (
                <div className="h-[280px] flex flex-col items-center justify-center text-center space-y-3">
                  <Activity className="h-8 w-8 text-muted-foreground" />
                  <p className="text-muted-foreground text-sm max-w-xs">
                    No study activity yet. Complete daily missions to unlock your activity chart.
                  </p>
                </div>
              ) : (
                <BarChart series={dailySeries} />
              )}
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-primary" /> Study minutes
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> XP earned
                </span>
              </div>
            </CardContent>
          </Card>

          {/* 3. Skill Breakdown */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" /> Skill Focus
              </CardTitle>
              <CardDescription>Study minutes by skill (lifetime).</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {skillRows.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center space-y-2">
                  <Info className="h-6 w-6 text-muted-foreground" />
                  <p className="text-xs text-muted-foreground max-w-[200px]">
                    Complete missions to see your skill balance.
                  </p>
                </div>
              ) : (
                skillRows.slice(0, 6).map((row) => {
                  const Icon = row.icon;
                  return (
                    <div key={row.skill} className="space-y-2">
                      <div className="flex justify-between items-end">
                        <span className="flex items-center gap-1.5 text-xs font-bold">
                          <Icon className={`h-3.5 w-3.5 ${row.color}`} /> {row.name}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {row.minutes} min • {row.tasks} tasks
                        </span>
                      </div>
                      <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${Math.round((row.minutes / maxSkillMinutes) * 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              )}

              {/* Weekly progress summary */}
              <div className="pt-3 border-t border-border space-y-3">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Daily goal</span>
                  <span className="font-bold">{daily?.minutes ?? 0} / {daily?.target_minutes ?? 0} min</span>
                </div>
                <Progress value={daily?.percent ?? 0} className="h-2" variant="success" />
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Weekly goal</span>
                  <span className="font-bold">{weekly?.minutes ?? 0} / {weekly?.target_minutes ?? 0} min</span>
                </div>
                <Progress value={weekly?.percent ?? 0} className="h-2" variant="accent" />
              </div>
            </CardContent>
          </Card>

        </div>

        {/* 4. Recent Study History */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Study History</CardTitle>
            <CardDescription>A log of your logged missions and practice sessions.</CardDescription>
          </CardHeader>
          <CardContent>
            {historyItems.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center space-y-3">
                <Activity className="h-8 w-8 text-muted-foreground" />
                <p className="text-muted-foreground text-sm max-w-sm">
                  No study sessions logged yet. Complete daily missions to start building your history.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      <th className="text-left font-medium py-3 px-2">Date</th>
                      <th className="text-left font-medium py-3 px-2">Activity</th>
                      <th className="text-left font-medium py-3 px-2">Skill</th>
                      <th className="text-right font-medium py-3 px-2">Minutes</th>
                      <th className="text-right font-medium py-3 px-2">XP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {historyItems.slice(0, 12).map((item: RecentHistoryItem) => {
                      const style = skillStyle(item.skill);
                      const Icon = style.icon;
                      return (
                        <tr key={item.id} className="group hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                          <td className="py-4 px-2 text-muted-foreground">{formatDate(item.date)}</td>
                          <td className="py-4 px-2 font-medium">{item.title}</td>
                          <td className="py-4 px-2">
                            <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${style.bg} ${style.color}`}>
                              <Icon className="h-3 w-3" /> {style.label}
                            </span>
                          </td>
                          <td className="py-4 px-2 text-right font-bold">{item.minutes}</td>
                          <td className="py-4 px-2 text-right">
                            <Badge variant={item.xp > 0 ? "warning" : "secondary"} className="text-[10px]">
                              +{item.xp} XP
                            </Badge>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {historyItems.length > 12 && (
              <button className="w-full mt-4 text-center text-xs text-primary hover:underline">
                Load More History
              </button>
            )}
          </CardContent>
        </Card>

      </div>
    </DashboardLayout>
  );
}

