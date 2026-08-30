"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, PenTool } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Badge } from "@/components/ui/badge";
import { WritingDiagnosticTest } from "@/components/diagnostic/writing-diagnostic-test";

export default function WritingDiagnosticTestPage() {
  return (
    <DashboardLayout>
      <div className="max-w-6xl mx-auto space-y-6 py-4">
        <div className="flex items-center justify-between">
          <Link href="/diagnostic/writing" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Writing Overview
          </Link>
          <Badge variant="accent" className="px-4 py-1">Auto-saved</Badge>
        </div>

        <div className="flex items-center gap-2">
          <PenTool className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-bold">Writing Diagnostic Test</h1>
        </div>

        <WritingDiagnosticTest />
      </div>
    </DashboardLayout>
  );
}
