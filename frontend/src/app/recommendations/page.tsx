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
  Star,
  Clock,
  Tag,
  ShieldCheck,
  Crown,
  Coins,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Info,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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

function ScoreBadge({ score }: { score: number }) {
  const getColor = (s: number) => {
    if (s >= 80) return "bg-green-100 text-green-800";
    if (s >= 60) return "bg-blue-100 text-blue-800";
    if (s >= 40) return "bg-yellow-100 text-yellow-800";
    if (s >= 20) return "bg-orange-100 text-orange-800";
    return "bg-gray-100 text-gray-800";
  };
  return (
    <Badge className={`text-xs font-semibold ${getColor(score)}`}>
      {score.toFixed(1)}/100
    </Badge>
  );
}

function RecommendedResourceCard({
  resource,
  score,
  rationale,
  factors,
}: {
  resource: ResourceItem;
  score: number;
  rationale: string;
  factors?: Record<string, any>;
}) {
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
              <ScoreBadge score={score} />
              {resource.verified && <Badge variant="success" className="text-xs"><ShieldCheck className="h-3 w-3 mr-1" />Verified</Badge>}
              {resource.official && <Badge variant="default" className="text-xs"><Crown className="h-3 w-3 mr-1" />Official</Badge>}
              {resource.is_free ? <Badge variant="secondary" className="text-xs"><Coins className="h-3 w-3 mr-1" />Free</Badge> : <Badge variant="outline" className="text-xs">Premium</Badge>}
            </div>
            <CardTitle className="text-base font-semibold line-clamp-2">{resource.title}</CardTitle>
            {resource.description && <CardDescription className="mt-1 line-clamp-2">{resource.description}</CardDescription>}
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <span className="font-semibold">{score.toFixed(1)}</span>
          </div>
          {resource.popularity_score > 0 && (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Star className="h-4 w-4" />
              <span>{resource.popularity_score}</span>
            </div>
          )}
          {resource.rating && (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              <span>{resource.rating.toFixed(1)}</span>
            </div>
          )}
          {resource.estimated_time && (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>{resource.estimated_time} min</span>
            </div>
          )}
        </div>

        <div className="flex items-start gap-2">
          <Info className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
          <p className="text-sm text-muted-foreground">{rationale}</p>
        </div>

        {expanded && factors && (
          <div className="pt-3 border-t border-border">
            <p className="text-xs font-semibold text-muted-foreground mb-2">Relevance Factors</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {Object.entries(factors).map(([key, value]) => {
                if (key === "total") return null;
                return (
                  <div key={key} className="flex justify-between">
                    <span className="text-muted-foreground capitalize">{key.replace(/_/g, " ")}</span>
                    <span className="font-medium">{typeof value === "number" ? value.toFixed(1) : String(value)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function RecommendationsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSkill, setFilterSkill] = useState<string>("");
  const [filterType, setFilterType] = useState<string>("");
  const [limit, setLimit] = useState(10);
  const [showFilters, setShowFilters] = useState(false);
  const [contextInfo, setContextInfo] = useState<any>(null);

  const fetchRecommendations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = { limit };
      if (filterSkill) params.skill = filterSkill;
      if (filterType) params.type = filterType;
      if (searchQuery) params.search = searchQuery;

      setRecommendations([]);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || "Failed to load recommendations");
    } finally {
      setLoading(false);
    }
  }, [filterSkill, filterType, searchQuery, limit]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6 pb-12">
          <Skeleton className="h-12 w-80" />
          <Skeleton className="h-6 w-64" />
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-64 rounded-xl" />)}
          </div>
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
          <Button variant="ghost" size="sm" onClick={fetchRecommendations}>Retry</Button>
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
              <BarChart3 className="h-8 w-8 text-primary" />
              Recommended Resources
            </h1>
            <p className="text-muted-foreground">
              Personalized resource recommendations based on your IELTS profile
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)}>
              <Filter className="h-4 w-4 mr-2" />Filters
            </Button>
            <Button variant="outline" size="sm" onClick={fetchRecommendations}>
              <RefreshCw className="h-4 w-4 mr-2" />Refresh
            </Button>
          </div>
        </div>

        {contextInfo && (
          <Card className="border-secondary/20 bg-secondary/5">
            <CardHeader>
              <CardTitle className="text-lg">Your Profile</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-xs text-muted-foreground">Current Band</p>
                  <p className="text-2xl font-bold">{contextInfo.current_band ?? "N/A"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Target Band</p>
                  <p className="text-2xl font-bold">{contextInfo.target_band ?? "N/A"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Days Remaining</p>
                  <p className="text-2xl font-bold">{contextInfo.remaining_days ?? "N/A"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Weakest Skill</p>
                  <p className="text-2xl font-bold">{contextInfo.weakest_skill ?? "N/A"}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search recommended resources..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-10" />
        </div>

        {showFilters && (
          <Card>
            <CardHeader><CardTitle className="text-lg">Filters</CardTitle></CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Skill</label>
                  <select value={filterSkill} onChange={(e) => setFilterSkill(e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
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
                  <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="">All Types</option>
                    <option value="Video">Video</option>
                    <option value="PDF">PDF</option>
                    <option value="Website">Website</option>
                    <option value="Quiz">Quiz</option>
                    <option value="Flashcard">Flashcard</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Limit</label>
                  <select value={limit} onChange={(e) => setLimit(parseInt(e.target.value))} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value={5}>5 resources</option>
                    <option value={10}>10 resources</option>
                    <option value={20}>20 resources</option>
                    <option value={50}>50 resources</option>
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">Recommended for You</h2>
            <p className="text-sm text-muted-foreground">{recommendations.length} recommendation{recommendations.length !== 1 ? "s" : ""}</p>
          </div>

          {!recommendations || recommendations.length === 0 ? (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-8">
                  <BookOpen className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">No recommendations found</p>
                  <p className="text-xs text-muted-foreground mt-1">Check back later or adjust your filters</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {recommendations.map((item, index) => (
                <RecommendedResourceCard
                  key={item.resource?.id || `rec-${index}`}
                  resource={item.resource}
                  score={item.score}
                  rationale={item.rationale}
                  factors={item.relevance_factors}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}