"use client";

import { useState, useEffect } from "react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { CountdownWidget } from "@/components/countdown/countdown-widget";
import { countdownService } from "@/services/api";
import type { ExamCountdown, ExamDateUpdateResponse } from "@/types";
import {
  Calendar,
  Save,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal, ModalHeader, ModalTitle, ModalFooter } from "@/components/ui/modal";

export default function CountdownPage() {
  const [countdown, setCountdown] = useState<ExamCountdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [updateResult, setUpdateResult] = useState<ExamDateUpdateResponse | null>(null);
  const [newExamDate, setNewExamDate] = useState("");
  const [autoRegenerate, setAutoRegenerate] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  const fetchCountdown = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await countdownService.getCountdown();
      setCountdown(data);
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

  const handleUpdateExamDate = async () => {
    if (!newExamDate) return;
    setUpdating(true);
    try {
      const result = await countdownService.updateExamDate({
        exam_date: newExamDate,
        auto_regenerate: autoRegenerate,
      });
      setUpdateResult(result);
      setModalOpen(false);
      // Re-fetch countdown to reflect the new date
      await fetchCountdown();
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to update exam date"
      );
    } finally {
      setUpdating(false);
    }
  };

  // Fetch on mount
  useEffect(() => {
    fetchCountdown();
  }, []);

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString("en-US", {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Exam Countdown</h1>
            <p className="text-sm text-muted-foreground">
              Track your preparation progress and time remaining until exam day.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchCountdown}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Update result banner */}
        {updateResult && (
          <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800 dark:border-green-900/30 dark:bg-green-900/10">
            <CheckCircle className="h-4 w-4" />
            {updateResult.message}
            {updateResult.regenerated && (
              <span className="font-medium">
                (Plan v{updateResult.new_study_plan_version} regenerated)
              </span>
            )}
          </div>
        )}

        {/* Main content */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : countdown ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Countdown Widget (Progress Ring + Numbers) */}
            <div className="lg:col-span-1">
              <CountdownWidget data={countdown} />
            </div>

            {/* Detailed Breakdown */}
            <div className="lg:col-span-2 space-y-6">
              {/* Exam Date Card */}
              <div className="rounded-xl border bg-card p-6 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-muted-foreground" />
                  <h2 className="text-lg font-semibold">Exam Details</h2>
                </div>
                <div className="space-y-3">
                  <div>
                    <span className="text-sm text-muted-foreground">Exam Date</span>
                    <div className="font-medium">
                      {formatDate(countdown.exam_date)}
                    </div>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Today</span>
                    <div className="font-medium">
                      {formatDate(countdown.today)}
                    </div>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">
                      Preparation Intensity
                    </span>
                    <div className="font-medium capitalize">
                      {countdown.intensity}
                    </div>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">
                      Active Study Plan
                    </span>
                    <div className="font-medium">
                      {countdown.has_active_plan
                        ? `Version ${countdown.study_plan_version}`
                        : "Not set"}
                    </div>
                  </div>
                </div>
              </div>

              {/* Study Hours Breakdown */}
              <div className="rounded-xl border bg-card p-6 shadow-sm">
                <h2 className="mb-4 text-lg font-semibold">Study Hours</h2>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      Planned Study Hours
                    </span>
                    <span className="text-2xl font-bold">
                      {countdown.study_hours.planned} hrs
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      Completed Study Hours
                    </span>
                    <span className="text-2xl font-bold text-green-600">
                      {countdown.study_hours.completed} hrs
                    </span>
                  </div>
                  <div className="flex items-center justify-between border-t pt-3">
                    <span className="text-sm text-muted-foreground">
                      Remaining Study Hours
                    </span>
                    <span className="text-2xl font-bold">
                      {countdown.study_hours.remaining} hrs
                    </span>
                  </div>
                  <div className="mt-4">
                    <div className="mb-1 flex justify-between text-sm">
                      <span>Completion</span>
                      <span className="font-medium">
                        {countdown.completion_percentage}%
                      </span>
                    </div>
                    <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${countdown.completion_percentage}%`,
                          backgroundColor:
                            countdown.intensity === "final"
                              ? "#ef4444"
                              : countdown.intensity === "intensive"
                              ? "#f97316"
                              : countdown.intensity === "focused"
                              ? "#f59e0b"
                              : "#3b82f6",
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Change Exam Date */}
              <div className="rounded-xl border bg-card p-6 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Change Exam Date</h2>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setModalOpen(true)}
                  >
                    <Save className="h-4 w-4 mr-2" />
                    Update Date
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground">
                  Your current exam date is{" "}
                  <span className="font-medium">
                    {formatDate(countdown.exam_date)}
                  </span>
                  . Update it here if your exam has been rescheduled.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            No countdown data available.
          </div>
        )}

        {/* Update Exam Date Modal */}
        <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)}>
          <ModalHeader>
            <ModalTitle>Update Exam Date</ModalTitle>
          </ModalHeader>
          <div className="space-y-4 py-4">
            <div>
              <label
                htmlFor="exam-date"
                className="block text-sm font-medium text-foreground mb-1"
              >
                New Exam Date
              </label>
              <Input
                id="exam-date"
                type="date"
                value={newExamDate}
                onChange={(e) => setNewExamDate(e.target.value)}
                min={new Date().toISOString().split("T")[0]}
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="auto-regen"
                checked={autoRegenerate}
                onChange={(e) => setAutoRegenerate(e.target.checked)}
              />
              <label htmlFor="auto-regen" className="text-sm">
                Auto-regenerate study plan for the new timeline
              </label>
            </div>
          </div>
          <ModalFooter>
            <Button
              variant="outline"
              onClick={() => setModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdateExamDate}
              disabled={updating || !newExamDate}
            >
              {updating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Updating…
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
          </ModalFooter>
        </Modal>
      </div>
    </DashboardLayout>
  );
}
