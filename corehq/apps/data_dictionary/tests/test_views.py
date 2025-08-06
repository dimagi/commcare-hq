import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from corehq import privileges
from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyAllowedValue,
    CasePropertyGroup,
    CaseType,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.geospatial.const import GPS_POINT_CASE_PROPERTY
from corehq.apps.users.models import HqPermissions, WebUser
from corehq.apps.users.models_role import UserRole
from corehq.util.test_utils import flag_disabled, flag_enabled, privilege_enabled


class DataDictionaryViewTestBase(TestCase):
    domain_name = 'data-dictionary-view-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.user = WebUser.create(None, 'username', 'Passw0rd!', None, None)
        cls.user.add_domain_membership(cls.domain_name, is_admin=True)
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, cls.domain_name, deleted_by=None)


@privilege_enabled(privileges.DATA_DICTIONARY)
@flag_enabled('CASE_IMPORT_DATA_DICTIONARY_VALIDATION')
class UpdateCasePropertyViewTest(DataDictionaryViewTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type_obj = CaseType(name='caseType', domain=cls.domain_name)
        cls.case_type_obj.save()
        CaseProperty(case_type=cls.case_type_obj, name='property').save()

        group = CasePropertyGroup(case_type=cls.case_type_obj, name='group')
        group.id = 1
        group.save()

    def setUp(self):
        self.url = reverse('update_case_property', args=[self.domain_name])
        self.client = Client()
        self.client.login(username='username', password='Passw0rd!')

    def _get_property(self):
        return CaseProperty.objects.filter(
            case_type=self.case_type_obj,
            name='property'
        ).first()

    def _assert_type(self, value=''):
        prop = self._get_property()
        self.assertEqual(prop.data_type, value)

    def _get_case_property(self, name, case_type):
        return CaseProperty.objects.filter(
            case_type__name=case_type,
            name=name
        ).first()

    def _get_allowed_values_payload(self, prop, all_valid=True):
        max_len = CasePropertyAllowedValue._meta.get_field('allowed_value').max_length
        payload = {
            "caseType": prop.case_type.name,
            "name": prop.name,
            "description": prop.description,
            "data_type": "select",
            "allowed_values": {
                "True": "Yes!",
                "False": "No!",
                "X" * max_len: "huh?",
            },
        }
        if not all_valid:
            payload["allowed_values"]["Z" * (max_len + 1)] = "oops"
        return payload

    def _assert_allowed_values(self, prop, payload):
        max_len = CasePropertyAllowedValue._meta.get_field('allowed_value').max_length
        valid_count = 0
        for allowed_value, description in payload["allowed_values"].items():
            if len(allowed_value) <= max_len:
                valid_count += 1
                self.assertTrue(
                    CasePropertyAllowedValue.objects.filter(
                        case_property=prop,
                        allowed_value=allowed_value,
                        description=description).exists())
        self.assertEqual(
            valid_count,
            CasePropertyAllowedValue.objects.filter(case_property=prop).count()
        )

    def test_new_case_type(self):
        self._assert_type()
        post_data = {
            "groups": '[]',
            "properties": '[{"caseType": "somethingelse", "name": "property", "data_type": "date"}]'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        prop = self._get_case_property(name="property", case_type="somethingelse")
        self.assertEqual(prop.data_type, 'date')

    def test_new_case_property(self):
        self._assert_type()
        post_data = {
            "groups": '[]',
            "properties": '[{"caseType": "caseType", "name": "otherproperty", "data_type": "date"}]'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        prop = self._get_case_property(name="otherproperty", case_type="caseType")
        self.assertEqual(prop.data_type, 'date')

    def test_update_with_incorrect_data_type(self):
        self._assert_type()
        post_data = {
            "groups": '[]',
            "properties": '[{"caseType": "caseType", "name": "property", "data_type": "blah"}]'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 400)
        self._assert_type()

    def test_update_no_name(self):
        self._assert_type()
        post_data = {
            "groups": '[]',
            "properties": '[{"caseType": "caseType", "name": "", "data_type": "date"}]'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 400)
        self._assert_type()

    def test_update_of_correct_data_type(self):
        self._assert_type()
        post_data = {
            "groups": '[]',
            "properties": '[{"caseType": "caseType", "name": "property", "data_type": "date"}]'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        self._assert_type('date')

    def test_update_description(self):
        prop = self._get_property()
        self.assertEqual(prop.description, '')
        post_data = {
            "groups": '[]',
            "properties": '[{"caseType": "caseType", "name": "property", "description": "description"}]'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        prop = self._get_property()
        self.assertEqual(prop.description, 'description')

    def test_allowed_values_all_valid(self):
        prop = self._get_property()
        prop_payload = self._get_allowed_values_payload(prop)
        response = self.client.post(self.url, {"groups": '[]', "properties": json.dumps([prop_payload])})
        self.assertEqual(response.status_code, 200)
        self._assert_allowed_values(prop, prop_payload)

    def test_allowed_values_with_invalid_one(self):
        prop = self._get_property()
        prop_payload = self._get_allowed_values_payload(prop, all_valid=False)
        response = self.client.post(self.url, {"groups": '[]', "properties": json.dumps([prop_payload])})
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["messages"][0].startswith("Unable to save valid values longer than"))
        self._assert_allowed_values(prop, prop_payload)

    def test_update_with_group_name(self):
        prop = self._get_property()
        self.assertIsNone(prop.group)
        post_data = {
            "groups": '[{"id": 1, "caseType": "caseType", "name": "group", "description": ""}]',
            "properties": '[{"caseType": "caseType", "name": "property", "group": "group"}]'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        prop = self._get_property()
        self.assertEqual(prop.group.name, 'group')
        self.assertIsNotNone(prop.group)

    def test_update_with_no_group_name(self):
        prop = self._get_property()
        group = (
            CasePropertyGroup.objects
            .filter(case_type=self.case_type_obj, name='group')
            .first()
        )
        prop.group = group
        prop.save()
        post_data = {
            "groups": '[]',
            "properties": '[{"caseType": "caseType", "name": "property", "group": ""}]'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        prop = self._get_property()
        self.assertIsNone(prop.group)

    def test_delete_case_property(self):
        prop = self._get_property()
        post_data = {
            "groups": '[]',
            "properties": '[{"caseType": "caseType", "name": "property", "group": "", "deleted": true}]'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        prop = self._get_property()
        self.assertIsNone(prop)


@privilege_enabled(privileges.DATA_DICTIONARY)
class DataDictionaryViewTest(TestCase):
    domain_name = 'data-dictionary-view-test'

    @staticmethod
    def make_user_with_data_dict_role(email, domain_obj, has_data_dict_access=False):
        user = WebUser.create(
            domain=domain_obj.name,
            username=email,
            password='Passw0rd!',
            created_by=None,
            created_via=None
        )
        role = UserRole.create(
            domain=domain_obj,
            name='Data Dictionary Access',
            permissions=HqPermissions(view_data_dict=has_data_dict_access),
        )
        user.set_role(domain_obj.name, role.get_qualified_id())
        user.save()
        return user

    @classmethod
    def setUpClass(cls):
        super(DataDictionaryViewTest, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.user_data_dict_access = cls.make_user_with_data_dict_role(
            'has_data_dict@ex.com',
            cls.domain_obj,
            has_data_dict_access=True,
        )
        cls.addClassCleanup(cls.user_data_dict_access.delete, cls.domain_name, deleted_by=None)

        cls.user_no_data_dict_access = cls.make_user_with_data_dict_role(
            'no_data_dict@ex.com',
            cls.domain_obj,
        )
        cls.addClassCleanup(cls.user_no_data_dict_access.delete, cls.domain_name, deleted_by=None)

        cls.client = Client()
        cls.url = reverse('data_dictionary', args=[cls.domain_name])

    def test_has_view_access(self):
        self.client.login(username='has_data_dict@ex.com', password='Passw0rd!')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_no_view_access(self):
        self.client.login(username='no_data_dict@ex.com', password='Passw0rd!')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


@privilege_enabled(privileges.DATA_DICTIONARY)
class TestDeprecateOrRestoreCaseTypeView(DataDictionaryViewTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type_name = 'caseType'
        cls.case_type_obj = CaseType(name=cls.case_type_name, domain=cls.domain_name)
        cls.case_type_obj.save()

        CaseProperty(case_type=cls.case_type_obj, name='property').save()
        CasePropertyGroup(case_type=cls.case_type_obj, name='group').save()

    def setUp(self):
        self.endpoint = reverse(
            'deprecate_or_restore_case_type',
            args=(self.domain_name, self.case_type_obj.name),
        )
        self.client = Client()
        self.client.login(username='username', password='Passw0rd!')

    def _update_deprecate_state(self, is_deprecated):
        case_type_obj = CaseType.objects.get(name=self.case_type_name)
        case_type_obj.is_deprecated = is_deprecated
        case_type_obj.save()
        CaseProperty.objects.filter(case_type=case_type_obj).update(deprecated=is_deprecated)
        CasePropertyGroup.objects.filter(case_type=case_type_obj).update(deprecated=is_deprecated)

    def test_deprecate_case_type(self):
        response = self.client.post(self.endpoint, {'is_deprecated': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'success'})
        case_type_obj = CaseType.objects.get(name=self.case_type_name)
        self.assertTrue(case_type_obj.is_deprecated)

        case_prop_count = (
            CaseProperty.objects
            .filter(case_type=case_type_obj, deprecated=False)
            .count()
        )
        self.assertEqual(case_prop_count, 0)
        case_prop_group_count = (
            CasePropertyGroup.objects
            .filter(case_type=case_type_obj, deprecated=False)
            .count()
        )
        self.assertEqual(case_prop_group_count, 0)

    def test_restore_case_type(self):
        self._update_deprecate_state(is_deprecated=True)

        response = self.client.post(self.endpoint, {'is_deprecated': 'false'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'success'})
        case_type_obj = CaseType.objects.get(name=self.case_type_name)
        self.assertFalse(case_type_obj.is_deprecated)

        case_prop_count = (
            CaseProperty.objects
            .filter(case_type=case_type_obj, deprecated=True)
            .count()
        )
        self.assertEqual(case_prop_count, 0)
        case_prop_group_count = (
            CasePropertyGroup.objects
            .filter(case_type=case_type_obj, deprecated=True)
            .count()
        )
        self.assertEqual(case_prop_group_count, 0)


@es_test(requires=[case_search_adapter], setup_class=True)
@privilege_enabled(privileges.DATA_DICTIONARY)
class CaseTypesTest(DataDictionaryViewTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_types_endpoint = reverse("data_dictionary_json_case_types", args=[cls.domain_name])

        cls.case_type_obj = CaseType.objects.create(name="case_type", domain=cls.domain_name)
        cls.fhir_resource_name = "fhir-sample"

        app_module_patcher = patch('corehq.apps.data_dictionary.views.get_case_type_app_module_count')
        cls.mock_app_module_count = app_module_patcher.start()
        cls.mock_app_module_count.return_value = {}
        cls.addClassCleanup(app_module_patcher.stop)

    def setUp(self):
        self.client.login(username='username', password='Passw0rd!')

    def test_no_access(self, *args):
        # uses a different client that is not logged in
        response = Client().get(self.case_types_endpoint)
        # returns 302 because it is a redirect to the login page
        self.assertEqual(response.status_code, 302)

    def test_expected_keys_for_case_type(self):
        response = self.client.get(self.case_types_endpoint)
        returned_case_type = response.json()['case_types'][0]
        assert set(returned_case_type.keys()) == {
            'deprecated_property_count',
            'fhir_resource_type',
            'is_deprecated',
            'is_safe_to_delete',
            'module_count',
            'name',
            'property_count',
        }
        assert returned_case_type['name'] == 'case_type'

    def test_app_module_count(self):
        self.mock_app_module_count.return_value = {}
        response = self.client.get(self.case_types_endpoint)
        case_type = response.json()['case_types'][0]
        assert case_type['module_count'] == 0

        self.mock_app_module_count.return_value = {self.case_type_obj.name: 10}
        response = self.client.get(self.case_types_endpoint)
        case_type = response.json()['case_types'][0]
        assert case_type['module_count'] == 10

    def test_property_count(self):
        response = self.client.get(self.case_types_endpoint)
        case_type = response.json()['case_types'][0]
        assert case_type['property_count'] == 0

        CaseProperty.objects.create(case_type=self.case_type_obj, name="prop")
        response = self.client.get(self.case_types_endpoint)
        case_type = response.json()['case_types'][0]
        assert case_type['property_count'] == 1

    def test_deprecated_property_count(self):
        case_prop = CaseProperty.objects.create(case_type=self.case_type_obj, name="prop")
        response = self.client.get(self.case_types_endpoint)
        case_type = response.json()['case_types'][0]
        assert case_type['deprecated_property_count'] == 0

        case_prop.deprecated = True
        case_prop.save()
        response = self.client.get(self.case_types_endpoint)
        case_type = response.json()['case_types'][0]
        assert case_type['deprecated_property_count'] == 1

    def test_deprecated_case_types(self):
        deprecated_case_type = CaseType.objects.create(name="dep", domain=self.domain_name, is_deprecated=True)

        response = self.client.get(self.case_types_endpoint, data={'load_deprecated_case_types': 'false'})
        returned_names = [case_type['name'] for case_type in response.json()['case_types']]
        assert deprecated_case_type.name not in returned_names

        response = self.client.get(self.case_types_endpoint, data={'load_deprecated_case_types': 'true'})
        returned_names = [case_type['name'] for case_type in response.json()['case_types']]
        assert deprecated_case_type.name in returned_names

    def test_is_safe_to_delete(self):
        with patch('corehq.apps.data_dictionary.views.is_case_type_unused', return_value=True):
            response = self.client.get(self.case_types_endpoint)
            case_type = response.json()['case_types'][0]
            assert case_type['is_safe_to_delete']

        with patch('corehq.apps.data_dictionary.views.is_case_type_unused', return_value=False):
            response = self.client.get(self.case_types_endpoint)
            case_type = response.json()['case_types'][0]
            assert not case_type['is_safe_to_delete']

    def test_fhir_integration(self):
        with flag_disabled('FHIR_INTEGRATION'):
            response = self.client.get(self.case_types_endpoint)
            case_type = response.json()['case_types'][0]
            assert case_type['fhir_resource_type'] is None

        with (
            flag_enabled('FHIR_INTEGRATION'),
            patch('corehq.apps.data_dictionary.views.load_fhir_case_type_mapping') as mock,
        ):
            mock.return_value = {self.case_type_obj: self.fhir_resource_name}
            response = self.client.get(self.case_types_endpoint)
            case_type = response.json()['case_types'][0]
            assert case_type['fhir_resource_type'] == self.fhir_resource_name

    def test_geo_case_property(self):
        response = self.client.get(self.case_types_endpoint)
        assert response.json()["geo_case_property"] == GPS_POINT_CASE_PROPERTY


@es_test(requires=[case_search_adapter], setup_class=True)
@privilege_enabled(privileges.DATA_DICTIONARY)
class CasePropertiesTest(DataDictionaryViewTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type_obj = CaseType.objects.create(name="case_type", domain=cls.domain_name)
        cls.group_obj = CasePropertyGroup.objects.create(case_type=cls.case_type_obj, name="group")
        cls.prop_obj = CaseProperty.objects.create(case_type=cls.case_type_obj, group=cls.group_obj, name="prop")

        cls.fhir_resource_name = "fhir-sample"
        cls.fhir_json_path = "sample.json.path"

    def setUp(self):
        self.client.login(username='username', password='Passw0rd!')

    @classmethod
    def case_properties_endpoint(cls, case_type=None):
        return reverse(
            "data_dictionary_json_case_properties",
            args=[cls.domain_name, case_type or cls.case_type_obj.name],
        )

    def test_no_access(self):
        # uses a different client that is not logged in
        response = Client().get(self.case_properties_endpoint())
        # returns 302 because it is a redirect to the login page
        self.assertEqual(response.status_code, 302)

    def test_unknown_case_type(self):
        response = self.client.get(self.case_properties_endpoint(case_type="does-not-exist"))
        self.assertEqual(response.status_code, 404)

    def test_expected_keys_for_case_properties_endpoint(self):
        response = self.client.get(self.case_properties_endpoint())
        assert response.status_code == 200
        assert set(response.json().keys()) == {
            'deprecated_property_count',
            'groups',
            'name',
            'property_count',
            '_links',
        }
        assert response.json()['name'] == self.case_type_obj.name

    def test_property_count(self):
        response = self.client.get(self.case_properties_endpoint())
        assert response.json()['property_count'] == 1

        CaseProperty.objects.create(case_type=self.case_type_obj, name="new-prop")
        response = self.client.get(self.case_properties_endpoint(case_type=self.case_type_obj.name))
        assert response.json()['property_count'] == 2

    def test_deprecated_property_count(self):
        case_prop = CaseProperty.objects.create(case_type=self.case_type_obj, name="dep-prop")
        response = self.client.get(self.case_properties_endpoint())
        assert response.json()['deprecated_property_count'] == 0

        case_prop.deprecated = True
        case_prop.save()
        response = self.client.get(self.case_properties_endpoint())
        assert response.json()['deprecated_property_count'] == 1

    def test_illegal_values_in_pagination(self):
        response = self.client.get(self.case_properties_endpoint(), data={"skip": -1, "limit": 2})
        assert response.status_code == 400

    def test_pagination(self):
        case_type = CaseType.objects.create(name='paginate', domain=self.domain_name)
        for i in range(4):
            CaseProperty.objects.create(case_type=case_type, name=f"test-{i}")

        response = self.client.get(self.case_properties_endpoint(case_type=case_type.name), data={"limit": 2})
        assert response.status_code == 200
        pagination_resp = response.json()['_links']
        assert 'previous' not in pagination_resp.keys()
        assert pagination_resp['self'] == f"http://testserver/a/{self.domain_name}/data_dictionary/json/{case_type.name}/?limit=2&skip=0"  # noqa: E501
        assert pagination_resp['next'] == f"http://testserver/a/{self.domain_name}/data_dictionary/json/{case_type.name}/?limit=2&skip=2"  # noqa: E501

        # next response
        response = self.client.get(pagination_resp['next'])
        assert response.status_code == 200
        pagination_resp = response.json()['_links']
        assert pagination_resp['previous'] == f"http://testserver/a/{self.domain_name}/data_dictionary/json/{case_type.name}/?limit=2&skip=0"  # noqa: E501
        assert pagination_resp['self'] == f"http://testserver/a/{self.domain_name}/data_dictionary/json/{case_type.name}/?limit=2&skip=2"  # noqa: E501
        assert 'next' not in pagination_resp.keys()

        # previous response
        response = self.client.get(pagination_resp['previous'])
        assert response.status_code == 200
        pagination_resp = response.json()['_links']
        assert 'previous' not in pagination_resp.keys()
        assert pagination_resp['self'] == f"http://testserver/a/{self.domain_name}/data_dictionary/json/{case_type.name}/?limit=2&skip=0"  # noqa: E501
        assert pagination_resp['next'] == f"http://testserver/a/{self.domain_name}/data_dictionary/json/{case_type.name}/?limit=2&skip=2"  # noqa: E501

    # Groups
    def test_expected_keys_for_group(self):
        response = self.client.get(self.case_properties_endpoint())
        assert response.status_code == 200
        assert len(response.json()['groups']) == 1
        group_response = response.json()['groups'][0]
        assert set(group_response.keys()) == {
            'deprecated',
            'description',
            'id',
            'index',
            'name',
            'properties',
        }
        assert group_response['id'] == self.group_obj.id
        assert group_response['name'] == self.group_obj.name

    def test_deprecated_group(self):
        case_type = CaseType.objects.create(name='group-test', domain=self.domain_name)
        group = CasePropertyGroup.objects.create(case_type=case_type, name="A", description="test description")
        CaseProperty.objects.create(case_type=case_type, name=f"test-{group.name}", group=group)

        response = self.client.get(self.case_properties_endpoint(case_type=case_type.name))
        group_response = response.json()['groups'][0]
        assert not group_response['deprecated']

        group.deprecated = True
        group.save()
        response = self.client.get(self.case_properties_endpoint(case_type=case_type.name))
        group_response = response.json()['groups'][0]
        assert group_response['deprecated']

    def test_index_for_group(self):
        case_type = CaseType.objects.create(name='group-test', domain=self.domain_name)
        group_a = CasePropertyGroup.objects.create(case_type=case_type, name="A", index=0)
        group_b = CasePropertyGroup.objects.create(case_type=case_type, name="B", index=1)
        for i in range(2):
            CaseProperty.objects.create(case_type=case_type, name=f"test-{group_a.name}-{i}", group=group_a)
        for i in range(2):
            CaseProperty.objects.create(case_type=case_type, name=f"test-{group_b.name}-{i}", group=group_b)

        response = self.client.get(self.case_properties_endpoint(case_type=case_type.name))
        group_response = response.json()['groups'][0]
        assert group_response['name'] == group_a.name
        assert group_response['index'] == 0

        group_a.index = 1
        group_a.save()
        group_b.index = 0
        group_b.save()
        response = self.client.get(self.case_properties_endpoint(case_type=case_type.name))
        group_response = response.json()['groups'][0]
        assert group_response['name'] == group_a.name
        assert group_response['index'] == 1

    # Properties
    def test_expected_keys_for_case_property(self):
        response = self.client.get(self.case_properties_endpoint())
        assert len(response.json()['groups']) == 1
        group_response = response.json()['groups'][0]
        assert len(group_response['properties']) == 1
        property_response = group_response['properties'][0]
        assert set(property_response.keys()) == {
            'deprecated',
            'description',
            'fhir_resource_prop_path',
            'id',
            'index',
            'is_safe_to_delete',
            'label',
            'name',
        }
        assert property_response['id'] == self.prop_obj.id
        assert property_response['name'] == self.prop_obj.name

    @flag_enabled('CASE_IMPORT_DATA_DICTIONARY_VALIDATION')
    def test_validation_feature_flag(self):
        response = self.client.get(self.case_properties_endpoint())
        property_response = response.json()['groups'][0]['properties'][0]
        validation_fields = {'allowed_values', 'data_type'}
        assert validation_fields.issubset(set(property_response.keys()))

    def test_fhir_resource_prop_path(self):
        with flag_disabled('FHIR_INTEGRATION'):
            response = self.client.get(self.case_properties_endpoint())
            property_response = response.json()['groups'][0]['properties'][0]
            assert property_response['fhir_resource_prop_path'] is None

        with (
            flag_enabled('FHIR_INTEGRATION'),
            patch('corehq.apps.data_dictionary.views.load_fhir_case_type_mapping') as mock_type,
            patch('corehq.apps.data_dictionary.views.load_fhir_case_properties_mapping') as mock_props
        ):
            mock_type.return_value = {self.case_type_obj: self.fhir_resource_name}
            mock_props.return_value = {
                case_property: self.fhir_json_path for case_property in self.case_type_obj.properties.all()
            }
            response = self.client.get(self.case_properties_endpoint())
            property_response = response.json()['groups'][0]['properties'][0]
            assert property_response['fhir_resource_prop_path'] == self.fhir_json_path

    def test_is_safe_to_delete(self):
        with patch('corehq.apps.data_dictionary.views.is_case_property_unused', return_value=True):
            response = self.client.get(self.case_properties_endpoint())
            property_response = response.json()['groups'][0]['properties'][0]
            assert property_response['is_safe_to_delete']

        with patch('corehq.apps.data_dictionary.views.is_case_property_unused', return_value=False):
            response = self.client.get(self.case_properties_endpoint())
            property_response = response.json()['groups'][0]['properties'][0]
            assert not property_response['is_safe_to_delete']

        case_type = CaseType.objects.create(name='geo-test', domain=self.domain_name)
        group = CasePropertyGroup.objects.create(case_type=case_type, name="geo", index=0)
        CaseProperty.objects.create(case_type=case_type, name="geo-prop", group=group)
        with (
            patch('corehq.apps.data_dictionary.views.is_case_property_unused', return_value=True),
            patch('corehq.apps.data_dictionary.views.get_geo_case_property', return_value='geo-prop'),
        ):
            response = self.client.get(self.case_properties_endpoint(case_type=case_type.name))
            property_response = response.json()['groups'][0]['properties'][0]
            # if property name is a geo case property, it isn't safe to delete despite no usage
            assert not property_response['is_safe_to_delete']


@privilege_enabled(privileges.DATA_DICTIONARY)
class TestDeleteCaseType(DataDictionaryViewTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type_name = 'caseType'
        cls.case_type_obj = CaseType(name=cls.case_type_name, domain=cls.domain_name)
        cls.case_type_obj.save()

        CaseProperty(case_type=cls.case_type_obj, name='property').save()

    def setUp(self):
        self.endpoint = reverse(
            'delete_case_type',
            args=(self.domain_name, self.case_type_obj.name),
        )
        self.client = Client()
        self.client.login(username='username', password='Passw0rd!')

    def test_delete_case_type(self):
        response = self.client.post(self.endpoint, {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'success'})

        case_prop = (
            CaseProperty.objects
            .filter(case_type__name=self.case_type_name, name='property')
            .first()
        )
        self.assertIsNone(case_prop)
        case_type = CaseType.objects.filter(name=self.case_type_name).first()
        self.assertIsNone(case_type)
