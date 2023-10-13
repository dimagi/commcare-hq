from copy import deepcopy
import json
from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.motech.dhis2.models import SQLDataSetMap, SQLDataValueMap
from corehq.motech.dhis2.repeaters import Dhis2EntityRepeater, Dhis2Repeater
from corehq.motech.models import ConnectionSettings
from corehq.util.test_utils import flag_enabled
from corehq.motech.dhis2.tests.data.repeater import dhis2_repeater_data, dhis2_entity_repeater_data

from ..views import DataSetMapUpdateView

DOMAIN = 'test'
USERNAME = 'test@testy.com'
PASSWORD = 'password'


class BaseViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(DOMAIN)
        cls.user = WebUser.create(DOMAIN, USERNAME, PASSWORD,
                                  created_by=None, created_via=None)
        cls.user.is_superuser = True
        cls.user.save()

        cls._create_data()

    def setUp(self):
        super().setUp()
        self.client.login(username=USERNAME, password=PASSWORD)

    @classmethod
    def _create_data(cls):
        conn = ConnectionSettings(
            domain=cls.domain,
            name="motech_conn",
            url="url",
            auth_type="Bearer Token",
            api_auth_settings="",
            username="",
            password="",
            client_id="",
            client_secret="",
            skip_cert_verify=False
        )
        conn.save()
        cls.connection_setting = conn

        sql_dsm = SQLDataSetMap(
            domain=cls.domain,
            connection_settings=conn,
            day_to_send=1,
            description="This is a description",
            ucr_id="1234"
        )
        sql_dsm.save()
        cls.dataset_map = sql_dsm

        sql_dvm = SQLDataValueMap(
            dataset_map=sql_dsm,
            column="My column",
            data_element_id="D1234567891",
            comment="Testy comment"
        )
        sql_dvm.save()
        cls.data_value_map = sql_dvm

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()


class TestDataSetMapUpdateView(BaseViewTest):
    view_path = DataSetMapUpdateView.urlname

    def test_user_from_other_domain_404(self):
        other_domain = 'other-domain'
        create_domain(other_domain)
        user = WebUser.create(other_domain, 'other@user.com', PASSWORD,
                              created_by=None, created_via=None)
        self.addCleanup(user.delete, other_domain, None)
        self.client.login(username='other@user.com', password=PASSWORD)

        (dataset_map, datavalue_map) = (self.dataset_map, self.data_value_map)
        new_comment = 'Testy comment one'

        data = {
            'id': datavalue_map.id,
            'column': datavalue_map.column,
            'data_element_id': datavalue_map.data_element_id,
            'category_option_combo_id': datavalue_map.category_option_combo_id,
            'comment': new_comment,
            'action': 'update'
        }

        url_kwargs = {
            'domain': self.domain.name,
            'pk': dataset_map.pk
        }
        response = self.client.post(reverse(self.view_path, kwargs=url_kwargs), data)

        self.assertEqual(response.status_code, 404)

    def test_flag_not_enabled(self):
        (dataset_map, datavalue_map) = (self.dataset_map, self.data_value_map)
        new_comment = 'Testy comment one'

        data = {
            'id': datavalue_map.id,
            'column': datavalue_map.column,
            'data_element_id': datavalue_map.data_element_id,
            'category_option_combo_id': datavalue_map.category_option_combo_id,
            'comment': new_comment,
            'action': 'update'
        }

        url_kwargs = {
            'domain': self.domain.name,
            'pk': dataset_map.pk
        }
        response = self.client.post(reverse(self.view_path, kwargs=url_kwargs), data)

        self.assertEqual(response.status_code, 404)

    @flag_enabled('DHIS2_INTEGRATION')
    def test_update_ok(self):
        (dataset_map, datavalue_map) = (self.dataset_map, self.data_value_map)
        new_comment = 'Testy comment one'

        data = {
            'id': datavalue_map.id,
            'column': datavalue_map.column,
            'data_element_id': datavalue_map.data_element_id,
            'category_option_combo_id': datavalue_map.category_option_combo_id,
            'comment': new_comment,
            'action': 'update'
        }

        url_kwargs = {
            'domain': self.domain.name,
            'pk': dataset_map.pk
        }

        response = self.client.post(reverse(self.view_path, kwargs=url_kwargs), data)

        self.assertEqual(response.status_code, 200)

        datavalue_map.refresh_from_db()
        self.assertEqual(datavalue_map.comment, new_comment)

    @flag_enabled('DHIS2_INTEGRATION')
    def test_invalid_data_element_id_update(self):
        (dataset_map, datavalue_map) = (self.dataset_map, self.data_value_map)
        invalid_data_element_id = "123"  # Must start with letter and be 11 chars long

        data = {
            'id': datavalue_map.id,
            'column': datavalue_map.column,
            'data_element_id': invalid_data_element_id,
            'category_option_combo_id': datavalue_map.category_option_combo_id,
            'comment': datavalue_map.comment,
            'action': 'update'
        }

        url_kwargs = {
            'domain': self.domain.name,
            'pk': dataset_map.pk
        }

        response = self.client.post(reverse(self.view_path, kwargs=url_kwargs), data)
        self.assertEqual(response.status_code, 200)

        datavalue_map.refresh_from_db()
        self.assertNotEqual(datavalue_map.data_element_id, invalid_data_element_id)

    @classmethod
    def tearDownClass(cls):
        cls.dataset_map.delete()
        cls.data_value_map.delete()
        return super().tearDownClass()


