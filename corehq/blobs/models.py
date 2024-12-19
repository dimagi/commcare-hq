from datetime import datetime
from uuid import uuid4

from django.db.models import (
    BigIntegerField,
    CharField,
    DateTimeField,
    Index,
    IntegerField,
    Model,
    PositiveSmallIntegerField,
    Q,
)
from memoized import memoized

from corehq.sql_db.models import PartitionedModel
from corehq.util.models import NullJsonField

from .util import get_content_md5


def uuid4_hex():
    return uuid4().hex


class BlobMeta(PartitionedModel, Model):
    """Metadata about an object stored in the blob db"""

    partition_attr = "parent_id"

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
    compressed_length = BigIntegerField(null=True)
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
            Index(
                fields=['expires_on'],
                name="blobs_blobmeta_expires_ed7e3d",
                condition=Q(expires_on__isnull=False),
            ),
        ]

    def __repr__(self):
        return "<BlobMeta id={self.id} key={self.key}>".format(self=self)

    @property
    def is_image(self):
        """Use content type to check if blob is an image"""
        return (self.content_type or "").startswith("image/")

    @property
    def is_compressed(self):
        return self.compressed_length is not None

    @property
    def stored_content_length(self):
        return self.compressed_length if self.is_compressed else self.content_length

    def open(self, db=None):
        """Get a file-like object containing blob content

        The returned object should be closed when it is no longer needed.
        """
        from . import get_blob_db
        db = db or get_blob_db()
        return db.get(meta=self)

    def blob_exists(self):
        from . import get_blob_db
        return get_blob_db().exists(self.key)

    @memoized
    def content_md5(self):
        """Get RFC-1864-compliant Content-MD5 header value"""
        with self.open() as fileobj:
            return get_content_md5(fileobj)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.parent_id, self.key


class DeletedBlobMeta(PartitionedModel, Model):
    """Metadata about a non-temporary object deleted from the blob db

    This is intended for research purposes when a blob is missing. It can
    be used to answer the question "Was the blob deleted by HQ?"
    """

    partition_attr = "parent_id"

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
