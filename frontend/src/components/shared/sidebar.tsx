"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  PenTool, 
  Mic, 
  BarChart2, 
  Settings, 
  GraduationCap,
  Zap,
  ListChecks,
  Calendar,
  TrendingUp,
  History,
  BookOpen,
  PlayCircle,
  Trophy,
  MessageSquare,
  Brain,
} from "lucide-react";
import { cn } from "@/app/lib/utils";

const Sidebar = () => {
  const pathname = usePathname();

  const routes = [
    {
      label: "Overview",
      icon: LayoutDashboard,
      href: "/dashboard",
      active: pathname === "/dashboard",
    },
    {
      label: "Writing Practice",
      icon: PenTool,
      href: "/writing",
      active: pathname.startsWith("/writing"),
    },
    {
      label: "Speaking Coach",
      icon: Mic,
      href: "/speaking",
      active: pathname.startsWith("/speaking"),
    },
    {
      label: "History & Analytics",
      icon: BarChart2,
      href: "/analytics",
      active: pathname === "/analytics",
    },
    {
      label: "Daily Missions",
      icon: ListChecks,
      href: "/missions",
      active: pathname === "/missions",
    },
    {
      label: "Exam Countdown",
      icon: Calendar,
      href: "/countdown",
      active: pathname === "/countdown",
    },
    {
      label: "Prediction Engine",
      icon: TrendingUp,
      href: "/prediction",
      active: pathname === "/prediction",
    },
    {
      label: "AI Memory",
      icon: Brain,
      href: "/ai-memory",
      active: pathname === "/ai-memory" || pathname.startsWith("/ai-memory"),
    },
    {
      label: "AI Recommendations",
      icon: Zap,
      href: "/recommendations-ai",
      active: pathname === "/recommendations-ai" || pathname.startsWith("/recommendations-ai"),
    },
    {
      label: "Weekly AI Reports",
      icon: Calendar,
      href: "/weekly-reports",
      active: pathname === "/weekly-reports" || pathname.startsWith("/weekly-reports"),
    },
    {
      label: "Schedule History",
      icon: History,
      href: "/schedule-history",
      active: pathname === "/schedule-history",
    },
    {
      label: "Resource Library",
      icon: BookOpen,
      href: "/resources",
      active: pathname === "/resources",
    },
    {
      label: "Recommendations",
      icon: TrendingUp,
      href: "/recommendations",
      active: pathname === "/recommendations",
    },
    {
      label: "Learning Session",
      icon: PlayCircle,
      href: "/learn",
      active: pathname === "/learn",
    },
    {
      label: "AI Mentor",
      icon: MessageSquare,
      href: "/mentor",
      active: pathname === "/mentor",
    },
  ];

  const footerRoutes = [
    {
      label: "Settings",
      icon: Settings,
      href: "/settings",
      active: pathname === "/settings",
    },
  ];

  return (
    <div className="flex h-full w-64 flex-col border-r border-border bg-card text-card-foreground">
      <div className="flex flex-col flex-1 px-3 py-4">
        
        {/* Brand/Logo Section in Sidebar */}
        <div className="mb-8 px-3 py-2">
          <div className="flex items-center space-x-2">
            <GraduationCap className="h-6 w-6 text-primary" />
            <span className="text-lg font-bold">Coach Portal</span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1">
          {routes.map((route) => (
            <Link
              key={route.href}
              href={route.href}
              className={cn(
                "group flex w-full items-center justify-start rounded-lg px-3 py-2 text-sm font-medium transition-all",
                route.active 
                  ? "bg-primary text-primary-foreground shadow-sm" 
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )}
            >
              <route.icon className={cn(
                "mr-3 h-5 w-5 shrink-0",
                route.active ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground"
              )} />
              {route.label}
            </Link>
          ))}
        </nav>

        <div className="mt-auto pt-4">
          {/* Pro Upgrade Card */}
          <div className="mb-4 rounded-xl bg-accent/10 p-4 border border-accent/20">
            <div className="flex items-center space-x-2 mb-2">
              <Zap className="h-4 w-4 text-accent fill-current" />
              <span className="text-xs font-bold uppercase tracking-wider text-accent">Upgrade to Pro</span>
            </div>
            <p className="text-[11px] text-muted-foreground mb-3">
              Get unlimited AI feedback and mock exams.
            </p>
            <button className="w-full rounded-md bg-accent px-2 py-1.5 text-xs font-semibold text-accent-foreground hover:bg-accent/90">
              Go Premium
            </button>
          </div>

          {/* Settings/Bottom Links */}
          <nav className="space-y-1">
            {footerRoutes.map((route) => (
              <Link
                key={route.href}
                href={route.href}
                className={cn(
                  "group flex w-full items-center justify-start rounded-lg px-3 py-2 text-sm font-medium transition-all",
                  route.active 
                    ? "bg-secondary text-foreground" 
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <route.icon className="mr-3 h-5 w-5 shrink-0" />
                {route.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
    </div>
  );
};

export { Sidebar };