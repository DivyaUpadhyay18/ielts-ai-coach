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
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Modal, ModalHeader, ModalTitle, ModalFooter } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { writingWorkspaceService } from "@/services/api";
import type {
  WritingWorkspacePrompt,
  WritingWorkspaceSubmission,
  WritingWorkspacePromptsResponse,
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
            </div>
            {warnings.length > 0 && (
              <div className="text-xs text-amber-600">
                Your submission has warnings that will be noted in evaluation.
              </div>
            )}
          </div>
          <ModalFooter>
            <Button size="sm" onClick={() => setShowSummary(false)}>
              Close
            </Button>
          </ModalFooter>
        </Modal>
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
