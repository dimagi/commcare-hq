from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.domain.models import Domain
from corehq.apps.sms.tests.util import setup_default_sms_test_backend, delete_domain_phone_numbers


class BaseReminderTestCase(BaseAccountingTest, DomainSubscriptionMixin):
    def setUp(self):
        super(BaseReminderTestCase, self).setUp()
        self.domain_obj = Domain(name="test")
        self.domain_obj.save()
        # Prevent resource conflict
        self.domain_obj = Domain.get(self.domain_obj._id)
        self.setup_subscription(self.domain_obj.name, SoftwarePlanEdition.ADVANCED)
        self.sms_backend, self.sms_backend_mapping = setup_default_sms_test_backend()

    def tearDown(self):
        delete_domain_phone_numbers('test')
        self.sms_backend_mapping.delete()
        self.sms_backend.delete()
        self.teardown_subscription()
        self.domain_obj.delete()
