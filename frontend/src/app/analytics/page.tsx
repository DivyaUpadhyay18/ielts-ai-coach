"use client";

import React from "react";
import { 
  BarChart3, 
  Target, 
  ArrowUpRight, 
  ArrowDownRight,
  Filter,
  Download,
  Info
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function ProgressAnalytics() {
  // Mock Data for UI
  const stats = [
    { label: "Overall Band", value: "6.8", trend: "+0.3", upward: true },
    { label: "Writing Avg", value: "6.5", trend: "+0.5", upward: true },
    { label: "Speaking Avg", value: "7.0", trend: "-0.2", upward: false },
    { label: "Tests Taken", value: "12", trend: "+2", upward: true },
  ];

  const skillGaps = [
    { name: "Task Response", score: 7.5, target: 8.0 },
    { name: "Cohesion & Coherence", score: 6.0, target: 7.5 },
    { name: "Lexical Resource", score: 7.0, target: 7.5 },
    { name: "Grammatical Accuracy", score: 6.5, target: 7.5 },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-8 pb-12">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Performance Analytics</h1>
            <p className="text-muted-foreground">Detailed insights into your IELTS preparation journey.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Download className="mr-2 h-4 w-4" /> Export Data
            </Button>
            <Button size="sm">
              <Filter className="mr-2 h-4 w-4" /> Last 30 Days
            </Button>
          </div>
        </div>

        {/* 1. Quick Stats Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => (
            <Card key={stat.label}>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
                  <Badge variant={stat.upward ? "success" : "destructive"} className="h-5">
                    {stat.upward ? <ArrowUpRight className="h-3 w-3 mr-1" /> : <ArrowDownRight className="h-3 w-3 mr-1" />}
                    {stat.trend}
                  </Badge>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <h3 className="text-3xl font-bold">{stat.value}</h3>
                  <span className="text-xs text-muted-foreground">avg</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid gap-8 lg:grid-cols-3">
          
          {/* 2. Main Chart: Band Score Trend (Visual Mock) */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Band Score Trend</CardTitle>
                <CardDescription>How your estimated band has evolved over time.</CardDescription>
              </div>
              <BarChart3 className="h-5 w-5 text-muted-foreground" />
            </CardHeader>
            <CardContent className="pt-4">
              <div className="h-[300px] w-full bg-slate-50 dark:bg-slate-900 rounded-xl border border-dashed border-border flex items-end justify-around p-6 relative">
                {/* Visual Bars for Mocking a Chart */}
                {[40, 55, 45, 70, 65, 80, 75, 85].map((height, i) => (
                  <div key={i} className="w-full max-w-[40px] group relative flex flex-col items-center">
                    <div 
                      className="w-full bg-primary/20 hover:bg-primary transition-all rounded-t-sm" 
                      style={{ height: `${height}%` }}
                    />
                    <span className="mt-2 text-[10px] text-muted-foreground">W{i+1}</span>
                  </div>
                ))}
                
                {/* Legend Overlay */}
                <div className="absolute top-4 right-6 flex gap-4">
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-primary" />
                    <span className="text-[10px] text-muted-foreground">Estimated Band</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 3. Skill Balance / Gap Analysis */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" /> Skill Gaps
              </CardTitle>
              <CardDescription>Current performance vs. Target Band 7.5</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {skillGaps.map((skill) => (
                <div key={skill.name} className="space-y-2">
                  <div className="flex justify-between items-end">
                    <span className="text-xs font-bold">{skill.name}</span>
                    <span className="text-[10px] text-muted-foreground">Gap: -{(skill.target - skill.score).toFixed(1)}</span>
                  </div>
                  <div className="relative h-2 w-full bg-secondary rounded-full overflow-hidden">
                    {/* The Target Marker */}
                    <div 
                      className="absolute top-0 bottom-0 w-0.5 bg-warning z-10" 
                      style={{ left: `${(skill.target / 9) * 100}%` }}
                    />
                    {/* The Current Progress */}
                    <div 
                      className="h-full bg-primary rounded-full" 
                      style={{ width: `${(skill.score / 9) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
              
              <div className="pt-4 p-3 bg-warning/5 border border-warning/20 rounded-lg flex items-start gap-3">
                <Info className="h-4 w-4 text-warning mt-0.5" />
                <p className="text-[11px] text-muted-foreground">
                  Your **Coherence & Cohesion** is currently your biggest bottleneck. Improving this will have the highest impact on your overall band.
                </p>
              </div>
            </CardContent>
          </Card>

        </div>

        {/* 4. Recent Test History Table */}
        <Card>
          <CardHeader>
            <CardTitle>Detailed Test History</CardTitle>
            <CardDescription>A complete log of your recent evaluations.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="text-left font-medium py-3 px-2">Date</th>
                    <th className="text-left font-medium py-3 px-2">Task Type</th>
                    <th className="text-left font-medium py-3 px-2">Topic</th>
                    <th className="text-right font-medium py-3 px-2">Band</th>
                    <th className="text-right font-medium py-3 px-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {[
                    { date: "Oct 24", type: "Writing T2", topic: "Environment", score: "7.0", status: "Improved" },
                    { date: "Oct 22", type: "Speaking P1", topic: "Hobbies", score: "6.5", status: "Stable" },
                    { date: "Oct 20", type: "Writing T1", topic: "Bar Chart", score: "6.0", status: "Needs Work" },
                    { date: "Oct 18", type: "Speaking P2", topic: "A Famous Person", score: "7.5", status: "Excellent" },
                  ].map((row, i) => (
                    <tr key={i} className="group hover:bg-slate-50 transition-colors">
                      <td className="py-4 px-2 text-muted-foreground">{row.date}</td>
                      <td className="py-4 px-2 font-medium">{row.type}</td>
                      <td className="py-4 px-2 text-muted-foreground">{row.topic}</td>
                      <td className="py-4 px-2 text-right font-bold">{row.score}</td>
                      <td className="py-4 px-2 text-right">
                        <Badge variant="secondary" className="text-[10px]">{row.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Button variant="ghost" className="w-full mt-4 text-xs">Load More History</Button>
          </CardContent>
        </Card>

      </div>
    </DashboardLayout>
  );
}