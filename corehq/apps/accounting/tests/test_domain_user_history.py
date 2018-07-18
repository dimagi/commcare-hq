from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
from dateutil.relativedelta import relativedelta

from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting import tasks
from corehq.apps.accounting.models import DomainUserHistory


class TestDomainUserHistory(BaseInvoiceTestCase):

    def setUp(self):
        super(TestDomainUserHistory, self).setUp()
        self.num_users = 2
        generator.arbitrary_commcare_users_for_domain(self.domain.name, self.num_users)
        self.today = datetime.date.today()

    def tearDown(self):
        for user in self.domain.all_users():
            user.delete()
        import ipdb; ipdb.set_trace()
        for domain_user_history in DomainUserHistory.objects.all():
            domain_user_history.delete()

    def test_domain_user_history(self):
        domain_user_history = DomainUserHistory.create(domain=self.domain.name, num_users=self.num_users)
        self.assertEqual(domain_user_history.domain, self.domain.name)
        self.assertEqual(domain_user_history.num_users, self.num_users)
        self.assertEqual(domain_user_history.record_date, self.today)

    def test_calculate_users_in_all_domains(self):
        tasks.calculate_users_in_all_domains()
        self.assertEqual(DomainUserHistory.objects.count(), 1)
        domain_user_history = DomainUserHistory.objects.first()
        self.assertEqual(domain_user_history.domain, self.domain.name)
        self.assertEqual(domain_user_history.num_users, self.num_users)
        self.assertEqual(domain_user_history.record_date, self.today)

    def test_delete_outdated_domain_user_history(self):
        tasks.calculate_users_in_all_domains()
        self.assertEqual(DomainUserHistory.objects.count(), 1)
        domain_user_history = DomainUserHistory.objects.first()
        domain_user_history.record_date = self.today - relativedelta(years=2)
        domain_user_history.save()

        tasks.delete_outdated_domain_user_history(self.today)
        self.assertEqual(DomainUserHistory.objects.count(), 0)
