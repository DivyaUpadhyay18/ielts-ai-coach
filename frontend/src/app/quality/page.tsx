"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Shield,
  TrendingUp,
  Award,
  Target,
  Star,
  Eye,
  Heart,
  CheckCircle2,
  RefreshCw,
  Loader2,
  Trophy,
  Gavel,
  BarChart3,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { resourceQualityService } from "@/services/api";
import { ModerationPanel } from "@/components/resources/resource-quality";
import type {
  ResourceQualityLeaderboardItem,
  ResourceQualityStats,
} from "@/types/resource-quality";

type Tab = "leaderboard" | "moderation" | "stats";

const SORT_OPTIONS = [
  { value: "recommendation_score", label: "Recommendation", icon: Award },
  { value: "quality_score", label: "Quality", icon: Shield },
  { value: "popularity_score", label: "Popularity", icon: TrendingUp },
  { value: "completion_score", label: "Completion", icon: Target },
];

function ScoreBadge({ score, label, icon: Icon }: { score: number; label: string; icon: React.ElementType }) {
  const color = score >= 75 ? "text-green-600 bg-green-50" : score >= 50 ? "text-amber-600 bg-amber-50" : "text-red-600 bg-red-50";
  return (
    <div className={`flex items-center gap-1.5 rounded-lg px-2 py-1 ${color}`}>
      <Icon className="h-3 w-3" />
      <span className="text-xs font-bold">{score.toFixed(0)}</span>
      <span className="text-[10px] opacity-70">{label}</span>
    </div>
  );
}

