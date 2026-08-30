"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  AlertTriangle,
  Lightbulb,
  Edit3,
  Star,
  Shield,
  TrendingUp,
  Award,
  Target,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Send,
  Trash2,
  Gavel,
  Flag,
  ThumbsUp,
  Activity,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { resourceQualityService } from "@/services/api";
import type {
  ResourceFeedback,
  ResourceFeedbackCreate,
  FeedbackType,
  ResourceQualityScores,
  ModerationQueue,
  ResourceQualityStats,
  FeedbackStatus,
} from "@/types/resource-quality";

// ─── Constants ────────────────────────────────────────────────────────────────

const FEEDBACK_TYPE_META: Record<
  FeedbackType,
  { label: string; icon: React.ElementType; color: string; gradient: string; description: string }
> = {
  broken_link: {
    label: "Broken Link",
    icon: AlertTriangle,
    color: "text-red-500",
    gradient: "from-red-500 to-rose-600",
    description: "Report a broken or inaccessible link",
  },
  better_resource: {
    label: "Better Resource",
    icon: Lightbulb,
    color: "text-amber-500",
    gradient: "from-amber-500 to-orange-600",
    description: "Suggest a better alternative resource",
  },
  correction: {
    label: "Correction",
    icon: Edit3,
    color: "text-blue-500",
    gradient: "from-blue-500 to-indigo-600",
    description: "Suggest a correction to the resource details",
  },
  rating: {
    label: "Rate Resource",
    icon: Star,
    color: "text-purple-500",
    gradient: "from-purple-500 to-violet-600",
    description: "Rate this resource on a 1-5 scale",
  },
};

const STATUS_META: Record<FeedbackStatus, { label: string; color: string; bg: string; icon: React.ElementType }> = {
  pending: { label: "Pending", color: "text-amber-700", bg: "bg-amber-100", icon: Clock },
  approved: { label: "Approved", color: "text-green-700", bg: "bg-green-100", icon: CheckCircle2 },
  rejected: { label: "Rejected", color: "text-red-700", bg: "bg-red-100", icon: XCircle },
  resolved: { label: "Resolved", color: "text-blue-700", bg: "bg-blue-100", icon: CheckCircle2 },
  dismissed: { label: "Dismissed", color: "text-gray-700", bg: "bg-gray-100", icon: XCircle },
};

// ─── Helper Components ────────────────────────────────────────────────────────

function ScoreRing({ score, label, icon: Icon, gradient }: { score: number; label: string; icon: React.ElementType; gradient: string }) {
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-24 w-24">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeWidth="8" className="text-muted/20" />
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke="url(#gradient)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
          <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" className={`stop-${gradient.split("-")[1]}`} />
              <stop offset="100%" className={`stop-${gradient.split("-")[3]}`} />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <Icon className="h-4 w-4 text-muted-foreground mb-0.5" />
          <span className="text-xl font-bold">{Math.round(score)}</span>
        </div>
      </div>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
    </div>
  );
}

