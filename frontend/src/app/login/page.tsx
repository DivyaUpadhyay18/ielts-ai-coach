"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Mail, Lock, Chrome } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/layouts/auth-layout";
import { useAuthStore } from "@/app/store/useAuthStore";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  const loginWithGoogle = useAuthStore((state) => state.loginWithGoogle);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    const result = await login(email, password);
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
          <h2 className="text-2xl font-bold">Welcome Back</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Log in to continue your IELTS journey
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-3 rounded-lg bg-error/10 border border-error/20 text-sm text-error">
            {error}
          </div>
        )}

        {/* Social Login */}
        <Button variant="outline" className="w-full py-6" onClick={loginWithGoogle}>
          <Chrome className="mr-2 h-5 w-5" />
          Continue with Google
        </Button>

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card px-2 text-muted-foreground">Or continue with email</span>
          </div>
        </div>

        {/* Login Form */}
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

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium leading-none" htmlFor="password">
                Password
              </label>
              <Link 
                href="/forgot-password" 
                className="text-xs text-primary hover:underline underline-offset-4"
              >
                Forgot password?
              </Link>
            </div>
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

          <Button type="submit" className="w-full py-6 text-base font-semibold" disabled={isLoading}>
            {isLoading ? "Signing in..." : "Sign In"}
          </Button>
        </form>

        {/* Footer Link */}
        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link 
            href="/signup" 
            className="font-semibold text-primary hover:underline underline-offset-4"
          >
            Create an account
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
