"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  Clock,
  Target,
  BookOpen,
  Bell,
  PenTool,
  Mic,
  Sparkles,
  GraduationCap,
  CheckCircle2,
  XCircle,
  AlertCircle,
  TrendingUp,
  Award,
  Flag,
  Loader2,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { timelineService } from "@/services/api";
import type { TimelineResponse, TimelineDay, TimelineTask } from "@/types";

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
};

const TASK_TYPE_COLORS: Record<string, string> = {
  full_mock: "bg-red-100 text-red-700 border-red-200",
  mock_section: "bg-orange-100 text-orange-700 border-orange-200",
  revision: "bg-blue-100 text-blue-700 border-blue-200",
  review: "bg-indigo-100 text-indigo-700 border-indigo-200",
  practice: "bg-green-100 text-green-700 border-green-200",
  default: "bg-gray-100 text-gray-700 border-gray-200",
};

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-100 text-green-700 border-green-200",
  pending: "bg-yellow-100 text-yellow-700 border-yellow-200",
  in_progress: "bg-blue-100 text-blue-700 border-blue-200",
  missed: "bg-red-100 text-red-700 border-red-200",
  skipped: "bg-gray-100 text-gray-700 border-gray-200",
};

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────
function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function getTaskTypeColor(taskType: string): string {
  return TASK_TYPE_COLORS[taskType] || TASK_TYPE_COLORS.default;
}

function getStatusColor(status: string): string {
  return STATUS_COLORS[status] || STATUS_COLORS.pending;
}

