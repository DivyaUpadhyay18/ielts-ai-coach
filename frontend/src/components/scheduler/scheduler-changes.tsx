"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SchedulerAdjustment, SchedulerAction } from "@/types";
import { getSchedulerActionIcon, getSchedulerActionColor } from "@/services/api";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";

interface SchedulerChangesProps {
  adjustments: SchedulerAdjustment[];
  summary?: string;
  className?: string;
}

export function SchedulerChanges({ adjustments, summary, className = "" }: SchedulerChangesProps) {
  if (!adjustments || adjustments.length === 0) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="flex items-center gap-3 text-green-600">
            <CheckCircle2 className="h-5 w-5" />
            <p className="text-sm font-medium">Your study plan is on track. No changes needed.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Info className="h-5 w-5 text-primary" />
          Schedule Changes
        </CardTitle>
        {summary && <CardDescription>{summary}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {adjustments.map((adjustment) => (
            <div
              key={adjustment.id}
              className="flex items-start gap-3 p-3 rounded-lg border border-border hover:border-primary/30 transition-colors"
            >
              {/* Action Icon */}
              <div className={`text-xl font-bold ${getSchedulerActionColor(adjustment.action)}`}>
                {getSchedulerActionIcon(adjustment.action)}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className="text-xs font-medium">
                    {adjustment.action.replace("_", " ")}
                  </Badge>
                  {adjustment.priority_delta !== 0 && (
                    <Badge
                      variant={adjustment.priority_delta > 0 ? "success" : "secondary"}
                      className="text-xs"
                    >
                      Priority {adjustment.priority_delta > 0 ? "+" : ""}{adjustment.priority_delta}
                    </Badge>
                  )}
                </div>

                <p className="text-sm font-medium text-foreground mb-1">
                  {adjustment.task_title || "Untitled Task"}
                </p>

                <p className="text-xs text-muted-foreground mb-2">{adjustment.reason}</p>

                {/* Date change */}
                {(adjustment.from_date || adjustment.to_date) && (
                  <div className="flex items-center gap-2 text-xs">
                    {adjustment.from_date && (
                      <span className="text-muted-foreground">
                        From: {new Date(adjustment.from_date).toLocaleDateString()}
                      </span>
                    )}
                    {adjustment.from_date && adjustment.to_date && <span className="text-muted-foreground">→</span>}
                    {adjustment.to_date && (
                      <span className="font-medium text-foreground">
                        To: {new Date(adjustment.to_date).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Summary Stats */}
        <div className="mt-4 pt-4 border-t border-border">
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>{adjustments.length} change{adjustments.length !== 1 ? "s" : ""}</span>
            <span>•</span>
            <span>
              {adjustments.filter((a) => a.action === "carried_forward").length} carried forward
            </span>
            <span>•</span>
            <span>
              {adjustments.filter((a) => a.action === "merged").length} merged
            </span>
            <span>•</span>
            <span>
              {adjustments.filter((a) => a.action === "rescheduled").length} rescheduled
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function SchedulerExplanation({ explanation, className = "" }: { explanation: any; className?: string }) {
  if (!explanation) {
    return null;
  }

  const { would_change, metrics, adjustments, note } = explanation;

  return (
    <div className={className}>
      {/* Status Banner */}
      <Card className="mb-4">
        <CardContent className="pt-6">
          <div className="flex items-center gap-3">
            {would_change ? (
              <>
                <AlertCircle className="h-5 w-5 text-amber-500" />
                <div>
                  <p className="text-sm font-medium text-foreground">Schedule adjustments available</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {note || "Your study plan can be optimized based on your recent activity."}
                  </p>
                </div>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <div>
                  <p className="text-sm font-medium text-foreground">Your plan is on track</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    No changes needed at this time.
                  </p>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Metrics Overview */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Card>
            <CardContent className="pt-4 pb-3">
              <p className="text-xs text-muted-foreground mb-1">Workload</p>
              <p className="text-lg font-bold">
                {metrics.new_workload_minutes}<span className="text-xs font-normal text-muted-foreground">/{metrics.previous_workload_minutes} min</span>
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <p className="text-xs text-muted-foreground mb-1">Adjustments</p>
              <p className="text-lg font-bold">{metrics.adjustment_count}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <p className="text-xs text-muted-foreground mb-1">Completion Rate</p>
              <p className="text-lg font-bold">{Math.round(metrics.completion_rate * 100)}%</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <p className="text-xs text-muted-foreground mb-1">Days Remaining</p>
              <p className="text-lg font-bold">{metrics.days_remaining}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Changes List */}
      {adjustments && adjustments.length > 0 && (
        <SchedulerChanges adjustments={adjustments} summary={note} />
      )}
    </div>
  );
}