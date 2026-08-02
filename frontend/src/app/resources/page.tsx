"use client";

import React, { useCallback, useEffect, useState } from "react";
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
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { resourcesService } from "@/services/api";
import type { ResourceItem } from "@/types";

type ResourceType = "Video" | "PDF" | "Website" | "Quiz" | "Flashcard";
type ResourceSkill = "Reading" | "Listening" | "Writing" | "Speaking" | "Vocabulary" | "Grammar";
type ResourceDifficulty = "beginner" | "intermediate" | "advanced" | "all_levels";

function ResourceTypeIcon({ type }: { type: ResourceType }) {
  const config: Record<ResourceType, { icon: any; color: string }> = {
    Video: { icon: Video, color: "text-red-500" },
    PDF: { icon: FileText, color: "text-blue-500" },
    Website: { icon: Globe, color: "text-green-500" },
    Quiz: { icon: HelpCircle, color: "text-purple-500" },
    Flashcard: { icon: Layers, color: "text-amber-500" },
  };
  const { icon: Icon, color } = config[type] || config.Video;
  return <Icon className={`h-4 w-4 ${color}`} />;
}

function SkillBadge({ skill }: { skill: ResourceSkill }) {
  const colors: Record<ResourceSkill, string> = {
    Reading: "bg-blue-100 text-blue-800",
    Listening: "bg-green-100 text-green-800",
    Writing: "bg-purple-100 text-purple-800",
    Speaking: "bg-pink-100 text-pink-800",
    Vocabulary: "bg-orange-100 text-orange-800",
    Grammar: "bg-teal-100 text-teal-800",
  };
  return <Badge className={`text-xs ${colors[skill]}`}>{skill}</Badge>;
}

function DifficultyBadge({ difficulty }: { difficulty?: ResourceDifficulty }) {
  if (!difficulty || difficulty === "all_levels") return null;
  const colors: Partial<Record<ResourceDifficulty, string>> = {
    beginner: "bg-green-100 text-green-800",
    intermediate: "bg-yellow-100 text-yellow-800",
    advanced: "bg-red-100 text-red-800",
  };
  return <Badge variant="outline" className={`text-xs ${colors[difficulty]}`}>{difficulty}</Badge>;
}

function RatingStars({ rating }: { rating?: number }) {
  if (rating === undefined || rating === null) return null;
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={`h-3 w-3 ${star <= Math.round(rating) ? "fill-amber-400 text-amber-400" : "text-gray-300"}`}
        />
      ))}
      <span className="text-xs text-muted-foreground ml-1">{rating.toFixed(1)}</span>
    </div>
  );
}

