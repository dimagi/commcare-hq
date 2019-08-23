"""Test S3 Blob DB

Commands to setup Docker with minio for development/testing

First, [install Docker](https://docs.docker.com/mac/#h_installation).

Initialize a docker machine for minio (skip if you already have one):

    docker-machine create --driver virtualbox minio
    eval "$(docker-machine env minio)"

Start the minio service:

    mkdir -p ~/.minio/data && mkdir ~/.minio/conf

    # INSECURE KEY VALUES FOR TESTING ONLY, DO NOT USE IN PRODUCTION!
    docker run -p 9988:9000 --name minio1 --detach \
      -e "MINIO_ACCESS_KEY=admin-key" \
      -e "MINIO_SECRET_KEY=admin-secret" \
      -v ~/.minio/data:/data \
      -v ~/.minio/conf:/root/.minio \
      minio/minio server /data

Test minio connection:

    DOCKER_MINIO_HOST=$(echo $DOCKER_HOST | cut -d/ -f3 | cut -d: -f1)
    curl -i http://$DOCKER_MINIO_HOST:9988; echo ""
    # expected output:
    # HTTP/1.1 403 Forbidden
    # ...

Finally, add the following to `localsettings.py`:

    def _get_s3_params():
        # these can change depending on host state
        import os, re, subprocess
        def run(command, pattern=None, group=1):
            out = subprocess.check_output(command.split())
            return re.search(pattern, out).group(group) if pattern else out
        try:
            evars = run("docker-machine env minio")
            for match in re.finditer(r'export (.*?)="(.*?)"', evars):
                os.environ[match.group(1)] = match.group(2)
            host = re.search(r'DOCKER_HOST="tcp://(.*?):', evars).group(1)
            port = run("docker port minio1 9000", r':(\d+)')
            return {"host": host, "port": port}
        except Exception:
            return None  # docker host is not running
    _s3_params = _get_s3_params()
    if _s3_params:
        S3_BLOB_DB_SETTINGS = {
            "url": "http://{host}:{port}".format(**_s3_params),

            # NOTE: THESE KEYS ARE INSECURE AND MEANT FOR TESTING ONLY
            "access_key": "admin-key",
            "secret_key": "admin-secret",

            # reduce timeouts to make tests fail faster
            "config": {"connect_timeout": 1, "read_timeout": 1}
        }

"""  # noqa: W605
from __future__ import unicode_literals
from __future__ import absolute_import
from io import BytesIO, SEEK_SET, TextIOWrapper

from django.conf import settings
from django.test import TestCase

from corehq.blobs.s3db import S3BlobDB, BlobStream
from corehq.blobs.tests.util import new_meta, TemporaryS3BlobDB
from corehq.blobs.tests.test_fsdb import _BlobDBTests
from corehq.util.test_utils import trap_extra_setup


class TestS3BlobDB(TestCase, _BlobDBTests):

    @classmethod
    def setUpClass(cls):
        super(TestS3BlobDB, cls).setUpClass()
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
        cls.db = TemporaryS3BlobDB(config)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(TestS3BlobDB, cls).tearDownClass()

    def test_put_from_other_s3_db(self):
        # cleanup will be done by self.db
        db2 = S3BlobDB(settings.S3_BLOB_DB_SETTINGS)
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        with self.db.get(meta.key) as blob:
            meta2 = db2.put(blob, meta=new_meta())
        self.assertEqual(meta2.content_length, meta.content_length)
        with db2.get(meta2.key) as blob2:
            self.assertEqual(blob2.read(), b"content")


class TestBlobStream(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestBlobStream, cls).setUpClass()
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
        cls.db = TemporaryS3BlobDB(config)
        cls.meta = cls.db.put(BytesIO(b"bytes"), meta=new_meta())

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(TestBlobStream, cls).tearDownClass()

    def test_text_io_wrapper(self):
        meta = self.db.put(BytesIO(b"x\ny\rz\n"), meta=new_meta())
        with self.db.get(key=meta.key) as fh:
            # universl unewline mode: \r -> \n
            textio = TextIOWrapper(fh, encoding="utf-8")
            self.assertEqual(list(textio), ["x\n", "y\n", "z\n"])

    def test_checks(self):
        with self.get_blob() as fh:
            self.assertTrue(fh.readable())
            self.assertFalse(fh.seekable())
            self.assertFalse(fh.writable())
            self.assertFalse(fh.isatty())

    def test_tell(self):
        with self.get_blob() as fh:
            self.assertEqual(fh.tell(), 0)
            self.assertEqual(fh.read(2), b"by")
            self.assertEqual(fh.tell(), 2)

    def test_seek(self):
        with self.get_blob() as fh:
            self.assertEqual(fh.seek(0), 0)
            fh.read(2)
            self.assertEqual(fh.seek(2, SEEK_SET), 2)

    def test_write(self):
        with self.get_blob() as fh, self.assertRaises(IOError):
            fh.write(b"def")

    def test_truncate(self):
        with self.get_blob() as fh, self.assertRaises(IOError):
            fh.truncate()

    def test_fileno(self):
        with self.get_blob() as fh, self.assertRaises(IOError):
            fh.fileno()

    def test_closed(self):
        with self.get_blob() as fh:
            self.assertFalse(fh.closed)
        self.assertTrue(fh.closed)

    def test_close(self):
        fake = FakeStream()
        self.assertEqual(fake.close_calls, 0)
        BlobStream(fake, fake, None).close()
        self.assertEqual(fake.close_calls, 1)

    def test_close_on_exit_context(self):
        fake = FakeStream()
        self.assertEqual(fake.close_calls, 0)
        with BlobStream(fake, fake, None):
            pass
        self.assertEqual(fake.close_calls, 1)

    def get_blob(self):
        return self.db.get(key=self.meta.key)


class FakeStream(object):
    close_calls = 0

    def close(self):
        self.close_calls += 1
