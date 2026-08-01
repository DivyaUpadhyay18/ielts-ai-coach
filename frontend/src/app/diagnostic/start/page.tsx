"use client";

import React, { useState } from "react";
import Link from "next/link";
import { 
  ArrowLeft, 
  Clock, 
  Mic, 
  PenTool, 
  BrainCircuit,
  CheckCircle
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function DiagnosticStartPage() {
  const [activeSection, setActiveSection] = useState<number | null>(null);

  const sections = [
    { id: 1, title: "Short Essay", icon: PenTool, color: "text-blue-500", duration: "10 mins" },
    { id: 2, title: "Speaking Clip", icon: Mic, color: "text-teal-500", duration: "5 mins" },
    { id: 3, title: "Vocabulary Check", icon: BrainCircuit, color: "text-purple-500", duration: "5 mins" },
  ];

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8 py-4">
        <div className="flex items-center justify-between">
          <Link href="/diagnostic" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Overview
          </Link>
          <Badge variant="accent" className="px-4 py-1">~20 minutes remaining</Badge>
        </div>

        <div className="text-center space-y-4">
          <h1 className="text-4xl font-extrabold tracking-tight">Diagnostic Assessment</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Complete each section below. Your AI coach will analyze your responses and create a personalized study plan.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {sections.map((section) => (
            <Card 
              key={section.id}
              className={`cursor-pointer transition-all hover:shadow-md ${activeSection === section.id ? 'ring-2 ring-primary border-transparent' : ''}`}
              onClick={() => setActiveSection(section.id)}
            >
              <CardContent className="pt-6 text-center space-y-4">
                <div className={`mx-auto p-3 rounded-xl bg-secondary w-fit ${section.color}`}>
                  <section.icon className="h-8 w-8" />
                </div>
                <div>
                  <h3 className="font-bold text-lg">{section.title}</h3>
                  <div className="flex items-center justify-center gap-1 text-sm text-muted-foreground mt-2">
                    <Clock className="h-3 w-3" /> {section.duration}
                  </div>
                </div>
                {activeSection === section.id && <CheckCircle className="mx-auto h-6 w-6 text-success" />}
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="flex flex-col items-center gap-4 pt-8 border-t border-border">
          <p className="text-sm text-muted-foreground">Select a section above to begin, or start the full assessment.</p>
          <Button size="lg" className="px-10 h-12 text-lg shadow-lg" disabled={activeSection === null}>
            Start Selected Section
          </Button>
        </div>
      </div>
    </DashboardLayout>
  );
}

