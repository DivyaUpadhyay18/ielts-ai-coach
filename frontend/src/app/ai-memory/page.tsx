"use client";

import React, {useCallback, useEffect, useState} from "react";
import {
  BookOpen,
  RefreshCw,
  AlertCircle,
  Loader2,
  Brain,
  Trophy,
  CheckCircle2,
  AlertTriangle,
  Target,
  Clock,
  User,
  Search,
} from "lucide-react";
import {DashboardLayout} from "@/components/layouts/dashboard-layout";
import {Card, CardContent, CardHeader, CardTitle, CardDescription} from "@/components/ui/card";
import {Button} from "@/components/ui/button";
import {Badge} from "@/components/ui/badge";
import {Skeleton} from "@/components/ui/skeleton";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {mentorMemoryService} from "@/services/api";
import type {MentorMemoryProfile, MentorMemoryEntry, MemoryTypeSchema, ExtractionResult} from "@/types";

const MEMORY_TYPE_COLORS: Record<string, { color: string; icon: React.ElementType }> = {
  recurring_mistake: { color: "border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-300", icon: AlertTriangle },
  faq: { color: "border-blue-500/30 bg-blue-500/5 text-blue-700 dark:text-blue-300", icon: BookOpen },
  weak_grammar: { color: "border-orange-500/30 bg-orange-500/5 text-orange-700 dark:text-orange-300", icon: Target },
  weak_vocabulary: { color: "border-purple-500/30 bg-purple-500/5 text-purple-700 dark:text-purple-300", icon: BookOpen },
  learning_preference: { color: "border-indigo-500/30 bg-indigo-500/5 text-indigo-700 dark:text-indigo-300", icon: User },
  motivation_style: { color: "border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-300", icon: Trophy },
  conversation_insight: { color: "border-teal-500/30 bg-teal-500/5 text-teal-700 dark:text-teal-300", icon: Brain },
};

function ConfidenceBadge({confidence}: {confidence: number}) {
  const pct = Math.round(confidence * 100);
  const colorClass = confidence >= 0.8
    ? "bg-green-100 text-green-800 dark:bg-green-900/30"
    : confidence >= 0.6
    ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30"
    : "bg-gray-100 text-gray-800 dark:bg-gray-900/30";
  return (
    <Badge className={`text-xs ${colorClass}`}>
      {pct}% confidence
    </Badge>
  );
}

