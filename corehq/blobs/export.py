import os
import time

from corehq.apps.dump_reload.sql.dump import (
    APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP,
    get_all_model_iterators_builders_for_domain,
)
from corehq.apps.dump_reload.timing import format_rate

from . import NotFound, get_blob_db, CODES
from .migrate import PROCESSING_COMPLETE_MESSAGE
from .models import BlobMeta
from .targzipdb import TarGzipBlobDB

PROGRESS_INTERVAL = 10_000  # print a progress line every N objects processed


class BlobDbBackendExporter(object):

    def __init__(self, filename, already_exported):
        self.db = TarGzipBlobDB(filename)
        self._already_exported = already_exported or set()
        self.src_db = get_blob_db()
        self.total_blobs = 0
        self.missing_ids = []
        self.missing_ids_filename = "missing_blob_ids.txt"

    def __enter__(self):
        self.db.open('w:gz')

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
        if self.missing_ids:
            self._write_missing_ids()
            print(PROCESSING_COMPLETE_MESSAGE.format(len(self.missing_ids), self.total_blobs))
            print(f"Missing blob ids have been written in the log file: {self.missing_ids_filename}")

    def run(self, metas, progress_interval=PROGRESS_INTERVAL):
        """Export each blob in ``metas``, logging per-chunk throughput every
        ``progress_interval`` objects and a total-time summary at the end."""
        start = batch_start = time.monotonic()
        for meta in metas:
            self.process_object(meta)
            if self.total_blobs % progress_interval == 0:
                now = time.monotonic()
                batch_elapsed = now - batch_start
                rate = format_rate(batch_elapsed, progress_interval, unit='objects')
                print(f"Processed {self.total_blobs} objects "
                      f"(last {progress_interval} in {batch_elapsed:.1f}s, {rate})")
                batch_start = now
        elapsed = time.monotonic() - start
        rate = format_rate(elapsed, self.total_blobs, unit='objects')
        print(f"Processed {self.total_blobs} objects in {elapsed:.1f}s ({rate})")

    def process_object(self, meta):
        self.total_blobs += 1
        if meta.key in self._already_exported:
            # This object is already in an another dump
            return

        try:
            content = self.src_db.get(meta.key, CODES.maybe_compressed)
        except NotFound:
            self.missing_ids.append(meta.key)
        else:
            with content:
                self.db.copy_blob(content, key=meta.key)

    def _write_missing_ids(self):
        if os.path.exists(self.missing_ids_filename):
            confirm = input(f"{self.missing_ids_filename} already exists. Overwrite? (y/N): ")
            if confirm != 'y':
                print("Cancelled export.")
                return
        with open(self.missing_ids_filename, 'w') as f:
            for missing_id in self.missing_ids:
                f.write(f"{missing_id}\n")


class BlobExporter:

    def __init__(self, domain):
        self.domain = domain

    def migrate(self, filename, progress_interval=PROGRESS_INTERVAL, limit_to_db=None,
                already_exported=None, force=False):
        if not self.domain:
            raise ExportError("Must specify domain")

        if not force and os.path.exists(filename):
            raise ExportError(
                "{} exporter doesn't support resume. "
                "To re-run the export use 'reset'".format(self.slug)
            )

        migrator = BlobDbBackendExporter(filename, already_exported)
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
