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
        self.zipname = get_export_filename(slug, domain)
        self._zipfile = None

    def put(self, content, identifier, bucket=DEFAULT_BUCKET):
        raise NotImplementedError

    def get(self, identifier, bucket=DEFAULT_BUCKET):
        raise NotImplementedError

    def delete(self, *args, **kw):
        raise NotImplementedError

    def bulk_delete(self, paths):
        raise NotImplementedError

    def copy_blob(self, content, info, bucket):
        path = self.get_path(info.identifier, bucket)
        self.zipfile.writestr(path, content.read())

    def get_path(self, identifier=None, bucket=DEFAULT_BUCKET):
        if identifier is None:
            return bucket
        return safejoin(bucket, identifier)

    def exists(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        return path in self.zipfile.namelist()

    @property
    def zipfile(self):
        if self._zipfile is None:
            self._zipfile = zipfile.ZipFile(self.zipname, 'w', allowZip64=True)
        return self._zipfile

    def close(self):
        if self._zipfile:
            self._zipfile.close()


def safejoin(root, subpath):
    if not SAFENAME.match(subpath):
        raise BadName(u"unsafe path name: %r" % subpath)
    path = join(root, subpath)
    if commonprefix([root + sep, path]) != root + sep:
        raise BadName(u"invalid relative path: %r" % subpath)
    return path


def get_export_filename(slug, domain):
    return 'export-{domain}-{slug}-blobs.zip'.format(domain=domain, slug=slug)