function ScoreBar({ score, label, icon: Icon, color }: { score: number; label: string; icon: React.ElementType; color: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 font-medium">
          <Icon className={`h-3.5 w-3.5 ${color}`} />
          {label}
        </span>
        <span className="font-bold">{score.toFixed(1)}/100</span>
      </div>
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${color.includes("red") ? "from-red-500 to-rose-600" : color.includes("amber") ? "from-amber-500 to-orange-600" : color.includes("blue") ? "from-blue-500 to-indigo-600" : "from-purple-500 to-violet-600"} transition-all duration-1000 ease-out`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

// ─── Feedback Form ────────────────────────────────────────────────────────────

function FeedbackForm({ resourceId, onSubmitted }: { resourceId: string; onSubmitted?: () => void }) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType>("broken_link");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [suggestedUrl, setSuggestedUrl] = useState("");
  const [suggestedTitle, setSuggestedTitle] = useState("");
  const [fieldName, setFieldName] = useState("");
  const [suggestedValue, setSuggestedValue] = useState("");
  const [reason, setReason] = useState("");
  const [rating, setRating] = useState(5);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(false);

    try {
      const data: ResourceFeedbackCreate = {
        resource_id: resourceId,
        feedback_type: feedbackType,
      };

      if (feedbackType === "broken_link") {
        data.title = title;
        data.description = description;
      } else if (feedbackType === "better_resource") {
        data.suggested_url = suggestedUrl;
        data.suggested_title = suggestedTitle;
        data.reason = reason || undefined;
      } else if (feedbackType === "correction") {
        data.field_name = fieldName;
        data.suggested_value = suggestedValue;
        data.reason = reason || undefined;
      } else if (feedbackType === "rating") {
        data.rating = rating;
      }

      await resourceQualityService.submitFeedback(data);
      setSuccess(true);
      // Reset form
      setTitle("");
      setDescription("");
      setSuggestedUrl("");
      setSuggestedTitle("");
      setFieldName("");
      setSuggestedValue("");
      setReason("");
      onSubmitted?.();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="border-2">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Flag className="h-4 w-4 text-primary" />
          Submit Feedback
        </CardTitle>
        <CardDescription className="text-xs">
          Help improve resource quality by reporting issues or suggesting improvements
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Feedback Type Selector */}
        <div className="grid grid-cols-2 gap-2">
          {(Object.keys(FEEDBACK_TYPE_META) as FeedbackType[]).map((type) => {
            const meta = FEEDBACK_TYPE_META[type];
            const Icon = meta.icon;
            const isActive = feedbackType === type;
            return (
              <button
                key={type}
                onClick={() => setFeedbackType(type)}
                className={`flex items-center gap-2 rounded-lg border p-2.5 text-left transition-all ${
                  isActive
                    ? "border-primary bg-primary/5"
                    : "border-input hover:border-primary/30 hover:bg-muted/50"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? meta.color : "text-muted-foreground"}`} />
                <div className="min-w-0">
                  <p className="text-xs font-semibold truncate">{meta.label}</p>
                  <p className="text-[10px] text-muted-foreground truncate">{meta.description}</p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Dynamic Form Fields */}
        <form onSubmit={handleSubmit} className="space-y-3">
          {feedbackType === "broken_link" && (
            <>
              <div>
                <label className="text-xs font-medium mb-1 block">Issue Title</label>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g., Video not loading"
                  required
                  maxLength={300}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe what's broken..."
                  required
                  maxLength={2000}
                  rows={3}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                />
              </div>
            </>
          )}

          {feedbackType === "better_resource" && (
            <>
              <div>
                <label className="text-xs font-medium mb-1 block">Suggested Resource URL</label>
                <Input
                  value={suggestedUrl}
                  onChange={(e) => setSuggestedUrl(e.target.value)}
                  placeholder="https://..."
                  required
                  type="url"
                  maxLength={2000}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Suggested Resource Title</label>
                <Input
                  value={suggestedTitle}
                  onChange={(e) => setSuggestedTitle(e.target.value)}
                  placeholder="Title of the better resource"
                  required
                  maxLength={300}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Reason (optional)</label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Why is this resource better?"
                  maxLength={2000}
                  rows={2}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                />
              </div>
            </>
          )}

          {feedbackType === "correction" && (
            <>
              <div>
                <label className="text-xs font-medium mb-1 block">Field to Correct</label>
                <Input
                  value={fieldName}
                  onChange={(e) => setFieldName(e.target.value)}
                  placeholder="e.g., title, description, url, skill"
                  required
                  maxLength={100}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Corrected Value</label>
                <textarea
                  value={suggestedValue}
                  onChange={(e) => setSuggestedValue(e.target.value)}
                  placeholder="The correct value..."
                  required
                  maxLength={2000}
                  rows={2}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Reason (optional)</label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Why does this need correction?"
                  maxLength={2000}
                  rows={2}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                />
              </div>
            </>
          )}

          {feedbackType === "rating" && (
            <div>
              <label className="text-xs font-medium mb-2 block">Your Rating</label>
              <div className="flex items-center gap-1">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    className="transition-all hover:scale-110 active:scale-95"
                  >
                    <Star
                      className={`h-8 w-8 ${
                        star <= rating ? "fill-amber-400 text-amber-400" : "text-gray-300"
                      }`}
                    />
                  </button>
                ))}
                <span className="ml-2 text-sm font-medium">{rating}/5</span>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 p-2.5 text-xs text-red-700">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              {error}
            </div>
          )}

          {success && (
            <div className="flex items-center gap-2 rounded-lg bg-green-50 p-2.5 text-xs text-green-700">
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
              Feedback submitted successfully! Thank you for helping improve resource quality.
            </div>
          )}

          <Button type="submit" disabled={submitting} className="w-full" size="sm">
            {submitting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <Send className="h-3.5 w-3.5 mr-1.5" />
                Submit Feedback
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

// ─── Quality Scores Display ──────────────────────────────────────────────────

function QualityScoresDisplay({ resourceId }: { resourceId: string }) {
  const [scores, setScores] = useState<ResourceQualityScores | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchScores = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await resourceQualityService.getScores(resourceId);
      setScores(data);
    } catch (err: any) {
      setError(err.message || "Failed to load quality scores");
    } finally {
      setLoading(false);
    }
  }, [resourceId]);

  useEffect(() => {
    fetchScores();
  }, [fetchScores]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-40" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-24 w-24 rounded-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!scores) return null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="h-4 w-4 text-primary" />
              Quality Scores
            </CardTitle>
            <CardDescription className="text-xs">
              Computed from ratings, views, completions, and feedback
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchScores}
            className="text-xs h-7"
          >
            <Activity className="h-3 w-3 mr-1" />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Score Rings */}
        <div className="grid grid-cols-4 gap-2">
          <ScoreRing score={scores.quality_score} label="Quality" icon={Shield} gradient="from-blue-500 to-indigo-600" />
          <ScoreRing score={scores.popularity_score} label="Popularity" icon={TrendingUp} gradient="from-amber-500 to-orange-600" />
          <ScoreRing score={scores.completion_score} label="Completion" icon={Target} gradient="from-green-500 to-emerald-600" />
          <ScoreRing score={scores.recommendation_score} label="Recommendation" icon={Award} gradient="from-purple-500 to-violet-600" />
        </div>

        {/* Component Breakdown */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 pt-2 border-t">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Avg Rating</span>
            <span className="font-medium">{scores.avg_rating.toFixed(1)} ({scores.rating_count})</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Views</span>
            <span className="font-medium">{scores.view_count}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Bookmarks</span>
            <span className="font-medium">{scores.bookmark_count}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Likes</span>
            <span className="font-medium">{scores.like_count}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Completions</span>
            <span className="font-medium">{scores.completion_count}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Broken Links</span>
            <span className="font-medium text-red-600">{scores.broken_link_count}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Feedback List ───────────────────────────────────────────────────────────

function FeedbackList({ resourceId }: { resourceId: string }) {
  const [feedback, setFeedback] = useState<ResourceFeedback[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchFeedback = useCallback(async () => {
    setLoading(true);
    try {
      const response = await resourceQualityService.listFeedback({
        resource_id: resourceId,
        limit: 20,
      });
      setFeedback(response.items);
    } catch {
      setFeedback([]);
    } finally {
      setLoading(false);
    }
  }, [resourceId]);

  useEffect(() => {
    fetchFeedback();
  }, [fetchFeedback]);

  const handleDelete = async (feedbackId: string) => {
    try {
      await resourceQualityService.deleteFeedback(feedbackId);
      setFeedback(feedback.filter((f) => f.id !== feedbackId));
    } catch {
      // Silently fail
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <ThumbsUp className="h-4 w-4 text-primary" />
          Your Feedback
          {feedback.length > 0 && (
            <Badge variant="secondary" className="text-xs">{feedback.length}</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {feedback.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-4">
            No feedback submitted yet. Use the form above to submit feedback.
          </p>
        ) : (
          feedback.map((item) => {
            const typeMeta = FEEDBACK_TYPE_META[item.feedback_type];
            const statusMeta = STATUS_META[item.status];
            const TypeIcon = typeMeta.icon;
            const StatusIcon = statusMeta.icon;

            return (
              <div
                key={item.id}
                className="flex items-start gap-2 rounded-lg border p-2.5 transition-colors hover:bg-muted/30"
              >
                <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${statusMeta.bg}`}>
                  <TypeIcon className={`h-3.5 w-3.5 ${typeMeta.color}`} />
                </div>
                <div className="flex-1 min-w-0 space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium truncate">
                      {item.title || item.suggested_title || typeMeta.label}
                    </span>
                    <Badge variant="outline" className={`text-[10px] h-4 px-1 ${statusMeta.bg} ${statusMeta.color} border-0`}>
                      <StatusIcon className="h-2.5 w-2.5 mr-0.5" />
                      {statusMeta.label}
                    </Badge>
                  </div>
                  {item.description && (
                    <p className="text-xs text-muted-foreground line-clamp-2">{item.description}</p>
                  )}
                  {item.suggested_url && (
                    <p className="text-xs text-muted-foreground truncate">
                      Suggests: {item.suggested_url}
                    </p>
                  )}
                  {item.field_name && (
                    <p className="text-xs text-muted-foreground">
                      Field: <span className="font-medium">{item.field_name}</span> → {item.suggested_value}
                    </p>
                  )}
                  {item.rating && (
                    <div className="flex items-center gap-0.5">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <Star
                          key={s}
                          className={`h-3 w-3 ${s <= item.rating! ? "fill-amber-400 text-amber-400" : "text-gray-300"}`}
                        />
                      ))}
                    </div>
                  )}
                  {item.admin_notes && (
                    <p className="text-xs text-blue-600 italic">Admin: {item.admin_notes}</p>
                  )}
                </div>
                {item.status === "pending" && (
                  <button
                    onClick={() => handleDelete(item.id)}
                    className="text-muted-foreground hover:text-red-500 transition-colors"
                    title="Withdraw feedback"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function ResourceQuality({ resourceId }: { resourceId: string }) {
  return (
    <div className="space-y-4">
      <QualityScoresDisplay resourceId={resourceId} />
      <FeedbackForm resourceId={resourceId} />
      <FeedbackList resourceId={resourceId} />
    </div>
  );
}

// ─── Admin Moderation Component ──────────────────────────────────────────────

export function ModerationPanel() {
  const [queue, setQueue] = useState<ModerationQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<ResourceQualityStats | null>(null);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    try {
      const [queueData, statsData] = await Promise.all([
        resourceQualityService.getModerationQueue({ limit: 50 }),
        resourceQualityService.getStats(),
      ]);
      setQueue(queueData);
      setStats(statsData);
    } catch {
      setQueue(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleModerate = async (feedbackId: string, action: any, notes?: string) => {
    try {
      await resourceQualityService.moderateFeedback(feedbackId, {
        action,
        admin_notes: notes,
      });
      fetchQueue();
    } catch {
      // Silently fail
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100">
                <Clock className="h-4 w-4 text-amber-600" />
              </div>
              <div>
                <p className="text-xl font-bold">{stats.pending_feedback}</p>
                <p className="text-xs text-muted-foreground">Pending</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-100">
                <AlertTriangle className="h-4 w-4 text-red-600" />
              </div>
              <div>
                <p className="text-xl font-bold">{stats.broken_link_reports}</p>
                <p className="text-xs text-muted-foreground">Broken Links</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
                <Edit3 className="h-4 w-4 text-blue-600" />
              </div>
              <div>
                <p className="text-xl font-bold">{stats.correction_suggestions}</p>
                <p className="text-xs text-muted-foreground">Corrections</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-100">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              </div>
              <div>
                <p className="text-xl font-bold">{stats.resolved_feedback}</p>
                <p className="text-xs text-muted-foreground">Resolved</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Moderation Queue */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Gavel className="h-5 w-5 text-primary" />
            Moderation Queue
          </CardTitle>
          <CardDescription>
            Review and moderate user-submitted feedback
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {queue && queue.items.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No feedback to moderate. All caught up! 🎉
            </p>
          ) : (
            queue?.items.map((item) => {
              const typeMeta = FEEDBACK_TYPE_META[item.feedback_type];
              const statusMeta = STATUS_META[item.status];
              const TypeIcon = typeMeta.icon;

              return (
                <div
                  key={item.id}
                  className="flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/30"
                >
                  <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${statusMeta.bg}`}>
                    <TypeIcon className={`h-4 w-4 ${typeMeta.color}`} />
                  </div>
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium">
                        {item.title || item.suggested_title || typeMeta.label}
                      </span>
                      <Badge variant="outline" className={`text-xs ${statusMeta.bg} ${statusMeta.color} border-0`}>
                        {statusMeta.label}
                      </Badge>
                      {item.priority === "high" || item.priority === "urgent" ? (
                        <Badge className="text-xs bg-red-500 text-white border-0">
                          {item.priority}
                        </Badge>
                      ) : null}
                    </div>
                    {item.description && (
                      <p className="text-xs text-muted-foreground">{item.description}</p>
                    )}
                    {item.suggested_url && (
                      <p className="text-xs text-muted-foreground">
                        Suggests: <a href={item.suggested_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">{item.suggested_url}</a>
                      </p>
                    )}
                    {item.field_name && (
                      <p className="text-xs text-muted-foreground">
                        Correct <span className="font-medium">{item.field_name}</span> to: {item.suggested_value}
                      </p>
                    )}
                    {item.rating && (
                      <div className="flex items-center gap-0.5">
                        {[1, 2, 3, 4, 5].map((s) => (
                          <Star key={s} className={`h-3 w-3 ${s <= item.rating! ? "fill-amber-400 text-amber-400" : "text-gray-300"}`} />
                        ))}
                      </div>
                    )}
                    {/* Moderation Actions */}
                    {item.status === "pending" && (
                      <div className="flex items-center gap-1.5 pt-1">
                        <Button size="sm" variant="outline" className="h-6 text-xs" onClick={() => handleModerate(item.id, "approved")}>
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          Approve
                        </Button>
                        <Button size="sm" variant="outline" className="h-6 text-xs" onClick={() => handleModerate(item.id, "resolved")}>
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          Resolve
                        </Button>
                        <Button size="sm" variant="outline" className="h-6 text-xs" onClick={() => handleModerate(item.id, "rejected")}>
                          <XCircle className="h-3 w-3 mr-1" />
                          Reject
                        </Button>
                        <Button size="sm" variant="ghost" className="h-6 text-xs" onClick={() => handleModerate(item.id, "dismissed")}>
                          Dismiss
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>
    </div>
  );
}