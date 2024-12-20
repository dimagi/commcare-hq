from unmagic import fixture

from corehq.blobs import get_blob_db
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB


@fixture
def blob_db():
    with TemporaryFilesystemBlobDB() as blob_db:
        assert get_blob_db() is blob_db, (get_blob_db(), blob_db)
        yield blob_db
