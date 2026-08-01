"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Mail, ArrowLeft, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/layouts/auth-layout";
import { useAuthStore } from "@/app/store/useAuthStore";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const resetPassword = useAuthStore((state) => state.resetPassword);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    const result = await resetPassword(email);
    setIsLoading(false);
    if (result.error) {
      setError(result.error);
    } else {
      setIsSubmitted(true);
    }
  };

  return (
    <AuthLayout>
      <div className="space-y-6">
        {!isSubmitted ? (
          <>
            {/* Initial Form State */}
            <div className="text-center">
              <h2 className="text-2xl font-bold">Forgot Password?</h2>
              <p className="text-sm text-muted-foreground mt-2">
                No worries, we&apos;ll send you reset instructions.
              </p>
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-error/10 border border-error/20 text-sm text-error">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none" htmlFor="email">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input 
                    id="email"
                    placeholder="name@example.com" 
                    type="email" 
                    className="pl-10"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              <Button type="submit" className="w-full py-6 text-base font-semibold" disabled={isLoading}>
                {isLoading ? "Sending..." : "Reset Password"}
              </Button>
            </form>
          </>
        ) : (
          <>
            {/* Success State */}
            <div className="text-center space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10 text-success">
                <Send className="h-6 w-6" />
              </div>
              <h2 className="text-2xl font-bold">Check your email</h2>
              <p className="text-sm text-muted-foreground">
                We have sent a password reset link to <br/>
                <span className="font-medium text-foreground">{email}</span>
              </p>
              <Button 
                variant="outline" 
                className="w-full" 
                onClick={() => setIsSubmitted(false)}
              >
                Didn&apos;t receive the email? Click to retry
              </Button>
            </div>
          </>
        )}

        {/* Footer Link */}
        <div className="text-center">
          <Link 
            href="/login" 
            className="inline-flex items-center text-sm font-semibold text-primary hover:underline underline-offset-4"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to login
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
