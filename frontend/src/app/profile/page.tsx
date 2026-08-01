"use client";

import React from "react";
import { 
  User, 
  Mail, 
  Calendar, 
  Target, 
  Clock, 
  Camera,
  Save,
  Globe
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

export default function ProfilePage() {
  // Mock User Data
  const user = {
    name: "Alex Thompson",
    email: "alex.t@example.com",
    avatar: null, // Testing fallback initials
    targetBand: 7.5,
    examDate: "2024-12-15",
    studyHours: 2,
    location: "United Kingdom"
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
  };

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Profile Settings</h1>
          <p className="text-muted-foreground">Manage your personal information and IELTS goals.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          <div className="grid gap-8 md:grid-cols-3">
            
            {/* Left Column: Photo & Basic Info */}
            <div className="space-y-6">
              <Card>
                <CardContent className="pt-6 flex flex-col items-center text-center">
                  <div className="relative group cursor-pointer">
                    <Avatar 
                      size="xl" 
                      fallback={user.name} 
                      className="ring-4 ring-background shadow-lg"
                    />
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                      <Camera className="text-white h-6 w-6" />
                    </div>
                  </div>
                  <h2 className="mt-4 text-xl font-bold">{user.name}</h2>
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                  <div className="mt-4 flex flex-wrap justify-center gap-2">
                    <Badge variant="secondary">Free Tier</Badge>
                    <Badge variant="outline" className="flex items-center gap-1">
                      <Globe className="h-3 w-3" /> {user.location}
                    </Badge>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Account Status</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Joined:</span>
                    <span className="font-medium">Nov 2023</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Status:</span>
                    <span className="text-success font-medium">Active</span>
                  </div>
                  <Button variant="outline" className="w-full text-xs h-8">
                    View Billing
                  </Button>
                </CardContent>
              </Card>
            </div>

            {/* Right Column: Personal Details & Goals */}
            <div className="md:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Personal Details</CardTitle>
                  <CardDescription>How we should address you in the app.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" /> Full Name
                      </label>
                      <Input defaultValue={user.name} />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-2">
                        <Mail className="h-4 w-4 text-muted-foreground" /> Email Address
                      </label>
                      <Input defaultValue={user.email} disabled />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>IELTS Exam Goals</CardTitle>
                  <CardDescription>The AI uses these to personalize your coaching.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid gap-6 sm:grid-cols-2">
                    {/* Target Band */}
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-2">
                        <Target className="h-4 w-4 text-primary" /> Target Band Score
                      </label>
                      <div className="flex items-center gap-4">
                        <Input 
                          type="number" 
                          step="0.5" 
                          min="0" 
                          max="9" 
                          defaultValue={user.targetBand} 
                          className="w-24"
                        />
                        <Badge variant="accent" className="h-10 px-4">
                          Band {user.targetBand}
                        </Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground italic">Most universities require 6.5 or 7.0</p>
                    </div>

                    {/* Exam Date */}
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-primary" /> Planned Exam Date
                      </label>
                      <Input type="date" defaultValue={user.examDate} />
                    </div>

                    {/* Daily Commitment */}
                    <div className="space-y-2 sm:col-span-2">
                      <label className="text-sm font-medium flex items-center gap-2">
                        <Clock className="h-4 w-4 text-primary" /> Daily Study Commitment
                      </label>
                      <div className="flex items-center gap-4">
                        <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
                          <option value="1">1 hour per day</option>
                          <option value="2">2 hours per day</option>
                          <option value="3">3+ hours per day</option>
                          <option value="0.5">30 mins (Casual)</option>
                        </select>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-4">
                <Button variant="ghost" type="button">Cancel</Button>
                <Button className="px-8" type="submit">
                  <Save className="mr-2 h-4 w-4" /> Save All Changes
                </Button>
              </div>
            </div>

          </div>
        </form>
      </div>
    </DashboardLayout>
  );
}