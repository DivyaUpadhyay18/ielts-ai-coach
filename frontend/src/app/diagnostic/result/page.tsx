"use client";

import React, { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Trophy,
  TrendingUp,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Lightbulb,
  Clock,
  Target,
  Calendar,
  BookOpen,
  BarChart3,
  Map,
  ArrowLeft,
  Loader2,
  Award,
  Zap,
  RefreshCw,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { diagnosticService } from "@/services/diagnostic";
import { bandEstimationService, studyPlanService, schedulerService } from "@/services/api";
import type { DiagnosticReport, SectionScore } from "@/types/diagnostic";
import type { BandEstimationResponse, StudyPlanGenerateResponse } from "@/types";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function cefrFromBand(band: number): string {
  if (band >= 8.5) return "C2 - Mastery";
  if (band >= 7.5) return "C1 - Advanced";
  if (band >= 6.5) return "B2 - Upper Intermediate";
  if (band >= 5.5) return "B1 - Intermediate";
  if (band >= 4.5) return "A2 - Elementary";
  return "A1 - Beginner";
}

function bandColor(band: number): string {
  if (band >= 7.5) return "text-green-600 bg-green-50 border-green-200";
  if (band >= 6.5) return "text-blue-600 bg-blue-50 border-blue-200";
  if (band >= 5.5) return "text-yellow-600 bg-yellow-50 border-yellow-200";
  return "text-red-600 bg-red-50 border-red-200";
}

function bandProgressColor(band: number): string {
  if (band >= 7.5) return "bg-green-500";
  if (band >= 6.5) return "bg-blue-500";
  if (band >= 5.5) return "bg-yellow-500";
  return "bg-red-500";
}

const SKILL_ICONS: Record<string, React.ReactNode> = {
  reading: <BookOpen className="h-5 w-5" />,
  listening: <BarChart3 className="h-5 w-5" />,
  writing: <BookOpen className="h-5 w-5" />,
  speaking: <Zap className="h-5 w-5" />,
  vocabulary: <Lightbulb className="h-5 w-5" />,
  grammar: <BookOpen className="h-5 w-5" />,
};

const SKILL_LABELS: Record<string, string> = {
  reading: "Reading",
  listening: "Listening",
  writing: "Writing",
  speaking: "Speaking",
  vocabulary: "Lexical Resource",
  grammar: "Grammatical Range",
};

export default function DiagnosticResultPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center text-muted-foreground">Loading...</div>}>
      <DiagnosticResultContent />
    </Suspense>
  );
}

