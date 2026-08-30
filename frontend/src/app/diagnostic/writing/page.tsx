"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  FileText,
  PenTool,
  Save,
  Sparkles,
  Target,
  Type,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const FEATURES = [
  { icon: Type, label: "Task 1 & Task 2", desc: "Report/letter and essay prompts.", color: "text-blue-500" },
  { icon: Clock, label: "Countdown Timer", desc: "Official 20 / 40 minute limits.", color: "text-orange-500" },
  { icon: Save, label: "Auto-save", desc: "Your essay is saved as you type.", color: "text-teal-500" },
  { icon: Target, label: "Word Count", desc: "Live tracking against the target.", color: "text-purple-500" },
  { icon: PenTool, label: "Manual Scoring", desc: "Score across the 4 IELTS criteria.", color: "text-rose-500" },
  { icon: Sparkles, label: "AI Ready", desc: "Architecture prepared for AI evaluation.", color: "text-accent" },
];

export default function WritingDiagnosticHome() {
  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        <div className="text-center space-y-4">
          <Badge variant="accent" className="px-4 py-1">
            Dedicated Writing Diagnostic
          </Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">Master your IELTS Writing</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Write authentic Task 1 and Task 2 responses with a live word counter and
            countdown timer. Your essay is auto-saved as you type, then scored across
            the four official IELTS criteria.
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
                  <FileText className="h-5 w-5 text-primary" /> What you&apos;ll get
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Type className="h-5 w-5 text-blue-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Both Task Types</p>
                    <p className="text-xs text-muted-foreground">Task 1 reports & Task 2 essays.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Save className="h-5 w-5 text-teal-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Auto-save</p>
                    <p className="text-xs text-muted-foreground">Never lose your work mid-essay.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <PenTool className="h-5 w-5 text-rose-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Manual Scoring</p>
                    <p className="text-xs text-muted-foreground">4-criteria IELTS rubric + overall band.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Sparkles className="h-5 w-5 text-accent mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">AI-Ready</p>
                    <p className="text-xs text-muted-foreground">Grammar, vocabulary & AI scaffold ready.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="h-full border-2 border-primary shadow-xl">
            <CardHeader className="text-center">
              <CardTitle>Ready to write?</CardTitle>
              <CardDescription>
                Select a task and prompt. Progress is auto-saved as you go.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <ul className="space-y-3 text-sm">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> Task 1 & Task 2 prompts
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> Live word count & timer
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> Manual 4-criteria scoring
                </li>
              </ul>
              <Link href="/diagnostic/writing/test">
                <Button className="w-full h-12 text-lg shadow-lg" size="lg">
                  Start Writing Diagnostic <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
              <Link href="/diagnostic/writing/results" className="block">
                <Button variant="outline" className="w-full">
                  View Past Essays
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
