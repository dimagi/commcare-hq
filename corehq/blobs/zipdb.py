"""Filesystem database for large binary data objects (blobs)
"""
from __future__ import absolute_import
import base64
from hashlib import md5
from os.path import commonprefix, join, sep
import zipfile

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName
from corehq.blobs.interface import AbstractBlobDB, SAFENAME


class ZipBlobDB(AbstractBlobDB):
    """Blobs stored in zip file. Used for importing/exporting environments
    """

    def __init__(self, domain):
        self.zipname = 'export-{domain}-blobs.zip'.format(domain=domain)

    def put(self, content, basename="", bucket=DEFAULT_BUCKET):
        identifier = self.get_identifier(basename)
        path = self.get_path(identifier, bucket)
        length = 0
        content = content.read()
        with zipfile.ZipFile(self.zipname, 'a') as z:
            z.writestr(path, content)
        digest = md5(content)
        b64digest = base64.b64encode(digest.digest())
        return BlobInfo(identifier, length, "md5-" + b64digest)

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
