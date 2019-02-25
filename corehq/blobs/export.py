from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import os

from . import get_blob_db, NotFound
from .migrate import PROCESSING_COMPLETE_MESSAGE
from .models import BlobMeta
from .zipdb import get_export_filename, ZipBlobDB


class BlobDbBackendExporter(object):

    def __init__(self, slug, domain):
        self.slug = slug
        self.db = ZipBlobDB(self.slug, domain)
        self.total_blobs = 0
        self.not_found = 0

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
        if self.not_found:
            print(PROCESSING_COMPLETE_MESSAGE.format(self.not_found, self.total_blobs))

    def process_object(self, meta):
        from_db = get_blob_db()
        self.total_blobs += 1
        try:
            content = from_db.get(key=meta.key)
        except NotFound:
            self.not_found += 1
        else:
            with content:
                self.db.copy_blob(content, key=meta.key)
        return True


class ExportByDomain(object):

    def __init__(self, slug):
        self.slug = slug
        self.domain = None

    def by_domain(self, domain):
        self.domain = domain

    def migrate(self, filename=None, reset=False, max_retry=2, chunk_size=100, limit_to_db=None):
        from corehq.apps.dump_reload.sql.dump import get_all_model_iterators_builders_for_domain

        if not self.domain:
            raise ExportError("Must specify domain")

        if os.path.exists(get_export_filename(self.slug, self.domain)):
            raise ExportError(
                "{} exporter doesn't support resume. "
                "To re-run the export use 'reset'".format(self.slug)
            )

        migrator = BlobDbBackendExporter(self.slug, self.domain)

        with migrator:
            builders = get_all_model_iterators_builders_for_domain(
                BlobMeta, self.domain, limit_to_db)
            for model_class, builder in builders:
                for iterator in builder.iterators():
                    for obj in iterator:
                        migrator.process_object(obj)
                        if migrator.total_blobs % chunk_size == 0:
                            print("Processed {} {} objects".format(migrator.total_blobs, self.slug))

        return migrator.total_blobs, 0


class ExportError(Exception):
    pass


EXPORTERS = {m.slug: m for m in [
    ExportByDomain("all_blobs"),
]}
