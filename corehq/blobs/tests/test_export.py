import doctest
import tarfile
from io import BytesIO, RawIOBase
from tempfile import NamedTemporaryFile

from django.test import SimpleTestCase, TestCase

from corehq.blobs import CODES, get_blob_db
from corehq.blobs.export import BlobExporter
from corehq.blobs.management.commands.run_blob_import import Command as ImportCommand
from corehq.blobs.tests.fixtures import blob_db
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB, new_meta


class TestBlobExporter(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'exporter-test'
        cls.blob_data = b'binary data not valid utf-8 \xe4\x94'
        cls.exporter = BlobExporter(cls.domain)

    def setUp(self):
        super().setUp()
        self.db = blob_db()

    def test_only_blob_in_targeted_domain_is_exported(self):
        # create blob that should be ignored
        self.db.put(BytesIO(self.blob_data), meta=new_meta(domain='random', type_code=CODES.form_xml))
        expected_meta = self.db.put(
            BytesIO(self.blob_data), meta=new_meta(domain=self.domain, type_code=CODES.form_xml)
        )

        with NamedTemporaryFile() as out:
            self.exporter.migrate(out.name, force=True)
            with tarfile.open(out.name, 'r:gz') as tgzfile:
                self.assertEqual([expected_meta.key], tgzfile.getnames())

    def test_different_blob_types_are_exported(self):
        form = self.db.put(BytesIO(self.blob_data), meta=new_meta(domain=self.domain, type_code=CODES.form_xml))
        multimedia = self.db.put(
            BytesIO(self.blob_data), meta=new_meta(domain=self.domain, type_code=CODES.multimedia)
        )

        with NamedTemporaryFile() as out:
            self.exporter.migrate(out.name, force=True)
            with tarfile.open(out.name, 'r:gz') as tgzfile:
                self.assertEqual({form.key, multimedia.key}, set(tgzfile.getnames()))

    def test_blob_meta_referencing_missing_blob_is_not_exported(self):
        expected_meta = self.db.put(
            BytesIO(self.blob_data), meta=new_meta(domain=self.domain, type_code=CODES.form_xml)
        )
        orphaned_meta = new_meta(domain=self.domain, type_code=CODES.form_xml, content_length=42)
        orphaned_meta.save()

        with NamedTemporaryFile() as out:
            self.exporter.migrate(out.name, force=True)
            with tarfile.open(out.name, 'r:gz') as tgzfile:
                self.assertEqual([expected_meta.key], tgzfile.getnames())

    def test_exported_blobs_can_be_imported_successfully(self):
        form = self.db.put(BytesIO(self.blob_data), meta=new_meta(domain=self.domain, type_code=CODES.form_xml))
        with NamedTemporaryFile() as out:
            self.exporter.migrate(out.name, force=True)
            with TemporaryFilesystemBlobDB() as dest_db:
                assert get_blob_db() is dest_db, (get_blob_db(), dest_db)
                ImportCommand.handle(None, out.name)
                with dest_db.get(meta=form) as fh:
                    self.assertEqual(fh.read(), self.blob_data)


class TestExtendingExport(TestCase):

    domain_name = 'extending-export-test-domain'

    def setUp(self):
        super().setUp()
        self.db = blob_db()
        self.blob_metas = []

    def tearDown(self):
        for meta in self.blob_metas:
            meta.delete()
        super().tearDown()

    def test_extends(self):

        # First export file ...
        for blob in (b'ham', b'spam', b'eggs'):
            meta_meta = new_meta(
                domain=self.domain_name,
                type_code=CODES.multimedia,
            )
            meta = self.db.put(BytesIO(blob), meta=meta_meta)  # Naming ftw
            self.blob_metas.append(meta)
        with NamedTemporaryFile() as file_one:
            exporter = BlobExporter(self.domain_name)
            exporter.migrate(file_one.name, force=True)
            with tarfile.open(file_one.name, 'r:gz') as tgzfile:
                keys_in_file_one = set(m.key for m in self.blob_metas[-3:])
                self.assertEqual(set(tgzfile.getnames()), keys_in_file_one)

            # Second export file extends first ...
            for blob in (b'foo', b'bar', b'baz'):
                meta_meta = new_meta(
                    domain=self.domain_name,
                    type_code=CODES.multimedia,
                )
                meta = self.db.put(BytesIO(blob), meta=meta_meta)
                self.blob_metas.append(meta)
            with NamedTemporaryFile() as file_two:
                exporter = BlobExporter(self.domain_name)
                exporter.migrate(
                    file_two.name,
                    already_exported=keys_in_file_one, force=True,
                )
                with tarfile.open(file_two.name, 'r:gz') as tgzfile:
                    keys_in_file_two = set(m.key for m in self.blob_metas[-3:])
                    self.assertEqual(set(tgzfile.getnames()), keys_in_file_two)

                # Third export file extends first and second ...
                for blob in (b'wibble', b'wobble', b'wubble'):
                    meta_meta = new_meta(
                        domain=self.domain_name,
                        type_code=CODES.multimedia,
                    )
                    meta = self.db.put(BytesIO(blob), meta=meta_meta)
                    self.blob_metas.append(meta)
                with NamedTemporaryFile() as file_three:
                    exporter = BlobExporter(self.domain_name)
                    exporter.migrate(
                        file_three.name,
                        already_exported=keys_in_file_one | keys_in_file_two, force=True,
                    )
                    with tarfile.open(file_three.name, 'r:gz') as tgzfile:
                        keys_in_file_three = set(m.key for m in self.blob_metas[-3:])
                        self.assertEqual(set(tgzfile.getnames()), keys_in_file_three)


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


def test_doctests():
    from corehq.blobs import targzipdb

    results = doctest.testmod(targzipdb)
    assert results.failed == 0