function DiagnosticResultContent() {
  const searchParams = useSearchParams();
  const attemptId = searchParams.get("attempt_id");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [bandEstimation, setBandEstimation] = useState<BandEstimationResponse | null>(null);
  const [estimatingBand, setEstimatingBand] = useState(false);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [generatedPlan, setGeneratedPlan] = useState<StudyPlanGenerateResponse | null>(null);

  const load = useCallback(async () => {
    if (!attemptId) {
      setError("Missing attempt_id parameter.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rep = await diagnosticService.getReport(attemptId);
      setReport(rep as DiagnosticReport);

      // Auto-estimate band from diagnostic skill scores.
      const skillScoresMap = Object.fromEntries(
        (rep.skill_scores || []).map((s) => [s.section, s.band])
      );
      const estimationInput = {
        reading: skillScoresMap.reading || 0,
        listening: skillScoresMap.listening || 0,
        writing: skillScoresMap.writing || 0,
        speaking: skillScoresMap.speaking || 0,
        vocabulary: skillScoresMap.vocabulary || 0,
        grammar: skillScoresMap.grammar || 0,
      };
      setEstimatingBand(true);
      try {
        const est = await bandEstimationService.estimate(estimationInput);
        setBandEstimation(est);
      } catch (e: any) {
        // Band estimation is best-effort — don't block the page.
        console.warn("Band estimation failed:", e);
      } finally {
        setEstimatingBand(false);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load diagnostic report.");
    } finally {
      setLoading(false);
    }
  }, [attemptId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRegenerate = async () => {
    if (!attemptId) return;
    setRegenerating(true);
    try {
      await diagnosticService.completeAttempt(attemptId);
      await load();
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to regenerate report.");
    } finally {
      setRegenerating(false);
    }
  };

  const handleGeneratePlan = async () => {
    setGeneratingPlan(true);
    setError(null);
    try {
      const plan = await studyPlanService.generateFromDiagnostic({
        daily_minutes_budget: 60,
        module: "academic",
      });
      setGeneratedPlan(plan);

      // Trigger the Adaptive Scheduler to rebalance based on the new plan.
      await schedulerService.run("app_open");
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to generate study plan.");
    } finally {
      setGeneratingPlan(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center py-24 space-y-4">
          <Spinner size="lg" />
          <p className="text-muted-foreground">Analyzing your diagnostic results...</p>
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="max-w-4xl mx-auto space-y-6 py-4">
          <Link href="/diagnostic" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Diagnostic
          </Link>
          <Card>
            <CardContent className="py-16 text-center space-y-4">
              <AlertCircle className="h-12 w-12 mx-auto text-error" />
              <p className="text-sm text-error">{error}</p>
              <Button onClick={load} variant="outline">
                <RefreshCw className="mr-2 h-4 w-4" /> Try Again
              </Button>
            </CardContent>
          </Card>
        </div>
      </DashboardLayout>
    );
  }

  if (!report) {
    return null;
  }

  const overallBand = report.overall_band || 0;
  const estimatedBand = bandEstimation?.overall_band ?? 0;
  const totalMinutes = Math.floor((report.total_time_seconds || 0) / 60);
  const avgAccuracy = report.skill_scores?.length
    ? report.skill_scores.reduce((sum, s) => sum + (s.accuracy || 0), 0) / report.skill_scores.length
    : 0;

  return (
    <DashboardLayout>
      <div className="max-w-6xl mx-auto space-y-8 pb-12">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <Badge variant="success" className="mb-2">Assessment Complete</Badge>
            <h1 className="text-3xl font-bold tracking-tight">Your Diagnostic Report</h1>
            <p className="text-muted-foreground mt-1">
              {report.completed_at
                ? `Completed on ${new Date(report.completed_at).toLocaleDateString("en-US", { dateStyle: "long" })}`
                : "Analysis ready"}
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={handleRegenerate}
              disabled={regenerating}
            >
              {regenerating ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Regenerate
            </Button>
            {generatedPlan ? (
              <Link href="/roadmap">
                <Button className="bg-accent hover:bg-accent/90 text-accent-foreground shadow-lg">
                  View My Study Plan <Map className="ml-2 h-5 w-5" />
                </Button>
              </Link>
            ) : (
              <Button
                className="bg-accent hover:bg-accent/90 text-accent-foreground shadow-lg"
                onClick={handleGeneratePlan}
                disabled={generatingPlan || estimatingBand}
              >
                {generatingPlan ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Map className="ml-2 h-5 w-5" />
                )}
                {generatingPlan ? "Generating Plan..." : "Generate My Personalized Study Plan"}
              </Button>
            )}
          </div>
        </div>

        {/* Main Grid */}
        <div className="grid gap-8 lg:grid-cols-3">
          
          {/* Left Column - Main Score & Skills */}
          <div className="lg:col-span-2 space-y-8">
            
            {/* Overall Band Card */}
            <Card className="bg-gradient-to-br from-primary via-blue-600 to-indigo-700 text-white border-none shadow-xl overflow-hidden relative">
              <div className="absolute inset-0 bg-grid-white/10 [mask-image:linear-gradient(0deg,transparent,rgba(255,255,255,0.5))]"></div>
              <CardContent className="relative pt-10 pb-10">
                <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                  <div className="flex flex-col items-center text-center">
                    <div className="relative">
                      <div className="h-36 w-36 rounded-full border-4 border-white/30 flex items-center justify-center bg-white/10 backdrop-blur-sm">
                        <div className="text-center">
                          <span className="text-5xl font-black block">{overallBand.toFixed(1)}</span>
                          <span className="text-xs text-white/70 uppercase tracking-wider">Band</span>
                        </div>
                      </div>
                      <div className="absolute -bottom-1 -right-1">
                        <Badge className="bg-warning text-white border-warning hover:bg-warning/90">
                          <Trophy className="h-3 w-3 mr-1" />
                          {cefrFromBand(overallBand).split(" - ")[0]}
                        </Badge>
                      </div>
                    </div>
                    <div className="mt-4 space-y-1">
                      <p className="text-lg font-semibold text-white/90">
                        {cefrFromBand(overallBand).split(" - ")[1]}
                      </p>
                      <p className="text-sm text-white/70 max-w-xs">
                        {report.target_note}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex-1 w-full space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-white/10 rounded-xl p-4 backdrop-blur-sm">
                        <div className="flex items-center gap-2 text-white/80 mb-1">
                          <Clock className="h-4 w-4" />
                          <span className="text-xs uppercase tracking-wider">Time Taken</span>
                        </div>
                        <p className="text-2xl font-bold">{totalMinutes}<span className="text-sm text-white/70 ml-1">min</span></p>
                      </div>
                      <div className="bg-white/10 rounded-xl p-4 backdrop-blur-sm">
                        <div className="flex items-center gap-2 text-white/80 mb-1">
                          <Target className="h-4 w-4" />
                          <span className="text-xs uppercase tracking-wider">Avg Accuracy</span>
                        </div>
                        <p className="text-2xl font-bold">{Math.round(avgAccuracy)}<span className="text-sm text-white/70 ml-1">%</span></p>
                      </div>
                    </div>
                    
                    <div className="bg-white/10 rounded-xl p-4 backdrop-blur-sm">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-white/80">Progress to Target</span>
                        <span className="text-sm font-bold">Band {overallBand.toFixed(1)}</span>
                      </div>
                      <div className="h-2 bg-white/20 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-white transition-all duration-1000"
                          style={{ width: `${(overallBand / 9) * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Skill-wise Performance */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-primary" />
                  Skill-wise Performance
                </CardTitle>
                <CardDescription>
                  Detailed breakdown of your performance across all IELTS skills
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  {report.skill_scores?.map((skill: SectionScore) => {
                    const section = skill.section;
                    const band = skill.band || 0;
                    const accuracy = skill.accuracy || 0;
                    const label = SKILL_LABELS[section] || section;
                    
                    return (
                      <div key={section} className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${bandColor(band)}`}>
                              {SKILL_ICONS[section]}
                            </div>
                            <div>
                              <p className="font-semibold text-sm">{label}</p>
                              <p className="text-xs text-muted-foreground">
                                {section !== "writing" && section !== "speaking" 
                                  ? `${Math.round(accuracy)}% accuracy` 
                                  : "Rubric-based assessment"}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-lg font-bold">{band.toFixed(1)}</p>
                            <p className="text-xs text-muted-foreground">Band Score</p>
                          </div>
                        </div>
                        <div className="space-y-1">
                          <div className="h-3 w-full bg-secondary rounded-full overflow-hidden">
                            <div
                              className={`h-full ${bandProgressColor(band)} transition-all duration-1000 ease-out`}
                              style={{ width: `${(band / 9) * 100}%` }}
                            />
                          </div>
                          <div className="flex justify-between text-xs text-muted-foreground">
                            <span>3.0</span>
                            <span>9.0</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Insights & Recommendations */}
          <div className="space-y-6">
            
            {/* Strengths */}
            <Card className="border-success/20 bg-success/5">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2 text-success">
                  <CheckCircle2 className="h-5 w-5" />
                  Strengths
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {(report.strengths?.length ? report.strengths : ["Complete more questions to see your strengths."]).map((s, i) => (
                    <li key={i} className="text-sm flex items-start gap-2 text-muted-foreground">
                      <CheckCircle2 className="h-4 w-4 text-success mt-0.5 shrink-0" />
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            {/* Weaknesses */}
            <Card className="border-error/20 bg-error/5">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2 text-error">
                  <AlertCircle className="h-5 w-5" />
                  Areas for Growth
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {(report.weaknesses?.length ? report.weaknesses : ["No significant weaknesses detected. Great job!"]).map((w, i) => (
                    <li key={i} className="text-sm flex items-start gap-2 text-muted-foreground">
                      <AlertCircle className="h-4 w-4 text-error mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            {/* Recommended Focus Areas */}
            <Card className="border-accent/20 bg-accent/5">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2 text-accent">
                  <Target className="h-5 w-5" />
                  Recommended Focus
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {(report.recommended_focus_areas?.length ? report.recommended_focus_areas : ["Keep practicing all skills to maintain your level."]).map((item, i) => (
                    <li key={i} className="text-sm flex items-start gap-2 text-muted-foreground">
                      <div className="h-1.5 w-1.5 rounded-full bg-accent mt-1.5 shrink-0" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            {/* Band Estimation Engine (auto-computed from diagnostic skill scores) */}
            <Card className="border-primary/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2 text-primary">
                  <Trophy className="h-5 w-5" />
                  Band Estimation Engine
                </CardTitle>
                <CardDescription>
                  {estimatedBand ? (
                    <>
                      Estimated from your diagnostic skill bands — mean of 4 official skills (0.5 steps)
                    </>
                  ) : estimatingBand ? "Computing your estimated band..." : (
                    "Click below to compute your band estimation."
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {estimatingBand ? (
                  <div className="flex items-center gap-3 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Estimating...</span>
                  </div>
                ) : bandEstimation ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-3xl font-bold text-primary">
                          {bandEstimation.overall_band.toFixed(1)}
                        </span>
                        <span className="text-xs text-muted-foreground ml-1">Overall Band</span>
                      </div>
                      <Badge
                        variant={
                          bandEstimation.confidence_label === "very_high" ? "default" :
                          bandEstimation.confidence_label === "high" ? "secondary" :
                          "outline"
                        }
                        className="text-xs"
                      >
                        {bandEstimation.confidence_label.replace("_", " ")} (
                        {bandEstimation.confidence_score.toFixed(0)}/100)
                      </Badge>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-full rounded-full ${bandProgressColor(bandEstimation.overall_band)}`}
                        style={{ width: `${(bandEstimation.overall_band / 9) * 100}%` }}
                      />
                    </div>
                    {bandEstimation.weakest_skills.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-medium text-muted-foreground">
                          Weakest Skills
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {bandEstimation.weakest_skills.map((skill) => (
                            <Badge key={skill} variant="destructive" className="text-xs">
                              {SKILL_LABELS[skill] || skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <Button variant="outline" size="sm" onClick={() => bandEstimationService.estimate({
                    reading: overallBand,
                    listening: overallBand,
                    writing: overallBand,
                    speaking: overallBand,
                    vocabulary: overallBand,
                    grammar: overallBand,
                  }).then(setBandEstimation).catch(() => {})}>
                    Estimate Band
                  </Button>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Study Plan & Timeline Section */}
        <div className="grid gap-8 md:grid-cols-2">
          
          {/* Suggested Study Hours */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-primary" />
                Suggested Weekly Study Hours
              </CardTitle>
              <CardDescription>
                Recommended time commitment based on your current level
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-4xl font-bold text-primary">
                    {report.suggested_weekly_hours || 10}
                    <span className="text-lg text-muted-foreground ml-1">hrs/week</span>
                  </p>
                  <p className="text-sm text-muted-foreground mt-2">
                    Based on your current band level and skill gaps
                  </p>
                </div>
                <div className="h-16 w-16 rounded-full border-4 border-primary/20 flex items-center justify-center">
                  <Zap className="h-8 w-8 text-primary" />
                </div>
              </div>
              <div className="mt-6 space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Intensity Level</span>
                  <Badge variant={overallBand < 6.0 ? "destructive" : overallBand < 7.0 ? "default" : "success"}>
                    {overallBand < 6.0 ? "Moderate" : overallBand < 7.0 ? "Focused" : "Intensive"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Daily Average</span>
                  <span className="font-semibold">~{Math.round((report.suggested_weekly_hours || 10) / 7 * 10) / 10} hrs/day</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Exam Timeline */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-primary" />
                Suggested Exam Timeline
              </CardTitle>
              <CardDescription>
                Estimated preparation time to reach your target band
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-4xl font-bold text-primary">
                    {report.suggested_exam_timeline_weeks || 12}
                    <span className="text-lg text-muted-foreground ml-1">weeks</span>
                  </p>
                  <p className="text-sm text-muted-foreground mt-2">
                    Recommended preparation period
                  </p>
                </div>
                <div className="h-16 w-16 rounded-full border-4 border-primary/20 flex items-center justify-center">
                  <Trophy className="h-8 w-8 text-primary" />
                </div>
              </div>
              <div className="mt-6 space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Target Band</span>
                  <span className="font-semibold">Band {Math.min(9.0, overallBand + 1.0).toFixed(1)}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Start Date</span>
                  <span className="font-semibold">{new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Target Date</span>
                  <span className="font-semibold">
                    {new Date(Date.now() + (report.suggested_exam_timeline_weeks || 12) * 7 * 24 * 60 * 60 * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Roadmap Preview */}
        <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-accent/5 overflow-hidden">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Map className="h-5 w-5 text-primary" />
              Roadmap Preview
            </CardTitle>
            <CardDescription>
              Personalized path to your target band
            </CardDescription>
          </CardHeader>
          <CardContent>
            {(() => {
              const rp = (report.roadmap_preview || {}) as Record<string, any>;
              if (rp.has_plan) {
                return (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <div>
                        <p className="font-semibold">{String(rp.title || "Active Study Plan")}</p>
                        <p className="text-sm text-muted-foreground">
                          Target Band {Number(rp.target_band || Math.min(9, overallBand + 1)).toFixed(1)}·{" "}
                          {String(rp.total_weeks || 0)} weeks
                        </p>
                      </div>
                      <Badge variant="success">{String(rp.status || "active")}</Badge>
                    </div>
                    <Link href="/roadmap" className="inline-flex w-full">
                      <Button className="w-full bg-accent hover:bg-accent/90 text-accent-foreground">
                        View My Study Plan <ChevronRight className="ml-2 h-4 w-4" />
                      </Button>
                    </Link>
                  </div>
                );
              }
              const focusSkills = (Array.isArray(rp.focus_skills) ? rp.focus_skills : []) as any[];
              return (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    {rp.message
                      ? String(rp.message)
                      : "Generate a personalized study plan based on your diagnostic results."}
                  </p>
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="space-y-1">
                      <p className="text-sm font-semibold">
                        Suggested Target: Band{" "}
                        {Number(rp.suggested_target || Math.min(9, overallBand + 1)).toFixed(1)}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Est. {Number(rp.estimated_weeks || 12)} weeks of preparation
                      </p>
                    </div>
                  </div>
                  {focusSkills.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {focusSkills.slice(0, 3).map((s: any, i: number) => (
                        <Badge key={i} variant="secondary">{String(s)}</Badge>
                      ))}
                    </div>
                  )}
                  <Link href="/roadmap" className="inline-flex w-full">
                    <Button className="w-full bg-accent hover:bg-accent/90 text-accent-foreground">
                      Generate My Study Plan <Map className="ml-2 h-5 w-5" />
                    </Button>
                  </Link>
                </div>
              );
            })()}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
