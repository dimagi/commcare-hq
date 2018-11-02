from __future__ import absolute_import
from __future__ import unicode_literals

from functools import wraps

from django.conf import settings

from .config import partition_config

__all__ = ["partitioned"]


def partitioned(cls_or_op):
    """Decorator/wrapper for partitioned migrations/migration operations

    May be applied to entire migration class (as decorator) or to individual
    migration operations (as wrapper).

    :param cls_or_op: Migration class or Operation instance.
    """
    operation_methods = ["database_forwards", "database_backwards"]
    if all(hasattr(cls_or_op, m) for m in operation_methods):
        for name in operation_methods:
            # monkey-patch to override method because Django uses
            # isinstance(operation, ...) extensively, so we cannot
            # easily create a proxy class that quacks but doesn't have
            # the same type as the operation it proxies to.
            setattr(cls_or_op, name, partitioned_override(getattr(cls_or_op, name)))
        return cls_or_op
    cls_or_op.operations = [partitioned(op) for op in cls_or_op.operations]
    return cls_or_op


def is_partition_alias(db):
    return not settings.USE_PARTITIONED_DATABASE or (
        db == partition_config.get_proxy_db() or
        db in partition_config.get_form_processing_dbs()
    )


def partitioned_override(method):
    """Create partition-aware database_forwards/database_backwards override"""
    @wraps(method)
    def override(app_label, schema_editor, *args, **kw):
        if is_partition_alias(schema_editor.connection.alias):
            method(app_label, schema_editor, *args, **kw)

    return override
