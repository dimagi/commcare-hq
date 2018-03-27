# coding=utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os
import uuid
from io import BytesIO
from os.path import join

import corehq.blobs.migrate as mod
from corehq.blobs import get_blob_db
from corehq.blobs.mixin import BlobMixin
from corehq.blobs.s3db import maybe_not_found
from corehq.blobs.tests.util import (
    install_blob_db,
    TemporaryFilesystemBlobDB, TemporaryMigratingBlobDB
)
from corehq.blobs.util import random_url_id
from corehq.sql_db.models import PartitionedModel
from corehq.util.doc_processor.couch import CouchDocumentProvider, doc_type_tuples_to_dict
from corehq.util.test_utils import trap_extra_setup

from django.conf import settings
from django.test import TestCase
from testil import replattr, tempdir

from corehq.apps.app_manager.models import Application, RemoteApp
from couchexport.models import SavedBasicExport, ExportConfiguration

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
            with open(filename) as fh:
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


class TestSavedExportsMigrations(BaseMigrationTest):

    slug = "saved_exports"

    def test_migrate_happy_path(self):
        saved = SavedBasicExport(configuration=_mk_config())
        saved.save()
        payload = b'binary data not valid utf-8 \xe4\x94'
        name = saved.get_attachment_name()
        super(BlobMixin, saved).put_attachment(payload, name)
        saved.save()

        self.do_migration([saved])

        exp = SavedBasicExport.get(saved._id)
        self.assertEqual(exp.get_payload(), payload)

    def test_migrate_with_concurrent_modification(self):
        saved = SavedBasicExport(configuration=_mk_config())
        saved.save()
        name = saved.get_attachment_name()
        new_payload = 'something new'
        old_payload = 'something old'
        super(BlobMixin, saved).put_attachment(old_payload, name)
        super(BlobMixin, saved).put_attachment(old_payload, "other")
        saved.save()
        self.assertEqual(len(saved._attachments), 2)

        def modify(doc):
            doc = SavedBasicExport.get(doc._id)
            doc.set_payload(new_payload)
            doc.save()

        self.do_failed_migration({saved: (1, 1)}, modify)

        exp = SavedBasicExport.get(saved._id)
        self.assertEqual(exp.get_payload(), new_payload)
        self.assertEqual(exp.fetch_attachment("other"), old_payload)


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
            app = model_class()
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
            app = model_class()
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


class TestMultimediaMigrations(BaseMigrationTest):

    slug = "multimedia"
    test_items = [
        (mod.hqmedia.CommCareAudio, "audio.mp3"),
        (mod.hqmedia.CommCareImage, "image.jpg"),
        (mod.hqmedia.CommCareVideo, "video.3gp"),
        (mod.hqmedia.CommCareMultimedia, "file.bin"),
    ]

    @staticmethod
    def make_unmigrated(media_class, filename, data):
        media = media_class.get_by_data(data)
        if media._id:
            media.delete()
        media = media_class.get_by_data(data)
        assert not media._id, media.aux_media

        class OldAttachmentMedia(media_class):
            def put_attachment(self, *args, **kw):
                return super(BlobMixin, self).put_attachment(*args, **kw)

        with replattr(media, "__class__", OldAttachmentMedia):
            media.attach_data(data, filename)
        return media

    def test_migrate_happy_path(self):
        data = b'binary data not valid utf-8 \xe4\x94'
        media = {}
        for media_class, name in self.test_items:
            item = self.make_unmigrated(media_class, name, name + data)
            item.save()
            media[item] = name

        self.do_migration(list(media))

        for item, name in media.items():
            exp = type(item).get(item._id)
            self.assertEqual(exp.fetch_attachment(exp.attachment_id), name + data)

    def test_migrate_with_concurrent_modification(self):
        new_data = 'something new not valid utf-8 \xe4\x94'
        old_data = 'something old not valid utf-8 \xe4\x94'
        media = {}
        for media_class, name in self.test_items:
            item = self.make_unmigrated(media_class, name, name + old_data)
            super(BlobMixin, item).put_attachment(old_data, "other")
            item.save()
            self.assertEqual(len(item._attachments), 2)
            media[item] = name

        def modify(item):
            # put_attachment() calls .save()
            type(item).get(item._id).put_attachment(new_data, "other")

        self.do_failed_migration({item: (1, 1) for item in media}, modify)

        for item, name in media.items():
            exp = type(item).get(item._id)
            self.assertEqual(exp.fetch_attachment(exp.attachment_id), name + old_data)
            self.assertEqual(exp.fetch_attachment("other"), new_data)


