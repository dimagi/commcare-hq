import os

from corehq.apps.dump_reload.sql.dump import (
    APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP,
    get_all_model_iterators_builders_for_domain,
)

from . import NotFound, get_blob_db, CODES
from .migrate import PROCESSING_COMPLETE_MESSAGE
from .models import BlobMeta
from .targzipdb import TarGzipBlobDB


class BlobDbBackendExporter(object):

    def __init__(self, filename, already_exported):
        self.db = TarGzipBlobDB(filename)
        self._already_exported = already_exported or set()
        self.src_db = get_blob_db()
        self.total_blobs = 0
        self.not_found = 0

    def __enter__(self):
        self.db.open('w:gz')

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
        if self.not_found:
            print(PROCESSING_COMPLETE_MESSAGE.format(self.not_found, self.total_blobs))

    def process_object(self, meta):
        self.total_blobs += 1
        if meta.key in self._already_exported:
            # This object is already in an another dump
            return

        try:
            content = self.src_db.get(meta.key, CODES.maybe_compressed)
        except NotFound:
            self.not_found += 1
        else:
            with content:
                self.db.copy_blob(content, key=meta.key)


class BlobExporter:

    def __init__(self, domain):
        self.domain = domain

    def migrate(self, filename, chunk_size=100, limit_to_db=None, already_exported=None, force=False):
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
            for model_class, builder in builders:
                for iterator in builder.iterators():
                    for obj in iterator:
                        migrator.process_object(obj)
                        if migrator.total_blobs % chunk_size == 0:
                            print("Processed {} objects".format(migrator.total_blobs))

        print("Processed {} total objects".format(migrator.total_blobs))
        return migrator.total_blobs, 0


class ExportError(Exception):
    pass
