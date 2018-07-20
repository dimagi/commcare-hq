# coding=utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
from os.path import join

import corehq.blobs.migrate as mod
from corehq.util.doc_processor.couch import doc_type_tuples_to_dict

from django.test import TestCase
from testil import replattr, tempdir

from io import open

NOT_SET = object()


class BaseMigrationTest(TestCase):

    def setUp(self):
        super(BaseMigrationTest, self).setUp()
        self.discard_migration_state(self.slug)
        self._old_flags = {}
        self.docs_to_delete = []

        for model in doc_type_tuples_to_dict(mod.MIGRATIONS[self.slug].doc_types).values():
            self._old_flags[model] = model._migrating_blobs_from_couch
            model._migrating_blobs_from_couch = True

    def tearDown(self):
        self.discard_migration_state(self.slug)
        for doc in self.docs_to_delete:
            doc.get_db().delete_doc(doc._id)
        for model, flag in self._old_flags.items():
            if flag is NOT_SET:
                del model._migrating_blobs_from_couch
            else:
                model._migrating_blobs_from_couch = flag
        super(BaseMigrationTest, self).tearDown()

    @staticmethod
    def discard_migration_state(slug):
        migrator = mod.MIGRATIONS[slug]
        if hasattr(migrator, "migrators"):
            providers = [m._get_document_provider() for m in migrator.migrators]
        else:
            providers = [migrator._get_document_provider()]
        for provider in providers:
            provider.get_document_iterator(1).discard_state()
        mod.BlobMigrationState.objects.filter(slug=slug).delete()

    # abstract property, must be overridden in base class
    slug = None

    @property
    def doc_types(self):
        return set(doc_type_tuples_to_dict(mod.MIGRATIONS[self.slug].doc_types))

    def do_migration(self, docs, num_attachments=1):
        self.docs_to_delete.extend(docs)
        test_types = {d.doc_type for d in docs}
        if test_types != self.doc_types:
            raise Exception("bad test: must have at least one document per doc "
                            "type (got: {})".format(test_types))
        if not num_attachments:
            raise Exception("bad test: must have at least one attachment")

        for doc in docs:
            # verify: attachment is in couch and migration not complete
            self.assertEqual(len(doc._attachments), num_attachments)
            self.assertEqual(len(doc.external_blobs), 0)

        with tempdir() as tmp:
            filename = join(tmp, "file.txt")

            # do migration
            migrated, skipped = mod.MIGRATIONS[self.slug].migrate(filename)
            self.assertGreaterEqual(migrated, len(docs))

            # verify: migration state recorded
            mod.BlobMigrationState.objects.get(slug=self.slug)

            # verify: migrated data was written to the file
            with open(filename, encoding='utf-8') as fh:
                lines = list(fh)
            lines_by_id = {d["_id"]: d for d in (json.loads(x) for x in lines)}
            for doc in docs:
                self.assertEqual(lines_by_id[doc._id]["_rev"], doc._rev)
            self.assertEqual(len(lines), migrated, lines)

        for doc in docs:
            # verify: attachments were moved to blob db
            exp = type(doc).get(doc._id)
            self.assertEqual(exp.doc_type, doc.doc_type)
            self.assertNotEqual(exp._rev, doc._rev)
            self.assertEqual(len(exp.blobs), num_attachments, repr(exp.blobs))
            self.assertFalse(exp._attachments, exp._attachments)
            self.assertEqual(len(exp.external_blobs), num_attachments)

    def do_failed_migration(self, docs, modify_doc):
        self.docs_to_delete.extend(docs)
        test_types = {d.doc_type for d in docs}
        if test_types != self.doc_types:
            raise Exception("bad test: must have at least one document per doc "
                            "type (got: {})".format(test_types))

        # verify: attachments are in couch, not blob db
        for doc in docs:
            self.assertGreaterEqual(len(doc._attachments), 1)
            self.assertEqual(len(doc.external_blobs), 0)

        # hook doc_migrator_class to simulate concurrent modification
        modified = set()
        docs_by_id = {d._id: d for d in docs}
        migrator = mod.MIGRATIONS[self.slug]

        class ConcurrentModify(migrator.doc_migrator_class):
            def _do_migration(self, doc):
                if doc["_id"] not in modified and doc["_id"] in docs_by_id:
                    # do concurrent modification
                    modify_doc(docs_by_id[doc["_id"]])
                    modified.add(doc["_id"])
                return super(ConcurrentModify, self)._do_migration(doc)

        with replattr(migrator, "doc_migrator_class", ConcurrentModify):
            # do migration
            migrated, skipped = migrator.migrate(max_retry=0)
            self.assertGreaterEqual(skipped, len(docs))

        self.assertEqual(modified, {d._id for d in docs})

        # verify: migration state not set when docs are skipped
        with self.assertRaises(mod.BlobMigrationState.DoesNotExist):
            mod.BlobMigrationState.objects.get(slug=self.slug)

        for doc, (num_attachments, num_blobs) in docs.items():
            exp = type(doc).get(doc._id)
            if not num_attachments:
                raise Exception("bad test: modify function should leave "
                                "unmigrated attachments")
            # verify: attachments were not migrated
            print(exp)
            self.assertEqual(len(exp._attachments), num_attachments)
            self.assertEqual(len(exp.external_blobs), num_blobs)
