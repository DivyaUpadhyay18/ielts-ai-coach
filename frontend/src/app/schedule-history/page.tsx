"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  History,
  Calendar,
  Clock,
  GitCompare,
  Filter,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Info,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { scheduleHistoryService } from "@/services/api";
import type {
  ScheduleHistoryEntry,
  ScheduleHistoryListResponse,
  ScheduleComparisonResponse,
  ScheduleHistoryStats,
  ScheduleChangeType,
  UserAction,
} from "@/types";

// ─────────────────────────────────────────────────────────────
// Helper Components
// ─────────────────────────────────────────────────────────────

function ChangeTypeBadge({ changeType }: { changeType: ScheduleChangeType }) {
  const config: Record<ScheduleChangeType, { label: string; variant: any; icon: any }> = {
    scheduler_run: { label: "Scheduler Run", variant: "default", icon: "🔄" },
    exam_date_update: { label: "Exam Date Update", variant: "destructive", icon: "📅" },
    manual_reschedule: { label: "Manual Reschedule", variant: "secondary", icon: "✏️" },
    study_plan_regeneration: { label: "Plan Regeneration", variant: "outline", icon: "♻️" },
    task_modification: { label: "Task Modified", variant: "secondary", icon: "📝" },
    user_override: { label: "User Override", variant: "destructive", icon: "👤" },
  };

  const { label, variant, icon } = config[changeType] || config.scheduler_run;

  return (
    <Badge variant={variant} className="text-xs">
      {icon} {label}
    </Badge>
  );
}

function UserActionBadge({ action }: { action?: UserAction | null }) {
  if (!action) return null;

  const config: Record<UserAction, { label: string; variant: any; icon: any }> = {
    accepted: { label: "Accepted", variant: "success", icon: <CheckCircle2 className="h-3 w-3" /> },
    rejected: { label: "Rejected", variant: "destructive", icon: <XCircle className="h-3 w-3" /> },
    modified: { label: "Modified", variant: "secondary", icon: <AlertCircle className="h-3 w-3" /> },
    pending: { label: "Pending", variant: "outline", icon: <Clock className="h-3 w-3" /> },
    auto_applied: { label: "Auto Applied", variant: "default", icon: <Info className="h-3 w-3" /> },
  };

  const { label, variant, icon } = config[action] || config.pending;

  return (
    <Badge variant={variant} className="text-xs flex items-center gap-1">
      {icon}
      {label}
    </Badge>
  );
}

