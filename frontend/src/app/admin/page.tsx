"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Shield,
  Users,
  BookOpen,
  CheckCircle2,
  XCircle,
  Clock,
  Star,
  Eye,
  TrendingUp,
  AlertCircle,
  Search,
  Plus,
  Upload,
  Pencil,
  Trash2,
  Filter,
  RefreshCw,
  ShieldCheck,
  ShieldX,
  Check,
  X,
  FileText,
  Video,
  Globe,
  HelpCircle,
  Layers,
  Crown,
  Coins,
  Award,
  Activity,
  BarChart3,
  Download,
  Loader2,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Target,
  Zap,
  Flame,
  GraduationCap,
  Settings,
  Lock,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Modal } from "@/components/ui/modal";
import { adminService, resourcesService } from "@/services/api";
import { useAuthStore } from "@/app/store/useAuthStore";
import type {
  AdminStats,
  AdminAnalytics,
  AdminUser,
  ResourceSuggestion,
  ResourceSuggestionUpdatePayload,
  AuditLogEntry,
  UserRole,
  ROLE_LABELS,
  Category,
} from "@/types/admin";
import type { ResourceItem, ResourceCreatePayload, ResourceUpdatePayload, ResourceType, ResourceSkill, ResourceDifficulty } from "@/types";

// ─── Constants ──────────────────────────────────────────────────────────────

const RESOURCE_TYPES = ["Video", "PDF", "Website", "Quiz", "Flashcard"];
const RESOURCE_SKILLS = ["Reading", "Listening", "Writing", "Speaking", "Vocabulary", "Grammar"];
const DIFFICULTIES = ["beginner", "intermediate", "advanced", "all_levels"];

const TYPE_META: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  Video: { icon: Video, color: "text-red-600", bg: "bg-red-100" },
  PDF: { icon: FileText, color: "text-blue-600", bg: "bg-blue-100" },
  Website: { icon: Globe, color: "text-green-600", bg: "bg-green-100" },
  Quiz: { icon: HelpCircle, color: "text-purple-600", bg: "bg-purple-100" },
  Flashcard: { icon: Layers, color: "text-amber-600", bg: "bg-amber-100" },
};

const SKILL_META: Record<string, { color: string; bg: string }> = {
  Reading: { color: "text-blue-700", bg: "bg-blue-50" },
  Listening: { color: "text-green-700", bg: "bg-green-50" },
  Writing: { color: "text-purple-700", bg: "bg-purple-50" },
  Speaking: { color: "text-pink-700", bg: "bg-pink-50" },
  Vocabulary: { color: "text-orange-700", bg: "bg-orange-50" },
  Grammar: { color: "text-teal-700", bg: "bg-teal-50" },
};

const ROLE_BADGES: Record<UserRole, { color: string; bg: string }> = {
  user: { color: "text-slate-700", bg: "bg-slate-100" },
  moderator: { color: "text-blue-700", bg: "bg-blue-100" },
  admin: { color: "text-purple-700", bg: "bg-purple-100" },
  super_admin: { color: "text-amber-700", bg: "bg-amber-100" },
};

type AdminTab = "overview" | "resources" | "suggestions" | "users" | "audit";