class TestXFormInstanceMigrations(BaseMigrationTest):

    slug = "xforms"
    doc_type_map = {
        "XFormInstance": mod.xform.XFormInstance,
        "XFormInstance-Deleted": mod.xform.XFormInstance,
        "XFormArchived": mod.xform.XFormArchived,
        "XFormDeprecated": mod.xform.XFormDeprecated,
        "XFormDuplicate": mod.xform.XFormDuplicate,
        "XFormError": mod.xform.XFormError,
        "SubmissionErrorLog": mod.xform.SubmissionErrorLog,
        "HQSubmission": mod.xform.XFormInstance,
    }

    def test_migrate_happy_path(self):
        items = {}
        form_name = mod.xform.ATTACHMENT_NAME
        form = '<fake xform submission>\u2713</fake>'
        data = b'binary data not valid utf-8 \xe4\x94'
        for doc_type, model_class in self.doc_type_map.items():
            item = model_class()
            item.save()
            super(BlobMixin, item).put_attachment(form, form_name)
            super(BlobMixin, item).put_attachment(data, "data.bin")
            item.doc_type = doc_type
            item.save()
            items[doc_type] = item

        self.do_migration(list(items.values()), num_attachments=2)

        for item in items.values():
            exp = type(item).get(item._id)
            self.assertEqual(exp.fetch_attachment(form_name), form)
            self.assertEqual(exp.fetch_attachment("data.bin"), data)

    def test_migrate_with_concurrent_modification(self):
        items = {}
        form_name = mod.xform.ATTACHMENT_NAME
        new_form = 'something new'
        old_form = 'something old'
        for doc_type, model_class in self.doc_type_map.items():
            item = model_class()
            item.save()
            super(BlobMixin, item).put_attachment(old_form, form_name)
            super(BlobMixin, item).put_attachment(old_form, "other.xml")
            item.doc_type = doc_type
            item.save()
            self.assertEqual(len(item._attachments), 2)
            items[item] = (1, 1)

        def modify(item):
            # put_attachment() calls .save()
            type(item).get(item._id).put_attachment(new_form, form_name)

        self.do_failed_migration(items, modify)

        for item in items:
            exp = type(item).get(item._id)
            self.assertEqual(exp.fetch_attachment(form_name), new_form)
            self.assertEqual(exp.fetch_attachment("other.xml"), old_form)


class TestCommCareCaseMigrations(BaseMigrationTest):

    slug = "cases"
    doc_type_map = {
        'CommCareCase': mod.cases.CommCareCase,
        'CommCareCase-deleted': mod.cases.CommCareCase,
        'CommCareCase-Deleted': mod.cases.CommCareCase,
        'CommCareCase-Deleted-Deleted': mod.cases.CommCareCase,
    }

    def test_migrate_happy_path(self):
        items = {}
        name = "photo.jpg"
        data = b'binary data not valid utf-8 \xe4\x94'
        for doc_type, model_class in self.doc_type_map.items():
            item = model_class()
            item.save()
            super(BlobMixin, item).put_attachment(data, name)
            item.doc_type = doc_type
            item.save()
            items[doc_type] = item

        self.do_migration(list(items.values()), num_attachments=1)

        for item in items.values():
            exp = type(item).get(item._id)
            self.assertEqual(exp.fetch_attachment(name), data)

    def test_migrate_with_concurrent_modification(self):
        items = {}
        name = "photo.jpg"
        new_data = 'something new'
        old_data = 'something old'
        for doc_type, model_class in self.doc_type_map.items():
            item = model_class()
            item.save()
            super(BlobMixin, item).put_attachment(old_data, name)
            super(BlobMixin, item).put_attachment(old_data, "other.png")
            item.doc_type = doc_type
            item.save()
            self.assertEqual(len(item._attachments), 2)
            items[item] = (1, 1)

        def modify(item):
            # put_attachment() calls .save()
            type(item).get(item._id).put_attachment(new_data, name)

        self.do_failed_migration(items, modify)

        for item in items:
            exp = type(item).get(item._id)
            self.assertEqual(exp.fetch_attachment(name), new_data)
            self.assertEqual(exp.fetch_attachment("other.png"), old_data)