// ─────────────────────────────────────────────────────────────
// Task Card Component
// ─────────────────────────────────────────────────────────────
function TaskCard({ task }: { task: TimelineTask }) {
  const skillStyle = SKILL_STYLES[task.skill] || SKILL_STYLES.reading;
  const Icon = skillStyle.icon;
  const isCompleted = task.status === "completed";
  const isMissed = task.status === "missed";

  return (
    <div
      className={`p-3 rounded-lg border transition-all ${
        isCompleted
          ? "border-green-200 bg-green-50/50"
          : isMissed
          ? "border-red-200 bg-red-50/50"
          : "border-gray-200 bg-white hover:border-primary/30"
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Skill Icon */}
        <div className={`p-2 rounded-lg shrink-0 ${skillStyle.bg} ${skillStyle.color}`}>
          <Icon className="h-4 w-4" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className={`text-[10px] font-medium ${getTaskTypeColor(task.task_type)}`}>
              {task.task_type.replace("_", " ")}
            </Badge>
            <Badge variant="outline" className={`text-[10px] font-medium ${getStatusColor(task.status)}`}>
              {task.status}
            </Badge>
          </div>

          <p className={`text-sm font-medium mb-1 ${isCompleted ? "text-muted-foreground line-through" : "text-foreground"}`}>
            {task.title}
          </p>

          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {task.duration_minutes} min
            </span>
            <span className="flex items-center gap-1">
              <Target className="h-3 w-3" />
              Priority {task.priority}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Day Card Component
// ─────────────────────────────────────────────────────────────
function DayCard({ day, onClick, isSelected }: { day: TimelineDay; onClick: () => void; isSelected: boolean }) {
  const skillStyle = SKILL_STYLES.reading; // Default for the card icon

  return (
    <Card
      className={`cursor-pointer transition-all hover:shadow-md ${
        isSelected ? "ring-2 ring-primary shadow-md" : ""
      } ${day.is_today ? "border-primary/30 bg-primary/5" : ""} ${
        day.is_exam_day ? "border-red-300 bg-red-50/30" : ""
      }`}
      onClick={onClick}
    >
      <CardContent className="p-4">
        {/* Date Header */}
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-semibold text-foreground">{day.display_date}</p>
            <p className="text-xs text-muted-foreground">{day.date}</p>
          </div>
          <div className="flex gap-1">
            {day.is_today && (
              <Badge variant="default" className="text-[10px]">
                Today
              </Badge>
            )}
            {day.is_exam_day && (
              <Badge variant="destructive" className="text-[10px]">
                Exam
              </Badge>
            )}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="text-center p-2 bg-gray-50 rounded">
            <p className="text-lg font-bold text-foreground">{day.total_tasks}</p>
            <p className="text-[10px] text-muted-foreground">Tasks</p>
          </div>
          <div className="text-center p-2 bg-gray-50 rounded">
            <p className="text-lg font-bold text-foreground">{day.total_minutes}</p>
            <p className="text-[10px] text-muted-foreground">Minutes</p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-medium text-foreground">{day.completion_percent}%</span>
          </div>
          <Progress value={day.completion_percent} className="h-1.5" />
        </div>

        {/* Quick Stats */}
        <div className="flex flex-wrap gap-1">
          {day.completed_tasks > 0 && (
            <Badge variant="success" className="text-[10px]">
              ✓ {day.completed_tasks}
            </Badge>
          )}
          {day.pending_tasks > 0 && (
            <Badge variant="accent" className="text-[10px]">
              ○ {day.pending_tasks}
            </Badge>
          )}
          {day.missed_tasks > 0 && (
            <Badge variant="destructive" className="text-[10px]">
              ✗ {day.missed_tasks}
            </Badge>
          )}
          {day.revision_tasks > 0 && (
            <Badge variant="outline" className="text-[10px]">
              📚 {day.revision_tasks}
            </Badge>
          )}
          {day.mock_tests > 0 && (
            <Badge variant="outline" className="text-[10px]">
              🎯 {day.mock_tests}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────
// Timeline View Page
// ─────────────────────────────────────────────────────────────
export default function TimelinePage() {
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  const fetchTimeline = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await timelineService.getTimeline();
      setTimeline(data);
      // Auto-select today or first day
      if (data.days.length > 0) {
        const today = data.days.find((d) => d.is_today);
        setSelectedDate(today?.date || data.days[0].date);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to load timeline");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  const selectedDay = useMemo(() => {
    if (!timeline || !selectedDate) return null;
    return timeline.days.find((d) => d.date === selectedDate) || null;
  }, [timeline, selectedDate]);

  const selectedIndex = useMemo(() => {
    if (!timeline || !selectedDate) return -1;
    return timeline.days.findIndex((d) => d.date === selectedDate);
  }, [timeline, selectedDate]);

  const goToPreviousDay = useCallback(() => {
    if (!timeline || selectedIndex <= 0) return;
    setSelectedDate(timeline.days[selectedIndex - 1].date);
  }, [timeline, selectedIndex]);

  const goToNextDay = useCallback(() => {
    if (!timeline || selectedIndex < 0 || selectedIndex >= timeline.days.length - 1) return;
    setSelectedDate(timeline.days[selectedIndex + 1].date);
  }, [timeline, selectedIndex]);

  const goToToday = useCallback(() => {
    if (!timeline) return;
    const today = timeline.days.find((d) => d.is_today);
    if (today) setSelectedDate(today.date);
  }, [timeline]);

  if (loading && !timeline) {
    return (
      <DashboardLayout>
        <div className="space-y-8 pb-12">
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
          <Button variant="ghost" size="sm" onClick={fetchTimeline}>
            Retry
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  if (!timeline || timeline.days.length === 0) {
    return (
      <DashboardLayout>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center space-y-4">
            <div className="p-4 rounded-full bg-primary/10 text-primary">
              <Calendar className="h-8 w-8" />
            </div>
            <h3 className="text-xl font-bold">No timeline available</h3>
            <p className="text-muted-foreground max-w-sm">
              Please set your exam date to view your study timeline.
            </p>
          </CardContent>
        </Card>
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
              <Calendar className="h-8 w-8 text-primary" />
              Study Timeline
            </h1>
            <p className="text-muted-foreground">
              {timeline.total_days} days until exam • {formatDate(timeline.exam_date)}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setViewMode(viewMode === "grid" ? "list" : "grid")}
            >
              {viewMode === "grid" ? "List View" : "Grid View"}
            </Button>
            <Button variant="outline" size="sm" onClick={fetchTimeline}>
              Refresh
            </Button>
          </div>
        </div>

        {/* Overall Progress */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-foreground">Overall Progress</p>
              <p className="text-2xl font-bold text-primary">
                {Math.round(
                  timeline.days.reduce((sum, d) => sum + d.completion_percent, 0) / timeline.days.length
                )}
                %
              </p>
            </div>
            <Progress
              value={
                timeline.days.reduce((sum, d) => sum + d.completion_percent, 0) / timeline.days.length
              }
              className="h-2"
            />
            <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3 text-green-600" />
                {timeline.days.reduce((sum, d) => sum + d.completed_tasks, 0)} completed
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3 text-amber-600" />
                {timeline.days.reduce((sum, d) => sum + d.pending_tasks, 0)} pending
              </span>
              <span className="flex items-center gap-1">
                <XCircle className="h-3 w-3 text-red-600" />
                {timeline.days.reduce((sum, d) => sum + d.missed_tasks, 0)} missed
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Day Navigation */}
        {selectedDay && (
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={goToPreviousDay}
                  disabled={selectedIndex <= 0}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>

                <div className="text-center">
                  <p className="text-lg font-bold text-foreground">{selectedDay.display_date}</p>
                  <p className="text-xs text-muted-foreground">
                    {selectedDay.is_today ? "Today" : selectedDay.is_exam_day ? "Exam Day" : ""}
                  </p>
                </div>

                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={goToToday}>
                    Today
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={goToNextDay}
                    disabled={selectedIndex >= timeline.days.length - 1}
                  >
                    Next
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Main Content: Timeline Grid + Selected Day Detail */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Timeline Grid */}
          <div className={selectedDay ? "lg:col-span-2" : "lg:col-span-3"}>
            {viewMode === "grid" ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {timeline.days.map((day) => (
                  <DayCard
                    key={day.date}
                    day={day}
                    onClick={() => setSelectedDate(day.date)}
                    isSelected={day.date === selectedDate}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {timeline.days.map((day) => (
                  <Card
                    key={day.date}
                    className={`cursor-pointer transition-all hover:shadow-md ${
                      day.date === selectedDate ? "ring-2 ring-primary" : ""
                    } ${day.is_today ? "border-primary/30" : ""}`}
                    onClick={() => setSelectedDate(day.date)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div>
                            <p className="font-semibold text-foreground">{day.display_date}</p>
                            <p className="text-xs text-muted-foreground">{day.date}</p>
                          </div>
                          {day.is_today && <Badge variant="default">Today</Badge>}
                          {day.is_exam_day && <Badge variant="destructive">Exam</Badge>}
                        </div>

                        <div className="flex items-center gap-6">
                          <div className="text-right">
                            <p className="text-sm font-medium text-foreground">
                              {day.completed_tasks}/{day.total_tasks} tasks
                            </p>
                            <p className="text-xs text-muted-foreground">{day.completion_percent}% complete</p>
                          </div>
                          <Progress value={day.completion_percent} className="w-24 h-2" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* Selected Day Detail */}
          {selectedDay && (
            <div className="lg:col-span-1">
              <Card className="sticky top-4">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>{selectedDay.display_date}</span>
                    {selectedDay.is_today && <Badge variant="default">Today</Badge>}
                    {selectedDay.is_exam_day && <Badge variant="destructive">Exam Day</Badge>}
                  </CardTitle>
                  <CardDescription>
                    {selectedDay.total_tasks} task{selectedDay.total_tasks !== 1 ? "s" : ""} •{" "}
                    {selectedDay.total_minutes} minutes
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Progress */}
                  <div>
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="text-muted-foreground">Completion</span>
                      <span className="font-bold text-foreground">{selectedDay.completion_percent}%</span>
                    </div>
                    <Progress value={selectedDay.completion_percent} className="h-2" />
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2 bg-green-50 rounded border border-green-200">
                      <p className="text-lg font-bold text-green-700">{selectedDay.completed_tasks}</p>
                      <p className="text-xs text-green-600">Completed</p>
                    </div>
                    <div className="p-2 bg-amber-50 rounded border border-amber-200">
                      <p className="text-lg font-bold text-amber-700">{selectedDay.pending_tasks}</p>
                      <p className="text-xs text-amber-600">Pending</p>
                    </div>
                    <div className="p-2 bg-red-50 rounded border border-red-200">
                      <p className="text-lg font-bold text-red-700">{selectedDay.missed_tasks}</p>
                      <p className="text-xs text-red-600">Missed</p>
                    </div>
                    <div className="p-2 bg-blue-50 rounded border border-blue-200">
                      <p className="text-lg font-bold text-blue-700">{selectedDay.upcoming_tasks}</p>
                      <p className="text-xs text-blue-600">Upcoming</p>
                    </div>
                  </div>

                  {/* Special Tasks */}
                  {(selectedDay.revision_tasks > 0 || selectedDay.mock_tests > 0) && (
                    <div className="space-y-2">
                      {selectedDay.revision_tasks > 0 && (
                        <div className="flex items-center gap-2 p-2 bg-blue-50 rounded border border-blue-200">
                          <BookOpen className="h-4 w-4 text-blue-600" />
                          <span className="text-sm font-medium text-blue-700">
                            {selectedDay.revision_tasks} Revision Task{selectedDay.revision_tasks !== 1 ? "s" : ""}
                          </span>
                        </div>
                      )}
                      {selectedDay.mock_tests > 0 && (
                        <div className="flex items-center gap-2 p-2 bg-red-50 rounded border border-red-200">
                          <Flag className="h-4 w-4 text-red-600" />
                          <span className="text-sm font-medium text-red-700">
                            {selectedDay.mock_tests} Mock Test{selectedDay.mock_tests !== 1 ? "s" : ""}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Task List */}
                  {selectedDay.tasks.length > 0 && (
                    <div>
                      <p className="text-sm font-semibold text-foreground mb-2">Tasks</p>
                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {selectedDay.tasks.map((task) => (
                          <TaskCard key={task.id} task={task} />
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedDay.tasks.length === 0 && (
                    <div className="text-center py-8 text-muted-foreground">
                      <Calendar className="h-8 w-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">No tasks scheduled</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}