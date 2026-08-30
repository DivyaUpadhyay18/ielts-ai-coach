"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Plus,
  ThumbsUp,
  FileText,
  Video,
  Globe,
  HelpCircle,
  Layers,
  Link2,
  AlertCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Tag,
  Award,
  Coins,
  ExternalLink,
  ShieldCheck,
  MessageSquare,
  List,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { resourcesService } from "@/services/api";
import type { Category, ResourceSuggestion, ResourceSuggestionCreatePayload } from "@/types/admin";
import type { ResourceSkill, ResourceDifficulty } from "@/types";

const CATEGORIES: Category[] = [
  "YouTube Video",
  "PDF",
  "Website",
  "Practice Test",
  "Vocabulary List",
];

const ALL_SKILLS: ResourceSkill[] = ["Reading", "Listening", "Writing", "Speaking", "Vocabulary", "Grammar"];
const ALL_DIFFICULTIES: ResourceDifficulty[] = ["beginner", "intermediate", "advanced", "all_levels"];

const CATEGORY_META: Record<Category, { icon: React.ElementType; color: string; bg: string }> = {
  "YouTube Video": { icon: Video, color: "text-red-600", bg: "bg-red-100" },
  PDF: { icon: FileText, color: "text-blue-600", bg: "bg-blue-100" },
  Website: { icon: Globe, color: "text-green-600", bg: "bg-green-100" },
  "Practice Test": { icon: HelpCircle, color: "text-purple-600", bg: "bg-purple-100" },
  "Vocabulary List": { icon: Layers, color: "text-amber-600", bg: "bg-amber-100" },
};

const STATUS_META: Record<string, { color: string; bg: string; icon: React.ElementType; label: string }> = {
  pending: { color: "text-amber-700", bg: "bg-amber-50", icon: Clock, label: "Pending Review" },
  approved: { color: "text-emerald-700", bg: "bg-emerald-50", icon: CheckCircle2, label: "Approved" },
  rejected: { color: "text-red-700", bg: "bg-red-50", icon: XCircle, label: "Rejected" },
};

const CATEGORY_TYPE_MAP: Record<Category, string> = {
  "YouTube Video": "Video",
  PDF: "PDF",
  Website: "Website",
  "Practice Test": "Quiz",
  "Vocabulary List": "Flashcard",
};

