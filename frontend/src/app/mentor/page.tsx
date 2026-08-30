"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  GraduationCap,
  MessageSquare,
  AlertCircle,
  CheckCircle2,
  Target,
  TrendingUp,
  ShieldCheck,
  Send,
  RefreshCw,
  ChevronRight,
  Sparkles,
  Sun,
  BookOpen,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { mentorService } from "@/services/api";
import type {
  CoachRequest,
  CoachResponse,
  MentorContextResponse,
  MentorConversationItem,
  MentorConversationResponse,
  MentorMode,
} from "@/types";
import { cn } from "@/app/lib/utils";

const MODES = [
  { value: "daily_coaching" as MentorMode, label: "Daily Coaching", description: "Today's focus", icon: Sun },
  { value: "roadmap_analysis" as MentorMode, label: "Roadmap Analysis", description: "Deep-dive", icon: BookOpen },
  { value: "risk_check" as MentorMode, label: "Risk Check", description: "Readiness", icon: ShieldCheck },
  { value: "ask_mentor" as MentorMode, label: "Ask Mentor", description: "Any question", icon: MessageSquare },
  { value: "missed_day" as MentorMode, label: "Missed Day", description: "Comeback", icon: RefreshCw },
];

const SKILL_LABELS: Record<string, string> = {
  reading: "Reading",
  listening: "Listening",
  writing: "Writing",
  speaking: "Speaking",
  vocabulary: "Vocabulary",
  grammar: "Grammar",
};

function sevIcon(s: string) {
  if (s === "positive") return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
  if (s === "high") return <AlertCircle className="h-4 w-4 text-red-500" />;
  if (s === "medium") return <AlertCircle className="h-4 w-4 text-amber-500" />;
  return <TrendingUp className="h-4 w-4 text-blue-500" />;
}

function sevColor(s: string) {
  if (s === "positive") return "border-emerald-500/30 bg-emerald-500/5";
  if (s === "high") return "border-red-500/30 bg-red-500/5";
  if (s === "medium") return "border-amber-500/30 bg-amber-500/5";
  return "border-blue-500/30 bg-blue-500/5";
}

function actionLabel(a: string) {
  const m: Record<string, string> = {
    complete_task: "Complete",
    prioritize_task: "Prioritize",
    focus_skill: "Focus",
    protect_revision: "Protect",
    keep_streak: "Streak",
    recover_gently: "Recover",
    reach_budget: "Budget",
    generate_roadmap: "Generate",
    review_assessment: "Review",
  };
  return m[a] || a.replace(/_/g, " ");
}

function SkeletonCard() {
  return <Skeleton className="h-28 rounded-xl" />;
}

function buildSummary(ctx: MentorContextResponse) {
  const exam = ctx.exam || {};
  const roadmap = ctx.roadmap || {};
  const history = ctx.study_history || {};
  const prediction = ctx.prediction || {};
  const days = exam.days_remaining ?? null;
  const intensity = exam.intensity || null;
  const cur = ctx.profile?.current_band ?? null;
  const tgt = ctx.profile?.target_band ?? null;
  const gap =
    ctx.band_gap ?? (cur != null && tgt != null ? +(tgt - cur).toFixed(1) : null);
  return {
    days,
    intensity,
    cur,
    tgt,
    gap,
    roadmap: roadmap.progress_percent ?? 0,
    hasRoadmap: roadmap.has_active_plan,
    missed: roadmap.missed_tasks ?? 0,
    readiness: prediction.readiness_score ?? null,
    risk: prediction.risk_level || null,
    streak: history.current_streak ?? 0,
    consistency: history.consistency_percent ?? 0,
    weak: ctx.profile?.weakest_skills || [],
    strong: ctx.profile?.strongest_skills || [],
  };
}

