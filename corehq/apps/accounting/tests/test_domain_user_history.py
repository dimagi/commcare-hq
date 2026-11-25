import datetime
from unittest import mock

from django.test import TestCase

from corehq.apps.accounting import tasks
from corehq.apps.accounting.models import DomainUserHistory, DomainWebUserHistory
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.domain.tests.test_utils import delete_all_domains


class TestDomainUserHistory(BaseInvoiceTestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_domains()
        super().setUpClass()

    def setUp(self):
        super(TestDomainUserHistory, self).setUp()
        self.num_users = 2
        generator.arbitrary_commcare_users_for_domain(self.domain.name, self.num_users)
        self.today = datetime.date.today()
        self.record_date = self.today - datetime.timedelta(days=1)

    def tearDown(self):
        for user in self.domain.all_users():
            user.delete(self.domain.name, deleted_by=None)
        super(TestDomainUserHistory, self).tearDown()

    def test_domain_user_history(self):
        domain_user_history = DomainUserHistory.objects.create(domain=self.domain.name,
                                                       num_users=self.num_users,
                                                       record_date=self.record_date)
        self.assertEqual(domain_user_history.domain, self.domain.name)
        self.assertEqual(domain_user_history.num_users, self.num_users)
        # DomainUserHistory calculates number of users and assigns to the previous month for statements
        self.assertEqual(domain_user_history.record_date, self.record_date)

    def test_calculate_users_in_all_domains(self):
        tasks.calculate_users_in_all_domains()
        self.assertEqual(DomainUserHistory.objects.count(), 1)
        domain_user_history = DomainUserHistory.objects.first()
        self.assertEqual(domain_user_history.domain, self.domain.name)
        self.assertEqual(domain_user_history.num_users, self.num_users)
        self.assertEqual(domain_user_history.record_date, self.record_date)


class TestCalculateWebUsersInAllDomains(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_1 = generator.arbitrary_domain()
        cls.domain_2 = generator.arbitrary_domain()
        cls.domain_without_web_users = generator.arbitrary_domain()
        for domain in [cls.domain_1, cls.domain_2, cls.domain_without_web_users]:
            cls.addClassCleanup(domain.delete)

    def _get_web_usernames(self, domain):
        if domain == self.domain_1.name:
            return ['a@example.com', 'staff@dimagi.com']
        if domain == self.domain_2.name:
            raise Exception('ES is down')
        return []

    def test_records_usernames_per_domain(self):
        with mock.patch.object(tasks, 'get_web_usernames', side_effect=self._get_web_usernames):
            tasks.calculate_web_users_in_all_domains(datetime.date(2026, 10, 1))

        history = DomainWebUserHistory.objects.get(domain=self.domain_1.name)
        assert history.record_date == datetime.date(2026, 9, 30)
        assert history.usernames == ['a@example.com', 'staff@dimagi.com']
        assert history.num_users == 2

    def test_records_empty_row_for_domain_without_web_users(self):
        with mock.patch.object(tasks, 'get_web_usernames', side_effect=self._get_web_usernames):
            tasks.calculate_web_users_in_all_domains(datetime.date(2026, 10, 1))

        history = DomainWebUserHistory.objects.get(domain=self.domain_without_web_users.name)
        assert (history.usernames, history.num_users) == ([], 0)

    def test_failure_in_one_domain_does_not_stop_others(self):
        with mock.patch.object(tasks, 'get_web_usernames', side_effect=self._get_web_usernames):
            tasks.calculate_web_users_in_all_domains(datetime.date(2026, 10, 1))

        assert not DomainWebUserHistory.objects.filter(domain=self.domain_2.name).exists()
        assert DomainWebUserHistory.objects.filter(domain=self.domain_1.name).exists()
