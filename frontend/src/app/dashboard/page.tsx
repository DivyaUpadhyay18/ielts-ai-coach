"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  TrendingUp,
  Calendar,
  Target,
  Flame,
  Clock,
  ArrowRight,
  PenTool,
  Mic,
  CheckCircle2,
  AlertCircle,
  Zap,
  Trophy,
  BarChart3,
  BookOpen,
  Sparkles,
  Bell,
  Award,
  ChevronRight,
  ListChecks,
  GraduationCap,
  Star,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardService, dailyMissionService, schedulerService } from "@/services/api";
import type {
  DashboardOverview,
  MissionTask,
  SchedulerAdjustment,
  SchedulerRunPayload,
} from "@/types";

// ─────────────────────────────────────────────────────────────
// Skill → color/icon mapping helper
// ─────────────────────────────────────────────────────────────
const SKILL_STYLES: Record<string, { color: string; bg: string; icon: any }> = {
  writing: { color: "text-blue-600", bg: "bg-blue-100", icon: PenTool },
  speaking: { color: "text-teal-600", bg: "bg-teal-100", icon: Mic },
  reading: { color: "text-purple-600", bg: "bg-purple-100", icon: BookOpen },
  listening: { color: "text-amber-600", bg: "bg-amber-100", icon: Bell },
  vocabulary: { color: "text-emerald-600", bg: "bg-emerald-100", icon: BookOpen },
  grammar: { color: "text-rose-600", bg: "bg-rose-100", icon: GraduationCap },
  mock: { color: "text-indigo-600", bg: "bg-indigo-100", icon: Trophy },
  general: { color: "text-slate-600", bg: "bg-slate-100", icon: Star },
};

