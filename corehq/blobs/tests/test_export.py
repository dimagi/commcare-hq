import doctest
import io
import os
import tarfile
from collections import namedtuple
from contextlib import redirect_stdout
from io import BytesIO, RawIOBase
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest import mock

import gevent
import pytest
from django.test import SimpleTestCase, TestCase

from corehq.blobs import CODES, get_blob_db
from corehq.blobs import export as export_module
from corehq.blobs.exceptions import NotFound
from corehq.blobs.export import (
    BlobDbBackendExporter,
    BlobExporter,
    _Result,
    _SKIPPED,
    missing_ids_filename_for,
)
from corehq.blobs.management.commands.run_blob_import import Command as ImportCommand
from corehq.blobs.targzipdb import TarGzipBlobDB
from corehq.blobs.tests.fixtures import blob_db
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB, new_meta

_Meta = namedtuple('_Meta', 'key')


@pytest.mark.parametrize("export_filename, expected", [
    # full archive path: same dir and prefix, .tar.gz stripped
    ("/data/2026-06-25_14.32-mydomain-blobs.tar.gz",
     "/data/2026-06-25_14.32-mydomain-blobs-missing_blob_ids.txt"),
    # -part / -db suffixes are part of the prefix and carried through
    ("/data/2026-06-25_14.32-mydomain-blobs-part-p0.tar.gz",
     "/data/2026-06-25_14.32-mydomain-blobs-part-p0-missing_blob_ids.txt"),
    # no directory -> sits beside the archive in the cwd
    ("export.tar.gz", "export-missing_blob_ids.txt"),
    # no .tar.gz suffix (e.g. a bare temp file in tests) -> append as-is
    ("/data/export", "/data/export-missing_blob_ids.txt"),
])
def test_missing_ids_filename_for(export_filename, expected):
    assert missing_ids_filename_for(export_filename) == expected


def test_exporter_derives_missing_ids_path_from_export_file():
    with mock.patch.object(export_module, 'get_blob_db'):
        migrator = BlobDbBackendExporter(
            "/data/2026-06-25_14.32-mydomain-blobs.tar.gz", None)
    assert migrator.missing_ids_filename == (
        "/data/2026-06-25_14.32-mydomain-blobs-missing_blob_ids.txt")


class _YieldingStream(io.BytesIO):
    """BytesIO that yields to other greenlets on every read, to force
    interleaving opportunities during the parallel export."""

    def __init__(self, data):
        super().__init__(data)
        self.content_length = len(data)

    def read(self, *args, **kwargs):
        gevent.sleep(0)
        return super().read(*args, **kwargs)


class _YieldingFakeSrcDB:
    def __init__(self, blobs):
        self.blobs = blobs  # {key: bytes}

    def get(self, key, type_code=None):
        gevent.sleep(0)  # force a context switch before returning the stream
        if key not in self.blobs:
            raise NotFound(key)
        return _YieldingStream(self.blobs[key])


def _export_with_fake_src(blobs, metas, already_exported=None, concurrency=8, src_db=None,
                          progress_interval=100):
    """Run a parallel export against a fake source DB; return (names->bytes, missing_ids, total)."""
    if src_db is None:
        src_db = _YieldingFakeSrcDB(blobs)
    with mock.patch.object(export_module, 'get_blob_db', return_value=src_db), \
            NamedTemporaryFile(suffix='.tar.gz') as out, \
            TemporaryDirectory() as tmpdir:
        migrator = BlobDbBackendExporter(out.name, already_exported, concurrency=concurrency)
        migrator.missing_ids_filename = os.path.join(tmpdir, 'missing_blob_ids.txt')
        with migrator:
            migrator.run(metas, progress_interval=progress_interval)
        with tarfile.open(out.name, 'r:gz') as tgz:
            extracted = {n: tgz.extractfile(n).read() for n in tgz.getnames()}
        return extracted, migrator.missing_ids, migrator.total_blobs


@pytest.mark.parametrize("kwargs", [
    {},  # fetched: key + fileobj + content_length
    {"missing": True},  # missing: key + missing flag
])
def test_result_valid_states(kwargs):
    # fetched/missing both carry a key; the only difference is the payload
    if kwargs:
        _Result("k", **kwargs)
    else:
        _Result("k", fileobj=io.BytesIO(b'data'), content_length=4)


def test_result_skipped_constant_is_valid():
    assert _SKIPPED.key is None
    assert _SKIPPED.fileobj is None
    assert not _SKIPPED.missing


@pytest.mark.parametrize("args, kwargs", [
    # fetched without a content_length is not a complete fetched result, and
    # has no other state set, so it is not any valid state
    (("k",), {"fileobj": io.BytesIO(b'data')}),
    # fetched payload on a keyless (skipped) result -> two states at once
    ((None,), {"fileobj": io.BytesIO(b'data'), "content_length": 4}),
    # keyless and flagged missing -> skipped and missing at once
    ((None,), {"missing": True}),
    # fetched payload and flagged missing -> two states at once
    (("k",), {"fileobj": io.BytesIO(b'data'), "content_length": 4, "missing": True}),
])
def test_result_invalid_states_raise(args, kwargs):
    with pytest.raises(AssertionError):
        _Result(*args, **kwargs)


