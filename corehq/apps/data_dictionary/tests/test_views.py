import json
import random
import string
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
from corehq.apps.geospatial.const import GPS_POINT_CASE_PROPERTY
from corehq.apps.users.models import HqPermissions, WebUser
from corehq.apps.users.models_role import UserRole
from corehq.util.test_utils import flag_enabled, privilege_enabled


class DataDictionaryViewTestBase(TestCase):
    domain_name = 'data-dictionary-view-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain_name)
        cls.user = WebUser.create(None, 'username', 'Passw0rd!', None, None)
        cls.user.add_domain_membership(cls.domain_name, is_admin=True)
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain_name, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()


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

    @classmethod
    def tearDownClass(cls):
        cls.case_type_obj.delete()
        super().tearDownClass()

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
        cls.user_data_dict_access = cls.make_user_with_data_dict_role(
            'has_data_dict@ex.com',
            cls.domain_obj,
            has_data_dict_access=True,
        )
        cls.user_no_data_dict_access = cls.make_user_with_data_dict_role(
            'no_data_dict@ex.com',
            cls.domain_obj,
        )
        cls.client = Client()
        cls.url = reverse('data_dictionary', args=[cls.domain_name])

    @classmethod
    def tearDownClass(cls):
        cls.user_data_dict_access.delete(cls.domain_name, deleted_by=None)
        cls.user_no_data_dict_access.delete(cls.domain_name, deleted_by=None)
        cls.domain_obj.delete()
        super(DataDictionaryViewTest, cls).tearDownClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.case_type_obj.delete()
        return super().tearDownClass()

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


# TODO Remove this Test Class once we migrate to the new view
@flag_enabled('CASE_IMPORT_DATA_DICTIONARY_VALIDATION')
@privilege_enabled(privileges.DATA_DICTIONARY)
class DataDictionaryJsonTest(DataDictionaryViewTestBase):

    @classmethod
    def setUpClass(cls):
        super(DataDictionaryJsonTest, cls).setUpClass()
        cls.case_type_obj = CaseType(name='caseType', domain=cls.domain_name)
        cls.case_type_obj.save()
        cls.case_prop_group = CasePropertyGroup(
            case_type=cls.case_type_obj,
            name='group',
        )
        cls.case_prop_group.save()
        cls.case_prop_obj = CaseProperty(
            case_type=cls.case_type_obj,
            name='property',
            data_type='number',
            group=cls.case_prop_group
        )
        cls.case_prop_obj.save()
        cls.deprecated_case_type_obj = CaseType(
            name='depCaseType',
            domain=cls.domain_name,
            is_deprecated=True,
        )
        cls.deprecated_case_type_obj.save()
        cls.client = Client()

    @classmethod
    def tearDownClass(cls):
        cls.case_type_obj.delete()
        cls.deprecated_case_type_obj.delete()
        super(DataDictionaryJsonTest, cls).tearDownClass()

    def setUp(self):
        self.endpoint = reverse('data_dictionary_json', args=[self.domain_name])

    @classmethod
    def _get_case_type_json(self, with_deprecated=False):
        expected_output = {
            "case_types": [
                {
                    "name": "caseType",
                    "fhir_resource_type": None,
                    "is_safe_to_delete": True,
                    "groups": [
                        {
                            "id": self.case_prop_group.id,
                            "name": "group",
                            "description": "",
                            "deprecated": False,
                            "properties": [
                                {
                                    "id": self.case_prop_obj.id,
                                    "description": "",
                                    "label": "",
                                    "fhir_resource_prop_path": None,
                                    "name": "property",
                                    "deprecated": False,
                                    "is_safe_to_delete": True,
                                    "allowed_values": {},
                                    "data_type": "number",
                                    "index": 0,
                                },
                            ],
                        },
                        {"name": "", "properties": []},
                    ],
                    "is_deprecated": False,
                    "module_count": 0,
                    "properties": [],
                },
            ],
            "geo_case_property": GPS_POINT_CASE_PROPERTY,
        }
        if with_deprecated:
            expected_output['case_types'].append(
                {
                    "name": "depCaseType",
                    "fhir_resource_type": None,
                    "is_safe_to_delete": True,
                    "groups": [
                        {
                            "name": '',
                            "properties": []
                        },
                    ],
                    "is_deprecated": True,
                    "module_count": 0,
                    "properties": [],
                }
            )
        return expected_output

    def test_no_access(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 302)

    @patch('corehq.apps.data_dictionary.views.get_case_type_app_module_count', return_value={})
    @patch('corehq.apps.data_dictionary.views.get_used_props_by_case_type', return_value={})
    def test_get_json_success(self, *args):
        self.client.login(username='username', password='Passw0rd!')
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_type_json()
        self.assertEqual(response.json(), expected_response)

    @patch('corehq.apps.data_dictionary.views.get_case_type_app_module_count', return_value={})
    @patch('corehq.apps.data_dictionary.views.get_used_props_by_case_type', return_value={})
    def test_get_json_success_with_deprecated_case_types(self, *args):
        self.client.login(username='username', password='Passw0rd!')
        response = self.client.get(self.endpoint, data={'load_deprecated_case_types': 'true'})
        expected_response = self._get_case_type_json(with_deprecated=True)
        self.assertEqual(response.json(), expected_response)


