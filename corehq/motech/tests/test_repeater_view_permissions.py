"""
Access-control tests for the OpenMRS and DHIS2 repeater views: users
need the "Edit MOTECH" permission, and the project needs the Data
Forwarding privilege and the integration's feature flag.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.motech.dhis2.repeaters import Dhis2EntityRepeater, Dhis2Repeater
from corehq.motech.dhis2.tests.data.repeater import (
    dhis2_entity_repeater_data,
    dhis2_repeater_data,
)
from corehq.motech.models import ConnectionSettings
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.motech.openmrs.tests.data.openmrs_repeater import test_data
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.requests import Requests
from corehq.util.test_utils import (
    flag_disabled,
    flag_enabled,
    privilege_enabled,
)

DOMAIN = 'motech-view-perms'
PASSWORD = 'Passw0rd!Passw0rd!'
NO_PERMS_USERNAME = 'no-perms@example.com'
MOTECH_USERNAME = 'motech-editor@example.com'

OPENMRS_VIEWS = [
    'config_openmrs_repeater',
    'openmrs_patient_identifier_types',
    'openmrs_person_attribute_types',
    'openmrs_raw_api',
    'openmrs_test_fire',
    'openmrs_import_now',
]
DHIS2_VIEWS = [
    'config_dhis2_repeater',
    'config_dhis2_entity_repeater',
]


class TestRepeaterViewPermissions(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.no_perms_user = cls._create_user(
            NO_PERMS_USERNAME,
            'no-perms',
            HqPermissions(),
        )
        cls.motech_user = cls._create_user(
            MOTECH_USERNAME,
            'motech-editor',
            HqPermissions(edit_motech=True),
        )
        conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='motech_conn',
            url='https://openmrs.example.com/',
        )
        cls.openmrs_repeater = OpenmrsRepeater.objects.create(
            domain=DOMAIN,
            connection_settings_id=conn.id,
            **deepcopy(test_data),
        )
        cls.dhis2_repeater = Dhis2Repeater.objects.create(
            domain=DOMAIN,
            connection_settings_id=conn.id,
            **deepcopy(dhis2_repeater_data),
        )
        cls.dhis2_entity_repeater = Dhis2EntityRepeater.objects.create(
            domain=DOMAIN,
            connection_settings_id=conn.id,
            **deepcopy(dhis2_entity_repeater_data),
        )
        cls.repeat_record = RepeatRecord.objects.create(
            domain=DOMAIN,
            repeater_id=cls.openmrs_repeater.repeater_id,
            payload_id='c0ffee',
            registered_at=datetime.utcnow(),
        )

    @classmethod
    def _create_user(cls, username, role_name, permissions):
        role = UserRole.create(DOMAIN, role_name, permissions=permissions)
        user = WebUser.create(
            DOMAIN, username, PASSWORD,
            created_by=None, created_via=None, role_id=role.get_id,
        )
        cls.addClassCleanup(user.delete, DOMAIN, deleted_by=None)
        return user

    def _url(self, view_name):
        openmrs_id = self.openmrs_repeater.repeater_id
        args_by_view = {
            'config_openmrs_repeater': [openmrs_id],
            'openmrs_patient_identifier_types': [openmrs_id],
            'openmrs_person_attribute_types': [openmrs_id],
            'openmrs_raw_api': [openmrs_id, '/patient'],
            'openmrs_test_fire': [openmrs_id, self.repeat_record.id],
            'openmrs_import_now': [],
            'config_dhis2_repeater': [self.dhis2_repeater.repeater_id],
            'config_dhis2_entity_repeater': [self.dhis2_entity_repeater.repeater_id],
        }
        return reverse(view_name, args=[DOMAIN] + args_by_view[view_name])

    @contextmanager
    def _side_effects_blocked(self):
        """
        Fails the test if a view gets as far as contacting the external
        system, sending a repeat record, or starting an import.
        """
        with (
            patch.object(Requests, 'get') as requests_get,
            patch.object(OpenmrsRepeater, 'fire_for_record') as fire_for_record,
            patch('corehq.motech.openmrs.views.import_patients_to_domain')
            as import_patients,
        ):
            yield
        requests_get.assert_not_called()
        fire_for_record.assert_not_called()
        import_patients.assert_not_called()

    def _get_configs(self):
        return (
            OpenmrsRepeater.objects.get(
                id=self.openmrs_repeater.id
            ).openmrs_config,
            Dhis2Repeater.objects.get(id=self.dhis2_repeater.id).dhis2_config,
            Dhis2EntityRepeater.objects.get(
                id=self.dhis2_entity_repeater.id,
            ).dhis2_entity_config,
        )

    @flag_enabled('OPENMRS_INTEGRATION')
    @flag_enabled('DHIS2_INTEGRATION')
    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_user_without_permission_is_denied(self):
        configs_before = self._get_configs()
        self.client.login(username=NO_PERMS_USERNAME, password=PASSWORD)
        for view_name in OPENMRS_VIEWS + DHIS2_VIEWS:
            for method in ('get', 'post'):
                with self.subTest(view=view_name, method=method):
                    with self._side_effects_blocked():
                        method = getattr(self.client, method)
                        response = method(self._url(view_name), data={
                            'openmrs_provider': 'attacker',
                            'patient_config': '{}',
                            'encounters_config': '[]',
                            'form_configs': '[]',
                            'case_configs': '[]',
                        })
                    assert response.status_code == 403
        assert self._get_configs() == configs_before

    @flag_disabled('OPENMRS_INTEGRATION')
    @flag_disabled('DHIS2_INTEGRATION')
    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_feature_flag_required(self):
        self.client.login(username=MOTECH_USERNAME, password=PASSWORD)
        for view_name in OPENMRS_VIEWS + DHIS2_VIEWS:
            with self.subTest(view=view_name):
                with self._side_effects_blocked():
                    response = self.client.post(self._url(view_name))
                assert response.status_code == 404

    @flag_enabled('OPENMRS_INTEGRATION')
    @flag_enabled('DHIS2_INTEGRATION')
    def test_data_forwarding_privilege_required(self):
        self.client.login(username=MOTECH_USERNAME, password=PASSWORD)
        # openmrs_import_now is for importers, not data forwarding,
        # so like OpenmrsImporterView it does not need the privilege.
        views = [
            v for v in OPENMRS_VIEWS + DHIS2_VIEWS
            if v != 'openmrs_import_now'
        ]
        for view_name in views:
            with self.subTest(view=view_name):
                with self._side_effects_blocked():
                    response = self.client.get(self._url(view_name))
                self.assertTemplateUsed(
                    response,
                    'domain/bootstrap3/insufficient_privilege_notification.html',
                )

    @flag_enabled('OPENMRS_INTEGRATION')
    @flag_enabled('DHIS2_INTEGRATION')
    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_config_views_allowed_with_permission(self):
        self.client.login(username=MOTECH_USERNAME, password=PASSWORD)
        for view_name in ['config_openmrs_repeater'] + DHIS2_VIEWS:
            with self.subTest(view=view_name):
                response = self.client.get(self._url(view_name))
                assert response.status_code == 200

    @flag_enabled('OPENMRS_INTEGRATION')
    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_raw_api_allowed_with_permission(self):
        self.client.login(username=MOTECH_USERNAME, password=PASSWORD)
        with patch.object(Requests, 'get') as requests_get:
            requests_get.return_value.json.return_value = {'results': []}
            response = self.client.get(self._url('openmrs_raw_api'))
        assert response.status_code == 200
        assert response.json() == {'results': []}

    @flag_enabled('OPENMRS_INTEGRATION')
    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_test_fire_allowed_with_permission(self):
        self.client.login(username=MOTECH_USERNAME, password=PASSWORD)
        with (
            patch.object(OpenmrsRepeater, 'fire_for_record') as fire_for_record
        ):
            response = self.client.post(self._url('openmrs_test_fire'))
        assert response.status_code == 200
        fire_for_record.assert_called_once()

    @flag_enabled('OPENMRS_INTEGRATION')
    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_test_fire_rejects_get(self):
        self.client.login(username=MOTECH_USERNAME, password=PASSWORD)
        with self._side_effects_blocked():
            response = self.client.get(self._url('openmrs_test_fire'))
        assert response.status_code == 405

    @flag_enabled('OPENMRS_INTEGRATION')
    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_test_fire_rejects_record_of_other_repeater(self):
        other_record = RepeatRecord.objects.create(
            domain=DOMAIN,
            repeater_id=self.dhis2_repeater.repeater_id,
            payload_id='c0ffee',
            registered_at=datetime.utcnow(),
        )
        url = reverse(
            'openmrs_test_fire',
            args=[DOMAIN, self.openmrs_repeater.repeater_id, other_record.id],
        )
        self.client.login(username=MOTECH_USERNAME, password=PASSWORD)
        with self._side_effects_blocked():
            response = self.client.post(url)
        assert response.status_code == 404

    @flag_enabled('OPENMRS_INTEGRATION')
    def test_import_now_allowed_with_permission(self):
        self.client.login(username=MOTECH_USERNAME, password=PASSWORD)
        with (
            patch('corehq.motech.openmrs.views.import_patients_to_domain')
            as import_patients
        ):
            response = self.client.post(self._url('openmrs_import_now'))
        assert response.status_code == 202
        import_patients.assert_called_once_with(DOMAIN, force=True)
