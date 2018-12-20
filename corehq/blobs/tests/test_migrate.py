# coding=utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os
from io import BytesIO
from os.path import join

import corehq.blobs.migrate as mod
from corehq.blobs import get_blob_db, CODES
from corehq.blobs.s3db import maybe_not_found
from corehq.blobs.tests.util import (
    new_meta,
    TemporaryFilesystemBlobDB,
    TemporaryMigratingBlobDB,
)

from django.test import TestCase
from testil import tempdir

from io import open


class TestMigrateBackend(TestCase):

    slug = "migrate_backend"

    def setUp(self):
        db1 = TemporaryFilesystemBlobDB()
        assert get_blob_db() is db1, (get_blob_db(), db1)
        data = b'binary data not valid utf-8 \xe4\x94'
        self.not_founds = set()
        self.blob_metas = []

        for type_code in [CODES.form_xml, CODES.multimedia, CODES.data_export]:
            meta = db1.put(BytesIO(data), meta=new_meta(type_code=type_code))
            lost = new_meta(type_code=type_code, content_length=42)
            self.blob_metas.append(meta)
            self.blob_metas.append(lost)
            lost.save()
            self.not_founds.add((
                lost.id,
                lost.domain,
                lost.type_code,
                lost.parent_id,
                lost.key,
            ))

        self.test_size = len(self.blob_metas)
        db2 = TemporaryFilesystemBlobDB()
        self.db = TemporaryMigratingBlobDB(db2, db1)
        assert get_blob_db() is self.db, (get_blob_db(), self.db)
        discard_migration_state(self.slug)

    def tearDown(self):
        self.db.close()
        discard_migration_state(self.slug)
        for doc in self.blob_metas:
            doc.delete()

    def test_migrate_backend(self):
        # verify: migration not complete
        with maybe_not_found():
            self.assertEqual(os.listdir(self.db.new_db.rootdir), [])

        with tempdir() as tmp:
            filename = join(tmp, "file.txt")

            # do migration
            migrated, skipped = mod.MIGRATIONS[self.slug].migrate(filename, num_workers=2)
            self.assertGreaterEqual(migrated, self.test_size)

            # verify: migration state recorded
            mod.BlobMigrationState.objects.get(slug=self.slug)

            # verify: missing blobs written to log files
            missing_log = set()
            fields = [
                "blobmeta_id",
                "domain",
                "type_code",
                "parent_id",
                "blob_key",
            ]
            with open(filename, encoding='utf-8') as fh:
                for line in fh:
                    doc = json.loads(line)
                    missing_log.add(tuple(doc[x] for x in fields))
            self.assertEqual(self.not_founds, missing_log)

        # verify: blobs were copied to new blob db
        not_found = set(t[0] for t in self.not_founds)
        for meta in self.blob_metas:
            if meta.id in not_found:
                with self.assertRaises(mod.NotFound):
                    self.db.new_db.get(key=meta.key)
                continue
            content = self.db.new_db.get(key=meta.key)
            data = content.read()
            self.assertEqual(data, b'binary data not valid utf-8 \xe4\x94')
            self.assertEqual(len(data), meta.content_length)


def discard_migration_state(slug):
    migrator = mod.MIGRATIONS[slug]
    if hasattr(migrator, "migrators"):
        migrators = migrator.migrators
    elif hasattr(migrator, "iter_migrators"):
        migrators = migrator.iter_migrators()
    else:
        migrators = [migrator]
    for provider in (m.get_document_provider() for m in migrators):
        provider.get_document_iterator(1).discard_state()
    mod.BlobMigrationState.objects.filter(slug=slug).delete()


"""
Tests below are commented out because they are slow and no longer relevant
to any current envs (all envs have been migrated). Kept for reference when
writing new migrations.

from testil import replattr, tempdir

from corehq.apps.app_manager.models import Application, RemoteApp
from corehq.blobs.mixin import BlobMixin
from corehq.util.doc_processor.couch import doc_type_tuples_to_dict

NOT_SET = object()


class BaseMigrationTest(TestCase):

    def setUp(self):
        super(BaseMigrationTest, self).setUp()
        discard_migration_state(self.slug)
        self._old_flags = {}
        self.docs_to_delete = []

        for model in doc_type_tuples_to_dict(mod.MIGRATIONS[self.slug].doc_types).values():
            self._old_flags[model] = model._migrating_blobs_from_couch
            model._migrating_blobs_from_couch = True

    def tearDown(self):
        discard_migration_state(self.slug)
        for doc in self.docs_to_delete:
            doc.get_db().delete_doc(doc._id)
        for model, flag in self._old_flags.items():
            if flag is NOT_SET:
                del model._migrating_blobs_from_couch
            else:
                model._migrating_blobs_from_couch = flag
        super(BaseMigrationTest, self).tearDown()

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


class TestApplicationMigrations(BaseMigrationTest):

    slug = "applications"
    doc_type_map = {
        "Application": Application,
        "RemoteApp": RemoteApp,
        "Application-Deleted": Application,
        "RemoteApp-Deleted": RemoteApp,
    }

    def test_migrate_happy_path(self):
        apps = {}
        form = '<fake xform source>\u2713</fake>'
        for doc_type, model_class in self.doc_type_map.items():
            app = model_class(domain="test")
            app.save()
            super(BlobMixin, app).put_attachment(form, "form.xml")
            app.doc_type = doc_type
            app.save()
            apps[doc_type] = app

        # add legacy attribute to make sure the migration uses doc_type.wrap()
        app = apps["Application"]
        db = app.get_db()
        doc = db.get(app._id, wrapper=None)
        doc["commtrack_enabled"] = True
        db.save_doc(doc)
        apps["Application"] = Application.get(app._id)  # update _rev

        self.do_migration(list(apps.values()))

        for app in apps.values():
            exp = type(app).get(app._id)
            self.assertEqual(exp.fetch_attachment("form.xml"), form)

    def test_migrate_with_concurrent_modification(self):
        apps = {}
        new_form = 'something new'
        old_form = 'something old'
        for doc_type, model_class in self.doc_type_map.items():
            app = model_class(domain="test")
            app.save()
            super(BlobMixin, app).put_attachment(old_form, "form.xml")
            super(BlobMixin, app).put_attachment(old_form, "other.xml")
            app.doc_type = doc_type
            app.save()
            self.assertEqual(len(app._attachments), 2)
            apps[app] = (1, 1)

        def modify(app):
            # put_attachment() calls .save()
            type(app).get(app._id).put_attachment(new_form, "form.xml")

        self.do_failed_migration(apps, modify)

        for app in apps:
            exp = type(app).get(app._id)
            self.assertEqual(exp.fetch_attachment("form.xml"), new_form)
            self.assertEqual(exp.fetch_attachment("other.xml"), old_form)
"""
