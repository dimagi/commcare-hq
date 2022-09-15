from contextlib import contextmanager
from unittest.mock import patch

from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from couchdbkit import BulkSaveError, ResourceNotFound
from dimagi.utils.couch.bulk import CouchTransaction

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from ..dbaccessors import delete_all_fixture_data
from ..models import LookupTable, LookupTableRow, Field, TypeField

DOMAIN = "lookup"
USER = "test@test.com"
PASS = "password"
UNKNOWN_ID = '69aa2070e28e4b6fbadbb32af702a718'


class LookupTableViewsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LookupTableViewsTest, cls).setUpClass()
        cls.domain = create_domain(DOMAIN)
        cls.domain.save()
        cls.addClassCleanup(cls.domain.delete)
        cls.user = WebUser.create(DOMAIN, USER, PASS, created_by=None, created_via=None)
        cls.user.is_superuser = True
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, DOMAIN, deleted_by=None)
        cls.addClassCleanup(delete_all_fixture_data, DOMAIN)

    def test_update_tables_get(self):
        table = self.create_lookup_table()
        with self.get_client() as client:
            response = client.get(self.url(data_type_id=table.id.hex))
            data = response.json()
        for key, value in {
            '_id': table.id.hex,
            'tag': 'atable',
            'description': 'A Table',
            'is_global': True,
            'item_attributes': [],
        }.items():
            self.assertEqual(data.get(key), value, f"unexpected value for {key!r}")
        field, = data["fields"]
        for key, value in {
            'name': 'wing',
            'is_indexed': False,
            'properties': [],
        }.items():
            self.assertEqual(field.get(key), value, f"unexpected value for {key!r}")

    def test_update_tables_get_wrong_domain(self):
        table = self.create_lookup_table()
        with self.get_client() as client:
            response = client.get(self.url(data_type_id=table.id.hex, domain="wrong"))
        self.assertEqual(response.status_code, 404)

    def test_update_tables_get_not_found(self):
        with self.get_client() as client:
            response = client.get(self.url(data_type_id=UNKNOWN_ID))
        self.assertEqual(response.status_code, 404)

    def test_update_tables_get_invalid_id(self):
        with self.get_client() as client:
            response = client.get(self.url(data_type_id='invalid-id'))
        self.assertEqual(response.status_code, 404)

    def test_update_tables_delete(self):
        table = self.create_lookup_table()
        row = self.create_row(table)
        with self.get_client() as client:
            response = client.delete(self.url(data_type_id=table.id.hex))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})
        with self.assertRaises(LookupTable.DoesNotExist):
            LookupTable.objects.get(id=table.id)
        with self.assertRaises(LookupTableRow.DoesNotExist):
            LookupTableRow.objects.get(id=row.id)

    def test_update_tables_delete_wrong_domain(self):
        table = self.create_lookup_table()
        with self.get_client() as client:
            response = client.delete(self.url(data_type_id=table.id.hex, domain="wrong"))
        self.assertEqual(response.status_code, 404)

    def test_update_tables_delete_not_found(self):
        with self.get_client() as client:
            response = client.delete(self.url(data_type_id=UNKNOWN_ID))
        self.assertEqual(response.status_code, 404)

    def test_update_tables_delete_invalid_id(self):
        with self.get_client() as client:
            response = client.delete(self.url(data_type_id='invalid-id'))
        self.assertEqual(response.status_code, 404)

    def test_update_tables_post_duplicate_table(self):
        self.create_lookup_table()
        data = {
            'tag': 'atable',
            'description': 'A Table',
            'is_global': True,
            'fields': {'wing': {}},
        }
        with self.get_client(data) as client:
            response = client.post(self.url(), data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'DuplicateFixture')

    def test_update_tables_post_create_table(self):
        data = {
            'tag': 'atable',
            'description': 'A Table',
            'is_global': True,
            'fields': {'wing': {}},
        }
        with self.get_client(data) as client:
            response = client.post(self.url(), data)
        self.assertEqual(response.status_code, 200)
        table = LookupTable.objects.get(domain=DOMAIN, tag="atable")
        self.addCleanup(table._migration_get_couch_object().delete)
        self.assertTrue(table.is_global)
        self.assertEqual(table.description, "A Table")
        self.assertEqual(table.fields, [TypeField(name="wing")])

    def test_update_tables_post_without_data_type_id(self):
        data = {
            "fields": {},
            "tag": "invalid tag",
            "is_global": False,
            "description": ""
        }
        with self.get_client(data) as client:
            # should not raise
            # TypeError: update_tables() missing 1 required positional argument: 'data_type_id'
            response = client.post(self.url(), data)
        self.assertEqual(response.status_code, 200, str(response))

    def test_update_tables_put(self):
        table = self.create_lookup_table()
        self.create_row(table)
        data = {
            'tag': 'atable',
            'description': 'A Modified Table',
            'is_global': False,
            'fields': {'wing': {'update': 'foot'}},
        }
        with self.get_client(data) as client:
            response = client.put(self.url(data_type_id=table.id.hex), data)
        self.assertEqual(response.status_code, 200)
        table = LookupTable.objects.get(domain=DOMAIN, tag="atable")
        self.assertFalse(table.is_global)
        self.assertEqual(table.description, "A Modified Table")
        self.assertEqual(table.fields, [TypeField(name="foot")])
        row = LookupTableRow.objects.get(table_id=table.id)
        self.assertEqual(row.fields, {
            "foot": [Field(value="duck", properties={"says": "quack"})]
        })

        from ..models import FieldList, FixtureItemField
        couch_row = row._migration_get_couch_object()
        self.assertEqual(couch_row.fields, {
            "foot": FieldList(field_list=[
                FixtureItemField(field_value="duck", properties={"says": "quack"})
            ])
        })

    def test_update_tables_put_multiple_field_updates_on_multiple_rows(self):
        table = self.create_lookup_table(fields=[
            TypeField("a"),
            TypeField("b"),
            TypeField("c"),
        ])
        row1 = self.create_row(table, fields={
            "a": [Field(value="1", properties={"p": "x"})],
            "b": [Field(value="2", properties={"p": "y"})],
            "c": [Field(value="3", properties={"p": "z"})],
        })
        row2 = self.create_row(table, fields={
            "a": [Field(value="4", properties={"p": "m"})],
            "b": [Field(value="5", properties={"p": "n"})],
            "c": [Field(value="6", properties={"p": "o"})],
        })
        data = {
            'tag': 'atable',
            'description': 'A Modified Table',
            'is_global': False,
            'fields': {
                'a': {'update': 'd'},
                'b': {'remove': 1},
                'c': {},
                'e': {'is_new': 1},
            },
        }
        with self.get_client(data) as client:
            response = client.put(self.url(data_type_id=table.id.hex), data)
        self.assertEqual(response.status_code, 200)
        table = LookupTable.objects.get(domain=DOMAIN, tag="atable")
        self.assertFalse(table.is_global)
        self.assertEqual(table.description, "A Modified Table")
        self.assertEqual(table.fields, [
            TypeField("d"),
            TypeField("c"),
            TypeField("e"),
        ])
        row1 = LookupTableRow.objects.get(id=row1.id)
        self.assertEqual(row1.fields, {
            "c": [Field(value="3", properties={"p": "z"})],
            "d": [Field(value="1", properties={"p": "x"})],
            "e": [],
        })
        row2 = LookupTableRow.objects.get(id=row2.id)
        self.assertEqual(row2.fields, {
            "c": [Field(value="6", properties={"p": "o"})],
            "d": [Field(value="4", properties={"p": "m"})],
            "e": [],
        })

        from ..models import FieldList, FixtureItemField
        couch_row1 = row1._migration_get_couch_object()
        self.assertEqual(couch_row1.fields, {
            "c": FieldList(field_list=[FixtureItemField(field_value="3", properties={"p": "z"})]),
            "d": FieldList(field_list=[FixtureItemField(field_value="1", properties={"p": "x"})]),
            "e": FieldList(field_list=[]),
        })
        couch_row2 = row2._migration_get_couch_object()
        self.assertEqual(couch_row2.fields, {
            "c": FieldList(field_list=[FixtureItemField(field_value="6", properties={"p": "o"})]),
            "d": FieldList(field_list=[FixtureItemField(field_value="4", properties={"p": "m"})]),
            "e": FieldList(field_list=[]),
        })

    def test_update_table_with_stale_caches(self):
        table = self.create_lookup_table()
        row1 = self.create_row(table)
        row2 = self.create_row(table)

        self.stale_caches(table)
        data = {
            'tag': 'a_modified_table',
            'description': 'A Modified Table',
            'is_global': False,
            'fields': {'wing': {'update': 'foot'}},
        }
        with self.get_client(data) as client:
            # should not raise BulkSaveError
            response = client.put(self.url(data_type_id=table.id.hex), data)
        self.assertEqual(response.status_code, 200)

        # verify FixtureDataItem caches have been reset
        FixtureDataItem = LookupTableRow._migration_get_couch_model_class()
        rows = [
            FixtureDataItem.get(row1._migration_couch_id),
            FixtureDataItem.get(row2._migration_couch_id),
        ]
        rows.extend(FixtureDataItem.by_data_type(table.domain, table._migration_couch_id))
        for row in rows:
            self.assertIn("foot", row.fields)

    def test_update_table_clears_caches_on_error(self):
        def bulk_save_fail(docs):
            cls = type(docs[0])
            super(cls, cls).bulk_save(docs)
            raise BulkSaveError([{}], [{}])
            # NOTE SQL state is probably out of sync at this point.

        table = self.create_lookup_table()
        row1 = self.create_row(table)
        row2 = self.create_row(table)
        FixtureDataItem = LookupTableRow._migration_get_couch_model_class()

        data = {
            'tag': 'a_modified_table',
            'description': 'A Modified Table',
            'is_global': False,
            'fields': {'wing': {'update': 'foot'}},
        }
        save_patch = patch.object(FixtureDataItem, "bulk_save", bulk_save_fail)
        with self.get_client(data) as client, save_patch, self.assertRaises(BulkSaveError):
            client.put(self.url(data_type_id=table.id.hex), data)

        # verify FixtureDataItem caches have been reset
        rows = [
            FixtureDataItem.get(row1._migration_couch_id),
            FixtureDataItem.get(row2._migration_couch_id),
        ]
        rows.extend(FixtureDataItem.by_data_type(table.domain, table._migration_couch_id))
        for row in rows:
            self.assertIn("foot", row.fields)

    def test_delete_table_with_stale_caches(self):
        table = self.create_lookup_table()
        row1 = self.create_row(table)
        row2 = self.create_row(table)

        self.stale_caches(table)
        with self.get_client() as client:
            # should not raise BulkSaveError
            response = client.delete(self.url(data_type_id=table.id.hex))
        self.assertEqual(response.status_code, 200)
        self.assert_deleted(table, [row1, row2])

    def test_delete_table_with_previously_deleted_row(self):
        from dimagi.utils.couch.bulk import _bulk_delete as real_bulk_delete

        def bulk_delete(cls, chunk):
            if cls in [LookupTableRow._migration_get_couch_model_class(), LookupTableRow]:
                # simulate concurrent delete, causes BulkSaveError
                chunk[0].delete()
            real_bulk_delete(cls, chunk)

        table = self.create_lookup_table()
        row1 = self.create_row(table)
        row2 = self.create_row(table)
        delete_patch = patch("dimagi.utils.couch.bulk._bulk_delete", bulk_delete)
        with self.get_client() as client, delete_patch:
            response = client.delete(self.url(data_type_id=table.id.hex))
        self.assertEqual(response.status_code, 200)
        self.assert_deleted(table, [row1, row2])

    def stale_caches(self, table):
        # An error during save can cause caches to become stale.
        # Additionaly, QuickCache maintains a local in-memory cache,
        # which immediately becomes stale when any other process
        # updates the cached document, even if proper cache invalidation
        # is performed in the foreign process.
        #
        # Caching on these documents is a performance optimization. A
        # side effect is that the Couch concurrency protections (document
        # versions) become less useful because caching is hard. We are
        # not using that anyway since docuemnt versions are not passed
        # to and from the client.

        # populate caches
        couch_rows = LookupTableRow._migration_get_couch_model_class().get_item_list(table.domain, table.tag)
        with CouchTransaction() as tx:
            # transaction does not clear caches -> stale caches
            for row in couch_rows:
                tx.save(row)
            tx.set_sql_save_action(type(couch_rows[0]), lambda: None)

    def assert_deleted(self, table, rows):
        row_ids = [row.id.hex for row in rows]
        self.assertFalse(LookupTable.objects.filter(id=table.id).exists())
        self.assertFalse(LookupTableRow.objects.filter(id__in=row_ids).exists())
        doc_ids = [table._migration_couch_id] + row_ids
        db = LookupTable._migration_get_couch_model_class().get_db()
        couch_rows = db.view("_all_docs", keys=doc_ids)
        self.assertTrue(all(r["value"]["deleted"] for r in couch_rows), couch_rows)
        self.assertFalse(LookupTableRow._migration_get_couch_model_class()
            .by_data_type(table.domain, table._migration_couch_id))

    @contextmanager
    def get_client(self, data=None):
        client = Client()
        client.login(username=USER, password=PASS)
        allow_all = patch('django_prbac.decorators.has_privilege', return_value=True)

        # Not sure why _to_kwargs doesn't work on a test client request,
        # or maybe why it does work in the real world? Mocking it was
        # the easiest way I could find to work around the issue.
        json_data = patch('corehq.apps.fixtures.views._to_kwargs', return_value=data or {})

        with allow_all, json_data:
            yield client

    def url(self, **kwargs):
        kwargs.setdefault("domain", DOMAIN)
        return reverse("update_lookup_tables", kwargs=kwargs)

    def create_lookup_table(self, fields=None):
        table = LookupTable(
            domain=DOMAIN,
            tag="atable",
            description="A Table",
            is_global=True,
            fields=fields or [TypeField(name="wing")]
        )
        table.save()
        self.addCleanup(delete_if_exists, table._migration_get_couch_object())
        return table

    def create_row(self, table, fields=None):
        row = LookupTableRow(
            table_id=table.id,
            domain=DOMAIN,
            fields=fields or {
                "wing": [Field(value="duck", properties={"says": "quack"})],
            },
            sort_key=0,
        )
        row.save()
        self.addCleanup(delete_if_exists, row._migration_get_couch_object())
        return row


def delete_if_exists(doc):
    try:
        doc.delete()
    except ResourceNotFound:
        pass