class TestExportRun(SimpleTestCase):

    def test_all_blobs_written_intact_under_concurrency(self):
        # varied sizes, including a blob larger than a chunk read, to exercise
        # multi-read copies that interleave across greenlets
        blobs = {f'key-{i}': bytes([i % 256]) * (i * 37) for i in range(1, 31)}
        metas = [_Meta(k) for k in blobs]

        extracted, missing, total = _export_with_fake_src(blobs, metas)

        assert extracted == blobs  # every blob present and byte-identical
        assert missing == []
        assert total == 30

    def test_missing_blob_is_recorded(self):
        blobs = {'present': b'data'}
        metas = [_Meta('present'), _Meta('absent')]

        extracted, missing, total = _export_with_fake_src(blobs, metas)

        assert set(extracted) == {'present'}
        assert missing == ['absent']
        assert total == 2

    def test_already_exported_blobs_are_skipped_but_counted(self):
        """Already-exported blobs are not re-written, but are still counted --
        in the total and the per-chunk progress heartbeat -- matching the
        original sequential exporter."""
        blobs = {f'k{i}': b'x' for i in range(150)}
        metas = [_Meta(k) for k in blobs]

        out = io.StringIO()
        with redirect_stdout(out):
            extracted, missing, total = _export_with_fake_src(
                blobs, metas, already_exported=set(blobs))

        assert extracted == {}  # nothing re-written
        assert total == 150  # all counted
        assert "Processed 100 objects (last 100 in " in out.getvalue()  # and reported

    def test_blob_larger_than_spill_threshold_round_trips(self):
        with mock.patch.object(export_module, 'SPILL_THRESHOLD', 16):
            blobs = {'big': b'x' * 1000}  # 1000 > 16 -> spills to disk
            metas = [_Meta('big')]
            extracted, missing, total = _export_with_fake_src(blobs, metas)
        assert extracted == blobs

    def test_spill_files_are_written_to_the_output_directory(self):
        """Spilled blob buffers go next to the output archive, not the system
        temp dir, so the operator's chosen disk absorbs the I/O."""
        captured = []
        real_spooled = export_module.SpooledTemporaryFile

        def spy(*args, **kwargs):
            captured.append(kwargs.get('dir'))
            return real_spooled(*args, **kwargs)

        blobs = {'k': b'data'}
        with TemporaryDirectory() as outdir:
            out_path = os.path.join(outdir, 'export.tar.gz')
            with mock.patch.object(export_module, 'get_blob_db',
                                   return_value=_YieldingFakeSrcDB(blobs)), \
                    mock.patch.object(export_module, 'SpooledTemporaryFile',
                                      side_effect=spy):
                migrator = BlobDbBackendExporter(out_path, None, concurrency=2)
                migrator.missing_ids_filename = os.path.join(outdir, 'missing.txt')
                with migrator:
                    migrator.run([_Meta('k')], progress_interval=100)
            assert captured == [outdir]

    def test_non_notfound_fetch_error_propagates(self):
        """A fetch error that is not NotFound must propagate, aborting the export."""

        class _ErrorDB(_YieldingFakeSrcDB):
            def get(self, key, type_code=None):
                if key == 'bad':
                    raise RuntimeError("boom")
                return super().get(key, type_code)

        blobs = {'ok': b'fine', 'bad': b'never'}
        metas = [_Meta('ok'), _Meta('bad')]
        src_db = _ErrorDB(blobs)
        with self.assertRaises(RuntimeError):
            _export_with_fake_src(blobs, metas, src_db=src_db)


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

    def test_progress_and_summary_report_throughput(self):
        for _ in range(3):
            self.db.put(BytesIO(self.blob_data), meta=new_meta(domain=self.domain, type_code=CODES.form_xml))

        out = io.StringIO()
        with NamedTemporaryFile() as f, redirect_stdout(out):
            self.exporter.migrate(f.name, progress_interval=2, force=True)
        printed = out.getvalue()
        # per-chunk line at the 2-object boundary, then the final summary
        assert "Processed 2 objects (last 2 in " in printed
        assert "Processed 3 objects in " in printed
        assert "/1M objects)" in printed

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

        # migrate() writes a missing-blob-ids log beside the export archive for
        # the orphaned meta; export into a temp dir so both files are cleaned up
        # and the test does not pollute the repo root.
        with TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, 'export.tar.gz')
            self.exporter.migrate(out, force=True)
            with tarfile.open(out, 'r:gz') as tgzfile:
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


class TestTarGzipCopyBlobContentLength(SimpleTestCase):

    def test_explicit_content_length_used_for_fileobj_without_attribute(self):
        data = b'spam and eggs'
        with NamedTemporaryFile(suffix='.tar.gz') as out:
            db = TarGzipBlobDB(out.name)
            db.open('w:gz')
            # io.BytesIO has no `content_length` attribute
            db.copy_blob(io.BytesIO(data), key='k', content_length=len(data))
            db.close()

            with tarfile.open(out.name, 'r:gz') as tgz:
                member = tgz.getmember('k')
                assert member.size == len(data)
                assert tgz.extractfile('k').read() == data


def test_doctests():
    from corehq.blobs import targzipdb

    results = doctest.testmod(targzipdb)
    assert results.failed == 0
