"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Mail, Lock, User, Eye, EyeOff, ArrowRight, AlertCircle, CheckCircle2, XCircle, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/layouts/auth-layout";
import { useAuthStore } from "@/app/store/useAuthStore";

// Password strength checker
const getPasswordStrength = (password: string): { score: number; label: string; color: string; checks: { label: string; passed: boolean }[] } => {
  const checks = [
    { label: "At least 8 characters", passed: password.length >= 8 },
    { label: "Contains uppercase letter", passed: /[A-Z]/.test(password) },
    { label: "Contains lowercase letter", passed: /[a-z]/.test(password) },
    { label: "Contains a number", passed: /\d/.test(password) },
    { label: "Contains special character", passed: /[!@#$%^&*(),.?":{}|<>_~`[\]';/\\]/.test(password) },
  ];
  
  const passedCount = checks.filter(c => c.passed).length;
  
  if (password.length === 0) return { score: 0, label: "", color: "bg-gray-200", checks };
  if (passedCount <= 2) return { score: 20, label: "Weak", color: "bg-error", checks };
  if (passedCount <= 3) return { score: 40, label: "Fair", color: "bg-warning", checks };
  if (passedCount <= 4) return { score: 70, label: "Good", color: "bg-accent", checks };
  return { score: 100, label: "Strong", color: "bg-success", checks };
};

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  
  const router = useRouter();
  const signup = useAuthStore((state) => state.signup);
  const user = useAuthStore((state) => state.user);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Redirect if already logged in
  useEffect(() => {
    if (mounted && user) {
      router.push("/dashboard");
    }
  }, [mounted, user, router]);

  const passwordStrength = getPasswordStrength(password);
  const passwordsMatch = password === confirmPassword;
  const isPasswordValid = passwordStrength.score >= 40;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Client-side validation
    if (!name.trim()) {
      setError("Please enter your full name");
      return;
    }
    if (!email.trim()) {
      setError("Please enter your email address");
      return;
    }
    if (!password) {
      setError("Please enter a password");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters long");
      return;
    }
    if (passwordStrength.score < 40) {
      setError("Please choose a stronger password");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setIsLoading(true);
    const result = await signup(email, password, name);
    setIsLoading(false);
    
    if (result.error) {
      setError(result.error);
    } else {
      router.push("/dashboard");
    }
  };

  if (!mounted) return null;

  return (
    <AuthLayout>
      <div className="space-y-6 animate-fade-in">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="mx-auto h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
            <User className="h-6 w-6 text-primary" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight">Create an Account</h2>
          <p className="text-sm text-muted-foreground">
            Start your 7-day free trial today
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 rounded-xl bg-error/5 border border-error/20 text-sm text-error animate-fade-in flex items-start gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Signup Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Full Name */}
          <div className="space-y-2">
            <label className="text-sm font-medium leading-none" htmlFor="name">
              Full Name
            </label>
            <div className="relative group">
              <User className="absolute left-3.5 top-3.5 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
              <Input 
                id="name"
                placeholder="John Doe" 
                type="text" 
                className="pl-10 h-12 transition-all focus:ring-2 focus:ring-primary/20"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isLoading}
                autoComplete="name"
              />
            </div>
          </div>

          {/* Email */}
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

          {/* Password */}
          <div className="space-y-2">
            <label className="text-sm font-medium leading-none" htmlFor="password">
              Password
            </label>
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
                autoComplete="new-password"
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
            
            {/* Password Strength Indicator */}
            {password.length > 0 && (
              <div className="space-y-2 pt-1 animate-fade-in">
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                    <div 
                      className={`h-full transition-all duration-300 rounded-full ${passwordStrength.color}`}
                      style={{ width: `${passwordStrength.score}%` }}
                    />
                  </div>
                  {passwordStrength.label && (
                    <span className="text-xs font-medium" style={{ color: passwordStrength.color.includes('bg-error') ? '#ef4444' : passwordStrength.color.includes('bg-warning') ? '#f59e0b' : passwordStrength.color.includes('bg-accent') ? '#14b8a6' : '#22c55e' }}>
                      {passwordStrength.label}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-1">
                  {passwordStrength.checks.map((check, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      {check.passed ? (
                        <CheckCircle2 className="h-3 w-3 text-success shrink-0" />
                      ) : (
                        <XCircle className="h-3 w-3 text-muted-foreground shrink-0" />
                      )}
                      <span className={check.passed ? "text-success" : "text-muted-foreground"}>
                        {check.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Confirm Password */}
          <div className="space-y-2">
            <label className="text-sm font-medium leading-none" htmlFor="confirmPassword">
              Confirm Password
            </label>
            <div className="relative group">
              <Lock className="absolute left-3.5 top-3.5 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
              <Input 
                id="confirmPassword"
                placeholder="••••••••" 
                type={showConfirmPassword ? "text" : "password"} 
                className="pl-10 pr-10 h-12 transition-all focus:ring-2 focus:ring-primary/20"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isLoading}
                autoComplete="new-password"
                error={confirmPassword.length > 0 && !passwordsMatch}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3.5 top-3.5 text-muted-foreground hover:text-foreground transition-colors"
                tabIndex={-1}
              >
                {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {confirmPassword.length > 0 && !passwordsMatch && (
              <p className="text-xs text-error animate-fade-in flex items-center gap-1">
                <XCircle className="h-3 w-3" /> Passwords do not match
              </p>
            )}
            {confirmPassword.length > 0 && passwordsMatch && (
              <p className="text-xs text-success animate-fade-in flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Passwords match
              </p>
            )}
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
                Creating Account...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                Create Account <ArrowRight className="h-5 w-5" />
              </span>
            )}
          </Button>
        </form>

        {/* Terms Disclaimer */}
        <p className="text-center text-[11px] text-muted-foreground px-4 leading-relaxed">
          By clicking &quot;Create Account&quot;, you agree to our{" "}
          <Link href="/terms" className="font-medium text-primary hover:text-primary/80 transition-colors underline underline-offset-2">
            Terms of Service
          </Link> and{" "}
          <Link href="/privacy" className="font-medium text-primary hover:text-primary/80 transition-colors underline underline-offset-2">
            Privacy Policy
          </Link>
        </p>

        {/* Footer Link */}
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link 
            href="/login" 
            className="font-semibold text-primary hover:text-primary/80 transition-colors underline-offset-4 hover:underline"
          >
            Log in
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