function LeaderboardTable({ items, loading }: { items: ResourceQualityLeaderboardItem[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(10)].map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardContent className="pt-12 pb-12">
          <div className="text-center space-y-2">
            <Trophy className="h-12 w-12 text-muted-foreground mx-auto opacity-50" />
            <p className="font-semibold">No scored resources yet</p>
            <p className="text-sm text-muted-foreground">
              Quality scores are computed when resources receive views, ratings, and feedback.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <Card key={item.resource_id} className="transition-all hover:shadow-md animate-stagger" style={{ animationDelay: `${Math.min(index * 50, 500)}ms` }}>
          <CardContent className="p-4">
            <div className="flex items-center gap-4">
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-bold ${
                index === 0 ? "bg-amber-100 text-amber-700" :
                index === 1 ? "bg-gray-100 text-gray-700" :
                index === 2 ? "bg-orange-100 text-orange-700" :
                "bg-muted text-muted-foreground"
              }`}>
                {index + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-sm truncate">{item.title}</h3>
                  <Badge variant="outline" className="text-xs shrink-0">{item.type}</Badge>
                  <Badge variant="outline" className="text-xs shrink-0">{item.skill}</Badge>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                    {item.avg_rating.toFixed(1)} ({item.rating_count})
                  </span>
                  <span className="flex items-center gap-1">
                    <Eye className="h-3 w-3" />
                    {item.view_count}
                  </span>
                  <span className="flex items-center gap-1">
                    <Heart className="h-3 w-3" />
                    {item.like_count}
                  </span>
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" />
                    {item.completion_count}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <ScoreBadge score={item.quality_score} label="Q" icon={Shield} />
                <ScoreBadge score={item.popularity_score} label="P" icon={TrendingUp} />
                <ScoreBadge score={item.completion_score} label="C" icon={Target} />
                <ScoreBadge score={item.recommendation_score} label="R" icon={Award} />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function StatsOverview({ stats, loading }: { stats: ResourceQualityStats | null; loading: boolean }) {
  if (loading || !stats) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[...Array(8)].map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }

  const statCards = [
    { label: "Total Feedback", value: stats.total_feedback, icon: BarChart3, color: "from-blue-500 to-indigo-600" },
    { label: "Pending", value: stats.pending_feedback, icon: RefreshCw, color: "from-amber-500 to-orange-600" },
    { label: "Approved", value: stats.approved_feedback, icon: CheckCircle2, color: "from-green-500 to-emerald-600" },
    { label: "Resolved", value: stats.resolved_feedback, icon: CheckCircle2, color: "from-blue-500 to-cyan-600" },
    { label: "Broken Links", value: stats.broken_link_reports, icon: Shield, color: "from-red-500 to-rose-600" },
    { label: "Corrections", value: stats.correction_suggestions, icon: Target, color: "from-purple-500 to-violet-600" },
    { label: "Suggestions", value: stats.better_resource_suggestions, icon: TrendingUp, color: "from-amber-500 to-yellow-600" },
    { label: "Resources Scored", value: stats.total_resources_scored, icon: Award, color: "from-indigo-500 to-purple-600" },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {statCards.map((stat) => {
        const Icon = stat.icon;
        return (
          <Card key={stat.label} className="overflow-hidden">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${stat.color} shadow-lg`}>
                  <Icon className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-2xl font-bold leading-none">{stat.value}</p>
                  <p className="text-xs text-muted-foreground mt-1">{stat.label}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
      <Card className="col-span-2 md:col-span-4">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            Average Scores Across All Resources
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <p className="text-3xl font-bold text-blue-600">{stats.avg_quality_score.toFixed(1)}</p>
              <p className="text-xs text-muted-foreground">Quality</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-amber-600">{stats.avg_popularity_score.toFixed(1)}</p>
              <p className="text-xs text-muted-foreground">Popularity</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-green-600">{stats.avg_completion_score.toFixed(1)}</p>
              <p className="text-xs text-muted-foreground">Completion</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-purple-600">{stats.avg_recommendation_score.toFixed(1)}</p>
              <p className="text-xs text-muted-foreground">Recommendation</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function QualityPage() {
  const [tab, setTab] = useState<Tab>("leaderboard");
  const [leaderboard, setLeaderboard] = useState<ResourceQualityLeaderboardItem[]>([]);
  const [stats, setStats] = useState<ResourceQualityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState("recommendation_score");
  const [recomputing, setRecomputing] = useState(false);

  const fetchLeaderboard = useCallback(async () => {
    setLoading(true);
    try {
      const response = await resourceQualityService.getLeaderboard({
        sort_by: sortBy,
        limit: 50,
      });
      setLeaderboard(response.items);
    } catch {
      setLeaderboard([]);
    } finally {
      setLoading(false);
    }
  }, [sortBy]);

  const fetchStats = useCallback(async () => {
    try {
      const data = await resourceQualityService.getStats();
      setStats(data);
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    fetchLeaderboard();
    fetchStats();
  }, [fetchLeaderboard, fetchStats]);

  const handleRecomputeAll = async () => {
    setRecomputing(true);
    try {
      await resourceQualityService.recomputeAll(100);
      fetchLeaderboard();
      fetchStats();
    } finally {
      setRecomputing(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="container mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Shield className="h-6 w-6 text-primary" />
              Resource Quality Scoring
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Quality scores, feedback, and moderation for the resource catalog
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={handleRecomputeAll} disabled={recomputing}>
            {recomputing ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            )}
            Recompute All
          </Button>
        </div>

        <div className="flex items-center gap-1 border-b">
          {([
            { key: "leaderboard", label: "Leaderboard", icon: Trophy },
            { key: "stats", label: "Statistics", icon: BarChart3 },
            { key: "moderation", label: "Moderation", icon: Gavel },
          ] as { key: Tab; label: string; icon: React.ElementType }[]).map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  tab === t.key
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="h-4 w-4" />
                {t.label}
              </button>
            );
          })}
        </div>

        {tab === "leaderboard" && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-muted-foreground">Sort by:</span>
              {SORT_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const isActive = sortBy === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => setSortBy(opt.value)}
                    className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
                      isActive
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-input hover:border-primary/30 hover:bg-muted/50"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {opt.label}
                  </button>
                );
              })}
            </div>
            <LeaderboardTable items={leaderboard} loading={loading} />
          </div>
        )}

        {tab === "stats" && <StatsOverview stats={stats} loading={!stats} />}

        {tab === "moderation" && <ModerationPanel />}
      </div>
    </DashboardLayout>
  );
}
