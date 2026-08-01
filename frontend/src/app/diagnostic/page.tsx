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
  BrainCircuit
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
              
              <Link href="/diagnostic/result">
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
      </div>
    </DashboardLayout>
  );
}