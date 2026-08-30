"use client";

import React, { useCallback, useEffect, useState, useMemo, useRef } from "react";
import {
  BookOpen,
  Video,
  FileText,
  Globe,
  HelpCircle,
  Layers,
  Search,
  Filter,
  RefreshCw,
  X,
  AlertCircle,
  Star,
  Clock,
  Tag,
  ShieldCheck,
  Crown,
  Coins,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Bookmark,
  BookmarkCheck,
  Eye,
  CheckCircle2,
  SortAsc,
  SortDesc,
  SlidersHorizontal,
  Heart,
  LayoutGrid,
  List as ListIcon,
  Sparkles,
  TrendingUp,
  Library,
  ExternalLink,
  Share2,
  Award,
  Flame,
  Zap,
  Target,
  ArrowRight,
  Loader2,
  StickyNote,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Modal } from "@/components/ui/modal";
import { IntelligentSearch } from "@/components/resources/intelligent-search";
import { ResourceNotes } from "@/components/resources/resource-notes";
import { resourcesService, analyticsService } from "@/services/api";
import type { ResourceItem, ResourceFilters, ResourceSortBy, SortOrder, ResourceType, ResourceSkill, ResourceDifficulty } from "@/types";

// ─── Constants ──────────────────────────────────────────────────────────────

const ALL_SKILLS: ResourceSkill[] = ["Reading", "Listening", "Writing", "Speaking", "Vocabulary", "Grammar"];
const ALL_TYPES: ResourceType[] = ["Video", "PDF", "Website", "Quiz", "Flashcard"];
const ALL_DIFFICULTIES: ResourceDifficulty[] = ["beginner", "intermediate", "advanced", "all_levels"];

const ResourceTypeMeta: Record<string, { icon: React.ElementType; color: string; gradient: string; bg: string }> = {
  Video: { icon: Video, color: "text-red-500", gradient: "from-red-500 to-rose-600", bg: "bg-red-50" },
  PDF: { icon: FileText, color: "text-blue-500", gradient: "from-blue-500 to-indigo-600", bg: "bg-blue-50" },
  Website: { icon: Globe, color: "text-green-500", gradient: "from-green-500 to-emerald-600", bg: "bg-green-50" },
  Quiz: { icon: HelpCircle, color: "text-purple-500", gradient: "from-purple-500 to-violet-600", bg: "bg-purple-50" },
  Flashcard: { icon: Layers, color: "text-amber-500", gradient: "from-amber-500 to-orange-600", bg: "bg-amber-50" },
};

const SkillMeta: Record<string, { color: string; bg: string; icon: React.ElementType; gradient: string }> = {
  Reading: { color: "text-blue-700", bg: "bg-blue-50", icon: BookOpen, gradient: "from-blue-500 to-cyan-600" },
  Listening: { color: "text-green-700", bg: "bg-green-50", icon: Eye, gradient: "from-green-500 to-emerald-600" },
  Writing: { color: "text-purple-700", bg: "bg-purple-50", icon: FileText, gradient: "from-purple-500 to-violet-600" },
  Speaking: { color: "text-pink-700", bg: "bg-pink-50", icon: Sparkles, gradient: "from-pink-500 to-rose-600" },
  Vocabulary: { color: "text-orange-700", bg: "bg-orange-50", icon: Tag, gradient: "from-orange-500 to-amber-600" },
  Grammar: { color: "text-teal-700", bg: "bg-teal-50", icon: CheckCircle2, gradient: "from-teal-500 to-cyan-600" },
};

const DifficultyMeta: Record<string, { color: string; bg: string; label: string; icon: React.ElementType }> = {
  beginner: { color: "text-green-700", bg: "bg-green-100", label: "Beginner", icon: Target },
  intermediate: { color: "text-yellow-700", bg: "bg-yellow-100", label: "Intermediate", icon: Zap },
  advanced: { color: "text-red-700", bg: "bg-red-100", label: "Advanced", icon: Flame },
  all_levels: { color: "text-gray-700", bg: "bg-gray-100", label: "All Levels", icon: Layers },
};

const DURATION_PRESETS = [
  { label: "< 15 min", min: 0, max: 15 },
  { label: "15-30 min", min: 15, max: 30 },
  { label: "30-60 min", min: 30, max: 60 },
  { label: "1+ hours", min: 60, max: 9999 },
];

const BAND_PRESETS = [
  { label: "5.0 - 6.0", min: 5.0, max: 6.0 },
  { label: "6.0 - 7.0", min: 6.0, max: 7.0 },
  { label: "7.0 - 8.0", min: 7.0, max: 8.0 },
  { label: "8.0 - 9.0", min: 8.0, max: 9.0 },
];

type ViewMode = "all" | "favorites" | "bookmarks" | "completed" | "recent" | "official";
type ViewLayout = "grid" | "list";

const VIEW_MODES: { key: ViewMode; label: string; icon: React.ElementType; gradient: string }[] = [
  { key: "all", label: "All", icon: Library, gradient: "from-blue-500 to-indigo-600" },
  { key: "favorites", label: "Favorites", icon: Heart, gradient: "from-red-500 to-rose-600" },
  { key: "bookmarks", label: "Bookmarks", icon: Bookmark, gradient: "from-indigo-500 to-purple-600" },
  { key: "completed", label: "Completed", icon: CheckCircle2, gradient: "from-green-500 to-emerald-600" },
  { key: "recent", label: "Recently Viewed", icon: Eye, gradient: "from-amber-500 to-orange-600" },
  { key: "official", label: "Official", icon: Crown, gradient: "from-yellow-500 to-amber-600" },
];

const SORT_OPTIONS: { value: ResourceSortBy; label: string; icon: React.ElementType }[] = [
  { value: "popularity", label: "Popularity", icon: TrendingUp },
  { value: "rating", label: "Rating", icon: Star },
  { value: "name", label: "Name", icon: BookOpen },
  { value: "time", label: "Duration", icon: Clock },
  { value: "created", label: "Recently Added", icon: Sparkles },
];

const PAGE_SIZE = 12;

// ─── Helper Components ───────────────────────────────────────────────────────

function AnimatedCounter({ value, duration = 800 }: { value: number; duration?: number }) {
  const [count, setCount] = useState(0);
  const prevValue = useRef(0);

  useEffect(() => {
    const startValue = prevValue.current;
    const diff = value - startValue;
    const startTime = Date.now();

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeOut = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(startValue + diff * easeOut));
      if (progress < 1) requestAnimationFrame(animate);
      else prevValue.current = value;
    };

    requestAnimationFrame(animate);
  }, [value, duration]);

  return <>{count}</>;
}

