"""
Resource Management Service.

Encapsulates business logic for the resource catalog that doesn't belong
in the repository layer:
- Bulk import validation and processing
- Bulk edit validation
- Verification workflow orchestration
- Community suggestion approval workflow
- Admin analytics aggregation
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.resource_management_repo import ResourceRepository


class ResourceManagementService:
    """Business logic for resource management operations."""

    def __init__(self, repo: ResourceRepository) -> None:
        self.repo = repo

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------
    def bulk_create_resources(
        self,
        resources: List[Dict[str, Any]],
        admin_id: str,
    ) -> Dict[str, Any]:
        """
        Validate and bulk-create resources.

        Returns a summary with created count, errors, and created items.
        """
        if not resources:
            raise ValidationError("No resources provided for bulk upload")

        if len(resources) > 500:
            raise ValidationError("Bulk upload limited to 500 resources per request")

        created: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for idx, item in enumerate(resources):
            try:
                # Validate required fields
                title = item.get("title")
                if not title or not str(title).strip():
                    raise ValidationError(f"Item {idx}: title is required")

                resource_type = item.get("type")
                if not resource_type:
                    raise ValidationError(f"Item {idx}: type is required")

                skill = item.get("skill")
                if not skill:
                    raise ValidationError(f"Item {idx}: skill is required")

                url = item.get("url")
                if url and not str(url).startswith(("https://", "http://")):
                    raise ValidationError(f"Item {idx}: URL must start with https:// or http://")

                # Normalize tags
                tags = item.get("tags", [])
                if tags:
                    normalized_tags = []
                    seen = set()
                    for tag in tags:
                        normalized = str(tag).strip().lower()
                        if normalized and normalized not in seen:
                            seen.add(normalized)
                            normalized_tags.append(normalized)
                    item["tags"] = normalized_tags

                # Set defaults
                item.setdefault("is_free", True)
                item.setdefault("verified", False)
                item.setdefault("official", False)
                item.setdefault("popularity_score", 0)
                item.setdefault("language", "en")

                created_item = self.repo.create(item)
                created.append(created_item)
            except Exception as e:
                errors.append({"index": idx, "error": str(e), "data": item})

        return {
            "created": len(created),
            "errors": len(errors),
            "created_items": created,
            "error_details": errors,
            "admin_id": admin_id,
        }

    def bulk_update_resources(
        self,
        updates: List[Dict[str, Any]],
        admin_id: str,
    ) -> Dict[str, Any]:
        """
        Validate and bulk-update resources.

        Each item must have an 'id' field and the fields to update.
        Returns a summary with updated count, errors, and updated items.
        """
        if not updates:
            raise ValidationError("No updates provided for bulk edit")

        if len(updates) > 500:
            raise ValidationError("Bulk edit limited to 500 resources per request")

        updated: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for idx, item in enumerate(updates):
            try:
                resource_id = item.get("id")
                if not resource_id:
                    raise ValidationError(f"Item {idx}: id is required")

                # Validate URL if present
                url = item.get("url")
                if url and not str(url).startswith(("https://", "http://")):
                    raise ValidationError(f"Item {idx}: URL must start with https:// or http://")

                # Normalize tags if present
                tags = item.get("tags")
                if tags is not None:
                    normalized_tags = []
                    seen = set()
                    for tag in tags:
                        normalized = str(tag).strip().lower()
                        if normalized and normalized not in seen:
                            seen.add(normalized)
                            normalized_tags.append(normalized)
                    item["tags"] = normalized_tags

                update_data = {k: v for k, v in item.items() if k != "id"}
                if not update_data:
                    continue

                updated_item = self.repo.update(resource_id, update_data)
                updated.append(updated_item)
            except Exception as e:
                errors.append({"index": idx, "id": item.get("id"), "error": str(e)})

        return {
            "updated": len(updated),
            "errors": len(errors),
            "updated_items": updated,
            "error_details": errors,
            "admin_id": admin_id,
        }

    def bulk_delete_resources(
        self,
        resource_ids: List[str],
        admin_id: str,
    ) -> Dict[str, Any]:
        """
        Bulk delete resources by IDs.
        Returns a summary with deleted count and not-found IDs.
        """
        if not resource_ids:
            raise ValidationError("No resource IDs provided for bulk delete")

        if len(resource_ids) > 500:
            raise ValidationError("Bulk delete limited to 500 resources per request")

        result = self.repo.bulk_delete(resource_ids)
        result["admin_id"] = admin_id
        return result

    # ------------------------------------------------------------------
    # Verification workflow
    # ------------------------------------------------------------------
    def verify_resource(
        self,
        resource_id: str,
        admin_id: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify a resource and log the action."""
        return self.repo.verify_resource(resource_id, admin_id, notes)

    def unverify_resource(
        self,
        resource_id: str,
        admin_id: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Remove verification from a resource and log the action."""
        return self.repo.unverify_resource(resource_id, admin_id, notes)

    def get_verification_log(self, resource_id: str) -> List[Dict[str, Any]]:
        """Get the verification log for a resource."""
        return self.repo.get_verification_log(resource_id)

    # ------------------------------------------------------------------
    # Community suggestion approval
    # ------------------------------------------------------------------
    def get_suggestions(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get community resource suggestions for admin review."""
        return self.repo.get_suggestions(status=status, limit=limit, offset=offset)

    def approve_suggestion(
        self,
        suggestion_id: str,
        admin_id: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a community suggestion and create the resource."""
        return self.repo.approve_suggestion(suggestion_id, admin_id, notes)

    def reject_suggestion(
        self,
        suggestion_id: str,
        admin_id: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reject a community suggestion."""
        return self.repo.reject_suggestion(suggestion_id, admin_id, notes)

    # ------------------------------------------------------------------
    # Admin analytics
    # ------------------------------------------------------------------
    def get_admin_analytics(self) -> Dict[str, Any]:
        """Get analytics data for the admin dashboard."""
        return self.repo.get_admin_analytics()

    def get_resource_analytics(self, resource_id: str) -> Dict[str, Any]:
        """Get detailed analytics for a single resource."""
        return self.repo.get_resource_analytics(resource_id)


# Singleton instance (initialized with default repo in deps)
resource_management_service: Optional[ResourceManagementService] = None


def get_resource_management_service(repo: ResourceRepository) -> ResourceManagementService:
    """Factory to create a ResourceManagementService with the given repository."""
    return ResourceManagementService(repo)
