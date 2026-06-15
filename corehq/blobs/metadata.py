from collections import defaultdict
from datetime import datetime, timedelta

from corehq.sql_db.util import (
    get_db_alias_for_partitioned_doc,
    split_list_by_db_partition,
)
from corehq.util.metrics import (
    metrics_counter,
    limit_domains,
)

from . import CODES

from .models import BlobMeta


class MetaDB(object):
    """Blob metadata database interface

    This class manages persistence of blob metadata in a SQL database.
    """
    DoesNotExist = BlobMeta.DoesNotExist

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
        if blob_meta_args.get('type_code') == CODES.form_xml:
            blob_meta_args['compressed_length'] = -1
        meta = BlobMeta(**blob_meta_args)
        if not meta.domain:
            raise TypeError("domain is required")
        if not meta.parent_id:
            raise TypeError("parent_id is required")
        if not isinstance(meta.parent_id, str):
            raise TypeError("parent_id must be a string")
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
        length = meta.stored_content_length
        tags = _meta_tags(meta)
        metrics_counter('commcare.blobs.added.count', tags=tags)
        metrics_counter('commcare.blobs.added.bytes', value=length, tags=tags)
        if meta.type_code == 3:
            domain = limit_domains(meta.domain)
            metrics_counter('commcare.blobs.added.form_attachment.count',
                            tags={'domain': domain})
            metrics_counter('commcare.blobs.added.form_attachment.bytes',
                            value=length, tags={'domain': domain})
        if meta.expires_on is not None:
            metrics_counter('commcare.temp_blobs.count', tags=tags)
            metrics_counter('commcare.temp_blobs.bytes_added', value=length, tags=tags)

    def delete(self, key, content_length):
        """Delete blob metadata

        Metadata for temporary blobs is deleted. Non-temporary metadata
        is retained to make it easier to track down missing blobs.

        :param key: Blob key string.
        :returns: The number of metadata rows deleted.
        """
        with BlobMeta.get_plproxy_cursor() as cursor:
            cursor.execute('SELECT 1 FROM delete_blob_meta(%s)', [key])
        metrics_counter('commcare.blobs.deleted.count')
        metrics_counter('commcare.blobs.deleted.bytes', value=content_length)

    def bulk_delete(self, metas):
        """Delete blob metadata in bulk

        :param metas: A list of `BlobMeta` objects.
        """
        if any(meta.id is None for meta in metas):
            raise ValueError("cannot delete unsaved BlobMeta")
        delete_blobs_sql = """
        WITH deleted AS (
            DELETE FROM blobs_blobmeta
            WHERE id IN %s
            RETURNING *
        ), ins AS (
            INSERT INTO blobs_deletedblobmeta (
                "id",
                "domain",
                "parent_id",
                "name",
                "key",
                "type_code",
                "created_on",
                "deleted_on"
            ) (
                SELECT
                    "id",
                    "domain",
                    "parent_id",
                    "name",
                    "key",
                    "type_code",
                    "created_on",
                    %s AS "deleted_on"
                FROM deleted
                WHERE expires_on IS NULL
            ) ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                key = EXCLUDED.key,
                type_code = EXCLUDED.type_code,
                created_on = EXCLUDED.created_on,
                deleted_on = CLOCK_TIMESTAMP()
            WHERE blobs_deletedblobmeta.parent_id = EXCLUDED.parent_id and blobs_deletedblobmeta.key = EXCLUDED.key
        ) SELECT COUNT(*) FROM deleted;
        """
        now = _utcnow()
        parents = defaultdict(list)
        for meta in metas:
            parents[meta.parent_id].append(meta.id)
        for dbname, split_parent_ids in split_list_by_db_partition(parents):
            ids = tuple(m for p in split_parent_ids for m in parents[p])
            with BlobMeta.get_cursor_for_partition_db(dbname) as cursor:
                cursor.execute(delete_blobs_sql, [ids, now])
        deleted_bytes = sum(m.stored_content_length for m in metas)
        metrics_counter('commcare.blobs.deleted.count', value=len(metas))
        metrics_counter('commcare.blobs.deleted.bytes', value=deleted_bytes)

    def expire(self, parent_id, key, minutes=60):
        """Set blob expiration to some minutes from now

        This makes it easy to handle the scenario where a new blob is
        replacing another (now obsolete) blob, but immediate deletion of
        the obsolete blob would introduce a race condition because in-
        flight code may retain references to it. This will schedule the
        obsolete blob for deletion in the near future at which point
        such a race condition is extremely unlikely to be triggered.

        :param parent_id: Parent identifier used for sharding.
        :param key: Blob key.
        :param minutes: Optional number of minutes from now that
        the blob will be set to expire. The default is 60.
        """
        try:
            meta = self.get(parent_id=parent_id, key=key)
        except BlobMeta.DoesNotExist:
            return
        if meta.expires_on is None:
            tags = _meta_tags(meta)
            metrics_counter('commcare.temp_blobs.count', tags=tags)
            metrics_counter('commcare.temp_blobs.bytes_added', value=meta.stored_content_length, tags=tags)
        meta.expires_on = _utcnow() + timedelta(minutes=minutes)
        meta.save()

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
                raise TypeError("Missing argument 'parent_id', 'type_code' and/or 'name'")
            raise TypeError("Unexpected arguments: {}".format(", ".join(kw)))
        meta = BlobMeta.objects.partitioned_query(kw["parent_id"]).filter(**kw).first()
        if meta is None:
            raise BlobMeta.DoesNotExist(repr(kw))
        return meta

    def get_for_parent(self, parent_id, type_code=None):
        """Get a list of `BlobMeta` objects for the given parent

        :param parent_id: `BlobMeta.parent_id`
        :param type_code: `BlobMeta.type_code` (optional).
        :returns: A list of `BlobMeta` objects.
        """
        kw = {"parent_id": parent_id}
        if type_code is not None:
            kw["type_code"] = type_code
        return list(BlobMeta.objects.partitioned_query(parent_id).filter(**kw))

    def get_for_parents(self, parent_ids, type_code=None):
        """Get a list of `BlobMeta` objects for the given parent(s)

        :param parent_ids: List of `BlobMeta.parent_id` values.
        :param type_code: `BlobMeta.type_code` (optional).
        :returns: A list of `BlobMeta` objects sorted by `parent_id`.
        """
        return list(BlobMeta.objects.plproxy_raw(
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
        query = BlobMeta.objects.partitioned_query(old_parent_id)
        query.filter(parent_id=old_parent_id).update(parent_id=new_parent_id)


def _utcnow():
    return datetime.utcnow()


def _meta_tags(meta):
    type_ = CODES.name_of(meta.type_code, f'type_code_{meta.type_code}')
    return {'type': type_}