function RatingStars({ rating, size = "sm" }: { rating?: number; size?: "sm" | "md" | "lg" }) {
  if (rating === undefined || rating === null) return null;
  const rounded = Math.round(rating);
  const sizeClass = size === "lg" ? "h-5 w-5" : size === "md" ? "h-4 w-4" : "h-3 w-3";
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={`${sizeClass} transition-colors ${star <= rounded ? "fill-amber-400 text-amber-400" : "text-gray-300"}`}
        />
      ))}
      <span className={`ml-1 font-medium ${size === "lg" ? "text-sm" : "text-xs"} text-muted-foreground`}>
        {rating.toFixed(1)}
      </span>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  gradient,
  delay = 0,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  gradient: string;
  delay?: number;
}) {
  return (
    <div
      className="group relative overflow-hidden rounded-xl bg-white/10 backdrop-blur-md p-3 border border-white/20 transition-all hover:bg-white/15 hover:scale-105 animate-stagger"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className={`absolute -right-4 -top-4 h-16 w-16 rounded-full bg-gradient-to-br ${gradient} opacity-20 blur-xl group-hover:opacity-40 transition-opacity`} />
      <div className="relative flex items-center gap-2">
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br ${gradient} shadow-lg`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="text-2xl font-bold leading-none">
            <AnimatedCounter value={value} />
          </p>
          <p className="text-xs text-white/80 mt-0.5">{label}</p>
        </div>
      </div>
    </div>
  );
}

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 text-primary px-3 py-1 text-xs font-medium animate-scale-in hover:bg-primary/20 transition-colors">
      {label}
      <button onClick={onRemove} className="hover:text-primary/70 transition-colors" aria-label={`Remove ${label}`}>
        <X className="h-3 w-3" />
      </button>
    </span>
  );
}

function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
  badge,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
  badge?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-border/50 last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between py-2.5 text-left hover:bg-muted/30 -mx-1 px-1 rounded-md transition-colors"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-semibold text-foreground uppercase tracking-wide">{title}</span>
          {badge !== undefined && badge > 0 && (
            <Badge variant="secondary" className="text-xs h-4 px-1.5">{badge}</Badge>
          )}
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
      </button>
      {open && <div className="pb-3 animate-slide-down">{children}</div>}
    </div>
  );
}

function ResourceCard({
  resource,
  index,
  onToggleFavorite,
  onToggleBookmark,
  onMarkComplete,
  onRecordView,
  onOpenDetail,
}: {
  resource: ResourceItem;
  index: number;
  onToggleFavorite: (r: ResourceItem) => void;
  onToggleBookmark: (r: ResourceItem) => void;
  onMarkComplete: (r: ResourceItem) => void;
  onRecordView: (r: ResourceItem) => void;
  onOpenDetail: (r: ResourceItem) => void;
}) {
  const typeMeta = ResourceTypeMeta[resource.type] || ResourceTypeMeta.Video;
  const skillMeta = SkillMeta[resource.skill];
  const diffMeta = resource.difficulty ? DifficultyMeta[resource.difficulty] : null;
  const TypeIcon = typeMeta.icon;

  const handleCardClick = () => {
    onOpenDetail(resource);
  };

  const handleVisit = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (resource.url) {
      window.open(resource.url, "_blank", "noopener,noreferrer");
      onRecordView(resource);
    }
  };

  return (
    <Card
      className="group relative overflow-hidden transition-all duration-300 hover:shadow-xl hover:-translate-y-1 cursor-pointer animate-stagger card-hover-lift"
      style={{ animationDelay: `${Math.min(index * 50, 600)}ms` }}
      onClick={handleCardClick}
      role="article"
      aria-label={`Resource: ${resource.title}`}
    >
      {/* Thumbnail / Gradient Header */}
      <div className={`relative h-32 bg-gradient-to-br ${typeMeta.gradient} overflow-hidden`}>
        {resource.thumbnail ? (
          <img
            src={resource.thumbnail}
            alt={resource.title}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <TypeIcon className="h-12 w-12 text-white/80 group-hover:scale-110 transition-transform duration-300" />
          </div>
        )}
        {/* Overlay gradient for text readability */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />

        {/* Type badge */}
        <Badge className="absolute top-2 left-2 bg-white/90 text-gray-800 text-xs border-0 backdrop-blur-sm">
          <TypeIcon className="h-3 w-3 mr-1" />
          {resource.type}
        </Badge>

        {/* Action buttons */}
        <div className="absolute top-2 right-2 flex gap-1" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onToggleFavorite(resource)}
            className={`flex h-7 w-7 items-center justify-center rounded-full backdrop-blur-md transition-all hover:scale-110 active:scale-95 ${
              resource.is_favorited
                ? "bg-red-500 text-white shadow-lg"
                : "bg-white/80 text-gray-600 hover:bg-white"
            }`}
            title={resource.is_favorited ? "Remove from favorites" : "Add to favorites"}
            aria-label={resource.is_favorited ? "Remove from favorites" : "Add to favorites"}
          >
            <Heart className={`h-3.5 w-3.5 transition-all ${resource.is_favorited ? "fill-current scale-110" : ""}`} />
          </button>
          <button
            onClick={() => onToggleBookmark(resource)}
            className={`flex h-7 w-7 items-center justify-center rounded-full backdrop-blur-md transition-all hover:scale-110 active:scale-95 ${
              resource.is_bookmarked
                ? "bg-blue-500 text-white shadow-lg"
                : "bg-white/80 text-gray-600 hover:bg-white"
            }`}
            title={resource.is_bookmarked ? "Remove bookmark" : "Bookmark"}
            aria-label={resource.is_bookmarked ? "Remove bookmark" : "Bookmark"}
          >
            {resource.is_bookmarked ? (
              <BookmarkCheck className="h-3.5 w-3.5" />
            ) : (
              <Bookmark className="h-3.5 w-3.5" />
            )}
          </button>
        </div>

        {/* Status badges */}
        <div className="absolute bottom-2 left-2 flex gap-1 flex-wrap">
          {resource.official && (
            <Badge className="bg-amber-500/90 text-white text-xs border-0 backdrop-blur-sm">
              <Crown className="h-3 w-3 mr-0.5" />
              Official
            </Badge>
          )}
          {resource.verified && (
            <Badge className="bg-emerald-500/90 text-white text-xs border-0 backdrop-blur-sm">
              <ShieldCheck className="h-3 w-3 mr-0.5" />
              Verified
            </Badge>
          )}
          {resource.is_completed && (
            <Badge className="bg-green-500/90 text-white text-xs border-0 backdrop-blur-sm">
              <CheckCircle2 className="h-3 w-3 mr-0.5" />
              Done
            </Badge>
          )}
        </div>
      </div>

      <CardContent className="p-4 space-y-3">
        {/* Badges row */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {skillMeta && (
            <Badge variant="outline" className={`text-xs ${skillMeta.bg} ${skillMeta.color} border-0`}>
              {resource.skill}
            </Badge>
          )}
          {resource.sub_skill && (
            <Badge variant="outline" className="text-xs">
              {resource.sub_skill}
            </Badge>
          )}
          {diffMeta && resource.difficulty !== "all_levels" && (
            <Badge variant="outline" className={`text-xs ${diffMeta.bg} ${diffMeta.color} border-0`}>
              {diffMeta.label}
            </Badge>
          )}
        </div>

        {/* Title & Description */}
        <div>
          <h3 className="font-semibold text-sm line-clamp-2 group-hover:text-primary transition-colors">
            {resource.title}
          </h3>
          {resource.description && (
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
              {resource.description}
            </p>
          )}
        </div>

        {/* Meta info */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {resource.rating !== undefined && resource.rating > 0 && (
            <div className="flex items-center gap-1">
              <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
              <span className="font-medium">{resource.rating.toFixed(1)}</span>
            </div>
          )}
          {resource.estimated_time && (
            <div className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              <span>{resource.estimated_time}m</span>
            </div>
          )}
          {resource.is_free ? (
            <Badge variant="secondary" className="text-xs bg-green-50 text-green-700 border-0">
              <Coins className="h-3 w-3 mr-0.5" />
              Free
            </Badge>
          ) : (
            <Badge variant="outline" className="text-xs">
              Premium
            </Badge>
          )}
        </div>
      </CardContent>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 pb-3">
        <Button
          variant="ghost"
          size="sm"
          className="text-xs h-7"
          onClick={(e) => {
            e.stopPropagation();
            onOpenDetail(resource);
          }}
        >
          Details
          <ChevronRight className="h-3 w-3 ml-1" />
        </Button>
        {resource.url && (
          <button
            onClick={handleVisit}
            className="text-xs text-primary hover:underline flex items-center gap-1 transition-colors"
          >
            <ExternalLink className="h-3 w-3" />
            Visit
          </button>
        )}
      </div>
    </Card>
  );
}

function ResourceListItem({
  resource,
  index,
  onToggleFavorite,
  onToggleBookmark,
  onMarkComplete,
  onRecordView,
  onOpenDetail,
}: {
  resource: ResourceItem;
  index: number;
  onToggleFavorite: (r: ResourceItem) => void;
  onToggleBookmark: (r: ResourceItem) => void;
  onMarkComplete: (r: ResourceItem) => void;
  onRecordView: (r: ResourceItem) => void;
  onOpenDetail: (r: ResourceItem) => void;
}) {
  const typeMeta = ResourceTypeMeta[resource.type] || ResourceTypeMeta.Video;
  const skillMeta = SkillMeta[resource.skill];
  const diffMeta = resource.difficulty ? DifficultyMeta[resource.difficulty] : null;
  const TypeIcon = typeMeta.icon;

  const handleClick = () => {
    onOpenDetail(resource);
  };

  const handleVisit = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (resource.url) {
      window.open(resource.url, "_blank", "noopener,noreferrer");
      onRecordView(resource);
    }
  };

  return (
    <Card
      className="group flex items-stretch overflow-hidden transition-all duration-300 hover:shadow-md cursor-pointer animate-stagger"
      style={{ animationDelay: `${Math.min(index * 40, 500)}ms` }}
      onClick={handleClick}
    >
      {/* Thumbnail */}
      <div className={`relative w-24 shrink-0 bg-gradient-to-br ${typeMeta.gradient} flex items-center justify-center`}>
        {resource.thumbnail ? (
          <img src={resource.thumbnail} alt={resource.title} className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <TypeIcon className="h-6 w-6 text-white/80" />
        )}
      </div>

      {/* Content */}
      <CardContent className="flex-1 p-3 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap mb-1">
              {skillMeta && (
                <Badge variant="outline" className={`text-xs ${skillMeta.bg} ${skillMeta.color} border-0`}>
                  {resource.skill}
                </Badge>
              )}
              {diffMeta && resource.difficulty !== "all_levels" && (
                <Badge variant="outline" className={`text-xs ${diffMeta.bg} ${diffMeta.color} border-0`}>
                  {diffMeta.label}
                </Badge>
              )}
              {resource.official && (
                <Badge className="bg-amber-500/90 text-white text-xs border-0">
                  <Crown className="h-2.5 w-2.5 mr-0.5" />
                  Official
                </Badge>
              )}
              {resource.is_free ? (
                <Badge variant="secondary" className="text-xs bg-green-50 text-green-700 border-0">
                  Free
                </Badge>
              ) : (
                <Badge variant="outline" className="text-xs">
                  Premium
                </Badge>
              )}
            </div>
            <h3 className="font-semibold text-sm line-clamp-1 group-hover:text-primary transition-colors">
              {resource.title}
            </h3>
            {resource.description && (
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                {resource.description}
              </p>
            )}
            <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
              {resource.rating !== undefined && resource.rating > 0 && (
                <div className="flex items-center gap-0.5">
                  <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                  <span>{resource.rating.toFixed(1)}</span>
                </div>
              )}
              {resource.estimated_time && (
                <div className="flex items-center gap-0.5">
                  <Clock className="h-3 w-3" />
                  <span>{resource.estimated_time}m</span>
                </div>
              )}
              {resource.is_completed && (
                <div className="flex items-center gap-0.5 text-green-600">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Completed</span>
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => onToggleFavorite(resource)}
              className={`flex h-7 w-7 items-center justify-center rounded-full transition-all hover:scale-110 active:scale-95 ${
                resource.is_favorited ? "text-red-500" : "text-gray-400 hover:text-gray-600"
              }`}
              aria-label={resource.is_favorited ? "Remove from favorites" : "Add to favorites"}
            >
              <Heart className={`h-4 w-4 transition-all ${resource.is_favorited ? "fill-current scale-110" : ""}`} />
            </button>
            <button
              onClick={() => onToggleBookmark(resource)}
              className={`flex h-7 w-7 items-center justify-center rounded-full transition-all hover:scale-110 active:scale-95 ${
                resource.is_bookmarked ? "text-blue-500" : "text-gray-400 hover:text-gray-600"
              }`}
              aria-label={resource.is_bookmarked ? "Remove bookmark" : "Bookmark"}
            >
              {resource.is_bookmarked ? (
                <BookmarkCheck className="h-4 w-4" />
              ) : (
                <Bookmark className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SkeletonCard() {
  return (
    <Card className="overflow-hidden">
      <Skeleton className="h-32 w-full rounded-none" />
      <CardContent className="p-4 space-y-3">
        <div className="flex gap-2">
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-5 w-12 rounded-full" />
        </div>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <div className="flex gap-3">
          <Skeleton className="h-3 w-12" />
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-3 w-14" />
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState({ viewMode, hasFilters, onClear }: { viewMode: ViewMode; hasFilters: boolean; onClear: () => void }) {
  const messages: Record<ViewMode, { title: string; description: string; icon: React.ElementType; gradient: string }> = {
    all: {
      title: "No resources found",
      description: "Try adjusting your filters or search terms to find what you're looking for.",
      icon: BookOpen,
      gradient: "from-blue-500 to-indigo-600",
    },
    favorites: {
      title: "No favorites yet",
      description: "Click the heart icon on any resource to add it to your favorites.",
      icon: Heart,
      gradient: "from-red-500 to-rose-600",
    },
    bookmarks: {
      title: "No bookmarks yet",
      description: "Bookmark resources to save them for later and find them quickly here.",
      icon: Bookmark,
      gradient: "from-indigo-500 to-purple-600",
    },
    completed: {
      title: "Nothing completed yet",
      description: "Resources you've completed will appear here. Start exploring to track your progress!",
      icon: CheckCircle2,
      gradient: "from-green-500 to-emerald-600",
    },
    recent: {
      title: "No recent views",
      description: "Resources you've recently viewed will show up here for quick access.",
      icon: Eye,
      gradient: "from-amber-500 to-orange-600",
    },
    official: {
      title: "No official resources",
      description: "Official IELTS resources from Cambridge, British Council, and IDP will appear here.",
      icon: Crown,
      gradient: "from-yellow-500 to-amber-600",
    },
  };

  const { title, description, icon: Icon, gradient } = messages[viewMode];

  return (
    <Card className="border-dashed">
      <CardContent className="pt-12 pb-12">
        <div className="text-center space-y-4">
          <div className="relative inline-flex">
            <div className={`absolute inset-0 rounded-full bg-gradient-to-br ${gradient} opacity-20 blur-xl animate-pulse-soft`} />
            <div className={`relative inline-flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br ${gradient} shadow-lg`}>
              <Icon className="h-10 w-10 text-white" />
            </div>
          </div>
          <div className="space-y-2">
            <p className="font-semibold text-lg">{title}</p>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">{description}</p>
          </div>
          {hasFilters && (
            <Button variant="outline" size="sm" className="mt-2" onClick={onClear}>
              <X className="h-3.5 w-3.5 mr-1.5" />
              Clear all filters
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ResourceDetailModal({
  resource,
  onClose,
  onToggleFavorite,
  onToggleBookmark,
  onMarkComplete,
  onRecordView,
}: {
  resource: ResourceItem | null;
  onClose: () => void;
  onToggleFavorite: (r: ResourceItem) => void;
  onToggleBookmark: (r: ResourceItem) => void;
  onMarkComplete: (r: ResourceItem) => void;
  onRecordView: (r: ResourceItem) => void;
}) {
  const [showNotes, setShowNotes] = useState(false);

  if (!resource) return null;

  const typeMeta = ResourceTypeMeta[resource.type] || ResourceTypeMeta.Video;
  const skillMeta = SkillMeta[resource.skill];
  const diffMeta = resource.difficulty ? DifficultyMeta[resource.difficulty] : null;
  const TypeIcon = typeMeta.icon;
  const SkillIcon = skillMeta?.icon;

  const handleVisit = () => {
    if (resource.url) {
      window.open(resource.url, "_blank", "noopener,noreferrer");
      onRecordView(resource);
    }
  };

  return (
    <Modal isOpen={!!resource} onClose={onClose} className="max-w-2xl p-0 overflow-hidden">
      {/* Header with gradient */}
      <div className={`relative h-40 bg-gradient-to-br ${typeMeta.gradient} overflow-hidden`}>
        {resource.thumbnail ? (
          <img src={resource.thumbnail} alt={resource.title} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center">
            <TypeIcon className="h-16 w-16 text-white/80" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />

        {/* Badges overlay */}
        <div className="absolute top-3 left-3 flex gap-2 flex-wrap">
          <Badge className="bg-white/90 text-gray-800 border-0 backdrop-blur-sm">
            <TypeIcon className="h-3 w-3 mr-1" />
            {resource.type}
          </Badge>
          {resource.official && (
            <Badge className="bg-amber-500/90 text-white border-0 backdrop-blur-sm">
              <Crown className="h-3 w-3 mr-0.5" />
              Official
            </Badge>
          )}
          {resource.verified && (
            <Badge className="bg-emerald-500/90 text-white border-0 backdrop-blur-sm">
              <ShieldCheck className="h-3 w-3 mr-0.5" />
              Verified
            </Badge>
          )}
        </div>

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 flex h-8 w-8 items-center justify-center rounded-full bg-white/80 backdrop-blur-sm hover:bg-white transition-colors"
          aria-label="Close"
        >
          <X className="h-4 w-4 text-gray-700" />
        </button>
      </div>

      {/* Content */}
      <div className="p-6 space-y-4 max-h-[calc(100vh-20rem)] overflow-y-auto scrollbar-thin">
        {/* Title & badges */}
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-2">
            {skillMeta && (
              <Badge variant="outline" className={`${skillMeta.bg} ${skillMeta.color} border-0`}>
                {SkillIcon && <SkillIcon className="h-3 w-3 mr-1" />}
                {resource.skill}
              </Badge>
            )}
            {resource.sub_skill && (
              <Badge variant="outline">{resource.sub_skill}</Badge>
            )}
            {diffMeta && resource.difficulty !== "all_levels" && (
              <Badge variant="outline" className={`${diffMeta.bg} ${diffMeta.color} border-0`}>
                {diffMeta.label}
              </Badge>
            )}
            {resource.is_free ? (
              <Badge variant="secondary" className="bg-green-50 text-green-700 border-0">
                <Coins className="h-3 w-3 mr-0.5" />
                Free
              </Badge>
            ) : (
              <Badge variant="outline">Premium</Badge>
            )}
          </div>
          <h2 className="text-xl font-bold leading-tight">{resource.title}</h2>
          {resource.description && (
            <p className="text-sm text-muted-foreground mt-2">{resource.description}</p>
          )}
        </div>

        {/* Rating */}
        {resource.rating !== undefined && resource.rating > 0 && (
          <div className="flex items-center gap-2">
            <RatingStars rating={resource.rating} size="md" />
            <span className="text-xs text-muted-foreground">({resource.rating.toFixed(1)} out of 5)</span>
          </div>
        )}

        {/* Details grid */}
        <div className="grid grid-cols-2 gap-3">
          {resource.author && (
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Author</p>
              <p className="text-sm font-medium mt-0.5">{resource.author}</p>
            </div>
          )}
          {resource.source && (
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Source</p>
              <p className="text-sm font-medium mt-0.5">{resource.source}</p>
            </div>
          )}
          {resource.estimated_time && (
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Duration</p>
              <p className="text-sm font-medium mt-0.5 flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {resource.estimated_time} minutes
              </p>
            </div>
          )}
          {(resource.minimum_band !== undefined || resource.maximum_band !== undefined) && (
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Band Range</p>
              <p className="text-sm font-medium mt-0.5 flex items-center gap-1">
                <Award className="h-3.5 w-3.5" />
                {resource.minimum_band ?? 0} – {resource.maximum_band ?? 9.0}
              </p>
            </div>
          )}
        </div>

        {/* Tags */}
        {resource.tags && resource.tags.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {resource.tags.map((tag) => (
                <Badge key={tag} variant="outline" className="text-xs">
                  <Tag className="h-2.5 w-2.5 mr-0.5" />
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Status */}
        {resource.is_completed && (
          <div className="flex items-center gap-2 rounded-lg bg-green-50 p-3 text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            <span className="text-sm font-medium">{"You've completed this resource"}</span>
          </div>
        )}

        {/* Notes & Highlights */}
        {showNotes && <ResourceNotes resource={resource} />}
      </div>

      {/* Notes toggle */}
      {!showNotes && (
        <div className="px-6 pb-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowNotes(true)}
            className="w-full"
          >
            <StickyNote className="h-4 w-4 mr-1.5" />
            Add Notes & Highlights
          </Button>
        </div>
      )}

      {/* Footer actions */}
      <div className="flex items-center gap-2 border-t border-border p-4 bg-card">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onToggleFavorite(resource)}
          className={resource.is_favorited ? "text-red-500 border-red-200" : ""}
        >
          <Heart className={`h-4 w-4 mr-1.5 ${resource.is_favorited ? "fill-current" : ""}`} />
          {resource.is_favorited ? "Favorited" : "Favorite"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onToggleBookmark(resource)}
          className={resource.is_bookmarked ? "text-blue-500 border-blue-200" : ""}
        >
          {resource.is_bookmarked ? <BookmarkCheck className="h-4 w-4 mr-1.5" /> : <Bookmark className="h-4 w-4 mr-1.5" />}
          {resource.is_bookmarked ? "Bookmarked" : "Bookmark"}
        </Button>
        {!resource.is_completed && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onMarkComplete(resource)}
          >
            <CheckCircle2 className="h-4 w-4 mr-1.5" />
            Mark Complete
          </Button>
        )}
        <div className="flex-1" />
        {resource.url && (
          <Button size="sm" onClick={handleVisit}>
            <ExternalLink className="h-4 w-4 mr-1.5" />
            Visit Resource
          </Button>
        )}
      </div>
    </Modal>
  );
}

function FilterPanel({
  filterSkill, setFilterSkill, setFilterSubSkill,
  filterSubSkill, filterType, setFilterType,
  filterDifficulty, setFilterDifficulty,
  filterMinBand, setFilterMinBand, filterMaxBand, setFilterMaxBand,
  filterDurationMin, setFilterDurationMin, filterDurationMax, setFilterDurationMax,
  filterSource, setFilterSource,
  filterFree, setFilterFree,
  filterOfficial, setFilterOfficial,
  filterVerified, setFilterVerified,
  availableSubSkills, availableSources,
  clearFilters, activeFilterCount,
}: any) {
  return (
    <Card className="sticky top-20 glass-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            Filters
          </CardTitle>
          {activeFilterCount > 0 && (
            <Button variant="ghost" size="sm" onClick={clearFilters} className="text-xs h-7">
              Clear ({activeFilterCount})
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-1 max-h-[calc(100vh-12rem)] overflow-y-auto scrollbar-thin pr-1">
        {/* Skill */}
        <CollapsibleSection title="Skill" icon={BookOpen}>
          <select
            value={filterSkill}
            onChange={(e) => { setFilterSkill(e.target.value); setFilterSubSkill(""); }}
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
          >
            <option value="">All Skills</option>
            {ALL_SKILLS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </CollapsibleSection>

        {/* Sub-Skill */}
        {filterSkill && availableSubSkills.length > 0 && (
          <CollapsibleSection title="Sub-Skill" icon={Tag} defaultOpen={true}>
            <select
              value={filterSubSkill}
              onChange={(e) => setFilterSubSkill(e.target.value)}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
            >
              <option value="">All Sub-Skills</option>
              {availableSubSkills.map((s: string) => <option key={s} value={s}>{s}</option>)}
            </select>
          </CollapsibleSection>
        )}

        {/* Resource Type */}
        <CollapsibleSection title="Resource Type" icon={Layers}>
          <div className="grid grid-cols-2 gap-1.5">
            {ALL_TYPES.map((t) => {
              const meta = ResourceTypeMeta[t];
              const Icon = meta.icon;
              const isActive = filterType === t;
              return (
                <button
                  key={t}
                  onClick={() => setFilterType(isActive ? "" : t)}
                  className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all ${
                    isActive
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-input hover:border-primary/30 hover:bg-muted/50"
                  }`}
                >
                  <Icon className={`h-3.5 w-3.5 ${isActive ? meta.color : "text-muted-foreground"}`} />
                  {t}
                </button>
              );
            })}
          </div>
        </CollapsibleSection>

        {/* Difficulty */}
        <CollapsibleSection title="Difficulty" icon={Target}>
          <div className="grid grid-cols-2 gap-1.5">
            {ALL_DIFFICULTIES.map((d) => {
              const meta = DifficultyMeta[d];
              const isActive = filterDifficulty === d;
              return (
                <button
                  key={d}
                  onClick={() => setFilterDifficulty(isActive ? "" : d)}
                  className={`rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all ${
                    isActive
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-input hover:border-primary/30 hover:bg-muted/50"
                  }`}
                >
                  {meta.label}
                </button>
              );
            })}
          </div>
        </CollapsibleSection>

        {/* Band Range */}
        <CollapsibleSection title="Band Range" icon={Award}>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Input
                type="number"
                step="0.5"
                min="0"
                max="9"
                value={filterMinBand}
                onChange={(e) => setFilterMinBand(e.target.value)}
                placeholder="Min"
                className="text-sm"
              />
              <span className="text-muted-foreground text-xs">–</span>
              <Input
                type="number"
                step="0.5"
                min="0"
                max="9"
                value={filterMaxBand}
                onChange={(e) => setFilterMaxBand(e.target.value)}
                placeholder="Max"
                className="text-sm"
              />
            </div>
            <div className="flex flex-wrap gap-1">
              {BAND_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  onClick={() => { setFilterMinBand(String(preset.min)); setFilterMaxBand(String(preset.max)); }}
                  className="rounded-full border border-input px-2 py-0.5 text-xs hover:border-primary/30 hover:bg-primary/5 transition-all"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
        </CollapsibleSection>

        {/* Duration Range */}
        <CollapsibleSection title="Duration" icon={Clock}>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min="0"
                value={filterDurationMin}
                onChange={(e) => setFilterDurationMin(e.target.value)}
                placeholder="Min"
                className="text-sm"
              />
              <span className="text-muted-foreground text-xs">–</span>
              <Input
                type="number"
                min="0"
                value={filterDurationMax}
                onChange={(e) => setFilterDurationMax(e.target.value)}
                placeholder="Max"
                className="text-sm"
              />
            </div>
            <div className="flex flex-wrap gap-1">
              {DURATION_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  onClick={() => { setFilterDurationMin(String(preset.min)); setFilterDurationMax(String(preset.max)); }}
                  className="rounded-full border border-input px-2 py-0.5 text-xs hover:border-primary/30 hover:bg-primary/5 transition-all"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
        </CollapsibleSection>

        {/* Source */}
        {availableSources.length > 0 && (
          <CollapsibleSection title="Source" icon={Globe} defaultOpen={false}>
            <select
              value={filterSource}
              onChange={(e) => setFilterSource(e.target.value)}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
            >
              <option value="">All Sources</option>
              {availableSources.map((s: string) => <option key={s} value={s}>{s}</option>)}
            </select>
          </CollapsibleSection>
        )}

        {/* Quick Filters */}
        <CollapsibleSection title="Quick Filters" icon={Zap}>
          <div className="space-y-2">
            {[
              { label: "Free Only", state: filterFree, setter: setFilterFree, icon: Coins, color: "text-green-600" },
              { label: "Official", state: filterOfficial, setter: setFilterOfficial, icon: Crown, color: "text-amber-600" },
              { label: "Verified", state: filterVerified, setter: setFilterVerified, icon: ShieldCheck, color: "text-emerald-600" },
            ].map(({ label, state, setter, icon: Icon, color }) => (
              <button
                key={label}
                onClick={() => setter(state ? undefined : true)}
                className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm transition-all ${
                  state
                    ? "border-primary bg-primary/5"
                    : "border-input hover:bg-muted/50"
                }`}
              >
                <span className="flex items-center gap-2">
                  <Icon className={`h-4 w-4 ${state ? color : "text-muted-foreground"}`} />
                  {label}
                </span>
                <div className={`relative h-5 w-9 rounded-full transition-colors ${state ? "bg-primary" : "bg-muted"}`}>
                  <div className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${state ? "translate-x-4" : "translate-x-0.5"}`} />
                </div>
              </button>
            ))}
          </div>
        </CollapsibleSection>
      </CardContent>
    </Card>
  );
}

