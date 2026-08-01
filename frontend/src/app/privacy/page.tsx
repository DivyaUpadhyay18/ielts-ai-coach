"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Shield } from "lucide-react";
import { LandingLayout } from "@/components/layouts/landing-layout";

export default function PrivacyPage() {
  return (
    <LandingLayout>
      <div className="container mx-auto px-4 py-16 max-w-3xl">
        <Link href="/" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary mb-8">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Home
        </Link>
        <div className="flex items-center gap-3 mb-8">
          <Shield className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Privacy Policy</h1>
        </div>
        <div className="prose prose-slate dark:prose-invert max-w-none">
          <p className="lead">Last updated: November 2024</p>
          <h2>1. Information We Collect</h2>
          <p>We collect information you provide when creating an account, including your name, email address, and IELTS target scores. We also collect your practice essays and speaking recordings to provide AI-powered feedback.</p>
          <h2>2. How We Use Your Information</h2>
          <p>Your data is used to personalize your learning experience, generate AI feedback on your practice tasks, and improve our assessment algorithms.</p>
          <h2>3. Data Storage</h2>
          <p>All data is stored securely using Supabase with encryption at rest and in transit. We do not share your personal data with third parties.</p>
          <h2>4. Your Rights</h2>
          <p>You can request deletion of your account and associated data at any time by contacting support.</p>
          <h2>5. Contact</h2>
          <p>For privacy-related inquiries, contact us at privacy@ieltsaicoach.com.</p>
        </div>
      </div>
    </LandingLayout>
  );
}

