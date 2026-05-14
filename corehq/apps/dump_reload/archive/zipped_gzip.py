import gzip
import json
import os
import zipfile
from contextlib import contextmanager
from functools import cached_property

from .base import ArchiveReader, ArchiveWriter, WrappedStream
from .utils import (
    META_FILENAME,
    contextmanager_class,
    get_tmp_extract_dir,
    validate_archive_path,
    validate_stream_meta,
)


@contextmanager_class
class ZippedGzipArchiveWriter(ArchiveWriter):

    SUFFIX = '.zip'

    def __init__(self, archive_path):
        validate_archive_path(archive_path, self.SUFFIX)
        self.path = archive_path
        self.meta = {}
        self._basename = archive_path[:-len(self.SUFFIX)]

    def __contextmanager__(self):
        yield self
        # Only reached on clean exit: append meta.json to the zip.
        with zipfile.ZipFile(self.path, mode='a', allowZip64=True) as z:
            z.writestr(META_FILENAME, json.dumps(self.meta, indent=4))

    @contextmanager
    def open_stream(self, stream_name):
        temp_path = f"{self._basename}-tmp-{stream_name}.gz"
        stream = gzip.open(temp_path, 'wt')
        wrapped_stream = WrappedStream(stream)
        try:
            yield wrapped_stream
            validate_stream_meta(wrapped_stream, stream_name)
        finally:
            stream.close()
        with zipfile.ZipFile(self.path, mode='a', allowZip64=True) as z:
            z.write(temp_path, f"{stream_name}.gz")
        os.remove(temp_path)
        self.meta[stream_name] = wrapped_stream.meta

    def __repr__(self):
        return f"<{type(self).__name__} {self.path!r}>"


@contextmanager_class
class ZippedGzipArchiveReader(ArchiveReader):

    SUFFIX = '.zip'
    _extracted_dir = None

    def __init__(self, archive_path, use_extracted=False):
        validate_archive_path(archive_path, self.SUFFIX)
        self.path = archive_path
        self._use_extracted = use_extracted

    @cached_property
    def meta(self):
        if self._extracted_dir is None:
            raise RuntimeError("Archive not opened; use as a context manager")
        with open(os.path.join(self._extracted_dir, META_FILENAME)) as f:
            return json.load(f)

    def __contextmanager__(self):
        target_dir = get_tmp_extract_dir(self.path)
        if os.path.exists(target_dir):
            if not self._use_extracted:
                raise ExtractedDumpExistsError(target_dir)
        else:
            with zipfile.ZipFile(self.path, 'r') as archive:
                archive.extractall(target_dir)
        self._extracted_dir = target_dir
        yield self
        # No teardown — extracted dir is preserved for --use-extracted reuse.

    @contextmanager
    def open_stream(self, stream_name):
        with gzip.open(os.path.join(self._extracted_dir, f"{stream_name}.gz")) as stream:
            yield WrappedStream(stream, meta=self.meta[stream_name])

    def __repr__(self):
        return f"<{type(self).__name__} {self.path!r}>"


class ExtractedDumpExistsError(Exception):
    def __init__(self, path):
        super().__init__(f"Extracted dump already exists at {path}")
        self.path = path
