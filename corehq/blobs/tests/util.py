from shutil import rmtree
from tempfile import mkdtemp

import corehq.blobs as blobs
from corehq.blobs.fsdb import FilesystemBlobDB


class TemporaryFilesystemBlobDB(FilesystemBlobDB):
    """Create temporary blob db and install as global blob db

    Global blob DB can be retrieved with `corehq.blobs.get_blob_db()`
    """

    def __init__(self):
        rootdir = mkdtemp(prefix="blobdb")
        super(TemporaryFilesystemBlobDB, self).__init__(rootdir)

        blobs._db.append(self)
        try:
            # verify get_blob_db() returns our new db
            assert blobs.get_blob_db() is self, 'got wrong blob db'
        except:
            self.close()
            raise

    def close(self):
        try:
            blobs._db.remove(self)
        finally:
            rmtree(self.rootdir)
            self.rootdir = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
