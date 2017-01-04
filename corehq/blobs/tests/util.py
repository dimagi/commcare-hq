from shutil import rmtree
from tempfile import mkdtemp
from uuid import uuid4

import corehq.blobs as blobs
from corehq.blobs.fsdb import FilesystemBlobDB
from corehq.blobs.s3db import S3BlobDB
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.blobs.util import random_url_id


def get_id():
    return random_url_id(8)


class TemporaryBlobDBMixin(object):
    """Create temporary blob db and install as global blob db

    Global blob DB can be retrieved with `corehq.blobs.get_blob_db()`
    """

    def __init__(self, *args, **kw):
        super(TemporaryBlobDBMixin, self).__init__(*args, **kw)

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
            self.clean_db()

    def clean_db(self):
        raise NotImplementedError("abstract method")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


class TemporaryFilesystemBlobDB(TemporaryBlobDBMixin, FilesystemBlobDB):

    def __init__(self):
        rootdir = mkdtemp(prefix="blobdb")
        super(TemporaryFilesystemBlobDB, self).__init__(rootdir)

    def clean_db(self):
        rmtree(self.rootdir)
        self.rootdir = None


class TemporaryS3BlobDB(TemporaryBlobDBMixin, S3BlobDB):

    def __init__(self, config):
        name_parts = ["test", config.get("s3_bucket", "blobdb"), uuid4().hex]
        config = dict(config)
        config["s3_bucket"] = "-".join(name_parts)
        super(TemporaryS3BlobDB, self).__init__(config)
        assert self.s3_bucket_name == config["s3_bucket"], \
            (self.s3_bucket_name, config)

    def clean_db(self):
        if not self._s3_bucket_exists:
            return
        assert self.s3_bucket_name.startswith("test-"), self.s3_bucket_name
        s3_bucket = self._s3_bucket()
        summaries = s3_bucket.objects.all()
        for page in summaries.pages():
            objects = [{"Key": o.key} for o in page]
            s3_bucket.delete_objects(Delete={"Objects": objects})
        s3_bucket.delete()


class TemporaryMigratingBlobDB(TemporaryBlobDBMixin, MigratingBlobDB):

    def __init__(self, *args):
        for arg in args:
            assert isinstance(arg, TemporaryBlobDBMixin), arg
        super(TemporaryMigratingBlobDB, self).__init__(*args)

    def clean_db(self):
        self.old_db.close()
        self.new_db.close()