class TestMigrateBackend(TestCase):

    slug = "migrate_backend"
    couch_doc_types = {
        "Application": mod.apps.Application,
        "LinkedApplication": mod.apps.LinkedApplication,
        "RemoteApp": mod.apps.RemoteApp,
        "Application-Deleted": mod.apps.Application,
        "RemoteApp-Deleted": mod.apps.RemoteApp,
        "SavedBasicExport": mod.SavedBasicExport,
        "CommCareAudio": mod.hqmedia.CommCareAudio,
        "CommCareImage": mod.hqmedia.CommCareImage,
        "CommCareVideo": mod.hqmedia.CommCareVideo,
        "CommCareMultimedia": mod.hqmedia.CommCareMultimedia,
        "XFormInstance": mod.xform.XFormInstance,
        "XFormInstance-Deleted": mod.xform.XFormInstance,
        "XFormArchived": mod.xform.XFormArchived,
        "XFormDeprecated": mod.xform.XFormDeprecated,
        "XFormDuplicate": mod.xform.XFormDuplicate,
        "XFormError": mod.xform.XFormError,
        "SubmissionErrorLog": mod.xform.SubmissionErrorLog,
        "HQSubmission": mod.xform.XFormInstance,
        "CommCareCase": mod.cases.CommCareCase,
        'CommCareCase-deleted': mod.cases.CommCareCase,
        'CommCareCase-Deleted': mod.cases.CommCareCase,
        'CommCareCase-Deleted-Deleted': mod.cases.CommCareCase,
        "CaseExportInstance": mod.exports.CaseExportInstance,
        "FormExportInstance": mod.exports.FormExportInstance,
    }
    sql_reindex_accessors = [
        mod.CaseUploadFileMetaReindexAccessor,
        mod.CaseAttachmentSQLReindexAccessor,
        mod.XFormAttachmentSQLReindexAccessor,
        mod.DemoUserRestoreReindexAccessor,
    ]

    def CaseAttachmentSQL_save(self, obj, rex):
        obj.attachment_id = uuid.uuid4()
        obj.case_id = "not-there"
        obj.name = "name"
        obj.identifier = "what is this?"
        obj.md5 = "blah"
        obj.save()

    def XFormAttachmentSQL_save(self, obj, rex):
        obj.attachment_id = uuid.uuid4()
        obj.form_id = "not-there"
        obj.name = "name"
        obj.identifier = "what is this?"
        obj.md5 = "blah"
        obj.save()

    def DemoUserRestore_save(self, obj, rex):
        obj.attachment_id = uuid.uuid4()
        obj.demo_user_id = "not-there"
        obj.save()

    def setUp(self):
        lost_db = TemporaryFilesystemBlobDB()  # must be created before other dbs
        db1 = TemporaryFilesystemBlobDB()
        assert get_blob_db() is db1, (get_blob_db(), db1)
        missing = "found.not"
        name = "blob.bin"
        data = b'binary data not valid utf-8 \xe4\x94'

        self.not_founds = set()
        self.couch_docs = []
        with lost_db:
            for doc_type, model_class in self.couch_doc_types.items():
                item = model_class()
                item.doc_type = doc_type
                item.save()
                item.put_attachment(data, name)
                with install_blob_db(lost_db):
                    item.put_attachment(data, missing)
                    self.not_founds.add((
                        doc_type,
                        item._id,
                        item.external_blobs[missing].id,
                        item._blobdb_bucket(),
                    ))
                item.save()
                self.couch_docs.append(item)

        def create_obj(rex):
            ident = random_url_id(8)
            args = {rex.blob_helper.id_attr: ident}
            fields = {getattr(f, "attname", "")
                for f in rex.model_class._meta.get_fields()}
            if "content_length" in fields:
                args["content_length"] = len(data)
            elif "length" in fields:
                args["length"] = len(data)
            item = rex.model_class(**args)
            save_attr = rex.model_class.__name__ + "_save"
            if hasattr(self, save_attr):
                getattr(self, save_attr)(item, rex)
            else:
                item.save()
            return item, ident
        self.sql_docs = []
        for rex in (x() for x in self.sql_reindex_accessors):
            item, ident = create_obj(rex)
            helper = rex.blob_helper({"_obj_not_json": item})
            db1.put(BytesIO(data), ident, helper._blobdb_bucket())
            self.sql_docs.append(item)
            lost, lost_blob_id = create_obj(rex)
            self.sql_docs.append(lost)
            self.not_founds.add((
                rex.model_class.__name__,
                lost.id,
                lost_blob_id,
                rex.blob_helper({"_obj_not_json": lost})._blobdb_bucket(),
            ))

        self.test_size = len(self.couch_docs) + len(self.sql_docs)
        db2 = TemporaryFilesystemBlobDB()
        self.db = TemporaryMigratingBlobDB(db2, db1)
        assert get_blob_db() is self.db, (get_blob_db(), self.db)
        BaseMigrationTest.discard_migration_state(self.slug)

    def tearDown(self):
        self.db.close()
        BaseMigrationTest.discard_migration_state(self.slug)
        for doc in self.couch_docs:
            doc.get_db().delete_doc(doc._id)
        for doc in self.sql_docs:
            doc.delete()

    def test_migrate_backend(self):
        # verify: migration not complete
        with maybe_not_found():
            self.assertEqual(os.listdir(self.db.new_db.rootdir), [])

        with tempdir() as tmp:
            filename = join(tmp, "file.txt")

            # do migration
            migrated, skipped = mod.MIGRATIONS[self.slug].migrate(filename)
            self.assertGreaterEqual(migrated, self.test_size)

            # verify: migration state recorded
            mod.BlobMigrationState.objects.get(slug=self.slug)

            # verify: missing blobs written to log files
            missing_log = set()
            fields = ["doc_type", "doc_id", "blob_identifier", "blob_bucket"]
            for n, ignore in enumerate(mod.MIGRATIONS[self.slug].migrators):
                with open("{}.{}".format(filename, n)) as fh:
                    for line in fh:
                        doc = json.loads(line)
                        missing_log.add(tuple(doc[x] for x in fields))
            self.assertEqual(
                len(self.not_founds.intersection(missing_log)),
                len(self.not_founds)
            )

        # verify: couch attachments were copied to new blob db
        for doc in self.couch_docs:
            exp = type(doc).get(doc._id)
            self.assertEqual(exp._rev, doc._rev)  # rev should not change
            self.assertTrue(doc.blobs)
            bucket = doc._blobdb_bucket()
            for name, meta in doc.blobs.items():
                if name == "found.not":
                    continue
                content = self.db.new_db.get(meta.id, bucket)
                data = content.read()
                self.assertEqual(data, b'binary data not valid utf-8 \xe4\x94')
                self.assertEqual(len(data), meta.content_length)


def _mk_config(name='some export name', index='dummy_index'):
    return ExportConfiguration(index=index, name=name, format='xlsx')
