from __future__ import absolute_import
from __future__ import unicode_literals

from functools import wraps

from django.conf import settings

from .config import partition_config

__all__ = ["partitioned"]


def partitioned(cls_or_op=None, apply_to_proxy=True):
    """Decorator/wrapper for partitioned migrations/migration operations

    This is useful for apps that have both partitioned and non-
    partitioned models. App names having partitioned models should be
    added to `TEST_NON_SERIALIZED_APPS` (see dev_settings.py) if model
    creations will be partitioned.

    May be applied to entire migration class (as decorator) or to individual
    migration operations (as wrapper).

    :param cls_or_op: Migration class or Operation instance.
    :param apply_to_proxy: Set this to `True` when migrating functions
    that should be applied to the shard dbs, but not to the proxy. It
    will be necessary to wrap migration operations individually if some
    should be applied to the proxy (table modifications) while some should
    only be applied to shard dbs (function modifications).
    """
    if cls_or_op is None:
        # decorator usage pattern: @partitioned(apply_to_proxy=False)
        def partitioned_decorator(cls_or_proxy):
            assert cls_or_proxy is not None
            return partitioned(cls_or_proxy, apply_to_proxy)
        return partitioned_decorator
    operation_methods = ["database_forwards", "database_backwards"]
    if all(hasattr(cls_or_op, m) for m in operation_methods):
        for name in operation_methods:
            # monkey-patch to override method because Django uses
            # isinstance(operation, ...) extensively, so we cannot
            # easily create a proxy class that quacks but doesn't have
            # the same type as the operation it proxies to.
            setattr(cls_or_op, name, partitioned_override(
                getattr(cls_or_op, name),
                apply_to_proxy
            ))
        return cls_or_op
    cls_or_op.operations = [
        partitioned(op, apply_to_proxy) for op in cls_or_op.operations
    ]
    return cls_or_op


def is_partition_alias(db, apply_to_proxy):
    return not settings.USE_PARTITIONED_DATABASE or (
        (db == partition_config.get_proxy_db() and apply_to_proxy) or
        db in partition_config.get_form_processing_dbs()
    )


def partitioned_override(method, apply_to_proxy):
    """Create partition-aware database_forwards/database_backwards override"""
    @wraps(method)
    def override(app_label, schema_editor, *args, **kw):
        if is_partition_alias(schema_editor.connection.alias, apply_to_proxy):
            method(app_label, schema_editor, *args, **kw)

    return override