function MemoryCard({memory}: {memory: MentorMemoryEntry}) {
  const style = MEMORY_TYPE_COLORS[memory.memory_type] || MEMORY_TYPE_COLORS.conversation_insight;
  const Icon = style.icon;

  return (
    <div className={`border rounded-xl p-4 ${style.color} transition-all hover:shadow-sm`}>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 p-2 bg-white/50 dark:bg-gray-800/50 rounded-lg">
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium break-words">{memory.content}</p>
            <ConfidenceBadge confidence={memory.confidence} />
          </div>
          {(memory.category || memory.subcategory) && (
            <div className="flex flex-wrap gap-1 mt-2">
              {memory.category && (
                <Badge variant="outline" className="text-xs">
                  {memory.category}
                </Badge>
              )}
              {memory.subcategory && (
                <Badge variant="outline" className="text-xs">
                  {memory.subcategory}
                </Badge>
              )}
            </div>
          )}
          {memory.structured_data && Object.keys(memory.structured_data).length > 0 && (
            <div className="mt-2 text-xs text-muted-foreground">
              {Object.entries(memory.structured_data).slice(0, 3).map(([key, value]) => (
                <span key={key} className="mr-3">
                  {key}: {String(value)}
                </span>
              ))}
            </div>
          )}
          <div className="mt-2 text-xs text-muted-foreground">
            Weight: {memory.weight} • Accessed: {memory.accessed_count}x
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AiMemoryPage() {
  const [profile, setProfile] = useState<MentorMemoryProfile | null>(null);
  const [memories, setMemories] = useState<MentorMemoryEntry[]>([]);
  const [types, setTypes] = useState<MemoryTypeSchema[]>([]);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileData, typesData] = await Promise.all([
        mentorMemoryService.getProfile(),
        mentorMemoryService.getMemoryTypes(),
      ]);
      setProfile(profileData);
      setTypes(typesData as MemoryTypeSchema[]);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail?.message ||
        err?.message ||
        "Failed to load memory profile"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const handleExtract = async () => {
    setExtracting(true);
    setError(null);
    try {
      const result = await mentorMemoryService.extractMemories(true);
      await fetchProfile();
      // Show result briefly.
      const resultMsg = `Extracted: ${result.memories_added} new, ${result.memories_updated} updated`;
      console.log("Extraction result:", resultMsg);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail?.message ||
        err?.message ||
        "Failed to extract memories"
      );
    } finally {
      setExtracting(false);
    }
  };

  const fetchMemoriesByType = useCallback(async (memoryType: string) => {
    try {
      const data = await mentorMemoryService.listMemories({memory_type: memoryType});
      setMemories(data);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail?.message ||
        err?.message ||
        "Failed to load memories"
      );
    }
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  useEffect(() => {
    if (activeTab !== "overview" && activeTab !== "formulas") {
      void fetchMemoriesByType(activeTab);
    }
  }, [activeTab, fetchMemoriesByType]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6 pb-12">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-80" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-32 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="flex items-center gap-3 rounded-xl border border-error/30 bg-error/5 p-4 text-error">
          <AlertCircle className="h-5 w-5" />
          <p className="text-sm font-medium flex-1">{error}</p>
          <Button variant="ghost" size="sm" onClick={fetchProfile}>
            Retry
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  if (!profile) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <Brain className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">No memory profile available yet.</p>
          <Button onClick={handleExtract} className="mt-4">
            Extract Memories
          </Button>
        </div>
      </DashboardLayout>
    );
  }

        const memorySections: Array<{ key: string; label: string; icon: React.ElementType; data: MentorMemoryEntry[] }> = [];

  if (profile.recurring_mistakes.length > 0) {
    memorySections.push({
      key: "recurring_mistakes",
      label: "Recurring Mistakes",
      icon: AlertTriangle,
      data: profile.recurring_mistakes,
    });
  }
  if (profile.faqs.length > 0) {
    memorySections.push({
      key: "faqs",
      label: "Frequently Asked Questions",
      icon: BookOpen,
      data: profile.faqs,
    });
  }
  if (profile.weak_grammar.length > 0) {
    memorySections.push({
      key: "weak_grammar",
      label: "Weak Grammar Topics",
      icon: Target,
      data: profile.weak_grammar,
    });
  }
  if (profile.weak_vocabulary.length > 0) {
    memorySections.push({
      key: "weak_vocabulary",
      label: "Weak Vocabulary",
      icon: BookOpen,
      data: profile.weak_vocabulary,
    });
  }
  if (profile.learning_preferences.length > 0) {
    memorySections.push({
      key: "learning_preferences",
      label: "Learning Preferences",
      icon: User,
      data: profile.learning_preferences,
    });
  }
  if (profile.motivation_styles.length > 0) {
    memorySections.push({
      key: "motivation_styles",
      label: "Motivation Style",
      icon: Trophy,
      data: profile.motivation_styles,
    });
  }
  if (profile.conversation_insights.length > 0) {
    memorySections.push({
      key: "conversation_insights",
      label: "Conversation Insights",
      icon: Brain,
      data: profile.conversation_insights,
    });
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Brain className="h-8 w-8 text-primary" />
              AI Mentor Memory
            </h1>
            <p className="text-sm text-muted-foreground">
              {profile.total_memories} memory{profile.total_memories !== 1 ? "ies" : "y"} stored
            </p>
          </div>
          <Button onClick={handleExtract} disabled={extracting} variant="outline">
            {extracting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Extracting...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                Extract Memories
              </>
            )}
          </Button>
        </div>

        {/* Overview stats */}
        <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <StatCard title="Recurring Mistakes" value={profile.recurring_mistakes.length} icon={AlertTriangle} color="text-red-600" />
          <StatCard title="FAQs" value={profile.faqs.length} icon={BookOpen} color="text-blue-600" />
          <StatCard title="Weak Grammar" value={profile.weak_grammar.length} icon={Target} color="text-orange-600" />
          <StatCard title="Weak Vocabulary" value={profile.weak_vocabulary.length} icon={BookOpen} color="text-purple-600" />
          <StatCard title="Preferences" value={profile.learning_preferences.length} icon={User} color="text-indigo-600" />
          <StatCard title="Motivation" value={profile.motivation_styles.length} icon={Trophy} color="text-amber-600" />
        </div>

        {/* Memory sections */}
        {memorySections.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-8">
                <Brain className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground mb-2">
                  Your mentor memory is empty. Complete a diagnostic test or start a mentor session
                  to begin building your personalized profile.
                </p>
                <Button onClick={handleExtract} disabled={extracting}>
                  {extracting ? "Extracting..." : "Extract Memories Now"}
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          memorySections.map((section) => (
            <Card key={section.key}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <section.icon className="h-5 w-5" />
                  {section.label}
                </CardTitle>
                <CardDescription>
                  {section.data.length} memor{section.data.length === 1 ? "y" : "ies"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {section.data.map((memory) => (
                    <MemoryCard key={memory.id} memory={memory} />
                  ))}
                </div>
              </CardContent>
            </Card>
          ))
        )}

        {/* Skills summary */}
        {profile.weak_skills.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Target className="h-5 w-5 text-red-600" />
                Identified Weak Skills
              </CardTitle>
              <CardDescription>
                Skills the mentor should focus on
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {profile.weak_skills.map((skill) => (
                  <Badge key={skill} variant="destructive">
                    {skill}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Preferences */}
        {profile.preference_texts.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <User className="h-5 w-5 text-indigo-600" />
                Learning Preferences
              </CardTitle>
              <CardDescription>
                How you prefer to study
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {profile.preference_texts.map((pref, idx) => (
                  <div key={idx} className="flex items-center gap-2 p-2 bg-indigo-50/30 rounded-lg">
                    <User className="h-4 w-4 text-indigo-600" />
                    <p className="text-sm">{pref}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Motivation */}
        {profile.motivation_texts.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Trophy className="h-5 w-5 text-amber-600" />
                Motivation Style
              </CardTitle>
              <CardDescription>
                What drives your learning journey
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {profile.motivation_texts.map((mot, idx) => (
                  <div key={idx} className="flex items-center gap-2 p-2 bg-amber-50/30 rounded-lg">
                    <Trophy className="h-4 w-4 text-amber-600" />
                    <p className="text-sm">{mot}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Available memory types reference */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Search className="h-5 w-5 text-slate-600" />
              Memory Types
            </CardTitle>
            <CardDescription>
              Types of learner insights the AI mentor tracks
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {types.map((t) => (
                <div key={t.type} className="p-3 bg-secondary/30 rounded-lg border border-border">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{t.label}</span>
                    <Badge variant="outline" className="text-xs">
                      {t.type}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {t.description}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}

function StatCard({
  title, value, icon: Icon, color = "text-primary",
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  color?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-primary/10 ${color}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {title}
            </p>
            <p className="text-2xl font-bold">{value}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
