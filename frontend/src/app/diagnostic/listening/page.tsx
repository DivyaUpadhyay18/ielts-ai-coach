"use client";

import React from "react";
import Link from "next/link";
import {
  Headphones,
  Clock,
  Target,
  ArrowRight,
  CheckCircle2,
  FileText,
  Layers,
  AudioLines,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const QUESTION_TYPES = [
  { type: "Multiple Choice", desc: "Select the correct answer from options.", color: "text-teal-500" },
  { type: "Map", desc: "Identify locations and directions from the audio.", color: "text-blue-500" },
  { type: "Form Completion", desc: "Fill in gaps in a form or table.", color: "text-orange-500" },
  { type: "Sentence Completion", desc: "Complete sentences using words you hear.", color: "text-rose-500" },
  { type: "Matching", desc: "Match items based on the audio content.", color: "text-purple-500" },
];

export default function ListeningDiagnosticHome() {
  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        {/* Header */}
        <div className="text-center space-y-4">
          <Badge variant="accent" className="px-4 py-1">
            Dedicated Listening Diagnostic
          </Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">Master your IELTS Listening</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Listen to authentic audio sections and answer questions covering all five official
            IELTS Listening question types. Get instant metrics on accuracy, time,
            your weak question types, and difficulty level.
          </p>
        </div>

        {/* Question types */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {QUESTION_TYPES.map((qt) => (
            <div key={qt.type} className="p-4 rounded-xl border border-border flex items-start gap-3">
              <Layers className={`h-5 w-5 ${qt.color} mt-0.5`} />
              <div>
                <p className="text-sm font-bold">{qt.type}</p>
                <p className="text-xs text-muted-foreground">{qt.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid gap-8 md:grid-cols-3">
          {/* Details */}
          <div className="md:col-span-2 space-y-6">
            <Card className="border-primary/20 bg-primary/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Headphones className="h-5 w-5 text-primary" /> What you&apos;ll get
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <AudioLines className="h-5 w-5 text-teal-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Audio Player</p>
                    <p className="text-xs text-muted-foreground">Play, pause & replay tracks with transcripts.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Target className="h-5 w-5 text-blue-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Accuracy</p>
                    <p className="text-xs text-muted-foreground">Overall & per-question-type scores.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Clock className="h-5 w-5 text-teal-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Time Tracking</p>
                    <p className="text-xs text-muted-foreground">Total time and average time per type.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <FileText className="h-5 w-5 text-purple-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Listening Band</p>
                    <p className="text-xs text-muted-foreground">Estimated IELTS band + CEFR level.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Action */}
          <Card className="h-full border-2 border-primary shadow-xl">
            <CardHeader className="text-center">
              <CardTitle>Ready to listen?</CardTitle>
              <CardDescription>
                Answer a series of audio-based questions. Progress is saved as you go.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <ul className="space-y-3 text-sm">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> 3 authentic audio tracks
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> 5 question types
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> Instant grading & report
                </li>
              </ul>
<Link href="/diagnostic/listening/test">
                <Button className="w-full h-12 text-lg shadow-lg" size="lg">
                  Start Listening Diagnostic <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
              <Link href="/diagnostic/listening/results" className="block">
                <Button variant="outline" className="w-full">
                  View Past Results
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
