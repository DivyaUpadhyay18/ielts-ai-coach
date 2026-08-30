"use client";

import React from "react";
import Link from "next/link";
import { 
  ClipboardCheck, 
  Clock, 
  Target, 
  Zap, 
  ArrowRight, 
ShieldCheck,
  PenTool,
  Mic,
BrainCircuit,
  BookOpen,
  Headphones,
  SpellCheck
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function DiagnosticHome() {
  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        {/* Header Section */}
        <div className="text-center space-y-4">
          <Badge variant="accent" className="px-4 py-1">
            Step 1: Baseline Assessment
          </Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">
            Find your starting point
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Complete this 20-minute diagnostic test. Our AI will analyze your performance 
            to create a custom study plan tailored to your target band score.
          </p>
        </div>

        {/* Main Content Grid */}
        <div className="grid gap-8 md:grid-cols-3">
          
          {/* Diagnostic Details */}
          <div className="md:col-span-2 space-y-6">
            <Card className="border-primary/20 bg-primary/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ClipboardCheck className="h-5 w-5 text-primary" />
                  What&apos;s included in this test?
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <PenTool className="h-5 w-5 text-blue-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Short Essay</p>
                    <p className="text-xs text-muted-foreground">150 words to check grammar and cohesion.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Mic className="h-5 w-5 text-teal-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Speaking Clip</p>
                    <p className="text-xs text-muted-foreground">2-minute talk to check fluency and pronunciation.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <BrainCircuit className="h-5 w-5 text-purple-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Vocabulary Check</p>
                    <p className="text-xs text-muted-foreground">Quick quiz on academic word usage.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Target className="h-5 w-5 text-orange-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Band Estimate</p>
                    <p className="text-xs text-muted-foreground">Get your current CEFR and IELTS equivalent.</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex items-center gap-3 p-4 rounded-xl border border-border">
                <Clock className="h-10 w-10 text-muted-foreground/40" />
                <div>
                  <p className="text-sm font-semibold">Total Duration</p>
                  <p className="text-2xl font-bold">20 Mins</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-4 rounded-xl border border-border">
                <Zap className="h-10 w-10 text-accent/40" />
                <div>
                  <p className="text-sm font-semibold">Result Speed</p>
                  <p className="text-2xl font-bold">Instant</p>
                </div>
              </div>
            </div>
          </div>

          {/* Action Card */}
          <Card className="h-full border-2 border-primary shadow-xl">
            <CardHeader className="text-center">
              <CardTitle>Ready to start?</CardTitle>
              <CardDescription>
                Ensure you are in a quiet room and your microphone is working.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <ul className="space-y-3 text-sm">
                <li className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-success" /> No credit card required
                </li>
                <li className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-success" /> 100% AI-powered analysis
                </li>
                <li className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-success" /> Save progress and exit anytime
                </li>
              </ul>
              
<Link href="/diagnostic/start">
                <Button className="w-full h-12 text-lg shadow-lg" size="lg">
                  Begin Diagnostic <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>

              <p className="text-[10px] text-center text-muted-foreground uppercase tracking-widest font-bold">
                Recommended for all new students
              </p>
            </CardContent>
          </Card>

</div>

{/* Reading Diagnostic Module */}
        <Card className="border-blue-500/30 bg-blue-500/5">
          <CardContent className="pt-6 flex flex-col md:flex-row md:items-center gap-4 md:justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-blue-500/10 text-blue-500">
                <BookOpen className="h-8 w-8" />
              </div>
              <div>
                <h3 className="text-lg font-bold">Reading Diagnostic</h3>
                <p className="text-sm text-muted-foreground">
                  Passage-based assessment covering all six IELTS Reading question types with
                  instant accuracy, timing, weak-type analysis, and difficulty rating.
                </p>
              </div>
            </div>
            <Link href="/diagnostic/reading">
              <Button variant="outline" className="shrink-0">
                Start Reading Diagnostic <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

{/* Listening Diagnostic Module */}
        <Card className="border-teal-500/30 bg-teal-500/5">
          <CardContent className="pt-6 flex flex-col md:flex-row md:items-center gap-4 md:justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-teal-500/10 text-teal-500">
                <Headphones className="h-8 w-8" />
              </div>
              <div>
                <h3 className="text-lg font-bold">Listening Diagnostic</h3>
                <p className="text-sm text-muted-foreground">
                  Audio-based assessment covering all five IELTS Listening question types with
                  an audio player, instant accuracy, timing, and weak-section analysis.
                </p>
              </div>
            </div>
            <Link href="/diagnostic/listening">
              <Button variant="outline" className="shrink-0">
                Start Listening Diagnostic <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

{/* Writing Diagnostic Module */}
        <Card className="border-blue-500/30 bg-blue-500/5">
          <CardContent className="pt-6 flex flex-col md:flex-row md:items-center gap-4 md:justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-blue-500/10 text-blue-500">
                <PenTool className="h-8 w-8" />
              </div>
              <div>
                <h3 className="text-lg font-bold">Writing Diagnostic</h3>
                <p className="text-sm text-muted-foreground">
                  Task 1 &amp; Task 2 essay practice with live word count, a timer, auto-save,
                  manual IELTS scoring, and grammar/vocabulary placeholders.
                </p>
              </div>
            </div>
            <Link href="/diagnostic/writing">
              <Button variant="outline" className="shrink-0">
                Start Writing Diagnostic <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Speaking Diagnostic Module */}
        <Card className="border-teal-500/30 bg-teal-500/5">
          <CardContent className="pt-6 flex flex-col md:flex-row md:items-center gap-4 md:justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-teal-500/10 text-teal-500">
                <Mic className="h-8 w-8" />
              </div>
              <div>
                <h3 className="text-lg font-bold">Speaking Diagnostic</h3>
                <p className="text-sm text-muted-foreground">
                  All three IELTS Speaking parts with microphone recording, playback, a timer,
                  question rotation, stored recordings, and 4-criteria manual scoring.
                </p>
              </div>
            </div>
<Link href="/diagnostic/speaking">
              <Button variant="outline" className="shrink-0">
                Start Speaking Diagnostic <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Vocabulary & Grammar Diagnostic Module */}
        <Card className="border-purple-500/30 bg-purple-500/5">
          <CardContent className="pt-6 flex flex-col md:flex-row md:items-center gap-4 md:justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-purple-500/10 text-purple-500">
                <SpellCheck className="h-8 w-8" />
              </div>
              <div>
                <h3 className="text-lg font-bold">Vocabulary &amp; Grammar Diagnostic</h3>
                <p className="text-sm text-muted-foreground">
                  Assess your vocabulary and grammar across eight topics (fill-in-the-blanks,
                  synonyms, antonyms, sentence correction, tenses, articles, prepositions) with
                  instant accuracy, grammar vs vocabulary breakdown, and weak-topic analysis.
                </p>
              </div>
            </div>
            <Link href="/diagnostic/vocab-grammar">
              <Button variant="outline" className="shrink-0">
                Start Vocabulary &amp; Grammar Diagnostic <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
