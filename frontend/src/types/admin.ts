/**
 * Admin Dashboard - TypeScript Types
 *
 * Backs the /api/v1/admin and /api/v1/resource-management admin endpoints.
 */

// ─── Roles ───────────────────────────────────────────────────────────────────

export type UserRole = 'user' | 'moderator' | 'admin' | 'super_admin';

export const USER_ROLES: UserRole[] = ['user', 'moderator', 'admin', 'super_admin'];

export const ROLE_LABELS: Record<UserRole, string> = {
  user: 'User',
  moderator: 'Moderator',
  admin: 'Admin',
  super_admin: 'Super Admin',
};

// ─── Admin Users ─────────────────────────────────────────────────────────────

export interface AdminUser {
  id: string;
  email: string;
  full_name?: string;
  role: UserRole;
  plan: string;
  is_active: boolean;
  created_at?: string;
}

export interface AdminUserListResponse {
  items: AdminUser[];
  total: number;
}

// ─── Admin Stats ─────────────────────────────────────────────────────────────

export interface AdminStats {
  total_users: number;
  active_users: number;
  admin_users: number;
  total_resources: number;
  verified_resources: number;
  pending_suggestions: number;
  total_views: number;
  total_completions: number;
  total_bookmarks: number;
}

// ─── Audit Log ───────────────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  admin_id: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  changes?: Record<string, unknown>;
  ip_address?: string;
  user_agent?: string;
  created_at?: string;
}

// ─── Resource Management Admin ───────────────────────────────────────────────

export interface AdminResourceAnalytics {
  resource: Record<string, unknown>;
  views: number;
  completions: number;
  bookmarks: number;
  likes: number;
  avg_rating: number | null;
  rating_count: number;
  completion_rate: number;
  drop_off_rate: number;
}

export interface AdminAnalytics {
  total_resources: number;
  published_count: number;
  unpublished_count: number;
  verified_count: number;
  unverified_count: number;
  free_count: number;
  paid_count: number;
  by_type: Record<string, number>;
  by_skill: Record<string, number>;
  avg_rating: number | null;
  total_views: number;
  total_completions: number;
  total_bookmarks: number;
  pending_suggestions: number;
  top_by_views: Array<Record<string, unknown>>;
  top_by_rating: Array<Record<string, unknown>>;
}

// ─── Community Suggestions ───────────────────────────────────────────────────

export type Category = 'YouTube Video' | 'PDF' | 'Website' | 'Practice Test' | 'Vocabulary List';

export const CATEGORIES: Category[] = [
  'YouTube Video',
  'PDF',
  'Website',
  'Practice Test',
  'Vocabulary List',
];

export interface ResourceSuggestion {
  id: string;
  user_id: string;
  title: string;
  description?: string;
  category: Category;
  reason?: string;
  votes: number;
  voted?: boolean;
  type: string;
  source?: string;
  author?: string;
  url?: string;
  thumbnail?: string;
  skill: string;
  sub_skill?: string;
  minimum_band?: number;
  maximum_band?: number;
  difficulty?: string;
  estimated_time?: number;
  tags: string[];
  language: string;
  is_free: boolean;
  status: 'pending' | 'approved' | 'rejected';
  admin_notes?: string;
  approved_by?: string;
  approved_at?: string;
  rejected_by?: string;
  rejected_at?: string;
  resource_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ResourceSuggestionCreatePayload {
  title: string;
  description?: string;
  category: Category;
  reason?: string;
  type: string;
  source?: string;
  author?: string;
  url?: string;
  skill: string;
  sub_skill?: string;
  minimum_band?: number;
  maximum_band?: number;
  difficulty?: string;
  estimated_time?: number;
tags?: string[];
  language?: string;
  is_free?: boolean;
}

export type ResourceSuggestionUpdatePayload = Partial<ResourceSuggestionCreatePayload> & {
  admin_notes?: string;
};

// ─── Bulk Operations ─────────────────────────────────────────────────────────

export interface BulkUploadResult {
  created: number;
  errors: number;
  created_items: Array<Record<string, unknown>>;
  error_details: Array<{ index: number; error: string; data?: Record<string, unknown> }>;
  admin_id: string;
}

export interface BulkEditResult {
  updated: number;
  errors: number;
  updated_items: Array<Record<string, unknown>>;
  error_details: Array<{ index: number; id?: string; error: string }>;
  admin_id: string;
}

export interface BulkDeleteResult {
  deleted: number;
  not_found: string[];
  admin_id: string;
}

// ─── Verification Log ────────────────────────────────────────────────────────

export interface VerificationLogEntry {
  id: string;
  resource_id: string;
  admin_id: string;
  action: 'verified' | 'unverified';
  notes?: string;
  created_at?: string;
}