function ScheduleHistoryCard({ entry, onSelect, isSelected }: {
  entry: ScheduleHistoryEntry;
  onSelect: (id: string) => void;
  isSelected: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return "N/A";
    return new Date(dateStr).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getWorkloadChange = () => {
    const before = entry.metrics_before?.new_workload_minutes || 0;
    const after = entry.metrics_after?.new_workload_minutes || 0;
    const change = after - before;
    if (change > 0) return { icon: <TrendingUp className="h-4 w-4" />, text: `+${change} min`, color: "text-red-600" };
    if (change < 0) return { icon: <TrendingDown className="h-4 w-4" />, text: `${change} min`, color: "text-green-600" };
    return { icon: <Minus className="h-4 w-4" />, text: "No change", color: "text-gray-600" };
  };

  const workloadChange = getWorkloadChange();

  return (
    <Card
      className={`cursor-pointer transition-all ${
        isSelected ? "ring-2 ring-primary border-primary" : "hover:border-primary/30"
      }`}
      onClick={() => onSelect(entry.id)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <ChangeTypeBadge changeType={entry.change_type} />
              <UserActionBadge action={entry.user_action} />
            </div>
            <CardTitle className="text-base font-semibold line-clamp-2">
              {entry.summary || entry.change_reason}
            </CardTitle>
            <CardDescription className="mt-1">
              {formatDate(entry.created_at)}
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Adjustments</p>
            <p className="font-semibold">{entry.adjustments_count}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Tasks Affected</p>
            <p className="font-semibold">{entry.tasks_affected}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Workload</p>
            <div className={`flex items-center gap-1 font-semibold ${workloadChange.color}`}>
              {workloadChange.icon}
              <span className="text-xs">{workloadChange.text}</span>
            </div>
          </div>
        </div>

        {expanded && (
          <div className="pt-3 border-t border-border space-y-3">
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">Reason</p>
              <p className="text-sm text-foreground">{entry.change_reason}</p>
            </div>

            {entry.user_action_notes && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Your Notes</p>
                <p className="text-sm text-foreground">{entry.user_action_notes}</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="p-2 bg-muted/50 rounded-lg">
                <p className="text-xs text-muted-foreground mb-1">Before</p>
                <p className="font-semibold">
                  {entry.metrics_before?.new_workload_minutes || 0} min
                </p>
                <p className="text-xs text-muted-foreground">
                  {Math.round((entry.metrics_before?.completion_rate || 0) * 100)}% complete
                </p>
              </div>
              <div className="p-2 bg-muted/50 rounded-lg">
                <p className="text-xs text-muted-foreground mb-1">After</p>
                <p className="font-semibold">
                  {entry.metrics_after?.new_workload_minutes || 0} min
                </p>
                <p className="text-xs text-muted-foreground">
                  {Math.round((entry.metrics_after?.completion_rate || 0) * 100)}% complete
                </p>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ComparisonView({ comparison, history1, history2 }: {
  comparison: ScheduleComparisonResponse;
  history1: ScheduleHistoryEntry;
  history2: ScheduleHistoryEntry;
}) {
  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return "N/A";
    return new Date(dateStr).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitCompare className="h-5 w-5 text-primary" />
          Schedule Comparison
        </CardTitle>
        <CardDescription>
          Comparing changes from {formatDate(comparison.history_1_date)} to {formatDate(comparison.history_2_date)}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center p-3 bg-white rounded-lg border border-border">
            <p className="text-2xl font-bold text-green-600">+{comparison.tasks_added}</p>
            <p className="text-xs text-muted-foreground mt-1">Tasks Added</p>
          </div>
          <div className="text-center p-3 bg-white rounded-lg border border-border">
            <p className="text-2xl font-bold text-red-600">-{comparison.tasks_removed}</p>
            <p className="text-xs text-muted-foreground mt-1">Tasks Removed</p>
          </div>
          <div className="text-center p-3 bg-white rounded-lg border border-border">
            <p className="text-2xl font-bold text-amber-600">{comparison.tasks_rescheduled}</p>
            <p className="text-xs text-muted-foreground mt-1">Rescheduled</p>
          </div>
          <div className="text-center p-3 bg-white rounded-lg border border-border">
            <p className={`text-2xl font-bold ${comparison.workload_change_minutes > 0 ? 'text-red-600' : 'text-green-600'}`}>
              {comparison.workload_change_minutes > 0 ? '+' : ''}{comparison.workload_change_minutes}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Minutes Change</p>
          </div>
          <div className="text-center p-3 bg-white rounded-lg border border-border">
            <p className={`text-2xl font-bold ${comparison.completion_rate_change > 0 ? 'text-green-600' : 'text-red-600'}`}>
              {comparison.completion_rate_change > 0 ? '+' : ''}{(comparison.completion_rate_change * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">Completion Rate</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
          <div>
            <p className="text-xs font-semibold text-muted-foreground mb-2">Earlier Change</p>
            <ChangeTypeBadge changeType={comparison.history_1_change_type} />
            <p className="text-xs text-muted-foreground mt-2">{formatDate(comparison.history_1_date)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold text-muted-foreground mb-2">Later Change</p>
            <ChangeTypeBadge changeType={comparison.history_2_change_type} />
            <p className="text-xs text-muted-foreground mt-2">{formatDate(comparison.history_2_date)}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Schedule History Page
// ─────────────────────────────────────────────────────────────

export default function ScheduleHistoryPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ScheduleHistoryListResponse | null>(null);
  const [selectedEntries, setSelectedEntries] = useState<string[]>([]);
  const [comparison, setComparison] = useState<ScheduleComparisonResponse | null>(null);
  const [stats, setStats] = useState<ScheduleHistoryStats | null>(null);
  const [filterChangeType, setFilterChangeType] = useState<ScheduleChangeType | undefined>();
  const [filterUserAction, setFilterUserAction] = useState<UserAction | undefined>();
  const [showFilters, setShowFilters] = useState(false);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [historyData, statsData] = await Promise.all([
        scheduleHistoryService.list({
          change_type: filterChangeType,
          user_action: filterUserAction,
          limit: 50,
        }),
        scheduleHistoryService.getStats(30),
      ]);
      setHistory(historyData);
      setStats(statsData);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to load schedule history");
    } finally {
      setLoading(false);
    }
  }, [filterChangeType, filterUserAction]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  useEffect(() => {
    // Auto-select first two entries for comparison
    if (history?.items && history.items.length >= 2 && selectedEntries.length === 0) {
      setSelectedEntries([history.items[0].id, history.items[1].id]);
    }
  }, [history, selectedEntries.length]);

  useEffect(() => {
    // Fetch comparison when two entries are selected
    if (selectedEntries.length === 2) {
      scheduleHistoryService
        .compare(selectedEntries[0], selectedEntries[1])
        .then(setComparison)
        .catch(() => setComparison(null));
    } else {
      setComparison(null);
    }
  }, [selectedEntries]);

  const handleSelectEntry = (id: string) => {
    setSelectedEntries((prev) => {
      if (prev.includes(id)) {
        return prev.filter((entryId) => entryId !== id);
      }
      if (prev.length >= 2) {
        return [prev[1], id];
      }
      return [...prev, id];
    });
  };

  const handleCompare = async () => {
    if (selectedEntries.length === 2) {
      try {
        const comp = await scheduleHistoryService.compare(selectedEntries[0], selectedEntries[1]);
        setComparison(comp);
      } catch (err: any) {
        setError(err?.response?.data?.detail?.message || "Failed to compare entries");
      }
    }
  };

  const selectedHistoryEntries = useMemo(() => {
    if (!history?.items) return [];
    return history.items.filter((entry) => selectedEntries.includes(entry.id));
  }, [history, selectedEntries]);

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
          <Button variant="ghost" size="sm" onClick={fetchHistory}>
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
              <History className="h-8 w-8 text-primary" />
              Schedule History
            </h1>
            <p className="text-muted-foreground">
              Track and compare all changes to your study schedule
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="h-4 w-4 mr-2" />
              Filters
            </Button>
            <Button variant="outline" size="sm" onClick={fetchHistory}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Stats Overview */}
        {stats && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Total Changes
                  </p>
                  <p className="text-3xl font-black text-primary">{stats.total_changes}</p>
                  <p className="text-xs text-muted-foreground">Last 30 days</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Accepted
                  </p>
                  <p className="text-3xl font-black text-green-600">{stats.accepted}</p>
                  <p className="text-xs text-muted-foreground">
                    {stats.rejected} rejected
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Auto Applied
                  </p>
                  <p className="text-3xl font-black text-blue-600">{stats.auto_applied}</p>
                  <p className="text-xs text-muted-foreground">
                    {stats.modified} modified
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Tasks Affected
                  </p>
                  <p className="text-3xl font-black text-amber-600">{stats.total_tasks_affected}</p>
                  <p className="text-xs text-muted-foreground">
                    {stats.total_adjustments} adjustments
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        {showFilters && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Filters</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Change Type</label>
                  <select
                    value={filterChangeType || ""}
                    onChange={(e) => setFilterChangeType(e.target.value as ScheduleChangeType || undefined)}
                    className="w-full p-2 rounded-lg border border-border bg-background text-sm"
                  >
                    <option value="">All Types</option>
                    <option value="scheduler_run">Scheduler Run</option>
                    <option value="exam_date_update">Exam Date Update</option>
                    <option value="manual_reschedule">Manual Reschedule</option>
                    <option value="study_plan_regeneration">Plan Regeneration</option>
                    <option value="task_modification">Task Modified</option>
                    <option value="user_override">User Override</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">User Action</label>
                  <select
                    value={filterUserAction || ""}
                    onChange={(e) => setFilterUserAction(e.target.value as UserAction || undefined)}
                    className="w-full p-2 rounded-lg border border-border bg-background text-sm"
                  >
                    <option value="">All Actions</option>
                    <option value="accepted">Accepted</option>
                    <option value="rejected">Rejected</option>
                    <option value="modified">Modified</option>
                    <option value="pending">Pending</option>
                    <option value="auto_applied">Auto Applied</option>
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Comparison View */}
        {selectedEntries.length === 2 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Comparison</h2>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedEntries([])}
              >
                Clear Selection
              </Button>
            </div>
            {comparison ? (
              <ComparisonView
                comparison={comparison}
                history1={selectedHistoryEntries[0]}
                history2={selectedHistoryEntries[1]}
              />
            ) : (
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <p className="text-sm">Loading comparison...</p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* History List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">Change History</h2>
            {selectedEntries.length > 0 && (
              <p className="text-sm text-muted-foreground">
                {selectedEntries.length} selected
                {selectedEntries.length === 2 && " (comparing)"}
              </p>
            )}
          </div>

          {!history || history.items.length === 0 ? (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-8">
                  <History className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">No schedule history yet</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Schedule changes will appear here
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {history.items.map((entry) => (
                <ScheduleHistoryCard
                  key={entry.id}
                  entry={entry}
                  onSelect={handleSelectEntry}
                  isSelected={selectedEntries.includes(entry.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}