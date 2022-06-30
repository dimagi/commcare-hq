import datetime

from unittest import mock

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.models import EnterpriseMobileWorkerSettings
from corehq.apps.enterprise.tasks import auto_deactivate_mobile_workers
from corehq.apps.enterprise.tests.utils import (
    get_enterprise_account,
    get_enterprise_software_plan,
    add_domains_to_enterprise_account,
)
from dimagi.utils.dates import add_months_to_date


class TestAutoDeactivateMobileWorkersTask(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.today = datetime.date.today()
        one_year_ago = add_months_to_date(cls.today, -12)
        enterprise_plan = get_enterprise_software_plan()

        cls.billing_account1 = get_enterprise_account()
        cls.domains1 = [
            create_domain('domain-account1-001'),
            create_domain('domain-account1-002'),
        ]
        add_domains_to_enterprise_account(
            cls.billing_account1,
            cls.domains1,
            enterprise_plan,
            one_year_ago
        )
        cls.emw_settings_active = EnterpriseMobileWorkerSettings.objects.create(
            account=cls.billing_account1,
            enable_auto_deactivation=True,
            allow_custom_deactivation=True,
        )

        cls.billing_account2 = get_enterprise_account()
        cls.domains2 = [
            create_domain('domain-account2-001'),
            create_domain('domain-account2-002'),
            create_domain('domain-account2-003'),
        ]
        add_domains_to_enterprise_account(
            cls.billing_account2,
            cls.domains2,
            enterprise_plan,
            one_year_ago
        )
        cls.emw_settings_no_custom = EnterpriseMobileWorkerSettings.objects.create(
            account=cls.billing_account2,
            enable_auto_deactivation=True,
        )

        cls.billing_account3 = get_enterprise_account()
        cls.domains3 = [
            create_domain('domain-account3-001'),
            create_domain('domain-account3-002'),
        ]
        add_domains_to_enterprise_account(
            cls.billing_account3,
            cls.domains3,
            enterprise_plan,
            one_year_ago
        )
        cls.emw_settings_inactive = EnterpriseMobileWorkerSettings.objects.create(
            account=cls.billing_account3,
            enable_auto_deactivation=False,
            allow_custom_deactivation=False,
        )

        cls.billing_account4 = get_enterprise_account()
        cls.domains4 = [
            create_domain('domain-account4-001'),
        ]
        add_domains_to_enterprise_account(
            cls.billing_account4,
            cls.domains4,
            enterprise_plan,
            one_year_ago
        )
        cls.emw_settings_inactive = EnterpriseMobileWorkerSettings.objects.create(
            account=cls.billing_account4,
            enable_auto_deactivation=False,
            allow_custom_deactivation=True,
        )

    @classmethod
    def tearDownClass(cls):
        EnterpriseMobileWorkerSettings.objects.all().delete()
        for domains in [cls.domains1, cls.domains2, cls.domains3, cls.domains4]:
            for domain in domains:
                domain.delete()
        super().tearDownClass()

    @mock.patch('corehq.apps.enterprise.tasks.metrics_gauge')
    @mock.patch('corehq.apps.enterprise.tasks.EnterpriseMobileWorkerSettings'
                '.deactivate_mobile_workers_by_inactivity')
    @mock.patch('corehq.apps.enterprise.tasks.DeactivateMobileWorkerTrigger'
                '.deactivate_mobile_workers')
    def test_auto_deactivate_mobile_workers_task(
        self, deactivate_mobile_workers, deactivate_mobile_workers_by_inactivity,
        metrics_gauge
    ):
        auto_deactivate_mobile_workers()
        domains_checked_for_inactivity = set(
            arg[0][0]
            for arg in deactivate_mobile_workers_by_inactivity.call_args_list
        )
        self.assertSetEqual(
            domains_checked_for_inactivity,
            {
                'domain-account1-002',
                'domain-account1-001',
                'domain-account2-003',
                'domain-account2-002',
                'domain-account2-001',
            }
        )
        domains_with_custom_deactivations = set(
            (arg[0][0], arg[1]['date_deactivation'])
            for arg in deactivate_mobile_workers.call_args_list
        )
        self.assertSetEqual(
            domains_with_custom_deactivations,
            {
                ('domain-account1-002', self.today),
                ('domain-account1-001', self.today),
                ('domain-account4-001', self.today),
            }
        )
        metrics_gauge.assert_called_once()