function ResourceCard({ resource, onEdit, onDelete }: { resource: ResourceItem; onEdit: (r: ResourceItem) => void; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="transition-all hover:shadow-md">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <ResourceTypeIcon type={resource.type} />
              <SkillBadge skill={resource.skill} />
              <DifficultyBadge difficulty={resource.difficulty} />
              {resource.verified && <Badge variant="success" className="text-xs"><ShieldCheck className="h-3 w-3 mr-1" />Verified</Badge>}
              {resource.official && <Badge variant="default" className="text-xs"><Crown className="h-3 w-3 mr-1" />Official</Badge>}
              {resource.is_free ? <Badge variant="secondary" className="text-xs"><Coins className="h-3 w-3 mr-1" />Free</Badge> : <Badge variant="outline" className="text-xs">Premium</Badge>}
            </div>
            <CardTitle className="text-base font-semibold line-clamp-2">{resource.title}</CardTitle>
            {resource.description && <CardDescription className="mt-1 line-clamp-2">{resource.description}</CardDescription>}
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={() => onEdit(resource)}><Edit3 className="h-4 w-4" /></Button>
            <Button variant="ghost" size="sm" onClick={() => onDelete(resource.id)}><Trash2 className="h-4 w-4" /></Button>
            <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>{expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1 text-muted-foreground"><Star className="h-4 w-4" /><span className="font-semibold">{resource.popularity_score}</span></div>
          {resource.rating && <RatingStars rating={resource.rating} />}
          {resource.estimated_time && <div className="flex items-center gap-1 text-muted-foreground"><Clock className="h-4 w-4" /><span>{resource.estimated_time} min</span></div>}
        </div>
        {expanded && (
          <div className="pt-3 border-t border-border space-y-3">
            {resource.author && <div><p className="text-xs font-semibold text-muted-foreground mb-1">Author</p><p className="text-sm">{resource.author}</p></div>}
            {resource.source && <div><p className="text-xs font-semibold text-muted-foreground mb-1">Source</p><p className="text-sm">{resource.source}</p></div>}
            {resource.sub_skill && <div><p className="text-xs font-semibold text-muted-foreground mb-1">Sub-Skill</p><p className="text-sm">{resource.sub_skill}</p></div>}
            {(resource.minimum_band || resource.maximum_band) && <div><p className="text-xs font-semibold text-muted-foreground mb-1">Band Range</p><p className="text-sm">{resource.minimum_band ?? 0} - {resource.maximum_band ?? 9.0}</p></div>}
            {resource.tags.length > 0 && <div><p className="text-xs font-semibold text-muted-foreground mb-1">Tags</p><div className="flex flex-wrap gap-1">{resource.tags.map((tag) => <Badge key={tag} variant="outline" className="text-xs"><Tag className="h-3 w-3 mr-1" />{tag}</Badge>)}</div></div>}
            {resource.url && <a href={resource.url} target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">Visit Resource →</a>}
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
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSkill, setFilterSkill] = useState<string>("");
  const [filterType, setFilterType] = useState<string>("");
  const [filterDifficulty, setFilterDifficulty] = useState<string>("");
  const [showFilters, setShowFilters] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingResource, setEditingResource] = useState<ResourceItem | null>(null);
  const [formData, setFormData] = useState<any>({});

  const fetchResources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResources([]);
    } catch (err: any) {
      setError(err?.message || "Failed to load resources");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResources();
  }, [fetchResources]);

  const handleCreate = () => {
    setEditingResource(null);
    setFormData({ type: "Video", skill: "Reading", is_free: true, difficulty: "intermediate" });
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
      setResources((prev) => prev.map((r) => (r.id === editingResource.id ? { ...formData, id: editingResource.id } : r)));
    } else {
      setResources((prev) => [...prev, { ...formData, id: `new-${Date.now()}`, created_at: new Date().toISOString() }]);
    }
    setShowForm(false);
    setFormData({});
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6 pb-12">
          <Skeleton className="h-12 w-64" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
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
          <Button variant="ghost" size="sm" onClick={fetchResources}>Retry</Button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 pb-12">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <BookOpen className="h-8 w-8 text-primary" />
              Resource Library
            </h1>
            <p className="text-muted-foreground">Manage learning resources for IELTS preparation</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)}>
              <Filter className="h-4 w-4 mr-2" />Filters
            </Button>
            <Button variant="outline" size="sm" onClick={fetchResources}>
              <RefreshCw className="h-4 w-4 mr-2" />Refresh
            </Button>
            <Button size="sm" onClick={handleCreate}>
              <Plus className="h-4 w-4 mr-2" />Add Resource
            </Button>
          </div>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search resources by title or description..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-10" />
        </div>

        {showFilters && (
          <Card>
            <CardHeader><CardTitle className="text-lg">Filters</CardTitle></CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Skill</label>
                  <select value={filterSkill} onChange={(e) => setFilterSkill(e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">
                    <option value="">All Skills</option>
                    <option value="Reading">Reading</option>
                    <option value="Listening">Listening</option>
                    <option value="Writing">Writing</option>
                    <option value="Speaking">Speaking</option>
                    <option value="Vocabulary">Vocabulary</option>
                    <option value="Grammar">Grammar</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Type</label>
                  <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">
                    <option value="">All Types</option>
                    <option value="Video">Video</option>
                    <option value="PDF">PDF</option>
                    <option value="Website">Website</option>
                    <option value="Quiz">Quiz</option>
                    <option value="Flashcard">Flashcard</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Difficulty</label>
                  <select value={filterDifficulty} onChange={(e) => setFilterDifficulty(e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">
                    <option value="">All Levels</option>
                    <option value="beginner">Beginner</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced</option>
                    <option value="all_levels">All Levels</option>
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {showForm && (
          <Card className="border-primary/20 bg-primary/5">
            <CardHeader>
              <CardTitle>{editingResource ? "Edit Resource" : "Add New Resource"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Title</label>
                  <Input value={formData.title || ""} onChange={(e) => setFormData((prev: any) => ({ ...prev, title: e.target.value }))} placeholder="Resource title" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Type</label>
                  <select value={formData.type || "Video"} onChange={(e) => setFormData((prev: any) => ({ ...prev, type: e.target.value }))} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="Video">Video</option>
                    <option value="PDF">PDF</option>
                    <option value="Website">Website</option>
                    <option value="Quiz">Quiz</option>
                    <option value="Flashcard">Flashcard</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Skill</label>
                  <select value={formData.skill || "Reading"} onChange={(e) => setFormData((prev: any) => ({ ...prev, skill: e.target.value }))} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="Reading">Reading</option>
                    <option value="Listening">Listening</option>
                    <option value="Writing">Writing</option>
                    <option value="Speaking">Speaking</option>
                    <option value="Vocabulary">Vocabulary</option>
                    <option value="Grammar">Grammar</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Difficulty</label>
                  <select value={formData.difficulty || "intermediate"} onChange={(e) => setFormData((prev: any) => ({ ...prev, difficulty: e.target.value }))} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="beginner">Beginner</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced</option>
                    <option value="all_levels">All Levels</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Author</label>
                  <Input value={formData.author || ""} onChange={(e) => setFormData((prev: any) => ({ ...prev, author: e.target.value }))} placeholder="Author name" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Source</label>
                  <Input value={formData.source || ""} onChange={(e) => setFormData((prev: any) => ({ ...prev, source: e.target.value }))} placeholder="Source name" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">URL</label>
                  <Input value={formData.url || ""} onChange={(e) => setFormData((prev: any) => ({ ...prev, url: e.target.value }))} placeholder="https://..." />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Estimated Time (minutes)</label>
                  <Input type="number" value={formData.estimated_time || ""} onChange={(e) => setFormData((prev: any) => ({ ...prev, estimated_time: parseInt(e.target.value) || 0 }))} placeholder="0" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Rating (0-5)</label>
                  <Input type="number" step="0.1" min="0" max="5" value={formData.rating || ""} onChange={(e) => setFormData((prev: any) => ({ ...prev, rating: parseFloat(e.target.value) || null }))} placeholder="0.0" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Popularity Score</label>
                  <Input type="number" min="0" value={formData.popularity_score || 0} onChange={(e) => setFormData((prev: any) => ({ ...prev, popularity_score: parseInt(e.target.value) || 0 }))} />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Description</label>
                <Textarea value={formData.description || ""} onChange={(e) => setFormData((prev: any) => ({ ...prev, description: e.target.value }))} placeholder="Resource description" rows={3} />
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={formData.is_free !== false} onChange={(e) => setFormData((prev: any) => ({ ...prev, is_free: e.target.checked }))} />
                  Free
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={formData.verified || false} onChange={(e) => setFormData((prev: any) => ({ ...prev, verified: e.target.checked }))} />
                  Verified
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={formData.official || false} onChange={(e) => setFormData((prev: any) => ({ ...prev, official: e.target.checked }))} />
                  Official
                </label>
              </div>
              <div className="flex items-center gap-2">
                <Button onClick={handleSave}><Save className="h-4 w-4 mr-2" />{editingResource ? "Update" : "Create"}</Button>
                <Button variant="outline" onClick={() => { setShowForm(false); setFormData({}); }}><X className="h-4 w-4 mr-2" />Cancel</Button>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">Resources</h2>
            <p className="text-sm text-muted-foreground">{resources.length} resource{resources.length !== 1 ? "s" : ""}</p>
          </div>

          {!resources || resources.length === 0 ? (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-8">
                  <BookOpen className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">No resources found</p>
                  <p className="text-xs text-muted-foreground mt-1">Try adjusting your filters or add a new resource</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {resources.map((resource) => (
                <ResourceCard key={resource.id} resource={resource} onEdit={handleEdit} onDelete={handleDelete} />
              ))}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}