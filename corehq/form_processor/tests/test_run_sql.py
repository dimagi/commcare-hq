from __future__ import unicode_literals
from __future__ import absolute_import
from datetime import datetime, timedelta
from io import BytesIO
from pprint import pformat
from uuid import uuid4

from django.db import connections
from django.test import TransactionTestCase
from mock import patch

from corehq.blobs import CODES
from corehq.blobs.models import BlobMeta
from corehq.blobs.tests.util import new_meta, TemporaryFilesystemBlobDB
from corehq.form_processor.management.commands.run_sql import Command
from corehq.form_processor.models import (
    DeprecatedXFormAttachmentSQL,
    XFormInstanceSQL,
)
from corehq.sql_db.util import (
    get_db_alias_for_partitioned_doc,
    get_db_aliases_for_partitioned_query,
)


class TestRunSql(TransactionTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestRunSql, cls).setUpClass()
        cls.db = TemporaryFilesystemBlobDB()
        for db in get_db_aliases_for_partitioned_query():
            with connections[db].cursor() as cursor:
                cursor.execute("""
                DROP TRIGGER IF EXISTS legacy_xform_attachment_insert_not_allowed
                    ON form_processor_xformattachmentsql;
                """)
        # this test requires a clean slate (no forms or blob metadata)
        cls.delete_all_forms_and_blob_metadata()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(TestRunSql, cls).tearDownClass()

        for db in get_db_aliases_for_partitioned_query():
            with connections[db].cursor() as cursor:
                cursor.execute("""
                CREATE TRIGGER legacy_xform_attachment_insert_not_allowed
                    BEFORE INSERT ON form_processor_xformattachmentsql
                    EXECUTE PROCEDURE insert_not_allowed();
                """)

    @classmethod
    def delete_all_forms_and_blob_metadata(cls):
        for db in get_db_aliases_for_partitioned_query():
            with connections[db].cursor() as cursor:
                cursor.execute("""
                DELETE FROM blobs_blobmeta_tbl;
                DELETE FROM form_processor_xformattachmentsql;
                DELETE FROM form_processor_xforminstancesql;
                """)

    def _fixture_teardown(self):
        # Normally _fixture_teardown truncates all tables on all databases,
        # which takes a long time. This just cleans up what we created.
        self.delete_all_forms_and_blob_metadata()

    def create_form(self, action="normal"):
        def put(parent_id, name, code):
            def create_old_meta(form_id, **kw):
                if name == "form.xml":
                    form = XFormInstanceSQL(
                        domain=meta.domain,
                        form_id=form_id,
                        received_on=RECEIVED_ON,
                        xmlns="testing",
                        **kw
                    )
                    form.save(using=db)
                DeprecatedXFormAttachmentSQL(
                    form_id=form_id,
                    attachment_id=uuid4().hex,
                    blob_id=meta.key,
                    blob_bucket="",
                    name=meta.name,
                    content_length=meta.content_length,
                    md5='wrong',
                ).save(using=db)

            db = get_db_alias_for_partitioned_doc(parent_id)
            args = {
                "parent_id": parent_id,
                "type_code": code,
                "name": name,
                "key": parent_id + "-" + name,
                "content_length": 2,
            }
            if "dup" not in action:
                args["created_on"] = RECEIVED_ON
            meta = new_meta(**args)

            # move blob metadata into old xformattachmentsql table
            deprecated = "deprecated" in action
            create_old_meta(
                form_id=parent_id + ("-dep" if deprecated else ""),
                orig_id=(parent_id if deprecated else None),
            )
            if action == "normal":
                count = 1
            else:
                count = 2
                meta = self.db.put(BytesIO(b"cx"), meta=meta)
                if "old" in action:
                    assert deprecated, action
                    create_old_meta(
                        form_id=parent_id,
                        deprecated_form_id=parent_id + "-dep",
                    )
                    if "dup" not in action:
                        meta.delete()
                    else:
                        count += 1
            metas = list(BlobMeta.objects.using(db).filter(key=meta.key))
            assert len(metas) == count, (metas, action, count)
            return meta

        assert action in "normal dup-deprecated-old", action

        class namespace(object):
            form_id = action
            metas = [
                put(form_id, "form.xml", CODES.form_xml),
                put(form_id, "pic.jpg", CODES.form_attachment),
                #put(form_id, "img.jpg", CODES.form_attachment),
            ]
            keys = {get_key(m) for m in metas}
        return namespace

    @patch('corehq.form_processor.management.commands.run_sql.confirm', return_value=True)
    def test_simple_move_form_attachments_to_blobmeta(self, mock):
        # this test can be removed with form_processor_xformattachmentsql table

        forms = [
            # Normal form, no dups.
            self.create_form(),

            # Two forms referencing same blob (old and new metadata).
            self.create_form("deprecated"),

            # Two forms referencing same blob (both old metadata).
            self.create_form("deprecated-old"),
        ]

        cmd = Command()
        cmd.handle(
            name="simple_move_form_attachments_to_blobmeta",
            dbname=None,
            chunk_size=100,
            print_rows=False,
        )

        attachments = list(DeprecatedXFormAttachmentSQL.objects.all())
        self.assertEqual(attachments, [])
        metas = []
        for db in get_db_aliases_for_partitioned_query():
            metas.extend(BlobMeta.objects.using(db).all())
        all_keys = {get_key(meta) for form in forms for meta in form.metas}
        form_keys = {k for f in forms for k in f.keys}
        self.assertTrue(all(k in all_keys for k in form_keys),
            pformat([all_keys] + [f.keys for f in forms]))
        self.assertTrue(all(m.created_on == RECEIVED_ON for m in metas),
            pformat([get_key(m, 1) for m in metas if m.created_on != RECEIVED_ON]))
        self.assertTrue(all(m.id > 0 for m in metas), metas)

    @patch('corehq.form_processor.management.commands.run_sql.confirm', return_value=True)
    def test_move_form_attachments_to_blobmeta(self, mock):
        # this test can be removed with form_processor_xformattachmentsql table

        forms = [
            # Normal form, no dups.
            self.create_form(),

            # Form with two sets of blob metadata (old and new metadata).
            # TODO row in form_processor_xformattachmentsql should be deleted.
            self.create_form("dup"),

            # Two forms referencing same blob (old and new metadata).
            self.create_form("deprecated"),

            # Two forms referencing same blob (both old metadata).
            self.create_form("deprecated-old"),

            # Two forms referencing same blob (both old metadata + new).
            # TODO row in form_processor_xformattachmentsql should be deleted.
            self.create_form("dup-deprecated-old"),
        ]

        cmd = Command()
        cmd.handle(
            name="move_form_attachments_to_blobmeta",
            dbname=None,
            # small chunk size to avoid
            # ON CONFLICT DO UPDATE command cannot affect row a second time
            chunk_size=1,
            print_rows=False,
        )

        attachments = list(DeprecatedXFormAttachmentSQL.objects.all())
        # some attachments will not be processed, need to be handled separately
        self.assertNotEqual(attachments, [])
        metas = []
        for db in get_db_aliases_for_partitioned_query():
            metas.extend(BlobMeta.objects.using(db).all())
        all_keys = {get_key(meta) for form in forms for meta in form.metas}
        self.assertTrue(all(k in all_keys for k in forms[0].keys | forms[2].keys),
            pformat([all_keys, forms[0].keys, forms[1].keys]))
        self.assertTrue(all(m.created_on == RECEIVED_ON for m in metas),
            pformat([get_key(m, 1) for m in metas if m.created_on != RECEIVED_ON]))
        self.assertTrue(all(m.id > 0 for m in metas), metas)


RECEIVED_ON = datetime.now() - timedelta(days=400)


#def get_id(name, _state={}):
#    number = _state[name] = _state.get(name, 0) + 1
#    return "{}-{}".format(name, number)


def get_key(meta, with_created_on=False):
    key = meta.key, meta.type_code
    if with_created_on:
        key += meta.created_on.isoformat(),
    return key
