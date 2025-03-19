from copy import deepcopy
import json

from django.urls import reverse

from corehq.motech.dhis2.tests.test_views import BaseViewTest
from corehq.motech.models import ConnectionSettings
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.motech.openmrs.tests.data.openmrs_repeater import test_data


class TestOpenmrsRepeaterViews(BaseViewTest):
    @classmethod
    def _create_data(cls):
        conn = ConnectionSettings(
            domain=cls.domain,
            name="motech_conn",
            url="url",
        )
        conn.save()
        cls.connection_setting = conn
        cls.repeater = OpenmrsRepeater(**deepcopy(test_data))
        cls.repeater.domain = cls.domain.name
        cls.repeater.connection_settings_id = conn.id
        cls.repeater.save()
        cls.url_kwargs = {
            'domain': cls.domain.name,
            'repeater_id': cls.repeater.repeater_id
        }

    def test_config_openmrs_repeater_get(self):
        response = self.client.get(reverse('config_openmrs_repeater', kwargs=self.url_kwargs))
        self.assertEqual(response.status_code, 200)

    def test_config_openmrs_repeater_post(self):
        repeater_data = deepcopy(test_data['openmrs_config'])
        repeater_data['openmrs_provider'] = 'abcd'
        repeater_data['case_config']['person_properties'] = {
            'gender': {
                'value': 'male',
                'external_data_type': 'omrs_text'
            }
        }
        post_data = {
            'openmrs_provider': repeater_data['openmrs_provider'],
            'patient_config': json.dumps(repeater_data['case_config']),
            'encounters_config': json.dumps(repeater_data['form_configs'])
        }
        response = self.client.post(reverse('config_openmrs_repeater', kwargs=self.url_kwargs), data=post_data)
        self.assertEqual(response.status_code, 200)
        updated_repeater = OpenmrsRepeater.objects.get(id=self.repeater.id)
        self.assertEqual(updated_repeater.to_json()['openmrs_config'], repeater_data)

    def test_config_openmrs_repeater_post_with_errors(self):
        repeater_data = deepcopy(test_data['openmrs_config'])
        repeater_data['openmrs_provider'] = 'abcd'
        repeater_data['case_config']['person_properties'] = {
            'blah': {
                'value': 'blah',
                'external_data_type': 'omrs_text'
            }
        }
        post_data = {
            'openmrs_provider': repeater_data['openmrs_provider'],
            'patient_config': json.dumps(repeater_data['case_config']),
            'encounters_config': json.dumps(repeater_data['form_configs'])
        }
        response = self.client.post(reverse('config_openmrs_repeater', kwargs=self.url_kwargs), data=post_data)
        self.assertEqual(response.status_code, 200)
        updated_repeater = OpenmrsRepeater.objects.get(id=self.repeater.id)

        # Config should not change
        self.assertEqual(updated_repeater.to_json(), self.repeater.to_json())
