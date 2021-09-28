import os
from abc import ABC, abstractmethod

from dimagi.utils.couch.database import iter_docs

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


class BlobExporter(ABC):
    def __init__(self, domain):
        self.domain = domain

    @property
    @abstractmethod
    def slug(self):
        raise NotImplementedError

    def migrate(self, filename, chunk_size=100, limit_to_db=None,
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
            self._migrate(migrator, chunk_size, limit_to_db)
        print("Processed {} {} objects".format(migrator.total_blobs, self.slug))
        return migrator.total_blobs, 0

    @abstractmethod
    def _migrate(self, migrator, chunk_size, limit_to_db):
        raise NotImplementedError


class ExportByDomain(BlobExporter):
    slug = 'all_blobs'

    def _migrate(self, migrator, chunk_size, limit_to_db):
        from corehq.apps.dump_reload.sql.dump import get_all_model_iterators_builders_for_domain
        from corehq.apps.dump_reload.sql.dump import APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP

        iterator_builders = APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP['blobs.BlobMeta']
        builders = get_all_model_iterators_builders_for_domain(
            BlobMeta, self.domain, iterator_builders, limit_to_db)
        for model_class, builder in builders:
            for iterator in builder.iterators():
                for obj in iterator:
                    migrator.process_object(obj)
                    if migrator.total_blobs % chunk_size == 0:
                        print("Processed {} {} objects".format(migrator.total_blobs, self.slug))


class ExportMultimedia(BlobExporter):
    slug = 'multimedia'

    def _migrate(self, migrator, chunk_size, limit_to_db):
        from corehq.apps.dump_reload.couch.dump import DOC_PROVIDERS_BY_DOC_TYPE

        db = get_blob_db()

        provider = DOC_PROVIDERS_BY_DOC_TYPE['CommCareMultimedia']
        for doc_class, doc_ids in provider.get_doc_ids(self.domain):
            couch_db = doc_class.get_db()
            for doc in iter_docs(couch_db, doc_ids, chunksize=chunk_size):
                obj = doc_class.get_doc_class(doc['doc_type']).wrap(doc)
                for name, blob_meta in obj.blobs.items():
                    meta = db.metadb.get(parent_id=obj._id, key=blob_meta.key)
                    migrator.process_object(meta)
                    if migrator.total_blobs % chunk_size == 0:
                        print("Processed {} {} objects".format(migrator.total_blobs, self.slug))


class ExportError(Exception):
    pass


EXPORTERS = {m.slug: m for m in [
    ExportByDomain,
    ExportMultimedia,
]}
