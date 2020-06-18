import tarfile
import time
from io import BytesIO
from tempfile import NamedTemporaryFile
from timeit import Timer

from django.test import SimpleTestCase

from mock import patch

from corehq.blobs.management.commands.run_blob_import import (
    NUM_WORKERS,
    asyncio_run,
    import_blobs_from_tgz,
)


class MockBlobDB:
    def copy_blob(self, content, key):
        # time.sleep() is not a coroutine. Worker must run in a separate
        # thread to run concurrently.
        time.sleep(0.1)


def import_sleep():
    with patch('corehq.blobs.management.commands.run_blob_import.get_blob_db') as mock_, \
            NamedTemporaryFile() as tempfile:
        mock_.return_value = MockBlobDB()

        with tarfile.open(tempfile.name, 'w:gz') as tgzfile:
            for i in range(NUM_WORKERS):
                tarinfo = tarfile.TarInfo(name=f'key-{i}')
                fileobj = BytesIO(b'spam')
                tgzfile.addfile(tarinfo, fileobj)

        asyncio_run(import_blobs_from_tgz(tempfile.name))


class BlobImportTests(SimpleTestCase):

    def test_concurrency(self):
        duration = Timer(
            'import_sleep()',
            setup="from corehq.blobs.tests.test_blob_import import import_sleep",
        ).timeit(1)
        # 5 workers each sleeping 0.1s should take less than 0.2s
        self.assertLess(duration, 0.2)
