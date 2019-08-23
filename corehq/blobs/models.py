from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from uuid import uuid4

from django.db.models import (
    BigIntegerField,
    CharField,
    DateTimeField,
    IntegerField,
    Model,
    PositiveSmallIntegerField,
)
from memoized import memoized
from partial_index import PartialIndex

from corehq.sql_db.models import PartitionedModel, RestrictedManager

from .util import get_content_md5, NullJsonField


def uuid4_hex():
    return uuid4().hex


class BlobMeta(PartitionedModel, Model):
    """Metadata about an object stored in the blob db"""

    partition_attr = "parent_id"
    objects = RestrictedManager()

    domain = CharField(max_length=255)
    parent_id = CharField(
        max_length=255,
        help_text="Parent primary key or unique identifier",
    )
    name = CharField(
        max_length=255,
        default="",
        help_text="""Optional blob name.

        This field is intended to be used by doc types having multiple
        blobs associated with a single document.
        """,
    )
    key = CharField(
        max_length=255,
        default=uuid4_hex,
        help_text="""Blob key in the external blob store.

        This must be a globally unique value. Historically this was
        `blob_bucket + '/' + identifier` for blobs associated with a
        couch document. Could be a UUID or the result of
        `util.random_url_id(16)`. Defaults to `uuid4().hex`.
        """,
    )
    type_code = PositiveSmallIntegerField(
        help_text="Blob type code. See `corehq.blobs.CODES`.",
    )
    content_length = BigIntegerField()
    content_type = CharField(max_length=255, null=True)
    properties = NullJsonField(default=dict)
    created_on = DateTimeField(default=datetime.utcnow)
    expires_on = DateTimeField(default=None, null=True)

    class Meta:
        unique_together = [
            # HACK work around unique=True implies db_index=True
            # https://code.djangoproject.com/ticket/24082
            # Avoid extra varchar_pattern_ops index
            # since we do not do LIKE queries on these
            # https://stackoverflow.com/a/50926644/10840
            ("key",),
        ]
        index_together = [("parent_id", "type_code", "name")]
        indexes = [
            PartialIndex(
                fields=['expires_on'],
                unique=False,
                where='expires_on IS NOT NULL',
            ),
        ]

    def __repr__(self):
        return "<BlobMeta id={self.id} key={self.key}>".format(self=self)

    @property
    def is_image(self):
        """Use content type to check if blob is an image"""
        return (self.content_type or "").startswith("image/")

    def open(self):
        """Get a file-like object containing blob content

        The returned object should be closed when it is no longer needed.
        """
        from . import get_blob_db
        return get_blob_db().get(key=self.key)

    @memoized
    def content_md5(self):
        """Get RFC-1864-compliant Content-MD5 header value"""
        with self.open() as fileobj:
            return get_content_md5(fileobj)


class DeletedBlobMeta(PartitionedModel, Model):
    """Metadata about a non-temporary object deleted from the blob db

    This is intended for research purposes when a blob is missing. It can
    be used to answer the question "Was the blob deleted by HQ?"
    """

    partition_attr = "parent_id"
    objects = RestrictedManager()

    id = IntegerField(primary_key=True)
    domain = CharField(max_length=255)
    parent_id = CharField(max_length=255)
    name = CharField(max_length=255)
    key = CharField(max_length=255)
    type_code = PositiveSmallIntegerField()
    created_on = DateTimeField()
    deleted_on = DateTimeField()


class BlobMigrationState(Model):
    slug = CharField(max_length=20, unique=True)
    timestamp = DateTimeField(auto_now=True)