// ─── Helper Components ──────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  bg,
  sub,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
  bg: string;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <div className={`p-2 rounded-lg ${bg} ${color}`}>
            <Icon className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <h3 className="text-3xl font-bold">{value}</h3>
        </div>
        {sub && <p className="mt-1 text-[11px] text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function ResourceFormModal({
  resource,
  onClose,
  onSave,
}: {
  resource: ResourceItem | null;
  onClose: () => void;
  onSave: (data: ResourceCreatePayload) => Promise<void>;
}) {
  const [form, setForm] = useState<ResourceCreatePayload>(() => ({
    title: resource?.title || "",
    description: resource?.description || "",
    type: ((resource?.type as ResourceType) ?? "Video") as ResourceType,
    source: resource?.source || "",
    author: resource?.author || "",
    url: resource?.url || "",
    thumbnail: resource?.thumbnail || "",
    skill: ((resource?.skill as ResourceSkill) ?? "Reading") as ResourceSkill,
    sub_skill: resource?.sub_skill || "",
    minimum_band: resource?.minimum_band,
    maximum_band: resource?.maximum_band,
    difficulty: ((resource?.difficulty as ResourceDifficulty) ?? "intermediate") as ResourceDifficulty,
    estimated_time: resource?.estimated_time || 15,
    tags: resource?.tags || [],
    language: resource?.language || "en",
    verified: resource?.verified ?? false,
    official: resource?.official ?? false,
    is_free: resource?.is_free ?? true,
    rating: resource?.rating,
    popularity_score: resource?.popularity_score ?? 0,
  }));
  const [tagsInput, setTagsInput] = useState((resource?.tags || []).join(", "));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const tags = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
      await onSave({ ...form, tags });
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to save resource");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={!!resource || true} onClose={onClose} className="max-w-2xl p-0 overflow-hidden">
      <div className="p-6 space-y-4 max-h-[calc(100vh-8rem)] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">{resource ? "Edit Resource" : "Add Resource"}</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-muted">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-error/10 text-error text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Title *</label>
              <Input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
                className="mt-1"
              />
            </div>

            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Description</label>
              <textarea
                value={form.description || ""}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[80px]"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Type *</label>
              <select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value as ResourceType })}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                {RESOURCE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Skill *</label>
              <select
                value={form.skill}
                onChange={(e) => setForm({ ...form, skill: e.target.value as ResourceSkill })}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                {RESOURCE_SKILLS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">URL *</label>
              <Input
                value={form.url || ""}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="https://..."
                required
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Source</label>
              <Input
                value={form.source || ""}
                onChange={(e) => setForm({ ...form, source: e.target.value })}
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Author</label>
              <Input
                value={form.author || ""}
                onChange={(e) => setForm({ ...form, author: e.target.value })}
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Difficulty</label>
              <select
                value={form.difficulty}
                onChange={(e) => setForm({ ...form, difficulty: e.target.value as ResourceDifficulty })}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

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
              <label className="text-xs font-medium text-muted-foreground">Min Band</label>
              <Input
                type="number"
                step="0.5"
                min="0"
                max="9"
                value={form.minimum_band ?? ""}
                onChange={(e) => setForm({ ...form, minimum_band: e.target.value ? parseFloat(e.target.value) : undefined })}
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Max Band</label>
              <Input
                type="number"
                step="0.5"
                min="0"
                max="9"
                value={form.maximum_band ?? ""}
                onChange={(e) => setForm({ ...form, maximum_band: e.target.value ? parseFloat(e.target.value) : undefined })}
                className="mt-1"
              />
            </div>

            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Tags (comma-separated)</label>
              <Input
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="ielts, writing, task2"
                className="mt-1"
              />
            </div>

            <div className="md:col-span-2 flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.verified}
                  onChange={(e) => setForm({ ...form, verified: e.target.checked })}
                  className="h-4 w-4"
                />
                Verified
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.official}
                  onChange={(e) => setForm({ ...form, official: e.target.checked })}
                  className="h-4 w-4"
                />
                Official
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_free}
                  onChange={(e) => setForm({ ...form, is_free: e.target.checked })}
                  className="h-4 w-4"
                />
                Free
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              {resource ? "Save Changes" : "Create Resource"}
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
}

