import os

import pytest
from unmagic import use

from corehq.apps.dump_reload.archive import (
    ZipWithZstdArchiveReader,
    ZipWithZstdArchiveWriter,
)
from corehq.apps.dump_reload.archive import zip_with_zstd

from ._common import tmp_work_dir


def test_zstd_writer_rejects_path_without_zip_suffix():
    with pytest.raises(ValueError, match=r"\.zip"):
        ZipWithZstdArchiveWriter("data-dump-foo")


def test_zstd_reader_rejects_path_without_zip_suffix():
    with pytest.raises(ValueError, match=r"\.zip"):
        ZipWithZstdArchiveReader("data-dump-foo")


@use(tmp_work_dir)
def test_zstd_writer_round_trips_streams_and_meta():
    tmp_path = tmp_work_dir()
    with ZipWithZstdArchiveWriter("data-dump-foo.zip") as writer:
        with writer.open_stream("sql") as stream:
            stream.write('{"model": "auth.User"}\n')
            stream.write('{"model": "auth.User"}\n')
            stream.meta = {"auth.User": 2}
        with writer.open_stream("couch") as stream:
            stream.write('{"doc_type": "CommCareUser"}\n')
            stream.meta = {"users.CommCareUser": 1}

    with ZipWithZstdArchiveReader(str(tmp_path / "data-dump-foo.zip")) as reader:
        assert reader.meta == {
            "sql": {"auth.User": 2},
            "couch": {"users.CommCareUser": 1},
        }
        with reader.open_stream("sql") as stream:
            assert stream.meta == {"auth.User": 2}
            assert stream.read() == (
                b'{"model": "auth.User"}\n'
                b'{"model": "auth.User"}\n'
            )
        with reader.open_stream("couch") as stream:
            assert stream.read() == b'{"doc_type": "CommCareUser"}\n'


@use(tmp_work_dir)
def test_zstd_writer_uses_zip_zstandard_compression():
    tmp_path = tmp_work_dir()
    with ZipWithZstdArchiveWriter("data-dump-foo.zip") as writer:
        with writer.open_stream("sql") as stream:
            stream.write('{"model": "auth.User"}\n')
            stream.meta = {}
        with writer.open_stream("couch") as stream:
            stream.write('{"doc_type": "X"}\n')
            stream.meta = {}

    # Use the same zipfile module the writer used, so we can read the
    # ZIP_ZSTANDARD compression method.
    zf_mod = zip_with_zstd.zipfile
    with zf_mod.ZipFile(tmp_path / "data-dump-foo.zip") as z:
        assert z.namelist() == ["sql", "couch", "meta.json"]
        assert z.getinfo("sql").compress_type == zf_mod.ZIP_ZSTANDARD
        assert z.getinfo("couch").compress_type == zf_mod.ZIP_ZSTANDARD


@use(tmp_work_dir)
def test_zstd_writer_leaves_no_temp_files():
    tmp_path = tmp_work_dir()
    with ZipWithZstdArchiveWriter("data-dump-foo.zip") as writer:
        with writer.open_stream("sql") as stream:
            stream.write("x\n")
            stream.meta = {}
    # Only the .zip on disk — streaming compression never writes a temp file.
    assert sorted(os.listdir(tmp_path)) == ["data-dump-foo.zip"]


@use(tmp_work_dir)
def test_zstd_writer_raises_when_stream_meta_not_set():
    tmp_work_dir()
    with pytest.raises(RuntimeError, match=r"meta not set for stream 'sql'"):
        with ZipWithZstdArchiveWriter("data-dump-foo.zip") as writer:
            with writer.open_stream("sql") as stream:
                stream.write("x\n")


@use(tmp_work_dir)
def test_zstd_reader_open_stream_handle_carries_per_stream_meta():
    tmp_path = tmp_work_dir()
    with ZipWithZstdArchiveWriter("data-dump-foo.zip") as writer:
        with writer.open_stream("sql") as stream:
            stream.write('{"model": "auth.User"}\n')
            stream.meta = {"auth.User": 1}

    with ZipWithZstdArchiveReader(str(tmp_path / "data-dump-foo.zip")) as reader:
        with reader.open_stream("sql") as stream:
            assert stream.meta == {"auth.User": 1}
