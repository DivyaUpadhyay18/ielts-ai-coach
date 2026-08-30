"use client";

import React from "react";
import Link from "next/link";
import {
  SpellCheck,
  Target,
  ArrowRight,
  CheckCircle2,
  TrendingUp,
  AlertTriangle,
  BookOpen,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const QUESTION_TYPES = [
  { type: "Fill in the Blanks", desc: "Complete sentences with the right word.", color: "text-blue-500", section: "Vocabulary" },
  { type: "Synonyms", desc: "Choose the closest meaning.", color: "text-teal-500", section: "Vocabulary" },
  { type: "Antonyms", desc: "Choose the opposite meaning.", color: "text-rose-500", section: "Vocabulary" },
  { type: "Sentence Correction", desc: "Pick the grammatically correct sentence.", color: "text-purple-500", section: "Grammar" },
  { type: "Grammar Correction", desc: "Fix a grammatically incorrect sentence.", color: "text-orange-500", section: "Grammar" },
  { type: "Tenses", desc: "Choose the correct verb tense.", color: "text-emerald-500", section: "Grammar" },
  { type: "Articles", desc: "Choose the correct article (a/an/the).", color: "text-amber-500", section: "Grammar" },
  { type: "Prepositions", desc: "Choose the correct preposition.", color: "text-cyan-500", section: "Grammar" },
];

export default function VocabGrammarDiagnosticHome() {
  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        {/* Header */}
        <div className="text-center space-y-4">
          <Badge variant="accent" className="px-4 py-1">
            Vocabulary &amp; Grammar Diagnostic
          </Badge>
          <h1 className="text-4xl font-extrabold tracking-tight">Sharpen your words &amp; grammar</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Answer questions across eight vocabulary and grammar topics. Get instant accuracy,
            grammar vs vocabulary breakdowns, weak-topic analysis, and an estimated band.
          </p>
        </div>

        {/* Question types */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {QUESTION_TYPES.map((qt) => (
            <div key={qt.type} className="p-4 rounded-xl border border-border flex items-start gap-3">
              <BookOpen className={`h-5 w-5 ${qt.color} mt-0.5`} />
              <div>
                <p className="text-sm font-bold">{qt.type}</p>
                <p className="text-xs text-muted-foreground">{qt.section}</p>
                <p className="text-xs text-muted-foreground mt-1">{qt.desc}</p>
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
                  <SpellCheck className="h-5 w-5 text-primary" /> What you&apos;ll get
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Target className="h-5 w-5 text-blue-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Accuracy</p>
                    <p className="text-xs text-muted-foreground">Overall &amp; per-topic scores.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <TrendingUp className="h-5 w-5 text-teal-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Grammar vs Vocabulary</p>
                    <p className="text-xs text-muted-foreground">Separate accuracy for each domain.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <AlertTriangle className="h-5 w-5 text-orange-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Weak Topics</p>
                    <p className="text-xs text-muted-foreground">Weak grammar topics &amp; weak vocabulary categories.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                  <Target className="h-5 w-5 text-purple-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-bold">Est. Band</p>
                    <p className="text-xs text-muted-foreground">Estimated IELTS band + CEFR level.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Action */}
          <Card className="h-full border-2 border-primary shadow-xl">
            <CardHeader className="text-center">
              <CardTitle>Ready to test yourself?</CardTitle>
              <CardDescription>
                Answer a series of vocabulary and grammar questions. Progress is saved as you go.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <ul className="space-y-3 text-sm">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> 8 question types
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> Instant grading &amp; report
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success" /> Results saved to your profile
                </li>
              </ul>
              <Link href="/diagnostic/vocab-grammar/test">
                <Button className="w-full h-12 text-lg shadow-lg" size="lg">
                  Start Diagnostic <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
