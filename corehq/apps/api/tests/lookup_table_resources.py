import json
import uuid
from contextlib import contextmanager
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils.http import urlencode

from tastypie.bundle import Bundle

from corehq.apps.api.tests.utils import APIResourceTest
from corehq.apps.fixtures.models import (
    Field,
    LookupTable,
    LookupTableRow,
    TypeField,
)
from corehq.apps.fixtures.resources.v0_1 import (
    FixtureResource,
    LookupTableItemResource,
    LookupTableResource,
    convert_fdt,
)


class TestFixtureResource(APIResourceTest):
    resource = FixtureResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.state = LookupTable(
            domain=cls.domain.name,
            tag="state",
            fields=[TypeField("state")],
            item_attributes=[]
        )
        cls.state.save()
        cls.city = LookupTable(
            domain=cls.domain.name,
            tag="city",
            fields=[TypeField("state"), TypeField("city")],
            item_attributes=[]
        )
        cls.city.save()
        cls.ohio = cls._create_data_item(cls.state, {"state": "Ohio"}, 0)
        cls.akron = cls._create_data_item(cls.city, {"city": "Akron", "state": "Ohio"}, 0)
        cls.toledo = cls._create_data_item(cls.city, {"city": "Toledo", "state": "Ohio"}, 1)

    def test_get_list(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        result = json.loads(response.content)['objects']
        expect = [self.ohio, self.akron, self.toledo]
        # Result order is non-deterministic because the table id (UUID)
        # is part of the sort key. Additionally, backwards table row
        # ordering (originating in FixtureDataItem.by_domain()) seems
        # like a bug (inconsistent with other results from this same API).
        self.assertCountEqual(result, [self._data_item_json(r) for r in expect])

    def test_get_list_for_value(self):
        response = self._assert_auth_get_resource(self.api_url(
            parent_id=self.ohio.id.hex,
            child_type=self.city.id.hex,
            parent_ref_name='state',
            references='state',
        ))
        self.assertEqual(response.status_code, 200)

        result = json.loads(response.content)['objects']
        # Result order is non-deterministic
        self.assertCountEqual(result, [self._data_item_json(r) for r in [self.akron, self.toledo]])

    def test_get_list_for_type_id(self):
        response = self._assert_auth_get_resource(self.api_url(fixture_type_id=self.city.id.hex))
        self.assertEqual(response.status_code, 200)

        result = json.loads(response.content)['objects']
        self.assertEqual(result, [self._data_item_json(r) for r in [self.akron, self.toledo]])

    def test_get_list_for_type_tag(self):
        response = self._assert_auth_get_resource(self.api_url(fixture_type="state"))
        self.assertEqual(response.status_code, 200)

        result = json.loads(response.content)['objects']
        self.assertEqual(result, [self._data_item_json(self.ohio)])

    def test_get_single(self):
        response = self._assert_auth_get_resource(self.single_endpoint(self.ohio.id.hex))
        self.assertEqual(response.status_code, 200)

        fixture_data_type = json.loads(response.content)
        self.assertEqual(fixture_data_type, self._data_item_json(self.ohio))

    def test_dehydrate_fields(self):
        obj = LookupTableRow(table_id=uuid.uuid4(), fields={
            "1": [Field("one", {"lang": "en"})],
            "2": [Field("two", {"lang": "en"})],
        })
        bundle = Bundle(obj=obj, data={})
        result = FixtureResource().full_dehydrate(bundle).data["fields"]
        self.assertEqual(result, {'1': "one", '2': "two"})

    def test_dehydrate_fields_with_version_error(self):
        obj = LookupTableRow(table_id=uuid.uuid4(), fields={
            "1": [Field("one", {"lang": "en"}), Field("uno", {"lang": "es"})],
            "2": [Field("two", {"lang": "en"})],
        })
        bundle = Bundle(obj=obj, data={})
        result = FixtureResource().full_dehydrate(bundle).data["fields"]
        self.assertEqual(result, {
            '1': {'field_list': [
                {'field_value': 'one', 'properties': {"lang": "en"}},
                {'field_value': 'uno', 'properties': {"lang": "es"}},
            ]},
            '2': {'field_list': [
                {'field_value': 'two', 'properties': {"lang": "en"}},
            ]},
        })

    @classmethod
    def _create_data_item(cls, table, field_map, sort_key):
        data_item = LookupTableRow(
            domain=cls.domain.name,
            table_id=table.id,
            fields={k: [Field(value=v)] for k, v in field_map.items()},
            sort_key=sort_key
        )
        data_item.save()
        return data_item

    def api_url(self, **params):
        return f'{self.list_endpoint}?{urlencode(params, doseq=True)}'

    def _data_item_json(self, row):
        return {
            "id": row.id.hex,
            "fixture_type": row.table.tag,
            "fields": {n: v[0].value for n, v in row.fields.items()},
            "resource_uri": "",
        }


class TestLookupTableResource(APIResourceTest):
    resource = LookupTableResource
    api_name = 'v0.5'

    def setUp(self):
        super(TestLookupTableResource, self).setUp()
        self.data_type = LookupTable(
            domain=self.domain.name,
            tag="lookup_table",
            fields=[TypeField("fixture_property", ["lang", "name"])],
            item_attributes=[]
        )
        self.data_type.save()

    def _data_type_json(self):
        return {
            "fields": [
                {
                    "field_name": "fixture_property",
                    "properties": ["lang", "name"],
                },
            ],
            "item_attributes": [],
            "id": self.data_type.id.hex,
            "is_global": False,
            "resource_uri": "",
            "tag": "lookup_table"
        }

    def test_get_list(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        fixture_data_types = json.loads(response.content)['objects']
        self.assertEqual(len(fixture_data_types), 1)
        self.assertEqual(fixture_data_types, [self._data_type_json()])

    def test_get_single(self):
        response = self._assert_auth_get_resource(self.single_endpoint(self.data_type.id))
        self.assertEqual(response.status_code, 200)

        fixture_data_type = json.loads(response.content)
        self.assertEqual(fixture_data_type, self._data_type_json())

    def test_delete(self):
        data_type = LookupTable(
            domain=self.domain.name,
            tag="lookup_table2",
            fields=[TypeField("fixture_property", ["lang", "name"])],
            item_attributes=[]
        )
        data_type.save()
        TestLookupTableItemResource._create_data_item(self, data_type=data_type)

        self.assertEqual(2, LookupTable.objects.by_domain(self.domain.name).count())
        response = self._assert_auth_post_resource(self.single_endpoint(data_type.id), '', method='DELETE')
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(1, LookupTable.objects.by_domain(self.domain.name).count())

    def test_create(self):
        lookup_table = {
            "tag": "table_name",
            "fields": [{
                "field_name": "fieldA",
                "properties": ["property1", "property2"]
            }]
        }

        response = self._assert_auth_post_resource(
            self.list_endpoint, json.dumps(lookup_table), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data_type = LookupTable.objects.by_domain_tag(self.domain.name, "table_name")

        self.assertEqual(data_type.tag, "table_name")
        self.assertEqual(len(data_type.fields), 1)
        self.assertEqual(data_type.fields[0].field_name, 'fieldA')
        self.assertEqual(data_type.fields[0].properties, ['property1', 'property2'])

    def test_update(self):
        lookup_table = {
            "tag": "lookup_table",
            "item_attributes": ["X"]
        }

        response = self._assert_auth_post_resource(
            self.single_endpoint(self.data_type.id), json.dumps(lookup_table), method="PUT")
        data_type = LookupTable.objects.get(id=self.data_type.id)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(data_type.tag, "lookup_table")
        self.assertEqual(len(data_type.fields), 1)
        self.assertEqual(data_type.fields[0].field_name, 'fixture_property')
        self.assertEqual(data_type.fields[0].properties, ['lang', 'name'])
        self.assertEqual(data_type.item_attributes, ['X'])


class TestLookupTableItemResource(APIResourceTest):
    resource = LookupTableItemResource
    api_name = 'v0.6'

    @classmethod
    def setUpClass(cls):
        super(TestLookupTableItemResource, cls).setUpClass()
        cls.data_type = LookupTable(
            domain=cls.domain.name,
            tag="lookup_table",
            fields=[TypeField("fixture_property", ["lang", "name"])],
            item_attributes=[]
        )
        cls.data_type.save()

    def _create_data_item(self, data_type=None):
        data_item = LookupTableRow(
            domain=self.domain.name,
            table_id=(data_type or self.data_type).id,
            fields={
                "state_name": [
                    Field(value="Tennessee", properties={"lang": "en"}),
                    Field(value="田納西", properties={"lang": "zh"}),
                ]
            },
            item_attributes={},
            sort_key=1
        )
        data_item.save()
        return data_item

    def _data_item_json(self, id_, sort_key):
        return {
            "id": id_,
            "data_type_id": self.data_type.id.hex,
            "fields": {
                "state_name": {
                    "field_list": [
                        {"field_value": "Tennessee", "properties": {"lang": "en"}},
                        {"field_value": "田納西", "properties": {"lang": "zh"}},
                    ]
                }
            },
            "resource_uri": "",
            "item_attributes": {},
            "sort_key": sort_key,
        }

    def test_get_list(self):
        data_item = self._create_data_item()
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        fixture_data_types = json.loads(response.content)['objects']
        self.assertEqual(len(fixture_data_types), 1)
        self.assertEqual(fixture_data_types, [self._data_item_json(data_item.id.hex, data_item.sort_key)])

    def test_get_single(self):
        data_item = self._create_data_item()
        response = self._assert_auth_get_resource(self.single_endpoint(data_item.id.hex))
        self.assertEqual(response.status_code, 200)

        fixture_data_type = json.loads(response.content)
        self.assertEqual(fixture_data_type, self._data_item_json(data_item.id.hex, data_item.sort_key))

    def test_delete(self):
        data_item = self._create_data_item()
        self.assertEqual(1, LookupTableRow.objects.filter(domain=self.domain.name).count())
        response = self._assert_auth_post_resource(self.single_endpoint(data_item.id.hex), '', method='DELETE')
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(0, LookupTableRow.objects.filter(domain=self.domain.name).count())

    def test_create(self):
        data_item_json = {
            "data_type_id": self.data_type.id.hex,
            "fields": {
                "state_name": {
                    "field_list": [
                        {"field_value": "Massachusetts", "properties": {"lang": "en"}},
                        {"field_value": "马萨诸塞", "properties": {"lang": "zh"}},
                    ]
                }
            },
        }

        response = self._assert_auth_post_resource(
            self.list_endpoint, json.dumps(data_item_json), content_type='application/json')
        response_json = json.loads(response.content.decode('utf-8'))
        self.assertIn('id', response_json)
        self.assertEqual(
            response_json['fields']['state_name']['field_list'][0]['field_value'],
            'Massachusetts'
        )
        self.assertEqual(response.status_code, 201)
        data_item = LookupTableRow.objects.filter(domain=self.domain.name).first()
        self.addCleanup(data_item.delete)
        self.assertEqual(data_item.table_id, self.data_type.id)
        self.assertEqual(len(data_item.fields), 1)
        self.assertEqual(data_item.fields['state_name'][0].value, 'Massachusetts')
        self.assertEqual(data_item.fields['state_name'][0].properties, {"lang": "en"})

    def test_update(self):
        data_item = self._create_data_item()

        data_item_update = {
            "data_type_id": self.data_type.id.hex,
            "fields": {
                "state_name": {
                    "field_list": [
                        {"field_value": "Massachusetts", "properties": {"lang": "en"}},
                        {"field_value": "马萨诸塞", "properties": {"lang": "zh"}},
                    ]
                }
            },
            "item_attributes": {
                "attribute1": "cool_attr_value",
            }
        }

        response = self._assert_auth_post_resource(
            self.single_endpoint(data_item.id.hex), json.dumps(data_item_update), method="PUT")
        response_json = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response_json['item_attributes']['attribute1'],
            'cool_attr_value'
        )
        data_item = LookupTableRow.objects.get(id=data_item.id)
        self.assertEqual(data_item.table_id, self.data_type.id)
        self.assertEqual(len(data_item.fields), 1)
        self.assertEqual(data_item.fields['state_name'][0].value, 'Massachusetts')
        self.assertEqual(data_item.fields['state_name'][0].properties, {"lang": "en"})
        self.assertEqual(data_item.item_attributes, {"attribute1": "cool_attr_value"})


FAKE_TABLE = {"tag": "faketable"}


class FakeRow:
    def __init__(self):
        self.table_id = uuid.uuid4()
        self.data_type_id = self.table_id.hex


class TestConvertFDT(SimpleTestCase):

    def test_without_cache(self):
        with self.patch_query():
            row = convert_fdt(FakeRow())
        self.assertEqual(row.fixture_type, FAKE_TABLE["tag"])

    def test_missing_table_without_cache(self):
        with self.patch_query(LookupTable.DoesNotExist):
            row = convert_fdt(FakeRow())
        self.assertFalse(hasattr(row, "fixture_type"))

    def test_cache_miss(self):
        cache = {}
        with self.patch_query():
            row = convert_fdt(FakeRow(), cache)
        self.assertEqual(row.fixture_type, FAKE_TABLE["tag"])
        self.assertIn(row.table_id, cache)

    def test_cache_hit(self):
        row = FakeRow()
        cache = {row.table_id: "atag"}
        with self.patch_query(Exception("should not happen")):
            row = convert_fdt(row, cache)
        self.assertEqual(row.fixture_type, "atag")

    def test_missing_table_cache_miss(self):
        cache = {}
        with self.patch_query(LookupTable.DoesNotExist):
            row = convert_fdt(FakeRow(), cache)
        self.assertFalse(hasattr(row, "fixture_type"))
        self.assertIn(row.table_id, cache)

    def test_missing_table_cache_hit(self):
        row = FakeRow()
        cache = {row.table_id: None}
        with self.patch_query(Exception("should not happen")):
            row = convert_fdt(row, cache)
        self.assertIn(row.table_id, cache)

    @staticmethod
    def patch_query(result=FAKE_TABLE):
        def fake_get(self, id):
            if isinstance(result, (type, Exception)):
                raise result
            return result

        @contextmanager
        def context():
            from django.db.models.query import QuerySet
            with patch.object(QuerySet, "get", fake_get):
                yield

        return context()