export default function SuggestPage() {
  // Form state
  const [form, setForm] = useState<ResourceSuggestionCreatePayload>({
    title: "",
    description: "",
    category: "Website",
    reason: "",
    type: "Website",
    url: "",
    skill: "Reading",
    difficulty: "intermediate",
    estimated_time: 15,
    tags: [],
    is_free: true,
  });
  const [tagsInput, setTagsInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  // My suggestions
  const [mySuggestions, setMySuggestions] = useState<ResourceSuggestion[]>([]);
  const [loadingMine, setLoadingMine] = useState(false);

  // Community suggestions
  const [community, setCommunity] = useState<ResourceSuggestion[]>([]);
  const [loadingCommunity, setLoadingCommunity] = useState(false);
  const [communityError, setCommunityError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("");

  const fetchMySuggestions = useCallback(async () => {
    setLoadingMine(true);
    try {
      const data = await resourcesService.getMySuggestions({ limit: 50 });
      setMySuggestions(data || []);
    } catch {
      setMySuggestions([]);
    } finally {
      setLoadingMine(false);
    }
  }, []);

  const fetchCommunity = useCallback(async () => {
    setLoadingCommunity(true);
    setCommunityError(null);
    try {
      const data = await resourcesService.getCommunitySuggestions({
        category: categoryFilter || undefined,
        limit: 50,
      });
      setCommunity(data || []);
    } catch (err: any) {
      setCommunityError(err?.response?.data?.detail || err?.message || "Failed to load community suggestions");
      setCommunity([]);
    } finally {
      setLoadingCommunity(false);
    }
  }, [categoryFilter]);

  useEffect(() => {
    fetchMySuggestions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchCommunity();
  }, [fetchCommunity]);

  const handleCategoryChange = (category: Category) => {
    setForm((prev) => ({
      ...prev,
      category,
      type: CATEGORY_TYPE_MAP[category],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(false);
    try {
      const tags = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
      await resourcesService.submitSuggestion({
        ...form,
        tags,
      });
      setSubmitSuccess(true);
      // Reset form
      setForm({
        title: "",
        description: "",
        category: "Website",
        reason: "",
        type: "Website",
        url: "",
        skill: "Reading",
        difficulty: "intermediate",
        estimated_time: 15,
        tags: [],
        is_free: true,
      });
      setTagsInput("");
      await fetchMySuggestions();
    } catch (err: any) {
      setSubmitError(err?.response?.data?.detail || err?.message || "Failed to submit suggestion");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVote = async (suggestion: ResourceSuggestion) => {
    try {
      if (suggestion.voted) {
        await resourcesService.unvoteSuggestion(suggestion.id);
      } else {
        await resourcesService.voteSuggestion(suggestion.id);
      }
      setCommunity((prev) =>
        prev.map((s) => (s.id === suggestion.id ? { ...s, voted: !s.voted, votes: s.votes + (s.voted ? -1 : 1) } : s))
      );
    } catch {
      // Silently fail on vote errors
    }
  };

  // Summary stats
  const stats = useMemo(() => ({
    total: mySuggestions.length,
    pending: mySuggestions.filter((s) => s.status === "pending").length,
    approved: mySuggestions.filter((s) => s.status === "approved").length,
    rejected: mySuggestions.filter((s) => s.status === "rejected").length,
  }), [mySuggestions]);

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary to-accent p-6 md:p-8 text-white">
          <div className="absolute -top-12 -right-12 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
          <div className="absolute -bottom-8 -left-8 h-32 w-32 rounded-full bg-white/10 blur-2xl" />
          <div className="relative z-10">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Sparkles className="h-8 w-8" />
              Community Resources
            </h1>
            <p className="text-white/80 text-sm md:text-base mt-1">
              Share useful IELTS resources with the community. Suggestions go through moderation before going live.
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">My Suggestions</p>
              <p className="text-3xl font-bold mt-1">{stats.total}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground flex items-center gap-1"><Clock className="h-3 w-3" /> Pending</p>
              <p className="text-3xl font-bold mt-1 text-amber-600">{stats.pending}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> Approved</p>
              <p className="text-3xl font-bold mt-1 text-emerald-600">{stats.approved}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground flex items-center gap-1"><XCircle className="h-3 w-3" /> Rejected</p>
              <p className="text-3xl font-bold mt-1 text-red-600">{stats.rejected}</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* ─── Submit Form ─────────────────────────────────── */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5 text-primary" />
                Suggest a Resource
              </CardTitle>
              <CardDescription>
                Share a YouTube video, PDF, website, practice test, or vocabulary list.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {submitSuccess && (
                <div className="mb-4 flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-emerald-700 text-sm">
                  <CheckCircle2 className="h-4 w-4" />
                  Suggestion submitted! It will be reviewed by our team.
                </div>
              )}
              {submitError && (
                <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-red-700 text-sm">
                  <AlertCircle className="h-4 w-4" />
                  {submitError}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Category */}
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Category *</label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-1">
                    {CATEGORIES.map((cat) => {
                      const meta = CATEGORY_META[cat];
                      const Icon = meta.icon;
                      const active = form.category === cat;
                      return (
                        <button
                          key={cat}
                          type="button"
                          onClick={() => handleCategoryChange(cat)}
                          className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-2 text-xs font-medium transition-all ${
                            active
                              ? "border-primary bg-primary/5 text-primary"
                              : "border-input hover:border-primary/30 hover:bg-muted/50"
                          }`}
                        >
                          <Icon className={`h-3.5 w-3.5 ${active ? meta.color : "text-muted-foreground"}`} />
                          {cat}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Title */}
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Title *</label>
                  <Input
                    value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                    placeholder="e.g. IELTS Speaking Part 2 Practice Video"
                    required
                    className="mt-1"
                  />
                </div>

                {/* URL */}
                <div>
                  <label className="text-xs font-medium text-muted-foreground">URL *</label>
                  <div className="relative mt-1">
                    <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      value={form.url || ""}
                      onChange={(e) => setForm({ ...form, url: e.target.value })}
                      placeholder="https://..."
                      className="pl-9"
                    />
                  </div>
                </div>

                {/* Reason */}
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Why is this resource valuable? *</label>
                  <textarea
                    value={form.reason || ""}
                    onChange={(e) => setForm({ ...form, reason: e.target.value })}
                    placeholder="Explain why this resource would help other IELTS learners..."
                    required
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[80px]"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Description</label>
                  <textarea
                    value={form.description || ""}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    placeholder="Brief description of the resource..."
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[60px]"
                  />
                </div>

                {/* Skill + Difficulty */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">Skill *</label>
                    <select
                      value={form.skill}
                      onChange={(e) => setForm({ ...form, skill: e.target.value as ResourceSkill })}
                      className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    >
                      {ALL_SKILLS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">Difficulty</label>
                    <select
                      value={form.difficulty}
                      onChange={(e) => setForm({ ...form, difficulty: e.target.value as ResourceDifficulty })}
                      className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    >
                      {ALL_DIFFICULTIES.map((d) => (
                        <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Estimated time + tags */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">Estimated Time (min)</label>
                    <Input
                      type="number"
                      min={0}
                      value={form.estimated_time || 0}
                      onChange={(e) => setForm({ ...form, estimated_time: parseInt(e.target.value) || 0 })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">Tags (comma-separated)</label>
                    <Input
                      value={tagsInput}
                      onChange={(e) => setTagsInput(e.target.value)}
                      placeholder="ielts, speaking, part2"
                      className="mt-1"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.is_free}
                      onChange={(e) => setForm({ ...form, is_free: e.target.checked })}
                      className="h-4 w-4"
                    />
                    Free resource
                  </label>
                  <Button type="submit" disabled={submitting}>
                    {submitting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
                    Submit for Review
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* ─── My Suggestions ──────────────────────────────── */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <List className="h-5 w-5 text-primary" />
                My Suggestions
              </CardTitle>
              <CardDescription>Track the status of your submissions.</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingMine ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : mySuggestions.length === 0 ? (
                <div className="py-12 text-center space-y-3">
                  <MessageSquare className="h-8 w-8 text-muted-foreground mx-auto" />
                  <p className="text-muted-foreground text-sm">You haven&apos;t submitted any suggestions yet.</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[calc(100vh-24rem)] overflow-y-auto pr-1">
                  {mySuggestions.map((s) => {
                    const catMeta = CATEGORY_META[s.category] || CATEGORY_META.Website;
                    const statusMeta = STATUS_META[s.status] || STATUS_META.pending;
                    const CatIcon = catMeta.icon;
                    const StatusIcon = statusMeta.icon;
                    return (
                      <div key={s.id} className="rounded-lg border border-border p-3 hover:bg-muted/30 transition-colors">
                        <div className="flex items-start gap-2">
                          <span className={`p-1.5 rounded-lg ${catMeta.bg} ${catMeta.color}`}>
                            <CatIcon className="h-3.5 w-3.5" />
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="font-medium text-sm truncate">{s.title}</p>
                              <Badge variant="outline" className={`${statusMeta.bg} ${statusMeta.color} border-0 text-[10px]`}>
                                <StatusIcon className="h-3 w-3 mr-1" />
                                {statusMeta.label}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-1">
                              <span>{s.category}</span>
                              <span>• {s.skill}</span>
                              <span className="inline-flex items-center gap-0.5">
                                <ThumbsUp className="h-3 w-3" /> {s.votes ?? 0}
                              </span>
                              {s.created_at && <span>• {new Date(s.created_at).toLocaleDateString()}</span>}
                            </div>
                            {s.admin_notes && (
                              <p className="text-[11px] text-muted-foreground mt-1.5 italic">
                                Review note: {s.admin_notes}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ─── Community Suggestions (Approved) ──────────────── */}
        <Card>
          <CardHeader>
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <ThumbsUp className="h-5 w-5 text-primary" />
                  Community Picks
                </CardTitle>
                <CardDescription>
                  Approved suggestions from the community. Vote for the ones you find most useful.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                <button
                  onClick={() => setCategoryFilter("")}
                  className={`whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
                    categoryFilter === "" ? "bg-primary text-primary-foreground" : "bg-muted/50 hover:bg-muted"
                  }`}
                >
                  All
                </button>
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setCategoryFilter(categoryFilter === cat ? "" : cat)}
                    className={`whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
                      categoryFilter === cat ? "bg-primary text-primary-foreground" : "bg-muted/50 hover:bg-muted"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {communityError && (
              <div className="flex items-center gap-3 rounded-xl border border-error/30 bg-error/5 p-4 text-error">
                <AlertCircle className="h-5 w-5" />
                <p className="text-sm font-medium flex-1">{communityError}</p>
                <Button variant="ghost" size="sm" onClick={fetchCommunity}><RefreshCw className="h-4 w-4 mr-1" /> Retry</Button>
              </div>
            )}
            {loadingCommunity ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : community.length === 0 && !communityError ? (
              <div className="py-12 text-center space-y-3">
                <ThumbsUp className="h-8 w-8 text-muted-foreground mx-auto" />
                <p className="text-muted-foreground text-sm">No approved suggestions yet. Be the first to contribute!</p>
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {community.map((s) => {
                  const catMeta = CATEGORY_META[s.category] || CATEGORY_META.Website;
                  const CatIcon = catMeta.icon;
                  return (
                    <div key={s.id} className="rounded-lg border border-border p-4 hover:shadow-md transition-shadow">
                      <div className="flex items-start gap-3">
                        <span className={`p-2 rounded-lg ${catMeta.bg} ${catMeta.color}`}>
                          <CatIcon className="h-4 w-4" />
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-semibold text-sm">{s.title}</h3>
                            <Badge variant="outline" className="text-[10px]">{s.category}</Badge>
                            <Badge variant="outline" className="text-[10px]">{s.skill}</Badge>
                          </div>
                          {s.description && (
                            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{s.description}</p>
                          )}
                          {s.reason && (
                            <p className="text-[11px] text-muted-foreground mt-1.5 italic line-clamp-2">
                              💡 {s.reason}
                            </p>
                          )}
                          <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-2">
                            <span className="inline-flex items-center gap-0.5">
                              <ThumbsUp className="h-3 w-3" /> {s.votes ?? 0} votes
                            </span>
                            {s.estimated_time && <span>• {s.estimated_time}m</span>}
                            {s.is_free && (
                              <span className="inline-flex items-center gap-0.5 text-green-600">
                                <Coins className="h-3 w-3" /> Free
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-col items-center gap-2 shrink-0">
                          <Button
                            variant={s.voted ? "default" : "outline"}
                            size="sm"
                            className="h-8 min-w-[64px]"
                            onClick={() => handleVote(s)}
                          >
                            <ThumbsUp className={`h-3.5 w-3.5 mr-1 ${s.voted ? "fill-current" : ""}`} />
                            {s.voted ? "Voted" : "Vote"}
                          </Button>
                          {s.url && (
                            <a
                              href={s.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[11px] text-primary hover:underline inline-flex items-center gap-0.5"
                            >
                              <ExternalLink className="h-3 w-3" /> Visit
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
