import datetime

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.models import EnterpriseMobileWorkerSettings
from corehq.apps.enterprise.tests.utils import (
    get_enterprise_account,
    add_domains_to_enterprise_account,
    get_enterprise_software_plan,
    cleanup_accounting,
)
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.mappings import XFORM_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.pillows.user import transform_user_for_elasticsearch
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import make_es_ready_form
from dimagi.utils.dates import add_months_to_date
from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.processors.form import mark_latest_submission


@es_test
class TestEnterpriseMobileWorkerSettings(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.es = get_es_new()
        initialize_index_and_mapping(cls.es, USER_INDEX_INFO)
        initialize_index_and_mapping(cls.es, XFORM_INDEX_INFO)

        today = datetime.datetime.utcnow()

        one_year_ago = add_months_to_date(today.date(), -12)
        enterprise_plan = get_enterprise_software_plan()
        cls.billing_account = get_enterprise_account()
        cls.addClassCleanup(cleanup_accounting)
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
            send_to_elasticsearch('forms', form_pair.json_form)
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
            elastic_user = transform_user_for_elasticsearch(fresh_user.to_json())
            send_to_elasticsearch('users', elastic_user)

        cls.es.indices.refresh(USER_INDEX_INFO.alias)
        cls.es.indices.refresh(XFORM_INDEX_INFO.alias)

    @classmethod
    def tearDownClass(cls):
        EnterpriseMobileWorkerSettings.objects.all().delete()
        ensure_index_deleted(USER_INDEX_INFO.alias)
        ensure_index_deleted(XFORM_INDEX_INFO.alias)
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
