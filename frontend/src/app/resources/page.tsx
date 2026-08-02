"use client";

import React, { useCallback, useEffect, useState, useMemo } from "react";
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
  Plus,
  Edit3,
  Trash2,
  Save,
  X,
  AlertCircle,
  Star,
  Clock,
  Tag,
  ShieldCheck,
  Crown,
  Coins,
  Loader2,
  ChevronDown,
  ChevronUp,
  Bookmark,
  BookmarkCheck,
  Eye,
  CheckCircle2,
  SortAsc,
  SortDesc,
  SlidersHorizontal,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { resourcesService } from "@/services/api";
import type { ResourceItem, ResourceFilters, ResourceSortBy, SortOrder } from "@/types";

const ResourceTypeIcon: Record<string, { icon: React.ElementType; color: string }> = {
  Video: { icon: Video, color: "text-red-500" },
  PDF: { icon: FileText, color: "text-blue-500" },
  Website: { icon: Globe, color: "text-green-500" },
  Quiz: { icon: HelpCircle, color: "text-purple-500" },
  Flashcard: { icon: Layers, color: "text-amber-500" },
};

const ResourceSkill: Record<string, string> = {
  Reading: "bg-blue-100 text-blue-800",
  Listening: "bg-green-100 text-green-800",
  Writing: "bg-purple-100 text-purple-800",
  Speaking: "bg-pink-100 text-pink-800",
  Vocabulary: "bg-orange-100 text-orange-800",
  Grammar: "bg-teal-100 text-teal-800",
};

const DifficultyBadge: Record<string, string> = {
  beginner: "bg-green-100 text-green-800",
  intermediate: "bg-yellow-100 text-yellow-800",
  advanced: "bg-red-100 text-red-800",
  all_levels: "bg-gray-100 text-gray-800",
};

const ALL_SKILLS = ["Reading", "Listening", "Writing", "Speaking", "Vocabulary", "Grammar"];
const ALL_TYPES = ["Video", "PDF", "Website", "Quiz", "Flashcard"];
const ALL_DIFFICULTIES = ["beginner", "intermediate", "advanced", "all_levels"];

function RatingStars({ rating }: { rating?: number }) {
  if (rating === undefined || rating === null) return null;
  const rounded = Math.round(rating);
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={`h-3 w-3 ${star <= rounded ? "fill-amber-400 text-amber-400" : "text-gray-300"}`}
        />
      ))}
      <span className="text-xs text-muted-foreground ml-1">{rating.toFixed(1)}</span>
    </div>
  );
}

