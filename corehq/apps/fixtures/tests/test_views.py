from contextlib import contextmanager
from unittest.mock import patch

from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from ..dbaccessors import delete_all_fixture_data
from ..models import LookupTable, LookupTableRow, Field, TypeField

DOMAIN = "lookup"
USER = "test@test.com"
PASS = "password"


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
        self.addCleanup(table._migration_get_couch_object().delete)
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
        self.addCleanup(row._migration_get_couch_object().delete)
        return row
