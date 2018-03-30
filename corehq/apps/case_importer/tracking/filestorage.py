from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
import os
from tempfile import mkstemp
import uuid
from django.core.cache import caches
from corehq.apps.case_importer.tracking.models import CaseUploadFileMeta
from corehq.blobs import get_blob_db
from corehq.blobs.util import random_url_id
from corehq.util.files import file_extention_from_filename
from memoized import memoized

BUCKET = 'case_importer'


class PersistentFileStore(object):
    """
    helper for writing and reading back arbitrary files to HIPAA-compliant storage
    (Riak or filesystem, via BlobDB)

    metadata is also stored in a django model given by meta_model,
    which is returned by write_file

    """
    def __init__(self, bucket, meta_model):
        """
        :meta_model is a django model used to store meta info
            must contain columns identifier, filename, length
        """

        self._bucket = bucket
        self._db = get_blob_db()
        self._meta_model = meta_model

    def write_file(self, f, filename):
        identifier = random_url_id(16)
        blob_info = self._db.put(f, bucket=self._bucket, identifier=identifier)
        assert identifier == blob_info.identifier
        file_meta = self._meta_model(identifier=identifier, filename=filename,
                                     length=blob_info.length)
        file_meta.save()
        return file_meta

    @memoized
    def get_tempfile_ref_for_contents(self, identifier):
        filename = self.get_filename(identifier)
        suffix = file_extention_from_filename(filename)
        content = self._db.get(identifier, bucket=self._bucket).read()
        return make_temp_file(content, suffix)

    @memoized
    def get_filename(self, identifier):
        return self._meta_model.objects.values_list('filename', flat=True).get(identifier=identifier)


FileMeta = namedtuple('FileMeta', ['identifier', 'filename', 'length'])


class TransientFileStore(object):
    """
    helper for writing and reading back arbitrary files to the cache

    """
    def __init__(self, bucket, timeout):
        self._bucket = bucket
        self._cache = caches['default']
        self._timeout = timeout

    def _get_key(self, identifier):
        return '{}/{}'.format(self._bucket, identifier)

    def _get_filename_key(self, identifier):
        return '{}/{}/filename'.format(self._bucket, identifier)

    def write_file(self, f, filename):
        identifier = str(uuid.uuid4())
        contents = f.read()
        content_length = len(contents)
        self._cache.set(self._get_key(identifier), (filename, contents), timeout=self._timeout)
        return FileMeta(identifier=identifier, filename=filename, length=content_length)

    def get_tempfile_ref_for_contents(self, identifier):
        try:
            filename, content = self._get_filename_content(identifier)
        except (TypeError, ValueError):
            return None
        suffix = file_extention_from_filename(filename)
        return make_temp_file(content, suffix)

    def get_filename(self, identifier):
        filename, _ = self._get_filename_content(identifier)
        return filename

    @memoized
    def _get_filename_content(self, identifier):
        return self._cache.get(self._get_key(identifier))


def make_temp_file(content, suffix):
    """
    Returns filename of a file containing the content for this.
    """
    fd, filename = mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as tmp:
        tmp.write(content)
    return filename


persistent_file_store = PersistentFileStore(BUCKET, CaseUploadFileMeta)
transient_file_store = TransientFileStore(BUCKET, timeout=1 * 60 * 60)
