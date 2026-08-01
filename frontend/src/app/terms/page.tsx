"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, FileText } from "lucide-react";
import { LandingLayout } from "@/components/layouts/landing-layout";

export default function TermsPage() {
  return (
    <LandingLayout>
      <div className="container mx-auto px-4 py-16 max-w-3xl">
        <Link href="/" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary mb-8">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Home
        </Link>
        <div className="flex items-center gap-3 mb-8">
          <FileText className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Terms of Service</h1>
        </div>
        <div className="prose prose-slate dark:prose-invert max-w-none">
          <p className="lead">Last updated: November 2024</p>
          <h2>1. Acceptance of Terms</h2>
          <p>By creating an account and using IELTS AI Coach, you agree to these Terms of Service. If you do not agree, please do not use the service.</p>
          <h2>2. Service Description</h2>
          <p>IELTS AI Coach provides AI-powered writing and speaking assessment tools to help users prepare for the IELTS exam. Results are estimates and should not be considered official IELTS scores.</p>
          <h2>3. User Accounts</h2>
          <p>You are responsible for maintaining the confidentiality of your account credentials. You must be at least 13 years of age to use this service.</p>
          <h2>4. Acceptable Use</h2>
          <p>You agree not to misuse the service, submit harmful content, or attempt to bypass any security measures.</p>
          <h2>5. Limitation of Liability</h2>
          <p>IELTS AI Coach provides practice tools only. We are not affiliated with the British Council, IDP, or Cambridge ESOL.</p>
        </div>
      </div>
    </LandingLayout>
  );
}

