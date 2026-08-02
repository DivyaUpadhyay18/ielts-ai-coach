"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  BookOpen,
  PenTool,
  Mic,
  Bell,
  GraduationCap,
  Sparkles,
  Clock,
  Zap,
  CheckCircle2,
  XCircle,
  RefreshCw,
  AlertCircle,
  Target,
  ListChecks,
  Trophy,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { dailyMissionService } from "@/services/api";
import type { DailyMission, DailyMissionListResponse, MissionSkill } from "@/types";

// ─────────────────────────────────────────────────────────────
// Skill → icon/color mapping
// ─────────────────────────────────────────────────────────────
const SKILL_STYLES: Record<MissionSkill, { color: string; bg: string; icon: any; label: string }> = {
  reading: { color: "text-purple-600", bg: "bg-purple-100", icon: BookOpen, label: "Reading" },
  listening: { color: "text-amber-600", bg: "bg-amber-100", icon: Bell, label: "Listening" },
  writing: { color: "text-blue-600", bg: "bg-blue-100", icon: PenTool, label: "Writing" },
  speaking: { color: "text-teal-600", bg: "bg-teal-100", icon: Mic, label: "Speaking" },
  vocabulary: { color: "text-emerald-600", bg: "bg-emerald-100", icon: Sparkles, label: "Vocabulary" },
  grammar: { color: "text-rose-600", bg: "bg-rose-100", icon: GraduationCap, label: "Grammar" },
};

function skillStyle(skill: string): (typeof SKILL_STYLES)[MissionSkill] {
  return SKILL_STYLES[skill as MissionSkill] || {
    color: "text-slate-600",
    bg: "bg-slate-100",
    icon: Target,
    label: skill,
  };
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

// ─────────────────────────────────────────────────────────────
// Status badge helper
// ─────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  if (status === "completed") {
    return <Badge variant="success"><CheckCircle2 className="mr-1 h-3 w-3" /> Completed</Badge>;
  }
  if (status === "skipped") {
    return <Badge variant="secondary"><XCircle className="mr-1 h-3 w-3" /> Skipped</Badge>;
  }
  return <Badge variant="accent"><Clock className="mr-1 h-3 w-3" /> Pending</Badge>;
}