// ─── Main Page Component ─────────────────────────────────────────────────────

export default function ResourcesPage() {
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resources, setResources] = useState<ResourceItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);

  // Search (debounced)
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Filters
  const [filterSkill, setFilterSkill] = useState("");
  const [filterSubSkill, setFilterSubSkill] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState("");
  const [filterMinBand, setFilterMinBand] = useState("");
  const [filterMaxBand, setFilterMaxBand] = useState("");
  const [filterDurationMin, setFilterDurationMin] = useState("");
  const [filterDurationMax, setFilterDurationMax] = useState("");
  const [filterSource, setFilterSource] = useState("");
  const [filterFree, setFilterFree] = useState<boolean | undefined>(undefined);
  const [filterOfficial, setFilterOfficial] = useState<boolean | undefined>(undefined);
  const [filterVerified, setFilterVerified] = useState<boolean | undefined>(undefined);

  // View mode & layout
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [viewLayout, setViewLayout] = useState<ViewLayout>("grid");
  const [showMobileFilters, setShowMobileFilters] = useState(false);

  // Sorting
  const [sortBy, setSortBy] = useState<ResourceSortBy>("popularity");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  // Data for dropdowns
  const [availableSubSkills, setAvailableSubSkills] = useState<string[]>([]);
  const [availableSources, setAvailableSources] = useState<string[]>([]);

  // Favorites
  const [favoriteIds, setFavoriteIds] = useState<string[]>([]);

  // Detail modal
  const [selectedResource, setSelectedResource] = useState<ResourceItem | null>(null);

  // Intelligent search results
  const [searchResults, setSearchResults] = useState<ResourceItem[] | null>(null);

  // ─── Debounce search ───
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 350);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // ─── Load favorites from localStorage ───
  useEffect(() => {
    setFavoriteIds(resourcesService.getFavoriteIds());
  }, []);

  // ─── Build filters object ───
  const buildFilters = useCallback((): ResourceFilters => ({
    skill: filterSkill || undefined,
    sub_skill: filterSubSkill || undefined,
    type: filterType || undefined,
    difficulty: filterDifficulty || undefined,
    minimum_band: filterMinBand ? parseFloat(filterMinBand) : undefined,
    maximum_band: filterMaxBand ? parseFloat(filterMaxBand) : undefined,
    estimated_time_min: filterDurationMin ? parseInt(filterDurationMin) : undefined,
    estimated_time_max: filterDurationMax ? parseInt(filterDurationMax) : undefined,
    source: filterSource || undefined,
    is_free: filterFree,
    verified: filterVerified,
    official: viewMode === "official" ? true : filterOfficial,
    bookmarks_only: viewMode === "bookmarks" ? true : undefined,
    completed_only: viewMode === "completed" ? true : undefined,
    recently_viewed: viewMode === "recent" ? true : undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
    search: debouncedSearch || undefined,
    limit: PAGE_SIZE,
    offset: 0,
  }), [filterSkill, filterSubSkill, filterType, filterDifficulty, filterMinBand, filterMaxBand,
       filterDurationMin, filterDurationMax, filterSource, filterFree, filterVerified, filterOfficial,
       viewMode, sortBy, sortOrder, debouncedSearch]);

  // ─── Fetch resources ───
  const fetchResources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await resourcesService.listAdvanced(buildFilters());
      // Normalize and annotate with favorites
      const favIds = resourcesService.getFavoriteIds();
      setFavoriteIds(favIds);
      const normalized = (data || []).map((r: any) => ({
        ...r,
        tags: r.tags || [],
        language: r.language || "en",
        verified: r.verified ?? false,
        official: r.official ?? false,
        is_free: r.is_free ?? true,
        popularity_score: r.popularity_score ?? 0,
        is_bookmarked: r.is_bookmarked ?? false,
        is_completed: r.is_completed ?? false,
        is_viewed: r.is_viewed ?? false,
        is_favorited: favIds.includes(r.id),
      })) as ResourceItem[];

      // Client-side filter for favorites view mode
      if (viewMode === "favorites") {
        setResources(normalized.filter((r) => r.is_favorited));
      } else {
        setResources(normalized);
      }
      setTotalCount(normalized.length);
    } catch (err: any) {
      setError(err?.message || "Failed to load resources. Please check your connection and try again.");
      setResources([]);
    } finally {
      setLoading(false);
    }
  }, [buildFilters, viewMode]);

  // ─── Load more ───
  const handleLoadMore = useCallback(async () => {
    setLoadingMore(true);
    try {
      const moreFilters = { ...buildFilters(), offset: resources.length };
      const data = await resourcesService.listAdvanced(moreFilters);
      const favIds = resourcesService.getFavoriteIds();
      const normalized = (data || []).map((r: any) => ({
        ...r,
        tags: r.tags || [],
        language: r.language || "en",
        verified: r.verified ?? false,
        official: r.official ?? false,
        is_free: r.is_free ?? true,
        popularity_score: r.popularity_score ?? 0,
        is_bookmarked: r.is_bookmarked ?? false,
        is_completed: r.is_completed ?? false,
        is_viewed: r.is_viewed ?? false,
        is_favorited: favIds.includes(r.id),
      })) as ResourceItem[];

      if (viewMode === "favorites") {
        setResources((prev) => [...prev, ...normalized.filter((r) => r.is_favorited)]);
      } else {
        setResources((prev) => [...prev, ...normalized]);
      }
    } catch {
      // Silently fail on load more
    } finally {
      setLoadingMore(false);
    }
  }, [buildFilters, resources.length, viewMode]);

  // ─── Fetch on filter/view/sort change ───
  useEffect(() => {
    fetchResources();
  }, [fetchResources]);

  // ─── Fetch sub-skills when skill changes ───
  useEffect(() => {
    if (filterSkill) {
      resourcesService.getSubSkills(filterSkill)
        .then(setAvailableSubSkills)
        .catch(() => setAvailableSubSkills([]));
    } else {
      setAvailableSubSkills([]);
    }
  }, [filterSkill]);

  // ─── Fetch sources on mount ───
  useEffect(() => {
    resourcesService.getSources()
      .then(setAvailableSources)
      .catch(() => setAvailableSources([]));
  }, []);

  // ─── Handlers ───
  const handleToggleFavorite = useCallback((resource: ResourceItem) => {
    const newFavState = !resource.is_favorited;
    resourcesService.toggleFavorite(resource.id, resource.is_favorited ?? false);
    setFavoriteIds(resourcesService.getFavoriteIds());
    setResources((prev) =>
      prev.map((r) => (r.id === resource.id ? { ...r, is_favorited: newFavState } : r))
    );
    // Update modal if open
    setSelectedResource((prev) => prev && prev.id === resource.id ? { ...prev, is_favorited: newFavState } : prev);
  }, []);

  const handleToggleBookmark = useCallback(async (resource: ResourceItem) => {
    const newState = !resource.is_bookmarked;
    // Optimistic update
    setResources((prev) =>
      prev.map((r) => (r.id === resource.id ? { ...r, is_bookmarked: newState } : r))
    );
    setSelectedResource((prev) => prev && prev.id === resource.id ? { ...prev, is_bookmarked: newState } : prev);
    try {
      await resourcesService.toggleBookmark(resource.id, resource.is_bookmarked ?? false);
      // Track analytics
      if (newState) {
        analyticsService.recordBookmark(resource.id).catch(() => {});
      } else {
        analyticsService.removeBookmark(resource.id).catch(() => {});
      }
    } catch {
      // Revert on error
      setResources((prev) =>
        prev.map((r) => (r.id === resource.id ? { ...r, is_bookmarked: !newState } : r))
      );
      setSelectedResource((prev) => prev && prev.id === resource.id ? { ...prev, is_bookmarked: !newState } : prev);
    }
  }, []);

  const handleMarkComplete = useCallback(async (resource: ResourceItem) => {
    if (resource.is_completed) return;
    try {
      await resourcesService.recordComplete(resource.id);
      // Track analytics
      analyticsService.recordComplete(resource.id).catch(() => {});
      setResources((prev) =>
        prev.map((r) => (r.id === resource.id ? { ...r, is_completed: true } : r))
      );
      setSelectedResource((prev) => prev && prev.id === resource.id ? { ...prev, is_completed: true } : prev);
    } catch {
      // Silently fail - completing is best-effort
    }
  }, []);

  const handleRecordView = useCallback(async (resource: ResourceItem) => {
    try {
      await resourcesService.recordView(resource.id);
      // Track analytics
      analyticsService.recordView(resource.id).catch(() => {});
    } catch {
      // Silently fail
    }
  }, []);

  const handleOpenDetail = useCallback((resource: ResourceItem) => {
    setSelectedResource(resource);
  }, []);

  // ─── Intelligent search handlers ───
  const handleIntelligentSearch = useCallback((_query: string, results: ResourceItem[]) => {
    setSearchResults(results);
  }, []);

  const handleClearIntelligentSearch = useCallback(() => {
    setSearchResults(null);
    setSearchQuery("");
    setDebouncedSearch("");
  }, []);

  // ─── Clear search results when filters change ───
  useEffect(() => {
    setSearchResults(null);
  }, [filterSkill, filterSubSkill, filterType, filterDifficulty, filterMinBand, filterMaxBand,
       filterDurationMin, filterDurationMax, filterSource, filterFree, filterOfficial, filterVerified,
       viewMode, sortBy, sortOrder]);

  const clearFilters = useCallback(() => {
    setFilterSkill("");
    setFilterSubSkill("");
    setFilterType("");
    setFilterDifficulty("");
    setFilterMinBand("");
    setFilterMaxBand("");
    setFilterDurationMin("");
    setFilterDurationMax("");
    setFilterSource("");
    setFilterFree(undefined);
    setFilterOfficial(undefined);
    setFilterVerified(undefined);
    setSearchQuery("");
    setSortBy("popularity");
    setSortOrder("desc");
  }, []);

  // ─── Active filter count & chips ───
  const activeFilterCount = useMemo(() => {
    return [
      filterSkill, filterSubSkill, filterType, filterDifficulty,
      filterMinBand, filterMaxBand, filterDurationMin, filterDurationMax,
      filterSource, debouncedSearch,
      filterFree, filterOfficial, filterVerified,
    ].filter(Boolean).length;
  }, [filterSkill, filterSubSkill, filterType, filterDifficulty, filterMinBand, filterMaxBand,
     filterDurationMin, filterDurationMax, filterSource, debouncedSearch, filterFree, filterOfficial, filterVerified]);

  const filterChips = useMemo(() => {
    const chips: { label: string; onRemove: () => void }[] = [];
    if (filterSkill) chips.push({ label: `Skill: ${filterSkill}`, onRemove: () => { setFilterSkill(""); setFilterSubSkill(""); } });
    if (filterSubSkill) chips.push({ label: filterSubSkill, onRemove: () => setFilterSubSkill("") });
    if (filterType) chips.push({ label: `Type: ${filterType}`, onRemove: () => setFilterType("") });
    if (filterDifficulty) chips.push({ label: `Difficulty: ${DifficultyMeta[filterDifficulty]?.label || filterDifficulty}`, onRemove: () => setFilterDifficulty("") });
    if (filterMinBand) chips.push({ label: `Min Band: ${filterMinBand}`, onRemove: () => setFilterMinBand("") });
    if (filterMaxBand) chips.push({ label: `Max Band: ${filterMaxBand}`, onRemove: () => setFilterMaxBand("") });
    if (filterDurationMin) chips.push({ label: `Min Duration: ${filterDurationMin}m`, onRemove: () => setFilterDurationMin("") });
    if (filterDurationMax) chips.push({ label: `Max Duration: ${filterDurationMax}m`, onRemove: () => setFilterDurationMax("") });
    if (filterSource) chips.push({ label: `Source: ${filterSource}`, onRemove: () => setFilterSource("") });
    if (debouncedSearch) chips.push({ label: `Search: "${debouncedSearch}"`, onRemove: () => setSearchQuery("") });
    if (filterFree) chips.push({ label: "Free Only", onRemove: () => setFilterFree(undefined) });
    if (filterOfficial) chips.push({ label: "Official", onRemove: () => setFilterOfficial(undefined) });
    if (filterVerified) chips.push({ label: "Verified", onRemove: () => setFilterVerified(undefined) });
    return chips;
  }, [filterSkill, filterSubSkill, filterType, filterDifficulty, filterMinBand, filterMaxBand,
     filterDurationMin, filterDurationMax, filterSource, debouncedSearch, filterFree, filterOfficial, filterVerified]);

  // ─── Display resources (use search results if available) ───
  const displayResources = searchResults ?? resources;

  // ─── Stats ───
  const stats = useMemo(() => ({
    total: displayResources.length,
    favorites: displayResources.filter((r) => r.is_favorited).length,
    bookmarks: displayResources.filter((r) => r.is_bookmarked).length,
    completed: displayResources.filter((r) => r.is_completed).length,
  }), [displayResources]);

  // ─── Featured resources (top 3 by popularity) ───
  const featuredResources = useMemo(() => {
    if (viewMode !== "all" || activeFilterCount > 0 || debouncedSearch || searchResults) return [];
    return [...displayResources]
      .sort((a, b) => (b.popularity_score || 0) - (a.popularity_score || 0))
      .slice(0, 3);
  }, [displayResources, viewMode, activeFilterCount, debouncedSearch, searchResults]);

  const hasMore = searchResults === null && resources.length < totalCount + PAGE_SIZE && resources.length >= PAGE_SIZE;

  // ─── Loading state ───
  if (loading && resources.length === 0) {
    return (
      <DashboardLayout>
        <div className="space-y-6 pb-12">
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary to-accent p-6 md:p-8 text-white h-40 animate-pulse-soft" />
          <Skeleton className="h-14 rounded-xl" />
          <div className="flex gap-2">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-9 w-28 rounded-full" />)}
          </div>
          <div className="flex gap-6">
            <Skeleton className="hidden lg:block w-72 h-96 rounded-xl" />
            <div className="flex-1 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* ─── Header with gradient & stats ─── */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary via-primary to-accent p-6 md:p-8 text-white animate-gradient">
          {/* Decorative elements */}
          <div className="absolute -top-12 -right-12 h-40 w-40 rounded-full bg-white/10 blur-2xl animate-float" />
          <div className="absolute -bottom-8 -left-8 h-32 w-32 rounded-full bg-white/10 blur-2xl animate-float" style={{ animationDelay: "1s" }} />
          <div className="absolute top-1/2 right-1/4 h-24 w-24 rounded-full bg-white/5 blur-xl animate-rotate-slow" />

          <div className="relative z-10">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
                  <Library className="h-8 w-8" />
                  Resource Library
                </h1>
                <p className="text-white/80 text-sm md:text-base">
                  Browse, filter, and discover curated IELTS preparation resources
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={fetchResources}
                className="bg-white/15 hover:bg-white/25 text-white border-white/20 backdrop-blur-md"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>

            {/* Stats cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
              <StatCard label="Total" value={stats.total} icon={BookOpen} gradient="from-blue-400 to-blue-600" delay={0} />
              <StatCard label="Favorites" value={stats.favorites} icon={Heart} gradient="from-red-400 to-rose-600" delay={100} />
              <StatCard label="Bookmarks" value={stats.bookmarks} icon={Bookmark} gradient="from-indigo-400 to-purple-600" delay={200} />
              <StatCard label="Completed" value={stats.completed} icon={CheckCircle2} gradient="from-green-400 to-emerald-600" delay={300} />
            </div>
          </div>
        </div>

        {/* ─── Intelligent Search ─── */}
        <IntelligentSearch
          resources={resources}
          onSearch={handleIntelligentSearch}
          onClear={handleClearIntelligentSearch}
        />

        {/* ─── View Mode Tabs ─── */}
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          {VIEW_MODES.map(({ key, label, icon: Icon, gradient }) => (
            <button
              key={key}
              onClick={() => setViewMode(key)}
              className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition-all ${
                viewMode === key
                  ? `bg-gradient-to-r ${gradient} text-white shadow-md scale-105`
                  : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon className={`h-3.5 w-3.5 ${viewMode === key ? "fill-current" : ""}`} />
              {label}
            </button>
          ))}
        </div>

        {/* ─── Featured Section ─── */}
        {featuredResources.length > 0 && (
          <div className="space-y-3 animate-fade-in">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber-400 to-orange-500">
                <TrendingUp className="h-4 w-4 text-white" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Trending Now</h2>
                <p className="text-xs text-muted-foreground">Most popular resources this week</p>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {featuredResources.map((resource, i) => (
                <ResourceCard
                  key={resource.id}
                  resource={resource}
                  index={i}
                  onToggleFavorite={handleToggleFavorite}
                  onToggleBookmark={handleToggleBookmark}
                  onMarkComplete={handleMarkComplete}
                  onRecordView={handleRecordView}
                  onOpenDetail={handleOpenDetail}
                />
              ))}
            </div>
          </div>
        )}

        {/* ─── Main Content: Sidebar + Grid ─── */}
        <div className="flex gap-6">
          {/* Desktop Filter Sidebar */}
          <aside className="hidden lg:block w-72 shrink-0">
            <FilterPanel
              filterSkill={filterSkill} setFilterSkill={setFilterSkill} setFilterSubSkill={setFilterSubSkill}
              filterSubSkill={filterSubSkill} filterType={filterType} setFilterType={setFilterType}
              filterDifficulty={filterDifficulty} setFilterDifficulty={setFilterDifficulty}
              filterMinBand={filterMinBand} setFilterMinBand={setFilterMinBand} filterMaxBand={filterMaxBand} setFilterMaxBand={setFilterMaxBand}
              filterDurationMin={filterDurationMin} setFilterDurationMin={setFilterDurationMin} filterDurationMax={filterDurationMax} setFilterDurationMax={setFilterDurationMax}
              filterSource={filterSource} setFilterSource={setFilterSource}
              filterFree={filterFree} setFilterFree={setFilterFree}
              filterOfficial={filterOfficial} setFilterOfficial={setFilterOfficial}
              filterVerified={filterVerified} setFilterVerified={setFilterVerified}
              availableSubSkills={availableSubSkills} availableSources={availableSources}
              clearFilters={clearFilters} activeFilterCount={activeFilterCount}
            />
          </aside>

          {/* Main Content */}
          <div className="flex-1 min-w-0 space-y-4">
            {/* Toolbar: Mobile filter + Sort + Layout */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {/* Mobile filter button */}
                <Button
                  variant="outline"
                  size="sm"
                  className="lg:hidden"
                  onClick={() => setShowMobileFilters(true)}
                >
                  <Filter className="h-4 w-4 mr-2" />
                  Filters
                  {activeFilterCount > 0 && (
                    <Badge variant="default" className="ml-2 h-5 w-5 rounded-full p-0 text-xs flex items-center justify-center">
                      {activeFilterCount}
                    </Badge>
                  )}
                </Button>

                {/* Results count */}
                <p className="text-sm text-muted-foreground">
                  <span className="font-semibold text-foreground">{loading ? "..." : displayResources.length}</span> resources
                </p>
              </div>

              {/* Sort + Layout */}
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-2 text-sm">
                  <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as ResourceSortBy)}
                    className="text-sm border-none bg-transparent text-foreground focus:outline-none cursor-pointer font-medium"
                    aria-label="Sort by"
                  >
                    {SORT_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
                  aria-label={sortOrder === "asc" ? "Sort ascending" : "Sort descending"}
                >
                  {sortOrder === "asc" ? <SortAsc className="h-4 w-4" /> : <SortDesc className="h-4 w-4" />}
                </Button>
                <div className="flex items-center rounded-lg border border-input overflow-hidden">
                  <button
                    onClick={() => setViewLayout("grid")}
                    className={`flex h-8 w-8 items-center justify-center transition-colors ${
                      viewLayout === "grid" ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                    }`}
                    aria-label="Grid view"
                    aria-pressed={viewLayout === "grid"}
                  >
                    <LayoutGrid className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setViewLayout("list")}
                    className={`flex h-8 w-8 items-center justify-center transition-colors ${
                      viewLayout === "list" ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                    }`}
                    aria-label="List view"
                    aria-pressed={viewLayout === "list"}
                  >
                    <ListIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Active filter chips */}
            {filterChips.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 animate-fade-in">
                {filterChips.map((chip, i) => (
                  <FilterChip key={i} label={chip.label} onRemove={chip.onRemove} />
                ))}
                <button
                  onClick={clearFilters}
                  className="text-xs text-muted-foreground hover:text-foreground underline transition-colors"
                >
                  Clear all
                </button>
              </div>
            )}

            {/* Error banner */}
            {error && (
              <div className="p-4 rounded-xl flex items-start gap-3 text-sm bg-red-50 text-red-800 border border-red-200 animate-slide-up">
                <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium">Failed to load resources</p>
                  <p className="text-xs text-red-600 mt-0.5">{error}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={fetchResources} className="border-red-300 text-red-700 hover:bg-red-100">
                    <RefreshCw className="h-3.5 w-3.5 mr-1" />
                    Retry
                  </Button>
                  <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Resources Grid/List */}
            {!error && (
              <>
                {loading ? (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
                  </div>
                ) : displayResources.length === 0 ? (
                  <EmptyState
                    viewMode={viewMode}
                    hasFilters={activeFilterCount > 0 || !!searchQuery || searchResults !== null}
                    onClear={clearFilters}
                  />
                ) : viewLayout === "grid" ? (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {displayResources.map((resource, i) => (
                      <ResourceCard
                        key={resource.id}
                        resource={resource}
                        index={i}
                        onToggleFavorite={handleToggleFavorite}
                        onToggleBookmark={handleToggleBookmark}
                        onMarkComplete={handleMarkComplete}
                        onRecordView={handleRecordView}
                        onOpenDetail={handleOpenDetail}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {displayResources.map((resource, i) => (
                      <ResourceListItem
                        key={resource.id}
                        resource={resource}
                        index={i}
                        onToggleFavorite={handleToggleFavorite}
                        onToggleBookmark={handleToggleBookmark}
                        onMarkComplete={handleMarkComplete}
                        onRecordView={handleRecordView}
                        onOpenDetail={handleOpenDetail}
                      />
                    ))}
                  </div>
                )}

                {/* Load More */}
                {hasMore && !loading && (
                  <div className="flex justify-center pt-4">
                    <Button
                      variant="outline"
                      onClick={handleLoadMore}
                      disabled={loadingMore}
                      className="min-w-40"
                    >
                      {loadingMore ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        <>
                          Load More
                          <ArrowRight className="h-4 w-4 ml-2" />
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* ─── Mobile Filter Drawer ─── */}
        {showMobileFilters && (
          <div className="fixed inset-0 z-[100] flex lg:hidden">
            <div
              className="fixed inset-0 bg-black/50 backdrop-blur-sm animate-fade-in"
              onClick={() => setShowMobileFilters(false)}
            />
            <div className="relative flex w-full max-w-xs flex-1 flex-col bg-card animate-slide-in-left overflow-y-auto">
              <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-card px-4 py-3">
                <h2 className="font-semibold flex items-center gap-2">
                  <SlidersHorizontal className="h-4 w-4 text-primary" />
                  Filters
                </h2>
                <Button variant="ghost" size="icon" onClick={() => setShowMobileFilters(false)}>
                  <X className="h-5 w-5" />
                </Button>
              </div>
              <div className="p-4">
                <FilterPanel
                  filterSkill={filterSkill} setFilterSkill={setFilterSkill} setFilterSubSkill={setFilterSubSkill}
                  filterSubSkill={filterSubSkill} filterType={filterType} setFilterType={setFilterType}
                  filterDifficulty={filterDifficulty} setFilterDifficulty={setFilterDifficulty}
                  filterMinBand={filterMinBand} setFilterMinBand={setFilterMinBand} filterMaxBand={filterMaxBand} setFilterMaxBand={setFilterMaxBand}
                  filterDurationMin={filterDurationMin} setFilterDurationMin={setFilterDurationMin} filterDurationMax={filterDurationMax} setFilterDurationMax={setFilterDurationMax}
                  filterSource={filterSource} setFilterSource={setFilterSource}
                  filterFree={filterFree} setFilterFree={setFilterFree}
                  filterOfficial={filterOfficial} setFilterOfficial={setFilterOfficial}
                  filterVerified={filterVerified} setFilterVerified={setFilterVerified}
                  availableSubSkills={availableSubSkills} availableSources={availableSources}
                  clearFilters={clearFilters} activeFilterCount={activeFilterCount}
                />
              </div>
              <div className="sticky bottom-0 border-t border-border bg-card p-4">
                <Button className="w-full" onClick={() => setShowMobileFilters(false)}>
                  Show {displayResources.length} results
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ─── Resource Detail Modal ─── */}
        <ResourceDetailModal
          resource={selectedResource}
          onClose={() => setSelectedResource(null)}
          onToggleFavorite={handleToggleFavorite}
          onToggleBookmark={handleToggleBookmark}
          onMarkComplete={handleMarkComplete}
          onRecordView={handleRecordView}
        />
      </div>
    </DashboardLayout>
  );
}