@patch('corehq.apps.data_dictionary.views.get_case_type_app_module_count', return_value={})
@patch('corehq.apps.data_dictionary.views.get_used_props_by_case_type', return_value={})
@flag_enabled('CASE_IMPORT_DATA_DICTIONARY_VALIDATION')
@privilege_enabled(privileges.DATA_DICTIONARY)
class DataDictionaryJsonV2Test(DataDictionaryViewTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type_obj = CaseType.objects.create(
            name="case_type",
            domain=cls.domain_name,
        )
        cls.group_obj = CasePropertyGroup.objects.create(
            case_type=cls.case_type_obj,
            name="group",
        )
        cls.case_properties_with_group = cls._create_properties_for_case_type(
            case_type=cls.case_type_obj,
            properties_count=2,
            group=cls.group_obj
        )
        cls.case_properties_without_group = cls._create_properties_for_case_type(
            case_type=cls.case_type_obj,
            properties_count=2,
        )

        cls.deprecated_case_type_obj = CaseType.objects.create(
            name="dep_case_type",
            domain=cls.domain_name,
            is_deprecated=True,
        )

        cls.fhir_resource_name = "fhir-sample"
        cls.fhir_json_path = "sample.json.path"
        cls.case_types_endpoint = reverse(
            "data_dictionary_json_case_types",
            args=[cls.domain_name],
        )

    @classmethod
    def tearDownClass(cls):
        cls.case_type_obj.delete()
        cls.deprecated_case_type_obj.delete()
        super().tearDownClass()

    def setUp(self):
        self.client.login(username='username', password='Passw0rd!')

    @classmethod
    def case_properties_endpoint(cls, case_type=None):
        if not case_type:
            case_type = cls.case_type_obj.name
        return reverse(
            "data_dictionary_json_case_properties",
            args=[cls.domain_name, case_type],
        )

    @classmethod
    def _create_properties_for_case_type(cls, case_type, properties_count, group=None):
        case_properties = []
        for index in range(properties_count):
            prop_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            case_prop_obj = CaseProperty.objects.create(
                case_type=case_type,
                name=prop_name,
                data_type='number',
                group=group if group else None
            )
            case_properties.append(case_prop_obj)
        return case_properties

    @classmethod
    def _get_case_types_json(cls, with_deprecated=False, fhir_enabled=False):
        expected_output = {
            "case_types": [
                {
                    "name": cls.case_type_obj.name,
                    "fhir_resource_type": cls.fhir_resource_name if fhir_enabled else None,
                    "is_safe_to_delete": True,
                    "is_deprecated": False,
                    "module_count": 0,
                    "properties_count": cls.case_type_obj.properties.count(),
                },
            ],
            "geo_case_property": GPS_POINT_CASE_PROPERTY,
        }
        if with_deprecated:
            expected_output['case_types'].append(
                {
                    "name": cls.deprecated_case_type_obj.name,
                    "fhir_resource_type": None,
                    "is_safe_to_delete": True,
                    "is_deprecated": True,
                    "module_count": 0,
                    "properties_count": cls.deprecated_case_type_obj.properties.count(),
                }
            )
        return expected_output

    @classmethod
    def _get_case_properties_json(
        cls,
        case_type_obj,
        groups_properties_dict=None,
        skip=0,
        limit=500,
        fhir_enabled=False,
    ):
        expected_output = {
            "name": case_type_obj.name,
            "properties_count": case_type_obj.properties.count(),
            "_links": {
                "self": f"http://testserver/a/{cls.domain_name}"
                        f"/data_dictionary/json_v2/{case_type_obj.name}/"
                        f"?skip={skip}&limit={limit}"
            },
            "groups": []
        }
        if skip:
            expected_output["_links"]["previous"] = (
                f"http://testserver/a/{cls.domain_name}/data_dictionary/"
                f"json_v2/{case_type_obj.name}/?skip={skip - limit}"
                f"&limit={limit}"
            )
        if case_type_obj.properties.count() > (skip + limit):
            expected_output["_links"]["next"] = (
                f"http://testserver/a/{cls.domain_name}/data_dictionary/json_v2/"
                f"{case_type_obj.name}/?skip={skip + limit}&limit={limit}"
            )
        if groups_properties_dict:
            for group, properties in groups_properties_dict.items():
                group_data = {
                    "name": group.name if group else "",
                    "properties": [
                        {
                            "id": prop.id,
                            "description": "",
                            "label": "",
                            "fhir_resource_prop_path": cls.fhir_json_path if fhir_enabled else None,
                            "name": prop.name,
                            "deprecated": False,
                            "is_safe_to_delete": True,
                            "data_type": "number",
                            "allowed_values": {},
                            "index": prop.index,
                        }
                        for prop in properties
                    ],
                }
                if group:
                    group_data.update({
                        "id": group.id,
                        "description": "",
                        "deprecated": False
                    })
                expected_output["groups"].append(group_data)
        return expected_output

    def test_get_case_types_no_access(self, *args):
        # uses a different client that is not logged in
        response = Client().get(self.case_types_endpoint)
        self.assertEqual(response.status_code, 302)

    def test_get_case_types(self, *args):
        response = self.client.get(self.case_types_endpoint)
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_types_json()
        self.assertEqual(response.json(), expected_response)

    @flag_enabled('FHIR_INTEGRATION')
    @patch('corehq.apps.data_dictionary.views.load_fhir_case_type_mapping')
    @patch('corehq.apps.data_dictionary.views.load_fhir_case_properties_mapping')
    def test_get_case_types_fhir_enabled(
        self,
        mocked_load_fhir_case_properties_mapping,
        mocked_load_fhir_case_type_mapping,
        *args
    ):
        mocked_load_fhir_case_type_mapping.return_value = {self.case_type_obj: self.fhir_resource_name}
        mocked_load_fhir_case_properties_mapping.return_value = {
            case_property: self.fhir_json_path
            for case_property in self.case_type_obj.properties.all()
        }
        response = self.client.get(self.case_types_endpoint)
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_types_json(fhir_enabled=True)
        self.assertEqual(response.json(), expected_response)

    def test_get_case_types_with_deprecated(self, *args):
        response = self.client.get(
            self.case_types_endpoint,
            data={'load_deprecated_case_types': 'true'}
        )
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_types_json(with_deprecated=True)
        self.assertEqual(response.json(), expected_response)

    def test_get_case_properties_no_access(self, *args):
        # uses a different client that is not logged in
        response = Client().get(self.case_properties_endpoint())
        self.assertEqual(response.status_code, 302)

    def test_get_case_properties_404(self, *args):
        response = self.client.get(self.case_properties_endpoint("does-not-exist"))
        self.assertEqual(response.status_code, 404)

    def test_get_case_properties(self, *args):
        response = self.client.get(self.case_properties_endpoint())
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_properties_json(
            self.case_type_obj,
            {
                self.group_obj: self.case_properties_with_group,
                None: self.case_properties_without_group,
            },
        )
        self.assertEqual(response.json(), expected_response)

    @flag_enabled('FHIR_INTEGRATION')
    @patch('corehq.apps.data_dictionary.views.load_fhir_case_type_mapping')
    @patch('corehq.apps.data_dictionary.views.load_fhir_case_properties_mapping')
    def test_get_case_properties_fhir_enabled(
        self,
        mocked_load_fhir_case_properties_mapping,
        mocked_load_fhir_case_type_mapping,
        *args
    ):
        mocked_load_fhir_case_type_mapping.return_value = {self.case_type_obj: self.fhir_resource_name}
        mocked_load_fhir_case_properties_mapping.return_value = {
            case_property: self.fhir_json_path
            for case_property in self.case_type_obj.properties.all()
        }
        response = self.client.get(self.case_properties_endpoint())
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_properties_json(
            self.case_type_obj,
            {
                self.group_obj: self.case_properties_with_group,
                None: self.case_properties_without_group,
            },
            fhir_enabled=True
        )
        self.assertEqual(response.json(), expected_response)

    def test_get_case_properties_with_skip_limit(self, *args):
        response = self.client.get(
            self.case_properties_endpoint(),
            data={"skip": 2, "limit": 2}
        )
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_properties_json(
            self.case_type_obj,
            {None: self.case_properties_without_group},
            skip=2,
            limit=2,
        )
        self.assertEqual(response.json(), expected_response)

    def test_get_case_properties_with_skip_limit_error(self, *args):
        response = self.client.get(
            self.case_properties_endpoint(),
            data={"skip": -1, "limit": 2}
        )
        self.assertEqual(response.status_code, 400)

    def test_get_case_properties_multi_page(self, *args):
        response = self.client.get(
            self.case_properties_endpoint(),
            data={"skip": 0, "limit": 2}
        )
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_properties_json(
            self.case_type_obj,
            {self.group_obj: self.case_properties_with_group},
            limit=2
        )
        self.assertEqual(response.json(), expected_response)
        # Get Next Page
        response = self.client.get(response.json()["_links"]["next"])
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_properties_json(
            self.case_type_obj,
            {None: self.case_properties_without_group},
            skip=2,
            limit=2
        )
        self.assertEqual(response.json(), expected_response)
        # Get Previous Page
        response = self.client.get(response.json()["_links"]["previous"])
        self.assertEqual(response.status_code, 200)
        expected_response = self._get_case_properties_json(
            self.case_type_obj,
            {self.group_obj: self.case_properties_with_group},
            limit=2
        )
        self.assertEqual(response.json(), expected_response)


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

    @classmethod
    def tearDownClass(cls):
        cls.case_type_obj.delete()
        return super().tearDownClass()

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