export default function MentorPage() {
  const [ctx, setCtx] = useState<MentorContextResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<MentorMode>("daily_coaching");
  const [question, setQuestion] = useState("");
  const [resp, setResp] = useState<CoachResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<MentorConversationItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const refreshHistory = useCallback(async () => {
    try {
      const list = await mentorService.listConversations({ limit: 20, offset: 0 });
      setHistory(list.items ?? []);
    } catch {
      // History is a soft feature — never block the page on it.
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await mentorService.getContext();
      setCtx(data);
      setMode("daily_coaching");
      setResp(null);
      setShowHistory(true);
      await refreshHistory();
    } catch (e) {
      setError("Could not load your mentor context. Try again.");
    } finally {
      setLoading(false);
    }
  }, [refreshHistory]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCoach = async () => {
    const text = mode === "ask_mentor" ? question.trim() : "Continue coaching";
    if (!text) return;
    setBusy(true);
    setError(null);
    try {
      const payload: CoachRequest = {
        mode,
        message: mode === "ask_mentor" ? text : undefined,
      };
      const data = await mentorService.coach(payload);
      setResp(data);
      if (mode === "ask_mentor") setQuestion("");
      await refreshHistory();
    } catch (e) {
      setError("Session failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    setMode("ask_mentor");
    try {
      const data = await mentorService.ask(question.trim());
      setResp(data);
      setQuestion("");
      await refreshHistory();
    } catch (e) {
      setError("Question failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const handleLoadConversation = async (conv: MentorConversationItem) => {
    try {
      const d: MentorConversationResponse = await mentorService.getConversation(conv.id);
      const msg = d.messages.find((m) => m.role === "mentor");
      setResp({
        conversation_id: d.id,
        mode: d.mode,
        created_at: d.created_at || new Date().toISOString(),
        title: d.title,
        message: {
          role: "mentor",
          content: msg?.content || "No message recorded for this session.",
          generated_by: msg?.structured?.generated_by || "template",
          tone: "neutral",
        },
        context_summary: {},
        insights: [],
        directives: [],
        guardrails: {
          never_generates_plan: true,
          plan_generation_triggered: false,
          analysis_source: "existing_roadmap",
          note: "The AI Mentor coaches within the student's existing roadmap and never generates a study plan from scratch.",
        },
      });
      setMode((d.mode as MentorMode) || "daily_coaching");
    } catch {
      setError("Could not load that session.");
    }
  };

  const Icon = MODES.find((m) => m.value === mode)?.icon || MessageSquare;

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-4">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-64 w-full" />
          <div className="grid gap-4 md:grid-cols-2">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !ctx) {
    return (
      <DashboardLayout>
        <Card className="border-red-500/20 bg-red-500/5">
          <CardContent className="pt-6">
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
            <Button onClick={load} variant="outline" className="mt-3">
              Retry
            </Button>
          </CardContent>
        </Card>
      </DashboardLayout>
    );
  }

  const sum = buildSummary(ctx);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
            <GraduationCap className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">AI Mentor</h1>
            <p className="text-sm text-muted-foreground">
              Your personal IELTS tutor — choose a coaching mode or ask anything.
            </p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Main column */}
          <div className="space-y-6 lg:col-span-2">
            {/* Mode selector */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  onClick={() => {
                    setMode(m.value);
                    setResp(null);
                  }}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-xl border p-3 text-center transition-all",
                    mode === m.value
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border hover:border-primary/40 hover:bg-secondary/50"
                  )}
                >
                  <m.icon
                    className={cn(
                      "h-5 w-5",
                      mode === m.value ? "text-primary" : "text-muted-foreground"
                    )}
                  />
                  <div>
                    <p className="text-xs font-semibold leading-tight">{m.label}</p>
                    <p className="text-[10px] text-muted-foreground leading-tight mt-0.5">
                      {m.description}
                    </p>
                  </div>
                </button>
              ))}
            </div>

            {/* Session card */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Icon className="h-4 w-4 text-primary" />
                  {MODES.find((m) => m.value === mode)?.label}
                </CardTitle>
                <CardDescription>
                  {mode === "ask_mentor"
                    ? "Ask any IELTS question and get a focused answer grounded in your roadmap."
                    : "Review your current performance and next actions within your roadmap."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {mode === "ask_mentor" && (
                  <div className="flex items-end gap-2">
                    <Textarea
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      placeholder="e.g., Explain True/False/Not Given. / Why is my predicted band low? / How do I improve Writing? / Give me today's strategy."
                      className="min-h-[80px] resize-none"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                          e.preventDefault();
                          handleAsk();
                        }
                      }}
                    />
                    <Button
                      onClick={handleAsk}
                      disabled={busy || !question.trim()}
                      className="shrink-0"
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                )}

                <Button onClick={handleCoach} disabled={busy} className="w-full sm:w-auto">
                  {busy ? (
                    <>
                      <Sparkles className="mr-2 h-4 w-4 animate-pulse" />
                      Coaching...
                    </>
                  ) : (
                    <>
                      <Sparkles className="mr-2 h-4 w-4" />
                      Start Session
                    </>
                  )}
                </Button>

                {busy && <Skeleton className="h-40 w-full" />}

                {resp && !busy && (
                  <div className="space-y-4 mt-4">
                    {/* Coaching message */}
                    <div className="rounded-xl border bg-card p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                          <GraduationCap className="h-4 w-4 text-primary" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold leading-tight">
                            {resp.title || MODES.find((m) => m.value === mode)?.label}
                          </p>
                          <p className="text-[10px] text-muted-foreground">
                            {resp.mode} • {new Date(resp.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">
                        {resp.message.content}
                      </p>
                      <div className="mt-3 flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px]">
                          {resp.message.generated_by}
                        </Badge>
                        <Badge variant="secondary" className="text-[10px] capitalize">
                          {resp.message.tone}
                        </Badge>
                      </div>
                    </div>

                    {/* Insights */}
                    {resp.insights.length > 0 && (
                      <Card>
                        <CardHeader className="pb-3">
                          <CardTitle className="text-base flex items-center gap-2">
                            <TrendingUp className="h-4 w-4 text-primary" />
                            Insights
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                          {resp.insights.map((ins, i) => (
                            <div
                              key={i}
                              className={cn(
                                "flex items-start gap-3 rounded-lg border p-3",
                                sevColor(ins.severity)
                              )}
                            >
                              <div className="mt-0.5 shrink-0">{sevIcon(ins.severity)}</div>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                  <p className="text-sm font-medium">{ins.title}</p>
                                  {ins.skill && (
                                    <Badge variant="secondary" className="text-[10px] h-5">
                                      {SKILL_LABELS[ins.skill] || ins.skill}
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                                  {ins.detail}
                                </p>
                              </div>
                            </div>
                          ))}
                        </CardContent>
                      </Card>
                    )}

                    {/* Directives / next steps */}
                    {resp.directives.length > 0 && (
                      <Card>
                        <CardHeader className="pb-3">
                          <CardTitle className="text-base flex items-center gap-2">
                            <Target className="h-4 w-4 text-primary" />
                            Next Steps
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            {resp.directives
                              .sort((a, b) => b.priority - a.priority)
                              .map((d, i) => (
                                <div
                                  key={i}
                                  className="flex items-start gap-3 rounded-lg border border-border p-3"
                                >
                                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                                    {d.priority}
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2">
                                      <Badge variant="outline" className="text-[10px] h-5">
                                        {actionLabel(d.action)}
                                      </Badge>
                                      {d.skill && (
                                        <Badge variant="secondary" className="text-[10px] h-5">
                                          {SKILL_LABELS[d.skill] || d.skill}
                                        </Badge>
                                      )}
                                    </div>
                                    <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
                                      {d.detail}
                                    </p>
                                  </div>
                                </div>
                              ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Guardrails */}
                    <Card className="border-emerald-500/20 bg-emerald-500/5">
                      <CardContent className="pt-4 pb-4">
                        <div className="flex items-center gap-2 text-xs text-emerald-700 dark:text-emerald-400">
                          <ShieldCheck className="h-4 w-4" />
                          <span className="font-medium">Guardrails active</span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                          {resp.guardrails.note}
                        </p>
                      </CardContent>
                    </Card>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right column */}
          <div className="space-y-6">
            {/* Snapshot */}
            {sum && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Your Snapshot</CardTitle>
                  <CardDescription>What the mentor sees.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Exam
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-lg border p-2">
                        <p className="text-[10px] text-muted-foreground">Days Left</p>
                        <p className="text-sm font-bold">{sum.days ?? "—"}</p>
                      </div>
                      <div className="rounded-lg border p-2">
                        <p className="text-[10px] text-muted-foreground">Intensity</p>
                        <p className="text-sm font-bold capitalize">
                          {sum.intensity || "—"}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Bands
                    </p>
                    <div className="grid grid-cols-3 gap-2">
                      <div className="rounded-lg border p-2">
                        <p className="text-[10px] text-muted-foreground">Current</p>
                        <p className="text-sm font-bold">{sum.cur ?? "—"}</p>
                      </div>
                      <div className="rounded-lg border p-2">
                        <p className="text-[10px] text-muted-foreground">Target</p>
                        <p className="text-sm font-bold">{sum.tgt ?? "—"}</p>
                      </div>
                      <div className="rounded-lg border p-2">
                        <p className="text-[10px] text-muted-foreground">Gap</p>
                        <p className="text-sm font-bold">{sum.gap ?? "—"}</p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Roadmap
                    </p>
                    <div className="rounded-lg border p-2">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">Progress</span>
                        <span className="text-xs font-medium">{sum.roadmap.toFixed(0)}%</span>
                      </div>
                      <Progress value={sum.roadmap} className="h-1.5" />
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-[10px] text-muted-foreground">
                          {sum.hasRoadmap ? "Active plan" : "No plan"}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {sum.missed} missed
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Readiness
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-lg border p-2">
                        <p className="text-[10px] text-muted-foreground">Readiness</p>
                        <p className="text-sm font-bold">
                          {sum.readiness != null ? `${sum.readiness}%` : "—"}
                        </p>
                      </div>
                      <div className="rounded-lg border p-2">
                        <p className="text-[10px] text-muted-foreground">Risk</p>
                        <p className="text-sm font-bold capitalize">{sum.risk || "—"}</p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Study Health
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-lg border p-2">
                        <p className="text-[10px] text-muted-foreground">Streak</p>
                        <p className="text-sm font-bold">{sum.streak} days</p>
                      </div>
                      <div className="rounded-lg border p-2">
                        <p className="text-[10px] text-muted-foreground">Consistency</p>
                        <p className="text-sm font-bold">{sum.consistency.toFixed(0)}%</p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Skills
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {sum.weak.map((s) => (
                        <Badge key={s} variant="destructive" className="text-[10px]">
                          {SKILL_LABELS[s] || s}
                        </Badge>
                      ))}
                      {sum.strong.map((s) => (
                        <Badge key={s} variant="success" className="text-[10px]">
                          {SKILL_LABELS[s] || s}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* History */}
            {showHistory && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Recent Sessions</CardTitle>
                </CardHeader>
                <CardContent>
                  {history.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No sessions yet.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {history.map((conv) => (
                        <div
                          key={conv.id}
                          className="flex items-center justify-between rounded-lg border p-2 hover:bg-secondary/50 transition-colors cursor-pointer"
                          onClick={() => handleLoadConversation(conv)}
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium truncate">{conv.title}</p>
                            <p className="text-[10px] text-muted-foreground">
                              {conv.mode} • {conv.message_count} messages
                            </p>
                          </div>
                          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

