"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Headphones } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Badge } from "@/components/ui/badge";
import { ListeningDiagnosticTest } from "@/components/diagnostic/listening-diagnostic-test";

export default function ListeningDiagnosticTestPage() {
  return (
    <DashboardLayout>
      <div className="max-w-5xl mx-auto space-y-6 py-4">
        <div className="flex items-center justify-between">
          <Link href="/diagnostic/listening" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Listening Overview
          </Link>
          <Badge variant="accent" className="px-4 py-1">Answers graded instantly</Badge>
        </div>

        <div className="flex items-center gap-2">
          <Headphones className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-bold">Listening Diagnostic Test</h1>
        </div>

        <ListeningDiagnosticTest />
      </div>
    </DashboardLayout>
  );
}
