import os
import tarfile
import uuid
from io import BytesIO, RawIOBase
from math import ceil
from tempfile import NamedTemporaryFile
from unittest import skip

from django.test import SimpleTestCase, TestCase

from corehq.apps.hqmedia.models import (
    CommCareAudio,
    CommCareImage,
    CommCareVideo,
)
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.export import EXPORTERS
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB, new_meta


class TestBlobExport(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.db = TemporaryFilesystemBlobDB()
        assert get_blob_db() is cls.db, (get_blob_db(), cls.db)
        data = b'binary data not valid utf-8 \xe4\x94'
        cls.blob_metas = []
        cls.not_found = set()

        cls.domain_name = str(uuid.uuid4)

        for type_code in [CODES.form_xml, CODES.multimedia, CODES.data_export]:
            for domain in (cls.domain_name, str(uuid.uuid4())):
                meta = cls.db.put(BytesIO(data), meta=new_meta(domain=domain, type_code=type_code))
                lost = new_meta(domain=domain, type_code=type_code, content_length=42)
                cls.blob_metas.append(meta)
                cls.blob_metas.append(lost)
                lost.save()
                cls.not_found.add(lost.key)

    @classmethod
    def tearDownClass(cls):
        for blob in cls.blob_metas:
            blob.delete()
        cls.db.close()
        super().tearDownClass()

    def test_migrate_all(self):
        expected = {
            m.key for m in self.blob_metas
            if m.domain == self.domain_name and m.key not in self.not_found
        }
        with NamedTemporaryFile() as out:
            exporter = EXPORTERS['all_blobs'](self.domain_name)
            exporter.migrate(out.name, force=True)
            with tarfile.open(out.name, 'r:gz') as tgzfile:
                self.assertEqual(expected, set(tgzfile.getnames()))

    def test_migrate_multimedia(self):
        image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'images',
                                  'commcare-hq-logo.png')
        with open(image_path, 'rb') as f:
            image_data = f.read()

        files = (
            (CommCareImage, self.domain_name, image_data),
            (CommCareAudio, self.domain_name, b'fake audio'),
            (CommCareVideo, self.domain_name, b'fake video'),
            (CommCareAudio, 'other_domain', b'fake audio 1'),
        )

        blob_keys = []
        for doc_class, domain, data in files:
            obj = doc_class.get_by_data(data)
            obj.attach_data(data)
            obj.add_domain(domain)
            self.addCleanup(obj.delete)
            self.assertEqual(data, obj.get_display_file(False))
            blob_keys.append(obj.blobs[obj.attachment_id].key)

        expected = set(blob_keys[:-1])
        with NamedTemporaryFile() as out:
            exporter = EXPORTERS['multimedia'](self.domain_name)
            exporter.migrate(out.name, force=True)
            with tarfile.open(out.name, 'r:gz') as tgzfile:
                self.assertEqual(expected, set(tgzfile.getnames()))


@skip('Takes a while, and uses as much drive space as there is RAM')
class TestBigBlobExport(TestCase):

    domain_name = 'big-blob-test-domain'

    def setUp(self):
        # psutil is in dev-requirements only. Don't bother trying to
        # import for the module if the test is skipped.
        from psutil import virtual_memory

        self.memory = virtual_memory().total
        self.db = TemporaryFilesystemBlobDB()
        assert get_blob_db() is self.db, (get_blob_db(), self.db)
        self.blob_metas = []

    def tearDown(self):
        for meta in self.blob_metas:
            meta.delete()
        self.db.close()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        MB = 1024 ** 2
        self.mb_block = b'\x00' * MB

    def mb_blocks(self):
        while True:
            yield self.mb_block

    def test_many_big_blobs(self):
        number_of_1gb_blobs = ceil(self.memory / 1024 ** 3) + 1

        for __ in range(number_of_1gb_blobs):
            meta = self.db.put(
                MockBigBlobIO(self.mb_blocks(), 1024),
                meta=new_meta(domain=self.domain_name, type_code=CODES.multimedia)
            )
            self.blob_metas.append(meta)

        with NamedTemporaryFile() as out:
            exporter = EXPORTERS['all_blobs'](self.domain_name)
            exporter.migrate(out.name, force=True)

            with tarfile.open(out.name, 'r:gz') as tgzfile:
                self.assertEqual(
                    set(tgzfile.getnames()),
                    {m.key for m in self.blob_metas}
                )

    def test_1_very_big_blob(self):
        number_of_1mb_blocks = ceil(self.memory / 1024 ** 2) + 1

        meta = self.db.put(
            MockBigBlobIO(self.mb_blocks(), number_of_1mb_blocks),
            meta=new_meta(domain=self.domain_name, type_code=CODES.multimedia)
        )
        self.blob_metas.append(meta)

        with NamedTemporaryFile() as out:
            exporter = EXPORTERS['all_blobs'](self.domain_name)
            exporter.migrate(out.name, force=True)

            with tarfile.open(out.name, 'r:gz') as tgzfile:
                self.assertEqual(
                    set(tgzfile.getnames()),
                    {m.key for m in self.blob_metas}
                )


class TestMockBigBlobIO(SimpleTestCase):

    @staticmethod
    def two_zeros():
        # Test for block size = 2 bytes
        while True:
            yield b'\x00\x00'

    def test_zeros(self):
        maybe_byte = next(self.two_zeros())
        self.assertIsInstance(maybe_byte, bytes)

    def test_read(self):
        big_blob = MockBigBlobIO(self.two_zeros(), 100)
        data = big_blob.read()
        self.assertEqual(len(data), 200)

    def test_read_size(self):
        big_blob = MockBigBlobIO(self.two_zeros(), 100)
        data = big_blob.read(10)
        self.assertEqual(len(data), 20)

    def test_read_chunks(self):
        big_blob = MockBigBlobIO(self.two_zeros(), 100)
        data1 = big_blob.read(25)
        data2 = big_blob.read(100)
        self.assertEqual(len(data1) + len(data2), 200)


class MockBigBlobIO(RawIOBase):
    """
    A file-like object used for mocking a very large blob.

    Consumes blocks of bytes from a generator up to a maximum number of
    blocks.
    """
    def __init__(self, bytes_gen, max_blocks):
        self.generator = bytes_gen
        self.blocks = max_blocks
        self._consumed = 0

    def readable(self):
        return True

    def seekable(self):
        return False

    def writable(self):
        return False

    def read(self, blocks=None):
        blocks_remaining = self.blocks - self._consumed
        if blocks is None or blocks < 0:
            blocks = blocks_remaining
        blocks = min(blocks, blocks_remaining)
        if blocks > 0:
            chunk = b''.join((next(self.generator) for __ in range(blocks)))
            self._consumed = self._consumed + blocks
            return bytes(chunk)

    def readall(self):
        return self.read()

    def readinto(self, buffer):
        raise NotImplementedError
