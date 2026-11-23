from datetime import date, datetime, timedelta

from django.test import TestCase

from time_machine import travel

from corehq.apps.cloudcare.const import DEVICE_ID
from corehq.apps.domain.models import ChatbotDomainUsage, Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.hqwebapp.models import ChatbotQuotaPressure
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, DomainMembership, WebUser

from ..daily_calcs import (
    _calc_chatbot_active_users_30d,
    _calc_chatbot_users_at_quota_30d,
    _calc_chatbot_users_near_quota_30d,
    _calc_users_with_web_apps_submission_30d,
    _calc_web_users_accessed_30d,
    _chatbot_user_ids_under_quota_pressure,
)
from ..metric_registry import DomainContext
from .utils import save_to_es_analytics_db


@es_test(requires=[user_adapter])
@travel('2026-06-08', tick=False)
class TestCalcWebUsersAccessed30d(TestCase):

    def setUp(self):
        super().setUp()
        self.domain_obj = create_domain('web-access-test')
        self.addCleanup(self.domain_obj.delete)

    def tearDown(self):
        delete_all_users()
        super().tearDown()

    def _make_web_user(self, name, domain, last_accessed):
        user = WebUser.create(
            domain=domain,
            username=f'{name}@example.com',
            password='Passw0rd!',
            created_by=None,
            created_via=None,
        )
        if last_accessed is not None:
            user.get_domain_membership(domain).last_accessed = last_accessed
            user.save()
        user_adapter.index(user, refresh=True)
        return user

    def test_counts_web_users_accessed_recently(self):
        today = date.today()
        self._make_web_user('recent', self.domain_obj.name, today)
        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 1

    def test_counts_web_users_with_other_domain_memberships_accessed_recently(self):
        today = date.today()
        other_domain_obj = create_domain('web-access-other')
        self.addCleanup(other_domain_obj.delete)

        # Multi-domain member who was active in this domain -> included in count.
        other_domain_user = self._make_web_user('elsewhere', 'web-access-other', None)
        other_domain_user.add_domain_membership(self.domain_obj.name)
        other_domain_user.get_domain_membership(self.domain_obj.name).last_accessed = today
        other_domain_user.save()
        user_adapter.index(other_domain_user, refresh=True)

        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 1

    def test_counts_web_users_accessed_30_days_ago(self):
        today = date.today()
        self._make_web_user('30_days', self.domain_obj.name, today - timedelta(days=30))
        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 1

    def test_excludes_web_users_accessed_31_days_ago(self):
        today = date.today()
        self._make_web_user('31_days', self.domain_obj.name, today - timedelta(days=31))
        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 0

    def test_excludes_web_users_never_accessed(self):
        self._make_web_user('never', self.domain_obj.name, None)
        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 0

    def test_excludes_web_users_only_accessed_other_domain(self):
        today = date.today()
        other_domain_obj = create_domain('web-access-other')
        self.addCleanup(other_domain_obj.delete)

        # Active only in another domain -> excluded by the domain filter.
        other_domain_user = self._make_web_user('elsewhere', 'web-access-other', today)
        other_domain_user.add_domain_membership(self.domain_obj.name)
        other_domain_user.save()
        user_adapter.index(other_domain_user, refresh=True)

        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 0