function skillStyle(skill: string) {
  return SKILL_STYLES[skill] || SKILL_STYLES.general;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

// ─────────────────────────────────────────────────────────────
// Skeleton loading block
// ─────────────────────────────────────────────────────────────
function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-36 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-8">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
        <div className="space-y-8">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Zone 1 — Goal Cluster (top row)
// ─────────────────────────────────────────────────────────────
function StatCard({
  label,
  icon: Icon,
  value,
  sub,
  highlight = false,
  iconBg = "bg-primary/10",
  iconColor = "text-primary",
}: {
  label: string;
  icon: any;
  value: React.ReactNode;
  sub?: React.ReactNode;
  highlight?: boolean;
  iconBg?: string;
  iconColor?: string;
}) {
  return (
    <Card className={highlight ? "bg-gradient-to-br from-primary to-blue-700 text-white border-none shadow-lg" : ""}>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <p className={`text-xs font-semibold uppercase tracking-wider ${highlight ? "text-white/70" : "text-muted-foreground"}`}>
            {label}
          </p>
          <div className={`p-2 rounded-lg ${highlight ? "bg-white/15 text-white" : iconBg + " " + iconColor}`}>
            <Icon className="h-4 w-4" />
          </div>
        </div>
        <div className={`mt-2 text-3xl font-black ${highlight ? "text-white" : ""}`}>{value}</div>
        {sub && <div className={`mt-1 text-xs ${highlight ? "text-white/70" : "text-muted-foreground"}`}>{sub}</div>}
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────
// Zone 2 — Action Surface
// ─────────────────────────────────────────────────────────────
function MissionTaskItem({ task, onToggle }: { task: MissionTask; onToggle: (id: string) => void }) {
  const style = skillStyle(task.skill);
  const Icon = style.icon;
  return (
    <div className="flex items-start space-x-3 py-2">
      <button
        type="button"
        onClick={() => onToggle(task.id)}
        aria-label={task.completed ? "Mark as incomplete" : "Mark as complete"}
        className={`mt-0.5 h-5 w-5 shrink-0 rounded-full border-2 flex items-center justify-center transition-colors cursor-pointer ${
          task.completed ? "bg-success border-success text-white" : "border-muted-foreground/30 hover:border-primary"
        }`}
      >
        {task.completed && <CheckCircle2 className="h-3 w-3" />}
      </button>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium ${task.completed ? "text-muted-foreground line-through" : "text-foreground"}`}>
          {task.title}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded ${style.bg} ${style.color}`}>
            <Icon className="h-2.5 w-2.5" />
            {task.skill}
          </span>
          <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
            <Clock className="h-2.5 w-2.5" /> {task.duration_minutes} min
          </span>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Daily Mission row (compact — for dashboard preview)
// ─────────────────────────────────────────────────────────────
function DailyMissionRow({
  mission,
  onComplete,
  onSkip,
  busy,
}: {
  mission: any;
  onComplete: (id: string) => void;
  onSkip: (id: string) => void;
  busy: boolean;
}) {
  const style = skillStyle(mission.skill);
  const Icon = style.icon;
  const isDone = mission.status === "completed";
  const isSkipped = mission.status === "skipped";

  return (
    <div className={`flex items-center space-x-3 py-2.5 ${isDone ? "opacity-70" : ""}`}>
      <div className={`p-2 rounded-lg shrink-0 ${style.bg} ${style.color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className={`text-sm font-medium truncate ${isDone ? "text-muted-foreground line-through" : isSkipped ? "text-muted-foreground" : "text-foreground"}`}>
            {mission.title}
          </p>
          {isDone && <CheckCircle2 className="h-3.5 w-3.5 text-success shrink-0" />}
          {isSkipped && <XCircleIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
            <Clock className="h-2.5 w-2.5" /> {mission.estimated_minutes} min
          </span>
          <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
            <Zap className="h-2.5 w-2.5 text-amber-500" /> {mission.xp_reward} XP
          </span>
          <span className="text-[10px] text-muted-foreground">{mission.completion_percent}%</span>
        </div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <Button
          size="sm"
          variant={isDone ? "outline" : "ghost"}
          className="h-7 px-2 text-[11px]"
          disabled={busy || isDone || isSkipped}
          onClick={() => onComplete(mission.id)}
        >
          {isDone ? "Done" : "Complete"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-[11px] text-muted-foreground"
          disabled={busy || isDone || isSkipped}
          onClick={() => onSkip(mission.id)}
        >
          Skip
        </Button>
      </div>
    </div>
  );
}

const XCircleIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />
  </svg>
);

// ─────────────────────────────────────────────────────────────
// Adaptive Scheduler panel ("What changed today")
// ─────────────────────────────────────────────────────────────
function actionStyles(action: string): { label: string; className: string } {
  switch (action) {
    case "carried_forward":
      return { label: "Carried Forward", className: "bg-amber-100 text-amber-700" };
    case "rescheduled":
      return { label: "Rescheduled", className: "bg-blue-100 text-blue-700" };
    case "deprioritized":
      return { label: "Deprioritized", className: "bg-slate-200 text-slate-600" };
    case "spread":
      return { label: "Spread", className: "bg-teal-100 text-teal-700" };
    case "merged":
      return { label: "Merged", className: "bg-purple-100 text-purple-700" };
    default:
      return { label: "Kept", className: "bg-muted text-muted-foreground" };
  }
}

function SchedulerAdjustmentBadge({ action }: { action: string }) {
  const { label, className } = actionStyles(action);
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${className}`}>
      {label}
    </span>
  );
}

function SchedulerPanel({
  scheduler,
  loading,
  onRunScheduler,
}: {
  scheduler: SchedulerRunPayload | null;
  loading: boolean;
  onRunScheduler: () => void;
}) {
  const metrics = scheduler?.metrics;
  const adjustments = (scheduler?.adjustments ?? []) as SchedulerAdjustment[];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-sm flex items-center">
            <SpinnerLike className="mr-2 h-4 w-4 text-primary" /> Adaptive Schedule
          </CardTitle>
          <CardDescription>What changed today &amp; why</CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="h-8 px-2 text-[11px]"
          onClick={onRunScheduler}
          disabled={loading}
        >
          {loading ? "Running..." : "Run Now"}
        </Button>
      </CardHeader>
      <CardContent>
        {loading && !scheduler ? (
          <div className="space-y-3">
            <Skeleton className="h-4 w-full rounded" />
            <Skeleton className="h-4 w-4/5 rounded" />
            <Skeleton className="h-4 w-3/5 rounded" />
          </div>
        ) : !scheduler || !scheduler.run ? (
          <p className="text-xs text-muted-foreground leading-relaxed">
            {scheduler?.summary || "No scheduler runs yet. Run the adaptive scheduler to rebalance your study plan automatically."}
          </p>
        ) : (
          <div className="space-y-4">
            {/* Summary strip */}
            <div className="rounded-lg bg-primary/5 border border-primary/10 p-3">
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {scheduler.summary || "Your plan was rebalanced based on yesterday's progress."}
              </p>
            </div>

            {/* Key metrics */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg border border-border p-2">
                <div className="text-lg font-black">{metrics?.carried_forward ?? 0}</div>
                <div className="text-[9px] uppercase tracking-wider text-muted-foreground">Carried</div>
              </div>
              <div className="rounded-lg border border-border p-2">
                <div className="text-lg font-black">{metrics?.rescheduled ?? 0}</div>
                <div className="text-[9px] uppercase tracking-wider text-muted-foreground">Moved</div>
              </div>
              <div className="rounded-lg border border-border p-2">
                <div className="text-lg font-black">{metrics?.deprioritized ?? 0}</div>
                <div className="text-[9px] uppercase tracking-wider text-muted-foreground">Lowered</div>
              </div>
            </div>

            {/* Workload progress */}
            <div>
              <div className="flex items-center justify-between text-[11px] mb-1">
                <span className="text-muted-foreground">Daily workload</span>
                <span className="font-semibold">
                  {Math.round(metrics?.workload_percent ?? 0)}%
                </span>
              </div>
              <Progress value={Math.min(metrics?.workload_percent ?? 0, 100)} className="h-1.5" variant="accent" />
            </div>

            {/* Adjustments list */}
            {adjustments.length > 0 && (
              <div className="divide-y divide-border">
                {adjustments.slice(0, 4).map((adj) => {
                  const title = adj.task_title || "Task";
                  return (
                    <div key={adj.id} className="py-2">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-medium truncate">{title}</p>
                        <SchedulerAdjustmentBadge action={adj.action} />
                      </div>
                      {adj.reason && (
                        <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2">{adj.reason}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const SpinnerLike = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
  </svg>
);

// ─────────────────────────────────────────────────────────────
// Page Component
// ─────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const overview = await dashboardService.getOverview();
      setData(overview);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Optimistic task toggle (visual only — server persistence arrives with scheduler)
  const handleToggleTask = useCallback((taskId: string) => {
    setData((prev) => {
      if (!prev) return prev;
      const tasks = prev.mission.tasks.map((t) =>
        t.id === taskId ? { ...t, completed: !t.completed } : t
      );
      const completed = tasks.filter((t) => t.completed).length;
      const percent = tasks.length > 0 ? Math.round((completed / tasks.length) * 100) : 0;
      return {
        ...prev,
        mission: { ...prev.mission, tasks, completed_tasks: completed, total_tasks: tasks.length },
        progress: {
          ...prev.progress,
          daily: { ...prev.progress.daily, tasks_completed: completed, tasks_target: tasks.length, percent },
        },
      };
    });
  }, []);

  // ── Adaptive Scheduler state ──────────────────────────────────
  const [scheduler, setScheduler] = useState<SchedulerRunPayload | null>(null);
  const [schedulerLoading, setSchedulerLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const loadScheduler = async () => {
      try {
        const latest = await schedulerService.getLatest();
        if (!cancelled) setScheduler(latest);
      } catch {
        if (!cancelled) setScheduler(null);
      } finally {
        if (!cancelled) setSchedulerLoading(false);
      }
    };
    loadScheduler();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleRunScheduler = useCallback(async () => {
    setSchedulerLoading(true);
    try {
      const result = await schedulerService.run("app_open");
      setScheduler(result);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to run scheduler");
    } finally {
      setSchedulerLoading(false);
    }
  }, []);

  // ── Daily Mission persistence handlers (server-backed) ─────────
  const [missionBusyId, setMissionBusyId] = useState<string | null>(null);

  const refreshDailyMissions = useCallback(async () => {
    try {
      const today = await dailyMissionService.getToday();
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          daily_missions: {
            mission_date: today.summary.mission_date,
            missions: today.missions,
            summary: today.summary,
            generated: today.missions.length > 0,
            note: "Missions are placeholder-generated (no AI scheduling).",
          },
        };
      });
    } catch {
      // Keep existing data; a later refetch will reconcile.
    }
  }, []);

  const handleCompleteMission = useCallback(async (missionId: string) => {
    setMissionBusyId(missionId);
    try {
      await dailyMissionService.complete(missionId);
      await refreshDailyMissions();
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to update mission");
    } finally {
      setMissionBusyId(null);
    }
  }, [refreshDailyMissions]);

  const handleSkipMission = useCallback(async (missionId: string) => {
    setMissionBusyId(missionId);
    try {
      await dailyMissionService.skip(missionId);
      await refreshDailyMissions();
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to update mission");
    } finally {
      setMissionBusyId(null);
    }
  }, [refreshDailyMissions]);

  if (loading) {
    return (
      <DashboardLayout>
        <DashboardSkeleton />
      </DashboardLayout>
    );
  }

  if (error || !data) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center py-32 text-center space-y-4">
          <div className="p-4 rounded-full bg-error/10 text-error">
            <AlertCircle className="h-10 w-10" />
          </div>
          <h2 className="text-2xl font-bold">Unable to load your dashboard</h2>
          <p className="text-muted-foreground max-w-md">{error || "Something went wrong."}</p>
          <Button onClick={fetchDashboard}>Retry</Button>
        </div>
      </DashboardLayout>
    );
  }

  const {
    message,
    countdown,
    current_band,
    target_band,
    predicted_band,
    mission,
    progress,
    study_time,
    xp,
    streak,
    daily_goal,
    weekly_goal,
    continue_learning,
    upcoming_mock,
    recent_activity,
    notifications,
  } = data;

  // Intensity badge config
  const intensityMap: Record<string, { label: string; variant: any }> = {
    normal: { label: "Steady Pace", variant: "secondary" },
    focused: { label: "Focused Prep", variant: "outline" },
    intensive: { label: "Intensive Mode", variant: "warning" },
    final: { label: "Final Stretch", variant: "destructive" },
  };
  const intensity = countdown.intensity ? intensityMap[countdown.intensity] : null;

  return (
    <DashboardLayout>
      <div className="space-y-8 pb-12">
        {/* ─────────────────────────────── */}
        {/* Header Row */}
        {/* ─────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight">{message.greeting}</h1>
            <p className="text-muted-foreground">{message.text}</p>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/notifications">
              <Button variant="outline" size="sm" className="relative">
                <Bell className="mr-2 h-4 w-4" />
                Notifications
                {notifications.unread_count > 0 && (
                  <span className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-error text-white text-[10px] font-bold flex items-center justify-center">
                    {notifications.unread_count}
                  </span>
                )}
              </Button>
            </Link>
            <Link href="/roadmap">
              <Button size="sm" rightIcon={ArrowRight}>
                View Full Roadmap
              </Button>
            </Link>
          </div>
        </div>

        {/* ─────────────────────────────── */}
        {/* ZONE 1 — Goal Cluster */}
        {/* ─────────────────────────────── */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          {/* Exam Countdown */}
          <StatCard
            label="Exam Countdown"
            icon={Calendar}
            value={countdown.exam_set ? `${countdown.days_left} Days` : "—"}
            sub={
              countdown.exam_set ? (
                <span className="inline-flex items-center gap-2">
                  {formatDate(countdown.exam_date)}
                  {intensity && <Badge variant={intensity.variant} className="text-[9px] h-4">{intensity.label}</Badge>}
                </span>
              ) : (
                "Set your exam date in onboarding"
              )
            }
          />

          {/* Current Band */}
          <StatCard
            label="Current Band"
            icon={TrendingUp}
            value={current_band ?? "—"}
            sub={current_band ? "From diagnostic baseline" : "Take your diagnostic"}
          />

          {/* Target Band */}
          <StatCard
            label="Target Band"
            icon={Target}
            value={target_band ?? "—"}
            sub={current_band && target_band ? `${Math.max((target_band - current_band), 0).toFixed(1)} band gap to close` : "Set in onboarding"}
            highlight
            iconBg="bg-white/15"
            iconColor="text-white"
          />

          {/* Predicted Band */}
          <StatCard
            label="Predicted Band"
            icon={Sparkles}
            value={predicted_band.band ?? "—"}
            sub={predicted_band.band ? `${predicted_band.confidence}% confidence` : predicted_band.note}
          />

          {/* Streak */}
          <StatCard
            label="Study Streak"
            icon={Flame}
            value={streak.current > 0 ? `${streak.current} days` : "0 days"}
            sub={
              streak.current > 0
                ? `Longest: ${streak.longest} days`
                : streak.note
            }
            iconBg="bg-orange-100"
            iconColor="text-orange-600"
          />
        </div>

        {/* ─────────────────────────────── */}
        {/* ZONE 2 + ZONE 3 Layout */}
        {/* ─────────────────────────────── */}
        <div className="grid gap-8 lg:grid-cols-3">
          {/* ════════════════ LEFT (Action Surface) ════════════════ */}
          <div className="lg:col-span-2 space-y-8">
            {/* Today's Mission */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="flex items-center">
                    <ListChecks className="mr-2 h-5 w-5 text-primary" />
                    Today&apos;s Mission
                  </CardTitle>
                  <CardDescription>
                    {mission.has_plan ? mission.phase_title : "No study plan yet"}
                    {mission.phase_title && ` • ${mission.completed_tasks}/${mission.total_tasks} complete`}
                  </CardDescription>
                </div>
                <Badge variant={mission.completed_tasks === mission.total_tasks && mission.total_tasks > 0 ? "success" : "accent"}>
                  {mission.total_tasks > 0 && mission.completed_tasks === mission.total_tasks
                    ? "All Done!"
                    : `${mission.completed_tasks}/${mission.total_tasks}`}
                </Badge>
              </CardHeader>
              <CardContent>
                {!mission.has_plan ? (
                  <div className="flex flex-col items-center py-8 text-center space-y-4">
                    <div className="p-4 rounded-full bg-primary/10 text-primary">
                      <MapIcon className="h-8 w-8" />
                    </div>
                    <p className="text-muted-foreground max-w-sm">
                      Complete onboarding and the diagnostic test to unlock your personalized daily mission.
                    </p>
                    <Link href="/diagnostic">
                      <Button>Take Diagnostic Test</Button>
                    </Link>
                  </div>
                ) : mission.tasks.length === 0 ? (
                  <div className="flex items-center justify-center py-8 text-center space-y-2 flex-col">
                    <p className="text-muted-foreground">No tasks in this phase yet.</p>
                    <Link href="/roadmap">
                      <Button variant="outline" size="sm">View Roadmap</Button>
                    </Link>
                  </div>
                ) : (
                  <>
                    <div className="divide-y divide-border">
                      {mission.tasks.map((task) => (
                        <MissionTaskItem key={task.id} task={task} onToggle={handleToggleTask} />
                      ))}
                    </div>
                    <Link href="/roadmap">
                      <Button variant="ghost" className="w-full mt-4 text-xs">
                        View All Tasks <ChevronRight className="ml-1 h-3 w-3" />
                      </Button>
                    </Link>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Continue Learning */}
            <Card className="bg-gradient-to-br from-slate-900 to-slate-800 text-white border-none shadow-lg">
              <CardContent className="pt-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 rounded-xl bg-white/10 text-accent">
                      <PlayCircle className="h-7 w-7" />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg flex items-center gap-2">
                        {continue_learning.has_item ? "Continue Learning" : "Ready to Start"}
                      </h3>
                      <p className="text-sm text-slate-400">
                        {continue_learning.has_item
                          ? continue_learning.title
                          : "You're all caught up! Great job today."}
                      </p>
                    </div>
                  </div>
                  {continue_learning.has_item && (
                    <Link href={continue_learning.type === "speaking" ? "/speaking" : "/writing"}>
                      <Button variant="accent" className="w-full md:w-auto">
                        Resume <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
                    </Link>
                  )}
                </div>
                {continue_learning.has_item && continue_learning.duration_minutes && (
                  <div className="mt-4 flex items-center gap-2 text-xs text-slate-400">
                    <Clock className="h-3.5 w-3.5" /> Est. {continue_learning.duration_minutes} min
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Quick Actions */}
            <div className="grid gap-4 sm:grid-cols-2">
              <Link href="/writing">
                <Card className="hover:border-primary/50 cursor-pointer transition-colors group">
                  <CardContent className="pt-6">
                    <div className="flex items-center space-x-4">
                      <div className="p-3 rounded-xl bg-blue-100 text-blue-600 group-hover:bg-primary group-hover:text-white transition-colors">
                        <PenTool className="h-6 w-6" />
                      </div>
                      <div>
                        <h3 className="font-bold">Writing Practice</h3>
                        <p className="text-xs text-muted-foreground">Grade your Task 1 & 2 essays</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
              <Link href="/speaking">
                <Card className="hover:border-accent/50 cursor-pointer transition-colors group">
                  <CardContent className="pt-6">
                    <div className="flex items-center space-x-4">
                      <div className="p-3 rounded-xl bg-teal-100 text-teal-600 group-hover:bg-accent group-hover:text-white transition-colors">
                        <Mic className="h-6 w-6" />
                      </div>
                      <div>
                        <h3 className="font-bold">Speaking Coach</h3>
                        <p className="text-xs text-muted-foreground">Practice with AI Examiner</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </div>

            {/* Study Time + Daily Goal */}
            <div className="grid gap-4 sm:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center">
                    <Clock className="mr-2 h-4 w-4 text-primary" /> Study Time Today
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold">
                    {study_time.today_minutes} <span className="text-sm font-normal text-muted-foreground">min</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Budget: {study_time.budget_minutes} min/day</p>
                  <Progress value={study_time.today_minutes > 0 ? Math.min((study_time.today_minutes / study_time.budget_minutes) * 100, 100) : 0} className="mt-3 h-2" variant="accent" />
                  {!study_time.today_minutes && (
                    <p className="text-[10px] text-muted-foreground mt-2 italic">{study_time.tracking_note}</p>
                  )}
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-accent/10 to-transparent border-accent/20">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center">
                    <Target className="mr-2 h-4 w-4 text-accent" /> Daily Goal
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold">
                    {daily_goal.completed_minutes} <span className="text-sm font-normal text-muted-foreground">/ {daily_goal.target_minutes} min</span>
                  </div>
                  <Progress value={daily_goal.percent} className="mt-3 h-2" variant="success" />
                </CardContent>
              </Card>
            </div>

            {/* Recent Activity */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <BarChart3 className="mr-2 h-5 w-5 text-primary" /> Recent Activity
                </CardTitle>
                <CardDescription>Your latest assessments and milestones.</CardDescription>
              </CardHeader>
              <CardContent>
                {recent_activity.length === 0 ? (
                  <div className="flex items-center justify-center py-8 text-center">
                    <p className="text-muted-foreground text-sm">
                      No assessments yet. Complete your first writing or speaking practice to see activity here.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {recent_activity.slice(0, 5).map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between border-b border-border pb-3 last:border-0 last:pb-0">
                        <div className="flex items-center space-x-3">
                          <div className={`p-2 rounded-lg ${item.type === "assessment" ? "bg-blue-50 text-blue-500" : "bg-slate-100 text-slate-500"}`}>
                            {item.type === "assessment" ? <PenTool className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                          </div>
                          <div>
                            <p className="text-sm font-medium leading-none">{item.title}</p>
                            <p className="text-xs text-muted-foreground mt-1">{item.meta} • {formatDate(item.created_at)}</p>
                          </div>
                        </div>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* ════════════════ RIGHT (Progress Rail) ════════════════ */}
          <div className="space-y-8">
            {/* Daily Missions Card */}
            <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm flex items-center">
                    <Zap className="mr-2 h-4 w-4 text-primary" /> Daily Missions
                  </CardTitle>
                  <CardDescription>
                    {data.daily_missions && data.daily_missions.missions.length > 0
                      ? `${data.daily_missions.summary.completed_missions}/${data.daily_missions.summary.total_missions} complete`
                      : "Generate today's missions"}
                  </CardDescription>
                </div>
                <Link href="/missions">
                  <Button variant="ghost" size="sm" className="h-8 px-2 text-[11px]">
                    View All <ChevronRight className="ml-1 h-3 w-3" />
                  </Button>
                </Link>
              </CardHeader>
              <CardContent>
                {data.daily_missions && data.daily_missions.missions.length > 0 ? (
                  <>
                    <div className="divide-y divide-border">
                      {data.daily_missions.missions.slice(0, 4).map((m: any) => (
                        <DailyMissionRow
                          key={m.id}
                          mission={m}
                          onComplete={handleCompleteMission}
                          onSkip={handleSkipMission}
                          busy={missionBusyId === m.id}
                        />
                      ))}
                    </div>
                    {data.daily_missions.missions.length > 4 && (
                      <Link href="/missions">
                        <Button variant="ghost" className="w-full mt-2 text-xs">
                          +{data.daily_missions.missions.length - 4} more missions
                        </Button>
                      </Link>
                    )}
                  </>
                ) : (
                  <div className="flex flex-col items-center py-6 text-center space-y-3">
                    <Sparkles className="h-6 w-6 text-primary" />
                    <p className="text-xs text-muted-foreground max-w-[200px]">
                      No missions for today yet. Generate placeholder missions covering all six IELTS skills.
                    </p>
                    <Link href="/missions">
                      <Button size="sm" className="h-8 text-xs">Generate Missions</Button>
                    </Link>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Adaptive Scheduler Panel */}
            <SchedulerPanel
              scheduler={scheduler}
              loading={schedulerLoading}
              onRunScheduler={handleRunScheduler}
            />

            {/* XP Card */}
            <Card className="bg-gradient-to-br from-amber-500/15 to-orange-500/5 border-amber-500/20">
              <CardHeader>
                <CardTitle className="text-sm flex items-center">
                  <Zap className="mr-2 h-4 w-4 text-amber-500" /> Today&apos;s XP
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-end justify-between">
                  <div>
                    <div className="text-3xl font-black">{xp.today} <span className="text-sm font-normal text-muted-foreground">/ {xp.daily_target} XP</span></div>
                    <p className="text-xs text-muted-foreground mt-1">Level {xp.level}</p>
                  </div>
                  <div className="text-right">
                    <Award className="h-8 w-8 text-amber-500 mx-auto" />
                  </div>
                </div>
                <Progress value={xp.level_progress} className="mt-3 h-2" variant="warning" />
                {xp.note && <p className="text-[10px] text-muted-foreground mt-2 italic">{xp.note}</p>}
              </CardContent>
            </Card>

            {/* Weekly Goal */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center">
                  <Trophy className="mr-2 h-4 w-4 text-primary" /> Weekly Goal
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Study minutes</span>
                  <span className="font-bold">{weekly_goal.completed_minutes} / {weekly_goal.target_minutes}</span>
                </div>
                <Progress value={weekly_goal.percent} className="mt-2 h-2 mb-3" />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Tasks</span>
                  <span className="font-bold">{weekly_goal.completed_tasks} / {weekly_goal.target_tasks}</span>
                </div>
                <Progress value={weekly_goal.target_tasks > 0 ? Math.min((weekly_goal.completed_tasks / weekly_goal.target_tasks) * 100, 100) : 0} className="mt-2 h-2" variant="accent" />
              </CardContent>
            </Card>

            {/* Upcoming Mock Test */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center">
                  <Trophy className="mr-2 h-4 w-4 text-indigo-500" /> Upcoming Mock Test
                </CardTitle>
              </CardHeader>
              <CardContent>
                {upcoming_mock.has_mock ? (
                  <div>
                    <p className="font-bold text-lg">Mock Test #1</p>
                    <p className="text-xs text-muted-foreground mt-1">Full IELTS Simulation</p>
                    <Button size="sm" className="mt-4 w-full" variant="outline">View Details</Button>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground leading-relaxed">{upcoming_mock.note}</p>
                )}
              </CardContent>
            </Card>

            {/* Notifications Preview */}
            {notifications.items.length > 0 && (
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-sm flex items-center">
                    <Bell className="mr-2 h-4 w-4 text-primary" /> Notifications
                  </CardTitle>
                  <Badge variant="secondary" className="text-[10px]">{notifications.unread_count} unread</Badge>
                </CardHeader>
                <CardContent className="space-y-3">
                  {notifications.items.slice(0, 3).map((n) => (
                    <div key={n.id} className={`p-3 rounded-lg border ${n.is_read ? "border-border bg-background" : "border-primary/30 bg-primary/5"}`}>
                      <p className="text-xs font-bold">{n.title}</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">{n.body}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Motivational / Quick Tip */}
            <Card className="bg-gradient-to-br from-primary/10 to-accent/10 border-primary/20">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <span className="text-xs font-bold uppercase tracking-wider">AI Coach Tip</span>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {predicted_band.band
                    ? `You're tracking at Band ${predicted_band.band} (${predicted_band.confidence}% confidence). ${predicted_band.note}`
                    : predicted_band.note}
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

// Inline icon used above (kept local to avoid extra imports at top)
const MapIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
    <line x1="8" y1="2" x2="8" y2="18" />
    <line x1="16" y1="6" x2="16" y2="22" />
  </svg>
);

const PlayCircle = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polygon points="10 8 16 12 10 16 10 8" />
  </svg>
);

