from .models import AuditLog


def record(user, action, entity=None, *, entity_type=None, entity_id=None, before=None, after=None, location=None, reason=""):
    """Write one audit row. `entity` may be a model instance."""
    if entity is not None:
        entity_type = entity_type or entity.__class__.__name__
        entity_id = entity_id or str(entity.pk)
        if location is None:
            location = getattr(entity, "location", None)
    return AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        entity_type=entity_type or "",
        entity_id=str(entity_id or ""),
        location=location,
        before=before,
        after=after,
        reason=reason,
    )
