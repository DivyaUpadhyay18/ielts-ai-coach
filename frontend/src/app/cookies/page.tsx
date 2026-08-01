"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Cookie } from "lucide-react";
import { LandingLayout } from "@/components/layouts/landing-layout";

export default function CookiesPage() {
  return (
    <LandingLayout>
      <div className="container mx-auto px-4 py-16 max-w-3xl">
        <Link href="/" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary mb-8">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Home
        </Link>
        <div className="flex items-center gap-3 mb-8">
          <Cookie className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Cookie Policy</h1>
        </div>
        <div className="prose prose-slate dark:prose-invert max-w-none">
          <p className="lead">Last updated: November 2024</p>
          <h2>1. What Are Cookies</h2>
          <p>Cookies are small text files stored on your device to help websites function properly and provide a better user experience.</p>
          <h2>2. How We Use Cookies</h2>
          <p>We use essential cookies for authentication and session management. We use analytics cookies to understand how our service is used and improve it.</p>
          <h2>3. Third-Party Cookies</h2>
          <p>We use Supabase for authentication, which may set session cookies. We do not use advertising or tracking cookies.</p>
          <h2>4. Managing Cookies</h2>
          <p>You can control cookies through your browser settings. Disabling cookies may affect certain features of the service.</p>
        </div>
      </div>
    </LandingLayout>
  );
}

