"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  RefreshCw,
  BarChart3,
  TrendingUp,
  Trophy,
  Award,
  Clock,
  FileText,
  Target,
  Loader2,
  X,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal, ModalHeader, ModalTitle, ModalFooter } from "@/components/ui/modal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { writingReattemptService, writingWorkspaceService } from "@/services/api";
import type {
  WritingEvaluation,
  WritingWorkspaceSubmission,
  WritingComparison,
  WritingReattemptStartResponse,
  WritingReattemptEvaluateResponse,
  CriterionComparison,
} from "@/types/writing-workspace";

interface WritingReattemptModalProps {
  submissionId: string;
  evaluation: WritingEvaluation;
  onClose: () => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function BandBadge({ band }: { band: number }) {
  const colorMap: Record<number, string> = {
    9: "bg-purple-500/20 text-purple-700",
    8: "bg-indigo-500/20 text-indigo-700",
    7: "bg-blue-500/20 text-blue-700",
    6: "bg-green-500/20 text-green-700",
    5: "bg-amber-500/20 text-amber-700",
    4: "bg-orange-500/20 text-orange-700",
    3: "bg-red-500/20 text-red-700",
  };
  const rounded = Math.round(band);
  const colorClass = colorMap[rounded] || "bg-gray-500/20 text-gray-700";
  return (
    <span className={`px-2 py-1 rounded text-xs font-bold ${colorClass}`}>
      {band.toFixed(1)}
    </span>
  );
}

function CriterionRow({ comp }: { comp: CriterionComparison }) {
  return (
    <div className="grid grid-cols-5 gap-2 items-center py-2 border-b border-border last:border-0">
      <span className="text-sm font-medium">{comp.label}</span>
      <div className="col-span-3">
        <div className="flex items-center gap-2 h-6">
          <span className="text-sm text-muted-foreground w-12">
            {comp.attempt_1_band.toFixed(1)}
          </span>
          <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded relative">
            <div
              className={`h-2 rounded ${
                comp.delta >= 0
                  ? "bg-green-500"
                  : "bg-red-500"
              }`}
              style={{
                width: `${Math.min(Math.abs(comp.delta) / 2 * 100, 100)}%`,
                marginLeft: comp.delta >= 0 ? "0" : "auto",
              }}
            />
          </div>
          <span className="text-sm text-muted-foreground w-12">
            {comp.attempt_2_band.toFixed(1)}
          </span>
        </div>
      </div>
      <div className="flex items-center justify-end gap-1">
        <Badge
          variant={comp.improved ? "default" : "secondary"}
          className={
            comp.improved
              ? "bg-green-500/20 text-green-700"
              : "bg-red-500/20 text-red-700"
          }
        >
          {comp.delta >= 0 ? "+" : ""}{comp.delta.toFixed(1)}
        </Badge>
        {comp.improved && (
          <TrendingUp className="h-3 w-3 text-green-600" />
        )}
      </div>
    </div>
  );
}

export function WritingReattemptModal({
  submissionId,
  evaluation,
  onClose,
}: WritingReattemptModalProps) {
  const [step, setStep] = useState<"start" | "writing" | "evaluating" | "comparison">("start");
  const [startData, setStartData] = useState<WritingReattemptStartResponse | null>(null);
  const [newSubmission, setNewSubmission] = useState<WritingWorkspaceSubmission | null>(null);
  const [essayText, setEssayText] = useState("");
  const [comparison, setComparison] = useState<WritingComparison | null>(null);
  const [evaluateResult, setEvaluateResult] =
    useState<WritingReattemptEvaluateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartReattempt = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await writingReattemptService.startReattempt(submissionId);
      setStartData(data);
      setNewSubmission(data.submission);
      setEssayText("");
      setStep("writing");
    } catch (err: any) {
      setError(err?.message || "Failed to start reattempt");
    } finally {
      setLoading(false);
    }
  }, [submissionId]);

  const handleSaveDraft = useCallback(async () => {
    if (!newSubmission) return;
    try {
      await writingWorkspaceService.autoSave(newSubmission.id, {
        essay_text: essayText,
        time_seconds_spent: 0,
      });
    } catch (err: any) {
      setError(err?.message || "Failed to save draft");
    }
  }, [newSubmission, essayText]);

  const handleSubmit = useCallback(async () => {
    if (!newSubmission) return;
    setLoading(true);
    setError(null);
    try {
      await writingWorkspaceService.submit(newSubmission.id, {
        time_seconds_spent: 0,
      });
      setStep("evaluating");

      // Evaluate the reattempt
      const result = await writingReattemptService.evaluateReattempt(
        newSubmission.id
      );
      setEvaluateResult(result);
      setComparison(result.comparison);
      setStep("comparison");
    } catch (err: any) {
      setError(err?.message || "Failed to evaluate reattempt");
      setStep("writing");
    } finally {
      setLoading(false);
    }
  }, [newSubmission]);

  const wordCount = essayText ? essayText.trim().split(/\s+/).filter(Boolean).length : 0;
  const wordLimit = newSubmission?.word_limit || 250;

  const renderStart = () => (
    <div className="text-center py-8">
      <RefreshCw className="h-12 w-12 text-blue-600 mx-auto mb-4" />
      <h3 className="text-lg font-semibold mb-2">Reattempt Mode</h3>
      <p className="text-sm text-muted-foreground mb-6">
        Rewrite your essay to improve your band score. Your original submission
        will be kept for comparison, and you&apos;ll see exactly how you improved.
      </p>
      <div className="mb-4 p-3 bg-secondary/50 rounded-lg">
        <div className="flex items-center justify-center gap-4">
          <div className="text-center">
            <span className="text-xs text-muted-foreground">Previous Band</span>
            <p className="font-bold text-lg">
              {evaluation?.overall_band?.toFixed(1) ?? "N/A"}
            </p>
          </div>
          <div className="text-center">
            <span className="text-xs text-muted-foreground">Weakest Area</span>
            <p className="font-bold text-sm">
              {evaluation?.weaknesses?.[0] || "N/A"}
            </p>
          </div>
        </div>
      </div>
      <Button onClick={handleStartReattempt} disabled={loading}>
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Starting...
          </>
        ) : (
          <>
            <FileText className="h-4 w-4 mr-2" />
            Start Reattempt
          </>
        )}
      </Button>
    </div>
  );

  const renderWriting = () => (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">
          Attempt #{startData?.attempt_number} — Rewrite Your Essay
        </h3>
        <Badge variant="outline">
          {wordCount}/{wordLimit} words
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground mb-3">{newSubmission?.prompt_text}</p>
      <textarea
        value={essayText}
        onChange={(e) => setEssayText(e.target.value)}
        className="w-full h-64 p-3 border border-border rounded-lg resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
        placeholder="Write your improved essay here..."
      />
      <div className="flex justify-between items-center mt-3">
        <span className="text-xs text-muted-foreground">
          {wordCount < wordLimit ? `Need ${wordLimit - wordCount} more words` : "Word count OK"}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setStep("start")}>
            <ChevronLeft className="h-3 w-3 mr-1" />
            Back
          </Button>
          <Button size="sm" onClick={handleSubmit} disabled={loading || !essayText.trim()}>
            Submit & Evaluate
          </Button>
        </div>
      </div>
    </div>
  );

  const renderEvaluating = () => (
    <div className="text-center py-12">
      <Loader2 className="h-12 w-12 animate-spin text-blue-600 mx-auto mb-4" />
      <h3 className="text-lg font-semibold mb-2">Evaluating Your Essay</h3>
      <p className="text-sm text-muted-foreground">
        AI is analyzing your improved essay and comparing it with your previous attempt...
      </p>
    </div>
  );

  const renderComparison = () => {
    if (!comparison || !evaluateResult) return null;
    const band = evaluateResult.evaluation;
    const { bonus_xp, bonus_reason } = evaluateResult;
    const improved = comparison.improvement;

    return (
      <div className="space-y-4">
        <div className="text-center">
          <h3 className="text-lg font-semibold mb-2">
            {improved ? "Improvement Detected!" : "Reattempt Complete"}
          </h3>
          {bonus_xp > 0 && bonus_reason && (
            <div className="flex items-center justify-center gap-2 mb-3">
              <Trophy className="h-5 w-5 text-yellow-500" />
              <span className="font-medium">+{bonus_xp} XP Bonus</span>
              <span className="text-sm text-muted-foreground">({bonus_reason})</span>
            </div>
          )}
        </div>

        {/* Overall Band Comparison */}
        <Card>
          <CardHeader>
            <CardTitle className="text-center text-lg">
              Overall Band Comparison
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center gap-8">
              <div className="text-center">
                <span className="text-sm text-muted-foreground">Attempt 1</span>
                <p className="text-3xl font-bold mt-1">
                  {comparison.overall_band.attempt_1.toFixed(1)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-8 h-1 bg-border rounded" />
                <ArrowIndicator delta={comparison.overall_band.delta} />
                <div className="w-8 h-1 bg-border rounded" />
              </div>
              <div className="text-center">
                <span className="text-sm text-muted-foreground">Attempt 2</span>
                <p className="text-3xl font-bold mt-1">
                  {comparison.overall_band.attempt_2.toFixed(1)}
                </p>
              </div>
            </div>
            <div className="text-center mt-3">
              {improved ? (
                <span className="text-green-600 font-medium flex items-center justify-center gap-1">
                  <TrendingUp className="h-4 w-4" />
                  Improved by {comparison.overall_band.delta.toFixed(1)} bands
                </span>
              ) : (
                <span className="text-muted-foreground">
                  Delta: {comparison.overall_band.delta.toFixed(1)}
                </span>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Band Badge for Attempt 2 */}
        {band?.overall_band != null && (
          <div className="flex justify-center">
            <BandBadge band={band.overall_band} />
          </div>
        )}

        {/* Criteria Comparison */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Per-Criterion Breakdown</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {comparison.criteria.map((c) => (
              <CriterionRow key={c.criterion} comp={c} />
            ))}
          </CardContent>
        </Card>

        {/* Time & Word Count */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Efficiency Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <FileText className="h-3 w-3" /> Word Count
                </span>
                <p className="font-medium">
                  {comparison.word_count.attempt_1} → {comparison.word_count.attempt_2}
                  <span className="text-xs text-muted-foreground ml-1">
                    (Δ {comparison.word_count.delta})
                  </span>
                </p>
              </div>
              <div>
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="h-3 w-4" /> Time Spent
                </span>
                <p className="font-medium">
                  {formatTime(comparison.time_seconds.attempt_1)} →{" "}
                  {formatTime(comparison.time_seconds.attempt_2)}
                  <span className="text-xs text-muted-foreground ml-1">
                    (Δ {comparison.time_seconds.delta}s)
                  </span>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  const handleRetry = () => {
    setStep("start");
    setStartData(null);
    setNewSubmission(null);
    setEssayText("");
    setComparison(null);
    setEvaluateResult(null);
    setError(null);
  };

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      className="max-w-3xl"
    >
      <ModalHeader>
        <ModalTitle>
          {step === "comparison" ? "Reattempt Results" : "Reattempt Writing"}
        </ModalTitle>
      </ModalHeader>
      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-200/30 rounded-lg">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {step === "start" && renderStart()}
      {step === "writing" && renderWriting()}
      {step === "evaluating" && renderEvaluating()}
      {step === "comparison" && renderComparison()}

      <ModalFooter>
        <Button size="sm" variant="outline" onClick={() => setStep("start")}>
          <ChevronLeft className="h-3 w-3 mr-1" />
        </Button>
        {step === "comparison" && (
          <Button size="sm" onClick={handleRetry}>
            <RefreshCw className="h-3 w-3 mr-1" />
            Try Again
          </Button>
        )}
      </ModalFooter>
    </Modal>
  );
}

function ArrowIndicator({ delta }: { delta: number }) {
  if (delta > 0) {
    return <TrendingUp className="h-5 w-5 text-green-600" />;
  }
  if (delta < 0) {
    return <TrendingUp className="h-5 w-5 text-red-600 rotate-180" />;
  }
  return <div className="h-5 w-5" />;
}
