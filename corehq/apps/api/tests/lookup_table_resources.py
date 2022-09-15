import json

from corehq.apps.api.tests.utils import APIResourceTest
from corehq.apps.fixtures.models import (
    FieldList,
    FixtureDataItem,
    FixtureDataType,
    LookupTable,
    TypeField,
)
from corehq.apps.fixtures.resources.v0_1 import (
    LookupTableItemResource,
    LookupTableResource,
)
from corehq.apps.fixtures.upload.run_upload import clear_fixture_quickcache


class TestLookupTableResource(APIResourceTest):
    resource = LookupTableResource
    api_name = 'v0.5'

    def setUp(self):
        super(TestLookupTableResource, self).setUp()

        def ensure_no_unexpected_fixture_types():
            fixture_data_types = FixtureDataType.by_domain(self.domain.name)
            if fixture_data_types:
                FixtureDataType.delete_docs(fixture_data_types)
                self.fail(f"Unexpected in Couch: {fixture_data_types}")
        # add cleanup to be done after all other cleanups
        self.addCleanup(ensure_no_unexpected_fixture_types)

        self.data_type = LookupTable(
            domain=self.domain.name,
            tag="lookup_table",
            fields=[TypeField("fixture_property", ["lang", "name"])],
            item_attributes=[]
        )
        self.data_type.save()
        self.addCleanup(self.ensure_couch_fixture_is_deleted, self.data_type, False)

    def ensure_couch_fixture_is_deleted(self, data_type, fail_if_found=True):
        from couchdbkit.exceptions import ResourceNotFound
        try:
            FixtureDataType.get(data_type._migration_couch_id).delete()
            if fail_if_found:
                self.fail("Expected Couch fixture type to be deleted")
        except ResourceNotFound:
            pass

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
        self.addCleanup(self.ensure_couch_fixture_is_deleted, data_type)
        TestLookupTableItemResource._create_data_item(self, cleanup=False, data_type=data_type)
        assert FixtureDataItem.by_data_type(self.domain.name, data_type)  # populate cache

        self.assertEqual(2, LookupTable.objects.by_domain(self.domain.name).count())
        response = self._assert_auth_post_resource(self.single_endpoint(data_type.id), '', method='DELETE')
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(1, LookupTable.objects.by_domain(self.domain.name).count())
        self.assertFalse(FixtureDataItem.by_data_type(
            self.domain.name, data_type._migration_couch_id), "stale cache")

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
        self.addCleanup(self.ensure_couch_fixture_is_deleted, data_type, False)

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
    api_name = 'v0.5'

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
        cls.addClassCleanup(lambda: FixtureDataType.get(cls.data_type._migration_couch_id).delete())

    def tearDown(self):
        clear_fixture_quickcache(self.domain.name, [self.data_type._migration_get_couch_object()])

    def _create_data_item(self, cleanup=True, data_type=None):
        data_item = FixtureDataItem(
            domain=self.domain.name,
            data_type_id=(data_type or self.data_type)._migration_couch_id,
            fields={
                "state_name": FieldList.wrap({
                    "field_list": [
                        {"field_value": "Tennessee", "properties": {"lang": "en"}},
                        {"field_value": "田納西", "properties": {"lang": "zh"}},
                    ]})
            },
            item_attributes={},
            sort_key=1
        )
        data_item.save()
        if cleanup:
            self.addCleanup(data_item.delete)
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
        self.assertEqual(fixture_data_types, [self._data_item_json(data_item._id, data_item.sort_key)])

    def test_get_single(self):
        data_item = self._create_data_item()
        response = self._assert_auth_get_resource(self.single_endpoint(data_item._id))
        self.assertEqual(response.status_code, 200)

        fixture_data_type = json.loads(response.content)
        self.assertEqual(fixture_data_type, self._data_item_json(data_item._id, data_item.sort_key))

    def test_delete(self):
        data_item = self._create_data_item(cleanup=False)
        assert FixtureDataItem.get_item_list(self.domain.name, self.data_type.tag)  # populate cache
        self.assertEqual(1, len(FixtureDataItem.by_domain(self.domain.name)))
        response = self._assert_auth_post_resource(self.single_endpoint(data_item._id), '', method='DELETE')
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(0, len(FixtureDataItem.by_domain(self.domain.name)))
        cached_docs = FixtureDataItem.get_item_list(self.domain.name, self.data_type.tag)
        self.assertNotIn(data_item._id, [d._id for d in cached_docs], "stale cache")

    def test_create(self):
        assert not FixtureDataItem.get_item_list(self.domain.name, self.data_type.tag)  # populate cache
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
        self.assertEqual(response.status_code, 201)
        data_item = FixtureDataItem.by_domain(self.domain.name).first()
        self.addCleanup(data_item.delete)
        self.assertEqual(data_item.data_type_id, self.data_type._migration_couch_id)
        self.assertEqual(len(data_item.fields), 1)
        self.assertEqual(data_item.fields['state_name'].field_list[0].field_value, 'Massachusetts')
        self.assertEqual(data_item.fields['state_name'].field_list[0].properties, {"lang": "en"})
        cached_docs = FixtureDataItem.get_item_list(self.domain.name, self.data_type.tag)
        self.assertIn(data_item._id, [d._id for d in cached_docs], "stale cache")

    def test_update(self):
        data_item = self._create_data_item()
        assert FixtureDataItem.get_item_list(self.domain.name, self.data_type.tag)  # populate cache

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
            self.single_endpoint(data_item._id), json.dumps(data_item_update), method="PUT")
        data_item = FixtureDataItem.get(data_item._id)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(data_item.data_type_id, self.data_type._migration_couch_id)
        self.assertEqual(len(data_item.fields), 1)
        self.assertEqual(data_item.fields['state_name'].field_list[0].field_value, 'Massachusetts')
        self.assertEqual(data_item.fields['state_name'].field_list[0].properties, {"lang": "en"})
        self.assertEqual(data_item.item_attributes, {"attribute1": "cool_attr_value"})
        cached, = FixtureDataItem.get_item_list(self.domain.name, self.data_type.tag)
        self.assertEqual(cached.item_attributes, {"attribute1": "cool_attr_value"}, "stale cache")
