import datetime

from django.test import TestCase

from dimagi.utils.dates import add_months_to_date
from pillowtop.processors.form import mark_latest_submission

from corehq import toggles
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.models import EnterpriseMobileWorkerSettings
from corehq.apps.enterprise.tests.utils import (
    add_domains_to_enterprise_account,
    get_enterprise_account,
    get_enterprise_software_plan,
)
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.utils import TestFormMetadata
from corehq.util.test_utils import make_es_ready_form


@es_test(requires=[user_adapter, form_adapter], setup_class=True)
class TestEnterpriseMobileWorkerSettings(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        today = datetime.datetime.utcnow()

        one_year_ago = add_months_to_date(today.date(), -12)
        enterprise_plan = get_enterprise_software_plan()
        cls.billing_account = get_enterprise_account()
        cls.domains = [
            create_domain('test-emw-settings-001'),
            create_domain('test-emw-settings-002'),
        ]
        add_domains_to_enterprise_account(
            cls.billing_account,
            cls.domains,
            enterprise_plan,
            one_year_ago
        )

        cls.emw_settings = EnterpriseMobileWorkerSettings.objects.create(
            account=cls.billing_account,
            enable_auto_deactivation=True,
        )

        cls.active_user1 = CommCareUser.create(
            domain=cls.domains[0].name,
            username='active1',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )
        cls.active_user2 = CommCareUser.create(
            domain=cls.domains[0].name,
            username='active2',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )
        cls.active_user3 = CommCareUser.create(
            domain=cls.domains[1].name,
            username='active3',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )
        cls.active_user4 = CommCareUser.create(
            domain=cls.domains[1].name,
            username='active4',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )
        cls.active_user5 = CommCareUser.create(
            domain=cls.domains[1].name,
            username='active5',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )
        cls.active_user5.created_on = today - datetime.timedelta(
            days=cls.emw_settings.inactivity_period
        )
        cls.active_user5.save()
        cls.active_user6 = CommCareUser.create(
            domain=cls.domains[1].name,
            username='active6',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )

        cls.users = [
            cls.active_user1,
            cls.active_user2,
            cls.active_user3,
            cls.active_user4,
            cls.active_user5,
            cls.active_user6,
            CommCareUser.create(
                domain=cls.domains[0].name,
                username='inactive',
                password='secret',
                created_by=None,
                created_via=None,
                is_active=False
            ),
            CommCareUser.create(
                domain=cls.domains[1].name,
                username='inactive2',
                password='secret',
                created_by=None,
                created_via=None,
                is_active=False
            ),
        ]

        form_submissions = [
            (TestFormMetadata(
                domain=cls.domains[0].name,
                received_on=today - datetime.timedelta(days=cls.emw_settings.inactivity_period - 1),
                user_id=cls.active_user1.user_id,
                username=cls.active_user1.username,
            ), cls.active_user1),
            (TestFormMetadata(
                domain=cls.domains[0].name,
                received_on=today - datetime.timedelta(days=cls.emw_settings.inactivity_period),
                user_id=cls.active_user2.user_id,
                username=cls.active_user2.username,
            ), cls.active_user2),
            (TestFormMetadata(
                domain=cls.domains[1].name,
                received_on=today - datetime.timedelta(days=cls.emw_settings.inactivity_period - 10),
                user_id=cls.active_user3.user_id,
                username=cls.active_user3.username,
            ), cls.active_user3),
            (TestFormMetadata(
                domain=cls.domains[1].name,
                received_on=today - datetime.timedelta(days=cls.emw_settings.inactivity_period + 1),
                user_id=cls.active_user6.user_id,
                username=cls.active_user6.username,
            ), cls.active_user6),
        ]
        for form_metadata, user in form_submissions:
            # ensure users are as old as the received_on dates of their submissions
            user.created_on = form_metadata.received_on
            user.save()
            form_pair = make_es_ready_form(form_metadata)
            form_adapter.index(form_pair.json_form, refresh=True)
            mark_latest_submission(
                form_metadata.domain,
                user,
                form_metadata.app_id,
                "build-id",
                "2",
                {'deviceID': 'device-id'},
                form_metadata.received_on
            )

        for user in cls.users:
            fresh_user = CommCareUser.get_by_user_id(user.user_id)
            user_adapter.index(fresh_user, refresh=True)

    @classmethod
    def tearDownClass(cls):
        EnterpriseMobileWorkerSettings.objects.all().delete()
        for user in cls.users:
            user.delete(user.domain, None)
        for domain in cls.domains:
            domain.delete()
        super().tearDownClass()

    def test_mobile_workers_are_deactivated(self):
        active_statuses = [(u.username, u.is_active) for u in self.users]
        self.assertListEqual(
            active_statuses,
            [
                ('active1', True),
                ('active2', True),
                ('active3', True),
                ('active4', True),
                ('active5', True),
                ('active6', True),
                ('inactive', False),
                ('inactive2', False),
            ]
        )

        for domain in self.emw_settings.account.get_domains():
            self.emw_settings.deactivate_mobile_workers_by_inactivity(domain)

        refreshed_users = [CommCareUser.get_by_user_id(u.get_id) for u in self.users]
        new_active_statuses = [(u.username, u.is_active) for u in refreshed_users]
        self.assertListEqual(
            new_active_statuses,
            [
                ('active1', True),
                ('active2', False),
                ('active3', True),
                ('active4', True),
                ('active5', False),
                ('active6', False),
                ('inactive', False),
                ('inactive2', False),
            ]
        )


class TestEnterpriseMobileWorkerSettingsCustomDeactivation(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        today = datetime.datetime.utcnow()

        one_year_ago = add_months_to_date(today.date(), -12)
        enterprise_plan = get_enterprise_software_plan()
        cls.account1 = get_enterprise_account()
        cls.account2 = get_enterprise_account()
        cls.account3 = get_enterprise_account()
        cls.domains1 = [
            create_domain('test-deactivation-account1-001'),
            create_domain('test-deactivation-account1-002'),
        ]
        cls.domains2 = [
            create_domain('test-deactivation-account2-001'),
        ]
        cls.domains3 = [
            create_domain('test-deactivation-account3-001'),
        ]
        add_domains_to_enterprise_account(
            cls.account1,
            cls.domains1,
            enterprise_plan,
            one_year_ago
        )
        toggles.AUTO_DEACTIVATE_MOBILE_WORKERS.set(
            cls.domains1[0].name, True, namespace=toggles.NAMESPACE_DOMAIN
        )
        add_domains_to_enterprise_account(
            cls.account2,
            cls.domains2,
            enterprise_plan,
            one_year_ago
        )
        toggles.AUTO_DEACTIVATE_MOBILE_WORKERS.set(
            cls.domains2[0].name, True, namespace=toggles.NAMESPACE_DOMAIN
        )
        add_domains_to_enterprise_account(
            cls.account3,
            cls.domains3,
            enterprise_plan,
            one_year_ago
        )
        toggles.AUTO_DEACTIVATE_MOBILE_WORKERS.set(
            cls.domains3[0].name, True, toggles.NAMESPACE_DOMAIN
        )

        cls.emw_settings1 = EnterpriseMobileWorkerSettings.objects.create(
            account=cls.account1,
            allow_custom_deactivation=True,
        )

        cls.emw_settings2 = EnterpriseMobileWorkerSettings.objects.create(
            account=cls.account2,
            allow_custom_deactivation=False,
        )

    @classmethod
    def tearDownClass(cls):
        EnterpriseMobileWorkerSettings.objects.all().delete()
        for domains in [cls.domains1, cls.domains2, cls.domains3]:
            for domain in domains:
                domain.delete()
        super().tearDownClass()

    def tearDown(self):
        for domains in [self.domains1, self.domains2, self.domains3]:
            for domain in domains:
                EnterpriseMobileWorkerSettings.clear_domain_caches(domain.name)
        super().tearDown()

    def test_domain_is_enabled(self):
        self.assertTrue(EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            self.domains1[0].name
        ))

    def test_domain_is_disabled_by_toggle(self):
        self.assertFalse(EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            self.domains1[1].name
        ))

    def test_domain_has_setting_disabled(self):
        self.assertFalse(EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            self.domains2[0].name
        ))

    def test_domain_has_no_settings_created(self):
        self.assertFalse(EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            self.domains3[0].name
        ))

    def _cleanup_cache_test(self):
        self.emw_settings1.allow_custom_deactivation = True
        self.emw_settings1.save()

    def test_cache_clearing(self):
        self.addCleanup(self._cleanup_cache_test)
        domain = self.domains1[0].name
        self.assertTrue(EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            domain
        ))
        self.emw_settings1.allow_custom_deactivation = False
        self.emw_settings1.save()
        self.assertTrue(EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            domain
        ))
        EnterpriseMobileWorkerSettings.clear_domain_caches(domain)
        self.assertFalse(EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            domain
        ))
