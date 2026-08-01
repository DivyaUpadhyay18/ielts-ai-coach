"use client";

import React from "react";
import { 
  TrendingUp, 
  Calendar, 
  Target, 
  Clock, 
  ArrowRight, 
  PenTool, 
  Mic, 
  CheckCircle2,
  AlertCircle
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

export default function Dashboard() {
  // Mock data for the UI
  const userStats = {
    name: "Alex",
    currentBand: 6.5,
    targetBand: 8.0,
    examDate: "Dec 15, 2024",
    daysLeft: 24,
    progress: 65,
  };

  const recentTasks = [
    { id: 1, type: "Writing", task: "Task 2: Education", score: 7.0, date: "2 hours ago" },
    { id: 2, type: "Speaking", task: "Part 1: Hobbies", score: 6.5, date: "Yesterday" },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-8">
        
        {/* 1. Welcome & High-Level Stats */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card className="col-span-full lg:col-span-2 bg-primary text-primary-foreground">
            <CardContent className="pt-6">
              <div className="flex flex-col space-y-2">
                <h1 className="text-3xl font-bold">Good Morning, {userStats.name}!</h1>
                <p className="text-primary-foreground/80">
                  You&apos;re making great progress. You&apos;ve studied for 5 days in a row!
                </p>
                <div className="pt-4">
                  <Button variant="accent" size="sm">
                    Continue Last Lesson
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium">Estimated Band</CardTitle>
              <TrendingUp className="h-4 w-4 text-accent" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{userStats.currentBand}</div>
              <p className="text-xs text-muted-foreground">+0.5 from last week</p>
              <Progress value={userStats.progress} className="mt-3" variant="accent" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium">Exam Countdown</CardTitle>
              <Calendar className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{userStats.daysLeft} Days</div>
              <p className="text-xs text-muted-foreground">Exam on {userStats.examDate}</p>
              <div className="mt-3 flex items-center text-xs text-warning font-medium">
                <AlertCircle className="mr-1 h-3 w-3" /> Time to intensify practice
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 2. Main Content Grid */}
        <div className="grid gap-8 lg:grid-cols-3">
          
          {/* Left/Middle: Progress & History */}
          <div className="lg:col-span-2 space-y-8">
            {/* Quick Actions */}
            <div className="grid gap-4 sm:grid-cols-2">
              <Card className="hover:border-primary/50 cursor-pointer transition-colors group">
                <CardContent className="pt-6">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 rounded-xl bg-blue-100 text-blue-600 group-hover:bg-primary group-hover:text-white transition-colors">
                      <PenTool className="h-6 w-6" />
                    </div>
                    <div>
                      <h3 className="font-bold">Writing Practice</h3>
                      <p className="text-xs text-muted-foreground">Grade your Task 1 & 2 essays</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="hover:border-accent/50 cursor-pointer transition-colors group">
                <CardContent className="pt-6">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 rounded-xl bg-teal-100 text-teal-600 group-hover:bg-accent group-hover:text-white transition-colors">
                      <Mic className="h-6 w-6" />
                    </div>
                    <div>
                      <h3 className="font-bold">Speaking Coach</h3>
                      <p className="text-xs text-muted-foreground">Practice with AI Examiner</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Recent Assessments */}
            <Card>
              <CardHeader>
                <CardTitle>Recent Assessments</CardTitle>
                <CardDescription>Your last attempts and AI feedback summaries.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  {recentTasks.map((task) => (
                    <div key={task.id} className="flex items-center justify-between border-b border-border pb-4 last:border-0 last:pb-0">
                      <div className="flex items-center space-x-4">
                        <div className={`p-2 rounded-lg ${task.type === 'Writing' ? 'bg-blue-50 text-blue-500' : 'bg-teal-50 text-teal-500'}`}>
                          {task.type === 'Writing' ? <PenTool className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                        </div>
                        <div>
                          <p className="text-sm font-medium leading-none">{task.task}</p>
                          <p className="text-xs text-muted-foreground mt-1">{task.date}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        <Badge variant={task.score >= 7 ? "success" : "warning"}>
                          Band {task.score}
                        </Badge>
                        <Button variant="ghost" size="icon">
                          <ArrowRight className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right: Today's Tasks & Goals */}
          <div className="space-y-8">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Target className="mr-2 h-5 w-5 text-primary" />
                  Today&apos;s Tasks
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <TaskItem title="Complete 1 Writing Task 2" time="40 mins" done={false} />
                  <TaskItem title="Vocabulary: Education" time="15 mins" done={true} />
                  <TaskItem title="Speaking Part 1 Drill" time="10 mins" done={false} />
                </div>
                <Button className="w-full mt-6" variant="outline">
                  View Full Roadmap
                </Button>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-slate-900 to-slate-800 text-white">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold">Daily Goal</h3>
                  <Clock className="h-4 w-4 text-accent" />
                </div>
                <div className="text-3xl font-bold mb-1">45 / 60</div>
                <p className="text-xs text-slate-400 mb-4">minutes studied today</p>
                <Progress value={75} className="h-2 bg-slate-700" variant="accent" />
              </CardContent>
            </Card>
          </div>

        </div>
      </div>
    </DashboardLayout>
  );
}

// Helper component for tasks
const TaskItem = ({ title, time, done }: { title: string, time: string, done: boolean }) => (
  <div className="flex items-start space-x-3">
    <div className={`mt-0.5 h-5 w-5 shrink-0 rounded-full border-2 flex items-center justify-center ${done ? 'bg-success border-success text-white' : 'border-muted-foreground/30'}`}>
      {done && <CheckCircle2 className="h-3 w-3" />}
    </div>
    <div className="flex-1">
      <p className={`text-sm font-medium ${done ? 'text-muted-foreground line-through' : 'text-foreground'}`}>
        {title}
      </p>
      <p className="text-xs text-muted-foreground">{time}</p>
    </div>
  </div>
);