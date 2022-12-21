import datetime

from django.test import TestCase
from unittest import mock

from corehq import toggles
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.forms import EnterpriseManageMobileWorkersForm
from corehq.apps.enterprise.models import EnterpriseMobileWorkerSettings
from corehq.apps.enterprise.tests.utils import (
    get_enterprise_account,
    add_domains_to_enterprise_account,
    get_enterprise_software_plan,
)
from dimagi.utils.dates import add_months_to_date


class EnterpriseManageMobileWorkersFormTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        today = datetime.datetime.utcnow()

        one_year_ago = add_months_to_date(today.date(), -12)
        enterprise_plan = get_enterprise_software_plan()
        cls.account = get_enterprise_account()

        cls.domains = [
            create_domain('test-emws-form-001'),
            create_domain('test-emws-form-002'),
        ]
        add_domains_to_enterprise_account(
            cls.account,
            cls.domains,
            enterprise_plan,
            one_year_ago
        )
        for domain in cls.domains:
            toggles.AUTO_DEACTIVATE_MOBILE_WORKERS.set(
                domain.name, True, namespace=toggles.NAMESPACE_DOMAIN
            )

        cls.emw_settings = EnterpriseMobileWorkerSettings.objects.create(
            account=cls.account,
        )

    def tearDown(self):
        # reset settings to defaults
        self.emw_settings.refresh_from_db()
        self.emw_settings.allow_custom_deactivation = False
        self.emw_settings.enable_auto_deactivation = False
        self.emw_settings.inactivity_period = 90
        self.emw_settings.save()

    def test_update_settings_auto_deactivation(self):
        post_data = {
            'enable_auto_deactivation': True,
            'inactivity_period': 30,
            'allow_custom_deactivation': False,
        }
        self.emw_settings.refresh_from_db()
        self.assertFalse(self.emw_settings.enable_auto_deactivation)
        self.assertEqual(self.emw_settings.inactivity_period, 90)
        self.assertFalse(self.emw_settings.allow_custom_deactivation)
        emw_settings_form = EnterpriseManageMobileWorkersForm(
            post_data, emw_settings=self.emw_settings
        )
        self.assertTrue(emw_settings_form.is_valid())
        emw_settings_form.update_settings()
        self.emw_settings.refresh_from_db()
        self.assertTrue(self.emw_settings.enable_auto_deactivation)
        self.assertEqual(self.emw_settings.inactivity_period, 30)
        self.assertFalse(self.emw_settings.allow_custom_deactivation)

    def test_update_settings_custom_deactivation(self):
        post_data = {
            'enable_auto_deactivation': False,
            'inactivity_period': 90,
            'allow_custom_deactivation': True,
        }
        self.emw_settings.refresh_from_db()
        self.assertFalse(self.emw_settings.enable_auto_deactivation)
        self.assertEqual(self.emw_settings.inactivity_period, 90)
        self.assertFalse(self.emw_settings.allow_custom_deactivation)
        emw_settings_form = EnterpriseManageMobileWorkersForm(
            post_data, emw_settings=self.emw_settings
        )
        self.assertTrue(emw_settings_form.is_valid())
        emw_settings_form.update_settings()
        self.emw_settings.refresh_from_db()
        self.assertFalse(self.emw_settings.enable_auto_deactivation)
        self.assertEqual(self.emw_settings.inactivity_period, 90)
        self.assertTrue(self.emw_settings.allow_custom_deactivation)

    @mock.patch('corehq.apps.enterprise.models.EnterpriseMobileWorkerSettings.clear_domain_caches')
    def test_update_settings_clears_cache(self, clear_domain_caches):
        post_data = {
            'enable_auto_deactivation': True,
            'inactivity_period': 90,
            'allow_custom_deactivation': True,
        }
        emw_settings_form = EnterpriseManageMobileWorkersForm(
            post_data, emw_settings=self.emw_settings
        )
        self.assertTrue(emw_settings_form.is_valid())
        emw_settings_form.update_settings()
        domains_cache_cleared = [
            arg[0][0] for arg in clear_domain_caches.call_args_list
        ]
        self.assertCountEqual(
            domains_cache_cleared,
            [
                'test-emws-form-002',
                'test-emws-form-001',
            ]
        )
