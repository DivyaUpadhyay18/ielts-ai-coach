"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Headphones,
  Mic,
  RefreshCcw,
  Save,
  Sparkles,
  Target,
  Volume2,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const FEATURES = [
  { icon: Mic, label: "Part 1 · 2 · 3", desc: "All three official IELTS Speaking parts.", color: "text-teal-500" },
  { icon: Clock, label: "Countdown Timer", desc: "Prep & speaking time limits per part.", color: "text-orange-500" },
  { icon: Volume2, label: "Recording & Playback", desc: "Record your response, then play it back.", color: "text-blue-500" },
  { icon: RefreshCcw, label: "Question Rotation", desc: "Shuffle & rotate through the question bank.", color: "text-purple-500" },
  { icon: Save, label: "Store Recordings", desc: "Every response is saved for review.", color: "text-teal-500" },
  { icon: Sparkles, label: "AI Ready", desc: "Architecture prepared for AI evaluation.", color: "text-accent" },
];

export default function SpeakingDiagnosticHome() {
  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        <div className="text-center space-y-4">
          <Badge variant="accent" className="px-4 py-1">
            Dedicated Speaking Diagnostic
          </Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">Master your IELTS Speaking</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Practice all three parts of the IELTS Speaking test with authentic prompts, a
            countdown timer, and microphone recording. Your responses are stored and scored
            across the four official IELTS criteria.
          </p>
        </div>

        {/* Features */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.label} className="p-4 rounded-xl border border-border flex items-start gap-3">
              <f.icon className={`h-5 w-5 ${f.color} mt-0.5`} />
              <div>
                <p className="text-sm font-bold">{f.label}</p>
                <p className="text-xs text-muted-foreground">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid gap-8 md:grid-cols-3">
          <div className="md:col-span-2 space-y-6">
            <Card className="border-primary/20 bg-primary/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Headphones className="h-5 w-5 text-primary" /> What you&apos;ll get
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Mic className="h-5 w-5 text-teal-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">All Three Parts</p>
                    <p className="text-xs text-muted-foreground">Part 1 interview, Part 2 long turn, Part 3 discussion.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Volume2 className="h-5 w-5 text-blue-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Recording & Playback</p>
                    <p className="text-xs text-muted-foreground">Capture your voice and review it instantly.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Target className="h-5 w-5 text-orange-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Manual Scoring</p>
                    <p className="text-xs text-muted-foreground">4-criteria IELTS rubric + overall band.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Sparkles className="h-5 w-5 text-accent mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">AI-Ready</p>
                    <p className="text-xs text-muted-foreground">Transcript & AI evaluation scaffold ready.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="h-full border-2 border-primary shadow-xl">
            <CardHeader className="text-center">
              <CardTitle>Ready to speak?</CardTitle>
              <CardDescription>
                Ensure your microphone is working, then pick a part and a prompt.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <ul className="space-y-3 text-sm">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> Part 1, 2 & 3 prompts
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> Recording + playback
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> 4-criteria manual scoring
                </li>
              </ul>
              <Link href="/diagnostic/speaking/test">
                <Button className="w-full h-12 text-lg shadow-lg" size="lg">
                  Start Speaking Diagnostic <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
              <Link href="/diagnostic/speaking/results" className="block">
                <Button variant="outline" className="w-full">
                  View Past Recordings
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
