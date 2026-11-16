from unittest.mock import patch

from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import send_sms
from corehq.apps.sms.models import SMS
from corehq.apps.sms.tests.util import setup_default_sms_test_backend
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend

PHONE_NUMBER = '+99912345678'


class TestSendRequiresMessagingAccess(DomainSubscriptionMixin, TestCase):
    """
    Outbound SMS must not reach a gateway unless the domain has been
    granted messaging access.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'messaging-access-test'
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()
        cls.addClassCleanup(clear_plan_version_cache)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.ADVANCED)
        cls.addClassCleanup(cls.teardown_subscriptions)
        backend, backend_mapping = setup_default_sms_test_backend()
        cls.addClassCleanup(backend.delete)
        cls.addClassCleanup(backend_mapping.delete)

    def setUp(self):
        patcher = patch.object(SQLTestSMSBackend, 'send')
        self.gateway_send = patcher.start()
        self.addCleanup(patcher.stop)

    def set_messaging_access(self, granted):
        self.domain_obj.granted_messaging_access = granted
        self.domain_obj.save()

    def get_sms(self, domain):
        return SMS.objects.get(domain=domain, phone_number=PHONE_NUMBER)

    def test_not_sent_without_messaging_access(self):
        self.set_messaging_access(False)

        assert send_sms(self.domain, None, PHONE_NUMBER, 'hello') is False

        self.gateway_send.assert_not_called()
        sms = self.get_sms(self.domain)
        assert sms.error
        assert sms.system_error_message == SMS.ERROR_MESSAGING_NOT_ENABLED

    def test_sent_with_messaging_access(self):
        self.set_messaging_access(True)

        assert send_sms(self.domain, None, PHONE_NUMBER, 'hello') is True

        self.gateway_send.assert_called_once()
        assert not self.get_sms(self.domain).error

    def test_sent_when_not_tied_to_a_domain(self):
        assert send_sms(None, None, PHONE_NUMBER, 'hello') is True

        self.gateway_send.assert_called_once()
        assert not self.get_sms(None).error


def test_messaging_not_enabled_has_error_message():
    assert SMS.ERROR_MESSAGING_NOT_ENABLED in SMS.ERROR_MESSAGES
