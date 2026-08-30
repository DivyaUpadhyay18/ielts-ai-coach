"use client";

import React, { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Award, Clock, Headphones, Mic, Sparkles } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { speakingDiagnosticService } from "@/services/speaking-diagnostic";
import type { SpeakingCriterion, SpeakingRecording } from "@/types/speaking-diagnostic";
import { SPEAKING_CRITERIA_LABELS, SPEAKING_PART_LABELS } from "@/types/speaking-diagnostic";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

const CRITERIA_KEYS: SpeakingCriterion[] = [
  "fluency_coherence",
  "lexical_resource",
  "grammatical_range",
  "pronunciation",
];

export default function SpeakingReportPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center text-muted-foreground">Loading...</div>}>
      <SpeakingReportContent />
    </Suspense>
  );
}

function SpeakingReportContent() {
  const searchParams = useSearchParams();
  const recordingId = searchParams.get("recording_id");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState<SpeakingRecording | null>(null);

  // Audio playback
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => {});
    } else {
      audio.pause();
    }
  }, []);

  const load = useCallback(async () => {
    if (!recordingId) {
      setError("Missing recording_id parameter.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rep = await speakingDiagnosticService.getReport(recordingId);
      setRecording(rep.recording);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.message || e?.message || "Failed to load speaking report.");
    } finally {
      setLoading(false);
    }
  }, [recordingId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6 py-4">
        <div className="flex items-center justify-between">
          <Link href="/diagnostic/speaking/results" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Results
          </Link>
          <Badge variant="accent" className="px-4 py-1">Stored Recording</Badge>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <Spinner size="lg" />
            <p className="text-muted-foreground">Loading your speaking report...</p>
          </div>
        ) : error ? (
          <Card>
            <CardContent className="py-16 text-center space-y-4">
              <Headphones className="h-12 w-12 mx-auto text-muted-foreground/40" />
              <p className="text-sm text-error">{error}</p>
              <Link href="/diagnostic/speaking">
                <Button variant="outline">Back to Speaking Overview</Button>
              </Link>
            </CardContent>
          </Card>
        ) : recording ? (
          <div className="space-y-6">
            <div className="text-center space-y-3">
              <Badge variant="success" className="px-4 py-1">Speaking Assessment</Badge>
              <h1 className="text-3xl font-extrabold tracking-tight">Your Speaking Report</h1>
              <p className="text-muted-foreground">
                {SPEAKING_PART_LABELS[recording.part]} — {formatTime(recording.duration_seconds)} spent
              </p>
            </div>

            <Card className="bg-gradient-to-br from-teal-600 to-emerald-700 text-white border-none shadow-xl">
              <CardContent className="py-10 flex flex-col items-center text-center">
                <div className="flex items-center gap-8">
                  <div className="flex flex-col items-center">
                    <span className="text-6xl font-black">
                      {recording.overall_band != null ? Number(recording.overall_band).toFixed(1) : "—"}
                    </span>
                    <span className="mt-2 text-sm uppercase tracking-widest text-white/70">Overall Band</span>
                  </div>
                  <div className="h-16 w-px bg-white/20" />
                  <div className="flex flex-col items-center">
                    <span className="text-6xl font-black">{formatTime(recording.duration_seconds)}</span>
                    <span className="mt-2 text-sm uppercase tracking-widest text-white/70">Duration</span>
                  </div>
                </div>
                <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
                  <Badge className="bg-white/20 text-white border-white/30">{SPEAKING_PART_LABELS[recording.part]}</Badge>
                  <Badge className="bg-white/20 text-white border-white/30">
                    <Clock className="mr-1 h-3 w-3" /> {formatTime(recording.duration_seconds || 0)}
                  </Badge>
                  <Badge className="bg-white/20 text-white border-white/30">
                    {recording.overall_band != null ? "Manual Score" : "Unscored"}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            {/* Audio playback */}
            {recording.audio_url && (
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <h3 className="font-bold text-lg flex items-center gap-2">
                    <Mic className="h-5 w-5 text-teal-500" /> Your Recording
                  </h3>
                  <audio
                    ref={audioRef}
                    src={recording.audio_url}
                    onPlay={() => setPlaying(true)}
                    onPause={() => setPlaying(false)}
                    onEnded={() => setPlaying(false)}
                    preload="metadata"
                  />
                  <div className="flex items-center gap-3">
                    <Button variant="outline" size="icon" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>
                      {playing ? <Mic className="h-5 w-5" /> : <Headphones className="h-5 w-5" />}
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      {playing ? "Playing..." : "Play your recorded response"}
                    </span>
                  </div>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardContent className="pt-6 space-y-6">
                <h3 className="font-bold text-lg">IELTS Speaking Criteria</h3>
                {recording.overall_band == null && (
                  <p className="text-sm text-muted-foreground">
                    This recording has not been manually scored yet.
                  </p>
                )}
                {CRITERIA_KEYS.map((key) => {
                  const val = recording[key] != null ? Number(recording[key]) : null;
                  return (
                    <div key={key} className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{SPEAKING_CRITERIA_LABELS[key]}</span>
                        <span className="font-bold">{val != null ? val.toFixed(1) : "—"}</span>
                      </div>
                      <Progress value={val != null ? (val / 9) * 100 : 0} className="h-3" />
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <h3 className="font-bold text-lg mb-3">{recording.title || "Your Response"}</h3>
                <p className="text-sm font-medium mb-2 text-muted-foreground">Question</p>
                <p className="text-sm leading-relaxed whitespace-pre-line mb-4">
                  {recording.prompt_text || "No prompt text available."}
                </p>
                <p className="text-sm font-medium mb-2 text-muted-foreground">Transcript</p>
                <p className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground">
                  {recording.transcript || "No transcript provided."}
                </p>
              </CardContent>
            </Card>

            <Card className="border-accent/30 bg-accent/5">
              <CardContent className="pt-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-lg flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-accent" /> AI Evaluation
                  </h3>
                  <Badge variant="outline">Coming soon</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {recording.ai_evaluation && (recording.ai_evaluation as any).feedback
                    ? (recording.ai_evaluation as any).feedback
                    : "AI evaluation placeholder. Connect an AI provider to enable automatic band assessment from your transcript."}
                </p>
              </CardContent>
            </Card>
          </div>
        ) : null}
      </div>
    </DashboardLayout>
  );
}
