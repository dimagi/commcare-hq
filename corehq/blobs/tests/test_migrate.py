# coding=utf-8
import json
from os.path import join

import corehq.blobs.migrate as mod
from corehq.blobs.mixin import BlobMixin
from couchexport.models import SavedBasicExport, ExportConfiguration
from django.test import TestCase
from testil import replattr, tempdir


class TestSavedExportsMigrations(TestCase):

    slug = "saved_exports"

    def setUp(self):
        mod.BlobMigrationState.objects.filter(slug=self.slug).delete()

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

        with tempdir() as tmp:
            filename = join(tmp, "file.txt")

            # do migration
            migrated, skipped = mod.MIGRATIONS[self.slug].migrate(filename)
            self.assertGreaterEqual(migrated, 1)

            # verify: migration state recorded
            mod.BlobMigrationState.objects.get(slug=self.slug)

            # verify: migrated data was written to the file
            with open(filename) as fh:
                lines = list(fh)
            doc = {d["_id"]: d for d in (json.loads(x) for x in lines)}[saved._id]
            self.assertEqual(doc["_rev"], saved._rev)
            self.assertEqual(len(lines), migrated, lines)

        # verify: attachment was moved to blob db
        exp = SavedBasicExport.get(saved._id)
        self.assertNotEqual(exp._rev, saved._rev)
        self.assertEqual(len(exp.blobs), 1)
        self.assertFalse(exp._attachments, exp._attachments)
        self.assertEqual(len(exp.external_blobs), 1)
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

        modified = []
        print_status = mod.print_status

        # setup concurrent modification
        def modify_doc_and_print_status(num, total):
            if not modified:
                # do concurrent modification
                doc = SavedBasicExport.get(saved._id)
                doc.set_payload(new_payload)
                doc.save()
                modified.append(True)
            print_status(num, total)

        # hook print_status() call to simulate concurrent modification
        with replattr(mod, "print_status", modify_doc_and_print_status):
            # do migration
            migrated, skipped = mod.MIGRATIONS[self.slug].migrate()
            self.assertGreaterEqual(skipped, 1)

        # verify: migration state not set when docs are skipped
        with self.assertRaises(mod.BlobMigrationState.DoesNotExist):
            mod.BlobMigrationState.objects.get(slug=self.slug)

        # verify: attachments were not migrated
        exp = SavedBasicExport.get(saved._id)
        self.assertEqual(len(exp._attachments), 1, exp._attachments)
        self.assertEqual(len(exp.external_blobs), 1, exp.external_blobs)
        self.assertEqual(exp.get_payload(), new_payload)
        self.assertEqual(exp.fetch_attachment("other"), old_payload)


def _mk_config(name='some export name', index='dummy_index'):
    return ExportConfiguration(index=index, name=name, format='xlsx')
