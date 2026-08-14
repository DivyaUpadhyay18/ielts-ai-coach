"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  PenTool,
  Timer,
  Type,
  Send,
  FileText,
  Save,
  BarChart3,
   AlertTriangle,
   CheckCircle2,
   X,
   BookOpen,
   Clock,
   Target,
   RefreshCw,
   Loader2,
   TrendingUp,
   ExternalLink,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Modal, ModalHeader, ModalTitle, ModalFooter } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { writingWorkspaceService, writingEvaluationService, writingImprovementPlanService } from "@/services/api";
import type {
  WritingWorkspacePrompt,
  WritingWorkspaceSubmission,
  WritingWorkspacePromptsResponse,
  WritingEvaluation,
  WritingError,
  WritingImprovementPlan,
} from "@/types/writing-workspace";
import {
  WRITING_WORKSPACE_TASK_LABELS,
  WRITING_WORKSPACE_TASK_DESCRIPTIONS,
} from "@/types/writing-workspace";

const TASK_1_TIME = 20 * 60; // 20 minutes
const TASK_2_TIME = 40 * 60; // 40 minutes

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function WordCountBadge({ count, limit }: { count: number; limit: number }) {
  const ratio = limit > 0 ? count / limit : 0;
  let colorClass = "text-muted-foreground";
  let label = "";
  if (count < limit * 0.5) {
    colorClass = "text-red-500";
    label = "Too short";
  } else if (count < limit) {
    colorClass = "text-amber-500";
    label = "Under minimum";
  } else {
    colorClass = "text-green-600";
    label = "Minimum met";
  }
  return (
    <div className="flex items-center gap-2 px-3 py-1 bg-secondary/50 rounded-full text-sm">
      <Type className={`h-4 w-4 ${colorClass}`} />
      <span className={`font-medium ${colorClass}`}>{count} / {limit}</span>
      <span className="text-xs text-muted-foreground">({label})</span>
    </div>
  );
}

