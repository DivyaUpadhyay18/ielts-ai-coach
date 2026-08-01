"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Mail, Lock, User, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/layouts/auth-layout";
import { useAuthStore } from "@/app/store/useAuthStore";

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const signup = useAuthStore((state) => state.signup);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
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

  return (
    <AuthLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="text-center">
          <h2 className="text-2xl font-bold">Create an Account</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Start your 7-day free trial today
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-3 rounded-lg bg-error/10 border border-error/20 text-sm text-error">
            {error}
          </div>
        )}

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card px-2 text-muted-foreground">Or use your email</span>
          </div>
        </div>

        {/* Signup Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Full Name */}
          <div className="space-y-2">
            <label className="text-sm font-medium leading-none" htmlFor="name">
              Full Name
            </label>
            <div className="relative">
              <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input 
                id="name"
                placeholder="John Doe" 
                type="text" 
                className="pl-10"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
          </div>

          {/* Email */}
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

          {/* Password */}
          <div className="space-y-2">
            <label className="text-sm font-medium leading-none" htmlFor="password">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input 
                id="password"
                placeholder="••••••••" 
                type="password" 
                className="pl-10"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {/* Confirm Password */}
          <div className="space-y-2">
            <label className="text-sm font-medium leading-none" htmlFor="confirmPassword">
              Confirm Password
            </label>
            <div className="relative">
              <CheckCircle className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input 
                id="confirmPassword"
                placeholder="••••••••" 
                type="password" 
                className="pl-10"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
          </div>

          <Button type="submit" className="w-full py-6 text-base font-semibold" disabled={isLoading}>
            {isLoading ? "Creating Account..." : "Create Account"}
          </Button>
        </form>

        {/* Terms Disclaimer */}
        <p className="text-center text-[11px] text-muted-foreground px-4">
          By clicking &quot;Create Account&quot;, you agree to our{" "}
          <Link href="/terms" className="underline hover:text-primary">Terms of Service</Link> and{" "}
          <Link href="/privacy" className="underline hover:text-primary">Privacy Policy</Link>.
        </p>

        {/* Footer Link */}
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link 
            href="/login" 
            className="font-semibold text-primary hover:underline underline-offset-4"
          >
            Log in
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}