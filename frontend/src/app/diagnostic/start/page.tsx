"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Badge } from "@/components/ui/badge";
import { DiagnosticTest } from "@/components/diagnostic/diagnostic-test";

export default function DiagnosticStartPage() {
  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6 py-4">
        <div className="flex items-center justify-between">
          <Link href="/diagnostic" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Overview
          </Link>
          <Badge variant="accent" className="px-4 py-1">Progress auto-saves as you go</Badge>
        </div>

        <DiagnosticTest />
      </div>
    </DashboardLayout>
  );
}

