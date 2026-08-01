"use client";

import React from "react";
import { 
  Lock, 
  Bell, 
  Eye, 
  Moon, 
  Sun, 
  Trash2, 
  ShieldCheck
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export default function SettingsPage() {
  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Page Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">Manage your account security and preferences.</p>
        </div>

        <div className="grid gap-8">
          
          {/* 1. Security & Password */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lock className="h-5 w-5 text-primary" /> Security
              </CardTitle>
              <CardDescription>Update your password and secure your account.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">New Password</label>
                  <Input type="password" placeholder="••••••••" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Confirm New Password</label>
                  <Input type="password" placeholder="••••••••" />
                </div>
              </div>
              <div className="flex justify-end pt-2">
                <Button size="sm">Update Password</Button>
              </div>
              <hr className="border-border my-4" />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg text-primary">
                    <ShieldCheck className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">Two-Factor Authentication</p>
                    <p className="text-xs text-muted-foreground">Add an extra layer of security to your account.</p>
                  </div>
                </div>
                <Badge variant="outline">Coming Soon</Badge>
              </div>
            </CardContent>
          </Card>

          {/* 2. Notifications */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="h-5 w-5 text-primary" /> Notifications
              </CardTitle>
              <CardDescription>Control how you receive updates and reminders.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <SettingToggle 
                title="Email Reminders" 
                description="Receive daily study reminders to hit your band goals." 
                defaultChecked={true} 
              />
              <SettingToggle 
                title="AI Feedback Alerts" 
                description="Get notified immediately when your essay grading is ready." 
                defaultChecked={true} 
              />
              <SettingToggle 
                title="Marketing & Tips" 
                description="Stay updated with new IELTS strategies and feature releases." 
                defaultChecked={false} 
              />
            </CardContent>
          </Card>

          {/* 3. Appearance */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-primary" /> Appearance
              </CardTitle>
              <CardDescription>Customize the look of your dashboard.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Theme Mode</p>
                  <p className="text-xs text-muted-foreground">Switch between light and dark themes.</p>
                </div>
                <div className="flex items-center p-1 bg-secondary rounded-lg border border-border">
                  <button className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-md bg-background shadow-sm">
                    <Sun className="h-4 w-4" /> Light
                  </button>
                  <button className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-md text-muted-foreground hover:text-foreground">
                    <Moon className="h-4 w-4" /> Dark
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 4. Danger Zone */}
          <Card className="border-error/20 bg-error/5">
            <CardHeader>
              <CardTitle className="text-error flex items-center gap-2">
                <Trash2 className="h-5 w-5" /> Danger Zone
              </CardTitle>
              <CardDescription>Irreversible actions related to your data.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold">Delete Account</p>
                  <p className="text-xs text-muted-foreground max-w-sm">
                    Once you delete your account, all your progress, history, and AI evaluations will be permanently removed.
                  </p>
                </div>
                <Button variant="destructive" size="sm">Delete Forever</Button>
              </div>
            </CardContent>
          </Card>

        </div>
      </div>
    </DashboardLayout>
  );
}

// Helper component for toggles
const SettingToggle = ({ title, description, defaultChecked }: { title: string, description: string, defaultChecked: boolean }) => (
  <div className="flex items-center justify-between py-2">
    <div className="space-y-0.5">
      <p className="text-sm font-medium">{title}</p>
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
    <div className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ring-offset-background ${defaultChecked ? 'bg-primary' : 'bg-slate-200'}`}>
      <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${defaultChecked ? 'translate-x-5' : 'translate-x-0'}`} />
    </div>
  </div>
);