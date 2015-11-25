# coding=utf-8
import json
from os.path import join

import corehq.blobs.migrate as mod
from corehq.blobs.mixin import BlobMixin
from couchexport.models import SavedBasicExport, ExportConfiguration
from django.test import TestCase
from testil import assert_raises, eq, tempdir


class TestMigrations(TestCase):

    def test_migrate_saved_exports(self):
        # TODO generalize this to make it reusable for other slugs
        slug = "saved_exports"

        def _mk_config(name='some export name', index='dummy_index'):
            return ExportConfiguration(index=index, name=name, format='xlsx')

        # setup data
        saved = SavedBasicExport(configuration=_mk_config())
        saved.save()
        payload = 'something small and simple'
        name = saved.get_attachment_name()
        super(BlobMixin, saved).put_attachment(payload, name)
        saved.save()

        # verify: attachment is in couch and migration not complete
        eq(len(saved._attachments), 1)
        eq(len(saved.external_blobs), 0)
        with assert_raises(mod.BlobMigrationState.DoesNotExist):
            mod.BlobMigrationState.objects.get(slug=slug)

        with tempdir() as tmp:
            filename = join(tmp, "file.txt")

            # do migration
            migrated = mod.MIGRATIONS[slug].migrate(filename)
            assert migrated >= 1, migrated

            # verify: migration state recorded
            mod.BlobMigrationState.objects.get(slug=slug)

            # verify: migrated data was written to the file
            with open(filename) as fh:
                lines = list(fh)
            doc = {d["_id"]: d for d in (json.loads(x) for x in lines)}[saved._id]
            eq(doc["_rev"], saved._rev)
            eq(len(lines), migrated, lines)
            data = doc["_attachments"].values()[0]["data"].decode("base64")
            eq(data, payload)

        # reload and verify: attachment was moved to blob db
        exp = SavedBasicExport.get(saved._id)
        assert exp._rev != saved._rev, exp._rev
        eq(len(exp.blobs), 1)
        assert not exp._attachments, exp._attachments
        eq(len(exp.external_blobs), 1)
        eq(exp.get_payload(), payload)