@es_test(requires=[form_adapter])
@travel('2026-06-08', tick=False)
class TestCalcUsersWithWebAppsSubmission30d(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'web-apps-sub-test'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

    def tearDown(self):
        delete_all_users()
        super().tearDown()

    def _make_user(self, name):
        user = CommCareUser.create(
            domain=self.domain,
            username=name,
            password='Passw0rd!',
            created_by=None,
            created_via=None,
        )
        return user

    def test_counts_only_recent_web_apps_submitters_in_domain(self):
        now = datetime.now()
        web_apps_user = self._make_user('webapps')
        mobile_user = self._make_user('mobile')

        # Counts: real domain user, web-apps device, within the window.
        save_to_es_analytics_db(self.domain, now, 'app', DEVICE_ID, web_apps_user.user_id)
        # Excluded: not from web apps.
        save_to_es_analytics_db(self.domain, now, 'app', 'some-phone-imei', mobile_user.user_id)
        # Excluded: weird (system) user id.
        save_to_es_analytics_db(self.domain, now, 'app', DEVICE_ID, 'commtrack-system')
        # Excluded: user id with no membership in this domain.
        save_to_es_analytics_db(self.domain, now, 'app', DEVICE_ID, 'unknown-user-id')
        assert _calc_users_with_web_apps_submission_30d(DomainContext(self.domain_obj)) == 1

    def counts_submission_30_days_ago(self):
        thirty_days_ago = datetime.now() - timedelta(days=30)
        web_apps_user = self._make_user('webapps')
        save_to_es_analytics_db(self.domain, thirty_days_ago, 'app', DEVICE_ID, web_apps_user.user_id)
        assert _calc_users_with_web_apps_submission_30d(DomainContext(self.domain_obj)) == 1

    def excludes_submission_31_days_ago(self):
        thirty_one_days_ago = datetime.now() - timedelta(days=31)
        web_apps_user = self._make_user('webapps')
        save_to_es_analytics_db(self.domain, thirty_one_days_ago, 'app', DEVICE_ID, web_apps_user.user_id)
        assert _calc_users_with_web_apps_submission_30d(DomainContext(self.domain_obj)) == 0


@travel('2026-11-20', tick=False)
class TestCalcChatbotActiveUsers30d(TestCase):
    domain = 'chatbot-active-users-test'

    def _chatted(self, user_id, days_ago, domain=None):
        ChatbotDomainUsage.objects.create(
            domain=domain or self.domain,
            user_id=user_id,
            last_message_at=datetime.now() - timedelta(days=days_ago),
        )

    def _calc(self):
        return _calc_chatbot_active_users_30d(DomainContext(Domain(name=self.domain)))

    def test_counts_users_who_chatted_recently(self):
        self._chatted('alice', days_ago=0)
        self._chatted('bob', days_ago=5)
        assert self._calc() == 2

    def test_counts_users_who_chatted_30_days_ago(self):
        self._chatted('alice', days_ago=30)
        assert self._calc() == 1

    def test_excludes_users_who_chatted_31_days_ago(self):
        self._chatted('alice', days_ago=31)
        assert self._calc() == 0

    def test_excludes_users_who_only_chatted_in_other_domain(self):
        self._chatted('alice', days_ago=0, domain='other-domain')
        assert self._calc() == 0


@es_test(requires=[user_adapter])
@travel('2026-11-20', tick=False)
class TestCalcChatbotUsersUnderQuotaPressure30d(TestCase):
    domain = 'chatbot-quota-test'

    def setUp(self):
        super().setUp()
        for field in ['last_quota_warning_at', 'last_quota_limit_at']:
            _chatbot_user_ids_under_quota_pressure.clear(field)
            self.addCleanup(_chatbot_user_ids_under_quota_pressure.clear, field)

    def _web_user_under_pressure(self, name, domain, days_ago, at_limit=True):
        user = WebUser(
            _id=f'{name}-id',
            username=f'{name}@example.com',
            domain_memberships=[DomainMembership(domain=domain)],
            is_active=True,
        )
        user_adapter.index(user, refresh=True)
        timestamp = datetime.now() - timedelta(days=days_ago)
        ChatbotQuotaPressure.objects.create(
            user_id=user.user_id,
            last_quota_warning_at=timestamp,
            last_quota_limit_at=timestamp if at_limit else None,
        )

    def _near_and_at_quota_counts(self):
        ctx = DomainContext(Domain(name=self.domain))
        return _calc_chatbot_users_near_quota_30d(ctx), _calc_chatbot_users_at_quota_30d(ctx)

    def test_counts_domain_web_users_under_pressure_in_last_30_days(self):
        self._web_user_under_pressure('alice', self.domain, days_ago=30)
        self._web_user_under_pressure('bob', self.domain, days_ago=31)
        self._web_user_under_pressure('carol', 'other-domain', days_ago=0)
        assert self._near_and_at_quota_counts() == (1, 1)

    def test_warning_only_does_not_count_as_at_quota(self):
        self._web_user_under_pressure('alice', self.domain, days_ago=0, at_limit=False)
        assert self._near_and_at_quota_counts() == (1, 0)
