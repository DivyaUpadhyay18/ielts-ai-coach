"use client";

import React, { useEffect, useState } from "react";
import { Calendar, Clock, BookOpen, CheckCircle, AlertCircle } from "lucide-react";
import { countdownService } from "@/services/api";
import type { ExamCountdown } from "@/types";

interface CountdownWidgetProps {
  /** Optional pre-fetched data. If not provided, the widget fetches on mount. */
  data?: ExamCountdown | null;
  /** If true, the widget will auto-refresh every 60 seconds. */
  autoRefresh?: boolean;
  /** Callback when data is loaded or refreshed. */
  onData?: (data: ExamCountdown) => void;
}

const INTENSITY_COLORS: Record<string, string> = {
  normal: "text-blue-500",
  focused: "text-amber-500",
  intensive: "text-orange-500",
  final: "text-red-500",
};

const INTENSITY_BG: Record<string, string> = {
  normal: "bg-blue-500/10",
  focused: "bg-amber-500/10",
  intensive: "bg-orange-500/10",
  final: "bg-red-500/10",
};

const INTENSITY_LABELS: Record<string, string> = {
  normal: "Normal Prep",
  focused: "Focused Prep",
  intensive: "Intensive Prep",
  final: "Final Sprint",
};

interface ProgressRingProps {
  progress: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
}

const ProgressRing: React.FC<ProgressRingProps> = ({
  progress,
  size = 120,
  strokeWidth = 8,
  color = "#3b82f6",
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <svg width={size} height={size} className="block">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="transparent"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        className="text-slate-200 dark:text-slate-700"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="transparent"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="transition-all duration-500 ease-out"
        style={{ transform: "rotate(-90deg)", transformOrigin: "50% 50%" }}
      />
    </svg>
  );
};

/**
 * CountdownWidget — displays the exam countdown with a progress ring,
 * study hours breakdown, and intensity indicator.
 */
export const CountdownWidget: React.FC<CountdownWidgetProps> = ({
  data: initialData,
  autoRefresh = false,
  onData,
}) => {
  const [data, setData] = useState<ExamCountdown | null>(initialData ?? null);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<string | null>(null);

  const fetchCountdown = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await countdownService.getCountdown();
      setData(result);
      onData?.(result);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to load countdown data"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!initialData) {
      fetchCountdown();
    }
  }, [initialData]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchCountdown, 60_000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground">
        <Clock className="h-5 w-5 animate-spin mr-2" />
        <span>Loading countdown…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
        <AlertCircle className="h-4 w-4" />
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No countdown data available.
      </div>
    );
  }

  const {
    days_remaining,
    weeks_remaining,
    study_hours,
    completion_percentage,
    intensity,
    has_active_plan,
  } = data;

  const intensityColor = INTENSITY_COLORS[intensity] || "text-blue-500";
  const intensityBg = INTENSITY_BG[intensity] || "bg-blue-500/10";
  const intensityLabel = INTENSITY_LABELS[intensity] || intensity;

  const ringColor =
    intensity === "final"
      ? "#ef4444"
      : intensity === "intensive"
      ? "#f97316"
      : intensity === "focused"
      ? "#f59e0b"
      : "#3b82f6";

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm">
      {/* Header: Exam Date + Intensity */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar className="h-5 w-5 text-muted-foreground" />
          <span className="text-sm font-medium text-muted-foreground">
            Exam Date
          </span>
        </div>
        <div
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${intensityBg} ${intensityColor}`}
        >
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "currentColor" }} />
          {intensityLabel}
        </div>
      </div>

      {/* Main: Progress Ring + Big Numbers */}
      <div className="mb-4 flex items-center justify-center">
        <div className="relative flex items-center justify-center">
          <ProgressRing progress={completion_percentage} color={ringColor} />
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold">{completion_percentage}%</span>
            <span className="text-xs text-muted-foreground">complete</span>
          </div>
        </div>
      </div>

      {/* Days / Weeks */}
      <div className="mb-4 grid grid-cols-2 gap-4 text-center">
        <div>
          <div className="text-2xl font-bold text-primary">{days_remaining}</div>
          <div className="text-xs text-muted-foreground">Days Left</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-primary">{weeks_remaining}</div>
          <div className="text-xs text-muted-foreground">Weeks Left</div>
        </div>
      </div>

      {/* Study Hours Breakdown */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2 text-muted-foreground">
            <BookOpen className="h-4 w-4" />
            Planned
          </span>
          <span className="font-medium">{study_hours.planned} hrs</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2 text-muted-foreground">
            <CheckCircle className="h-4 w-4 text-green-500" />
            Completed
          </span>
          <span className="font-medium text-green-600">{study_hours.completed} hrs</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2 text-muted-foreground">
            <Clock className="h-4 w-4" />
            Remaining
          </span>
          <span className="font-medium">{study_hours.remaining} hrs</span>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${completion_percentage}%`,
              backgroundColor: ringColor,
            }}
          />
        </div>
      </div>

      {/* Plan status */}
      {!has_active_plan && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-900/30 dark:bg-amber-900/10">
          No active study plan. Generate one to see study hour projections.
        </div>
      )}
    </div>
  );
};

export default CountdownWidget;
