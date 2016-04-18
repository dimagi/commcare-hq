# coding=utf-8
import json
from os.path import join

import corehq.blobs.migrate as mod
from corehq.blobs import get_blob_db
from corehq.blobs.mixin import BlobMixin
from corehq.blobs.s3db import maybe_not_found
from corehq.blobs.tests.util import (TemporaryFilesystemBlobDB,
    TemporaryMigratingBlobDB, TemporaryS3BlobDB)
from corehq.util.test_utils import trap_extra_setup

from django.conf import settings
from django.test import TestCase
from testil import replattr, tempdir

from couchexport.models import SavedBasicExport, ExportConfiguration

NOT_SET = object()


class BaseMigrationTest(TestCase):

    def setUp(self):
        mod.BlobMigrationState.objects.filter(slug=self.slug).delete()
        self._old_flag = getattr(self.model, "migrating_blobs_from_couch", NOT_SET)
        self.model.migrating_blobs_from_couch = True

    def tearDown(self):
        mod.BlobMigrationState.objects.filter(slug=self.slug).delete()
        if self._old_flag is NOT_SET:
            del self.model.migrating_blobs_from_couch
        else:
            self.model.migrating_blobs_from_couch = self._old_flag

    # abstract properties, must be overridden in base class
    slug = None
    model = None

    def do_migration(self, docs, num_attachments=1):
        if not docs or not num_attachments:
            raise Exception("bad test: must have at least one document and "
                            "one attachment")
        with tempdir() as tmp:
            filename = join(tmp, "file.txt")

            # do migration
            migrated, skipped = mod.MIGRATIONS[self.slug].migrate(filename)
            self.assertGreaterEqual(migrated, len(docs))

            # verify: migration state recorded
            mod.BlobMigrationState.objects.get(slug=self.slug)

            # verify: migrated data was written to the file
            with open(filename) as fh:
                lines = list(fh)
            lines_by_id = {d["_id"]: d for d in (json.loads(x) for x in lines)}
            for doc in docs:
                self.assertEqual(lines_by_id[doc._id]["_rev"], doc._rev)
            self.assertEqual(len(lines), migrated, lines)

        for doc in docs:
            # verify: attachments were moved to blob db
            exp = self.model.get(doc._id)
            self.assertNotEqual(exp._rev, doc._rev)
            self.assertEqual(len(exp.blobs), num_attachments, repr(exp.blobs))
            self.assertFalse(exp._attachments, exp._attachments)
            self.assertEqual(len(exp.external_blobs), num_attachments)

    def do_failed_migration(self, docs, modify_docs):
        if not docs:
            raise Exception("bad test: must have at least one document")
        modified = []
        print_status = mod.print_status

        # setup concurrent modification
        def modify_doc_and_print_status(num, total):
            if not modified:
                # do concurrent modification
                modify_docs()
                modified.append(True)
            print_status(num, total)

        # hook print_status() call to simulate concurrent modification
        with replattr(mod, "print_status", modify_doc_and_print_status):
            # do migration
            migrated, skipped = mod.MIGRATIONS[self.slug].migrate()
            self.assertGreaterEqual(skipped, len(docs))

        self.assertTrue(modified)

        # verify: migration state not set when docs are skipped
        with self.assertRaises(mod.BlobMigrationState.DoesNotExist):
            mod.BlobMigrationState.objects.get(slug=self.slug)

        for doc_id, (num_attachments, num_blobs) in docs.items():
            exp = self.model.get(doc_id)
            if not num_attachments:
                raise Exception("bad test: modify function should leave "
                                "unmigrated attachments")
            # verify: attachments were not migrated
            print(exp)
            self.assertEqual(len(exp._attachments), num_attachments)
            self.assertEqual(len(exp.external_blobs), num_blobs)


