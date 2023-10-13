import os
import uuid
from contextlib import contextmanager
from io import BytesIO

import attr
from memoized import memoized
from PIL import Image

from corehq.blobs import CODES, get_blob_db
from corehq.blobs.atomic import AtomicBlobs
from corehq.blobs.models import BlobMeta
from corehq.blobs.util import get_content_md5

from ..exceptions import AttachmentNotFound
from .mixin import IsImageMixin, SaveStateMixin


@attr.s
class Attachment(IsImageMixin):
    """Unsaved form attachment

    This class implements the subset of the `BlobMeta` interface needed
    when handling attachments before they are saved.
    """

    name = attr.ib()
    raw_content = attr.ib(repr=False)
    content_type = attr.ib()
    properties = attr.ib(default=None)

    def __attrs_post_init__(self):
        """This is necessary for case attachments

        DO NOT USE `self.key` OR `self.properties`; they are only
        referenced when creating case attachments, which are slated for
        removal. The `properties` calculation should be moved back into
        `write()` when case attachments are removed.
        """
        self.key = uuid.uuid4().hex
        if self.properties is None:
            self.properties = {}
            if self.is_image:
                try:
                    img_size = Image.open(self.open()).size
                    self.properties.update(width=img_size[0], height=img_size[1])
                except IOError:
                    self.content_type = 'application/octet-stream'

    def has_size(self):
        if not hasattr(self.raw_content, 'size'):
            return False

        return self.raw_content.size is not None

    @property
    @memoized
    def content_length(self):
        """This is necessary for case attachments

        DO NOT USE THIS. It is only referenced when creating case
        attachments, which are slated for removal.
        """
        if isinstance(self.raw_content, bytes):
            return len(self.raw_content)
        if isinstance(self.raw_content, str):
            return len(self.raw_content.encode('utf-8'))
        pos = self.raw_content.tell()
        try:
            self.raw_content.seek(0, os.SEEK_END)
            return self.raw_content.tell()
        finally:
            self.raw_content.seek(pos)

    @property
    @memoized
    def content(self):
        """Get content bytes

        This is not part of the `BlobMeta` interface. Avoid this method
        for large attachments because it reads the entire attachment
        content into memory.
        """
        if hasattr(self.raw_content, 'read'):
            if hasattr(self.raw_content, 'seek'):
                self.raw_content.seek(0)
            data = self.raw_content.read()
        else:
            data = self.raw_content

        if isinstance(data, str):
            data = data.encode("utf-8")
        return data

    def open(self):
        """Get a file-like object with attachment content

        This is the preferred way to read attachment content.

        If the underlying raw content is a django `File` object this
        will call `raw_content.open()`, which changes the state of the
        underlying file object and will affect other concurrent readers
        (it is not safe to use this for multiple concurrent reads).
        """
        if isinstance(self.raw_content, (bytes, str)):
            return BytesIO(self.content)
        return self.raw_content.open()

    @memoized
    def content_md5(self):
        """Get RFC-1864-compliant Content-MD5 header value"""
        return get_content_md5(self.open())

    @property
    def type_code(self):
        return CODES.form_xml if self.name == "form.xml" else CODES.form_attachment

    def write(self, blob_db, xform):
        """Save attachment

        This is not part of the `BlobMeta` interface.

        This will create an orphaned blob if the xform is not saved.
        If this is called in a SQL transaction and the transaction is
        rolled back, then there will be no record of the blob (blob
        metadata will be lost), but the blob content will continue to
        use space in the blob db unless something like `AtomicBlobs` is
        used to clean up on rollback.

        :param blob_db: Blob db where content will be written.
        :param xform: The XForm instance associated with this attachment.
        :returns: `BlobMeta` object.
        """
        return blob_db.put(
            self.open(),
            key=self.key,
            domain=xform.domain,
            parent_id=xform.form_id,
            type_code=self.type_code,
            name=self.name,
            content_type=self.content_type,
            properties=self.properties,
        )


@attr.s
class AttachmentContent:
    content_type = attr.ib()
    content_stream = attr.ib()
    content_length = attr.ib()

    @property
    def content_body(self):
        # WARNING an error is likely if this property is accessed more than once
        # self.content_stream is a file-like object, and most file-like objects
        # will error on subsequent read attempt once closed (by with statement).
        with self.content_stream as stream:
            return stream.read()


class AttachmentMixin(SaveStateMixin):
    """Mixin for models that have attachments

    This class has some features that are not used by all subclasses.
    For example cases never have unsaved attachments, and therefore never
    write attachments.
    """

    @property
    def attachments_list(self):
        try:
            rval = self._attachments_list
        except AttributeError:
            rval = self._attachments_list = []
        return rval

    @attachments_list.setter
    def attachments_list(self, value):
        assert not hasattr(self, "_attachments_list"), self._attachments_list
        self._attachments_list = value

    def copy_attachments(self, xform):
        """Copy attachments from the given xform"""
        existing_names = {a.name for a in self.attachments_list}
        self.attachments_list.extend(
            Attachment(meta.name, meta, meta.content_type, meta.properties)
            for meta in xform.attachments.values()
            if meta.name not in existing_names
        )

    def has_unsaved_attachments(self):
        """Return true if this form has unsaved attachments else false"""
        return any(isinstance(a, Attachment) for a in self.attachments_list)

    def attachment_writer(self):
        """Context manager for atomically writing attachments

        Usage:
            with form.attachment_writer() as write_attachments, \\
                    transaction.atomic(using=form.db, savepoint=False):
                form.save()
                write_attachments()
                ...
        """
        if all(isinstance(a, BlobMeta) for a in self.attachments_list):
            # do nothing if all attachments have already been written
            class NoopWriter():
                def write(self):
                    pass

                def commit(self):
                    pass

            @contextmanager
            def noop_context():
                yield NoopWriter()

            return noop_context()

        class Writer():
            def __init__(self, form, blob_db):
                self.form = form
                self.blob_db = blob_db

            def write(self):
                self.saved_attachments = [
                    attachment.write(self.blob_db, self.form)
                    for attachment in self.form.attachments_list
                ]

            def commit(self):
                self.form._attachments_list = self.saved_attachments

        @contextmanager
        def atomic_attachments():
            unsaved = self.attachments_list
            assert all(isinstance(a, Attachment) for a in unsaved), unsaved
            with AtomicBlobs(get_blob_db()) as blob_db:
                yield Writer(self, blob_db)

        return atomic_attachments()

    def get_attachments(self):
        attachments = getattr(self, '_attachments_list', None)
        if attachments is not None:
            return attachments

        if self.is_saved():
            return self._get_attachments_from_db()
        return []

    def get_attachment(self, attachment_name):
        """Read attachment content

        Avoid this method because it reads the entire attachment into
        memory at once.
        """
        attachment = self.get_attachment_meta(attachment_name)
        with attachment.open() as content:
            return content.read()

    def get_attachment_meta(self, attachment_name):
        def _get_attachment_from_list(attachments):
            for attachment in attachments:
                if attachment.name == attachment_name:
                    return attachment
            raise AttachmentNotFound(self.get_id, attachment_name)

        attachments = getattr(self, '_attachments_list', None)
        if attachments is not None:
            return _get_attachment_from_list(attachments)

        if self.is_saved():
            return self._get_attachment_from_db(attachment_name)
        raise AttachmentNotFound(self.get_id, attachment_name)

    def _get_attachment_from_db(self, attachment_name):
        raise NotImplementedError

    def _get_attachments_from_db(self):
        raise NotImplementedError
