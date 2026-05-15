import io
import json
import sys
from contextlib import contextmanager
from functools import cached_property

if sys.version_info >= (3, 14):
    import zipfile
else:
    # Python's stdlib zipfile gained ZIP_ZSTANDARD support in 3.14.
    # backports.zstd ships the 3.14 zipfile module for older versions.
    from backports.zstd import zipfile

from .base import ArchiveReader, ArchiveWriter, WrappedStream
from .utils import (
    META_FILENAME,
    contextmanager_class,
    validate_archive_path,
    validate_stream_meta,
)


@contextmanager_class
class ZipWithZstdArchiveWriter(ArchiveWriter):
    """Streams compression directly into the zip; no intermediate temp
    files.
    """

    SUFFIX = '.zip'
    _zipfile = None

    def __init__(self, archive_path):
        validate_archive_path(archive_path, self.SUFFIX)
        self.path = archive_path
        self.meta = {}

    def __contextmanager__(self):
        self._zipfile = zipfile.ZipFile(
            self.path,
            mode='w',
            compression=zipfile.ZIP_ZSTANDARD,
            allowZip64=True,
        )
        try:
            yield self
            # Only reached on clean exit: write meta.json as the last entry.
            self._zipfile.writestr(
                META_FILENAME, json.dumps(self.meta, indent=4),
            )
        finally:
            self._zipfile.close()
            self._zipfile = None

    @contextmanager
    def open_stream(self, stream_name):
        with self._zipfile.open(stream_name, mode='w', force_zip64=True) as entry:
            text = io.TextIOWrapper(entry, encoding='utf-8', newline='')
            wrapped_stream = WrappedStream(text)
            try:
                yield wrapped_stream
                validate_stream_meta(wrapped_stream, stream_name)
                text.flush()
            finally:
                text.detach()
        self.meta[stream_name] = wrapped_stream.meta

    def __repr__(self):
        return f"<{type(self).__name__} {self.path!r}>"


@contextmanager_class
class ZipWithZstdArchiveReader(ArchiveReader):
    """Streams decompression directly from the zip; no temp files."""

    SUFFIX = '.zip'
    _zipfile = None

    def __init__(self, archive_path):
        validate_archive_path(archive_path, self.SUFFIX)
        self.path = archive_path

    @cached_property
    def meta(self):
        if self._zipfile is None:
            raise RuntimeError("Archive not opened; use as a context manager")
        return json.loads(self._zipfile.read(META_FILENAME))

    def __contextmanager__(self):
        self._zipfile = zipfile.ZipFile(self.path, mode='r')
        try:
            yield self
        finally:
            self._zipfile.close()
            self._zipfile = None

    @contextmanager
    def open_stream(self, stream_name):
        with self._zipfile.open(stream_name) as stream:
            yield WrappedStream(stream, meta=self.meta[stream_name])

    def __repr__(self):
        return f"<{type(self).__name__} {self.path!r}>"
