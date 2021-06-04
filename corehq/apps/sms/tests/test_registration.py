import base64
import json

from django.test import Client, TestCase

from django_prbac.models import Role
from mock import Mock, patch

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustment,
)
from corehq.apps.domain.calculations import num_mobile_users
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import incoming
from corehq.apps.sms.models import (
    OUTGOING,
    SMS,
    SQLMobileBackendMapping,
)
from corehq.apps.sms.tests.util import BaseSMSTest, delete_domain_phone_numbers
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend

DUMMY_APP_ODK_URL = 'http://localhost/testapp'
DUMMY_REGISTRATION_URL = 'http://localhost/register'
DUMMY_APP_INFO_URL = 'http://localhost/appinfo'
DUMMY_APP_INFO_URL_B64 = base64.b64encode(DUMMY_APP_INFO_URL.encode('utf-8')).decode('utf-8')


def noop(*args, **kwargs):
    pass


class RegistrationTestCase(BaseSMSTest):

    def setUp(self):
        super(RegistrationTestCase, self).setUp()

        self.domain = 'sms-reg-test-domain'
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()

        self.create_account_and_subscription(self.domain)
        self.domain_obj = Domain.get(self.domain_obj.get_id)

        self.backend = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            is_global=False,
            domain=self.domain,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        SQLMobileBackendMapping.set_default_domain_backend(self.domain, self.backend)

        self.app_id = 'app_id'

    def tearDown(self):
        delete_domain_phone_numbers(self.domain)
        SQLMobileBackendMapping.unset_default_domain_backend(self.domain)
        self.backend.delete()
        self.domain_obj.delete()

        super(RegistrationTestCase, self).tearDown()

    def _get_last_sms(self, count=1, direction=None, phone_number=None):
        result = SMS.objects.filter(domain=self.domain)
        if direction:
            result = result.filter(direction=direction)

        if phone_number:
            result = result.filter(phone_number=phone_number)

        result = result.order_by('-date')
        result = list(result[:count])
        self.assertEqual(len(result), count)
        return result

    def assertLastOutgoingSMS(self, phone_number, expected_texts):
        result = self._get_last_sms(
            count=len(expected_texts),
            direction=OUTGOING,
            phone_number=phone_number
        )
        actual_texts = set([sms.text for sms in result])
        self.assertEqual(actual_texts, set(expected_texts))

    def test_sms_registration(self):
        formatted_username = format_username('tester', self.domain)

        # Test without mobile worker registration enabled
        incoming('+9991234567', 'JOIN {} WORKER tester'.format(self.domain), self.backend.hq_api_id)
        self.assertIsNone(CommCareUser.get_by_username(formatted_username))

        # Test with mobile worker registration enabled
        self.domain_obj.sms_mobile_worker_registration_enabled = True
        self.domain_obj.save()

        incoming('+9991234567', 'JOIN {} WORKER tester'.format(self.domain), self.backend.hq_api_id)
        self.assertIsNotNone(CommCareUser.get_by_username(formatted_username))

        # Test a duplicate registration
        prev_num_users = num_mobile_users(self.domain)
        incoming('+9991234568', 'JOIN {} WORKER tester'.format(self.domain), self.backend.hq_api_id)
        current_num_users = num_mobile_users(self.domain)
        self.assertEqual(prev_num_users, current_num_users)