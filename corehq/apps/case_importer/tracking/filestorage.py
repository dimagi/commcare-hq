import os
from tempfile import mkstemp
import uuid
from django.core.cache import caches
from corehq.apps.case_importer.tracking.models import CaseUploadFileMeta
from corehq.blobs import get_blob_db
from corehq.util.files import file_extention_from_filename
from dimagi.utils.decorators.memoized import memoized

BUCKET = 'case_importer/upload_files'


class PersistentFileStore(object):
    def __init__(self, bucket, meta_model):
        """
        :meta_model is a django model used to store meta info
            must contain columns identifier, filename, length
        """

        self._bucket = bucket
        self._db = get_blob_db()
        self._meta_model = meta_model

    def write_file(self, f, filename):
        blob_info = self._db.put(f, bucket=self._bucket)
        self._meta_model(identifier=blob_info.identifier, filename=filename,
                         length=blob_info.length).save()
        return blob_info.identifier

    @memoized
    def get_tempfile(self, identifier):
        filename = self._meta_model.objects.values_list('filename', flat=True).get(identifier=identifier)
        suffix = file_extention_from_filename(filename)
        content = self._db.get(identifier, bucket=self._bucket).read()
        return make_temp_file(content, suffix)


class TransientFileStore(object):
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
        self._cache.set(self._get_key(identifier), (filename, f.read()), timeout=self._timeout)
        return identifier

    @memoized
    def get_tempfile(self, identifier):
        filename, content = self._cache.get(self._get_key(identifier))
        suffix = file_extention_from_filename(filename)
        return make_temp_file(content, suffix)


def make_temp_file(content, suffix):
    """
    Returns filename of a file containing the content for this.
    """
    fd, filename = mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as tmp:
        tmp.write(content)
    return filename


def get_suffix(filename):
    try:
        return filename.split('.')[-1]
    except IndexError:
        return None

persistent_file_store = PersistentFileStore(BUCKET, CaseUploadFileMeta)
transient_file_store = TransientFileStore(BUCKET, timeout=1 * 60 * 60)
