"use client";

import React from "react";
import { 
  Map as MapIcon, 
  CheckCircle2, 
  Lock, 
  PlayCircle,
  Flag,
  PenTool,
  Mic,
  BookOpen,
  ChevronRight,
  TrendingUp
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

export default function RoadmapPage() {
  const roadmapData = [
    {
      phase: "Phase 1: Foundation",
      status: "completed",
      description: "Mastering the basics and understanding the exam format.",
      tasks: [
        { title: "Diagnostic Assessment", skill: "General", done: true },
        { title: "Grammar: Subject-Verb Agreement", skill: "Writing", done: true },
      ]
    },
    {
      phase: "Phase 2: Skill Building",
      status: "active",
      description: "Deep dive into complex structures and fluency techniques.",
      tasks: [
        { title: "Writing Task 2: Opinion Essays", skill: "Writing", done: true },
        { title: "Speaking Part 2: Long Turn Drills", skill: "Speaking", done: false, active: true },
        { title: "Lexical Resource: Academic Verbs", skill: "Vocabulary", done: false },
      ]
    },
    {
      phase: "Phase 3: Mock Intensive",
      status: "locked",
      description: "Full-length timed practices and final strategy refinement.",
      tasks: [
        { title: "Writing Task 1: Data Trends", skill: "Writing", done: false },
        { title: "Full Speaking Mock Exam", skill: "Speaking", done: false },
        { title: "Final Band Strategy Session", skill: "General", done: false },
      ]
    }
  ];

  return (
    <DashboardLayout>
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <MapIcon className="h-8 w-8 text-primary" /> Study Roadmap
            </h1>
            <p className="text-muted-foreground">Your personalized path from Band 6.5 to Band 7.5</p>
          </div>
          <Card className="min-w-[240px]">
            <CardContent className="py-4">
              <div className="flex justify-between items-end mb-2">
                <span className="text-xs font-semibold text-muted-foreground uppercase">Overall Progress</span>
                <span className="text-sm font-bold">35%</span>
              </div>
              <Progress value={35} className="h-2" variant="default" />
            </CardContent>
          </Card>
        </div>

        {/* Milestone Timeline */}
        <div className="relative space-y-12 before:absolute before:left-4 before:top-2 before:bottom-2 before:w-0.5 before:bg-border md:before:left-8">
          
          {roadmapData.map((section, idx) => (
            <div key={idx} className="relative pl-12 md:pl-20">
              {/* Timeline Indicator Icon */}
              <div className={`absolute left-0 md:left-4 top-0 flex h-8 w-8 md:h-10 md:w-10 items-center justify-center rounded-full border-4 border-background z-10 shadow-sm
                ${section.status === 'completed' ? 'bg-success text-white' : 
                  section.status === 'active' ? 'bg-primary text-white animate-pulse' : 'bg-muted text-muted-foreground'}`}
              >
                {section.status === 'completed' ? <CheckCircle2 className="h-5 w-5" /> : 
                 section.status === 'active' ? <PlayCircle className="h-5 w-5" /> : <Lock className="h-5 w-5" />}
              </div>

              {/* Phase Content */}
              <div className="space-y-4">
                <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4">
                  <h2 className={`text-xl font-bold ${section.status === 'locked' ? 'text-muted-foreground' : 'text-foreground'}`}>
                    {section.phase}
                  </h2>
                  {section.status === 'active' && <Badge variant="accent">Current Focus</Badge>}
                </div>
                <p className="text-muted-foreground text-sm max-w-2xl">{section.description}</p>

                {/* Tasks Grid */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 pt-2">
                  {section.tasks.map((task, tIdx) => (
                    <Card key={tIdx} className={`relative overflow-hidden transition-all ${task.active ? 'ring-2 ring-primary border-transparent shadow-md' : 'shadow-none'}`}>
                      <CardContent className="p-4">
                        <div className="flex justify-between items-start mb-3">
                          <Badge variant="outline" className="text-[10px]">
                            {task.skill === 'Writing' ? <PenTool className="h-3 w-3 mr-1" /> : 
                             task.skill === 'Speaking' ? <Mic className="h-3 w-3 mr-1" /> : <BookOpen className="h-3 w-3 mr-1" />}
                            {task.skill}
                          </Badge>
                          {task.done && <CheckCircle2 className="h-4 w-4 text-success" />}
                        </div>
                        <h4 className={`text-sm font-bold mb-4 ${section.status === 'locked' ? 'text-muted-foreground' : ''}`}>
                          {task.title}
                        </h4>
                        
                        {section.status !== 'locked' && (
                          <Button 
                            variant={task.done ? "ghost" : task.active ? "default" : "outline"} 
                            size="sm" 
                            className="w-full text-xs h-8"
                          >
                            {task.done ? "Review" : task.active ? "Start Now" : "Unlock"} 
                            <ChevronRight className="ml-1 h-3 w-3" />
                          </Button>
                        )}
                      </CardContent>
                      {section.status === 'locked' && <div className="absolute inset-0 bg-background/40 backdrop-blur-[1px]" />}
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          ))}

          {/* Goal Flag */}
          <div className="relative pl-12 md:pl-20">
            <div className="absolute left-0 md:left-4 top-0 flex h-8 w-8 md:h-10 md:w-10 items-center justify-center rounded-full bg-warning text-white z-10 shadow-lg">
              <Flag className="h-5 w-5" />
            </div>
            <div className="bg-slate-900 rounded-2xl p-6 text-white flex flex-col md:flex-row items-center justify-between gap-6 border border-slate-800">
               <div className="space-y-1 text-center md:text-left">
                  <h3 className="text-xl font-bold">Goal: IELTS Band 7.5</h3>
                  <p className="text-slate-400 text-sm">Estimated Achievement Date: Dec 10, 2024</p>
               </div>
               <div className="flex items-center gap-3 bg-white/10 px-4 py-2 rounded-xl">
                  <TrendingUp className="h-5 w-5 text-accent" />
                  <span className="text-sm font-medium">Confidence Score: 88%</span>
               </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}