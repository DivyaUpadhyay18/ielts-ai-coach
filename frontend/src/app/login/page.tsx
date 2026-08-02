"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail, Lock, Eye, EyeOff, ArrowRight, Chrome, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/layouts/auth-layout";
import { useAuthStore } from "@/app/store/useAuthStore";

// Page wrapper with Suspense boundary for useSearchParams (Next.js 15 CSR bailout requirement)
export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginForm />
    </Suspense>
  );
}

// Rendered while the Suspense boundary is waiting
function LoginFallback() {
  return (
    <AuthLayout>
      <div className="space-y-6 animate-fade-in">
        <div className="text-center space-y-2">
          <div className="mx-auto h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
            <Lock className="h-6 w-6 text-primary" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight">Welcome Back</h2>
          <p className="text-sm text-muted-foreground">
            Log in to continue your IELTS journey
          </p>
        </div>
        <div className="space-y-4">
          <div className="h-12 w-full rounded-xl bg-secondary animate-pulse" />
          <div className="h-12 w-full rounded-xl bg-secondary animate-pulse" />
          <div className="h-12 w-full rounded-xl bg-secondary animate-pulse" />
        </div>
      </div>
    </AuthLayout>
  );
}

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  
  const router = useRouter();
  const searchParams = useSearchParams();
  const login = useAuthStore((state) => state.login);
  const loginWithGoogle = useAuthStore((state) => state.loginWithGoogle);
  const user = useAuthStore((state) => state.user);

  useEffect(() => {
    setMounted(true);
    // Check for redirect parameter
    const redirect = searchParams.get("redirect");
    if (redirect && user) {
      router.push(redirect);
    }
  }, [searchParams, user, router]);

  // Redirect if already logged in
  useEffect(() => {
    if (mounted && user) {
      const redirect = searchParams.get("redirect") || "/dashboard";
      router.push(redirect);
    }
  }, [mounted, user, router, searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Please enter your email address");
      return;
    }
    if (!password) {
      setError("Please enter your password");
      return;
    }

    setIsLoading(true);
    const result = await login(email, password);
    setIsLoading(false);
    
    if (result.error) {
      setError(result.error);
    } else {
      const redirect = searchParams.get("redirect") || "/dashboard";
      router.push(redirect);
    }
  };

  if (!mounted) return null;

  return (
    <AuthLayout>
      <div className="space-y-6 animate-fade-in">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="mx-auto h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
            <Lock className="h-6 w-6 text-primary" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight">Welcome Back</h2>
          <p className="text-sm text-muted-foreground">
            Log in to continue your IELTS journey
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 rounded-xl bg-error/5 border border-error/20 text-sm text-error animate-fade-in flex items-start gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Social Login */}
        <Button 
          variant="outline" 
          className="w-full h-12 text-base font-medium transition-all hover:bg-secondary/80 active:scale-[0.98]"
          onClick={loginWithGoogle}
        >
          <Chrome className="mr-3 h-5 w-5" />
          Continue with Google
        </Button>

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card px-3 text-muted-foreground">Or continue with email</span>
          </div>
        </div>

        {/* Login Form */}
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

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium leading-none" htmlFor="password">
                Password
              </label>
              <Link 
                href="/forgot-password" 
                className="text-xs text-primary hover:text-primary/80 transition-colors underline-offset-4 hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative group">
              <Lock className="absolute left-3.5 top-3.5 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
              <Input 
                id="password"
                placeholder="••••••••" 
                type={showPassword ? "text" : "password"} 
                className="pl-10 pr-10 h-12 transition-all focus:ring-2 focus:ring-primary/20"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-3.5 text-muted-foreground hover:text-foreground transition-colors"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
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
                Signing in...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                Sign In <ArrowRight className="h-5 w-5" />
              </span>
            )}
          </Button>
        </form>

        {/* Footer Link */}
        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link 
            href="/signup" 
            className="font-semibold text-primary hover:text-primary/80 transition-colors underline-offset-4 hover:underline"
          >
            Create an account
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