function BulkUploadModal({
  onClose,
  onUpload,
}: {
  onClose: () => void;
  onUpload: (resources: ResourceCreatePayload[]) => Promise<void>;
}) {
  const [jsonInput, setJsonInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const parsed = JSON.parse(jsonInput);
      if (!Array.isArray(parsed)) throw new Error("Input must be a JSON array");
      await onUpload(parsed);
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to parse JSON or upload resources");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} className="max-w-2xl p-0 overflow-hidden">
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">Bulk Upload Resources</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-muted">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-error/10 text-error text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground">
              JSON Array of Resources (max 500)
            </label>
            <textarea
              value={jsonInput}
              onChange={(e) => setJsonInput(e.target.value)}
              className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono min-h-[300px]"
              placeholder={`[
  {
    "title": "IELTS Writing Task 2 Guide",
    "type": "PDF",
    "skill": "Writing",
    "url": "https://example.com/guide.pdf",
    "difficulty": "intermediate",
    "estimated_time": 30
  }
]`}
              required
            />
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
              Upload Resources
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
}

function SuggestionEditModal({
  suggestion,
  onClose,
  onSave,
}: {
  suggestion: ResourceSuggestion;
  onClose: () => void;
  onSave: (data: ResourceSuggestionUpdatePayload) => Promise<void>;
}) {
  const [form, setForm] = useState<ResourceSuggestionUpdatePayload>(() => ({
    title: suggestion.title,
    description: suggestion.description || "",
    category: suggestion.category,
    reason: suggestion.reason || "",
    type: suggestion.type,
    source: suggestion.source || "",
    author: suggestion.author || "",
    url: suggestion.url || "",
    skill: suggestion.skill,
    sub_skill: suggestion.sub_skill || "",
    minimum_band: suggestion.minimum_band,
    maximum_band: suggestion.maximum_band,
    difficulty: suggestion.difficulty,
    estimated_time: suggestion.estimated_time,
    tags: suggestion.tags || [],
    language: suggestion.language || "en",
    is_free: suggestion.is_free ?? true,
    admin_notes: suggestion.admin_notes || "",
  }));
  const [tagsInput, setTagsInput] = useState((suggestion.tags || []).join(", "));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const tags = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
      await onSave({ ...form, tags });
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to save suggestion");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} className="max-w-2xl p-0 overflow-hidden">
      <div className="p-6 space-y-4 max-h-[calc(100vh-8rem)] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">Edit Suggestion</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-muted">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-error/10 text-error text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Title *</label>
              <Input
                value={form.title || ""}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
                className="mt-1"
              />
            </div>

            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Description</label>
              <textarea
                value={form.description || ""}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[80px]"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Category *</label>
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value as Category })}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                {(["YouTube Video", "PDF", "Website", "Practice Test", "Vocabulary List"] as Category[]).map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Skill *</label>
              <select
                value={form.skill}
                onChange={(e) => setForm({ ...form, skill: e.target.value })}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                {RESOURCE_SKILLS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Reason</label>
              <Input
                value={form.reason || ""}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                placeholder="Why is this resource valuable?"
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">URL</label>
              <Input
                value={form.url || ""}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="https://..."
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Source</label>
              <Input
                value={form.source || ""}
                onChange={(e) => setForm({ ...form, source: e.target.value })}
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Author</label>
              <Input
                value={form.author || ""}
                onChange={(e) => setForm({ ...form, author: e.target.value })}
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Difficulty</label>
              <select
                value={form.difficulty || "intermediate"}
                onChange={(e) => setForm({ ...form, difficulty: e.target.value })}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

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
              <label className="text-xs font-medium text-muted-foreground">Min Band</label>
              <Input
                type="number"
                step="0.5"
                min="0"
                max="9"
                value={form.minimum_band ?? ""}
                onChange={(e) => setForm({ ...form, minimum_band: e.target.value ? parseFloat(e.target.value) : undefined })}
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground">Max Band</label>
              <Input
                type="number"
                step="0.5"
                min="0"
                max="9"
                value={form.maximum_band ?? ""}
                onChange={(e) => setForm({ ...form, maximum_band: e.target.value ? parseFloat(e.target.value) : undefined })}
                className="mt-1"
              />
            </div>

            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Tags (comma-separated)</label>
              <Input
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="ielts, writing, task2"
                className="mt-1"
              />
            </div>

            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Admin Notes</label>
              <Input
                value={form.admin_notes || ""}
                onChange={(e) => setForm({ ...form, admin_notes: e.target.value })}
                placeholder="Review notes..."
                className="mt-1"
              />
            </div>

            <div className="md:col-span-2 flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_free ?? true}
                  onChange={(e) => setForm({ ...form, is_free: e.target.checked })}
                  className="h-4 w-4"
                />
                Free
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Save Changes
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<AdminTab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [analytics, setAnalytics] = useState<AdminAnalytics | null>(null);
  const [resources, setResources] = useState<ResourceItem[]>([]);
  const [suggestions, setSuggestions] = useState<ResourceSuggestion[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);

  // UI state
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
const [editingResource, setEditingResource] = useState<ResourceItem | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [editingSuggestion, setEditingSuggestion] = useState<ResourceSuggestion | null>(null);
  const [suggestionFilter, setSuggestionFilter] = useState<"pending" | "approved" | "rejected">("pending");

  const isAdmin = user?.role === "admin" || user?.role === "super_admin";
  const isSuperAdmin = user?.role === "super_admin";

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsData, analyticsData, resourcesData, suggestionsData, usersData, auditData] = await Promise.all([
        adminService.getStats(),
        adminService.getAdminAnalytics(),
        resourcesService.listAdvanced({ limit: 100 }),
        adminService.getSuggestions({ status: suggestionFilter, limit: 50 }),
        adminService.listUsers({ limit: 50 }),
        adminService.getAuditLog({ limit: 50 }),
      ]);
      setStats(statsData);
      setAnalytics(analyticsData);
      setResources(resourcesData);
      setSuggestions(suggestionsData);
      setUsers(usersData);
      setAuditLog(auditData);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, [suggestionFilter]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // ─── Resource CRUD ────────────────────────────────────────────
  const handleCreateResource = async (data: ResourceCreatePayload) => {
    await resourcesService.create(data);
    await fetchAll();
  };

  const handleUpdateResource = async (data: ResourceCreatePayload) => {
    if (!editingResource) return;
    await resourcesService.update(editingResource.id, data as ResourceUpdatePayload);
    setEditingResource(null);
    await fetchAll();
  };

  const handleDeleteResource = async (resourceId: string) => {
    if (!confirm("Delete this resource?")) return;
    await resourcesService.delete(resourceId);
    await fetchAll();
  };

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    if (!confirm(`Delete ${selectedIds.length} selected resources?`)) return;
    await adminService.bulkDelete(selectedIds);
    setSelectedIds([]);
    await fetchAll();
  };

  const handleBulkUpload = async (resources: ResourceCreatePayload[]) => {
    await adminService.bulkUpload(resources);
    await fetchAll();
  };

  // ─── Verification ─────────────────────────────────────────────
  const handleVerify = async (resourceId: string) => {
    await adminService.verifyResource(resourceId);
    await fetchAll();
  };

  const handleUnverify = async (resourceId: string) => {
    await adminService.unverifyResource(resourceId);
    await fetchAll();
  };

  // ─── Suggestions ──────────────────────────────────────────────
  const handleApproveSuggestion = async (suggestionId: string) => {
    await adminService.approveSuggestion(suggestionId);
    await fetchAll();
  };

