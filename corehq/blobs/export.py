import os
import shutil
import time
from collections import namedtuple
from tempfile import SpooledTemporaryFile

from gevent.pool import Pool

from corehq.apps.dump_reload.sql.dump import (
    APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP,
    get_all_model_iterators_builders_for_domain,
)
from corehq.apps.dump_reload.timing import format_rate

from . import NotFound, get_blob_db, CODES
from .migrate import PROCESSING_COMPLETE_MESSAGE
from .models import BlobMeta
from .targzipdb import TarGzipBlobDB

DEFAULT_CONCURRENCY = 15  # benchmarked sweet spot; the S3 pool is auto-bumped to match
SPILL_THRESHOLD = 10 * 1024 * 1024  # buffer blobs in RAM up to 10 MB, then spill to disk
PROGRESS_INTERVAL = 10_000  # print a progress line every N objects processed
# Blobs are largely already compressed at rest, so gzip's default level 9 burns
# CPU scanning incompressible data for almost no size gain. Level 1 keeps the
# .tar.gz format (readable by run_blob_import) at a fraction of the CPU.
COMPRESS_LEVEL = 1

_Fetched = namedtuple('_Fetched', 'key fileobj content_length')
_Missing = namedtuple('_Missing', 'key')
_Skipped = namedtuple('_Skipped', 'key')


class BlobDbBackendExporter(object):

    def __init__(self, filename, already_exported, concurrency=DEFAULT_CONCURRENCY):
        self.db = TarGzipBlobDB(filename)
        self._already_exported = already_exported or set()
        self.src_db = get_blob_db()
        self.concurrency = concurrency
        # Spill large blob buffers next to the output archive (the operator's
        # chosen --dir), not the system temp dir which may be small or tmpfs.
        self._spill_dir = os.path.dirname(os.path.abspath(filename))
        self.total_blobs = 0
        self.missing_ids = []
        self.missing_ids_filename = missing_ids_filename_for(filename)

    def __enter__(self):
        self.db.open('w:gz', compresslevel=COMPRESS_LEVEL)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
        if self.missing_ids:
            self._write_missing_ids()
            print(PROCESSING_COMPLETE_MESSAGE.format(len(self.missing_ids), self.total_blobs))
            print(f"Missing blob ids have been written in the log file: {self.missing_ids_filename}")

    def run(self, metas, progress_interval=PROGRESS_INTERVAL):
        """Fetch blobs concurrently and write them to the tar archive serially.

        ``_fetch_object`` runs in many worker greenlets; ``_write_object``
        runs only here in the single consume loop, so it is the sole tar
        writer and entries cannot interleave.
        """
        pool = Pool(self.concurrency)
        start = batch_start = time.monotonic()
        try:
            for result in pool.imap_unordered(self._fetch_object, metas, maxsize=self.concurrency):
                self._write_object(result)
                self.total_blobs += 1
                if self.total_blobs % progress_interval == 0:
                    now = time.monotonic()
                    batch_elapsed = now - batch_start
                    rate = format_rate(batch_elapsed, progress_interval, unit='objects')
                    print(f"Processed {self.total_blobs} objects "
                          f"(last {progress_interval} in {batch_elapsed:.1f}s, {rate})")
                    batch_start = now
        finally:
            # On the fail-fast path (a fetch raising a non-NotFound error),
            # stop outstanding fetchers so their buffers are released promptly
            # rather than relying on process exit.
            pool.kill()
        elapsed = time.monotonic() - start
        rate = format_rate(elapsed, self.total_blobs, unit='objects')
        print(f"Processed {self.total_blobs} objects in {elapsed:.1f}s ({rate})")

    def _fetch_object(self, meta):
        """Fetch and fully buffer one blob, returning a _Fetched/_Missing/_Skipped result.

        Safe for concurrent use -- it only reads shared state and buffers into
        its own file, never touching the tar, so many fetches can run in
        parallel.
        """
        if meta.key in self._already_exported:
            return _Skipped(meta.key)
        try:
            content = self.src_db.get(meta.key, CODES.maybe_compressed)
        except NotFound:
            return _Missing(meta.key)
        spool = SpooledTemporaryFile(max_size=SPILL_THRESHOLD, dir=self._spill_dir)
        with content:
            content_length = content.content_length
            shutil.copyfileobj(content, spool)
        spool.seek(0)
        return _Fetched(meta.key, spool, content_length)

    def _write_object(self, result):
        """Apply one fetched result: write it to the tar, or record it missing.

        Not safe for concurrent use -- it writes to the shared tar stream, so
        callers must invoke it serially. Interleaved calls (e.g. from multiple
        greenlets) would corrupt the archive.
        """
        if isinstance(result, _Fetched):
            with result.fileobj as fileobj:
                self.db.copy_blob(fileobj, result.key, result.content_length)
        elif isinstance(result, _Missing):
            self.missing_ids.append(result.key)
        # _Skipped: already in another dump; counted but not written.

    def _write_missing_ids(self):
        if os.path.exists(self.missing_ids_filename):
            confirm = input(f"{self.missing_ids_filename} already exists. Overwrite? (y/N): ")
            if confirm != 'y':
                print("Cancelled export.")
                return
        with open(self.missing_ids_filename, 'w') as f:
            for missing_id in self.missing_ids:
                f.write(f"{missing_id}\n")


def missing_ids_filename_for(export_filename):
    """Derive the missing-blob-ids log path from the export archive path.

    Placing the log beside the archive -- same directory and filename prefix --
    keeps a run's two outputs together, honors the ``--dir`` chosen by the
    operator, and disambiguates the logs of repeated or concurrent runs that
    would otherwise all clobber a single ``missing_blob_ids.txt`` in the cwd.
    """
    return f"{export_filename.removesuffix('.tar.gz')}-missing_blob_ids.txt"


class BlobExporter:

    def __init__(self, domain):
        self.domain = domain

    def migrate(self, filename, progress_interval=PROGRESS_INTERVAL, limit_to_db=None,
                already_exported=None, force=False, concurrency=DEFAULT_CONCURRENCY):
        if not self.domain:
            raise ExportError("Must specify domain")

        if not force and os.path.exists(filename):
            raise ExportError(
                "{} exporter doesn't support resume. "
                "To re-run the export use 'reset'".format(self.slug)
            )

        migrator = BlobDbBackendExporter(filename, already_exported, concurrency)
        with migrator:
            iterator_builders = APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP['blobs.BlobMeta']
            builders = get_all_model_iterators_builders_for_domain(
                BlobMeta, self.domain, iterator_builders, limit_to_db
            )
            migrator.run(self._iter_metas(builders), progress_interval=progress_interval)

        return migrator.total_blobs, 0

    @staticmethod
    def _iter_metas(builders):
        for model_class, builder in builders:
            for iterator in builder.iterators():
                yield from iterator


class ExportError(Exception):
    pass