class TestConfigDhis2RepeaterView(BaseViewTest):

    @classmethod
    def _create_data(cls):
        conn = ConnectionSettings(
            domain=cls.domain,
            name="motech_conn",
            url="url",
        )
        conn.save()
        cls.connection_setting = conn
        cls.dhis2_repeater = Dhis2Repeater(**deepcopy(dhis2_repeater_data))
        cls.dhis2_repeater.domain = DOMAIN
        cls.dhis2_repeater.connection_settings = conn
        cls.dhis2_repeater.save()
        cls.url_kwargs = {
            'domain': cls.domain.name,
            'repeater_id': cls.dhis2_repeater.repeater_id
        }

    def test_config_get(self):
        response = self.client.get(reverse('config_dhis2_repeater', kwargs=self.url_kwargs))
        self.assertEqual(response.status_code, 200)

    def test_config_post_with_correct_data(self):
        form_configs = deepcopy(self.dhis2_repeater.dhis2_config['form_configs'])
        form_configs[0]['program_id'] = 'abcd'

        data = {
            'form_configs': json.dumps(form_configs)
        }

        response = self.client.post(reverse('config_dhis2_repeater', kwargs=self.url_kwargs), data)
        self.assertEqual(response.status_code, 200)

        updated_repeater = Dhis2Repeater.objects.get(id=self.dhis2_repeater.id)

        self.assertEqual(updated_repeater.dhis2_config['form_configs'], form_configs)

        # restore the state
        updated_repeater.dhis2_config = dhis2_repeater_data['dhis2_config']
        updated_repeater.save()

    def test_config_post_with_incorrect_data(self):
        form_configs = deepcopy(dhis2_repeater_data['dhis2_config']['form_configs'])

        # Delete a required Property
        form_configs[0].pop('program_id')

        data = {
            'form_configs': json.dumps(form_configs)
        }

        response = self.client.post(reverse('config_dhis2_repeater', kwargs=self.url_kwargs), data)

        self.assertEqual(response.status_code, 400)

        # No changes in repeater doc when request fails
        unchanged_repeater = Dhis2Repeater.objects.get(id=self.dhis2_repeater.id)

        self.assertEqual(unchanged_repeater.dhis2_config, self.dhis2_repeater.dhis2_config)


class TestConfigDhis2EntityRepeaterView(BaseViewTest):

    @classmethod
    def _create_data(cls):
        conn = ConnectionSettings(
            domain=cls.domain,
            name="motech_conn",
            url="url",
        )
        conn.save()
        cls.connection_setting = conn
        cls.dhis2_repeater = Dhis2EntityRepeater(**deepcopy(dhis2_entity_repeater_data))
        cls.dhis2_repeater.domain = DOMAIN
        cls.dhis2_repeater.connection_settings = conn
        cls.dhis2_repeater.save()
        cls.url_kwargs = {
            'domain': cls.domain.name,
            'repeater_id': cls.dhis2_repeater.repeater_id
        }

    def test_config_get(self):
        response = self.client.get(reverse('config_dhis2_entity_repeater', kwargs=self.url_kwargs))
        self.assertEqual(response.status_code, 200)

    def test_config_post_with_correct_data(self):
        case_configs = deepcopy(self.dhis2_repeater.dhis2_entity_config['case_configs'])
        case_configs[0]['te_type_id'] = 'abcd'

        data = {
            'case_configs': json.dumps(case_configs)
        }

        response = self.client.post(reverse('config_dhis2_entity_repeater', kwargs=self.url_kwargs), data)
        self.assertEqual(response.status_code, 200)

        updated_repeater = Dhis2EntityRepeater.objects.get(id=self.dhis2_repeater.id)

        self.assertEqual(updated_repeater.dhis2_entity_config['case_configs'], case_configs)

        # restore the state
        updated_repeater.dhis2_config = dhis2_repeater_data['dhis2_config']
        updated_repeater.save()