const handleRejectSuggestion = async (suggestionId: string) => {
    await adminService.rejectSuggestion(suggestionId);
    await fetchAll();
  };

const handleUpdateSuggestion = async (data: ResourceSuggestionUpdatePayload) => {
    if (!editingSuggestion) return;
    await adminService.editSuggestion(editingSuggestion.id, data);
    setEditingSuggestion(null);
    await fetchAll();
  };

  // ─── User Management ──────────────────────────────────────────
  const handleRoleChange = async (userId: string, role: UserRole) => {
    await adminService.updateUserRole(userId, role);
    await fetchAll();
  };

  const handleToggleUserStatus = async (userId: string, isActive: boolean) => {
    await adminService.updateUserStatus(userId, !isActive);
    await fetchAll();
  };

  // ─── Filtered resources ───────────────────────────────────────
  const filteredResources = useMemo(() => {
    if (!searchQuery) return resources;
    const q = searchQuery.toLowerCase();
    return resources.filter((r) =>
      r.title?.toLowerCase().includes(q) ||
      r.skill?.toLowerCase().includes(q) ||
      r.type?.toLowerCase().includes(q) ||
      r.source?.toLowerCase().includes(q)
    );
  }, [resources, searchQuery]);

  if (!isAdmin) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center py-32 text-center space-y-4">
          <div className="p-4 rounded-full bg-error/10 text-error">
            <Lock className="h-10 w-10" />
          </div>
          <h2 className="text-2xl font-bold">Admin Access Required</h2>
          <p className="text-muted-foreground max-w-md">
            You need admin or super_admin role to access this dashboard.
          </p>
        </div>
      </DashboardLayout>
    );
  }

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
          </div>
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </DashboardLayout>
    );
  }

  const tabs: { key: AdminTab; label: string; icon: React.ElementType }[] = [
    { key: "overview", label: "Overview", icon: BarChart3 },
    { key: "resources", label: "Resources", icon: BookOpen },
    { key: "suggestions", label: "Suggestions", icon: Sparkles },
    { key: "users", label: "Users", icon: Users },
    { key: "audit", label: "Audit Log", icon: Activity },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-8 pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Shield className="h-8 w-8 text-primary" />
              Admin Dashboard
            </h1>
            <p className="text-muted-foreground">
              Manage resources, approve suggestions, and monitor platform health.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="h-8 px-3">
              <ShieldCheck className="mr-1 h-3.5 w-3.5" />
              {user?.role === "super_admin" ? "Super Admin" : "Admin"}
            </Badge>
            <Button variant="outline" size="sm" onClick={fetchAll}>
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-3 rounded-xl border border-error/30 bg-error/5 p-4 text-error">
            <AlertCircle className="h-5 w-5" />
            <p className="text-sm font-medium flex-1">{error}</p>
            <Button variant="ghost" size="sm" onClick={fetchAll}>Retry</Button>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 overflow-x-auto pb-1">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition-all ${
                activeTab === key
                  ? "bg-primary text-primary-foreground shadow-md"
                  : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* ─── Overview Tab ─────────────────────────────────────── */}
        {activeTab === "overview" && (
          <div className="space-y-8">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Total Users" value={stats?.total_users ?? 0} icon={Users} color="text-blue-600" bg="bg-blue-100" sub={`${stats?.active_users ?? 0} active`} />
              <StatCard label="Total Resources" value={stats?.total_resources ?? 0} icon={BookOpen} color="text-emerald-600" bg="bg-emerald-100" sub={`${stats?.verified_resources ?? 0} verified`} />
              <StatCard label="Pending Suggestions" value={stats?.pending_suggestions ?? 0} icon={Sparkles} color="text-amber-600" bg="bg-amber-100" sub="Awaiting review" />
              <StatCard label="Total Views" value={stats?.total_views ?? 0} icon={Eye} color="text-purple-600" bg="bg-purple-100" sub={`${stats?.total_completions ?? 0} completions`} />
            </div>

            <div className="grid gap-8 lg:grid-cols-2">
              {/* Resource Analytics */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-primary" /> Resource Analytics
                  </CardTitle>
                  <CardDescription>Catalog health and engagement metrics.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-muted/50 p-3">
                      <p className="text-xs text-muted-foreground">Published</p>
                      <p className="text-2xl font-bold">{analytics?.published_count ?? 0}</p>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-3">
                      <p className="text-xs text-muted-foreground">Unpublished</p>
                      <p className="text-2xl font-bold">{analytics?.unpublished_count ?? 0}</p>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-3">
                      <p className="text-xs text-muted-foreground">Verified</p>
                      <p className="text-2xl font-bold">{analytics?.verified_count ?? 0}</p>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-3">
                      <p className="text-xs text-muted-foreground">Free</p>
                      <p className="text-2xl font-bold">{analytics?.free_count ?? 0}</p>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-2">By Type</p>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(analytics?.by_type ?? {}).map(([type, count]) => {
                        const meta = TYPE_META[type] || TYPE_META.Video;
                        const Icon = meta.icon;
                        return (
                          <Badge key={type} variant="outline" className={`${meta.bg} ${meta.color} border-0`}>
                            <Icon className="h-3 w-3 mr-1" /> {type}: {count}
                          </Badge>
                        );
                      })}
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-2">By Skill</p>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(analytics?.by_skill ?? {}).map(([skill, count]) => {
                        const meta = SKILL_META[skill] || { color: "text-slate-700", bg: "bg-slate-100" };
                        return (
                          <Badge key={skill} variant="outline" className={`${meta.bg} ${meta.color} border-0`}>
                            {skill}: {count}
                          </Badge>
                        );
                      })}
                    </div>
                  </div>

                  <div className="pt-3 border-t">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Avg Rating</span>
                      <span className="font-bold flex items-center gap-1">
                        <Star className="h-3.5 w-3.5 text-amber-500 fill-amber-500" />
                        {analytics?.avg_rating ? analytics.avg_rating.toFixed(1) : "—"}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Top Resources */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-primary" /> Top Resources
                  </CardTitle>
                  <CardDescription>Most viewed resources in the catalog.</CardDescription>
                </CardHeader>
                <CardContent>
                  {(analytics?.top_by_views ?? []).length === 0 ? (
                    <div className="flex flex-col items-center py-12 text-center space-y-3">
                      <BookOpen className="h-8 w-8 text-muted-foreground" />
                      <p className="text-muted-foreground text-sm">No resource views yet.</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {(analytics?.top_by_views ?? []).slice(0, 8).map((item: any, i: number) => (
                        <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors">
                          <span className="text-sm font-bold text-muted-foreground w-6">{i + 1}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{item.title || "Untitled"}</p>
                            <p className="text-[11px] text-muted-foreground">
                              {item.skill} • {item.type}
                            </p>
                          </div>
                          <Badge variant="secondary" className="text-[10px]">
                            <Eye className="h-3 w-3 mr-1" /> {item.views ?? 0}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* ─── Resources Tab ────────────────────────────────────── */}
        {activeTab === "resources" && (
          <div className="space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-2 flex-1 max-w-md">
                <Search className="h-4 w-4 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search resources..."
                  className="flex-1"
                />
              </div>
              <div className="flex items-center gap-2">
                {selectedIds.length > 0 && (
                  <Button variant="destructive" size="sm" onClick={handleBulkDelete}>
                    <Trash2 className="h-4 w-4 mr-2" /> Delete ({selectedIds.length})
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={() => setShowBulkModal(true)}>
                  <Upload className="h-4 w-4 mr-2" /> Bulk Upload
                </Button>
                <Button size="sm" onClick={() => { setEditingResource(null); setShowAddModal(true); }}>
                  <Plus className="h-4 w-4 mr-2" /> Add Resource
                </Button>
              </div>
            </div>

            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground">
                        <th className="text-left font-medium py-3 px-4 w-8">
                          <input
                            type="checkbox"
                            checked={selectedIds.length === filteredResources.length && filteredResources.length > 0}
                            onChange={(e) => {
                              if (e.target.checked) setSelectedIds(filteredResources.map((r) => r.id));
                              else setSelectedIds([]);
                            }}
                            className="h-4 w-4"
                          />
                        </th>
                        <th className="text-left font-medium py-3 px-2">Resource</th>
                        <th className="text-left font-medium py-3 px-2">Type</th>
                        <th className="text-left font-medium py-3 px-2">Skill</th>
                        <th className="text-right font-medium py-3 px-2">Views</th>
                        <th className="text-right font-medium py-3 px-2">Rating</th>
                        <th className="text-center font-medium py-3 px-2">Verified</th>
                        <th className="text-right font-medium py-3 px-2">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {filteredResources.map((r) => {
                        const typeMeta = TYPE_META[r.type] || TYPE_META.Video;
                        const skillMeta = SKILL_META[r.skill] || { color: "text-slate-700", bg: "bg-slate-100" };
                        const TypeIcon = typeMeta.icon;
                        return (
                          <tr key={r.id} className="hover:bg-muted/50 transition-colors">
                            <td className="py-3 px-4">
                              <input
                                type="checkbox"
                                checked={selectedIds.includes(r.id)}
                                onChange={(e) => {
                                  if (e.target.checked) setSelectedIds([...selectedIds, r.id]);
                                  else setSelectedIds(selectedIds.filter((id) => id !== r.id));
                                }}
                                className="h-4 w-4"
                              />
                            </td>
                            <td className="py-3 px-2">
                              <div className="flex items-center gap-2">
                                <span className={`p-1.5 rounded-lg ${typeMeta.bg} ${typeMeta.color}`}>
                                  <TypeIcon className="h-3.5 w-3.5" />
                                </span>
                                <div className="min-w-0">
                                  <p className="font-medium truncate max-w-[200px]">{r.title}</p>
                                  <p className="text-[10px] text-muted-foreground">{r.source || "—"}</p>
                                </div>
                              </div>
                            </td>
                            <td className="py-3 px-2">
                              <Badge variant="outline" className={`${typeMeta.bg} ${typeMeta.color} border-0 text-[10px]`}>
                                {r.type}
                              </Badge>
                            </td>
                            <td className="py-3 px-2">
                              <Badge variant="outline" className={`${skillMeta.bg} ${skillMeta.color} border-0 text-[10px]`}>
                                {r.skill}
                              </Badge>
                            </td>
                            <td className="py-3 px-2 text-right">{r.popularity_score ?? 0}</td>
                            <td className="py-3 px-2 text-right">
                              {r.rating ? (
                                <span className="inline-flex items-center gap-1">
                                  <Star className="h-3 w-3 text-amber-500 fill-amber-500" />
                                  {r.rating.toFixed(1)}
                                </span>
                              ) : "—"}
                            </td>
                            <td className="py-3 px-2 text-center">
                              {r.verified ? (
                                <button onClick={() => handleUnverify(r.id)} title="Unverify" className="text-emerald-600 hover:text-emerald-700">
                                  <ShieldCheck className="h-4 w-4" />
                                </button>
                              ) : (
                                <button onClick={() => handleVerify(r.id)} title="Verify" className="text-muted-foreground hover:text-emerald-600">
                                  <ShieldX className="h-4 w-4" />
                                </button>
                              )}
                            </td>
                            <td className="py-3 px-2">
                              <div className="flex items-center justify-end gap-1">
                                <button
                                  onClick={() => { setEditingResource(r); setShowAddModal(true); }}
                                  className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-primary"
                                  title="Edit"
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  onClick={() => handleDeleteResource(r.id)}
                                  className="p-1.5 rounded-lg hover:bg-error/10 text-muted-foreground hover:text-error"
                                  title="Delete"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* ─── Suggestions Tab ──────────────────────────────────── */}
        {activeTab === "suggestions" && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              {(["pending", "approved", "rejected"] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setSuggestionFilter(status)}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                    suggestionFilter === status
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/50 text-muted-foreground hover:bg-muted"
                  }`}
                >
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </button>
              ))}
            </div>

            {suggestions.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center space-y-3">
                  <Sparkles className="h-8 w-8 text-muted-foreground mx-auto" />
                  <p className="text-muted-foreground text-sm">No {suggestionFilter} suggestions.</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {suggestions.map((s) => {
                  const typeMeta = TYPE_META[s.type] || TYPE_META.Video;
                  const skillMeta = SKILL_META[s.skill] || { color: "text-slate-700", bg: "bg-slate-100" };
                  const TypeIcon = typeMeta.icon;
                  return (
                    <Card key={s.id}>
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <span className={`p-2 rounded-lg ${typeMeta.bg} ${typeMeta.color}`}>
                            <TypeIcon className="h-4 w-4" />
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h3 className="font-semibold text-sm">{s.title}</h3>
                              <Badge variant="outline" className={`${skillMeta.bg} ${skillMeta.color} border-0 text-[10px]`}>
                                {s.skill}
                              </Badge>
                              <Badge variant="outline" className="text-[10px]">{s.type}</Badge>
                              {s.is_free && (
                                <Badge variant="secondary" className="text-[10px] bg-green-50 text-green-700 border-0">
                                  <Coins className="h-3 w-3 mr-0.5" /> Free
                                </Badge>
                              )}
                            </div>
                            {s.description && (
                              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{s.description}</p>
                            )}
                            <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-2">
                              {s.url && <span className="truncate max-w-[200px]">{s.url}</span>}
                              {s.source && <span>• {s.source}</span>}
                              {s.estimated_time && <span>• {s.estimated_time}m</span>}
                              <span>• {new Date(s.created_at || "").toLocaleDateString()}</span>
                            </div>
                          </div>
<div className="flex items-center justify-end gap-2 shrink-0">
                            <button
                              onClick={() => setEditingSuggestion(s)}
                              className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-primary"
                              title="Edit Suggestion"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                            <div className="flex items-center gap-2">
                              {s.status === "pending" && (
                                <>
                                  <Button size="sm" variant="outline" className="text-emerald-600" onClick={() => handleApproveSuggestion(s.id)}>
                                    <Check className="h-4 w-4 mr-1" /> Approve
                                  </Button>
                                  <Button size="sm" variant="outline" className="text-error" onClick={() => handleRejectSuggestion(s.id)}>
                                    <X className="h-4 w-4 mr-1" /> Reject
                                  </Button>
                                </>
                              )}
                              {s.status === "approved" && (
                                <Badge variant="success" className="text-[10px]">
                                  <CheckCircle2 className="h-3 w-3 mr-1" /> Approved
                                </Badge>
                              )}
                              {s.status === "rejected" && (
                                <Badge variant="destructive" className="text-[10px]">
                                  <XCircle className="h-3 w-3 mr-1" /> Rejected
                                </Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ─── Users Tab ────────────────────────────────────────── */}
        {activeTab === "users" && (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      <th className="text-left font-medium py-3 px-4">User</th>
                      <th className="text-left font-medium py-3 px-2">Role</th>
                      <th className="text-left font-medium py-3 px-2">Plan</th>
                      <th className="text-center font-medium py-3 px-2">Status</th>
                      <th className="text-right font-medium py-3 px-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {users.map((u) => {
                      const roleBadge = ROLE_BADGES[u.role] || ROLE_BADGES.user;
                      return (
                        <tr key={u.id} className="hover:bg-muted/50 transition-colors">
                          <td className="py-3 px-4">
                            <div>
                              <p className="font-medium">{u.full_name || "—"}</p>
                              <p className="text-[11px] text-muted-foreground">{u.email}</p>
                            </div>
                          </td>
                          <td className="py-3 px-2">
                            <Badge variant="outline" className={`${roleBadge.bg} ${roleBadge.color} border-0 text-[10px]`}>
                              {u.role}
                            </Badge>
                          </td>
                          <td className="py-3 px-2 text-muted-foreground">{u.plan}</td>
                          <td className="py-3 px-2 text-center">
                            <Badge variant={u.is_active ? "success" : "secondary"} className="text-[10px]">
                              {u.is_active ? "Active" : "Inactive"}
                            </Badge>
                          </td>
                          <td className="py-3 px-2">
                            <div className="flex items-center justify-end gap-2">
                              {isSuperAdmin && (
                                <select
                                  value={u.role}
                                  onChange={(e) => handleRoleChange(u.id, e.target.value as UserRole)}
                                  className="text-xs rounded-lg border border-input bg-background px-2 py-1"
                                >
                                  {(["user", "moderator", "admin", "super_admin"] as UserRole[]).map((r) => (
                                    <option key={r} value={r}>{r}</option>
                                  ))}
                                </select>
                              )}
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-[10px] h-7"
                                onClick={() => handleToggleUserStatus(u.id, u.is_active)}
                              >
                                {u.is_active ? "Deactivate" : "Activate"}
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ─── Audit Log Tab ────────────────────────────────────── */}
        {activeTab === "audit" && (
          <Card>
            <CardContent className="p-0">
              {auditLog.length === 0 ? (
                <div className="py-12 text-center space-y-3">
                  <Activity className="h-8 w-8 text-muted-foreground mx-auto" />
                  <p className="text-muted-foreground text-sm">No audit log entries yet.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground">
                        <th className="text-left font-medium py-3 px-4">Action</th>
                        <th className="text-left font-medium py-3 px-2">Entity</th>
                        <th className="text-left font-medium py-3 px-2">Entity ID</th>
                        <th className="text-left font-medium py-3 px-2">Changes</th>
                        <th className="text-right font-medium py-3 px-2">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {auditLog.map((entry) => (
                        <tr key={entry.id} className="hover:bg-muted/50 transition-colors">
                          <td className="py-3 px-4">
                            <Badge variant="outline" className="text-[10px]">{entry.action}</Badge>
                          </td>
                          <td className="py-3 px-2 text-muted-foreground">{entry.entity_type}</td>
                          <td className="py-3 px-2 text-muted-foreground font-mono text-[11px]">
                            {entry.entity_id ? entry.entity_id.slice(0, 8) + "..." : "—"}
                          </td>
                          <td className="py-3 px-2">
                            <span className="text-[11px] text-muted-foreground">
                              {entry.changes ? JSON.stringify(entry.changes).slice(0, 60) : "—"}
                            </span>
                          </td>
                          <td className="py-3 px-2 text-right text-muted-foreground text-[11px]">
                            {entry.created_at ? new Date(entry.created_at).toLocaleString() : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Modals */}
      {showAddModal && (
        <ResourceFormModal
          resource={editingResource}
          onClose={() => { setShowAddModal(false); setEditingResource(null); }}
          onSave={editingResource ? handleUpdateResource : handleCreateResource}
        />
      )}

{showBulkModal && (
        <BulkUploadModal
          onClose={() => setShowBulkModal(false)}
          onUpload={handleBulkUpload}
        />
      )}

      {editingSuggestion && (
        <SuggestionEditModal
          suggestion={editingSuggestion}
          onClose={() => setEditingSuggestion(null)}
          onSave={handleUpdateSuggestion}
        />
      )}
    </DashboardLayout>
  );
}
