"use client";

import React, { useState } from "react";
import { Sidebar } from "@/components/shared/sidebar";
import { Menu, X, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

const DashboardLayout = ({ children }: DashboardLayoutProps) => {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Desktop Sidebar (Hidden on Mobile) */}
      <div className="hidden md:flex md:flex-col md:fixed md:inset-y-0 md:z-50">
        <Sidebar />
      </div>

      {/* Main Content Wrapper */}
      <div className="flex flex-1 flex-col md:pl-64">
        
        {/* Dashboard Header (Mobile Toggle + Notifications) */}
        <header className="sticky top-0 z-40 flex h-16 shrink-0 items-center justify-between border-b border-border bg-background px-4 shadow-sm md:px-8">
          <div className="flex items-center">
            {/* Mobile Menu Button */}
            <button
              type="button"
              className="mr-4 text-muted-foreground md:hidden"
              onClick={() => setIsMobileSidebarOpen(true)}
            >
              <Menu className="h-6 w-6" />
            </button>
            <h2 className="text-sm font-medium text-muted-foreground md:text-base">
              Welcome back, Student
            </h2>
          </div>

          <div className="flex items-center space-x-4">
            <Button variant="ghost" size="icon" className="relative text-muted-foreground">
              <Bell className="h-5 w-5" />
              <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-error border-2 border-background"></span>
            </Button>
          </div>
        </header>

        {/* Scrollable Content Area */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="mx-auto max-w-7xl">
            {children}
          </div>
        </main>
      </div>

      {/* Mobile Sidebar Overlay (Drawer) */}
      {isMobileSidebarOpen && (
        <div className="fixed inset-0 z-[100] flex md:hidden">
          {/* Backdrop */}
          <div 
            className="fixed inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" 
            onClick={() => setIsMobileSidebarOpen(false)}
          />
          
          {/* Sidebar content */}
          <div className="relative flex w-full max-w-xs flex-1 flex-col bg-card animate-in slide-in-from-left duration-300">
            <div className="absolute right-2 top-2">
              <Button variant="ghost" size="icon" onClick={() => setIsMobileSidebarOpen(false)}>
                <X className="h-6 w-6" />
              </Button>
            </div>
            <Sidebar />
          </div>
        </div>
      )}
    </div>
  );
};

export { DashboardLayout };