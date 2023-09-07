from contextlib import contextmanager
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.test.client import Client, RequestFactory
from django.urls import reverse
from corehq.apps.domain.models import Domain

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from ..interface import FixtureEditInterface
from ..models import LookupTable, LookupTableRow, Field, TypeField
from corehq.apps.fixtures.views import update_tables

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
        return row


class TestFixtureEditInterface(TestCase):
    def test_json_conversion(self):
        # initial_page_data performs JSON conversion in manage_tables.html
        class FakeRequest:
            class couch_user:
                def can_view_some_reports(domain):
                    return True
                _id = "..."
            method = "GET"
            GET = {}
            META = {}

        import json
        from corehq.apps.hqwebapp.templatetags.hq_shared_tags import JSON
        table = LookupTableViewsTest.create_lookup_table(self)
        interface = FixtureEditInterface(FakeRequest, {}, DOMAIN)
        self.assertEqual(
            json.loads(JSON(interface.data_types)),
            [{
                "_id": table.id.hex,
                "is_global": True,
                "is_synced": False,
                "tag": "atable",
                "fields": [{
                    "name": "wing",
                    "properties": [],
                    "is_indexed": False,
                }],
                "item_attributes": [],
                "description": "A Table",
            }],
        )


@override_settings(REQUIRE_TWO_FACTOR_FOR_SUPERUSERS=False)
class UpdateTablesTests(TestCase):
    def test_can_delete_synced_fixture(self):
        request = self._create_request('DELETE')
        fixture = LookupTable.objects.create(domain='test-domain', tag='test-fixture', is_synced=True)

        update_tables(request, 'test-domain', fixture.id)

        remaining_table_count = LookupTable.objects.filter(domain='test-domain', tag='test-fixture').count()
        self.assertEqual(remaining_table_count, 0)

    def setUp(self):
        super().setUp()

        self.domain = Domain(name='test-domain', is_active=True)

        patcher = patch.object(Domain, 'get_by_name', return_value=self.domain)
        patcher.start()
        self.addCleanup(patcher.stop)

        privilege_patcher = patch('django_prbac.decorators.has_privilege', return_value=True)
        privilege_patcher.start()
        self.addCleanup(privilege_patcher.stop)

    def _create_request(self, method):
        method = method.lower()
        request = getattr(RequestFactory(), method)('/some/url')
        request.user = request.couch_user = WebUser(is_superuser=True, is_authenticated=True, is_active=True)

        return request
