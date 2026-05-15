import gzip
import json
import os
import zipfile

import pytest
from unmagic import use

from corehq.apps.dump_reload.archive import (
    ExtractedDumpExistsError,
    ZippedGzipArchiveReader,
    ZippedGzipArchiveWriter,
)
from corehq.apps.dump_reload.archive.utils import get_tmp_extract_dir

from ._common import tmp_work_dir


def test_writer_rejects_path_without_zip_suffix():
    with pytest.raises(ValueError, match=r"\.zip"):
        ZippedGzipArchiveWriter("data-dump-foo")


@use(tmp_work_dir)
def test_writer_writes_streams_and_meta_to_zip():
    tmp_path = tmp_work_dir()
    with ZippedGzipArchiveWriter("data-dump-foo.zip") as writer:
        with writer.open_stream("sql") as stream:
            stream.write('{"model": "auth.User"}\n')
            stream.write('{"model": "auth.User"}\n')
            stream.meta = {"auth.User": 2}
        with writer.open_stream("couch") as stream:
            stream.write('{"doc_type": "CommCareUser"}\n')
            stream.meta = {"users.CommCareUser": 1}

    archive_path = tmp_path / "data-dump-foo.zip"
    assert archive_path.exists()
    with zipfile.ZipFile(archive_path) as z:
        names = z.namelist()
        assert names == ["sql.gz", "couch.gz", "meta.json"]
        with z.open("sql.gz") as raw, gzip.open(raw, "rt") as gz:
            assert gz.read() == (
                '{"model": "auth.User"}\n'
                '{"model": "auth.User"}\n'
            )
        with z.open("couch.gz") as raw, gzip.open(raw, "rt") as gz:
            assert gz.read() == '{"doc_type": "CommCareUser"}\n'
        meta = json.loads(z.read("meta.json"))
        assert meta == {
            "sql": {"auth.User": 2},
            "couch": {"users.CommCareUser": 1},
        }


@use(tmp_work_dir)
def test_writer_raises_when_stream_meta_not_set():
    tmp_work_dir()
    with pytest.raises(RuntimeError, match=r"meta not set for stream 'sql'"):
        with ZippedGzipArchiveWriter("data-dump-foo.zip") as writer:
            with writer.open_stream("sql") as stream:
                stream.write("x\n")
                # forgot to set stream.meta


@use(tmp_work_dir)
def test_writer_cleans_up_temp_file_on_success():
    tmp_path = tmp_work_dir()
    with ZippedGzipArchiveWriter("data-dump-foo.zip") as writer:
        with writer.open_stream("sql") as stream:
            stream.write("x\n")
            stream.meta = {}
    # Only the .zip remains in the directory.
    assert sorted(os.listdir(tmp_path)) == ["data-dump-foo.zip"]


@use(tmp_work_dir)
def test_writer_skips_zip_append_when_inner_block_raises():
    tmp_path = tmp_work_dir()
    with pytest.raises(RuntimeError, match="boom"):
        with ZippedGzipArchiveWriter("data-dump-foo.zip") as writer:
            with writer.open_stream("sql") as stream:
                stream.write("partial\n")
                raise RuntimeError("boom")
    # The archive should not exist: nothing was appended and meta.json
    # was never finalized.
    assert not (tmp_path / "data-dump-foo.zip").exists()


@use(tmp_work_dir)
def test_writer_skips_meta_when_writer_block_raises():
    tmp_path = tmp_work_dir()
    with pytest.raises(RuntimeError, match="boom"):
        with ZippedGzipArchiveWriter("data-dump-foo.zip") as writer:
            with writer.open_stream("sql") as stream:
                stream.write("x\n")
                stream.meta = {}
            raise RuntimeError("boom")
    # The first stream was added but meta.json was not.
    with zipfile.ZipFile(tmp_path / "data-dump-foo.zip") as z:
        assert z.namelist() == ["sql.gz"]


def test_reader_rejects_path_without_zip_suffix():
    with pytest.raises(ValueError, match=r"\.zip"):
        ZippedGzipArchiveReader("data-dump-foo")


def test_extracted_dump_exists_error_carries_path():
    err = ExtractedDumpExistsError("/some/path")
    assert err.path == "/some/path"
    assert "/some/path" in str(err)


def _build_archive(tmp_path, name="data-dump-foo.zip"):
    """Helper: write a small one-stream archive into tmp_path and return its
    name. Assumes the caller is already chdir'd to tmp_path.
    """
    with ZippedGzipArchiveWriter(name) as writer:
        with writer.open_stream("sql") as stream:
            stream.write('{"model": "auth.User"}\n')
            stream.meta = {"auth.User": 1}
    return name


@use(tmp_work_dir)
def test_reader_extracts_zip_on_enter():
    tmp_path = tmp_work_dir()
    name = _build_archive(tmp_path)
    with ZippedGzipArchiveReader(name):
        target_dir = get_tmp_extract_dir(name)
        assert os.path.isdir(target_dir)
        assert os.path.isfile(os.path.join(target_dir, "sql.gz"))
        assert os.path.isfile(os.path.join(target_dir, "meta.json"))


@use(tmp_work_dir)
def test_reader_rejects_existing_dir_without_use_extracted():
    tmp_path = tmp_work_dir()
    name = _build_archive(tmp_path)
    # First open extracts.
    with ZippedGzipArchiveReader(name):
        pass
    # Second open must reject because the extracted dir already exists.
    with pytest.raises(ExtractedDumpExistsError) as excinfo:
        with ZippedGzipArchiveReader(name):
            pass
    assert excinfo.value.path == get_tmp_extract_dir(name)


@use(tmp_work_dir)
def test_reader_reuses_existing_dir_with_use_extracted():
    tmp_path = tmp_work_dir()
    name = _build_archive(tmp_path)
    with ZippedGzipArchiveReader(name):
        pass
    with ZippedGzipArchiveReader(name, use_extracted=True):
        target_dir = get_tmp_extract_dir(name)
        assert os.path.isfile(os.path.join(target_dir, "meta.json"))


@use(tmp_work_dir)
def test_reader_open_stream_yields_bytes_lines():
    tmp_path = tmp_work_dir()
    name = _build_archive(tmp_path)
    with ZippedGzipArchiveReader(name) as reader:
        with reader.open_stream("sql") as stream:
            lines = list(stream)
    assert lines == [b'{"model": "auth.User"}\n']


@use(tmp_work_dir)
def test_reader_open_stream_handle_carries_per_stream_meta():
    tmp_path = tmp_work_dir()
    name = _build_archive(tmp_path)
    with ZippedGzipArchiveReader(name) as reader:
        with reader.open_stream("sql") as stream:
            assert stream.meta == {"auth.User": 1}
