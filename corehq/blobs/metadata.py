from __future__ import absolute_import
from __future__ import unicode_literals

from collections import defaultdict
from datetime import datetime, timedelta
from itertools import chain

import attr
from django.db import connections

from corehq.sql_db.routers import get_cursor
from corehq.sql_db.util import (
    get_db_alias_for_partitioned_doc,
    split_list_by_db_partition,
)
from corehq.util.datadog.gauges import datadog_counter

from .models import BlobMeta


class MetaDB(object):
    """Blob metadata database interface

    This class manages persistence of blob metadata in a SQL database.
    """

    def new(self, **blob_meta_args):
        """Get a new `BlobMeta` object

        :param **blob_meta_args: See `AbstractBlobDB.put` for argument
        documentation. If the given `meta` argument is a `BlobMeta`
        object it will be returned instead of creating a new instance.
        """
        if "meta" in blob_meta_args:
            if len(blob_meta_args) > 1:
                raise ValueError(
                    "keyword arguments are incompatible with `meta` argument")
            return blob_meta_args["meta"]
        timeout = blob_meta_args.pop("timeout", None)
        meta = BlobMeta(**blob_meta_args)
        if not meta.domain:
            raise TypeError("domain is required")
        if not meta.parent_id:
            raise TypeError("parent_id is required")
        if meta.type_code is None:
            raise TypeError("type_code is required")
        if timeout is not None:
            if "expires_on" in blob_meta_args:
                raise ValueError("pass one: timeout or expires_on")
            meta.expires_on = _utcnow() + timedelta(minutes=timeout)
        return meta

    def put(self, meta):
        """Save `BlobMeta` in the metadata database"""
        meta.save()
        length = meta.content_length
        datadog_counter('commcare.blobs.added.count')
        datadog_counter('commcare.blobs.added.bytes', value=length)
        if meta.expires_on is not None:
            datadog_counter('commcare.temp_blobs.count')
            datadog_counter('commcare.temp_blobs.bytes_added', value=length)

    def delete(self, key, content_length):
        """Delete blob metadata

        Metadata for temporary blobs is deleted. Non-temporary metadata
        is retained to make it easier to track down missing blobs.

        :param key: Blob key string.
        :returns: The number of metadata rows deleted.
        """
        with get_cursor(BlobMeta) as cursor:
            cursor.execute('SELECT 1 FROM delete_blob_meta(%s)', [key])
        datadog_counter('commcare.blobs.deleted.count')
        datadog_counter('commcare.blobs.deleted.bytes', value=content_length)

    def bulk_delete(self, metas):
        """Delete blob metadata in bulk

        :param metas: A list of `BlobMeta` objects.
        """
        if any(meta.id is None for meta in metas):
            raise ValueError("cannot delete unsaved BlobMeta")
        parents = defaultdict(IdLists)
        for meta in metas:
            data = parents[meta.parent_id]
            if meta.expires_on is None:
                data.keep.append(meta.id)
            else:
                data.temp.append(meta.id)
        for dbname, split_parent_ids in split_list_by_db_partition(parents):
            temps = [m for p in split_parent_ids for m in parents[p].temp]
            keeps = [m for p in split_parent_ids for m in parents[p].keep]
            if temps:
                BlobMeta.objects.using(dbname).filter(id__in=temps).delete()
            if keeps:
                BlobMeta.objects.using(dbname).filter(id__in=keeps).update(
                    deleted_on=datetime.utcnow()
                )
        deleted_bytes = sum(meta.content_length for m in metas)
        datadog_counter('commcare.blobs.deleted.count', value=len(metas))
        datadog_counter('commcare.blobs.deleted.bytes', value=deleted_bytes)

    def get(self, **kw):
        """Get metadata for a single blob

        All arguments must be passed as keyword arguments.

        :param parent_id: `BlobMeta.parent_id`
        :param type_code: `BlobMeta.type_code`
        :param name: `BlobMeta.name`
        :param key: `BlobMeta.key`
        :raises: `BlobMeta.DoesNotExist` if the metadata is not found.
        :returns: A `BlobMeta` object.
        """
        keywords = set(kw)
        if 'key' in keywords and keywords != {'key', 'parent_id'}:
            kw.pop('key', None)
            if 'parent_id' not in keywords:
                raise TypeError("Missing argument 'parent_id'")
            else:
                kw.pop('parent_id')
                raise TypeError("Unexpected arguments: {}".format(", ".join(kw)))
        elif 'key' not in keywords and keywords != {"parent_id", "type_code", "name"}:
            # arg check until on Python 3 -> PEP 3102: required keyword args
            kw.pop("parent_id", None)
            kw.pop("type_code", None)
            kw.pop("name", None)
            if not kw:
                raise TypeError("Missing argument 'name' and/or 'parent_id'")
            raise TypeError("Unexpected arguments: {}".format(", ".join(kw)))
        dbname = get_db_alias_for_partitioned_doc(kw["parent_id"])
        meta = BlobMeta.objects.using(dbname).filter(
            deleted_on__isnull=True, **kw).first()
        if meta is None:
            raise BlobMeta.DoesNotExist(repr(kw))
        return meta

    def get_for_parent(self, parent_id, type_code=None):
        """Get a list of `BlobMeta` objects for the given parent

        :param parent_id: `BlobMeta.parent_id`
        :param type_code: `BlobMeta.type_code` (optional).
        :returns: A list of `BlobMeta` objects.
        """
        dbname = get_db_alias_for_partitioned_doc(parent_id)
        kw = {"parent_id": parent_id, "deleted_on__isnull": True}
        if type_code is not None:
            kw["type_code"] = type_code
        return list(BlobMeta.objects.using(dbname).filter(**kw))

    def get_for_parents(self, parent_ids, type_code=None):
        """Get a list of `BlobMeta` objects for the given parent(s)

        :param parent_ids: List of `BlobMeta.parent_id` values.
        :param type_code: `BlobMeta.type_code` (optional).
        :returns: A list of `BlobMeta` objects sorted by `parent_id`.
        """
        return list(BlobMeta.objects.raw(
            'SELECT * FROM get_blobmetas(%s, %s::SMALLINT)',
            [parent_ids, type_code],
        ))

    def reparent(self, old_parent_id, new_parent_id):
        """Reassign blobs' parent

        Both `old_parent_id` and `new_parent_id` must map to the same
        database partition.
        """
        dbname = get_db_alias_for_partitioned_doc(old_parent_id)
        new_db = get_db_alias_for_partitioned_doc(new_parent_id)
        assert dbname == new_db, ("Cannot reparent to new partition: %s -> %s" %
            (old_parent_id, new_parent_id))
        with connections[dbname].cursor() as cursor:
            cursor.execute(
                "UPDATE blobs_blobmeta SET parent_id = %s WHERE parent_id = %s",
                [new_parent_id, old_parent_id],
            )


@attr.s
class IdLists(object):
    keep = attr.ib(factory=list)  # non-temporary ids
    temp = attr.ib(factory=list)  # temporary/expired ids


def _utcnow():
    return datetime.utcnow()
