"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Map as MapIcon,
  Calendar,
  Clock,
  Target,
  BookOpen,
  Flag,
  CheckCircle2,
  XCircle,
  AlertCircle,
  TrendingUp,
  Award,
  Zap,
  Flame,
  Loader2,
  RefreshCw,
  ChevronRight,
  PlayCircle,
  Lock,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardService, countdownService, dailyMissionService, timelineService, streakService, predictionService } from "@/services/api";
import type {
  DashboardOverview,
  ExamCountdown,
  DailyMissionListResponse,
  TimelineResponse,
  StreakOverviewResponse,
  PredictionResponse,
} from "@/types";

// ─────────────────────────────────────────────────────────────
// Helper Components
// ─────────────────────────────────────────────────────────────
function StatCard({ title, value, subtitle, icon: Icon, color = "text-primary" }: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: any;
  color?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>
            <p className={`text-3xl font-black ${color}`}>{value}</p>
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

// ─────────────────────────────────────────────────────────────
// Main Roadmap Page
// ─────────────────────────────────────────────────────────────
export default function RoadmapPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DashboardOverview | null>(null);
  const [countdown, setCountdown] = useState<ExamCountdown | null>(null);
  const [todayMissions, setTodayMissions] = useState<DailyMissionListResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [streak, setStreak] = useState<StreakOverviewResponse | null>(null);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);

  const fetchAllData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashboardData, countdownData, missionsData, timelineData, streakData, predictionData] = await Promise.all([
        dashboardService.getOverview(),
        countdownService.getCountdown(),
        dailyMissionService.getToday(),
        timelineService.getTimeline(),
        streakService.getOverview(),
        predictionService.getPrediction(),
      ]);
      setDashboard(dashboardData);
      setCountdown(countdownData);
      setTodayMissions(missionsData);
      setTimeline(timelineData);
      setStreak(streakData);
      setPrediction(predictionData);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to load roadmap data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  // Calculate current week info
  const currentWeek = useMemo(() => {
    if (!timeline || !timeline.days.length) return null;
    const today = timeline.days.find(d => d.is_today);
    if (!today) return null;
    
    const todayIndex = timeline.days.findIndex(d => d.is_today);
    const weekStart = Math.max(0, todayIndex - 3);
    const weekEnd = Math.min(timeline.days.length - 1, todayIndex + 3);
    const weekDays = timeline.days.slice(weekStart, weekEnd + 1);
    
    const weekTotal = weekDays.reduce((sum, d) => sum + d.total_tasks, 0);
    const weekCompleted = weekDays.reduce((sum, d) => sum + d.completed_tasks, 0);
    
    return {
      days: weekDays,
      total: weekTotal,
      completed: weekCompleted,
      percent: weekTotal > 0 ? Math.round((weekCompleted / weekTotal) * 100) : 0,
    };
  }, [timeline]);

  // Get upcoming mocks
  const upcomingMocks = useMemo(() => {
    if (!timeline) return [];
    return timeline.days
      .filter(d => d.mock_tests > 0 && !d.is_today)
      .slice(0, 3);
  }, [timeline]);

  // Get revision days
  const revisionDays = useMemo(() => {
    if (!timeline) return [];
    return timeline.days
      .filter(d => d.revision_tasks > 0)
      .slice(0, 5);
  }, [timeline]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6 pb-12">
          <Skeleton className="h-12 w-64" />
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
          <Button variant="ghost" size="sm" onClick={fetchAllData}>
            Retry
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <MapIcon className="h-8 w-8 text-primary" />
              Study Roadmap
            </h1>
            <p className="text-muted-foreground">
              {dashboard?.user?.full_name ? `${dashboard.user.full_name}'s` : "Your"} personalized IELTS preparation path
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchAllData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>

        {/* Top Stats Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Exam Countdown"
            value={countdown?.days_remaining ?? "—"}
            subtitle={countdown?.intensity || "days remaining"}
            icon={Calendar}
            color="text-red-600"
          />
          <StatCard
            title="Current Streak"
            value={streak?.daily?.current ?? 0}
            subtitle={`Longest: ${streak?.daily?.longest ?? 0} days`}
            icon={Flame}
            color="text-orange-600"
          />
          <StatCard
            title="Total XP"
            value={dashboard?.xp?.total ?? 0}
            subtitle={`Level ${dashboard?.xp?.level ?? 1}`}
            icon={Zap}
            color="text-amber-600"
          />
          <StatCard
            title="Completion"
            value={`${Math.round((dashboard?.progress?.daily?.percent ?? 0))}%`}
            subtitle={`${dashboard?.progress?.daily?.tasks_completed ?? 0}/${dashboard?.progress?.daily?.tasks_target ?? 0} tasks`}
            icon={Target}
            color="text-green-600"
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left Column: Calendar + Timeline */}
          <div className="lg:col-span-2 space-y-6">
            {/* Current Week */}
            {currentWeek && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Calendar className="h-5 w-5 text-primary" />
                    Current Week
                  </CardTitle>
                  <CardDescription>
                    {currentWeek.completed}/{currentWeek.total} tasks completed ({currentWeek.percent}%)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-7 gap-2">
                    {currentWeek.days.map((day) => (
                      <div
                        key={day.date}
                        className={`p-3 rounded-lg border text-center ${
                          day.is_today
                            ? "border-primary bg-primary/10 ring-2 ring-primary"
                            : day.is_exam_day
                            ? "border-red-300 bg-red-50"
                            : "border-border hover:border-primary/30"
                        }`}
                      >
                        <p className="text-[10px] font-medium text-muted-foreground mb-1">
                          {new Date(day.date).toLocaleDateString("en-US", { weekday: "short" })}
                        </p>
                        <p className="text-lg font-bold text-foreground">{new Date(day.date).getDate()}</p>
                        <div className="mt-2 space-y-1">
                          <p className="text-xs font-semibold text-foreground">{day.completion_percent}%</p>
                          <Progress value={day.completion_percent} className="h-1" />
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Timeline Overview */}
            {timeline && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-primary" />
                    Study Timeline
                  </CardTitle>
                  <CardDescription>
                    {timeline.total_days} days until exam • {countdown?.exam_date ? new Date(countdown.exam_date).toLocaleDateString() : ""}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {timeline.days.slice(0, 7).map((day) => (
                      <div
                        key={day.date}
                        className={`flex items-center justify-between p-3 rounded-lg border ${
                          day.is_today ? "border-primary bg-primary/5" : "border-border"
                        }`}
                      >
                        <div className="flex items-center gap-4">
                          <div>
                            <p className="text-sm font-semibold text-foreground">
                              {day.is_today ? "Today" : new Date(day.date).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {day.total_tasks} tasks • {day.total_minutes} min
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <p className="text-sm font-bold text-foreground">{day.completion_percent}%</p>
                            <p className="text-xs text-muted-foreground">
                              {day.completed_tasks}/{day.total_tasks}
                            </p>
                          </div>
                          <Progress value={day.completion_percent} className="w-16 h-2" />
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column: Missions, Mocks, Revision, Progress */}
          <div className="space-y-6">
            {/* Today's Missions */}
            {todayMissions && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Target className="h-5 w-5 text-primary" />
Today&apos;s Mission
                  </CardTitle>
                  <CardDescription>
                    {todayMissions.summary.completed_missions}/{todayMissions.summary.total_missions} completed
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {todayMissions.missions.slice(0, 4).map((mission) => (
                      <div key={mission.id} className="flex items-start gap-3">
                        <div className={`mt-0.5 h-2 w-2 rounded-full ${
                          mission.status === "completed" ? "bg-green-500" :
                          mission.status === "skipped" ? "bg-gray-400" : "bg-amber-500"
                        }`} />
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium ${
                            mission.status === "completed" ? "text-muted-foreground line-through" : "text-foreground"
                          }`}>
                            {mission.title}
                          </p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {mission.estimated_minutes} min • {mission.xp_reward} XP
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 pt-3 border-t border-border">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Progress</span>
                      <span className="font-bold text-foreground">{todayMissions.summary.completion_percent}%</span>
                    </div>
                    <Progress value={todayMissions.summary.completion_percent} className="h-2 mt-2" />
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Upcoming Mocks */}
            {upcomingMocks.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Flag className="h-5 w-5 text-red-600" />
                    Upcoming Mock Tests
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {upcomingMocks.map((day) => (
                      <div key={day.date} className="flex items-center justify-between p-3 bg-red-50 rounded-lg border border-red-200">
                        <div>
                          <p className="text-sm font-semibold text-red-900">
                            {new Date(day.date).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                          </p>
                          <p className="text-xs text-red-700 mt-0.5">
                            {day.mock_tests} mock test{day.mock_tests !== 1 ? "s" : ""} • {day.total_minutes} min
                          </p>
                        </div>
                        <Badge variant="destructive" className="text-[10px]">
                          Mock
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Revision Days */}
            {revisionDays.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <BookOpen className="h-5 w-5 text-blue-600" />
                    Revision Days
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {revisionDays.map((day) => (
                      <div key={day.date} className="flex items-center justify-between p-3 bg-blue-50 rounded-lg border border-blue-200">
                        <div>
                          <p className="text-sm font-semibold text-blue-900">
                            {new Date(day.date).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                          </p>
                          <p className="text-xs text-blue-700 mt-0.5">
                            {day.revision_tasks} revision task{day.revision_tasks !== 1 ? "s" : ""}
                          </p>
                        </div>
                        <Badge variant="outline" className="text-[10px] border-blue-300 text-blue-700">
                          Revision
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Progress & XP */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Award className="h-5 w-5 text-amber-600" />
                  Progress & Achievements
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-muted-foreground">Overall Completion</span>
                    <span className="font-bold text-foreground">
                      {Math.round(dashboard?.progress?.daily?.percent ?? 0)}%
                    </span>
                  </div>
                  <Progress value={dashboard?.progress?.daily?.percent ?? 0} className="h-2" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                    <p className="text-2xl font-bold text-amber-700">{dashboard?.xp?.total ?? 0}</p>
                    <p className="text-xs text-amber-600">Total XP</p>
                  </div>
                  <div className="p-3 bg-orange-50 rounded-lg border border-orange-200">
                    <p className="text-2xl font-bold text-orange-700">{streak?.daily?.current ?? 0}</p>
                    <p className="text-xs text-orange-600">Day Streak</p>
                  </div>
                </div>
                {prediction && (
                  <div className="pt-3 border-t border-border">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Predicted Band</span>
                      <span className="text-lg font-bold text-primary">{prediction.estimated_band.toFixed(1)}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {prediction.risk_level} risk • {prediction.readiness_score}% ready
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
