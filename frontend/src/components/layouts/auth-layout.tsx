import React from "react";
import Link from "next/link";
import { Zap, ChevronLeft } from "lucide-react";

interface AuthLayoutProps {
  children: React.ReactNode;
}

const AuthLayout = ({ children }: AuthLayoutProps) => {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8 dark:bg-slate-950">
      <div className="w-full max-w-md space-y-8">
        
        {/* Top Navigation / Brand */}
        <div className="flex flex-col items-center">
          <Link 
            href="/" 
            className="group mb-6 flex items-center text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
          >
            <ChevronLeft className="mr-1 h-4 w-4 transition-transform group-hover:-translate-x-1" />
            Back to home
          </Link>
          
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary shadow-lg text-primary-foreground mb-4">
            <Zap className="h-8 w-8 fill-current" />
          </div>
          
          <h1 className="text-2xl font-bold tracking-tight">
            IELTS<span className="text-accent">AI</span> Coach
          </h1>
        </div>

        {/* The Auth Form (Login or Signup) */}
        <div className="rounded-2xl border border-border bg-card p-8 shadow-xl">
          {children}
        </div>

        {/* Trust Footer */}
        <p className="text-center text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} IELTS AI Coach. <br />
          Secure, encrypted authentication.
        </p>
      </div>
    </div>
  );
};

export { AuthLayout };