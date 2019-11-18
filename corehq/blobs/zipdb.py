from os.path import commonprefix, join, sep
import zipfile

from corehq.blobs.exceptions import BadName
from corehq.blobs.interface import AbstractBlobDB
from corehq.blobs.util import SAFENAME


class ZipBlobDB(AbstractBlobDB):
    """Blobs stored in zip file. Used for exporting a domain's blobs
    """

    def __init__(self, slug, domain):
        super(ZipBlobDB, self).__init__()
        self.zipname = get_export_filename(slug, domain)
        self._zipfile = None

    def put(self, **blob_meta_args):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

    def bulk_delete(self, metas):
        raise NotImplementedError

    def copy_blob(self, content, key):
        # NOTE this does not save all metadata, and therefore
        # the zip file cannot be used to fully rebuild the
        # blob db state in another environment.
        self.zipfile.writestr(key, content.read())

    def exists(self, key):
        return key in self.zipfile.namelist()

    def size(self, key):
        raise NotImplementedError

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
        raise BadName("unsafe path name: %r" % subpath)
    path = join(root, subpath)
    if commonprefix([root + sep, path]) != root + sep:
        raise BadName("invalid relative path: %r" % subpath)
    return path


def get_export_filename(slug, domain):
    return 'export-{domain}-{slug}-blobs.zip'.format(domain=domain, slug=slug)
