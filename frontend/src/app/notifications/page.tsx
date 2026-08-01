"use client";

import React, { useState } from "react";
import { 
  Bell, 
  Sparkles, 
  Calendar, 
  Settings, 
  CheckCheck, 
  Trash2, 
  Zap,
  Clock
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function NotificationsPage() {
  const [activeTab, setActiveTab] = useState("all");

  // Mock Notifications Data
  const notifications = [
    {
      id: 1,
      type: "ai",
      title: "AI Evaluation Ready",
      description: "Your essay on 'Environmental Protection' has been graded. You achieved an estimated Band 7.0!",
      time: "10 mins ago",
      isRead: false,
    },
    {
      id: 2,
      type: "reminder",
      title: "Daily Practice Reminder",
      description: "Don't forget your Speaking Part 2 drill today to maintain your 5-day streak.",
      time: "2 hours ago",
      isRead: false,
    },
    {
      id: 3,
      type: "system",
      title: "New Feature: Vocabulary Flashcards",
      description: "We've added 500+ new academic words to our resource library. Check them out!",
      time: "Yesterday",
      isRead: true,
    },
    {
      id: 4,
      type: "ai",
      title: "Speaking Analysis Complete",
      description: "Great improvement in your fluency! Click to see your detailed pronunciation feedback.",
      time: "2 days ago",
      isRead: true,
    },
  ];

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Header Area */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Bell className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Notifications</h1>
              <p className="text-muted-foreground">Stay updated with your AI Coach and exam progress.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <CheckCheck className="mr-2 h-4 w-4" /> Mark all as read
            </Button>
            <Button variant="ghost" size="icon">
              <Settings className="h-5 w-5 text-muted-foreground" />
            </Button>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-2 border-b border-border pb-4">
          <button 
            onClick={() => setActiveTab("all")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'all' ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-secondary'}`}
          >
            All
          </button>
          <button 
            onClick={() => setActiveTab("ai")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'ai' ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-secondary'}`}
          >
            AI Feedback
          </button>
          <button 
            onClick={() => setActiveTab("reminder")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'reminder' ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-secondary'}`}
          >
            Reminders
          </button>
        </div>

        {/* Notifications List */}
        <div className="space-y-4">
          {notifications.length > 0 ? (
            notifications
              .filter(n => activeTab === 'all' || n.type === activeTab)
              .map((notification) => (
              <Card 
                key={notification.id} 
                className={`transition-all border-l-4 ${!notification.isRead ? 'border-l-primary bg-primary/5' : 'border-l-transparent'}`}
              >
                <CardContent className="p-4 flex items-start gap-4">
                  {/* Icon Based on Type */}
                  <div className={`p-2 rounded-full shrink-0 ${
                    notification.type === 'ai' ? 'bg-purple-100 text-purple-600' : 
                    notification.type === 'reminder' ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'
                  }`}>
                    {notification.type === 'ai' ? <Sparkles className="h-5 w-5" /> : 
                     notification.type === 'reminder' ? <Calendar className="h-5 w-5" /> : <Zap className="h-5 w-5" />}
                  </div>

                  {/* Content */}
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <h3 className={`text-sm font-bold ${!notification.isRead ? 'text-foreground' : 'text-muted-foreground'}`}>
                        {notification.title}
                      </h3>
                      <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" /> {notification.time}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {notification.description}
                    </p>
                    
                    {!notification.isRead && (
                      <div className="pt-2">
                        <Button variant="link" className="p-0 h-auto text-xs text-primary">
                          View Details
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col gap-2">
                    {!notification.isRead && (
                      <div className="h-2 w-2 rounded-full bg-primary self-center" />
                    )}
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-error">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <div className="text-center py-20 bg-slate-50 rounded-2xl border-2 border-dashed border-border">
              <div className="mx-auto h-12 w-12 rounded-full bg-white flex items-center justify-center shadow-sm mb-4">
                <CheckCheck className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-medium">All caught up!</h3>
              <p className="text-muted-foreground">You have no new notifications.</p>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex justify-center pt-4">
          <Button variant="ghost" className="text-muted-foreground text-xs">
            Show older notifications
          </Button>
        </div>
      </div>
    </DashboardLayout>
  );
}