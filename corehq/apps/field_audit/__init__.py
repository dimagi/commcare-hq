from field_audit import audit_fields
from field_audit.models import AuditAction, AuditingManager, AuditingQuerySet


__all__ = [
    "audit_hq_fields",
    "HQAuditingQuerySet",
    "HQAuditingManager",
]


def audit_hq_fields(*field_names, **kw):
    """Audit special QuerySet methods by default."""
    kw.setdefault("audit_special_queryset_writes", True)
    return audit_fields(*field_names, **kw)


class HQAuditingQuerySet(AuditingQuerySet):
    """An auditing QuerySet that audits special QuerySet methods by default."""

    def bulk_create(self, *args, **kw):
        kw.setdefault("audit_action", AuditAction.AUDIT)
        return super().bulk_create(*args, **kw)

    def bulk_update(self, *args, **kw):
        kw.setdefault("audit_action", AuditAction.AUDIT)
        return super().bulk_update(*args, **kw)

    def delete(self, *args, **kw):
        kw.setdefault("audit_action", AuditAction.AUDIT)
        return super().delete(*args, **kw)

    def update(self, *args, **kw):
        kw.setdefault("audit_action", AuditAction.AUDIT)
        return super().update(*args, **kw)


HQAuditingManager = AuditingManager.from_queryset(HQAuditingQuerySet)
