from __future__ import absolute_import
from __future__ import unicode_literals

from collections import defaultdict
from datetime import datetime, timedelta
from itertools import chain

from corehq.sql_db.routers import get_cursor
from corehq.sql_db.util import split_list_by_db_partition
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
        :raises: `ValueError` if the given `meta` object is a `BlobMeta`
        instance that has already been saved.
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
        parents = defaultdict(list)
        for meta in metas:
            parents[meta.parent_id].append(meta.id)
        for db_name, split_parent_ids in split_list_by_db_partition(parents):
            ids = chain.from_iterable(parents[x] for x in split_parent_ids)
            BlobMeta.objects.using(db_name).filter(id__in=list(ids)).delete()
        deleted_bytes = sum(meta.content_length for m in metas)
        datadog_counter('commcare.blobs.deleted.count', value=len(metas))
        datadog_counter('commcare.blobs.deleted.bytes', value=deleted_bytes)


def _utcnow():
    return datetime.utcnow()
