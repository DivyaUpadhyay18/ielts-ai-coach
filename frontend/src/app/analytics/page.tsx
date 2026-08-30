"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  Eye,
  CheckCircle2,
  Bookmark,
  ThumbsUp,
  Star,
  Clock,
  Target,
  TrendingUp,
  Activity,
  AlertCircle,
  Download,
  Filter,
  Info,
  PenTool,
  Mic,
  BookOpen,
  Bell,
  Sparkles,
  GraduationCap,
  Flame,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { analyticsService } from "@/services/api";
import type {
  AnalyticsDashboardResponse,
  AnalyticsTrendPoint,
  SkillBreakdown,
  ResourcePerformanceItem,
  AnalyticsEvent,
} from "@/types/analytics";

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

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso || "—";
  }
}

function formatEventName(event: string): string {
  const map: Record<string, string> = {
    resource_viewed: "Resource Viewed",
    resource_completed: "Resource Completed",
    resource_bookmarked: "Resource Bookmarked",
    resource_unbookmarked: "Resource Unbookmarked",
    resource_liked: "Resource Liked",
    resource_unliked: "Resource Unliked",
    resource_rated: "Resource Rated",
    study_session_logged: "Study Session",
  };
  return map[event] || event.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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
function TrendChart({ series }: { series: AnalyticsTrendPoint[] }) {
  const max = Math.max(...series.map((s) => Math.max(s.views, s.completions, s.study_minutes)), 1);
  return (
    <div className="h-[280px] w-full bg-slate-50 dark:bg-slate-900 rounded-xl border border-dashed border-border flex items-end justify-around gap-1 p-6 relative">
      {series.map((point, i) => {
        const h = Math.max(4, Math.round(((point.views || point.study_minutes || 0) / max) * 100));
        return (
          <div key={i} className="w-full max-w-[40px] group relative flex flex-col items-center justify-end h-full">
            <div className="relative flex items-end w-full justify-center" style={{ height: `${h}%` }}>
              <div className="w-full bg-primary/20 group-hover:bg-primary transition-all rounded-t-sm" style={{ height: "100%" }} />
              <div className="absolute inset-x-0 -bottom-0 h-full flex items-end justify-center">
                <span className="text-[9px] font-bold text-muted-foreground bg-background/90 rounded px-1 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap mb-1">
                  {point.views} views • {point.study_minutes} min
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
export default function AnalyticsDashboard() {
  const [dashboard, setDashboard] = useState<AnalyticsDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await analyticsService.getDashboard(days);
      setDashboard(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [days]);

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

  if (error && !dashboard) {
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

  const summary = dashboard?.summary;
  const trends = dashboard?.trends ?? [];
  const skills = dashboard?.skill_breakdown ?? [];
  const topResources = dashboard?.top_resources ?? [];
  const recentEvents = dashboard?.recent_events ?? [];

  const stats = [
    {
      label: "Total Views",
      value: String(summary?.total_views ?? 0),
      sub: `${summary?.active_days ?? 0} active days`,
      icon: Eye,
      iconBg: "bg-blue-100",
      iconColor: "text-blue-600",
    },
    {
      label: "Completions",
      value: String(summary?.total_completions ?? 0),
      sub: `${summary?.completion_rate ?? 0}% completion rate`,
      icon: CheckCircle2,
      iconBg: "bg-emerald-100",
      iconColor: "text-emerald-600",
    },
    {
      label: "Study Time",
      value: `${Math.round((summary?.total_study_minutes ?? 0) / 60)}h`,
      sub: `${summary?.total_study_minutes ?? 0} min total`,
      icon: Clock,
      iconBg: "bg-amber-100",
      iconColor: "text-amber-600",
    },
    {
      label: "Bookmarks",
      value: String(summary?.total_bookmarks ?? 0),
      sub: `${summary?.total_likes ?? 0} likes • ${summary?.total_ratings ?? 0} ratings`,
      icon: Bookmark,
      iconBg: "bg-purple-100",
      iconColor: "text-purple-600",
    },
  ];

  const rateCards = [
    {
      label: "Completion Rate",
      value: `${summary?.completion_rate ?? 0}%`,
      sub: "Completions / Views",
      icon: Target,
      iconBg: "bg-emerald-100",
      iconColor: "text-emerald-600",
      progress: summary?.completion_rate ?? 0,
      variant: "success" as const,
    },
    {
      label: "Success Rate",
      value: `${summary?.success_rate ?? 0}%`,
      sub: "Tasks / Sessions",
      icon: TrendingUp,
      iconBg: "bg-blue-100",
      iconColor: "text-blue-600",
      progress: summary?.success_rate ?? 0,
      variant: "accent" as const,
    },
    {
      label: "Drop-off Rate",
      value: `${summary?.drop_off_rate ?? 0}%`,
      sub: "100% - Completion",
      icon: ArrowDownRight,
      iconBg: "bg-rose-100",
      iconColor: "text-rose-600",
      progress: summary?.drop_off_rate ?? 0,
      variant: "default" as const,
    },
    {
      label: "Avg Study / Session",
      value: `${summary?.avg_study_time_per_session ?? 0} min`,
      sub: `${summary?.total_sessions ?? 0} total sessions`,
      icon: Zap,
      iconBg: "bg-amber-100",
      iconColor: "text-amber-600",
      progress: Math.min((summary?.avg_study_time_per_session ?? 0) / 60 * 100, 100),
      variant: "warning" as const,
    },
  ];

  const skillRows = skills.map((s) => ({
    ...s,
    ...skillStyle(s.skill),
  }));
  const maxSkillMinutes = Math.max(...skillRows.map((r) => r.study_minutes), 1);

  return (
    <DashboardLayout>
      <div className="space-y-8 pb-12">

        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Analytics Dashboard</h1>
            <p className="text-muted-foreground">Track views, completions, bookmarks, likes, ratings, and study time.</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 rounded-lg border border-border p-1">
              {[7, 30, 90].map((d) => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    days === d ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary"
                  }`}
                >
                  {d}D
                </button>
              ))}
            </div>
            <Button variant="outline" size="sm">
              <Download className="mr-2 h-4 w-4" /> Export
            </Button>
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

        {/* 2. Rate Metrics */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {rateCards.map((card) => (
            <Card key={card.label}>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-muted-foreground">{card.label}</p>
                  <div className={`p-2 rounded-lg ${card.iconBg} ${card.iconColor}`}>
                    <card.icon className="h-4 w-4" />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <h3 className="text-3xl font-bold">{card.value}</h3>
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">{card.sub}</p>
                <Progress value={card.progress} className="h-1.5 mt-3" variant={card.variant} />
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid gap-8 lg:grid-cols-3">

          {/* 3. Main Trend Chart */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Activity Trends</CardTitle>
                <CardDescription>Views, completions, and study minutes over the last {days} days.</CardDescription>
              </div>
              <BarChart3 className="h-5 w-5 text-muted-foreground" />
            </CardHeader>
            <CardContent className="pt-4">
              {trends.length === 0 || trends.every((t) => t.views === 0 && t.study_minutes === 0) ? (
                <div className="h-[280px] flex flex-col items-center justify-center text-center space-y-3">
                  <Activity className="h-8 w-8 text-muted-foreground" />
                  <p className="text-muted-foreground text-sm max-w-xs">
                    No activity yet. View resources and log study sessions to unlock your analytics.
                  </p>
                </div>
              ) : (
                <TrendChart series={trends} />
              )}
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-primary" /> Views
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> Study minutes
                </span>
              </div>
            </CardContent>
          </Card>

          {/* 4. Skill Breakdown */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" /> Skill Focus
              </CardTitle>
              <CardDescription>Study minutes by skill.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {skillRows.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center space-y-2">
                  <Info className="h-6 w-6 text-muted-foreground" />
                  <p className="text-xs text-muted-foreground max-w-[200px]">
                    Log study sessions to see your skill balance.
                  </p>
                </div>
              ) : (
                skillRows.slice(0, 6).map((row) => {
                  const Icon = row.icon;
                  return (
                    <div key={row.skill} className="space-y-2">
                      <div className="flex justify-between items-end">
                        <span className="flex items-center gap-1.5 text-xs font-bold">
                          <Icon className={`h-3.5 w-3.5 ${row.color}`} /> {row.label}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {row.study_minutes} min • {row.views} views
                        </span>
                      </div>
                      <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${Math.round((row.study_minutes / maxSkillMinutes) * 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>

        </div>

        {/* 5. Top Resources */}
        <Card>
          <CardHeader>
            <CardTitle>Top Performing Resources</CardTitle>
            <CardDescription>Resources ranked by views and completion rate.</CardDescription>
          </CardHeader>
          <CardContent>
            {topResources.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center space-y-3">
                <BookOpen className="h-8 w-8 text-muted-foreground" />
                <p className="text-muted-foreground text-sm max-w-sm">
                  No resource activity yet. View and complete resources to see performance data.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      <th className="text-left font-medium py-3 px-2">Resource</th>
                      <th className="text-left font-medium py-3 px-2">Type</th>
                      <th className="text-right font-medium py-3 px-2">Views</th>
                      <th className="text-right font-medium py-3 px-2">Completions</th>
                      <th className="text-right font-medium py-3 px-2">Bookmarks</th>
                      <th className="text-right font-medium py-3 px-2">Likes</th>
                      <th className="text-right font-medium py-3 px-2">Rating</th>
                      <th className="text-right font-medium py-3 px-2">Completion %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {topResources.slice(0, 8).map((r: ResourcePerformanceItem) => {
                      const style = skillStyle(r.skill);
                      const Icon = style.icon;
                      return (
                        <tr key={r.resource_id} className="group hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                          <td className="py-4 px-2">
                            <div className="flex items-center gap-2">
                              <span className={`p-1.5 rounded-lg ${style.bg} ${style.color}`}>
                                <Icon className="h-3.5 w-3.5" />
                              </span>
                              <span className="font-medium max-w-[200px] truncate">{r.title}</span>
                            </div>
                          </td>
                          <td className="py-4 px-2">
                            <Badge variant="secondary" className="text-[10px]">{r.type}</Badge>
                          </td>
                          <td className="py-4 px-2 text-right font-bold">{r.views}</td>
                          <td className="py-4 px-2 text-right">{r.completions}</td>
                          <td className="py-4 px-2 text-right">{r.bookmarks}</td>
                          <td className="py-4 px-2 text-right">{r.likes}</td>
                          <td className="py-4 px-2 text-right">
                            <span className="inline-flex items-center gap-1">
                              <Star className="h-3 w-3 text-amber-500 fill-amber-500" />
                              {r.avg_rating > 0 ? r.avg_rating.toFixed(1) : "—"}
                            </span>
                          </td>
                          <td className="py-4 px-2 text-right">
                            <Badge variant={r.completion_rate >= 50 ? "success" : "secondary"} className="text-[10px]">
                              {r.completion_rate}%
                            </Badge>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 6. Recent Events */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Your latest analytics events.</CardDescription>
          </CardHeader>
          <CardContent>
            {recentEvents.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center space-y-3">
                <Activity className="h-8 w-8 text-muted-foreground" />
                <p className="text-muted-foreground text-sm max-w-sm">
                  No events tracked yet. Your interactions will appear here.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {recentEvents.slice(0, 10).map((ev: AnalyticsEvent) => {
                  const props = ev.properties || {};
                  const isPositive = !ev.event.includes("un");
                  return (
                    <div key={ev.id} className="flex items-center gap-3 p-3 rounded-lg border border-border/50 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                      <div className={`p-2 rounded-lg ${isPositive ? "bg-emerald-100 text-emerald-600" : "bg-rose-100 text-rose-600"}`}>
                        {isPositive ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium">{formatEventName(ev.event)}</p>
                        <p className="text-[11px] text-muted-foreground">
                          {ev.entity_type ? `${ev.entity_type} • ` : ""}
                          {props.skill ? `${props.skill} • ` : ""}
                          {props.minutes ? `${props.minutes} min • ` : ""}
                          {props.rating ? `${props.rating}★ • ` : ""}
                          {formatDate(ev.timestamp)}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

      </div>
    </DashboardLayout>
  );
}