// ─────────────────────────────────────────────────────────────
// Single mission row
// ─────────────────────────────────────────────────────────────
function MissionCard({
  mission,
  onComplete,
  onSkip,
  busy,
}: {
  mission: DailyMission;
  onComplete: (id: string) => void;
  onSkip: (id: string) => void;
  busy: boolean;
}) {
  const style = skillStyle(mission.skill);
  const Icon = style.icon;
  const isDone = mission.status === "completed";
  const isSkipped = mission.status === "skipped";

  return (
    <Card className={`transition-all ${isDone ? "border-success/30 bg-success/5" : isSkipped ? "border-border opacity-70" : "hover:border-primary/40"}`}>
      <CardContent className="p-4 sm:p-5">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          {/* Icon */}
          <div className={`p-3 rounded-xl shrink-0 ${style.bg} ${style.color}`}>
            <Icon className="h-6 w-6" />
          </div>

          {/* Main content */}
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${style.bg} ${style.color}`}>
                {style.label}
              </span>
              <StatusBadge status={mission.status} />
            </div>
            <h3 className={`font-bold ${isDone ? "text-muted-foreground line-through" : "text-foreground"}`}>
              {mission.title}
            </h3>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" /> {mission.estimated_minutes} min
              </span>
              <span className="flex items-center gap-1">
                <Zap className="h-3.5 w-3.5 text-amber-500" /> {mission.xp_reward} XP
              </span>
              <span className="flex items-center gap-1">
                <Target className="h-3.5 w-3.5" /> {mission.completion_percent}% complete
              </span>
            </div>
          </div>

          {/* Progress + Actions */}
          <div className="sm:w-64 space-y-3">
            <Progress
              value={mission.completion_percent}
              variant={isDone ? "success" : isSkipped ? "default" : "accent"}
              className="h-2"
            />
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant={isDone ? "outline" : "success"}
                className="flex-1"
                disabled={busy || isDone || isSkipped}
                onClick={() => onComplete(mission.id)}
              >
                {isDone ? "Completed" : "Complete"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1"
                disabled={busy || isDone || isSkipped}
                onClick={() => onSkip(mission.id)}
              >
                Skip
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────
// Loading skeleton
// ─────────────────────────────────────────────────────────────
function MissionsSkeleton() {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-3">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-72 rounded-xl" />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────
export default function DailyMissionsPage() {
  const [data, setData] = useState<DailyMissionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const fetchMissions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await dailyMissionService.getToday();
      setData(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to load missions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMissions();
  }, [fetchMissions]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    try {
      await dailyMissionService.generate({ days: 7 });
      await fetchMissions();
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to generate missions");
    } finally {
      setGenerating(false);
    }
  }, [fetchMissions]);

  const handleComplete = useCallback(async (missionId: string) => {
    setBusyId(missionId);
    setError(null);
    try {
      await dailyMissionService.complete(missionId);
      await fetchMissions();
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to update mission");
    } finally {
      setBusyId(null);
    }
  }, [fetchMissions]);

  const handleSkip = useCallback(async (missionId: string) => {
    setBusyId(missionId);
    setError(null);
    try {
      await dailyMissionService.skip(missionId);
      await fetchMissions();
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to update mission");
    } finally {
      setBusyId(null);
    }
  }, [fetchMissions]);

  if (loading && !data) {
    return (
      <DashboardLayout>
        <MissionsSkeleton />
      </DashboardLayout>
    );
  }

  const missions = data?.missions ?? [];
  const summary = data?.summary;

  return (
    <DashboardLayout>
      <div className="space-y-8 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <ListChecks className="h-8 w-8 text-primary" /> Daily Missions
            </h1>
            <p className="text-muted-foreground">
              {summary ? formatDate(summary.mission_date) : "Your daily IELTS practice plan"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={handleGenerate}
              isLoading={generating}
              leftIcon={RefreshCw}
            >
              Generate 7 Days
            </Button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-3 rounded-xl border border-error/30 bg-error/5 p-4 text-error">
            <AlertCircle className="h-5 w-5" />
            <p className="text-sm font-medium flex-1">{error}</p>
            <Button variant="ghost" size="sm" onClick={fetchMissions}>Retry</Button>
          </div>
        )}

        {/* Summary cards */}
        {summary && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Completion</p>
                  <Target className="h-4 w-4 text-primary" />
                </div>
                <div className="mt-2 text-3xl font-black">{summary.completion_percent}%</div>
                <Progress value={summary.completion_percent} className="mt-3 h-2" variant={summary.completion_percent === 100 ? "success" : "accent"} />
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Missions</p>
                  <ListChecks className="h-4 w-4 text-primary" />
                </div>
                <div className="mt-2 text-3xl font-black">
                  {summary.completed_missions}<span className="text-sm font-normal text-muted-foreground"> / {summary.total_missions}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {summary.pending_missions} pending • {summary.skipped_missions} skipped
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Est. Time</p>
                  <Clock className="h-4 w-4 text-primary" />
                </div>
                <div className="mt-2 text-3xl font-black">
                  {summary.total_estimated_minutes} <span className="text-sm font-normal text-muted-foreground">min</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">Across all skill missions</p>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-amber-500/15 to-orange-500/5 border-amber-500/20">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">XP Today</p>
                  <Trophy className="h-4 w-4 text-amber-500" />
                </div>
                <div className="mt-2 text-3xl font-black">
                  {summary.earned_xp} <span className="text-sm font-normal text-muted-foreground">/ {summary.total_xp_reward} XP</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">Earned by completing missions</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Mission list */}
        {missions.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16 text-center space-y-4">
              <div className="p-4 rounded-full bg-primary/10 text-primary">
                <Sparkles className="h-8 w-8" />
              </div>
              <h3 className="text-xl font-bold">No missions generated yet</h3>
              <p className="text-muted-foreground max-w-sm">
                Generate placeholder missions for the next 7 days covering all six IELTS skills.
                This uses deterministic placeholder data — no AI scheduling.
              </p>
              <Button onClick={handleGenerate} isLoading={generating} leftIcon={RefreshCw}>
                Generate Missions
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold flex items-center gap-2">
                <ListChecks className="h-5 w-5 text-primary" /> Today&apos;s Missions
              </h2>
              <Badge variant="secondary">{missions.length} missions</Badge>
            </div>
            {missions.map((mission) => (
              <MissionCard
                key={mission.id}
                mission={mission}
                onComplete={handleComplete}
                onSkip={handleSkip}
                busy={busyId === mission.id}
              />
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

