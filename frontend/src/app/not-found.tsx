"use client";

import React from "react";
import Link from "next/link";
import { 
  Home, 
  LayoutDashboard, 
  BookOpen, 
  ArrowLeft,
  Search,
  Zap
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { LandingLayout } from "@/components/layouts/landing-layout";

export default function NotFound() {
  return (
    <LandingLayout>
      <div className="min-h-[70vh] flex items-center justify-center px-4">
        <div className="max-w-2xl w-full text-center space-y-8">
          
          {/* Visual 404 Element */}
          <div className="relative inline-block">
            <h1 className="text-[12rem] font-black text-slate-100 dark:text-slate-900 leading-none select-none">
              404
            </h1>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="bg-primary p-4 rounded-2xl shadow-2xl rotate-3 animate-bounce">
                <Zap className="h-12 w-12 text-white fill-current" />
              </div>
            </div>
          </div>

          {/* Message Area */}
          <div className="space-y-4">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Lost your way to Band 9.0?
            </h2>
            <p className="text-lg text-muted-foreground max-w-md mx-auto">
              The page you are looking for doesn&apos;t exist or has been moved. 
              Let&apos;s get your study session back on track.
            </p>
          </div>

          {/* Action Links */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <Link href="/">
              <Button variant="outline" size="lg" className="w-full sm:w-auto">
                <Home className="mr-2 h-4 w-4" /> Go Home
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button size="lg" className="w-full sm:w-auto shadow-lg shadow-primary/20">
                <LayoutDashboard className="mr-2 h-4 w-4" /> Go to Dashboard
              </Button>
            </Link>
          </div>

          {/* Secondary Links */}
          <div className="pt-8 border-t border-border mt-12">
            <p className="text-sm font-medium text-muted-foreground mb-4">Looking for something else?</p>
            <div className="flex flex-wrap justify-center gap-6">
              <Link href="/resources" className="text-sm flex items-center gap-1.5 text-muted-foreground hover:text-primary transition-colors">
                <BookOpen className="h-4 w-4" /> Resource Library
              </Link>
              <Link href="/dashboard" className="text-sm flex items-center gap-1.5 text-muted-foreground hover:text-primary transition-colors">
                <Search className="h-4 w-4" /> Go to Dashboard
              </Link>
            </div>
          </div>

          <div className="pt-6">
            <Button variant="ghost" onClick={() => window.history.back()} className="text-xs">
              <ArrowLeft className="mr-2 h-3 w-3" /> Go back to previous page
            </Button>
          </div>

        </div>
      </div>
    </LandingLayout>
  );
}