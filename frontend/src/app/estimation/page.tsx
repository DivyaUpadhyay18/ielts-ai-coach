"use client";

import { useState, useCallback } from "react";
import {
  Trophy,
  TrendingUp,
  AlertCircle,
  BarChart3,
  BookOpen,
  Headphones,
  PenTool,
  Mic,
  Library,
  BookMarked,
  CheckCircle2,
  History,
  RefreshCw,
  Award,
  FileText,
  Copy,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { bandEstimationService } from "@/services/api";
import type { BandEstimationResponse, BandEstimationHistoryResponse, BandEstimationInput } from "@/types";

const SKILL_ICONS: Record<string, React.ElementType> = {
  reading: BookOpen,
  listening: Headphones,
  writing: PenTool,
  speaking: Mic,
  vocabulary: Library,
  grammar: BookMarked,
};

const SKILL_LABELS: Record<string, string> = {
  reading: "Reading",
  listening: "Listening",
  writing: "Writing",
  speaking: "Speaking",
  vocabulary: "Vocabulary",
  grammar: "Grammar",
};

const CONFIDENCE_COLORS: Record<string, string> = {
  very_high: "bg-green-500",
  high: "bg-blue-500",
  medium: "bg-yellow-500",
  low: "bg-red-500",
};

const CONFIDENCE_BG: Record<string, string> = {
  very_high: "bg-green-50",
  high: "bg-blue-50",
  medium: "bg-yellow-50",
  low: "bg-red-50",
};

export default function BandEstimationPage() {
  const [scores, setScores] = useState<BandEstimationInput>({
    reading: 6.0,
    listening: 6.0,
    writing: 6.0,
    speaking: 6.0,
    vocabulary: 6.0,
    grammar: 6.0,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BandEstimationResponse | null>(null);
  const [history, setHistory] = useState<BandEstimationHistoryResponse | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const handleScoreChange = (skill: keyof BandEstimationInput, value: number) => {
    setScores((prev) => ({ ...prev, [skill]: value }));
  };

  const handleEstimate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await bandEstimationService.estimate(scores);
      setResult(data);
    } catch (err: any) {
      setError(err?.message || "Failed to estimate band");
    } finally {
      setLoading(false);
    }
  }, [scores]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleEstimate();
    }
  };

  const handleHistory = useCallback(async () => {
    setShowHistory(true);
    setError(null);
    try {
      const data = await bandEstimationService.getHistory();
      setHistory(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load history");
    }
  }, []);

  const handleCopyResult = () => {
    if (!result) return;
    const text = `Overall Band: ${result.overall_band}\nConfidence: ${result.confidence_score}/100 (${result.confidence_label})\n\nSkill Bands:\n${Object.entries(result.skill_bands).map(([skill, band]) => `  ${SKILL_LABELS[skill] || skill}: ${band}`).join('\n')}`;
    navigator.clipboard.writeText(text).then(() => {
      setError("Copied to clipboard!");
      setTimeout(() => setError(null), 3000);
    });
  };

  const overallBand = result?.overall_band ?? 0;

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Trophy className="h-8 w-8 text-yellow-400" />
              Band Estimation Engine
            </h1>
            <p className="text-muted-foreground">
              Enter your skill-wise scores to estimate your overall IELTS band. Results are stored for tracking progress over time.
            </p>
          </div>
          <div className="flex gap-2">
            {result && (
              <Button variant="outline" size="sm" onClick={handleCopyResult}>
                <Copy className="h-4 w-4 mr-2" />
                Copy Result
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setShowHistory(!showHistory)}>
              <History className="h-4 w-4 mr-2" />
              {showHistory ? "Hide History" : "History"}
            </Button>
          </div>
        </div>

        {error && (
          <div
            className={`p-4 rounded-lg flex items-center gap-3 text-sm ${
              error.includes("Copied")
                ? "bg-green-50 text-green-800 border border-green-200"
                : "bg-red-50 text-red-800 border border-red-200"
            }`}
          >
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Input Panel */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Skill Scores (0-9)
              </CardTitle>
              <CardDescription>
                Enter your estimated band scores for each skill. Use 0.5 increments (IELTS convention).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {Object.entries(SKILL_LABELS).map(([skill, label]) => {
                const Icon = SKILL_ICONS[skill] || BookOpen;
                return (
                  <div key={skill} className="space-y-1">
                    <label className="flex items-center gap-2 text-sm font-medium">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      {label}
                    </label>
                    <Input
                      type="number"
                      step="0.5"
                      min="0"
                      max="9"
                      value={scores[skill as keyof BandEstimationInput]}
                      onChange={(e) => handleScoreChange(skill as keyof BandEstimationInput, parseFloat(e.target.value) || 0)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleEstimate();
                      }}
                      className="text-center text-lg font-medium"
                    />
                  </div>
                );
              })}
              <Button
                className="w-full"
                onClick={handleEstimate}
                disabled={loading}
                size="lg"
              >
                {loading ? (
                  <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Trophy className="h-4 w-4 mr-2" />
                )}
                {loading ? "Estimating..." : "Estimate My Band"}
              </Button>
            </CardContent>
          </Card>

          {/* Overall Result */}
          <Card>
            <CardHeader>
              <CardTitle>Estimated Overall Band</CardTitle>
              <CardDescription>
                Mean of Reading, Listening, Writing, and Speaking
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col items-center text-center">
              {result ? (
                <>
                  <div className="relative mb-4">
                    <div className="h-32 w-32 rounded-full border-4 border-primary/10 flex items-center justify-center">
                      <span className="text-5xl font-black text-primary">
                        {result.overall_band.toFixed(1)}
                      </span>
                    </div>
                    <Award className="absolute -top-2 -right-2 h-10 w-10 text-yellow-400" />
                  </div>

                  <div className="space-y-2">
                    <Badge
                      variant={result.confidence_label === "very_high" ? "default" : "secondary"}
                      className={`text-sm ${CONFIDENCE_BG[result.confidence_label] || "bg-gray-50"}`}
                    >
                      Confidence: {result.confidence_score}/100
                    </Badge>
                    <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${CONFIDENCE_COLORS[result.confidence_label] || "bg-gray-400"}`}
                        style={{ width: `${result.confidence_score}%` }}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Confidence level: {result.confidence_label.replace("_", " ")}
                    </p>
                  </div>
                </>
              ) : (
                <div className="py-12 text-center text-muted-foreground">
                  <Trophy className="h-16 w-16 mx-auto mb-3 opacity-30" />
                  <p>Enter your scores and click &quot;Estimate My Band&quot;</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Skill Bands & Quick Stats */}
          {result ? (
            <Card>
              <CardHeader>
                <CardTitle>Skill-wise Bands</CardTitle>
                <CardDescription>Per-skill breakdown of your estimated scores</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Object.entries(result.skill_bands).map(([skill, band]) => {
                    const Icon = SKILL_ICONS[skill] || BookOpen;
                    const label = SKILL_LABELS[skill] || skill;
                    const isWeakest = result.weakest_skills.includes(skill);
                    const isStrongest = result.strongest_skills.includes(skill);

                    return (
                      <div key={skill} className="space-y-1">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Icon className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium text-sm">{label}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-lg">{band.toFixed(1)}</span>
                            {isWeakest && (
                              <Badge variant="outline" className="text-xs text-red-600">
                                Weakest
                              </Badge>
                            )}
                            {isStrongest && (
                              <Badge variant="outline" className="text-xs text-green-600">
                                Strongest
                              </Badge>
                            )}
                          </div>
                        </div>
                        <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500"
                            style={{ width: `${(band / 9) * 100}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Strengths & Weaknesses</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8 text-muted-foreground">
                  <AlertCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>Submit your scores to see analysis</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Detailed Results: Explanations, Weakest/Strongest, Formulas */}
        {result ? (
          <div className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Weakest Skills */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-red-600">
                    <TrendingUp className="h-5 w-5" />
                    Weakest Skills
                  </CardTitle>
                  <CardDescription>
                    Focus your study plan on these areas
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {result.weakest_skills.map((skill, idx) => (
                      <div key={skill} className="flex items-center gap-3 p-2 bg-red-50 rounded-lg">
                        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-red-100 flex items-center justify-center text-xs font-bold text-red-600">
                          {idx + 1}
                        </div>
                        <div className="flex-1">
                          <span className="font-medium">
                            {SKILL_LABELS[skill] || skill}
                          </span>
                          <div className="text-sm text-muted-foreground">
                            Band {result.skill_bands[skill]?.toFixed(1)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Strongest Skills */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-green-600">
                    <TrendingUp className="h-5 w-5" />
                    Strongest Skills
                  </CardTitle>
                  <CardDescription>
                    These are your highest performing areas
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {result.strongest_skills.map((skill, idx) => (
                      <div key={skill} className="flex items-center gap-3 p-2 bg-green-50 rounded-lg">
                        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-green-100 flex items-center justify-center text-xs font-bold text-green-600">
                          {idx + 1}
                        </div>
                        <div className="flex-1">
                          <span className="font-medium">
                            {SKILL_LABELS[skill] || skill}
                          </span>
                          <div className="text-sm text-muted-foreground">
                            Band {result.skill_bands[skill]?.toFixed(1)}
                          </div>
                        </div>
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Explanations */}
            <Card>
              <CardHeader>
                <CardTitle>Explanations</CardTitle>
                <CardDescription>
                  Why each score was assigned (computed deterministically — no AI)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Object.entries(result.explanations).map(([skill, explanation]) => (
                    <div key={skill} className="border-l-3 border-primary pl-4 py-2">
                      <h4 className="font-medium text-sm mb-1">
                        {SKILL_LABELS[skill] || skill}
                      </h4>
                      <p className="text-sm text-muted-foreground">{explanation}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Formulas */}
            <Card>
              <CardHeader>
                <CardTitle>Formula Reference</CardTitle>
                <CardDescription>
                  All formulas are deterministic and documented for transparency
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(result.formulas).map(([key, formula]) => (
                    <div key={key}>
                      <code className="text-xs font-medium text-primary bg-primary/10 px-2 py-1 rounded">
                        {key}
                      </code>
                      <p className="text-sm text-muted-foreground mt-1 ml-2">{formula}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        ) : null}

        {/* History Modal */}
        {showHistory && (
          <Card>
            <CardHeader>
              <CardTitle>Estimation History</CardTitle>
              <CardDescription>
                Your previous band estimation results
              </CardDescription>
            </CardHeader>
            <CardContent>
              {history ? (
                history.items.length > 0 ? (
                  <div className="space-y-4">
                    {history.items.map((item) => (
                      <div key={item.id} className="border rounded-lg p-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge variant="secondary">{item.run_date}</Badge>
                            <span className="text-xs text-muted-foreground">
                              {new Date(item.created_at || "").toLocaleTimeString()}
                            </span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="font-bold">Band {item.overall_band.toFixed(1)}</span>
                            <Badge variant="outline" className="text-xs">
                              {item.confidence_label} ({item.confidence_score})
                            </Badge>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                          {Object.entries(item.skill_bands).map(([skill, band]) => (
                            <div key={skill}>
                              <span className="text-muted-foreground">
                                {SKILL_LABELS[skill] || skill}:
                              </span>{" "}
                              <span className="font-medium">{band.toFixed(1)}</span>
                            </div>
                          ))}
                        </div>
                        <div className="flex gap-2">
                          {item.weakest_skills.map((s) => (
                            <Badge key={s} variant="destructive" className="text-xs">
                              Weak: {SKILL_LABELS[s] || s}
                            </Badge>
                          ))}
                          {item.strongest_skills.map((s) => (
                            <Badge key={s} variant="default" className="text-xs">
                              Strong: {SKILL_LABELS[s] || s}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                    {history.items.length < (history.total || 0) && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full"
                        onClick={() =>
                          bandEstimationService.getHistory({ limit: 50, offset: history.items.length })
                            .then(setHistory)
                            .catch((err: any) => setError(err?.message || "Failed to load more history"))
                        }
                      >
                        Load more...
                      </Button>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <FileText className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p>No estimation history yet</p>
                  </div>
                )
              ) : (
                <div className="space-y-3">
                  {[...Array(3)].map((_, i) => (
                    <Skeleton key={i} className="h-24 rounded-lg" />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}