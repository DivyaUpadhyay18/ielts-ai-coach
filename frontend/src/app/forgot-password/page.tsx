"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Mail, ArrowLeft, Send, AlertCircle, CheckCircle2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/layouts/auth-layout";
import { useAuthStore } from "@/app/store/useAuthStore";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  const resetPassword = useAuthStore((state) => state.resetPassword);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Please enter your email address");
      return;
    }

    setIsLoading(true);
    const result = await resetPassword(email);
    setIsLoading(false);
    
    if (result.error) {
      setError(result.error);
    } else {
      setIsSubmitted(true);
    }
  };

  const handleRetry = () => {
    setIsSubmitted(false);
    setError("");
  };

  if (!mounted) return null;

  return (
    <AuthLayout>
      <div className="space-y-6 animate-fade-in">
        {!isSubmitted ? (
          <>
            {/* Initial Form State */}
            <div className="text-center space-y-2">
              <div className="mx-auto h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Mail className="h-6 w-6 text-primary" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight">Forgot Password?</h2>
              <p className="text-sm text-muted-foreground">
                No worries, we&apos;ll send you reset instructions.
              </p>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-4 rounded-xl bg-error/5 border border-error/20 text-sm text-error animate-fade-in flex items-start gap-3">
                <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none" htmlFor="email">
                  Email Address
                </label>
                <div className="relative group">
                  <Mail className="absolute left-3.5 top-3.5 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <Input 
                    id="email"
                    placeholder="name@example.com" 
                    type="email" 
                    className="pl-10 h-12 transition-all focus:ring-2 focus:ring-primary/20"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isLoading}
                    autoComplete="email"
                  />
                </div>
              </div>

              <Button 
                type="submit" 
                className="w-full h-12 text-base font-semibold transition-all active:scale-[0.98]"
                disabled={isLoading}
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Sending...
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    Send Reset Instructions <ArrowRight className="h-5 w-5" />
                  </span>
                )}
              </Button>
            </form>
          </>
        ) : (
          <>
            {/* Success State */}
            <div className="text-center space-y-4 animate-fade-in">
              <div className="mx-auto h-16 w-16 rounded-full bg-success/10 flex items-center justify-center">
                <CheckCircle2 className="h-8 w-8 text-success" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold tracking-tight">Check your email</h2>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  We have sent a password reset link to
                </p>
                <p className="text-sm font-semibold text-foreground bg-secondary/50 rounded-lg px-4 py-2 inline-block">
                  {email}
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  Didn&apos;t receive the email? Check your spam folder or try again.
                </p>
              </div>
              
              <div className="space-y-3 pt-2">
                <Button 
                  variant="outline" 
                  className="w-full h-12"
                  onClick={handleRetry}
                >
                  <Send className="mr-2 h-4 w-4" />
                  Click to retry
                </Button>
              </div>
            </div>
          </>
        )}

        {/* Footer Link */}
        <div className="text-center pt-2">
          <Link 
            href="/login" 
            className="inline-flex items-center text-sm font-semibold text-primary hover:text-primary/80 transition-colors underline-offset-4 hover:underline"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to login
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
