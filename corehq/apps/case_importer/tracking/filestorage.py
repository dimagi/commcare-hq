import os
from tempfile import mkstemp
import uuid
from django.core.cache import caches
from corehq.blobs import get_blob_db
from dimagi.utils.decorators.memoized import memoized

BUCKET = 'case_importer/upload_files'


class PersistentFileStore(object):
    def __init__(self, bucket):
        self._bucket = bucket
        self._db = get_blob_db()

    def write_file(self, f):
        blob_info = self._db.put(f, bucket=self._bucket)
        return blob_info.identifier

    @memoized
    def get_filename(self, identifier, suffix):
        return make_temp_file(
            self._db.get(identifier, bucket=self._bucket).read(), suffix)


class TransientFileStore(object):
    def __init__(self, bucket, timeout):
        self._bucket = bucket
        self._cache = caches['default']
        self._timeout = timeout

    def _get_key(self, identifier):
        return '{}/{}'.format(self._bucket, identifier)

    def write_file(self, f):
        identifier = str(uuid.uuid4())
        self._cache.set(self._get_key(identifier), f.read(), timeout=self._timeout)
        return identifier

    @memoized
    def get_filename(self, identifier, suffix):
        content = self._cache.get(self._get_key(identifier))
        print 'content', content
        return make_temp_file(content, suffix)


def make_temp_file(content, suffix):
    """
    Returns filename of a file containing the content for this.
    """
    fd, filename = mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as tmp:
        tmp.write(content)
    return filename


persistent_file_store = PersistentFileStore(BUCKET)
transient_file_store = TransientFileStore(BUCKET, timeout=1 * 60 * 60)
