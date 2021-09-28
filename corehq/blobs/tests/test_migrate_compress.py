from io import BytesIO
from os.path import join

from django.conf import settings
from django.test import TestCase

import corehq.blobs.migrate as mod
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.tests.test_migrate import (
    discard_migration_state,
    verify_migration,
)
from corehq.blobs.tests.util import TemporaryS3BlobDB, new_meta
from testil import tempdir


class TestCompressMigration(TestCase):
    slug = 'compress_form_xml'

    def setUp(self):
        self.db = TemporaryS3BlobDB(settings.S3_BLOB_DB_SETTINGS)
        assert get_blob_db() is self.db, (get_blob_db(), self.db)
        data = b'binary data not valid utf-8 \xe4\x94'

        self.blob_metas, self.not_founds = [], set()
        for domain, type_code in (('a', CODES.form_xml), ('a', CODES.application), ('b', CODES.form_xml)):
            meta = new_meta(domain=domain, type_code=type_code, compressed_length=None)
            self.blob_metas.append(
                self.db.put(BytesIO(data), meta=meta)
            )
            lost = new_meta(
                domain=domain,
                type_code=CODES.form_xml,
                content_length=42,
                compressed_length=None,
            )
            lost.save()
            self.blob_metas.append(lost)
            self.not_founds.add((
                lost.id,
                lost.domain,
                lost.type_code,
                lost.parent_id,
                lost.key,
            ))

        discard_migration_state(self.slug)
        discard_migration_state(self.slug, domain='a')

    def tearDown(self):
        self.db.close()
        discard_migration_state(self.slug)
        discard_migration_state(self.slug, domain='a')
        for doc in self.blob_metas:
            doc.delete()

    def test_compress_all(self):
        self._test_compress(2)

    def test_compress_domain(self):
        self._test_compress(1, 'a')

    def _test_compress(self, expected_count, domain=None):
        self.assertTrue(all(
            not meta.is_compressed
            for meta in self.blob_metas
            if meta.type_code == CODES.form_xml
        ))
        with tempdir() as tmp:
            filename = join(tmp, "file.txt")

            # do migration
            migrated, skipped = mod.MIGRATIONS[self.slug]().migrate(filename, num_workers=2, domain=domain)
            self.assertGreaterEqual(migrated, expected_count)

            not_founds = {nf for nf in self.not_founds if not domain or nf[1] == domain}
            verify_migration(self, self.slug, filename, not_founds)

        # verify: blobs were compressed
        not_found = set(t[0] for t in self.not_founds)
        for meta in self.blob_metas:
            if domain and meta.domain != domain:
                continue
            meta.refresh_from_db()
            if meta.id in not_found:
                with self.assertRaises(mod.NotFound):
                    meta.open(self.db)
                continue
            content = meta.open(self.db)
            data = content.read()
            self.assertEqual(data, b'binary data not valid utf-8 \xe4\x94')
            self.assertEqual(len(data), meta.content_length)
            if meta.type_code == CODES.form_xml:
                self.assertGreaterEqual(meta.compressed_length, 1)
            else:
                self.assertIsNone(meta.compressed_length)