function ResourceCard({
  resource,
  onEdit,
  onDelete,
  onToggleBookmark,
  onMarkComplete,
}: {
  resource: ResourceItem;
  onEdit: (r: ResourceItem) => void;
  onDelete: (id: string) => void;
  onToggleBookmark: (resource: ResourceItem) => void;
  onMarkComplete: (resource: ResourceItem) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const TypeIcon = ResourceTypeIcon[resource.type]?.icon || BookOpen;

  return (
    <Card
      className="group transition-all duration-300 hover:shadow-lg hover:-translate-y-1 cursor-pointer"
      onClick={() => {
        if (resource.url) {
          window.open(resource.url, "_blank", "noopener,noreferrer");
          onMarkComplete(resource);
        }
      }}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <TypeIcon className={`h-4 w-4 ${ResourceTypeIcon[resource.type]?.color || "text-gray-500"}`} />
              <Badge
                className={`text-xs ${ResourceSkill[resource.skill] || "bg-gray-100 text-gray-800"}`}
              >
                {resource.skill}
              </Badge>
              {resource.sub_skill && (
                <Badge variant="outline" className="text-xs">
                  {resource.sub_skill}
                </Badge>
              )}
              {resource.difficulty && resource.difficulty !== "all_levels" && (
                <Badge variant="outline" className={`text-xs ${DifficultyBadge[resource.difficulty] || ""}`}>
                  {resource.difficulty}
                </Badge>
              )}
              {resource.verified && (
                <Badge variant="success" className="text-xs">
                  <ShieldCheck className="h-3 w-3 mr-1" />
                  Verified
                </Badge>
              )}
              {resource.official && (
                <Badge variant="default" className="text-xs">
                  <Crown className="h-3 w-3 mr-1" />
                  Official
                </Badge>
              )}
            </div>
            <CardTitle className="text-base font-semibold line-clamp-2 group-hover:text-blue-600 transition-colors">
              {resource.title}
            </CardTitle>
            {resource.description && (
              <CardDescription className="mt-1 line-clamp-2 text-sm">
                {resource.description}
              </CardDescription>
            )}
          </div>

          <div
            className="flex items-center gap-1 flex-col opacity-60 group-hover:opacity-100 transition-opacity"
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onToggleBookmark(resource)}
              title={resource.is_bookmarked ? "Remove bookmark" : "Bookmark"}
            >
              {resource.is_bookmarked ? (
                <BookmarkCheck className="h-4 w-4 text-blue-500" />
              ) : (
                <Bookmark className="h-4 w-4" />
              )}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1 text-muted-foreground">
            <Star className="h-4 w-4" />
            <span className="font-semibold">{resource.popularity_score}</span>
          </div>
          {resource.rating !== undefined && <RatingStars rating={resource.rating} />}
          {resource.estimated_time && (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>{resource.estimated_time} min</span>
            </div>
          )}
          {resource.is_free ? (
            <Badge variant="secondary" className="text-xs">
              <Coins className="h-3 w-3 mr-1" />
              Free
            </Badge>
          ) : (
            <Badge variant="outline" className="text-xs">
              Premium
            </Badge>
          )}
          {resource.is_completed && (
            <Badge variant="outline" className="text-xs bg-green-50 text-green-700">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Completed
            </Badge>
          )}
        </div>

        {expanded && (
          <div className="pt-3 border-t border-border space-y-3 animate-in slide-in-from-top duration-200">
            {resource.author && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Author</p>
                <p className="text-sm">{resource.author}</p>
              </div>
            )}
            {resource.source && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Source</p>
                <p className="text-sm">{resource.source}</p>
              </div>
            )}
            {(resource.minimum_band || resource.maximum_band) && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Band Range</p>
                <p className="text-sm">
                  {resource.minimum_band ?? 0} - {resource.maximum_band ?? 9.0}
                </p>
              </div>
            )}
            {resource.tags && resource.tags.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Tags</p>
                <div className="flex flex-wrap gap-1">
                  {resource.tags.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      <Tag className="h-3 w-3 mr-1" />
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            {resource.url && (
              <a
                href={resource.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
                onClick={(e) => {
                  e.stopPropagation();
                  onMarkComplete(resource);
                }}
              >
                Visit Resource →
              </a>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function ResourcesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resources, setResources] = useState<ResourceItem[]>([]);

  // Search
  const [searchQuery, setSearchQuery] = useState("");

  // Filters
  const [filterSkill, setFilterSkill] = useState<string>("");
  const [filterSubSkill, setFilterSubSkill] = useState<string>("");
  const [filterType, setFilterType] = useState<string>("");
  const [filterDifficulty, setFilterDifficulty] = useState<string>("");
  const [filterMinBand, setFilterMinBand] = useState<string>("");
  const [filterMaxBand, setFilterMaxBand] = useState<string>("");
  const [filterDurationMin, setFilterDurationMin] = useState<string>("");
  const [filterDurationMax, setFilterDurationMax] = useState<string>("");
  const [filterSource, setFilterSource] = useState<string>("");
  const [filterFree, setFilterFree] = useState<boolean | undefined>(undefined);
  const [filterOfficial, setFilterOfficial] = useState<boolean | undefined>(undefined);
  const [filterVerified, setFilterVerified] = useState<boolean | undefined>(undefined);
  const [showFilters, setShowFilters] = useState(false);

  // View modes
  const [viewMode, setViewMode] = useState<"all" | "bookmarks" | "completed" | "recent">("all");

  // Sorting
  const [sortBy, setSortBy] = useState<ResourceSortBy>("popularity");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  // Data for filter dropdowns
  const [availableSubSkills, setAvailableSubSkills] = useState<string[]>([]);
  const [availableSources, setAvailableSources] = useState<string[]>([]);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingResource, setEditingResource] = useState<ResourceItem | null>(null);
  const [formData, setFormData] = useState<Partial<ResourceItem>>({});

  const buildFilters = (): ResourceFilters => ({
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
    official: filterOfficial,
    bookmarks_only: viewMode === "bookmarks" ? true : undefined,
    completed_only: viewMode === "completed" ? true : undefined,
    recently_viewed: viewMode === "recent" ? true : undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
    search: searchQuery || undefined,
  });

  const fetchResources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResources(await resourcesService.listAdvanced(buildFilters()));
    } catch (err: any) {
      setError(err?.message || "Failed to load resources");
    } finally {
      setLoading(false);
    }
  }, [filterSkill, filterSubSkill, filterType, filterDifficulty, filterMinBand, filterMaxBand, filterDurationMin, filterDurationMax, filterSource, viewMode, sortBy, sortOrder, searchQuery]);

  useEffect(() => {
    fetchResources();
  }, [fetchResources]);

  useEffect(() => {
    if (filterSkill) {
      resourcesService.getSubSkills(filterSkill)
        .then(setAvailableSubSkills)
        .catch(() => setAvailableSubSkills([]));
    } else {
      setAvailableSubSkills([]);
    }
  }, [filterSkill]);

  useEffect(() => {
    resourcesService.getSources()
      .then(setAvailableSources)
      .catch(() => setAvailableSources([]));
  }, []);

  const handleCreate = () => {
    setEditingResource(null);
    setFormData({ type: "Video", skill: "Reading", is_free: true, difficulty: "intermediate", tags: [] });
    setShowForm(true);
  };

  const handleEdit = (resource: ResourceItem) => {
    setEditingResource(resource);
    setFormData(resource);
    setShowForm(true);
  };

  const handleDelete = (id: string) => {
    setResources((prev) => prev.filter((r) => r.id !== id));
  };

  const handleSave = () => {
    if (editingResource) {
      setResources((prev) =>
        prev.map((r) => (r.id === editingResource.id ? { ...formData, id: editingResource.id } as ResourceItem : r))
      );
    } else {
      setResources((prev) =>
        [...prev, { ...formData, id: `new-${Date.now()}`, created_at: new Date().toISOString() } as ResourceItem]
      );
    }
    setShowForm(false);
    setFormData({});
  };

  const handleToggleBookmark = async (resource: ResourceItem) => {
    try {
      if (resource.is_bookmarked) {
        setResources((prev) =>
          prev.map((r) => (r.id === resource.id ? { ...r, is_bookmarked: false } : r))
        );
      } else {
        setResources((prev) =>
          prev.map((r) => (r.id === resource.id ? { ...r, is_bookmarked: true } : r))
        );
      }
    } catch (err: any) {
      setError(err?.message || "Could not update bookmark");
    }
  };

  const handleMarkComplete = async (resource: ResourceItem) => {
    try {
      await resourcesService.recordComplete(resource.id);
      setResources((prev) =>
        prev.map((r) => (r.id === resource.id ? { ...r, is_completed: true } : r))
      );
    } catch (err: any) {
      // Silently fail - completing is best-effort for tracking
    }
  };

  const clearFilters = () => {
    setFilterSkill("");
    setFilterSubSkill("");
    setFilterType("");
    setFilterDifficulty("");
    setFilterMinBand("");
    setFilterMaxBand("");
    setFilterDurationMin("");
    setFilterDurationMax("");
    setFilterSource("");
    setSearchQuery("");
    setSortBy("popularity");
    setSortOrder("desc");
  };

  const activeFilterCount = [
    filterSkill, filterSubSkill, filterType, filterDifficulty,
    filterMinBand, filterMaxBand, filterDurationMin, filterDurationMax,
    filterSource, searchQuery,
    filterFree, filterOfficial, filterVerified,
  ].filter(Boolean).length;

  if (loading && resources.length === 0) {
    return (
      <DashboardLayout>
        <div className="space-y-6 pb-12">
          <Skeleton className="h-12 w-64" />
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

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <BookOpen className="h-8 w-8 text-primary" />
              Resource Library
            </h1>
            <p className="text-muted-foreground">
              Browse, filter, and manage learning resources for IELTS preparation
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={showFilters ? "default" : "outline"}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="h-4 w-4 mr-2" />
              Filters
              {activeFilterCount > 0 && (
                <Badge variant="default" className="ml-2 h-5 w-5 rounded-full p-0 text-xs">
                  {activeFilterCount}
                </Badge>
              )}
            </Button>
            <Button variant="outline" size="sm" onClick={fetchResources}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
            <Button size="sm" onClick={handleCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Add Resource
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search resources by title, description, or tags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 h-12 text-base transition-all focus:ring-2 focus:ring-primary"
          />
        </div>

        {/* View Mode Tabs */}
        <div className="flex gap-2 overflow-x-auto pb-1">
          {[
            { key: "all", label: "All Resources", icon: BookOpen },
            { key: "bookmarks", label: "Bookmarks", icon: Bookmark },
            { key: "completed", label: "Completed", icon: CheckCircle2 },
            { key: "recent", label: "Recently Viewed", icon: Eye },
          ].map(({ key, label, icon: Icon }) => (
            <Button
              key={key}
              variant={viewMode === key ? "default" : "outline"}
              size="sm"
              className="flex items-center gap-1 whitespace-nowrap"
              onClick={() => setViewMode(key as typeof viewMode)}
            >
              <Icon className="h-3 w-3" />
              {label}
            </Button>
          ))}
        </div>

        {/* Sorting Bar */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Sort by:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as ResourceSortBy)}
              className="text-sm border-none bg-transparent text-foreground focus:outline-none focus:ring-0"
            >
              <option value="popularity">Popularity</option>
              <option value="rating">Rating</option>
              <option value="name">Name</option>
              <option value="time">Duration</option>
              <option value="created">Recently Added</option>
            </select>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
          >
            {sortOrder === "asc" ? <SortAsc className="h-4 w-4" /> : <SortDesc className="h-4 w-4" />}
          </Button>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="p-4 rounded-lg flex items-center gap-3 text-sm bg-red-50 text-red-800 border border-red-200 animate-in slide-in-from-top duration-200">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-400 hover:text-red-600"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Filters Panel */}
        {showFilters && (
          <Card className="animate-in slide-in-from-top duration-200">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Filters</CardTitle>
                {activeFilterCount > 0 && (
                  <Button variant="ghost" size="sm" onClick={clearFilters}>
                    Clear All ({activeFilterCount})
                  </Button>
                )}
              </div>
              <CardDescription>Narrow down your resource search</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Skill</label>
                  <select
                    value={filterSkill}
                    onChange={(e) => {
                      setFilterSkill(e.target.value);
                      setFilterSubSkill("");
                    }}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="">All Skills</option>
                    {ALL_SKILLS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>

                {filterSkill && availableSubSkills.length > 0 && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Sub-Skill</label>
                    <select
                      value={filterSubSkill}
                      onChange={(e) => setFilterSubSkill(e.target.value)}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">All Sub-Skills</option>
                      {availableSubSkills.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-sm font-medium">Resource Type</label>
                  <select
                    value={filterType}
                    onChange={(e) => setFilterType(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="">All Types</option>
                    {ALL_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Difficulty</label>
                  <select
                    value={filterDifficulty}
                    onChange={(e) => setFilterDifficulty(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="">All Levels</option>
                    {ALL_DIFFICULTIES.map((d) => (
                      <option key={d} value={d}>
                        {d.charAt(0).toUpperCase() + d.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Min Band</label>
                  <Input
                    type="number"
                    step="0.5"
                    min="0"
                    max="9"
                    value={filterMinBand}
                    onChange={(e) => setFilterMinBand(e.target.value)}
                    placeholder="e.g. 6.0"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Max Band</label>
                  <Input
                    type="number"
                    step="0.5"
                    min="0"
                    max="9"
                    value={filterMaxBand}
                    onChange={(e) => setFilterMaxBand(e.target.value)}
                    placeholder="e.g. 8.5"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Min Duration (min)</label>
                  <Input
                    type="number"
                    min="0"
                    value={filterDurationMin}
                    onChange={(e) => setFilterDurationMin(e.target.value)}
                    placeholder="e.g. 10"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Max Duration (min)</label>
                  <Input
                    type="number"
                    min="0"
                    value={filterDurationMax}
                    onChange={(e) => setFilterDurationMax(e.target.value)}
                    placeholder="e.g. 60"
                  />
                </div>

                {availableSources.length > 0 && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Source</label>
                    <select
                      value={filterSource}
                      onChange={(e) => setFilterSource(e.target.value)}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">All Sources</option>
                      {availableSources.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-sm font-medium">Free Only</label>
                  <select
                    value={String(filterFree)}
                    onChange={(e) => setFilterFree(e.target.value === "" ? undefined : e.target.value === "true")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="">Any</option>
                    <option value="true">Free Only</option>
                    <option value="false">Premium Only</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Official Only</label>
                  <select
                    value={String(filterOfficial)}
                    onChange={(e) => setFilterOfficial(e.target.value === "" ? undefined : e.target.value === "true")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="">Any</option>
                    <option value="true">Official Only</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Verified Only</label>
                  <select
                    value={String(filterVerified)}
                    onChange={(e) => setFilterVerified(e.target.value === "" ? undefined : e.target.value === "true")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="">Any</option>
                    <option value="true">Verified Only</option>
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Results Summary */}
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold">{resources.length}</span> resource
            {resources.length !== 1 ? "s" : ""} found
            {activeFilterCount > 0 && (
              <span className="ml-2 text-xs">({activeFilterCount} active filter{activeFilterCount !== 1 ? "s" : ""})</span>
            )}
          </p>
        </div>

        {/* Resources Grid */}
        {!resources || resources.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-12">
                <BookOpen className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">No resources found</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Try adjusting your filters or search terms
                </p>
                {(searchQuery || activeFilterCount > 0) && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-4"
                    onClick={clearFilters}
                  >
                    Clear all filters
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {resources.map((resource) => (
              <ResourceCard
                key={resource.id}
                resource={resource}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onToggleBookmark={handleToggleBookmark}
                onMarkComplete={handleMarkComplete}
              />
            ))}
          </div>
        )}

        {/* Create/Edit Form */}
        {showForm && (
          <Card className="border-primary/20 bg-primary/5 animate-in slide-in-from-bottom duration-300">
            <CardHeader>
              <CardTitle>{editingResource ? "Edit Resource" : "Add New Resource"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Title</label>
                  <Input
                    value={formData.title || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
                    placeholder="Resource title"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Type</label>
                  <select
                    value={formData.type || "Video"}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, type: e.target.value as ResourceItem["type"] }))
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="Video">Video</option>
                    <option value="PDF">PDF</option>
                    <option value="Website">Website</option>
                    <option value="Quiz">Quiz</option>
                    <option value="Flashcard">Flashcard</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Skill</label>
                  <select
                    value={formData.skill || "Reading"}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, skill: e.target.value as ResourceItem["skill"] }))
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="Reading">Reading</option>
                    <option value="Listening">Listening</option>
                    <option value="Writing">Writing</option>
                    <option value="Speaking">Speaking</option>
                    <option value="Vocabulary">Vocabulary</option>
                    <option value="Grammar">Grammar</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Sub-Skill</label>
                  <Input
                    value={formData.sub_skill || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, sub_skill: e.target.value }))}
                    placeholder="e.g. Task 1, Part 2..."
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Difficulty</label>
                  <select
                    value={formData.difficulty || "intermediate"}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, difficulty: e.target.value as ResourceItem["difficulty"] }))
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="beginner">Beginner</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced</option>
                    <option value="all_levels">All Levels</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Duration (min)</label>
                  <Input
                    type="number"
                    value={formData.estimated_time || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, estimated_time: parseInt(e.target.value) || 0 }))}
                    placeholder="0"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Min Band</label>
                  <Input
                    type="number"
                    step="0.5"
                    value={formData.minimum_band || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, minimum_band: parseFloat(e.target.value) || undefined }))}
                    placeholder="0.0"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Max Band</label>
                  <Input
                    type="number"
                    step="0.5"
                    value={formData.maximum_band || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, maximum_band: parseFloat(e.target.value) || undefined }))}
                    placeholder="9.0"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Author</label>
                  <Input
                    value={formData.author || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, author: e.target.value }))}
                    placeholder="Author name"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Source</label>
                  <Input
                    value={formData.source || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, source: e.target.value }))}
                    placeholder="Source name"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">URL</label>
                  <Input
                    value={formData.url || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, url: e.target.value }))}
                    placeholder="https://..."
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Thumbnail URL</label>
                  <Input
                    value={formData.thumbnail || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, thumbnail: e.target.value }))}
                    placeholder="https://..."
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Tags (comma separated)</label>
                  <Input
                    value={formData.tags?.join(", ") || ""}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean),
                      }))
                    }
                    placeholder="tag1, tag2, tag3"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Rating (0-5)</label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="5"
                    value={formData.rating || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, rating: parseFloat(e.target.value) || undefined }))}
                    placeholder="0.0"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Description</label>
                <Textarea
                  value={formData.description || ""}
                  onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="Resource description"
                  rows={3}
                />
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.is_free !== false}
                    onChange={(e) => setFormData((prev) => ({ ...prev, is_free: e.target.checked }))}
                  />
                  Free
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.verified || false}
                    onChange={(e) => setFormData((prev) => ({ ...prev, verified: e.target.checked }))}
                  />
                  Verified
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.official || false}
                    onChange={(e) => setFormData((prev) => ({ ...prev, official: e.target.checked }))}
                  />
                  Official
                </label>
              </div>

              <div className="flex items-center gap-2">
                <Button onClick={handleSave}>
                  <Save className="h-4 w-4 mr-2" />
                  {editingResource ? "Update" : "Create"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowForm(false);
                    setFormData({});
                  }}
                >
                  <X className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}