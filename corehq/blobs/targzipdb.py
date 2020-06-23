import tarfile

from corehq.blobs.interface import AbstractBlobDB


class TarGzipBlobDB(AbstractBlobDB):
    """
    Stores blobs in a ".tar.gz" file. Used for exporting a domain's
    blobs.

    Avoids memory problems by compressing data without reading it all
    into memory first.
    """

    def __init__(self, filename, extends):
        super().__init__()
        self.filename = filename
        self.extends = extends
        self._tgzfile = None
        self._names = None

    def open(self, mode='r:gz'):
        self._tgzfile = tarfile.open(self.filename, mode)

    def close(self):
        self._tgzfile.close()
        self._tgzfile = None

    def put(self, **blob_meta_args):
        raise NotImplementedError

    def get(self, key=None, type_code=None, meta=None):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

    def bulk_delete(self, metas):
        raise NotImplementedError

    def copy_blob(self, in_fileobj, key):
        """
        Streams content from ``in_fileobj`` to a tar gzip file.

        .. NOTE::
            ``copy_blob()`` does not include BlobMeta. In order to
            rebuild the blob DB in another environment, you will also
            need to use the ``dump_domain_data`` management command.

        """
        if not self.exists(key):
            tarinfo = tarfile.TarInfo(name=key)
            tarinfo.size = in_fileobj.content_length
            self._tgzfile.addfile(tarinfo, in_fileobj)

    def exists(self, key):
        if self._names is None:
            self._names = set()
            for filename in self.extends:
                with tarfile.open(filename, 'r:gz') as tgzfile:
                    self._names.update(tgzfile.getnames())
        return key in self._names

    def size(self, key):
        raise NotImplementedError


def get_export_filename(slug, domain, extends):
    """
    Returns a filename that includes filenames in ``extends``

    >>> get_export_filename('multimedia', 'domain',
    ...                     ['oldexport.tar.gz', 'olderexport.tar.gz'])
    'export-domain-multimedia-blobs-extends-oldexport+olderexport.tar.gz'

    """
    filenames = [strip_tar_gz(f) for f in extends]
    _extends = '-extends-' + '+'.join(filenames) if filenames else ''
    return f'export-{domain}-{slug}-blobs{_extends}.tar.gz'


def strip_tar_gz(filename):
    """
    Strips ".tar.gz" extensions.

    >>> strip_tar_gz('spam.tar.gz')
    'spam'
    >>> strip_tar_gz('spam.ham')
    'spam.ham'

    """
    if filename.endswith('.tar.gz'):
        return filename[:-7]
    return filename