class TestSavedExportsMigrations(BaseMigrationTest):

    slug = "saved_exports"
    model = SavedBasicExport

    def test_migrate_saved_exports(self):
        # setup data
        saved = SavedBasicExport(configuration=_mk_config())
        saved.save()
        payload = 'something small and simple'
        name = saved.get_attachment_name()
        super(BlobMixin, saved).put_attachment(payload, name)
        saved.save()

        # verify: attachment is in couch and migration not complete
        self.assertEqual(len(saved._attachments), 1)
        self.assertEqual(len(saved.external_blobs), 0)

        self.do_migration([saved])

        exp = SavedBasicExport.get(saved._id)
        self.assertEqual(exp.get_payload(), payload)

    def test_migrate_with_concurrent_modification(self):
        # setup data
        saved = SavedBasicExport(configuration=_mk_config())
        saved.save()
        name = saved.get_attachment_name()
        new_payload = 'something new'
        old_payload = 'something old'
        super(BlobMixin, saved).put_attachment(old_payload, name)
        super(BlobMixin, saved).put_attachment(old_payload, "other")
        saved.save()

        # verify: attachments are in couch
        self.assertEqual(len(saved._attachments), 2)
        self.assertEqual(len(saved.external_blobs), 0)

        def modify():
            doc = SavedBasicExport.get(saved._id)
            doc.set_payload(new_payload)
            doc.save()

        self.do_failed_migration({saved._id: (1, 1)}, modify)

        # verify: attachments were not migrated
        exp = SavedBasicExport.get(saved._id)
        self.assertEqual(exp.get_payload(), new_payload)
        self.assertEqual(exp.fetch_attachment("other"), old_payload)


class TestMigrateBackend(TestCase):

    slug = "migrate_backend"
    test_size = 5

    def setUp(self):
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS

        fsdb = TemporaryFilesystemBlobDB()
        assert get_blob_db() is fsdb, (get_blob_db(), fsdb)
        self.migrate_docs = docs = []
        for i in range(self.test_size):
            doc = SavedBasicExport(configuration=_mk_config("config-%s" % i))
            doc.save()
            doc.set_payload(("content %s" % i).encode('utf-8'))
            docs.append(doc)

        s3db = TemporaryS3BlobDB(config)
        self.db = TemporaryMigratingBlobDB(s3db, fsdb)
        assert get_blob_db() is self.db, (get_blob_db(), self.db)
        mod.BlobMigrationState.objects.filter(slug=self.slug).delete()

    def tearDown(self):
        self.db.close()
        mod.BlobMigrationState.objects.filter(slug=self.slug).delete()

    def test_migrate_backend(self):
        # verify: attachment is in couch and migration not complete
        with maybe_not_found():
            s3_blobs = sum(1 for b in self.db.new_db._s3_bucket().objects.all())
            self.assertEqual(s3_blobs, 0)

        with tempdir() as tmp:
            filename = join(tmp, "file.txt")

            # do migration
            migrated, skipped = mod.MIGRATIONS[self.slug].migrate(filename)
            self.assertGreaterEqual(migrated, self.test_size)

            # verify: migration state recorded
            mod.BlobMigrationState.objects.get(slug=self.slug)

            # verify: migrated data was written to the file
            with open(filename) as fh:
                lines = list(fh)
            ids = {d._id for d in self.migrate_docs}
            migrated = {d["_id"] for d in (json.loads(x) for x in lines)}
            self.assertEqual(len(ids.intersection(migrated)), self.test_size)

        # verify: attachment was copied to new blob db
        for doc in self.migrate_docs:
            exp = SavedBasicExport.get(doc._id)
            self.assertEqual(exp._rev, doc._rev)  # rev should not change
            self.assertTrue(doc.blobs)
            bucket = doc._blobdb_bucket()
            for meta in doc.blobs.values():
                content = self.db.new_db.get(meta.id, bucket)
                self.assertEqual(len(content.read()), meta.content_length)


def _mk_config(name='some export name', index='dummy_index'):
    return ExportConfiguration(index=index, name=name, format='xlsx')
