from __future__ import absolute_import
from os.path import commonprefix, join, sep
import zipfile

from corehq.blobs import DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName
from corehq.blobs.interface import AbstractBlobDB, SAFENAME


class ZipBlobDB(AbstractBlobDB):
    """Blobs stored in zip file. Used for exporting a domain's blobs
    """

    def __init__(self, slug, domain):
        self.zipname = 'export-{domain}-{slug}-blobs.zip'.format(domain=domain, slug=slug)

    def put(self, content, basename="", bucket=DEFAULT_BUCKET):
        raise NotImplementedError

    def get(self, identifier, bucket=DEFAULT_BUCKET):
        raise NotImplementedError

    def delete(self, *args, **kw):
        raise NotImplementedError

    def bulk_delete(self, paths):
        raise NotImplementedError

    def copy_blob(self, content, info, bucket):
        path = self.get_path(info.identifier, bucket)
        with zipfile.ZipFile(self.zipname, 'a') as z:
            z.writestr(path, content.read())

    def get_path(self, identifier=None, bucket=DEFAULT_BUCKET):
        if identifier is None:
            return bucket
        return safejoin(bucket, identifier)


def safejoin(root, subpath):
    if not SAFENAME.match(subpath):
        raise BadName(u"unsafe path name: %r" % subpath)
    path = join(root, subpath)
    if commonprefix([root + sep, path]) != root + sep:
        raise BadName(u"invalid relative path: %r" % subpath)
    return path


def get_blob_db_exporter(slug, domain):
    from .migratingdb import MigratingBlobDB
    from corehq.blobs import get_blob_db
    return MigratingBlobDB(_get_zip_db(slug, domain), get_blob_db())


def _get_zip_db(slug, domain):
    return ZipBlobDB(slug, domain)