export default function WritingWorkspacePage() {
  // Task selection
  const [selectedTask, setSelectedTask] = useState<"task_1" | "task_2">("task_2");
  const [promptsLoading, setPromptsLoading] = useState(true);
  const [prompts, setPrompts] = useState<WritingWorkspacePrompt[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Active submission
  const [submission, setSubmission] = useState<WritingWorkspaceSubmission | null>(null);
  const [essayText, setEssayText] = useState("");
  const [timeSpent, setTimeSpent] = useState(0);
  const [isTimerRunning, setIsTimerRunning] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluation, setEvaluation] = useState<WritingEvaluation | null>(null);
  const [improvementPlan, setImprovementPlan] = useState<WritingImprovementPlan | null>(null);
  const [isPlanLoading, setIsPlanLoading] = useState(false);
  const [showPlanModal, setShowPlanModal] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Load prompts
  const loadPrompts = useCallback(async () => {
    setPromptsLoading(true);
    setError(null);
    try {
      const data: WritingWorkspacePromptsResponse = await writingWorkspaceService.getPrompts(selectedTask);
      setPrompts(data.prompts);
    } catch (err: any) {
      setError(err?.message || "Failed to load prompts");
    } finally {
      setPromptsLoading(false);
    }
  }, [selectedTask]);

  useEffect(() => {
    void loadPrompts();
  }, [loadPrompts]);

  // Timer
  useEffect(() => {
    if (isTimerRunning) {
      timerRef.current = setInterval(() => {
        setTimeSpent(prev => prev + 1);
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isTimerRunning]);

  // Auto-save (every 30 seconds or on blur)
  const autoSave = useCallback(async () => {
    if (!submission || submission.is_locked) return;

    const word_count = essayText.trim() ? essayText.trim().split(/\s+/).length : 0;
    setIsSaving(true);
    try {
      const updated = await writingWorkspaceService.autoSave(submission.id, {
        essay_text: essayText,
        time_seconds_spent: timeSpent,
      });
      setSubmission(updated);
    } catch (err: any) {
      console.error("Auto-save failed:", err);
    } finally {
      setIsSaving(false);
    }
  }, [submission, essayText, timeSpent]);

  // Periodic auto-save every 30 seconds
  useEffect(() => {
    if (!submission || submission.is_locked) return;
    const interval = setInterval(() => {
      void autoSave();
    }, 30000);
    return () => clearInterval(interval);
  }, [submission, autoSave]);

  // Handle prompt selection
  const handleSelectPrompt = async (prompt: WritingWorkspacePrompt) => {
    try {
      const data = await writingWorkspaceService.startSubmission({ prompt_id: prompt.id });
      setSubmission(data);
      setEssayText(data.essay_text);
      setTimeSpent(data.time_seconds_spent);
      setIsTimerRunning(true);
    } catch (err: any) {
      setError(err?.message || "Failed to start submission");
    }
  };

  // Handle text change
  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEssayText(e.target.value);
  };

  // Submit
  const handleSubmit = async () => {
    if (!submission) return;
    setIsSubmitting(true);
    try {
      const updated = await writingWorkspaceService.submit(submission.id, {
        time_seconds_spent: timeSpent,
      });
      setSubmission(updated);
      setIsTimerRunning(false);
      setShowSubmitModal(false);
      setShowSummary(true);
    } catch (err: any) {
      setError(err?.message || "Failed to submit");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Evaluate with AI
  const handleEvaluate = async () => {
    if (!submission) return;
    setIsEvaluating(true);
    try {
      const result = await writingEvaluationService.evaluateSubmission(
        submission.id,
        submission.task_type
      );
      setEvaluation(result);
    } catch (err: any) {
      setError(err?.message || "Failed to evaluate essay");
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleGeneratePlan = async (targetBand?: number) => {
    if (!submission) return;
    setIsPlanLoading(true);
    setError(null);
    try {
      const plan = await writingImprovementPlanService.generatePlan(
        submission.id,
        targetBand
      );
      setImprovementPlan(plan);
      setShowPlanModal(true);
    } catch (err: any) {
      setError(err?.message || "Failed to generate improvement plan");
    } finally {
      setIsPlanLoading(false);
    }
  };

  // Load existing evaluation when submission is loaded
  const loadEvaluation = useCallback(async () => {
    if (!submission) return;
    try {
      const result = await writingEvaluationService.getEvaluation(submission.id);
      setEvaluation(result);
    } catch {
      // No evaluation yet — that's fine
    }
  }, [submission]);

  useEffect(() => {
    if (submission?.is_locked && !evaluation) {
      void loadEvaluation();
    }
  }, [submission?.is_locked, loadEvaluation, evaluation]);

  // Resume existing submission
  const resumeSubmission = async (sub: WritingWorkspaceSubmission) => {
    setSubmission(sub);
    setEssayText(sub.essay_text);
    setTimeSpent(sub.time_seconds_spent);
    setIsTimerRunning(sub.status === "draft");
  };

  // Load existing submissions
  const [submissionsList, setSubmissionsList] = useState<WritingWorkspaceSubmission[]>([]);
  const [showSubmissions, setShowSubmissions] = useState(false);

  const loadSubmissions = useCallback(async () => {
    try {
      const data = await writingWorkspaceService.listSubmissions();
      setSubmissionsList(data.results);
      setShowSubmissions(true);
    } catch (err: any) {
      setError(err?.message || "Failed to load submissions");
    }
  }, []);

  const taskTime = selectedTask === "task_1" ? TASK_1_TIME : TASK_2_TIME;
  const wordCount = essayText.trim() ? essayText.trim().split(/\s+/).length : 0;
  const wordLimit = submission ? submission.word_limit : (selectedTask === "task_1" ? 150 : 250);
  const timeLimit = submission ? submission.time_limit_seconds : taskTime;
  const timeRemaining = timeLimit - timeSpent;
  const isOverTime = timeRemaining <= 0;

  const warnings: string[] = [];
  if (submission && wordCount < wordLimit) {
    warnings.push(`Word count (${wordCount}) is below the minimum (${wordLimit})`);
  }
  if (isOverTime) {
    warnings.push(`Time limit (${formatTime(timeLimit)}) has been exceeded`);
  }
  if (!essayText.trim()) {
    warnings.push("Your essay is empty");
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <PenTool className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Writing Workspace</h1>
              <p className="text-sm text-muted-foreground">
                Practice IELTS Writing Task 1 & Task 2 with timed sessions
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {submissionsList.length > 0 && (
              <Button variant="outline" size="sm" onClick={() => setShowSubmissions(true)}>
                <FileText className="h-4 w-4 mr-2" />
                My Essays ({submissionsList.length})
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={loadSubmissions}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-error/5 border border-error/30 text-error text-sm">
            {error}
          </div>
        )}

        {!submission ? (
          <TaskSelector
            selectedTask={selectedTask}
            onTaskChange={setSelectedTask}
            prompts={prompts}
            loading={promptsLoading}
            onSelectPrompt={handleSelectPrompt}
            submissionsList={submissionsList}
            onResumeSubmission={resumeSubmission}
            loadSubmissions={loadSubmissions}
          />
        ) : (
          <EditorView
            submission={submission}
            essayText={essayText}
            timeSpent={timeSpent}
            wordCount={wordCount}
            wordLimit={wordLimit}
            timeLimit={timeLimit}
            isTimerRunning={isTimerRunning}
            setIsTimerRunning={setIsTimerRunning}
            onTextChange={handleTextChange}
            onSave={autoSave}
            isSaving={isSaving}
            onSubmit={() => setShowSubmitModal(true)}
            onBack={() => {
              // Save before navigating back
              void autoSave().then(() => {
                setSubmission(null);
                setShowSubmissions(false);
              });
            }}
            warnings={warnings}
          />
        )}

        {/* Submit Confirmation Modal */}
        <Modal isOpen={showSubmitModal} onClose={() => setShowSubmitModal(false)}>
          <ModalHeader>
            <ModalTitle>Submit Essay for Evaluation</ModalTitle>
          </ModalHeader>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Word Count:</span>
                <span className="font-medium">{wordCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Required:</span>
                <span className="font-medium">{wordLimit}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Time Spent:</span>
                <span className="font-medium">{formatTime(timeSpent)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Time Limit:</span>
                <span className="font-medium">{formatTime(timeLimit)}</span>
              </div>
            </div>
            {warnings.length > 0 && (
              <div className="p-3 rounded-lg bg-amber-50/30 border border-amber-200/30">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-amber-800 dark:text-amber-300 text-sm">
                      Warnings:
                    </p>
                    <ul className="text-xs text-amber-700 dark:text-amber-400 mt-1 list-disc list-inside">
                      {warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </div>
                </div>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Once submitted, your essay will be locked and cannot be edited.
            </p>
          </div>
          <ModalFooter>
            <Button variant="outline" size="sm" onClick={() => setShowSubmitModal(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSubmit}
              disabled={isSubmitting}
              variant={warnings.length > 0 ? "destructive" : "default"}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Submitting...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4 mr-2" />
                  Submit Essay
                </>
              )}
            </Button>
          </ModalFooter>
        </Modal>

        {/* Submission Summary Modal */}
        <Modal isOpen={showSummary} onClose={() => setShowSummary(false)}>
          <ModalHeader>
            <ModalTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              Submission Successful
            </ModalTitle>
          </ModalHeader>
          <div className="space-y-4 py-4">
            <p className="text-sm">Your essay has been submitted and locked for evaluation.</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-xs text-muted-foreground">Word Count</span>
                <p className="font-bold">{wordCount} / {wordLimit}</p>
              </div>
              <div>
                <span className="text-xs text-muted-foreground">Time Spent</span>
                <p className="font-bold">{formatTime(timeSpent)}</p>
              </div>
              <div>
                <span className="text-xs text-muted-foreground">Task</span>
                <p className="font-bold">{submission?.task_type === "task_1" ? "Task 1" : "Task 2"}</p>
              </div>
              <div>
                <span className="text-xs text-muted-foreground">Status</span>
                <p className="font-bold text-green-600">Submitted</p>
              </div>
              <div>
                <span className="text-xs text-muted-foreground">Evaluation</span>
                <p className="font-bold text-amber-600">
                  {evaluation?.evaluation_status === "evaluated" ? "Completed" :
                   evaluation?.evaluation_status === "pending" ? "Pending" :
                   "Not started"}
                </p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Your essay is locked. Click &quot;Evaluate with AI&quot; below to receive a
              full assessment across all four IELTS criteria. This is an AI
              estimate, not an official IELTS score.
            </p>
            {warnings.length > 0 && (
              <div className="text-xs text-amber-600">
                Your submission has warnings that will be noted in evaluation.
              </div>
            )}
            {evaluation?.evaluation_status === "evaluated" && evaluation.overall_band !== null && (
              <div className="mt-3 p-3 rounded-lg bg-green-50/30 border border-green-200/30">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Overall Band</span>
                  <span className="text-2xl font-bold text-green-700 dark:text-green-300">
                    {evaluation.overall_band.toFixed(1)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Confidence: {(evaluation.confidence || 0).toFixed(2)}
                  {" · "} AI estimate (not official IELTS)
                </p>
              </div>
            )}
             <Button
               size="sm"
               onClick={handleEvaluate}
               disabled={isEvaluating || evaluation?.evaluation_status === "evaluated"}
               className="w-full mt-2"
             >
               {isEvaluating ? (
                 <>
                   <Loader2 className="h-4 w-4 animate-spin mr-2" />
                   Evaluating...
                 </>
               ) : (
                 <>
                   <BarChart3 className="h-4 w-4 mr-2" />
                   Evaluate with AI
                 </>
               )}
             </Button>
              {evaluation?.overall_band != null && (
                <div className="mt-3 pt-3 border-t border-border space-y-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleGeneratePlan()}
                    disabled={isPlanLoading}
                    className="w-full"
                  >
                    {isPlanLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Generating plan...
                      </>
                    ) : (
                      <>
                        <Target className="h-4 w-4 mr-2" />
                        Improve My Band
                      </>
                    )}
                  </Button>
                </div>
              )}
           </div>
           <ModalFooter>
             <Button size="sm" onClick={() => setShowSummary(false)}>
               Close
             </Button>
           </ModalFooter>
          </Modal>

        {/* Evaluation Detail Modal */}
        {evaluation && evaluation.evaluation_status === "evaluated" && evaluation.criteria && (
          <EvaluationDetailModal
            evaluation={evaluation}
            essayText={essayText}
            onClose={() => setEvaluation(null)}
            onImproveMyBand={() => handleGeneratePlan()}
          />
        )}

        {/* Improve My Band Modal */}
        {showPlanModal && improvementPlan && (
          <ImproveMyBandModal
            plan={improvementPlan}
            onClose={() => setShowPlanModal(false)}
          />
        )}
      </div>
    </DashboardLayout>
  );
}

// ─── Task Selector Component ─────────────────────────────────────────
function TaskSelector({
  selectedTask,
  onTaskChange,
  prompts,
  loading,
  onSelectPrompt,
  submissionsList,
  onResumeSubmission,
  loadSubmissions,
}: {
  selectedTask: "task_1" | "task_2";
  onTaskChange: (task: "task_1" | "task_2") => void;
  prompts: WritingWorkspacePrompt[];
  loading: boolean;
  onSelectPrompt: (prompt: WritingWorkspacePrompt) => void;
  submissionsList: WritingWorkspaceSubmission[];
  onResumeSubmission: (sub: WritingWorkspaceSubmission) => void;
  loadSubmissions: () => void;
}) {
  return (
    <div className="grid lg:grid-cols-3 gap-6">
      {/* Task type selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Target className="h-5 w-5 text-primary" />
            Select Writing Task
          </CardTitle>
          <CardDescription>
            Choose between Task 1 (report/letter) or Task 2 (essay)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Button
              variant={selectedTask === "task_1" ? "default" : "outline"}
              className="w-full justify-start"
              onClick={() => onTaskChange("task_1")}
            >
              <div className="flex flex-col text-left">
                <span>Task 1 — {WRITING_WORKSPACE_TASK_LABELS.task_1}</span>
                <span className="text-xs text-muted-foreground">
                  {WRITING_WORKSPACE_TASK_DESCRIPTIONS.task_1}
                </span>
              </div>
            </Button>
            <Button
              variant={selectedTask === "task_2" ? "default" : "outline"}
              className="w-full justify-start"
              onClick={() => onTaskChange("task_2")}
            >
              <div className="flex flex-col text-left">
                <span>Task 2 — {WRITING_WORKSPACE_TASK_LABELS.task_2}</span>
                <span className="text-xs text-muted-foreground">
                  {WRITING_WORKSPACE_TASK_DESCRIPTIONS.task_2}
                </span>
              </div>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Prompt selection */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BookOpen className="h-5 w-5 text-blue-600" />
            Available Prompts
          </CardTitle>
          <CardDescription>
            {loading ? "Loading prompts..." : `${prompts.length} prompts available for ${WRITING_WORKSPACE_TASK_LABELS[selectedTask]}`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <Skeleton key={i} className="h-20 rounded-lg" />
              ))}
            </div>
          ) : prompts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No prompts available.</p>
          ) : (
            <div className="space-y-4">
              {prompts.map((prompt) => (
                <div
                  key={prompt.id}
                  className="border border-border rounded-lg p-4 hover:bg-secondary/50 transition-colors cursor-pointer"
                  onClick={() => onSelectPrompt(prompt)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-medium">{prompt.title}</h3>
                    <Badge variant="outline" className="text-xs">
                      {prompt.difficulty}/5
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                    {prompt.prompt_text}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Type className="h-3 w-3" /> {prompt.word_limit} words
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" /> {formatTime(prompt.time_limit_seconds)}
                    </span>
                    {prompt.topics && prompt.topics.length > 0 && (
                      <span>Topics: {prompt.topics.join(", ")}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Resume section */}
      {submissionsList.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <FileText className="h-5 w-5 text-green-600" />
              Resume Draft
            </CardTitle>
            <CardDescription>
              Continue working on a saved draft
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {submissionsList
                .filter(s => s.status === "draft" && !s.is_locked)
                .map(sub => (
                  <div
                    key={sub.id}
                    className="cursor-pointer p-3 border border-border rounded-lg hover:bg-secondary/50 transition-colors"
                    onClick={() => onResumeSubmission(sub)}
                  >
                    <p className="font-medium text-sm line-clamp-1">{sub.title}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="secondary" className="text-xs">
                        {sub.task_type === "task_1" ? "Task 1" : "Task 2"}
                      </Badge>
                      <span>{sub.word_count} words</span>
                      <span>{formatTime(sub.time_seconds_spent)}</span>
                    </div>
                  </div>
                ))}
              {submissionsList.filter(s => s.status === "draft" && !s.is_locked).length === 0 && (
                <p className="text-xs text-muted-foreground">No drafts to resume.</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─── Editor View Component ────────────────────────────────────────────
function EditorView({
  submission,
  essayText,
  timeSpent,
  wordCount,
  wordLimit,
  timeLimit,
  isTimerRunning,
  setIsTimerRunning,
  onTextChange,
  onSave,
  isSaving,
  onSubmit,
  onBack,
  warnings,
}: {
  submission: WritingWorkspaceSubmission | null;
  essayText: string;
  timeSpent: number;
  wordCount: number;
  wordLimit: number;
  timeLimit: number;
  isTimerRunning: boolean;
  setIsTimerRunning: (v: boolean) => void;
  onTextChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onSave: () => void;
  isSaving: boolean;
  onSubmit: () => void;
  onBack: () => void;
  warnings: string[];
}) {
  const timeRemaining = timeLimit - timeSpent;
  const isOverTime = timeRemaining <= 0;

  return (
    <div className="flex flex-col h-[calc(100vh-220px)]">
      {/* Top bar: prompt info + controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack}>
            <X className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="text-lg font-bold">
              {submission?.task_type === "task_1" ? "Academic Task 1" : "Task 2 Essay"}
            </h2>
            <p className="text-sm text-muted-foreground line-clamp-1">
              {submission?.title}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsTimerRunning(!isTimerRunning)}
            disabled={submission?.is_locked}
          >
            {isTimerRunning ? (
              <Pause className="h-4 w-4 mr-1" />
            ) : (
              <Play className="h-4 w-4 mr-1" />
            )}
            {isTimerRunning ? "Pause" : "Resume"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onSave}
            disabled={isSaving || submission?.is_locked}
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            {isSaving ? "Saving..." : "Save Draft"}
          </Button>
        </div>
      </div>

      {/* Prompt display */}
      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
            IELTS Writing Question
          </CardTitle>
        </CardHeader>
        <CardContent className="prose prose-slate dark:prose-invert max-w-none">
          <p className="text-lg leading-relaxed">{submission?.prompt_text}</p>
        </CardContent>
      </Card>

      {/* Instructions + stats */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span>Word limit: {wordLimit}</span>
          <span>Time limit: {formatTime(timeLimit)}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 bg-secondary/50 rounded-full font-mono text-lg font-bold">
            <Timer className={`h-4 w-4 ${isOverTime ? "text-error" : "text-primary"}`} />
            {formatTime(timeRemaining)}
          </div>
          <WordCountBadge count={wordCount} limit={wordLimit} />
        </div>
      </div>

      {/* Word count warning */}
      {wordCount < wordLimit && !submission?.is_locked && (
        <div className="p-2 rounded-lg bg-amber-50/30 border border-amber-200/30 text-amber-800 dark:text-amber-300 text-xs mb-3">
          <AlertTriangle className="h-3 w-3 inline mr-1" />
          Your essay is {wordCount} words. IELTS {submission?.task_type === "task_1" ? "Task 1" : "Task 2"} requires at least {wordLimit} words.
        </div>
      )}

      {/* Editor */}
      <div className="flex-1 min-h-0 border border-border rounded-lg overflow-hidden">
        <Textarea
          className="h-full w-full border-none rounded-none p-4 text-lg leading-relaxed focus-visible:ring-0 resize-none bg-transparent min-h-[300px]"
          placeholder="Type your essay here..."
          value={essayText}
          onChange={onTextChange}
          disabled={submission?.is_locked}
        />
      </div>

      {/* Submit bar */}
      {!submission?.is_locked && (
        <div className="flex items-center justify-between mt-4">
          <div className="flex items-center gap-2">
            {warnings.length > 0 && (
              <Badge variant="destructive" className="text-xs">
                {warnings.length} warning{warnings.length !== 1 ? "s" : ""}
              </Badge>
            )}
            <span className="text-xs text-muted-foreground">
              {wordCount} / {wordLimit} words · {formatTime(timeSpent)} spent
            </span>
          </div>
          <Button
            onClick={onSubmit}
            disabled={wordCount < 1}
            variant={warnings.length > 0 ? "outline" : "default"}
          >
            <Send className="h-4 w-4 mr-2" />
            Submit for Evaluation
          </Button>
        </div>
      )}

      {submission?.is_locked && (
        <div className="mt-4 p-3 rounded-lg bg-green-50/30 border border-green-200/30 text-green-800 dark:text-green-300 text-sm">
          <CheckCircle2 className="h-4 w-4 inline mr-1" />
          This essay has been submitted and locked for evaluation.
        </div>
      )}
    </div>
  );
}

// ─── Icons ────────────────────────────────────────────────────────────
function Play(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg {...props} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="6 4 20 12 6 20" />
    </svg>
  );
}
function Pause(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg {...props} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="6" y="6" width="4" height="12" />
      <rect x="14" y="6" width="4" height="12" />
    </svg>
  );
}

// ─── Error Analysis UI helpers ──────────────────────────────────────────
const ERROR_TYPE_COLORS: Record<string, string> = {
  Grammar: "bg-rose-500/15 text-rose-600 dark:text-rose-300 border-rose-400/50",
  Vocabulary: "bg-violet-500/15 text-violet-600 dark:text-violet-300 border-violet-400/50",
  Spelling: "bg-red-500/15 text-red-600 dark:text-red-300 border-red-400/50",
  Punctuation: "bg-sky-500/15 text-sky-600 dark:text-sky-300 border-sky-400/50",
  "Sentence Structure": "bg-orange-500/15 text-orange-600 dark:text-orange-300 border-orange-400/50",
  Cohesion: "bg-teal-500/15 text-teal-600 dark:text-teal-300 border-teal-400/50",
  Repetition: "bg-fuchsia-500/15 text-fuchsia-600 dark:text-fuchsia-300 border-fuchsia-400/50",
  "Word Choice": "bg-indigo-500/15 text-indigo-600 dark:text-indigo-300 border-indigo-400/50",
  "Task Response": "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-400/50",
};

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  major: "bg-amber-500",
  minor: "bg-blue-400",
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: "Critical",
  major: "Major",
  minor: "Minor",
};

const CRITERION_LABEL: Record<string, string> = {
  task_response: "Task Response / Achievement",
  coherence_cohesion: "Coherence & Cohesion",
  lexical_resource: "Lexical Resource",
  grammatical_range_accuracy: "Grammatical Range & Accuracy",
};

/**
 * Render the essay with clickable, highlighted spans for each detected issue.
 * Errors with unusable offsets (start === 0 && end === 0) are skipped by the
 * highlighting but still appear in the error list. Overlapping ranges are
 * chained so no text is dropped.
 */
function HighlightedEssay({
  text,
  errors,
  selectedId,
  onSelect,
}: {
  text: string;
  errors: WritingError[];
  selectedId?: string | null;
  onSelect: (err: WritingError) => void;
}) {
  const highlightable = errors.filter(
    (e) => e.end > e.start && e.start >= 0 && e.end <= text.length + 1
  );
  if (highlightable.length === 0) {
    return (
      <p className="text-sm text-muted-foreground whitespace-pre-wrap">
        {text || "—"}
      </p>
    );
  }

  const ranges = highlightable
    .slice()
    .sort((a, b) => a.start - b.start || a.end - b.end);

  const segments: { text: string; error?: WritingError }[] = [];
  let pos = 0;
  for (const err of ranges) {
    if (err.start > pos) {
      segments.push({ text: text.slice(pos, err.start) });
      pos = err.start;
    }
    const end = Math.min(err.end, text.length);
    if (end > pos) {
      segments.push({ text: text.slice(pos, end), error: err });
      pos = end;
    }
  }
  if (pos < text.length) segments.push({ text: text.slice(pos) });

  return (
    <p className="text-sm leading-relaxed whitespace-pre-wrap">
      {segments.map((seg, i) =>
        seg.error ? (
          <button
            key={`hl-${seg.error.id}-${i}`}
            type="button"
            onClick={() => onSelect(seg.error!)}
            className={`inline px-0.5 rounded font-medium border-b-2 underline decoration-wavy decoration-1 ${
              ERROR_TYPE_COLORS[seg.error.error_type] ?? ERROR_TYPE_COLORS.Grammar
            } ${selectedId === seg.error.id ? "ring-2 ring-offset-1 ring-primary/70" : ""}`}
            title={seg.error.explanation}
          >
            {seg.text}
          </button>
        ) : (
          <React.Fragment key={`tx-${i}`}>{seg.text}</React.Fragment>
        )
      )}
    </p>
  );
}

// ─── Evaluation Detail Modal Component ──────────────────────────────────
function EvaluationDetailModal({
  evaluation,
  essayText,
  onClose,
  onImproveMyBand,
}: {
  evaluation: WritingEvaluation;
  essayText: string;
  onClose: () => void;
  onImproveMyBand: () => void;
}) {
  const {
    overall_band,
    confidence,
    criteria,
    strengths,
    weaknesses,
    errors,
    suggestions,
    word_count,
    is_estimate,
    error_analysis,
  } = evaluation;

  const analysisErrors = error_analysis || [];

  // Group issues by error type for a tidy, clickable summary.
  const grouped = analysisErrors.reduce<Record<string, WritingError[]>>((acc, e) => {
    if (!acc[e.error_type]) acc[e.error_type] = [];
    acc[e.error_type].push(e);
    return acc;
  }, {});
  const groupedKeys = Object.keys(grouped);

  const [selectedErrorId, setSelectedErrorId] = useState<string | null>(
    analysisErrors.length > 0 ? analysisErrors[0].id : null
  );
  const selectedError =
    analysisErrors.find((e) => e.id === selectedErrorId) ?? null;

  const criterionOrder: (keyof typeof criteria)[] = [
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammatical_range_accuracy",
  ];

  return (
    <Modal isOpen={true} onClose={onClose} className="max-w-4xl">
      <ModalHeader>
        <ModalTitle className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-primary" />
          AI Writing Evaluation
        </ModalTitle>
      </ModalHeader>
      <div className="max-h-[70vh] overflow-y-auto py-4 space-y-6">
        {/* Overall band */}
        <div className="flex items-center justify-center gap-4 p-4 bg-primary/5 rounded-lg border">
          <div className="text-center">
            <span className="text-sm text-muted-foreground">Overall Band</span>
            <p className="text-4xl font-bold text-primary">
              {overall_band?.toFixed(1) ?? "—"}
            </p>
          </div>
          <div className="text-center">
            <span className="text-sm text-muted-foreground">Confidence</span>
            <p className="text-2xl font-bold">
              {(confidence || 0).toFixed(2)}
            </p>
          </div>
        </div>
        {is_estimate && (
          <p className="text-xs text-muted-foreground text-center">
            AI estimate — this is NOT an official IELTS score.
          </p>
        )}

        {/* Criterion breakdown */}
        <div className="space-y-4">
          {criterionOrder.map((key) => {
            const c = criteria[key];
            return (
              <Card key={key}>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center justify-between text-base">
                    <span>{c.label}</span>
                    <Badge variant="outline" className="text-lg font-bold">
                      {c.band.toFixed(1)}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div>
                    <span className="font-medium text-green-700">Strength:</span>{" "}
                    <span className="text-muted-foreground">{c.strength}</span>
                  </div>
                  <div>
                    <span className="font-medium text-amber-700">Weakness:</span>{" "}
                    <span className="text-muted-foreground">{c.weakness}</span>
                  </div>
                  {c.errors.length > 0 && (
                    <div>
                      <span className="font-medium text-red-700">Errors:</span>
                      <ul className="list-disc list-inside text-muted-foreground mt-1">
                        {c.errors.map((err, i) => (
                          <li key={`err-${key}-${i}`}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {c.suggestions.length > 0 && (
                    <div>
                      <span className="font-medium text-blue-700">Suggestions:</span>
                      <ul className="list-disc list-inside text-muted-foreground mt-1">
                        {c.suggestions.map((s, i) => (
                          <li key={`sug-${key}-${i}`}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Aggregated insights */}
        {(strengths.length > 0 || weaknesses.length > 0 || errors.length > 0 || suggestions.length > 0) && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Detailed Insights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {strengths.length > 0 && (
                <div>
                  <span className="font-medium">Strengths:</span>
                  <ul className="list-disc list-inside">
                    {strengths.map((s, i) => <li key={`s-${i}`}>{s}</li>)}
                  </ul>
                </div>
              )}
              {weaknesses.length > 0 && (
                <div>
                  <span className="font-medium">Weaknesses:</span>
                  <ul className="list-disc list-inside">
                    {weaknesses.map((w, i) => <li key={`w-${i}`}>{w}</li>)}
                  </ul>
                </div>
              )}
              {errors.length > 0 && (
                <div>
                  <span className="font-medium">Specific Errors:</span>
                  <ul className="list-disc list-inside">
                    {errors.map((e, i) => <li key={`e-${i}`}>{e}</li>)}
                  </ul>
                </div>
              )}
              {suggestions.length > 0 && (
                <div>
                  <span className="font-medium">Improvement Suggestions:</span>
                  <ul className="list-disc list-inside">
                    {suggestions.map((s, i) => <li key={`i-${i}`}>{s}</li>)}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        )}

{/* ─── Writing Error Analysis ─── */}
        {analysisErrors.length > 0 && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-semibold">Writing Error Analysis</h3>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                {(["critical", "major", "minor"] as const).map((s) => (
                  <span key={s} className="inline-flex items-center gap-1">
                    <span className={`h-2.5 w-2.5 rounded-full ${SEVERITY_DOT[s]}`} />
                    {SEVERITY_LABEL[s]}
                  </span>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">
                    Your essay
                    <span className="ml-2 font-normal text-xs text-muted-foreground">
                      — click any highlighted section
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="max-h-80 overflow-y-auto rounded-md border bg-secondary/20 p-3">
                  <HighlightedEssay
                    text={essayText}
                    errors={analysisErrors}
                    selectedId={selectedErrorId}
                    onSelect={(e) => setSelectedErrorId(e.id)}
                  />
                </CardContent>
              </Card>
              <div className="space-y-3">
                {/* Grouped, clickable error list */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">
                      Issues by category ({analysisErrors.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 max-h-52 overflow-y-auto">
                    {groupedKeys.map((type) => (
                      <div key={type}>
                        <div className="mb-1 text-xs font-semibold uppercase tracking-wide">
                          {type} · {grouped[type].length}
                        </div>
                        <div className="space-y-1">
                          {grouped[type].map((e2) => (
                            <button
                              key={e2.id}
                              type="button"
                              onClick={() => setSelectedErrorId(e2.id)}
                              className={`w-full truncate text-left text-sm px-2 py-1.5 rounded-md border transition-colors ${
                                selectedErrorId === e2.id
                                  ? "ring-1 ring-primary bg-primary/10"
                                  : "hover:bg-secondary/50"
                              } ${ERROR_TYPE_COLORS[e2.error_type] ?? ""}`}
                            >
                              <span className="inline-flex items-center gap-1.5">
                                <span
                                  className={`h-2 w-2 flex-shrink-0 rounded-full ${
                                    SEVERITY_DOT[e2.severity] ?? "bg-gray-400"
                                  }`}
                                />
                                <span className="truncate inline-block align-middle">
                                  “{e2.original}”
                                </span>
                              </span>
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                {/* Detail panel */}
                {selectedError && (
                  <Card className="border-l-4 border-l-primary">
                    <CardHeader className="pb-2">
                      <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                        <span
                          className={`px-2 py-0.5 rounded-md text-xs font-semibold border ${
                            ERROR_TYPE_COLORS[selectedError.error_type] ?? ""
                          }`}
                        >
                          {selectedError.error_type}
                        </span>
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <span
                            className={`h-2 w-2 rounded-full ${
                              SEVERITY_DOT[selectedError.severity] ?? "bg-gray-400"
                            }`}
                          />
                          {SEVERITY_LABEL[selectedError.severity] ?? selectedError.severity}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {CRITERION_LABEL[selectedError.criterion] ?? selectedError.criterion}
                        </span>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <div>
                        <div className="font-medium text-red-600 dark:text-red-400">
                          What is wrong?
                        </div>
                        <p className="text-muted-foreground">“{selectedError.original}”</p>
                      </div>
                      <div>
                        <div className="font-medium text-amber-600 dark:text-amber-400">
                          Why is it wrong?
                        </div>
                        <p className="text-muted-foreground">{selectedError.explanation}</p>
                      </div>
                      <div>
                        <div className="font-medium text-green-600 dark:text-green-400">
                          How can I improve?
                        </div>
                        <p className="text-muted-foreground">{selectedError.correction}</p>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Apply this fix yourself — your essay is never rewritten automatically.
                      </p>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </div>
        )}
        <p className="text-xs text-muted-foreground text-center">
          Word count: {word_count} · Source: {evaluation.source}
        </p>
        <div className="pt-2 border-t border-border">
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            onClick={() => {
              onClose();
              onImproveMyBand();
            }}
          >
            <Target className="h-4 w-4 mr-2" />
            Improve My Band
          </Button>
        </div>
      </div>
      <ModalFooter>
        <Button size="sm" variant="outline" onClick={onClose}>
          Close
        </Button>
      </ModalFooter>
    </Modal>
  );
}

// ─── Improve My Band Modal ───────────────────────────────────────────
function ImproveMyBandModal({
  plan,
  onClose,
}: {
  plan: WritingImprovementPlan;
  onClose: () => void;
}) {
  const PRIORITY_COLOR: Record<string, string> = {
    high: "bg-red-500/15 text-red-600 dark:text-red-300 border-red-400/50",
    medium: "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-400/50",
    low: "bg-blue-500/15 text-blue-600 dark:text-blue-300 border-blue-400/50",
  };

  return (
    <Modal isOpen={true} onClose={onClose} className="max-w-4xl">
      <ModalHeader>
        <ModalTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-primary" />
          Improve My Band
        </ModalTitle>
      </ModalHeader>

      <div className="max-h-[70vh] overflow-y-auto py-4 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Current Band</span>
              <p className="text-3xl font-bold text-primary">{plan.current_band.toFixed(1)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Target Band</span>
              <p className="text-3xl font-bold text-green-600 dark:text-green-400">{plan.target_band.toFixed(1)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <span className="text-xs text-muted-foreground">Gap to Target</span>
              <p className="text-3xl font-bold text-amber-600 dark:text-amber-400">+{plan.band_gap.toFixed(1)}</p>
            </CardContent>
          </Card>
        </div>

        {plan.weaknesses.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Main Weaknesses</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-decimal list-inside text-sm space-y-1">
                {plan.weaknesses.map((w, i) => (
                  <li key={`weak-${i}`} className="text-muted-foreground capitalize">
                    {w.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-amber-600 dark:text-amber-400">
                What the student is doing now
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{plan.current_level_description}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-green-600 dark:text-green-400">
                What a Band {plan.target_band.toFixed(0)} response requires
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{plan.target_level_description}</p>
            </CardContent>
          </Card>
        </div>

        {plan.specific_changes.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Specific Changes to Make</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {plan.specific_changes.map((c, i) => (
                <div key={`change-${i}`} className="border border-border rounded-lg p-3">
                  <Badge className={`text-xs mb-1 ${PRIORITY_COLOR[c.priority] ?? PRIORITY_COLOR.medium}`}>
                    {c.area} · {c.priority}
                  </Badge>
                  <p className="text-sm text-muted-foreground">{c.change}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {plan.practice_exercises.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Practice Exercises</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {plan.practice_exercises.map((ex, i) => (
                <div key={`ex-${i}`} className="border border-border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm">{ex.title}</span>
                    <Badge variant="outline" className="text-xs">
                      {ex.estimated_minutes} min
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{ex.description}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {plan.recommended_resources.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Recommended Resources</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {plan.recommended_resources.map((res, i) => (
                <div key={`res-${i}`} className="border border-border rounded-lg p-3">
                  <div className="flex items-start justify-between mb-1">
                    <a
                      href={res.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-sm hover:text-primary flex items-center gap-1"
                    >
                      {res.title}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                  <p className="text-sm text-muted-foreground">{res.why}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {plan.suggested_mission && plan.suggested_mission.title && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Target className="h-4 w-4 text-primary" />
                Suggested Next Writing Mission
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <p className="font-medium">{plan.suggested_mission.title}</p>
                <p className="text-sm text-muted-foreground">
                  {plan.suggested_mission.description}
                </p>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <Badge variant="outline" className="text-xs">
                    {plan.suggested_mission.sub_skill === "task_1" ? "Task 1" : "Task 2"}
                  </Badge>
                  <span>{plan.suggested_mission.duration_minutes} min</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {plan.is_estimate && (
          <p className="text-xs text-muted-foreground text-center">
            This plan is an AI estimate based on your evaluation — not official IELTS advice.
          </p>
        )}
      </div>

      <ModalFooter>
        <Button size="sm" variant="outline" onClick={onClose}>
          Close
        </Button>
      </ModalFooter>
    </Modal>
  );
}