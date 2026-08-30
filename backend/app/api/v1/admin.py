"""
Admin API endpoints for user management, role management, and audit logging.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.api.deps import get_current_admin, get_current_super_admin
from app.db.supabase import supabase

router = APIRouter()


@router.get("/users", response_model=List[dict], summary="List all users (admin)")
async def list_users(
    role: Optional[str] = Query(None, description="Filter by role"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin_id: str = Depends(get_current_admin),
):
    """List all users with optional role and search filters."""
    query = supabase.table("users").select("id, email, full_name, role, plan, is_active, created_at")
    if role:
        query = query.eq("role", role)
    if search:
        query = query.or_(f"email.ilike.%{search}%,full_name.ilike.%{search}%")
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return result.data or []


@router.patch("/users/{user_id}/role", response_model=dict, summary="Update user role (admin)")
async def update_user_role(
    user_id: str,
    role: str = Query(..., description="New role: user, moderator, admin, super_admin"),
    admin_id: str = Depends(get_current_admin),
):
    """Update a user's role. Only super_admin can assign admin/super_admin roles."""
    if role not in ("user", "moderator", "admin", "super_admin"):
        raise HTTPException(status_code=400, detail="Role must be one of: user, moderator, admin, super_admin")
    if role in ("admin", "super_admin"):
        admin_result = supabase.table("users").select("role").eq("id", admin_id).single().execute()
        if not admin_result.data or admin_result.data.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Only super_admin can assign admin or super_admin roles")
    if user_id == admin_id and role != "super_admin":
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    result = supabase.table("users").update({"role": role}).eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    supabase.table("admin_audit_log").insert({
        "admin_id": admin_id, "action": "update_role", "entity_type": "user",
        "entity_id": user_id, "changes": {"role": role},
    }).execute()
    return {"user_id": user_id, "role": role}


@router.patch("/users/{user_id}/status", response_model=dict, summary="Activate/deactivate user (admin)")
async def update_user_status(
    user_id: str,
    is_active: bool = Query(..., description="Set user active status"),
    admin_id: str = Depends(get_current_admin),
):
    """Activate or deactivate a user account."""
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    result = supabase.table("users").update({"is_active": is_active}).eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    supabase.table("admin_audit_log").insert({
        "admin_id": admin_id, "action": "update_status", "entity_type": "user",
        "entity_id": user_id, "changes": {"is_active": is_active},
    }).execute()
    return {"user_id": user_id, "is_active": is_active}


@router.get("/audit-log", response_model=List[dict], summary="Get admin audit log (admin)")
async def get_audit_log(
    admin_id: Optional[str] = Query(None, description="Filter by admin ID"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_admin_id: str = Depends(get_current_admin),
):
    """Get the admin audit log with optional filters."""
    query = supabase.table("admin_audit_log").select("*")
    if admin_id:
        query = query.eq("admin_id", admin_id)
    if entity_type:
        query = query.eq("entity_type", entity_type)
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return result.data or []


@router.get("/stats", response_model=dict, summary="Get admin dashboard stats (admin)")
async def get_admin_stats(
    current_admin_id: str = Depends(get_current_admin),
):
    """Get overall admin dashboard statistics."""
    total_users = supabase.table("users").select("*", count="exact").execute()
    active_users = supabase.table("users").select("*", count="exact").eq("is_active", True).execute()
    admin_users = supabase.table("users").select("*", count="exact").in_("role", ["admin", "super_admin"]).execute()
    total_resources = supabase.table("resources").select("*", count="exact").execute()
    verified_resources = supabase.table("resources").select("*", count="exact").eq("verified", True).execute()
    pending_suggestions = supabase.table("resource_suggestions").select("*", count="exact").eq("status", "pending").execute()
    total_views = supabase.table("resource_views").select("*", count="exact").execute()
    total_completions = supabase.table("resource_completions").select("*", count="exact").execute()
    total_bookmarks = supabase.table("resource_bookmarks").select("*", count="exact").execute()
    return {
        "total_users": total_users.count or 0,
        "active_users": active_users.count or 0,
        "admin_users": admin_users.count or 0,
        "total_resources": total_resources.count or 0,
        "verified_resources": verified_resources.count or 0,
        "pending_suggestions": pending_suggestions.count or 0,
        "total_views": total_views.count or 0,
        "total_completions": total_completions.count or 0,
        "total_bookmarks": total_bookmarks.count or 0,
    }